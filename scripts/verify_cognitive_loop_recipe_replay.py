#!/usr/bin/env python3
"""Verify Cognitive Loop adoption recipes are replay-ready for platform Agents."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RECIPES_PATH = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-adoption-recipes.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-replay.json"
COOKBOOK = ROOT / "docs" / "cognitive-loop-adoption-cookbook.md"
ECOSYSTEM_SUBMISSION = ROOT / "platform" / "ecosystem-submission.json"
SCHEMA_VERSION = "cognitive-loop-recipe-replay-verification-v1"
SOURCE_SCHEMA_VERSION = "cognitive-loop-adoption-recipes-v1"

EXPECTED_RECIPE_IDS = {
    "first_adoption",
    "daily_project_review",
    "risk_decision",
    "learning_handoff",
}
EXPECTED_PLATFORMS = {
    "kimi",
    "codex",
    "workbuddy",
    "private-platform-agent",
    "generic-openapi-tools",
}
RUNTIME_SCRIPT_NAMES = {
    "run_skill_mode_demo.sh",
    "verify_platform_lesson_flow.py",
    "verify_importer_lesson_flow.py",
}
HUMAN_GATE_FRAGMENTS = (" gate --reject", " gate --approve")
PRIVATE_NEEDLES = (
    "sk-proj-",
    "bearer ",
    "api_key",
    "secret_access_key",
    "raw private source text",
    "learner answer:",
    "http://127.0.0.1:8787/",
)


class RecipeReplayVerificationError(RuntimeError):
    """Readable recipe replay verification failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RecipeReplayVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RecipeReplayVerificationError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RecipeReplayVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc


def reject_private_text(value: str, *, label: str) -> None:
    lowered = value.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle in lowered]
    if leaked:
        raise RecipeReplayVerificationError(f"{label} contains private or secret-like text: {leaked}")


def command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError as exc:
        raise RecipeReplayVerificationError(f"Command is not shell-tokenizable: {command}") from exc


def command_script(command: str) -> str | None:
    tokens = command_tokens(command)
    while tokens and "=" in tokens[0] and not tokens[0].startswith("-"):
        tokens.pop(0)
    if not tokens:
        return None
    executable = tokens[0]
    if executable in {"python", "python3", sys.executable}:
        if len(tokens) < 2:
            return None
        return tokens[1]
    if executable.startswith("./"):
        return executable[2:]
    if executable.startswith("scripts/"):
        return executable
    return None


def classify_command(command: str) -> str:
    script = command_script(command) or ""
    script_name = Path(script).name
    if script_name in RUNTIME_SCRIPT_NAMES:
        return "runtime_required"
    if "verify_external_adoption.py" in script:
        return "external_adoption"
    if any(fragment in f" {command}" for fragment in HUMAN_GATE_FRAGMENTS):
        return "human_gate"
    if "repair-plan" in command:
        return "manual_repair_plan"
    return "metadata_only"


def public_evidence_text() -> str:
    chunks = [read_text(COOKBOOK), read_text(ECOSYSTEM_SUBMISSION), read_text(RECIPES_PATH)]
    for path in sorted((ROOT / "platform" / "generated").glob("*.json")):
        chunks.append(read_text(path))
    return "\n".join(chunks)


def verify_recipe(recipe: dict[str, Any], *, evidence_text: str) -> dict[str, Any]:
    recipe_id = str(recipe.get("recipe_id") or "")
    if recipe_id not in EXPECTED_RECIPE_IDS:
        raise RecipeReplayVerificationError(f"Unexpected recipe_id: {recipe_id}")
    for key in ("title", "zh_title", "operator_goal", "platform_agent_role", "study_anything_role"):
        value = recipe.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RecipeReplayVerificationError(f"{recipe_id} missing {key}.")
        reject_private_text(value, label=f"{recipe_id}.{key}")

    commands = recipe.get("commands")
    if not isinstance(commands, list) or not commands:
        raise RecipeReplayVerificationError(f"{recipe_id} must include commands.")
    evidence = recipe.get("acceptance_evidence")
    if not isinstance(evidence, list) or not evidence:
        raise RecipeReplayVerificationError(f"{recipe_id} must include acceptance evidence.")

    missing_scripts: list[str] = []
    command_classes: list[str] = []
    command_scripts: list[str] = []
    for command in commands:
        if not isinstance(command, str) or not command.strip():
            raise RecipeReplayVerificationError(f"{recipe_id} has an empty command.")
        reject_private_text(command, label=f"{recipe_id}.commands")
        script = command_script(command)
        if not script:
            raise RecipeReplayVerificationError(f"{recipe_id} command does not reference a repo script: {command}")
        command_scripts.append(script)
        if not (ROOT / script).exists():
            missing_scripts.append(script)
        command_classes.append(classify_command(command))
    if missing_scripts:
        raise RecipeReplayVerificationError(f"{recipe_id} references missing scripts: {missing_scripts}")

    missing_evidence = [str(item) for item in evidence if str(item) not in evidence_text]
    if missing_evidence:
        raise RecipeReplayVerificationError(f"{recipe_id} evidence is not backed by public assets: {missing_evidence}")

    classes = sorted(set(command_classes))
    runtime_required = "runtime_required" in classes or "external_adoption" in classes
    human_gate_required = recipe_id == "risk_decision" or "human_gate" in classes
    if recipe_id == "risk_decision" and "human_gate" not in classes:
        raise RecipeReplayVerificationError("risk_decision recipe must include a Human Mastery Gate command.")
    if recipe_id == "learning_handoff" and "runtime_required" not in classes:
        raise RecipeReplayVerificationError("learning_handoff recipe must declare runtime-required commands.")

    return {
        "recipe_id": recipe_id,
        "command_count": len(commands),
        "evidence_count": len(evidence),
        "command_scripts": command_scripts,
        "command_classes": classes,
        "all_scripts_exist": True,
        "all_evidence_resolved": True,
        "runtime_required": runtime_required,
        "human_gate_required": human_gate_required,
        "metadata_replay_only": True,
    }


