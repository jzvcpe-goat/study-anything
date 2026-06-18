#!/usr/bin/env python3
"""Generate machine-readable Cognitive Loop adoption recipes for platform Agents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-adoption-recipes.json"
COOKBOOK = ROOT / "docs" / "cognitive-loop-adoption-cookbook.md"
SCHEMA_VERSION = "cognitive-loop-adoption-recipes-v1"

RECIPES: list[dict[str, Any]] = [
    {
        "recipe_id": "first_adoption",
        "title": "First Adoption",
        "zh_title": "首次接入",
        "operator_goal": "Prove the local-first platform Agent path before adding real model keys.",
        "platform_agent_role": "Keep the conversation surface, explain commands, and report only redacted evidence.",
        "study_anything_role": "Generate and verify the platform adoption pack, ecosystem submission, and adoption proof.",
        "commands": [
            "python3 scripts/generate_platform_adoption_pack.py --check",
            "python3 scripts/verify_ecosystem_submission_pack.py",
            "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
        ],
        "acceptance_evidence": [
            "adoption-proof-v1",
            "ecosystem-submission-verification-v1",
            "no standalone frontend requirement",
            "no Study Anything custody of real model keys",
        ],
    },
    {
        "recipe_id": "daily_project_review",
        "title": "Daily Project Review",
        "zh_title": "日常项目审查",
        "operator_goal": "Summarize current project state from local metadata-only Cognitive Loop artifacts.",
        "platform_agent_role": "Run local commands, open local HTML if allowed, and summarize artifact paths, hashes, status, and next commands.",
        "study_anything_role": "Create snapshots, LoopRuns, event indexes, and static artifact indexes without embedding file contents.",
        "commands": [
            "python3 scripts/cognitive_loop_cli.py init",
            "python3 scripts/cognitive_loop_cli.py snapshot --html",
            "python3 scripts/cognitive_loop_cli.py run-once --html",
            "python3 scripts/cognitive_loop_cli.py index --html",
            "python3 scripts/cognitive_loop_cli.py artifact-index --html",
        ],
        "acceptance_evidence": [
            "cognitive-loop-project-snapshot-verification-v1",
            "cognitive-loop-run-once-evidence-verification-v1",
            "cognitive-loop-event-index-verification-v1",
            "cognitive-loop-artifact-index-verification-v1",
        ],
    },
    {
        "recipe_id": "risk_decision",
        "title": "Risk Decision",
        "zh_title": "风险决策",
        "operator_goal": "Gate risky actions until the human explicitly approves or rejects the decision.",
        "platform_agent_role": "Request human approval, preserve the decision result, and never auto-apply repair actions.",
        "study_anything_role": "Record Human Mastery Gate status and produce manual-only doctor and repair-plan evidence.",
        "commands": [
            "python3 scripts/cognitive_loop_cli.py report --html",
            "python3 scripts/cognitive_loop_cli.py gate --reject --html --reason \"Needs human review\"",
            "python3 scripts/cognitive_loop_cli.py doctor --html",
            "python3 scripts/cognitive_loop_cli.py repair-plan --html",
            "python3 scripts/cognitive_loop_cli.py artifact-index --html",
        ],
        "acceptance_evidence": [
            "cognitive-loop-human-gate-verification-v1",
            "cognitive-loop-artifact-doctor-verification-v1",
            "cognitive-loop-repair-plan-verification-v1",
            "manual-only repair actions",
        ],
    },
    {
        "recipe_id": "learning_handoff",
        "title": "Learning Handoff",
        "zh_title": "学习交接",
        "operator_goal": "Turn repo, document, app, web, or video-slice context into learning, eval, and second-brain handoff evidence.",
        "platform_agent_role": "Collect external context and call Study Anything without handing it browser control or real model keys.",
        "study_anything_role": "Run source-bound learning, Agent audit/eval, Obsidian export, NotebookLM-style package, and second-brain handoff.",
        "commands": [
            "./scripts/run_skill_mode_demo.sh",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py",
        ],
        "acceptance_evidence": [
            "agent-eval-artifact-v1",
            "agent-eval-report-v1",
            "obsidian-markdown-export-v1",
            "learning-package-v1",
            "second-brain-handoff-v1",
        ],
    },
]

PRIVACY_DO_NOT_SHARE = [
    "raw source text",
    "diff bodies or file contents",
    "learner answers",
    "grading feedback",
    "generated private insights",
    "Agent endpoints or raw Agent metadata",
    "API keys, judge keys, or model secrets",
    "browser, video, app, or personal private context",
]


class AdoptionRecipesError(RuntimeError):
    """Readable adoption recipe generation failure."""


def read_cookbook() -> str:
    try:
        return COOKBOOK.read_text(encoding="utf-8")
    except OSError as exc:
        raise AdoptionRecipesError(f"Cannot read {COOKBOOK.relative_to(ROOT)}: {exc}") from exc


def validate_against_cookbook(payload: dict[str, Any]) -> None:
    text = read_cookbook()
    missing: list[str] = []
    for recipe in payload["recipes"]:
        for value in (recipe["title"], recipe["zh_title"], *recipe["commands"], *recipe["acceptance_evidence"]):
            if value not in text:
                missing.append(value)
    for item in payload["privacy"]["do_not_share"]:
        if item not in text:
            missing.append(item)
    if missing:
        raise AdoptionRecipesError(f"Cookbook is missing recipe text: {missing}")


def build_payload() -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "source_doc": "docs/cognitive-loop-adoption-cookbook.md",
        "purpose": "Machine-readable adoption recipes for Kimi, Codex, WorkBuddy, and private platform Agents.",
        "supported_platforms": ["kimi", "codex", "workbuddy", "private-platform-agent", "generic-openapi-tools"],
        "recipes": RECIPES,
        "privacy": {
            "do_not_share": PRIVACY_DO_NOT_SHARE,
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
            "generate": "python3 scripts/generate_cognitive_loop_adoption_recipes.py",
            "check": "python3 scripts/generate_cognitive_loop_adoption_recipes.py --check",
            "cookbook": "python3 scripts/verify_cognitive_loop_adoption_cookbook.py --check",
        },
    }
    validate_against_cookbook(payload)
    return payload


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()

    output = Path(args.output)
    serialized = dump_json(build_payload())
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop adoption recipes are missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop adoption recipes are stale. "
                "Run: python3 scripts/generate_cognitive_loop_adoption_recipes.py"
            )
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        print(f"wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_cognitive_loop_adoption_recipes failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
