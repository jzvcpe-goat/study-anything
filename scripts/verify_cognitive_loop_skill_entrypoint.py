#!/usr/bin/env python3
"""Verify Cognitive Loop recipe entrypoints are visible from the Skill and platform packs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-skill-entrypoint.json"
SKILL = ROOT / "skills" / "study-anything" / "SKILL.md"
PACKS_DIR = ROOT / "platform" / "packs"
ECOSYSTEM_SUBMISSION = ROOT / "platform" / "ecosystem-submission.json"
BUNDLE_GENERATOR = ROOT / "scripts" / "generate_platform_bundle_manifest.py"
ADOPTION_PACK_GENERATOR = ROOT / "scripts" / "generate_platform_adoption_pack.py"
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"
PLATFORM_PACK_VERIFIER = ROOT / "scripts" / "verify_platform_ecosystem_packs.py"
ECOSYSTEM_SUBMISSION_VERIFIER = ROOT / "scripts" / "verify_ecosystem_submission_pack.py"

SCHEMA_VERSION = "cognitive-loop-skill-entrypoint-verification-v1"
REPORT_RELATIVE_PATH = "platform/generated/study-anything-cognitive-loop-skill-entrypoint.json"
SCRIPT_RELATIVE_PATH = "scripts/verify_cognitive_loop_skill_entrypoint.py"
COOKBOOK_RELATIVE_PATH = "docs/cognitive-loop-adoption-cookbook.md"
RECIPES_RELATIVE_PATH = "platform/generated/study-anything-cognitive-loop-adoption-recipes.json"
REPLAY_RELATIVE_PATH = "platform/generated/study-anything-cognitive-loop-recipe-replay.json"
REQUIRED_PACKS = ("codex", "kimi", "workbuddy", "hermes")

REQUIRED_RECIPE_IDS = (
    "first_adoption",
    "daily_project_review",
    "risk_decision",
    "learning_handoff",
)
REQUIRED_COMMANDS = (
    "python3 scripts/verify_cognitive_loop_adoption_cookbook.py --check",
    "python3 scripts/generate_cognitive_loop_adoption_recipes.py --check",
    "python3 scripts/verify_cognitive_loop_recipe_replay.py --check",
    "python3 scripts/verify_cognitive_loop_skill_entrypoint.py --check",
)
REQUIRED_SKILL_TEXT = (
    "## Cognitive Loop Recipes",
    COOKBOOK_RELATIVE_PATH,
    RECIPES_RELATIVE_PATH,
    REPLAY_RELATIVE_PATH,
    "metadata-only replay",
    "does not execute recipe commands",
    "start runtime",
    "apply file changes",
    "Human Mastery Gate",
    "platform Agent owns browser",
    "Study Anything owns the local Learning Adapter",
    "raw source text",
    "diff bodies",
    "learner answers",
    "grading feedback",
    "generated private insights",
    "Agent endpoints",
    "raw Agent metadata",
    "API keys",
    "model secrets",
    "browser/video/app private context",
)
REQUIRED_README_TEXT = (
    COOKBOOK_RELATIVE_PATH,
    RECIPES_RELATIVE_PATH,
    REPLAY_RELATIVE_PATH,
    SCRIPT_RELATIVE_PATH,
    "machine-readable",
    "human-gated",
)
FORBIDDEN_CLAIMS = (
    "Mastra runtime is shipped",
    "Mastra is integrated",
    "watcher daemon is shipped",
    "realtime HTML console is shipped",
    "standalone frontend is required",
    "Study Anything stores real model keys",
    "Study Anything 托管真实模型密钥",
)


class SkillEntrypointVerificationError(RuntimeError):
    """Readable Skill entrypoint verification failure."""


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillEntrypointVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise SkillEntrypointVerificationError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def require_text(text: str, needles: tuple[str, ...], *, label: str) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SkillEntrypointVerificationError(f"{label} is missing required text: {missing}")


def reject_text(text: str, needles: tuple[str, ...], *, label: str) -> None:
    lowered = text.lower()
    leaked = [needle for needle in needles if needle.lower() in lowered]
    if leaked:
        raise SkillEntrypointVerificationError(f"{label} contains forbidden claim text: {leaked}")


def verify_skill() -> dict[str, Any]:
    text = read_text(SKILL)
    require_text(text, REQUIRED_SKILL_TEXT + REQUIRED_RECIPE_IDS + REQUIRED_COMMANDS, label="skills/study-anything/SKILL.md")
    reject_text(text, FORBIDDEN_CLAIMS, label="skills/study-anything/SKILL.md")
    return {
        "path": "skills/study-anything/SKILL.md",
        "mentions_cookbook": True,
        "mentions_recipe_matrix": True,
        "mentions_replay_report": True,
        "recipe_ids": list(REQUIRED_RECIPE_IDS),
        "verification_commands": list(REQUIRED_COMMANDS),
        "metadata_only_replay": True,
        "human_gate_explicit": True,
        "privacy_boundary_explicit": True,
    }


def verify_pack_readme(pack_id: str) -> dict[str, Any]:
    path = PACKS_DIR / pack_id / "README.md"
    text = read_text(path)
    require_text(text, REQUIRED_README_TEXT + REQUIRED_COMMANDS, label=str(path.relative_to(ROOT)))
    reject_text(text, FORBIDDEN_CLAIMS, label=str(path.relative_to(ROOT)))
    return {
        "platform_id": pack_id,
        "path": str(path.relative_to(ROOT)),
        "mentions_cookbook": True,
        "mentions_recipe_matrix": True,
        "mentions_replay_report": True,
        "runs_skill_entrypoint_verifier": True,
    }


def verify_pack_manifest(pack_id: str) -> dict[str, Any]:
    path = PACKS_DIR / pack_id / "pack.json"
    pack = load_json(path)
    import_assets = set(str(asset) for asset in pack.get("import_assets", []))
    for asset in (COOKBOOK_RELATIVE_PATH, RECIPES_RELATIVE_PATH, REPLAY_RELATIVE_PATH, REPORT_RELATIVE_PATH):
        if asset not in import_assets:
            raise SkillEntrypointVerificationError(f"{path.relative_to(ROOT)} import_assets missing {asset}.")
    commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
    for command in REQUIRED_COMMANDS:
        if command not in commands:
            raise SkillEntrypointVerificationError(f"{path.relative_to(ROOT)} commands missing {command}.")
    acceptance = set(str(item) for item in pack.get("acceptance_evidence", []))
    expected = f"cognitive_loop_skill_entrypoint.schema_version == {SCHEMA_VERSION}"
    if expected not in acceptance:
        raise SkillEntrypointVerificationError(f"{path.relative_to(ROOT)} acceptance evidence missing {expected}.")
    return {
        "platform_id": pack_id,
        "imports_report": True,
        "runs_verifier": True,
        "accepts_schema": True,
    }


def verify_ecosystem_submission() -> dict[str, Any]:
    submission = load_json(ECOSYSTEM_SUBMISSION)
    shared_assets = set(str(asset) for asset in submission.get("shared_assets", []))
    for asset in (REPORT_RELATIVE_PATH, SCRIPT_RELATIVE_PATH, RECIPES_RELATIVE_PATH, REPLAY_RELATIVE_PATH):
        if asset not in shared_assets:
            raise SkillEntrypointVerificationError(f"platform/ecosystem-submission.json shared_assets missing {asset}.")
    commands = "\n".join(str(command) for command in submission.get("acceptance", {}).get("minimum_commands", []))
    if REQUIRED_COMMANDS[-1] not in commands:
        raise SkillEntrypointVerificationError("ecosystem submission minimum_commands must run the Skill entrypoint verifier.")
    must_prove = "\n".join(str(item) for item in submission.get("acceptance", {}).get("must_prove", []))
    if SCHEMA_VERSION not in must_prove:
        raise SkillEntrypointVerificationError("ecosystem submission must_prove must mention the Skill entrypoint schema.")

    missing_imports: list[str] = []
    for entry in submission.get("submissions", []):
        import_assets = set(str(asset) for asset in entry.get("import_assets", []))
        for asset in (REPORT_RELATIVE_PATH, RECIPES_RELATIVE_PATH, REPLAY_RELATIVE_PATH):
            if asset not in import_assets:
                missing_imports.append(f"{entry.get('platform')}:{asset}")
    if missing_imports:
        raise SkillEntrypointVerificationError(f"ecosystem submission entries missing Skill entrypoint imports: {missing_imports}")
    return {
        "shared_assets_registered": True,
        "minimum_command_registered": True,
        "must_prove_registered": True,
        "submission_imports_registered": True,
    }


def verify_distribution_sources() -> dict[str, Any]:
    for path, label in (
        (BUNDLE_GENERATOR, "bundle generator"),
        (ADOPTION_PACK_GENERATOR, "adoption pack generator"),
    ):
        text = read_text(path)
        for needle in (REPORT_RELATIVE_PATH, SCRIPT_RELATIVE_PATH):
            if needle not in text:
                raise SkillEntrypointVerificationError(f"{label} must include {needle}.")

    release_text = read_text(RELEASE_CHECK)
    if "verify_cognitive_loop_skill_entrypoint.py --check" not in release_text:
        raise SkillEntrypointVerificationError("release check must run verify_cognitive_loop_skill_entrypoint.py --check.")

    platform_verifier_text = read_text(PLATFORM_PACK_VERIFIER)
    for needle in (REPORT_RELATIVE_PATH, "verify_cognitive_loop_skill_entrypoint.py --check"):
        if needle not in platform_verifier_text:
            raise SkillEntrypointVerificationError(f"platform pack verifier must include {needle}.")

    ecosystem_verifier_text = read_text(ECOSYSTEM_SUBMISSION_VERIFIER)
    for needle in (REPORT_RELATIVE_PATH, SCRIPT_RELATIVE_PATH, SCHEMA_VERSION):
        if needle not in ecosystem_verifier_text:
            raise SkillEntrypointVerificationError(f"ecosystem submission verifier must include {needle}.")
    return {
        "bundle_manifest_source_registered": True,
        "adoption_pack_source_registered": True,
        "release_check_registered": True,
        "platform_pack_verifier_registered": True,
        "ecosystem_submission_verifier_registered": True,
    }


def verify_platform_pack_index() -> dict[str, Any]:
    path = PACKS_DIR / "README.md"
    text = read_text(path)
    require_text(text, (REPORT_RELATIVE_PATH, SCRIPT_RELATIVE_PATH, "repo-local Skill"), label=str(path.relative_to(ROOT)))
    return {
        "path": str(path.relative_to(ROOT)),
        "mentions_report": True,
        "runs_verifier": True,
    }


def build_report() -> dict[str, Any]:
    skill = verify_skill()
    pack_readmes = [verify_pack_readme(pack_id) for pack_id in REQUIRED_PACKS]
    pack_manifests = [verify_pack_manifest(pack_id) for pack_id in REQUIRED_PACKS]
    platform_pack_index = verify_platform_pack_index()
    ecosystem_submission = verify_ecosystem_submission()
    distribution_sources = verify_distribution_sources()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Verify Cognitive Loop recipe and replay entrypoints are discoverable from the Skill and platform packs.",
        "skill": skill,
        "platform_pack_index": platform_pack_index,
        "platform_pack_readmes": pack_readmes,
        "platform_pack_manifests": pack_manifests,
        "ecosystem_submission": ecosystem_submission,
        "distribution_sources": distribution_sources,
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
            "skill_entrypoint_is_recipe_index": True,
            "cognitive_loop_artifacts_are_metadata_only": True,
            "mastra_runtime_shipped": False,
            "watcher_daemon_shipped": False,
            "realtime_html_console_shipped": False,
            "standalone_frontend_required": False,
        },
        "commands": {
            "verify": f"python3 {SCRIPT_RELATIVE_PATH} --check",
            "write": f"python3 {SCRIPT_RELATIVE_PATH} --write",
            "cookbook": "python3 scripts/verify_cognitive_loop_adoption_cookbook.py --check",
            "recipes": "python3 scripts/generate_cognitive_loop_adoption_recipes.py --check",
            "replay": "python3 scripts/verify_cognitive_loop_recipe_replay.py --check",
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
            raise SystemExit(f"Cognitive Loop Skill entrypoint report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Skill entrypoint report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_skill_entrypoint.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_skill_entrypoint failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
