#!/usr/bin/env python3
"""Verify negative fixtures for Cognitive Loop recipe CLI JSON Schemas."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

from verify_cognitive_loop_recipe_cli_schemas import (
    FAILURES_REPORT,
    PR_CI_RECEIPT_REPORT,
    RECEIPTS_REPORT,
    REPORT as SCHEMA_BUNDLE_REPORT,
    ROOT,
    SCHEMA_VERSION as SCHEMA_BUNDLE_VERSION,
    SUCCESS_REPORT,
    RecipeCliSchemaError,
    build_schemas,
    default_pr_ci_source,
    dump_json,
    load_json,
    reject_private_text,
    validate_instance,
)


REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json"
)
SCHEMA_VERSION = "cognitive-loop-recipe-cli-schema-negative-fixtures-v1"
CASE_IDS = (
    "success_wrong_schema_version",
    "success_auto_execute_true",
    "receipts_missing_privacy",
    "failures_exit_code_string",
    "pr_ci_receipt_missing_required_checks",
    "pr_ci_receipt_github_tokens_true",
    "pr_ci_source_unsupported_source",
    "pr_ci_source_unsafe_url_query",
    "pr_ci_source_raw_logs_true",
    "pr_ci_source_unsafe_command",
    "private_text_probe_rejected",
)


class SchemaNegativeFixtureError(RuntimeError):
    """Readable schema negative-fixture verification failure."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact_schema_error(message: str) -> str:
    reject_private_text(message, label="schema negative fixture error")
    return sha256_text(message)


def mutate_success_wrong_schema_version(payload: dict[str, Any]) -> None:
    payload["schema_version"] = "unexpected-schema"


def mutate_success_auto_execute_true(payload: dict[str, Any]) -> None:
    payload["cli_outputs"]["plans"][0]["safe_to_auto_execute"] = True


def mutate_receipts_missing_privacy(payload: dict[str, Any]) -> None:
    payload.pop("privacy", None)


def mutate_failures_exit_code_string(payload: dict[str, Any]) -> None:
    payload["cases"][0]["exit_code"] = "1"


def mutate_pr_ci_receipt_missing_required_checks(payload: dict[str, Any]) -> None:
    payload["required_checks"] = ["api-tests"]


def mutate_pr_ci_receipt_github_tokens_true(payload: dict[str, Any]) -> None:
    payload["privacy_flags"]["github_tokens_included"] = True


def mutate_pr_ci_source_unsupported_source(payload: dict[str, Any]) -> None:
    payload["source"] = "webhook"


def mutate_pr_ci_source_unsafe_url_query(payload: dict[str, Any]) -> None:
    payload["checks"][0]["url"] = "https://github.com/jzvcpe-goat/study-anything/actions/runs/1?token=leak"


def mutate_pr_ci_source_raw_logs_true(payload: dict[str, Any]) -> None:
    payload["raw_logs_included"] = True


def mutate_pr_ci_source_unsafe_command(payload: dict[str, Any]) -> None:
    payload["operator_next_commands"][0] = "gh pr merge 180 --merge"


def expect_schema_rejection(
    *,
    case_id: str,
    schema_key: str,
    schema: dict[str, Any],
    source_path: Path | None,
    source_payload: dict[str, Any],
    mutation: str,
    mutate: Callable[[dict[str, Any]], None],
    expected_error_contains: str,
) -> dict[str, Any]:
    payload = copy.deepcopy(source_payload)
    mutate(payload)
    try:
        validate_instance(payload, schema, path=f"${schema_key}")
    except RecipeCliSchemaError as exc:
        message = str(exc)
        if expected_error_contains not in message:
            raise SchemaNegativeFixtureError(
                f"{case_id} expected error containing {expected_error_contains!r}, got {message!r}"
            ) from exc
        return {
            "case_id": case_id,
            "schema_key": schema_key,
            "source_report_path": source_path.relative_to(ROOT).as_posix() if source_path else None,
            "mutation": mutation,
            "expected_error_contains": expected_error_contains,
            "rejected": True,
            "error_sha256": redact_schema_error(message),
            "mutated_payload_persisted": False,
            "safe_to_attach_to_issue": True,
        }
    raise SchemaNegativeFixtureError(f"{case_id} unexpectedly passed schema validation.")


