#!/usr/bin/env python3
"""Generate and verify deterministic Cognitive Loop recipe CLI receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli-receipts.json"
CLI = ROOT / "scripts" / "cognitive_loop_recipe_cli.py"

SCHEMA_VERSION = "cognitive-loop-recipe-cli-receipts-v1"
CLI_SCHEMA_VERSION = "cognitive-loop-recipe-cli-v1"
EXPECTED_RECIPE_IDS = ("first_adoption", "daily_project_review", "risk_decision", "learning_handoff")
PRIVATE_NEEDLES = (
    "sk-proj-",
    "bearer ",
    "api_key",
    "secret_access_key",
    "raw private source text",
    "learner answer:",
    "http://127.0.0.1:8787/",
)


class RecipeCliReceiptError(RuntimeError):
    """Readable recipe CLI receipt verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def reject_private_text(value: str, *, label: str) -> None:
    lowered = value.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle in lowered]
    if leaked:
        raise RecipeCliReceiptError(f"{label} contains private or secret-like text: {leaked}")


def run_receipt(args: tuple[str, ...]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(ROOT),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.stderr.strip():
        raise RecipeCliReceiptError(f"Recipe CLI wrote unexpected stderr for {args}: {completed.stderr}")
    reject_private_text(completed.stdout, label=f"stdout {args}")
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RecipeCliReceiptError(f"Recipe CLI returned invalid JSON for {args}: {exc}") from exc

    action = parsed.get("action")
    recipe_id = None
    if action == "show":
        recipe_id = (parsed.get("recipe") or {}).get("recipe_id")
    return {
        "command": "python3 scripts/cognitive_loop_recipe_cli.py " + " ".join(args),
        "exit_code": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "stdout_line_count": completed.stdout.count("\n"),
        "output_schema_version": parsed.get("schema_version"),
        "output_action": action,
        "recipe_id": recipe_id,
        "stdout_json": parsed,
        "safe_to_attach_to_issue": True,
    }


def assert_policy_and_privacy(payload: dict[str, Any], *, label: str) -> None:
    if payload.get("schema_version") != CLI_SCHEMA_VERSION or payload.get("status") != "ok":
        raise RecipeCliReceiptError(f"{label} schema/status drifted.")
    policy = payload.get("safe_replay_policy") or {}
    expected_true = (
        "metadata_only",
        "requires_operator_for_runtime_commands",
        "requires_human_gate_for_risk_decisions",
    )
    expected_false = ("executes_recipe_commands", "starts_runtime", "applies_file_changes")
    for key in expected_true:
        if policy.get(key) is not True:
            raise RecipeCliReceiptError(f"{label} safe_replay_policy.{key} must be true.")
    for key in expected_false:
        if policy.get(key) is not False:
            raise RecipeCliReceiptError(f"{label} safe_replay_policy.{key} must be false.")
    privacy = payload.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise RecipeCliReceiptError(f"{label} privacy.{key} must be false.")


def verify_receipts(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    by_action = {receipt["output_action"]: receipt for receipt in receipts if receipt["output_action"] == "list"}
    list_receipt = by_action.get("list")
    if not list_receipt:
        raise RecipeCliReceiptError("Recipe CLI receipts must include list output.")
    list_payload = list_receipt["stdout_json"]
    assert_policy_and_privacy(list_payload, label="list receipt")
    if tuple(list_payload.get("recipe_ids", [])) != EXPECTED_RECIPE_IDS:
        raise RecipeCliReceiptError("Recipe CLI list receipt recipe ids drifted.")
    if list_payload.get("recipe_count") != len(EXPECTED_RECIPE_IDS):
        raise RecipeCliReceiptError("Recipe CLI list receipt count drifted.")

    show_receipts = {
        receipt.get("recipe_id"): receipt for receipt in receipts if receipt.get("output_action") == "show"
    }
    if set(show_receipts) != set(EXPECTED_RECIPE_IDS):
        raise RecipeCliReceiptError(f"Recipe CLI show receipt coverage drifted: {sorted(show_receipts)}")

    plans: list[dict[str, Any]] = []
    for recipe_id in EXPECTED_RECIPE_IDS:
        receipt = show_receipts[recipe_id]
        payload = receipt["stdout_json"]
        assert_policy_and_privacy(payload, label=f"show receipt {recipe_id}")
        recipe = payload.get("recipe") or {}
        if recipe.get("recipe_id") != recipe_id:
            raise RecipeCliReceiptError(f"Recipe CLI show receipt {recipe_id} returned wrong recipe.")
        if recipe.get("safe_to_auto_execute") is not False:
            raise RecipeCliReceiptError(f"Recipe CLI show receipt {recipe_id} must not auto-execute.")
        if not recipe.get("steps"):
            raise RecipeCliReceiptError(f"Recipe CLI show receipt {recipe_id} must include steps.")
        if not all(step.get("script_exists") is True for step in recipe.get("steps", [])):
            raise RecipeCliReceiptError(f"Recipe CLI show receipt {recipe_id} references missing scripts.")
        plans.append(
            {
                "recipe_id": recipe_id,
                "command_count": recipe.get("command_count"),
                "command_classes": recipe.get("command_classes"),
                "runtime_required": recipe.get("runtime_required"),
                "requires_operator_before_runtime": recipe.get("requires_operator_before_runtime"),
                "requires_human_mastery_gate": recipe.get("requires_human_mastery_gate"),
                "safe_to_auto_execute": recipe.get("safe_to_auto_execute"),
                "stdout_sha256": receipt.get("stdout_sha256"),
            }
        )

    by_id = {plan["recipe_id"]: plan for plan in plans}
    if by_id["risk_decision"]["requires_human_mastery_gate"] is not True:
        raise RecipeCliReceiptError("risk_decision receipt must require the Human Mastery Gate.")
    if by_id["daily_project_review"]["requires_human_mastery_gate"] is not False:
        raise RecipeCliReceiptError("daily_project_review receipt must not require the Human Mastery Gate.")
    if by_id["first_adoption"]["requires_operator_before_runtime"] is not True:
        raise RecipeCliReceiptError("first_adoption receipt must require operator before runtime.")
    if by_id["learning_handoff"]["requires_operator_before_runtime"] is not True:
        raise RecipeCliReceiptError("learning_handoff receipt must require operator before runtime.")

    return {
        "receipt_count": len(receipts),
        "list_stdout_sha256": list_receipt["stdout_sha256"],
        "recipe_ids": list(EXPECTED_RECIPE_IDS),
        "show_receipts": plans,
        "includes_list": True,
        "includes_all_show_recipes": True,
        "includes_risk_decision_human_gate": True,
        "all_outputs_schema_version": CLI_SCHEMA_VERSION,
        "all_outputs_safe_to_attach_to_issue": True,
        "all_show_outputs_safe_to_auto_execute": False,
        "all_steps_reference_existing_scripts": True,
    }


def build_report() -> dict[str, Any]:
    receipts = [run_receipt(("list",))]
    receipts.extend(run_receipt(("show", recipe_id)) for recipe_id in EXPECTED_RECIPE_IDS)
    coverage = verify_receipts(receipts)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Provide deterministic, redacted samples of read-only Cognitive Loop recipe CLI outputs.",
        "cli": {
            "path": "scripts/cognitive_loop_recipe_cli.py",
            "schema_version": CLI_SCHEMA_VERSION,
            "receipt_commands": [
                "python3 scripts/cognitive_loop_recipe_cli.py list",
                "python3 scripts/cognitive_loop_recipe_cli.py show risk_decision",
            ],
        },
        "coverage": coverage,
        "receipts": receipts,
        "safe_replay_policy": {
            "invokes_recipe_cli_only": True,
            "executes_recipe_commands": False,
            "starts_runtime": False,
            "applies_file_changes": False,
            "requires_operator_for_runtime_commands": True,
            "requires_human_gate_for_risk_decisions": True,
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
        "boundaries": {
            "platform_agent_owns_browser_files_apps_video_external_data": True,
            "study_anything_is_learning_adapter": True,
            "recipe_cli_receipts_are_read_only": True,
            "recipe_cli_receipts_execute_recipe_commands": False,
            "recipe_cli_receipts_apply_file_changes": False,
            "standalone_frontend_required": False,
        },
        "commands": {
            "verify": "python3 scripts/verify_cognitive_loop_recipe_cli_receipts.py --check",
            "write": "python3 scripts/verify_cognitive_loop_recipe_cli_receipts.py --write",
            "cli_list": "python3 scripts/cognitive_loop_recipe_cli.py list",
            "cli_show_risk": "python3 scripts/cognitive_loop_recipe_cli.py show risk_decision",
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
            raise SystemExit(f"Cognitive Loop recipe CLI receipt report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop recipe CLI receipt report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_recipe_cli_receipts.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_recipe_cli_receipts failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
