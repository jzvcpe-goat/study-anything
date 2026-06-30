#!/usr/bin/env python3
"""Verify the WorkBuddy inline learning flow."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_FIXTURE = ROOT / "fixtures" / "workbuddy-learning-flow" / "deepseek-pm-interview" / "input.json"
BOUNDARY_FIXTURE = ROOT / "fixtures" / "workbuddy-learning-flow" / "deepseek-pm-interview" / "expected-boundary.json"
OUTPUT_SCHEMA = ROOT / "platform" / "schemas" / "workbuddy-learning-output-v1.schema.json"
INPUT_SCHEMA = ROOT / "platform" / "schemas" / "workbuddy-learning-input-v1.schema.json"
REPORT_PATH = ROOT / "platform" / "generated" / "study-anything-workbuddy-inline-learning-flow.json"
SCHEMA_VERSION = "workbuddy-inline-learning-flow-verification-v1"

SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s,'\"<>]+"),
)
PROXY_ENV = {
    "HTTP_PROXY": "http://127.0.0.1:55264",
    "HTTPS_PROXY": "http://127.0.0.1:55264",
    "http_proxy": "http://127.0.0.1:55264",
    "https_proxy": "http://127.0.0.1:55264",
    "ALL_PROXY": "http://127.0.0.1:55264",
    "all_proxy": "http://127.0.0.1:55264",
}


class WorkBuddyInlineVerifierError(RuntimeError):
    """Readable verifier failure."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise WorkBuddyInlineVerifierError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkBuddyInlineVerifierError(f"JSON object expected: {path.relative_to(ROOT)}")
    return payload


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def assert_no_private_text(label: str, text: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise WorkBuddyInlineVerifierError(f"{label} contains private-looking text: {pattern.pattern}")
    boundary = read_json(BOUNDARY_FIXTURE)
    for forbidden in boundary.get("forbidden_output_text", []):
        if str(forbidden) in text:
            raise WorkBuddyInlineVerifierError(f"{label} leaked forbidden text: {forbidden}")


def proxied_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(PROXY_ENV)
    env["PYTHONPATH"] = str(ROOT / "apps" / "api")
    return env


def run_cli_in_temp(command_args: list[str], *, input_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-workbuddy-inline-") as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "input.json"
        output_path = tmp_path / "out.json"
        markdown_path = tmp_path / "out.md"
        if input_payload is not None:
            input_path.write_text(dump_json(input_payload), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "workbuddy_learning_flow.py"),
                *[
                    str(input_path) if value == "{input}" else value
                    for value in command_args
                ],
                "--output",
                str(output_path),
                "--markdown",
                str(markdown_path),
            ],
            cwd=tmp_path,
            env=proxied_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise WorkBuddyInlineVerifierError(
                f"workbuddy_learning_flow.py failed rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        if not output_path.is_file() or not markdown_path.is_file():
            raise WorkBuddyInlineVerifierError("Inline flow did not write expected temp outputs.")
        if (tmp_path / ".workbuddy").exists():
            raise WorkBuddyInlineVerifierError("Inline flow should not create .workbuddy during verification.")
        stdout_payload = json.loads(result.stdout)
        file_payload = read_json(output_path)
        if stdout_payload != file_payload:
            raise WorkBuddyInlineVerifierError("CLI stdout and --output JSON differ.")
        assert_no_private_text("inline stdout", result.stdout)
        assert_no_private_text("inline markdown", markdown_path.read_text(encoding="utf-8"))
        return file_payload


def run_demo_in_temp() -> dict[str, Any]:
    return run_cli_in_temp(["demo", "--case", "deepseek-pm-interview"])


def run_platform_agent_input_in_temp() -> dict[str, Any]:
    payload = read_json(INPUT_FIXTURE)
    payload["agent_evidence"] = {
        "generated_by_platform_agent": True,
        "mode": "platform_agent",
        "model_label": "Kimi model via WorkBuddy",
        "platform_agent": "WorkBuddy",
    }
    return run_cli_in_temp(["run", "--input", "{input}"], input_payload=payload)


def verify_run_rejects_deterministic_input() -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-workbuddy-inline-negative-") as tmp:
        tmp_path = Path(tmp)
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "workbuddy_learning_flow.py"),
                "run",
                "--input",
                str(INPUT_FIXTURE),
            ],
            cwd=tmp_path,
            env=proxied_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            raise WorkBuddyInlineVerifierError("Real run accepted deterministic fixture input.")
        if "generated_by_platform_agent=true" not in result.stderr:
            raise WorkBuddyInlineVerifierError("Real run rejection did not explain missing WorkBuddy/Kimi agent evidence.")


def verify_low_quality_input_is_rejected() -> None:
    payload = read_json(INPUT_FIXTURE)
    payload["agent_evidence"] = {
        "generated_by_platform_agent": True,
        "mode": "platform_agent",
        "model_label": "Kimi model via WorkBuddy",
        "platform_agent": "WorkBuddy",
    }
    payload["workbuddy_teaching"]["overview"][0]["text"] = "DeepSeek is a key idea in this source."
    with tempfile.TemporaryDirectory(prefix="study-anything-workbuddy-inline-quality-") as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "bad.json"
        input_path.write_text(dump_json(payload), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "workbuddy_learning_flow.py"),
                "run",
                "--input",
                str(input_path),
            ],
            cwd=tmp_path,
            env=proxied_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            raise WorkBuddyInlineVerifierError("Low-quality WorkBuddy teaching placeholder was accepted.")
        if "placeholder teaching text" not in result.stderr:
            raise WorkBuddyInlineVerifierError("Low-quality rejection did not identify placeholder teaching text.")


