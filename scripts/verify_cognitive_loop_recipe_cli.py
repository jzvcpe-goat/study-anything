#!/usr/bin/env python3
"""Verify the read-only Cognitive Loop recipe CLI for platform Agents."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli.json"
CLI = ROOT / "scripts" / "cognitive_loop_recipe_cli.py"
SKILL = ROOT / "skills" / "study-anything" / "SKILL.md"
PACKS_DIR = ROOT / "platform" / "packs"
ECOSYSTEM_SUBMISSION = ROOT / "platform" / "ecosystem-submission.json"
BUNDLE_GENERATOR = ROOT / "scripts" / "generate_platform_bundle_manifest.py"
ADOPTION_PACK_GENERATOR = ROOT / "scripts" / "generate_platform_adoption_pack.py"
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"
PLATFORM_PACK_VERIFIER = ROOT / "scripts" / "verify_platform_ecosystem_packs.py"
ECOSYSTEM_SUBMISSION_VERIFIER = ROOT / "scripts" / "verify_ecosystem_submission_pack.py"

SCHEMA_VERSION = "cognitive-loop-recipe-cli-verification-v1"
CLI_SCHEMA_VERSION = "cognitive-loop-recipe-cli-v1"
REPORT_RELATIVE_PATH = "platform/generated/study-anything-cognitive-loop-recipe-cli.json"
SCRIPT_RELATIVE_PATH = "scripts/verify_cognitive_loop_recipe_cli.py"
CLI_RELATIVE_PATH = "scripts/cognitive_loop_recipe_cli.py"
RECIPES_RELATIVE_PATH = "platform/generated/study-anything-cognitive-loop-adoption-recipes.json"
REPLAY_RELATIVE_PATH = "platform/generated/study-anything-cognitive-loop-recipe-replay.json"
REQUIRED_PACKS = ("codex", "kimi", "workbuddy", "hermes")
EXPECTED_RECIPE_IDS = ("first_adoption", "daily_project_review", "risk_decision", "learning_handoff")


class RecipeCliVerificationError(RuntimeError):
    """Readable recipe CLI verification failure."""


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RecipeCliVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise RecipeCliVerificationError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def run_cli(*args: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(ROOT),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RecipeCliVerificationError(f"Recipe CLI returned invalid JSON for {args}: {exc}") from exc


def require_text(text: str, needles: tuple[str, ...], *, label: str) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise RecipeCliVerificationError(f"{label} is missing required text: {missing}")


def verify_cli_outputs() -> dict[str, Any]:
    listed = run_cli("list")
    if listed.get("schema_version") != CLI_SCHEMA_VERSION or listed.get("status") != "ok":
        raise RecipeCliVerificationError("Recipe CLI list output schema/status drifted.")
    if listed.get("action") != "list":
        raise RecipeCliVerificationError("Recipe CLI list action drifted.")
    if tuple(listed.get("recipe_ids", [])) != EXPECTED_RECIPE_IDS:
        raise RecipeCliVerificationError("Recipe CLI list recipe ids drifted.")
    if listed.get("recipe_count") != len(EXPECTED_RECIPE_IDS):
        raise RecipeCliVerificationError("Recipe CLI list recipe count drifted.")

    plans: list[dict[str, Any]] = []
    for recipe_id in EXPECTED_RECIPE_IDS:
        shown = run_cli("show", recipe_id)
        if shown.get("schema_version") != CLI_SCHEMA_VERSION or shown.get("status") != "ok":
            raise RecipeCliVerificationError(f"Recipe CLI show {recipe_id} schema/status drifted.")
        if shown.get("action") != "show":
            raise RecipeCliVerificationError(f"Recipe CLI show {recipe_id} action drifted.")
        recipe = shown.get("recipe") or {}
        if recipe.get("recipe_id") != recipe_id:
            raise RecipeCliVerificationError(f"Recipe CLI show {recipe_id} returned wrong recipe.")
        if recipe.get("safe_to_auto_execute") is not False:
            raise RecipeCliVerificationError(f"Recipe CLI show {recipe_id} must not be safe_to_auto_execute.")
        if not recipe.get("steps"):
            raise RecipeCliVerificationError(f"Recipe CLI show {recipe_id} must include steps.")
        if not all(step.get("script_exists") is True for step in recipe.get("steps", [])):
            raise RecipeCliVerificationError(f"Recipe CLI show {recipe_id} references missing scripts.")
        plans.append(
            {
                "recipe_id": recipe_id,
                "command_count": recipe.get("command_count"),
                "command_classes": recipe.get("command_classes"),
                "runtime_required": recipe.get("runtime_required"),
                "requires_operator_before_runtime": recipe.get("requires_operator_before_runtime"),
                "requires_human_mastery_gate": recipe.get("requires_human_mastery_gate"),
                "safe_to_auto_execute": recipe.get("safe_to_auto_execute"),
            }
        )

    by_id = {plan["recipe_id"]: plan for plan in plans}
    if by_id["risk_decision"]["requires_human_mastery_gate"] is not True:
        raise RecipeCliVerificationError("risk_decision must require the Human Mastery Gate.")
    if by_id["daily_project_review"]["requires_human_mastery_gate"] is not False:
        raise RecipeCliVerificationError("daily_project_review must not require the Human Mastery Gate.")
    if by_id["first_adoption"]["requires_operator_before_runtime"] is not True:
        raise RecipeCliVerificationError("first_adoption must require an operator before runtime/external adoption.")
    if by_id["learning_handoff"]["requires_operator_before_runtime"] is not True:
        raise RecipeCliVerificationError("learning_handoff must require an operator before runtime.")
    for payload in (listed, *(run_cli("show", recipe_id) for recipe_id in EXPECTED_RECIPE_IDS)):
        policy = payload.get("safe_replay_policy") or {}
        if policy.get("executes_recipe_commands") is not False:
            raise RecipeCliVerificationError("Recipe CLI must not execute recipe commands.")
        if policy.get("metadata_only") is not True:
            raise RecipeCliVerificationError("Recipe CLI must be metadata-only.")
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
                raise RecipeCliVerificationError(f"Recipe CLI privacy.{key} must be false.")

    return {
        "list_schema_version": listed["schema_version"],
        "recipe_ids": list(EXPECTED_RECIPE_IDS),
        "recipe_count": listed["recipe_count"],
        "plans": plans,
        "all_steps_reference_existing_scripts": True,
        "metadata_only": True,
        "executes_recipe_commands": False,
    }


def verify_entrypoint_docs() -> dict[str, Any]:
    required = (
        CLI_RELATIVE_PATH,
        REPORT_RELATIVE_PATH,
        "python3 scripts/cognitive_loop_recipe_cli.py list",
        "python3 scripts/cognitive_loop_recipe_cli.py show risk_decision",
        "python3 scripts/verify_cognitive_loop_recipe_cli.py --check",
    )
    checked = ["skills/study-anything/SKILL.md"]
    require_text(read_text(SKILL), required, label="skills/study-anything/SKILL.md")
    for pack_id in REQUIRED_PACKS:
        path = PACKS_DIR / pack_id / "README.md"
        require_text(read_text(path), required, label=str(path.relative_to(ROOT)))
        checked.append(str(path.relative_to(ROOT)))
    return {"checked_docs": checked, "cli_documented": True}


def verify_distribution_sources() -> dict[str, Any]:
    for path, label in (
        (BUNDLE_GENERATOR, "bundle generator"),
        (ADOPTION_PACK_GENERATOR, "adoption pack generator"),
    ):
        text = read_text(path)
        for needle in (REPORT_RELATIVE_PATH, SCRIPT_RELATIVE_PATH, CLI_RELATIVE_PATH):
            if needle not in text:
                raise RecipeCliVerificationError(f"{label} must include {needle}.")

    release_text = read_text(RELEASE_CHECK)
    if "verify_cognitive_loop_recipe_cli.py --check" not in release_text:
        raise RecipeCliVerificationError("release check must run verify_cognitive_loop_recipe_cli.py --check.")

    platform_verifier_text = read_text(PLATFORM_PACK_VERIFIER)
    for needle in (REPORT_RELATIVE_PATH, CLI_RELATIVE_PATH, "verify_cognitive_loop_recipe_cli.py --check"):
        if needle not in platform_verifier_text:
            raise RecipeCliVerificationError(f"platform pack verifier must include {needle}.")

    ecosystem_verifier_text = read_text(ECOSYSTEM_SUBMISSION_VERIFIER)
    for needle in (REPORT_RELATIVE_PATH, SCRIPT_RELATIVE_PATH, CLI_RELATIVE_PATH, SCHEMA_VERSION):
        if needle not in ecosystem_verifier_text:
            raise RecipeCliVerificationError(f"ecosystem submission verifier must include {needle}.")
    return {
        "bundle_manifest_source_registered": True,
        "adoption_pack_source_registered": True,
        "release_check_registered": True,
        "platform_pack_verifier_registered": True,
        "ecosystem_submission_verifier_registered": True,
    }


def verify_pack_manifests() -> dict[str, Any]:
    packs: list[dict[str, Any]] = []
    for pack_id in REQUIRED_PACKS:
        path = PACKS_DIR / pack_id / "pack.json"
        pack = load_json(path)
        import_assets = set(str(asset) for asset in pack.get("import_assets", []))
        for asset in (RECIPES_RELATIVE_PATH, REPLAY_RELATIVE_PATH, REPORT_RELATIVE_PATH, CLI_RELATIVE_PATH):
            if asset not in import_assets:
                raise RecipeCliVerificationError(f"{path.relative_to(ROOT)} import_assets missing {asset}.")
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        if "python3 scripts/verify_cognitive_loop_recipe_cli.py --check" not in commands:
            raise RecipeCliVerificationError(f"{path.relative_to(ROOT)} commands missing recipe CLI verifier.")
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        expected = f"cognitive_loop_recipe_cli.schema_version == {SCHEMA_VERSION}"
        if expected not in evidence:
            raise RecipeCliVerificationError(f"{path.relative_to(ROOT)} acceptance evidence missing {expected}.")
        packs.append({"platform_id": pack_id, "imports_cli": True, "runs_verifier": True, "accepts_schema": True})
    return {"packs": packs}


def verify_ecosystem_submission() -> dict[str, Any]:
    submission = load_json(ECOSYSTEM_SUBMISSION)
    shared_assets = set(str(asset) for asset in submission.get("shared_assets", []))
    for asset in (REPORT_RELATIVE_PATH, SCRIPT_RELATIVE_PATH, CLI_RELATIVE_PATH):
        if asset not in shared_assets:
            raise RecipeCliVerificationError(f"platform/ecosystem-submission.json shared_assets missing {asset}.")
    commands = "\n".join(str(command) for command in submission.get("acceptance", {}).get("minimum_commands", []))
    if "python3 scripts/verify_cognitive_loop_recipe_cli.py --check" not in commands:
        raise RecipeCliVerificationError("ecosystem submission minimum_commands must run the recipe CLI verifier.")
    must_prove = "\n".join(str(item) for item in submission.get("acceptance", {}).get("must_prove", []))
    if SCHEMA_VERSION not in must_prove:
        raise RecipeCliVerificationError("ecosystem submission must_prove must mention the recipe CLI schema.")
    for entry in submission.get("submissions", []):
        import_assets = set(str(asset) for asset in entry.get("import_assets", []))
        for asset in (REPORT_RELATIVE_PATH, CLI_RELATIVE_PATH):
            if asset not in import_assets:
                raise RecipeCliVerificationError(f"{entry.get('platform_id')} import_assets missing {asset}.")
    return {
        "shared_assets_registered": True,
        "minimum_command_registered": True,
        "must_prove_registered": True,
        "submission_imports_registered": True,
    }


def build_report() -> dict[str, Any]:
    cli_outputs = verify_cli_outputs()
    docs = verify_entrypoint_docs()
    pack_manifests = verify_pack_manifests()
    ecosystem = verify_ecosystem_submission()
    distribution = verify_distribution_sources()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Verify platform Agents can query Cognitive Loop recipe plans without executing commands.",
        "cli": {
            "path": CLI_RELATIVE_PATH,
            "schema_version": CLI_SCHEMA_VERSION,
            "commands": {
                "list": "python3 scripts/cognitive_loop_recipe_cli.py list",
                "show_risk": "python3 scripts/cognitive_loop_recipe_cli.py show risk_decision",
            },
        },
        "cli_outputs": cli_outputs,
        "entrypoint_docs": docs,
        "platform_pack_manifests": pack_manifests,
        "ecosystem_submission": ecosystem,
        "distribution_sources": distribution,
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
            "recipe_cli_is_read_only": True,
            "recipe_cli_executes_commands": False,
            "recipe_cli_applies_file_changes": False,
            "standalone_frontend_required": False,
        },
    }


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


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
            raise SystemExit(f"Cognitive Loop recipe CLI report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop recipe CLI report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_recipe_cli.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_recipe_cli failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
