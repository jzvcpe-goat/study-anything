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


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_PROMPTFOO_VERSION = os.getenv("PROMPTFOO_VERSION", "0.121.15")
DEEPEVAL_SCRIPT = ROOT / "evals" / "deepeval" / "study_anything_quality_eval.py"


def output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


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
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not parse verify_agent_eval_flow output: {completed.stdout}"
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
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not parse verify_importer_runtime_retrieval_flow output: {completed.stdout}"
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
        session_id = create_eval_session(args.api_base, args.timeout_seconds)

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
            "stdout": output_text(exc.stdout),
            "stderr": output_text(exc.stderr),
            "command": " ".join(command),
        }

    if completed.returncode != 0:
        return {
            "status": "failed",
            "tool": "promptfoo",
            "reason": "Promptfoo returned a non-zero exit code.",
            "returncode": completed.returncode,
            "session_id": session_id,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "command": " ".join(command),
        }

    return {
        "status": "ok",
        "tool": "promptfoo",
        "version": args.promptfoo_version,
        "session_id": session_id,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def run_deepeval(args: argparse.Namespace) -> dict[str, Any]:
    session_id = args.session_id
    if args.create_session or not session_id:
        session_id = create_eval_session(args.api_base, args.timeout_seconds)

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
            "stdout": output_text(exc.stdout),
            "stderr": output_text(exc.stderr),
            "command": " ".join(command),
        }
    if completed.returncode != 0:
        return {
            "status": "failed",
            "tool": "deepeval",
            "reason": "DeepEval adapter returned a non-zero exit code.",
            "returncode": completed.returncode,
            "session_id": session_id,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "command": " ".join(command),
        }
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        return {
            "status": "failed",
            "tool": "deepeval",
            "reason": f"Could not parse DeepEval adapter output: {exc}",
            "session_id": session_id,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    return payload


def run_retrieval_eval(args: argparse.Namespace) -> dict[str, Any]:
    session_id = args.session_id
    if args.create_session or not session_id:
        session_id = create_retrieval_eval_session(
            args.api_base,
            args.query,
            args.timeout_seconds,
        )
    query = urlencode({"q": args.query, "limit": args.limit})
    path = (
        f"{args.api_base.rstrip('/')}/v1/sessions/{session_id}/retrieval/eval"
        f"?{query}"
    )
    completed = run(
        [
            sys.executable,
            "-c",
            (
                "import json,sys,urllib.request;"
                "u=sys.argv[1];"
                "print(urllib.request.urlopen(u, timeout=int(sys.argv[2])).read().decode())"
            ),
            path,
            str(args.timeout_seconds),
        ],
        timeout_seconds=args.timeout_seconds,
    )
    if completed.returncode != 0:
        return {
            "status": "failed",
            "tool": "retrieval",
            "reason": "Retrieval eval endpoint returned a non-zero exit code.",
            "returncode": completed.returncode,
            "session_id": session_id,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    try:
        report = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        return {
            "status": "failed",
            "tool": "retrieval",
            "reason": f"Could not parse retrieval eval output: {exc}",
            "session_id": session_id,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tool",
        choices=["promptfoo", "deepeval", "retrieval"],
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
    else:
        result = run_retrieval_eval(args)
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] == "failed" or (args.required and result["status"] != "ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