def verify_schema_files() -> None:
    for path, schema_version in (
        (INPUT_SCHEMA, "workbuddy-learning-input-v1"),
        (OUTPUT_SCHEMA, "workbuddy-learning-output-v1"),
    ):
        payload = read_json(path)
        if payload.get("$id") != schema_version:
            raise WorkBuddyInlineVerifierError(f"{path.relative_to(ROOT)} must use $id {schema_version}")
        if payload.get("properties", {}).get("schema_version", {}).get("const") != schema_version:
            raise WorkBuddyInlineVerifierError(f"{path.relative_to(ROOT)} must pin schema_version const.")


def verify_output(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != "workbuddy-learning-output-v1":
        raise WorkBuddyInlineVerifierError("Output schema_version drifted.")
    runtime = payload.get("runtime") or {}
    boundary = read_json(BOUNDARY_FIXTURE)
    for key, expected in boundary["required_output_flags"].items():
        if runtime.get(key) is not expected:
            raise WorkBuddyInlineVerifierError(f"runtime.{key} must be {expected}.")
    if runtime.get("data_dir_strategy") != "workspace_dot_workbuddy":
        raise WorkBuddyInlineVerifierError("Default data_dir_strategy should be workspace_dot_workbuddy.")
    if runtime.get("proxy_env_removed_count", 0) < len(PROXY_ENV):
        raise WorkBuddyInlineVerifierError("Inline flow should sanitize proxy env vars without requiring env -u.")
    if payload.get("package_type") != "credential-free-source-bound-learning-package":
        raise WorkBuddyInlineVerifierError("Output package_type drifted.")
    text = dump_json(payload)
    assert_no_private_text("inline output", text)
    for term in boundary["minimum_terms"]:
        if str(term) not in text:
            raise WorkBuddyInlineVerifierError(f"Output missing quality term: {term}")
    if "MoE" not in text or "R1" not in text or "product metric" not in text:
        raise WorkBuddyInlineVerifierError("DeepSeek PM fixture quality boundary is too weak.")
    if not payload.get("answer_refs") or "answers" in text:
        raise WorkBuddyInlineVerifierError("Output should expose answer_refs, not raw answer bodies.")
    source_claims = [
        item
        for item in payload.get("study_card", {}).get("overview", [])
        if item.get("claim_type") in {"source_bound", "factual"}
    ]
    if not source_claims or any(not item.get("evidence_refs") for item in source_claims):
        raise WorkBuddyInlineVerifierError("Source-bound claims must carry evidence_refs.")
    quality = payload.get("quality_gate") or {}
    if quality.get("placeholder_phrases_rejected") is not True:
        raise WorkBuddyInlineVerifierError("Output quality_gate must reject placeholder teaching phrases.")
    return {
        "session_ref": payload.get("session_ref"),
        "source_count": len(payload.get("source_refs", [])),
        "quiz_count": len(payload.get("quiz_items", [])),
        "grading_count": len(payload.get("grading_summary", [])),
        "mastery": payload.get("mastery"),
        "agent_evidence": payload.get("agent_evidence"),
    }


def build_report() -> dict[str, Any]:
    verify_schema_files()
    demo_output = run_demo_in_temp()
    demo_summary = verify_output(demo_output)
    output = run_platform_agent_input_in_temp()
    summary = verify_output(output)
    verify_run_rejects_deterministic_input()
    verify_low_quality_input_is_rejected()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "mode": "workbuddy_inline",
        "fixture": "deepseek-pm-interview",
        "summary": summary,
        "deterministic_demo_summary": demo_summary,
        "runtime_boundary": {
            "http_server_started": False,
            "localhost_required": False,
            "background_process_required": False,
            "proxy_sensitive": False,
            "real_model_key_required": False,
            "model_calls_performed_by_study_anything": False,
        },
        "privacy": {
            "credential_free": True,
            "raw_source_in_report": False,
            "raw_answer_in_report": False,
            "local_absolute_paths_in_report": False,
        },
        "quality": {
            "real_run_requires_platform_agent_evidence": True,
            "deterministic_demo_cannot_be_used_as_real_run": True,
            "low_quality_placeholder_rejected": True,
            "manual_env_unset_required": False,
        },
        "verification_command": "python3 scripts/verify_workbuddy_inline_learning_flow.py --check",
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(serialized, encoding="utf-8")
    if args.check:
        if not REPORT_PATH.is_file():
            raise SystemExit(f"Missing report: {REPORT_PATH.relative_to(ROOT)}")
        if REPORT_PATH.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "WorkBuddy inline learning report is stale. "
                "Run: python3 scripts/verify_workbuddy_inline_learning_flow.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_workbuddy_inline_learning_flow failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
