#!/usr/bin/env python3
"""Verify deterministic Cognitive Loop recipe CLI failure receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli-failures.json"
CLI = ROOT / "scripts" / "cognitive_loop_recipe_cli.py"
TMP_DIR = ROOT / "platform" / "generated"

SCHEMA_VERSION = "cognitive-loop-recipe-cli-failures-v1"
CLI_SCHEMA_VERSION = "cognitive-loop-recipe-cli-v1"
SOURCE_SCHEMA_VERSION = "cognitive-loop-adoption-recipes-v1"
PRIVATE_NEEDLES = (
    "sk-proj-",
    "bearer ",
    "api_key",
    "secret_access_key",
    "raw private source text",
    "learner answer:",
    "http://127.0.0.1:8787/",
)


class RecipeCliFailureError(RuntimeError):
    """Readable recipe CLI failure verification error."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def reject_private_text(value: str, *, label: str) -> None:
    lowered = value.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle in lowered]
    if leaked:
        raise RecipeCliFailureError(f"{label} contains private or secret-like text: {leaked}")


def run_cli(args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(ROOT),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_failure_case(
    *,
    case_id: str,
    args: tuple[str, ...],
    expected_message: str,
    expected_diagnostic: str,
) -> dict[str, Any]:
    completed = run_cli(args)
    if completed.returncode == 0:
        raise RecipeCliFailureError(f"{case_id} unexpectedly succeeded.")
    if completed.stdout:
        raise RecipeCliFailureError(f"{case_id} must not write stdout on failure.")
    reject_private_text(completed.stderr, label=f"{case_id}.stderr")
    if expected_message not in completed.stderr:
        raise RecipeCliFailureError(f"{case_id} stderr drifted: {completed.stderr!r}")
    return {
        "case_id": case_id,
        "command": "python3 scripts/cognitive_loop_recipe_cli.py " + " ".join(args),
        "exit_code": completed.returncode,
        "stdout_empty": completed.stdout == "",
        "stderr": completed.stderr,
        "stderr_sha256": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
        "diagnostic_code": expected_diagnostic,
        "expected_message": expected_message,
        "safe_to_attach_to_issue": True,
    }


def write_temp_recipes(payload: dict[str, Any]) -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        prefix="recipe-cli-negative-",
        dir=str(TMP_DIR),
        delete=False,
    )
    path = Path(handle.name)
    try:
        with handle:
            handle.write(dump_json(payload))
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def run_temp_failure_case(
    *,
    case_id: str,
    payload: dict[str, Any],
    expected_message: str,
    expected_diagnostic: str,
) -> dict[str, Any]:
    path = write_temp_recipes(payload)
    try:
        rel = path.relative_to(ROOT).as_posix()
        result = run_failure_case(
            case_id=case_id,
            args=("--recipes", rel, "list"),
            expected_message=expected_message,
            expected_diagnostic=expected_diagnostic,
        )
        result["command"] = "python3 scripts/cognitive_loop_recipe_cli.py --recipes <temporary-negative-fixture> list"
        return result
    finally:
        path.unlink(missing_ok=True)


def build_report() -> dict[str, Any]:
    cases = [
        run_failure_case(
            case_id="unknown_recipe_id",
            args=("show", "not_a_recipe"),
            expected_message="Unknown recipe_id: not_a_recipe",
            expected_diagnostic="unknown_recipe_id",
        ),
        run_temp_failure_case(
            case_id="source_schema_drift",
            payload={"schema_version": "unexpected-schema", "status": "pass", "recipes": []},
            expected_message="Cognitive Loop adoption recipes schema drifted.",
            expected_diagnostic="source_schema_drift",
        ),
        run_temp_failure_case(
            case_id="source_status_failed",
            payload={"schema_version": SOURCE_SCHEMA_VERSION, "status": "fail", "recipes": []},
            expected_message="Cognitive Loop adoption recipes must have status=pass.",
            expected_diagnostic="source_status_failed",
        ),
        run_temp_failure_case(
            case_id="empty_recipe_matrix",
            payload={"schema_version": SOURCE_SCHEMA_VERSION, "status": "pass", "recipes": []},
            expected_message="Cognitive Loop adoption recipes are empty.",
            expected_diagnostic="empty_recipe_matrix",
        ),
    ]
    if not all(case["exit_code"] != 0 and case["stdout_empty"] for case in cases):
        raise RecipeCliFailureError("All recipe CLI failure cases must exit non-zero with empty stdout.")
    if len({case["diagnostic_code"] for case in cases}) != len(cases):
        raise RecipeCliFailureError("Recipe CLI failure diagnostic codes must be unique.")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Document deterministic read-only Cognitive Loop recipe CLI failure behavior for platform Agents.",
        "cli": {
            "path": "scripts/cognitive_loop_recipe_cli.py",
            "success_schema_version": CLI_SCHEMA_VERSION,
            "failure_surface": "nonzero_exit_with_redacted_stderr",
        },
        "coverage": {
            "case_count": len(cases),
            "case_ids": [case["case_id"] for case in cases],
            "all_exit_nonzero": True,
            "all_stdout_empty": True,
            "all_stderr_redacted": True,
            "all_safe_to_attach_to_issue": True,
        },
        "cases": cases,
        "safe_failure_policy": {
            "invokes_recipe_cli_only": True,
            "executes_recipe_commands": False,
            "starts_runtime": False,
            "applies_file_changes": False,
            "writes_only_temporary_negative_fixtures": True,
            "temporary_negative_fixtures_removed": True,
        },
        "privacy": {
            "raw_source_text_included": False,
            "diff_bodies_included": False,
            "learner_answers_included": False,
            "grading_feedback_included": False,
            "generated_private_insights_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "real_model_keys_stored": False,
            "browser_video_app_private_context_included": False,
        },
        "commands": {
            "verify": "python3 scripts/verify_cognitive_loop_recipe_cli_failures.py --check",
            "write": "python3 scripts/verify_cognitive_loop_recipe_cli_failures.py --write",
            "sample_failure": "python3 scripts/cognitive_loop_recipe_cli.py show not_a_recipe",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
            raise SystemExit(f"Cognitive Loop recipe CLI failure report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop recipe CLI failure report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_recipe_cli_failures.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_recipe_cli_failures failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
