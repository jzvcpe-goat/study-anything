#!/usr/bin/env python3
"""Run mature external Agent eval tools against Study Anything artifacts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import (
    format_api_unreachable,
    redact_diagnostic,
    resolve_api_base,
    verifier_name_from_file,
)


DEFAULT_API_BASE = resolve_api_base()
DEFAULT_PROMPTFOO_VERSION = os.getenv("PROMPTFOO_VERSION", "0.121.15")
DEEPEVAL_SCRIPT = ROOT / "evals" / "deepeval" / "study_anything_quality_eval.py"
VERIFIER_NAME = verifier_name_from_file(__file__)


def output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def redacted_output(value: str | bytes | None, *, limit: int = 2000) -> str:
    text = redact_diagnostic(output_text(value))
    if len(text) <= limit:
        return text
    return text[-limit:]


def redacted_command(command: list[str]) -> str:
    return redact_diagnostic(" ".join(command))


def run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
    )


def request_json(
    api_base: str,
    url: str,
    *,
    timeout_seconds: int,
    parse_error_prefix: str,
) -> dict[str, Any]:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = redacted_output(exc.read(), limit=500)
        safe_url = redact_diagnostic(url)
        raise RuntimeError(f"API returned HTTP {exc.code} for {safe_url}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(format_api_unreachable(api_base, exc, verifier=VERIFIER_NAME)) from exc
    except json.JSONDecodeError as exc:
        safe_url = redact_diagnostic(url)
        raise RuntimeError(f"{parse_error_prefix}: API returned invalid JSON for {safe_url}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"API response must be a JSON object for {redact_diagnostic(url)}.")
    return value


def session_creation_failure(tool: str, exc: BaseException, *, required: bool) -> dict[str, Any]:
    return {
        "status": "failed",
        "tool": tool,
        "reason": redact_diagnostic(str(exc)),
        "required": required,
        "recovery_hint": (
            "Start Study Anything with ./scripts/launch_skill_mode.sh from a normal terminal, "
            "or pass --api-base/ API_BASE for an already running deployment."
        ),
    }


def create_eval_session(api_base: str, timeout_seconds: int) -> str:
    env = os.environ.copy()
    env["API_BASE"] = api_base
    env.setdefault("AGENT_EVAL_REQUEST_TIMEOUT_SECONDS", str(timeout_seconds))
    env.setdefault("AGENT_PROVIDER_TIMEOUT_SECONDS", str(timeout_seconds))
    completed = run(
        [sys.executable, str(ROOT / "scripts" / "verify_agent_eval_flow.py")],
        env=env,
        timeout_seconds=timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Could not create a completed Study Anything eval session.\n"
            f"stdout:\n{redacted_output(completed.stdout)}\n"
            f"stderr:\n{redacted_output(completed.stderr)}"
        )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not parse verify_agent_eval_flow output: {redacted_output(completed.stdout)}"
        ) from exc
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise RuntimeError(f"verify_agent_eval_flow did not return a session_id: {payload}")
    return session_id


def create_retrieval_eval_session(api_base: str, query: str, timeout_seconds: int) -> str:
    env = os.environ.copy()
    env["API_BASE"] = api_base
    completed = run(
        [
            sys.executable,
            str(ROOT / "scripts" / "verify_importer_runtime_retrieval_flow.py"),
            "--query",
            query,
        ],
        env=env,
        timeout_seconds=timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Could not create a Study Anything retrieval eval session.\n"
            f"stdout:\n{redacted_output(completed.stdout)}\n"
            f"stderr:\n{redacted_output(completed.stderr)}"
        )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not parse retrieval eval output from verify_importer_runtime_retrieval_flow: "
            f"{redacted_output(completed.stdout)}"
        ) from exc
    session_id = payload.get("source_session_id")
    if not isinstance(session_id, str) or not session_id:
        raise RuntimeError(
            "verify_importer_runtime_retrieval_flow did not return a source_session_id: "
            f"{payload}"
        )
    return session_id


def promptfoo_command(api_base: str, session_id: str, version: str) -> list[str]:
    return [
        "npx",
        "--yes",
        f"promptfoo@{version}",
        "eval",
        "-c",
        "evals/promptfoo/agent-eval-artifact.yaml",
        "--var",
        f"apiBase={api_base}",
        "--var",
        f"sessionId={session_id}",
    ]


def run_promptfoo(args: argparse.Namespace) -> dict[str, Any]:
    session_id = args.session_id
    if args.create_session or not session_id:
        try:
            session_id = create_eval_session(args.api_base, args.timeout_seconds)
        except RuntimeError as exc:
            return session_creation_failure("promptfoo", exc, required=args.required)

    if shutil.which("npx") is None:
        return {
            "status": "skipped",
            "tool": "promptfoo",
            "reason": "npx is not available; install Node.js or run in CI with setup-node.",
            "required": args.required,
            "session_id": session_id,
        }

    command = promptfoo_command(args.api_base, session_id, args.promptfoo_version)
    try:
        completed = run(command, timeout_seconds=args.timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "skipped",
            "tool": "promptfoo",
            "reason": f"Promptfoo did not finish within {args.timeout_seconds}s.",
            "required": args.required,
            "session_id": session_id,
            "stdout": redacted_output(exc.stdout),
            "stderr": redacted_output(exc.stderr),
            "command": redacted_command(command),
        }

    if completed.returncode != 0:
        return {
            "status": "failed",
            "tool": "promptfoo",
            "reason": "Promptfoo returned a non-zero exit code.",
            "returncode": completed.returncode,
            "session_id": session_id,
            "stdout": redacted_output(completed.stdout),
            "stderr": redacted_output(completed.stderr),
            "command": redacted_command(command),
        }

    return {
        "status": "ok",
        "tool": "promptfoo",
        "version": args.promptfoo_version,
        "session_id": session_id,
        "stdout_tail": redacted_output(completed.stdout),
        "stderr_tail": redacted_output(completed.stderr),
    }


def run_deepeval(args: argparse.Namespace) -> dict[str, Any]:
    session_id = args.session_id
    if args.create_session or not session_id:
        try:
            session_id = create_eval_session(args.api_base, args.timeout_seconds)
        except RuntimeError as exc:
            return session_creation_failure("deepeval", exc, required=args.required)

    command = [
        sys.executable,
        str(DEEPEVAL_SCRIPT),
        "--api-base",
        args.api_base,
        "--session-id",
        session_id,
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    if args.allow_native_quality_fallback:
        command.append("--allow-native-fallback")
    try:
        completed = run(command, timeout_seconds=args.timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "skipped",
            "tool": "deepeval",
            "reason": f"DeepEval adapter did not finish within {args.timeout_seconds}s.",
            "required": args.required,
            "session_id": session_id,
            "stdout": redacted_output(exc.stdout),
            "stderr": redacted_output(exc.stderr),
            "command": redacted_command(command),
        }
    if completed.returncode != 0:
        return {
            "status": "failed",
            "tool": "deepeval",
            "reason": "DeepEval adapter returned a non-zero exit code.",
            "returncode": completed.returncode,
            "session_id": session_id,
            "stdout": redacted_output(completed.stdout),
            "stderr": redacted_output(completed.stderr),
            "command": redacted_command(command),
        }
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        return {
            "status": "failed",
            "tool": "deepeval",
            "reason": f"Could not parse DeepEval adapter output: {exc}",
            "diagnostic_code": "deepeval_parse_error",
            "session_id": session_id,
            "stdout": redacted_output(completed.stdout),
            "stderr": redacted_output(completed.stderr),
        }
    return payload


def run_retrieval_eval(args: argparse.Namespace) -> dict[str, Any]:
    session_id = args.session_id
    if args.create_session or not session_id:
        try:
            session_id = create_retrieval_eval_session(
                args.api_base,
                args.query,
                args.timeout_seconds,
            )
        except RuntimeError as exc:
            return session_creation_failure("retrieval", exc, required=args.required)
    query = urlencode({"q": args.query, "limit": args.limit})
    path = (
        f"{args.api_base.rstrip('/')}/v1/sessions/{session_id}/retrieval/eval"
        f"?{query}"
    )
    try:
        report = request_json(
            args.api_base,
            path,
            timeout_seconds=args.timeout_seconds,
            parse_error_prefix="Could not parse retrieval eval output",
        )
    except RuntimeError as exc:
        return {
            "status": "failed",
            "tool": "retrieval",
            "reason": redact_diagnostic(str(exc)),
            "diagnostic_code": "retrieval_parse_error"
            if "Could not parse retrieval eval output" in str(exc)
            else "retrieval_eval_request_failed",
            "session_id": session_id,
        }
    if report.get("schema_version") != "retrieval-quality-eval-v1":
        return {
            "status": "failed",
            "tool": "retrieval",
            "reason": f"Unexpected retrieval eval schema: {report.get('schema_version')}",
            "session_id": session_id,
            "report": report,
        }
    return {
        "status": "ok" if report.get("status") == "pass" else "failed",
        "tool": "retrieval",
        "framework": "ragas-compatible-native",
        "session_id": session_id,
        "query": args.query,
        "quality_score": report.get("quality_score"),
        "threshold": report.get("threshold"),
        "report_status": report.get("status"),
        "schema_version": "study-anything-retrieval-eval-result-v1",
        "privacy": report.get("privacy"),
    }


def run_agent_eval_report(args: argparse.Namespace) -> dict[str, Any]:
    session_id = args.session_id
    if args.create_session or not session_id:
        try:
            session_id = create_eval_session(args.api_base, args.timeout_seconds)
        except RuntimeError as exc:
            return session_creation_failure("report", exc, required=args.required)
    path = f"{args.api_base.rstrip('/')}/v1/sessions/{session_id}/agent-eval/report"
    try:
        report = request_json(
            args.api_base,
            path,
            timeout_seconds=args.timeout_seconds,
            parse_error_prefix="Could not parse Agent eval report output",
        )
    except RuntimeError as exc:
        return {
            "status": "failed",
            "tool": "report",
            "reason": redact_diagnostic(str(exc)),
            "diagnostic_code": "agent_eval_report_parse_error"
            if "Could not parse Agent eval report output" in str(exc)
            else "agent_eval_report_request_failed",
            "session_id": session_id,
        }
    if report.get("schema_version") != "agent-eval-report-v1":
        return {
            "status": "failed",
            "tool": "report",
            "reason": f"Unexpected Agent eval report schema: {report.get('schema_version')}",
            "session_id": session_id,
            "report": report,
        }
    native_gate = report.get("native_fast_gate") or {}
    report_status = str(report.get("status") or "")
    return {
        "status": "ok"
        if native_gate.get("status") == "pass" and report_status.startswith("pass")
        else "failed",
        "tool": "report",
        "framework": "study-anything-native-maturity-report",
        "session_id": session_id,
        "report_status": report.get("status"),
        "schema_version": report.get("schema_version"),
        "native_fast_gate": native_gate,
        "privacy": report.get("privacy"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tool",
        choices=["promptfoo", "deepeval", "retrieval", "report"],
        default="promptfoo",
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--session-id", default=os.getenv("SESSION_ID"))
    parser.add_argument(
        "--create-session",
        action="store_true",
        help="Run scripts/verify_agent_eval_flow.py first and evaluate the completed session.",
    )
    parser.add_argument(
        "--required",
        action="store_true",
        help="Return non-zero when the external eval tool is unavailable, times out, or fails.",
    )
    parser.add_argument("--promptfoo-version", default=DEFAULT_PROMPTFOO_VERSION)
    parser.add_argument(
        "--query",
        default="AI product learning feedback vocabulary",
        help="For --tool retrieval, query used when creating or evaluating a retrieval session.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="For --tool retrieval, maximum retrieval results to score.",
    )
    parser.add_argument(
        "--allow-native-quality-fallback",
        action="store_true",
        help="For --tool deepeval, allow the deterministic quality report when deepeval is absent.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("EXTERNAL_EVAL_TIMEOUT_SECONDS", "180")),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.tool == "promptfoo":
        result = run_promptfoo(args)
    elif args.tool == "deepeval":
        result = run_deepeval(args)
    elif args.tool == "retrieval":
        result = run_retrieval_eval(args)
    else:
        result = run_agent_eval_report(args)
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] == "failed" or (args.required and result["status"] != "ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
