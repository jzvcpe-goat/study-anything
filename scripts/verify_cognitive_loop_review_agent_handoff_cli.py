#!/usr/bin/env python3
"""Verify the external Review Agent handoff CLI and redacted validation path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_review_agent_handoff.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-handoff-cli.json"
FIXTURE_DIR = ROOT / "fixtures" / "review-agent"
SCHEMA_VERSION = "cognitive-loop-review-agent-handoff-cli-v1"


class ReviewAgentHandoffCliVerificationError(RuntimeError):
    """Readable handoff CLI verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentHandoffCliVerificationError(message)


def run(args: list[str], *, cwd: Path, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if expect_success and completed.returncode != 0:
        raise ReviewAgentHandoffCliVerificationError(
            f"Command failed: {' '.join(args)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    if not expect_success and completed.returncode == 0:
        raise ReviewAgentHandoffCliVerificationError(f"Command unexpectedly passed: {' '.join(args)}")
    return completed


def init_temp_repo(tmp: Path) -> None:
    run(["git", "init", "-q"], cwd=tmp)
    run(["git", "config", "user.email", "review-agent@example.invalid"], cwd=tmp)
    run(["git", "config", "user.name", "Review Agent Fixture"], cwd=tmp)
    source = tmp / "app.py"
    source.write_text(
        "def add_one(value):\n"
        "    return value + 1\n",
        encoding="utf-8",
    )
    run(["git", "add", "app.py"], cwd=tmp)
    run(["git", "commit", "-q", "-m", "base"], cwd=tmp)
    source.write_text(
        "def add_one(value):\n"
        "    if value is None:\n"
        "        return 1\n"
        "    return value + 1\n",
        encoding="utf-8",
    )


def parse_json_output(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        payload = json.loads(completed.stdout)
    except Exception as exc:
        raise ReviewAgentHandoffCliVerificationError(f"Invalid JSON output: {completed.stdout}") from exc
    if not isinstance(payload, dict):
        raise ReviewAgentHandoffCliVerificationError("JSON object output expected.")
    return payload


def verify_prepare_stdout(tmp: Path) -> dict[str, Any]:
    completed = run(
        [
            sys.executable,
            str(CLI),
            "prepare",
            "--root",
            str(tmp),
            "--pr-id",
            "fixture-pr",
            "--title",
            "Fixture review",
            "--description",
            "Synthetic local-only diff for handoff CLI verification.",
        ],
        cwd=ROOT,
    )
    request = parse_json_output(completed)
    review_input = request.get("review_input", {})
    require(request.get("schema_version") == "cognitive-loop-review-agent-handoff-request-v1", "Request schema drifted.")
    require("diff --git" in review_input.get("git_diff", ""), "Prepare request must include the operator-provided raw diff.")
    require(review_input.get("diff_sha256"), "Prepare request must include a diff hash.")
    require(request.get("privacy_boundary", {}).get("study_anything_may_persist_raw_diff") is False, "Raw diff persistence boundary drifted.")
    require(
        request.get("final_report_schema", {}).get("$id")
        == "https://study-anything.local/schemas/cognitive-loop-review-agent-report-v1.json",
        "Final report schema id missing from handoff request.",
    )
    return {
        "schema_version": request["schema_version"],
        "changed_files": review_input.get("changed_files", []),
        "diff_sha256": review_input["diff_sha256"],
        "stdout_json": "pass",
    }


def verify_prepare_output_dir_guard(tmp: Path) -> dict[str, Any]:
    rejected = run(
        [
            sys.executable,
            str(CLI),
            "prepare",
            "--root",
            str(tmp),
            "--output-dir",
            str(tmp / "handoff"),
        ],
        cwd=ROOT,
        expect_success=False,
    )
    require("Refusing to write raw-diff handoff material" in rejected.stderr, "Repo output refusal message drifted.")

    allowed_dir = tmp.parent / "review-agent-handoff-allowed"
    written = parse_json_output(
        run(
            [
                sys.executable,
                str(CLI),
                "prepare",
                "--root",
                str(tmp),
                "--output-dir",
                str(allowed_dir),
            ],
            cwd=ROOT,
        )
    )
    files = written.get("files", {})
    required = {
        "request": "review-agent-handoff-request.json",
        "prompt": "review-agent-prompt-contract.json",
        "schema": "review-agent-report-schema.json",
        "readme": "README.md",
    }
    for key, suffix in required.items():
        path = Path(files.get(key, ""))
        require(path.name == suffix and path.is_file(), f"Missing handoff output file: {key}")
    return {
        "repo_output_default_refusal": "pass",
        "temp_output_files": sorted(required.values()),
    }


def verify_validate() -> dict[str, Any]:
    accepted = parse_json_output(
        run(
            [
                sys.executable,
                str(CLI),
                "validate",
                "--report",
                str(FIXTURE_DIR / "needs-review.json"),
            ],
            cwd=ROOT,
        )
    )
    require(accepted.get("schema_version") == "cognitive-loop-review-agent-handoff-validation-v1", "Validation schema drifted.")
    require(accepted.get("status") == "pass", "Accepted fixture validation failed.")
    require(accepted.get("report_summary", {}).get("decision") == "needs-review", "Accepted fixture decision drifted.")
    require(accepted.get("privacy", {}).get("validation_summary_safe_to_store") is True, "Validation summary privacy drifted.")

    rejected = run(
        [
            sys.executable,
            str(CLI),
            "validate",
            "--report",
            str(FIXTURE_DIR / "invalid-low-confidence-final.json"),
        ],
        cwd=ROOT,
        expect_success=False,
    )
    require("final finding confidence" in rejected.stderr, "Invalid fixture rejection reason drifted.")
    return {
        "accepted_fixture": "needs-review.json",
        "accepted_decision": accepted["report_summary"]["decision"],
        "invalid_low_confidence_rejected": "pass",
    }


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-handoff-") as tmp_name:
        tmp = Path(tmp_name)
        repo = tmp / "repo"
        repo.mkdir()
        init_temp_repo(repo)
        prepare_stdout = verify_prepare_stdout(repo)
        prepare_output_dir = verify_prepare_output_dir_guard(repo)
    validate_report = verify_validate()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "cli": "scripts/cognitive_loop_review_agent_handoff.py",
        "prepare": {
            **prepare_stdout,
            **prepare_output_dir,
        },
        "validate": validate_report,
        "privacy": {
            "prepare_request_contains_raw_diff": True,
            "raw_diff_written_to_platform_generated": False,
            "raw_diff_written_to_cognitive_loop_events": False,
            "validation_summary_contains_raw_diff": False,
            "validation_summary_safe_to_store": True,
            "real_model_keys_stored_by_study_anything": False,
            "private_agent_endpoints_stored_by_study_anything": False,
        },
        "acceptance": {
            "minimum_prepare_command": "python3 scripts/cognitive_loop_review_agent_handoff.py prepare --base main --head HEAD",
            "minimum_validate_command": "python3 scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json",
            "release_gate": "python3 scripts/verify_cognitive_loop_review_agent_handoff_cli.py --check",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop Review Agent handoff CLI report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent handoff CLI report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_handoff_cli.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentHandoffCliVerificationError as exc:
        raise SystemExit(f"error: {exc}") from exc
