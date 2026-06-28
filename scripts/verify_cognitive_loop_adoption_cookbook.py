#!/usr/bin/env python3
"""Verify the Cognitive Loop platform-agent adoption cookbook."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-adoption-cookbook.json"
COOKBOOK = ROOT / "docs" / "cognitive-loop-adoption-cookbook.md"
ECOSYSTEM_SUBMISSION = ROOT / "platform" / "ecosystem-submission.json"
PACKS_DIR = ROOT / "platform" / "packs"
BUNDLE_GENERATOR = ROOT / "scripts" / "generate_platform_bundle_manifest.py"
ADOPTION_PACK_GENERATOR = ROOT / "scripts" / "generate_platform_adoption_pack.py"
SCHEMA_VERSION = "cognitive-loop-adoption-cookbook-verification-v1"
REPORT_RELATIVE_PATH = "platform/generated/study-anything-cognitive-loop-adoption-cookbook.json"
SCRIPT_RELATIVE_PATH = "scripts/verify_cognitive_loop_adoption_cookbook.py"
COOKBOOK_RELATIVE_PATH = "docs/cognitive-loop-adoption-cookbook.md"
REQUIRED_PACKS = ("codex", "kimi", "workbuddy", "hermes")

REQUIRED_SECTIONS = (
    "# Cognitive Loop Adoption Cookbook / 认知自循环接入手册",
    "## Operating Split / 分工",
    "## Path 1: First Adoption / 路径一：首次接入",
    "## Path 2: Daily Project Review / 路径二：日常项目审查",
    "## Path 3: Risk Decision / 路径三：风险决策",
    "## Path 4: Learning Handoff / 路径四：学习交接",
    "## Platform Prompts / 平台 Agent 提示词",
    "## Privacy Boundary / 隐私边界",
    "## Quick Acceptance / 快速验收",
)

REQUIRED_COMMANDS = (
    "python3 scripts/generate_platform_adoption_pack.py --check",
    "python3 scripts/verify_ecosystem_submission_pack.py",
    "python3 scripts/verify_external_adoption.py",
    "python3 scripts/cognitive_loop_cli.py init",
    "python3 scripts/cognitive_loop_cli.py snapshot --html",
    "python3 scripts/cognitive_loop_cli.py run-once --html",
    "python3 scripts/cognitive_loop_cli.py index --html",
    "python3 scripts/cognitive_loop_cli.py artifact-index --html",
    "python3 scripts/cognitive_loop_cli.py report --html",
    "python3 scripts/cognitive_loop_cli.py gate --reject --html",
    "python3 scripts/cognitive_loop_cli.py doctor --html",
    "python3 scripts/cognitive_loop_cli.py repair-plan --html",
    "./scripts/run_skill_mode_demo.sh",
    "python3 scripts/verify_platform_lesson_flow.py",
    "python3 scripts/verify_importer_lesson_flow.py",
    "python3 scripts/verify_cognitive_loop_contracts.py --check",
    "python3 scripts/verify_cognitive_loop_artifact_index.py --check",
    "python3 scripts/generate_platform_bundle_manifest.py --check",
)

REQUIRED_PRIVACY_ITEMS = (
    "raw source text",
    "diff bodies or file contents",
    "learner answers",
    "grading feedback",
    "generated private insights",
    "Agent endpoints or raw Agent metadata",
    "API keys, judge keys, or model secrets",
    "browser, video, app, or personal private context",
)

REQUIRED_BOUNDARY_TEXT = (
    "local Learning Adapter",
    "rather than a standalone frontend",
    "no Study Anything custody of real model keys",
    "Do not ask it to browse, store model keys, or replace",
    "不要让它负责浏览器、真实模型密钥，或替代平台",
    "remain planned layers, not shipped requirements",
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


class CookbookVerificationError(RuntimeError):
    """Readable cookbook verification failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CookbookVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CookbookVerificationError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CookbookVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc


def require_text(text: str, needles: tuple[str, ...], *, label: str) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise CookbookVerificationError(f"{label} is missing required text: {missing}")


def reject_text(text: str, needles: tuple[str, ...], *, label: str) -> None:
    lowered = text.lower()
    leaked = [needle for needle in needles if needle.lower() in lowered]
    if leaked:
        raise CookbookVerificationError(f"{label} contains forbidden claim text: {leaked}")


def verify_cookbook_text(text: str) -> dict[str, Any]:
    require_text(text, REQUIRED_SECTIONS, label=COOKBOOK_RELATIVE_PATH)
    require_text(text, REQUIRED_COMMANDS, label=COOKBOOK_RELATIVE_PATH)
    require_text(text, REQUIRED_PRIVACY_ITEMS, label=COOKBOOK_RELATIVE_PATH)
    require_text(text, REQUIRED_BOUNDARY_TEXT, label=COOKBOOK_RELATIVE_PATH)
    reject_text(text, FORBIDDEN_CLAIMS, label=COOKBOOK_RELATIVE_PATH)
    for platform in ("Kimi", "Codex", "WorkBuddy"):
        if platform not in text:
            raise CookbookVerificationError(f"{COOKBOOK_RELATIVE_PATH} must mention {platform}.")
    return {
        "path": COOKBOOK_RELATIVE_PATH,
        "sections": len(REQUIRED_SECTIONS),
        "commands": len(REQUIRED_COMMANDS),
        "privacy_items": len(REQUIRED_PRIVACY_ITEMS),
        "bilingual": True,
        "planned_layers_not_shipped": True,
        "standalone_frontend_required": False,
        "real_model_key_custody": False,
    }


