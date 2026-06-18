#!/usr/bin/env python3
"""Generate and verify offline JSON Schemas for Cognitive Loop recipe CLI reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli-schemas.json"
SUCCESS_REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli.json"
RECEIPTS_REPORT = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli-receipts.json"
)
FAILURES_REPORT = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli-failures.json"
)

SCHEMA_VERSION = "cognitive-loop-recipe-cli-schemas-v1"
CLI_SCHEMA_VERSION = "cognitive-loop-recipe-cli-v1"
SUCCESS_SCHEMA_VERSION = "cognitive-loop-recipe-cli-verification-v1"
RECEIPTS_SCHEMA_VERSION = "cognitive-loop-recipe-cli-receipts-v1"
FAILURES_SCHEMA_VERSION = "cognitive-loop-recipe-cli-failures-v1"
EXPECTED_RECIPE_IDS = ("first_adoption", "daily_project_review", "risk_decision", "learning_handoff")
FAILURE_CASE_IDS = (
    "unknown_recipe_id",
    "source_schema_drift",
    "source_status_failed",
    "empty_recipe_matrix",
)
PRIVACY_FALSE_KEYS = (
    "raw_source_text_included",
    "diff_bodies_included",
    "learner_answers_included",
    "grading_feedback_included",
    "generated_private_insights_included",
    "agent_endpoints_included",
    "agent_metadata_included",
    "real_model_keys_stored",
    "browser_video_app_private_context_included",
)
PRIVATE_NEEDLES = (
    "sk-proj-",
    "bearer ",
    "api_key",
    "secret_access_key",
    "raw private source text",
    "learner answer:",
    "http://127.0.0.1:8787/",
)


class RecipeCliSchemaError(RuntimeError):
    """Readable recipe CLI schema verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RecipeCliSchemaError(f"Missing required report: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise RecipeCliSchemaError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def reject_private_text(value: str, *, label: str) -> None:
    lowered = value.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle in lowered]
    if leaked:
        raise RecipeCliSchemaError(f"{label} contains private or secret-like text: {leaked}")


def schema_bool(value: bool) -> dict[str, Any]:
    return {"type": "boolean", "const": value}


def privacy_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "required": list(PRIVACY_FALSE_KEYS),
        "properties": {key: schema_bool(False) for key in PRIVACY_FALSE_KEYS},
    }


def recipe_plan_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "required": [
            "recipe_id",
            "command_count",
            "command_classes",
            "runtime_required",
            "requires_operator_before_runtime",
            "requires_human_mastery_gate",
            "safe_to_auto_execute",
        ],
        "properties": {
            "recipe_id": {"type": "string", "enum": list(EXPECTED_RECIPE_IDS)},
            "command_count": {"type": "integer", "minimum": 1},
            "command_classes": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "runtime_required": {"type": "boolean"},
            "requires_operator_before_runtime": {"type": "boolean"},
            "requires_human_mastery_gate": {"type": "boolean"},
            "safe_to_auto_execute": schema_bool(False),
        },
    }