def expect_private_text_rejection() -> dict[str, Any]:
    probe = "synthetic private marker: " + "api" + "_key"
    try:
        reject_private_text(probe, label="private text negative fixture")
    except RecipeCliSchemaError as exc:
        message = str(exc)
        expected = "contains private or secret-like text"
        if expected not in message:
            raise SchemaNegativeFixtureError(
                f"private text probe expected error containing {expected!r}, got {message!r}"
            ) from exc
        return {
            "case_id": "private_text_probe_rejected",
            "schema_key": "privacy_scanner",
            "source_report_path": None,
            "mutation": "inject synthetic private marker into scanner only",
            "expected_error_contains": expected,
            "rejected": True,
            "error_sha256": sha256_text(message),
            "mutated_payload_persisted": False,
            "safe_to_attach_to_issue": True,
        }
    raise SchemaNegativeFixtureError("private text probe unexpectedly passed privacy scanning.")


def build_report() -> dict[str, Any]:
    schemas = build_schemas()
    success = load_json(SUCCESS_REPORT)
    receipts = load_json(RECEIPTS_REPORT)
    failures = load_json(FAILURES_REPORT)
    pr_ci_receipt = load_json(PR_CI_RECEIPT_REPORT)
    pr_ci_source = default_pr_ci_source(source="gh_live")

    canonical_reports = [
        (
            "cognitive_loop_recipe_cli_verification",
            SUCCESS_REPORT,
            "cognitive-loop-recipe-cli-verification-v1",
            success,
        ),
        (
            "cognitive_loop_recipe_cli_receipts",
            RECEIPTS_REPORT,
            "cognitive-loop-recipe-cli-receipts-v1",
            receipts,
        ),
        (
            "cognitive_loop_recipe_cli_failures",
            FAILURES_REPORT,
            "cognitive-loop-recipe-cli-failures-v1",
            failures,
        ),
        (
            "cognitive_loop_pr_ci_receipt",
            PR_CI_RECEIPT_REPORT,
            "cognitive-loop-pr-ci-receipt-v1",
            pr_ci_receipt,
        ),
        (
            "cognitive_loop_pr_ci_source",
            None,
            "cognitive-loop-pr-ci-source-v1",
            pr_ci_source,
        ),
    ]
    canonical_validations: list[dict[str, Any]] = []
    for schema_key, path, schema_version, payload in canonical_reports:
        validate_instance(payload, schemas[schema_key], path=f"${schema_key}")
        canonical_validations.append(
            {
                "schema_key": schema_key,
                "path": path.relative_to(ROOT).as_posix() if path else "<synthetic:gh_live:cognitive-loop-pr-ci-source-v1>",
                "schema_version": schema_version,
                "status": "pass",
            }
        )

    cases = [
        expect_schema_rejection(
            case_id="success_wrong_schema_version",
            schema_key="cognitive_loop_recipe_cli_verification",
            schema=schemas["cognitive_loop_recipe_cli_verification"],
            source_path=SUCCESS_REPORT,
            source_payload=success,
            mutation="set schema_version to an unexpected value",
            mutate=mutate_success_wrong_schema_version,
            expected_error_contains="$cognitive_loop_recipe_cli_verification.schema_version expected const",
        ),
        expect_schema_rejection(
            case_id="success_auto_execute_true",
            schema_key="cognitive_loop_recipe_cli_verification",
            schema=schemas["cognitive_loop_recipe_cli_verification"],
            source_path=SUCCESS_REPORT,
            source_payload=success,
            mutation="set the first recipe plan safe_to_auto_execute flag to true",
            mutate=mutate_success_auto_execute_true,
            expected_error_contains="safe_to_auto_execute expected const False",
        ),
        expect_schema_rejection(
            case_id="receipts_missing_privacy",
            schema_key="cognitive_loop_recipe_cli_receipts",
            schema=schemas["cognitive_loop_recipe_cli_receipts"],
            source_path=RECEIPTS_REPORT,
            source_payload=receipts,
            mutation="remove required privacy block",
            mutate=mutate_receipts_missing_privacy,
            expected_error_contains="$cognitive_loop_recipe_cli_receipts missing required key 'privacy'",
        ),
        expect_schema_rejection(
            case_id="failures_exit_code_string",
            schema_key="cognitive_loop_recipe_cli_failures",
            schema=schemas["cognitive_loop_recipe_cli_failures"],
            source_path=FAILURES_REPORT,
            source_payload=failures,
            mutation="change first failure case exit_code from integer to string",
            mutate=mutate_failures_exit_code_string,
            expected_error_contains="$cognitive_loop_recipe_cli_failures.cases[0].exit_code expected type integer",
        ),
        expect_schema_rejection(
            case_id="pr_ci_receipt_missing_required_checks",
            schema_key="cognitive_loop_pr_ci_receipt",
            schema=schemas["cognitive_loop_pr_ci_receipt"],
            source_path=PR_CI_RECEIPT_REPORT,
            source_payload=pr_ci_receipt,
            mutation="remove compose-smoke from required_checks",
            mutate=mutate_pr_ci_receipt_missing_required_checks,
            expected_error_contains="required_checks expected const",
        ),
        expect_schema_rejection(
            case_id="pr_ci_receipt_github_tokens_true",
            schema_key="cognitive_loop_pr_ci_receipt",
            schema=schemas["cognitive_loop_pr_ci_receipt"],
            source_path=PR_CI_RECEIPT_REPORT,
            source_payload=pr_ci_receipt,
            mutation="set privacy_flags.github_tokens_included to true",
            mutate=mutate_pr_ci_receipt_github_tokens_true,
            expected_error_contains="github_tokens_included expected const False",
        ),
        expect_schema_rejection(
            case_id="pr_ci_source_unsupported_source",
            schema_key="cognitive_loop_pr_ci_source",
            schema=schemas["cognitive_loop_pr_ci_source"],
            source_path=None,
            source_payload=pr_ci_source,
            mutation="set source to unsupported webhook value",
            mutate=mutate_pr_ci_source_unsupported_source,
            expected_error_contains="$cognitive_loop_pr_ci_source.source expected one of",
        ),
        expect_schema_rejection(
            case_id="pr_ci_source_unsafe_url_query",
            schema_key="cognitive_loop_pr_ci_source",
            schema=schemas["cognitive_loop_pr_ci_source"],
            source_path=None,
            source_payload=pr_ci_source,
            mutation="append a query string to a GitHub details URL",
            mutate=mutate_pr_ci_source_unsafe_url_query,
            expected_error_contains="url did not match pattern",
        ),
        expect_schema_rejection(
            case_id="pr_ci_source_raw_logs_true",
            schema_key="cognitive_loop_pr_ci_source",
            schema=schemas["cognitive_loop_pr_ci_source"],
            source_path=None,
            source_payload=pr_ci_source,
            mutation="set raw_logs_included to true",
            mutate=mutate_pr_ci_source_raw_logs_true,
            expected_error_contains="raw_logs_included expected const False",
        ),
        expect_schema_rejection(
            case_id="pr_ci_source_unsafe_command",
            schema_key="cognitive_loop_pr_ci_source",
            schema=schemas["cognitive_loop_pr_ci_source"],
            source_path=None,
            source_payload=pr_ci_source,
            mutation="replace operator command allowlist with gh pr merge",
            mutate=mutate_pr_ci_source_unsafe_command,
            expected_error_contains="operator_next_commands[0] expected one of",
        ),
        expect_private_text_rejection(),
    ]
    if tuple(case["case_id"] for case in cases) != CASE_IDS:
        raise SchemaNegativeFixtureError("Schema negative fixture case order drifted.")
    if not all(case["rejected"] and not case["mutated_payload_persisted"] for case in cases):
        raise SchemaNegativeFixtureError("All schema negative fixtures must be rejected without persisted payloads.")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Prove Cognitive Loop recipe CLI JSON Schemas reject representative drift, unsafe flags, malformed types, and private text probes.",
        "source_schema_bundle": {
            "path": SCHEMA_BUNDLE_REPORT.relative_to(ROOT).as_posix(),
            "schema_version": SCHEMA_BUNDLE_VERSION,
            "schema_keys": sorted(schemas),
        },
        "coverage": {
            "case_count": len(cases),
            "case_ids": [case["case_id"] for case in cases],
            "canonical_reports_validated": canonical_validations,
            "all_cases_rejected": True,
            "all_expected_errors_matched": True,
            "all_errors_redacted": True,
            "mutated_payloads_persisted": False,
            "validated_without_running_recipe_cli": True,
            "recipe_cli_invoked": False,
            "runtime_started": False,
            "file_changes_applied": False,
        },
        "cases": cases,
        "distribution": {
            "negative_fixture_report_path": REPORT.relative_to(ROOT).as_posix(),
            "verification_command": (
                "python3 scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py --check"
            ),
            "safe_for_platform_agent_static_import": True,
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
    }
    reject_private_text(dump_json(report), label="recipe CLI schema negative fixture report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    serialized = dump_json(build_report())
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop recipe CLI schema negative fixture report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop recipe CLI schema negative fixture report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_recipe_cli_schema_negative_fixtures failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