def verify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise RecipeReplayVerificationError("Cognitive Loop adoption recipes source schema drifted.")
    if payload.get("status") != "pass":
        raise RecipeReplayVerificationError("Cognitive Loop adoption recipes source must pass.")
    if payload.get("source_doc") != "docs/cognitive-loop-adoption-cookbook.md":
        raise RecipeReplayVerificationError("Cognitive Loop adoption recipes source_doc drifted.")
    if set(payload.get("supported_platforms", [])) != EXPECTED_PLATFORMS:
        raise RecipeReplayVerificationError("Cognitive Loop adoption recipes platform coverage drifted.")

    recipes = payload.get("recipes")
    if not isinstance(recipes, list) or len(recipes) != len(EXPECTED_RECIPE_IDS):
        raise RecipeReplayVerificationError("Cognitive Loop adoption recipes must include four recipes.")
    recipe_ids = {str(recipe.get("recipe_id")) for recipe in recipes if isinstance(recipe, dict)}
    if recipe_ids != EXPECTED_RECIPE_IDS:
        raise RecipeReplayVerificationError(f"Cognitive Loop adoption recipe ids drifted: {sorted(recipe_ids)}")

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
            raise RecipeReplayVerificationError(f"Cognitive Loop adoption recipes privacy.{key} must be false.")
    boundaries = payload.get("boundaries") or {}
    for key in (
        "platform_agent_owns_browser_files_apps_video_external_data",
        "study_anything_is_learning_adapter",
        "cognitive_loop_artifacts_are_metadata_only",
    ):
        if boundaries.get(key) is not True:
            raise RecipeReplayVerificationError(f"Cognitive Loop adoption recipes boundary {key} must be true.")
    for key in (
        "mastra_runtime_shipped",
        "watcher_daemon_shipped",
        "realtime_html_console_shipped",
        "standalone_frontend_required",
    ):
        if boundaries.get(key) is not False:
            raise RecipeReplayVerificationError(f"Cognitive Loop adoption recipes boundary {key} must be false.")

    evidence_text = public_evidence_text()
    replayed = [verify_recipe(recipe, evidence_text=evidence_text) for recipe in recipes]
    return {
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "source_doc": payload["source_doc"],
        "supported_platforms": sorted(payload["supported_platforms"]),
        "recipes": replayed,
        "all_commands_reference_existing_scripts": all(item["all_scripts_exist"] for item in replayed),
        "all_evidence_resolved": all(item["all_evidence_resolved"] for item in replayed),
        "runtime_required_recipe_ids": sorted(
            item["recipe_id"] for item in replayed if item["runtime_required"]
        ),
        "human_gate_recipe_ids": sorted(
            item["recipe_id"] for item in replayed if item["human_gate_required"]
        ),
    }


def build_report() -> dict[str, Any]:
    source = load_json(RECIPES_PATH)
    replay = verify_payload(source)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Verify Cognitive Loop adoption recipes are safe for platform Agent metadata replay.",
        "replay": replay,
        "safe_replay_policy": {
            "metadata_replay_only": True,
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
            "cognitive_loop_artifacts_are_metadata_only": True,
            "mastra_runtime_shipped": False,
            "watcher_daemon_shipped": False,
            "realtime_html_console_shipped": False,
            "standalone_frontend_required": False,
        },
        "commands": {
            "verify": "python3 scripts/verify_cognitive_loop_recipe_replay.py --check",
            "write": "python3 scripts/verify_cognitive_loop_recipe_replay.py --write",
            "source": "python3 scripts/generate_cognitive_loop_adoption_recipes.py --check",
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
            raise SystemExit(f"Cognitive Loop recipe replay report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop recipe replay report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_recipe_replay.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_recipe_replay failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