def verify_pack(pack_id: str) -> dict[str, Any]:
    pack_path = PACKS_DIR / pack_id / "pack.json"
    readme_path = PACKS_DIR / pack_id / "README.md"
    pack = load_json(pack_path)
    import_assets = set(str(asset) for asset in pack.get("import_assets", []))
    commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
    acceptance = set(str(item) for item in pack.get("acceptance_evidence", []))
    if COOKBOOK_RELATIVE_PATH not in import_assets:
        raise CookbookVerificationError(f"{pack_path.relative_to(ROOT)} must import the cookbook.")
    if REPORT_RELATIVE_PATH not in import_assets:
        raise CookbookVerificationError(f"{pack_path.relative_to(ROOT)} must import the cookbook report.")
    if SCRIPT_RELATIVE_PATH not in commands:
        raise CookbookVerificationError(f"{pack_path.relative_to(ROOT)} must run the cookbook verifier.")
    if f"cognitive_loop_adoption_cookbook.schema_version == {SCHEMA_VERSION}" not in acceptance:
        raise CookbookVerificationError(f"{pack_path.relative_to(ROOT)} must accept the cookbook report schema.")
    readme = read_text(readme_path)
    require_text(readme, (COOKBOOK_RELATIVE_PATH, "platform Agent", "local Cognitive Loop"), label=str(readme_path.relative_to(ROOT)))
    return {
        "platform_id": pack_id,
        "imports_cookbook": True,
        "imports_report": True,
        "runs_verifier": True,
        "accepts_schema": True,
    }


def verify_ecosystem_submission() -> dict[str, Any]:
    submission = load_json(ECOSYSTEM_SUBMISSION)
    shared_assets = set(str(asset) for asset in submission.get("shared_assets", []))
    for asset in (COOKBOOK_RELATIVE_PATH, REPORT_RELATIVE_PATH, SCRIPT_RELATIVE_PATH):
        if asset not in shared_assets:
            raise CookbookVerificationError(f"platform/ecosystem-submission.json shared_assets missing {asset}.")

    minimum_commands = "\n".join(str(command) for command in submission.get("acceptance", {}).get("minimum_commands", []))
    if SCRIPT_RELATIVE_PATH not in minimum_commands:
        raise CookbookVerificationError("ecosystem submission minimum_commands must run the cookbook verifier.")
    must_prove = "\n".join(str(item) for item in submission.get("acceptance", {}).get("must_prove", []))
    if SCHEMA_VERSION not in must_prove:
        raise CookbookVerificationError("ecosystem submission must_prove must mention the cookbook schema.")

    missing_imports: list[str] = []
    for entry in submission.get("submissions", []):
        import_assets = set(str(asset) for asset in entry.get("import_assets", []))
        for asset in (COOKBOOK_RELATIVE_PATH, REPORT_RELATIVE_PATH):
            if asset not in import_assets:
                missing_imports.append(f"{entry.get('platform')}:{asset}")
    if missing_imports:
        raise CookbookVerificationError(f"ecosystem submission entries missing cookbook imports: {missing_imports}")
    return {
        "shared_assets_registered": True,
        "minimum_command_registered": True,
        "must_prove_registered": True,
        "submission_imports_registered": True,
    }


def verify_source_generators() -> dict[str, Any]:
    bundle_text = read_text(BUNDLE_GENERATOR)
    adoption_text = read_text(ADOPTION_PACK_GENERATOR)
    for path, label, text in (
        (REPORT_RELATIVE_PATH, "bundle generator", bundle_text),
        (SCRIPT_RELATIVE_PATH, "bundle generator", bundle_text),
        (COOKBOOK_RELATIVE_PATH, "bundle generator", bundle_text),
        (REPORT_RELATIVE_PATH, "adoption pack generator", adoption_text),
        (SCRIPT_RELATIVE_PATH, "adoption pack generator", adoption_text),
        (COOKBOOK_RELATIVE_PATH, "adoption pack generator", adoption_text),
    ):
        if path not in text:
            raise CookbookVerificationError(f"{label} must include {path}.")
    return {
        "bundle_manifest_source_registered": True,
        "adoption_pack_source_registered": True,
    }


def build_report() -> dict[str, Any]:
    text = read_text(COOKBOOK)
    cookbook = verify_cookbook_text(text)
    packs = [verify_pack(pack_id) for pack_id in REQUIRED_PACKS]
    ecosystem = verify_ecosystem_submission()
    generators = verify_source_generators()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "cookbook": cookbook,
        "platform_packs": packs,
        "ecosystem_submission": ecosystem,
        "distribution_sources": generators,
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
            "verify": f"python3 {SCRIPT_RELATIVE_PATH} --check",
            "generate_pack": "python3 scripts/generate_platform_adoption_pack.py --check",
            "external_adoption": "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
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
            raise SystemExit(f"Cognitive Loop adoption cookbook report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop adoption cookbook report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_adoption_cookbook.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_adoption_cookbook failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
