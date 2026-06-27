#!/usr/bin/env python3
"""Read-only Cognitive Loop recipe CLI for platform Agents."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RECIPES_PATH = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-adoption-recipes.json"
REPLAY_PATH = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-replay.json"
SCHEMA_VERSION = "cognitive-loop-recipe-cli-v1"
SOURCE_SCHEMA_VERSION = "cognitive-loop-adoption-recipes-v1"


class CognitiveLoopRecipeCliError(RuntimeError):
    """Readable recipe CLI failure."""


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CognitiveLoopRecipeCliError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CognitiveLoopRecipeCliError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def _load_recipes(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if payload.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise CognitiveLoopRecipeCliError("Cognitive Loop adoption recipes schema drifted.")
    if payload.get("status") != "pass":
        raise CognitiveLoopRecipeCliError("Cognitive Loop adoption recipes must have status=pass.")
    recipes = payload.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        raise CognitiveLoopRecipeCliError("Cognitive Loop adoption recipes are empty.")
    return payload


def _command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError as exc:
        raise CognitiveLoopRecipeCliError(f"Command is not shell-tokenizable: {command}") from exc


def _command_script(command: str) -> str | None:
    tokens = _command_tokens(command)
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


def _classify_command(command: str) -> str:
    script = _command_script(command) or ""
    script_name = Path(script).name
    if script_name in {"run_skill_mode_demo.sh", "verify_platform_lesson_flow.py", "verify_importer_lesson_flow.py"}:
        return "runtime_required"
    if script_name == "verify_external_adoption.py":
        return "external_adoption"
    if " gate --reject" in f" {command}" or " gate --approve" in f" {command}":
        return "human_gate"
    if "repair-plan" in command:
        return "manual_repair_plan"
    return "metadata_only"


def _recipe_summary(recipe: dict[str, Any]) -> dict[str, Any]:
    commands = [str(command) for command in recipe.get("commands", [])]
    classes = sorted({_classify_command(command) for command in commands})
    return {
        "recipe_id": recipe.get("recipe_id"),
        "title": recipe.get("title"),
        "zh_title": recipe.get("zh_title"),
        "operator_goal": recipe.get("operator_goal"),
        "command_count": len(commands),
        "acceptance_evidence_count": len(recipe.get("acceptance_evidence", [])),
        "command_classes": classes,
        "runtime_required": "runtime_required" in classes or "external_adoption" in classes,
        "human_gate_required": "human_gate" in classes,
        "metadata_only_plan": True,
    }


def _recipe_plan(recipe: dict[str, Any]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for index, command in enumerate([str(item) for item in recipe.get("commands", [])], start=1):
        script = _command_script(command)
        steps.append(
            {
                "step": index,
                "command": command,
                "command_class": _classify_command(command),
                "script": script,
                "script_exists": bool(script and (ROOT / script).exists()),
            }
        )
    summary = _recipe_summary(recipe)
    return {
        **summary,
        "platform_agent_role": recipe.get("platform_agent_role"),
        "study_anything_role": recipe.get("study_anything_role"),
        "acceptance_evidence": list(recipe.get("acceptance_evidence", [])),
        "steps": steps,
        "safe_to_auto_execute": False,
        "requires_operator_before_runtime": summary["runtime_required"],
        "requires_human_mastery_gate": summary["human_gate_required"],
    }


def _base_payload(source: dict[str, Any], *, action: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "action": action,
        "source_schema_version": source["schema_version"],
        "source_doc": source.get("source_doc"),
        "source_path": RECIPES_PATH.relative_to(ROOT).as_posix(),
        "replay_path": REPLAY_PATH.relative_to(ROOT).as_posix(),
        "safe_replay_policy": {
            "metadata_only": True,
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
    }


def cmd_list(args: argparse.Namespace) -> int:
    source = _load_recipes(Path(args.recipes))
    recipes = [_recipe_summary(recipe) for recipe in source["recipes"]]
    payload = {
        **_base_payload(source, action="list"),
        "recipe_count": len(recipes),
        "recipe_ids": [str(recipe["recipe_id"]) for recipe in recipes],
        "recipes": recipes,
    }
    print(_dump(payload), end="")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    source = _load_recipes(Path(args.recipes))
    recipes = {str(recipe.get("recipe_id")): recipe for recipe in source["recipes"]}
    recipe = recipes.get(args.recipe_id)
    if recipe is None:
        raise CognitiveLoopRecipeCliError(f"Unknown recipe_id: {args.recipe_id}")
    payload = {
        **_base_payload(source, action="show"),
        "recipe": _recipe_plan(recipe),
    }
    print(_dump(payload), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recipes",
        default=str(RECIPES_PATH),
        help="Path to cognitive-loop-adoption-recipes-v1 JSON.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List available Cognitive Loop recipes as JSON.")
    list_cmd.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="Show a single Cognitive Loop recipe plan as JSON.")
    show.add_argument("recipe_id")
    show.set_defaults(func=cmd_show)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"cognitive_loop_recipe_cli failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