def build_success_report_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://study-anything.local/schemas/cognitive-loop-recipe-cli-verification-v1.json",
        "title": "Cognitive Loop recipe CLI verification report",
        "type": "object",
        "additionalProperties": True,
        "required": ["schema_version", "status", "cli", "cli_outputs", "privacy", "boundaries"],
        "properties": {
            "schema_version": {"const": SUCCESS_SCHEMA_VERSION},
            "status": {"const": "pass"},
            "cli": {
                "type": "object",
                "additionalProperties": True,
                "required": ["path", "schema_version", "commands"],
                "properties": {
                    "path": {"const": "scripts/cognitive_loop_recipe_cli.py"},
                    "schema_version": {"const": CLI_SCHEMA_VERSION},
                    "commands": {"type": "object"},
                },
            },
            "cli_outputs": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "recipe_ids",
                    "recipe_count",
                    "plans",
                    "metadata_only",
                    "executes_recipe_commands",
                    "all_steps_reference_existing_scripts",
                ],
                "properties": {
                    "recipe_ids": {
                        "type": "array",
                        "minItems": len(EXPECTED_RECIPE_IDS),
                        "items": {"type": "string", "enum": list(EXPECTED_RECIPE_IDS)},
                    },
                    "recipe_count": {"type": "integer", "const": len(EXPECTED_RECIPE_IDS)},
                    "plans": {
                        "type": "array",
                        "minItems": len(EXPECTED_RECIPE_IDS),
                        "items": recipe_plan_schema(),
                    },
                    "metadata_only": schema_bool(True),
                    "executes_recipe_commands": schema_bool(False),
                    "all_steps_reference_existing_scripts": schema_bool(True),
                },
            },
            "privacy": privacy_schema(),
            "boundaries": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "recipe_cli_is_read_only",
                    "recipe_cli_executes_commands",
                    "recipe_cli_applies_file_changes",
                    "standalone_frontend_required",
                    "study_anything_is_learning_adapter",
                    "platform_agent_owns_browser_files_apps_video_external_data",
                ],
                "properties": {
                    "recipe_cli_is_read_only": schema_bool(True),
                    "recipe_cli_executes_commands": schema_bool(False),
                    "recipe_cli_applies_file_changes": schema_bool(False),
                    "standalone_frontend_required": schema_bool(False),
                    "study_anything_is_learning_adapter": schema_bool(True),
                    "platform_agent_owns_browser_files_apps_video_external_data": schema_bool(True),
                },
            },
        },
    }


def build_receipts_report_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://study-anything.local/schemas/cognitive-loop-recipe-cli-receipts-v1.json",
        "title": "Cognitive Loop recipe CLI receipt report",
        "type": "object",
        "additionalProperties": True,
        "required": ["schema_version", "status", "cli", "coverage", "receipts", "safe_replay_policy", "privacy"],
        "properties": {
            "schema_version": {"const": RECEIPTS_SCHEMA_VERSION},
            "status": {"const": "pass"},
            "cli": {
                "type": "object",
                "additionalProperties": True,
                "required": ["path", "schema_version", "receipt_commands"],
                "properties": {
                    "path": {"const": "scripts/cognitive_loop_recipe_cli.py"},
                    "schema_version": {"const": CLI_SCHEMA_VERSION},
                    "receipt_commands": {"type": "array", "minItems": 2, "items": {"type": "string"}},
                },
            },
            "coverage": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "receipt_count",
                    "recipe_ids",
                    "includes_list",
                    "includes_all_show_recipes",
                    "all_outputs_schema_version",
                    "all_outputs_safe_to_attach_to_issue",
                    "all_show_outputs_safe_to_auto_execute",
                ],
                "properties": {
                    "receipt_count": {"type": "integer", "minimum": 5},
                    "recipe_ids": {
                        "type": "array",
                        "minItems": len(EXPECTED_RECIPE_IDS),
                        "items": {"type": "string", "enum": list(EXPECTED_RECIPE_IDS)},
                    },
                    "includes_list": schema_bool(True),
                    "includes_all_show_recipes": schema_bool(True),
                    "all_outputs_schema_version": {"const": CLI_SCHEMA_VERSION},
                    "all_outputs_safe_to_attach_to_issue": schema_bool(True),
                    "all_show_outputs_safe_to_auto_execute": schema_bool(False),
                },
            },
            "receipts": {
                "type": "array",
                "minItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": [
                        "command",
                        "exit_code",
                        "stdout_sha256",
                        "output_schema_version",
                        "output_action",
                        "stdout_json",
                        "safe_to_attach_to_issue",
                    ],
                    "properties": {
                        "command": {"type": "string"},
                        "exit_code": {"type": "integer", "const": 0},
                        "stdout_sha256": {"type": "string", "minLength": 64},
                        "output_schema_version": {"const": CLI_SCHEMA_VERSION},
                        "output_action": {"type": "string", "enum": ["list", "show"]},
                        "stdout_json": {"type": "object"},
                        "safe_to_attach_to_issue": schema_bool(True),
                    },
                },
            },
            "safe_replay_policy": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "invokes_recipe_cli_only",
                    "executes_recipe_commands",
                    "starts_runtime",
                    "applies_file_changes",
                    "requires_operator_for_runtime_commands",
                    "requires_human_gate_for_risk_decisions",
                ],
                "properties": {
                    "invokes_recipe_cli_only": schema_bool(True),
                    "executes_recipe_commands": schema_bool(False),
                    "starts_runtime": schema_bool(False),
                    "applies_file_changes": schema_bool(False),
                    "requires_operator_for_runtime_commands": schema_bool(True),
                    "requires_human_gate_for_risk_decisions": schema_bool(True),
                },
            },
            "privacy": privacy_schema(),
        },
    }


def build_failures_report_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://study-anything.local/schemas/cognitive-loop-recipe-cli-failures-v1.json",
        "title": "Cognitive Loop recipe CLI failure receipt report",
        "type": "object",
        "additionalProperties": True,
        "required": ["schema_version", "status", "cli", "coverage", "cases", "safe_failure_policy", "privacy"],
        "properties": {
            "schema_version": {"const": FAILURES_SCHEMA_VERSION},
            "status": {"const": "pass"},
            "cli": {
                "type": "object",
                "additionalProperties": True,
                "required": ["path", "success_schema_version", "failure_surface"],
                "properties": {
                    "path": {"const": "scripts/cognitive_loop_recipe_cli.py"},
                    "success_schema_version": {"const": CLI_SCHEMA_VERSION},
                    "failure_surface": {"const": "nonzero_exit_with_redacted_stderr"},
                },
            },
            "coverage": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "case_count",
                    "case_ids",
                    "all_exit_nonzero",
                    "all_stdout_empty",
                    "all_stderr_redacted",
                    "all_safe_to_attach_to_issue",
                ],
                "properties": {
                    "case_count": {"type": "integer", "const": len(FAILURE_CASE_IDS)},
                    "case_ids": {
                        "type": "array",
                        "minItems": len(FAILURE_CASE_IDS),
                        "items": {"type": "string", "enum": list(FAILURE_CASE_IDS)},
                    },
                    "all_exit_nonzero": schema_bool(True),
                    "all_stdout_empty": schema_bool(True),
                    "all_stderr_redacted": schema_bool(True),
                    "all_safe_to_attach_to_issue": schema_bool(True),
                },
            },
            "cases": {
                "type": "array",
                "minItems": len(FAILURE_CASE_IDS),
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": [
                        "case_id",
                        "command",
                        "exit_code",
                        "stdout_empty",
                        "stderr_sha256",
                        "diagnostic_code",
                        "expected_message",
                        "safe_to_attach_to_issue",
                    ],
                    "properties": {
                        "case_id": {"type": "string", "enum": list(FAILURE_CASE_IDS)},
                        "command": {"type": "string"},
                        "exit_code": {"type": "integer", "minimum": 1},
                        "stdout_empty": schema_bool(True),
                        "stderr_sha256": {"type": "string", "minLength": 64},
                        "diagnostic_code": {"type": "string", "enum": list(FAILURE_CASE_IDS)},
                        "expected_message": {"type": "string", "minLength": 1},
                        "safe_to_attach_to_issue": schema_bool(True),
                    },
                },
            },
            "safe_failure_policy": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "invokes_recipe_cli_only",
                    "executes_recipe_commands",
                    "starts_runtime",
                    "applies_file_changes",
                    "writes_only_temporary_negative_fixtures",
                    "temporary_negative_fixtures_removed",
                ],
                "properties": {
                    "invokes_recipe_cli_only": schema_bool(True),
                    "executes_recipe_commands": schema_bool(False),
                    "starts_runtime": schema_bool(False),
                    "applies_file_changes": schema_bool(False),
                    "writes_only_temporary_negative_fixtures": schema_bool(True),
                    "temporary_negative_fixtures_removed": schema_bool(True),
                },
            },
            "privacy": privacy_schema(),
        },
    }


def matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise RecipeCliSchemaError(f"Unsupported JSON Schema type in verifier: {expected}")


def validate_instance(value: Any, schema: dict[str, Any], *, path: str = "$") -> None:
    if "const" in schema and value != schema["const"]:
        raise RecipeCliSchemaError(f"{path} expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise RecipeCliSchemaError(f"{path} expected one of {schema['enum']!r}, got {value!r}")
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not matches_type(value, expected_type):
        raise RecipeCliSchemaError(f"{path} expected type {expected_type}, got {type(value).__name__}")
    if isinstance(expected_type, list) and not any(matches_type(value, item) for item in expected_type):
        raise RecipeCliSchemaError(f"{path} expected one of types {expected_type}, got {type(value).__name__}")

    if isinstance(value, str) and "minLength" in schema and len(value) < int(schema["minLength"]):
        raise RecipeCliSchemaError(f"{path} is shorter than minLength {schema['minLength']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and "minimum" in schema:
        if value < schema["minimum"]:
            raise RecipeCliSchemaError(f"{path} is lower than minimum {schema['minimum']}")

    if isinstance(value, dict):
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                raise RecipeCliSchemaError(f"{path} missing required key {key!r}")
        properties = schema.get("properties") or {}
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise RecipeCliSchemaError(f"{path} has unexpected keys {extra}")
        for key, child_schema in properties.items():
            if key in value:
                validate_instance(value[key], child_schema, path=f"{path}.{key}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            raise RecipeCliSchemaError(f"{path} has fewer than minItems {schema['minItems']}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                validate_instance(item, item_schema, path=f"{path}[{index}]")


def build_schemas() -> dict[str, Any]:
    return {
        "cognitive_loop_recipe_cli_verification": build_success_report_schema(),
        "cognitive_loop_recipe_cli_receipts": build_receipts_report_schema(),
        "cognitive_loop_recipe_cli_failures": build_failures_report_schema(),
    }


def build_report() -> dict[str, Any]:
    schemas = build_schemas()
    report_inputs = [
        (
            "cognitive_loop_recipe_cli_verification",
            SUCCESS_REPORT,
            SUCCESS_SCHEMA_VERSION,
            load_json(SUCCESS_REPORT),
        ),
        (
            "cognitive_loop_recipe_cli_receipts",
            RECEIPTS_REPORT,
            RECEIPTS_SCHEMA_VERSION,
            load_json(RECEIPTS_REPORT),
        ),
        (
            "cognitive_loop_recipe_cli_failures",
            FAILURES_REPORT,
            FAILURES_SCHEMA_VERSION,
            load_json(FAILURES_REPORT),
        ),
    ]

    validations: list[dict[str, Any]] = []
    for schema_key, path, schema_version, payload in report_inputs:
        validate_instance(payload, schemas[schema_key], path=f"${schema_key}")
        validations.append(
            {
                "schema_key": schema_key,
                "path": path.relative_to(ROOT).as_posix(),
                "schema_version": schema_version,
                "status": "pass",
            }
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Provide offline JSON Schemas for Cognitive Loop recipe CLI success, receipt, and failure reports.",
        "json_schema": {
            "dialect": "https://json-schema.org/draft/2020-12/schema",
            "schema_count": len(schemas),
            "schema_keys": sorted(schemas),
            "schemas": schemas,
        },
        "validation": {
            "validated_without_running_recipe_cli": True,
            "recipe_cli_invoked": False,
            "runtime_started": False,
            "file_changes_applied": False,
            "reports": validations,
        },
        "distribution": {
            "schema_bundle_path": REPORT.relative_to(ROOT).as_posix(),
            "verification_command": "python3 scripts/verify_cognitive_loop_recipe_cli_schemas.py --check",
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
    reject_private_text(dump_json(report), label="recipe CLI schema bundle")
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
            raise SystemExit(f"Cognitive Loop recipe CLI schema bundle is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop recipe CLI schema bundle is stale. "
                "Run: python3 scripts/verify_cognitive_loop_recipe_cli_schemas.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_recipe_cli_schemas failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
