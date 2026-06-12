#!/usr/bin/env python3
"""Verify platform ecosystem packs stay aligned with the public tool contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "platform" / "study-anything-platform-tools.json"
PACKS_DIR = ROOT / "platform" / "packs"
REQUIRED_PACKS = {"codex", "kimi", "workbuddy"}
REQUIRED_ACCEPTANCE = {
    "agent_audit.status == verified",
    "agent_eval_artifact.schema_version == agent-eval-artifact-v1",
    "all required native gates pass",
    "agent_eval_artifact.trajectory includes quiz.generate, answer.grade, insight.synthesize",
    "agent_quality_eval.schema_version == agent-quality-eval-v1",
    "agent_quality_eval.status == pass",
    "obsidian_export.schema_version == obsidian-markdown-export-v1",
    "learning_package.schema_version == learning-package-v1",
}
REQUIRED_COMMAND_FRAGMENTS = {
    "verify_platform_lesson_flow.py",
    "verify_platform_agent_tools.py",
    "verify_agent_eval_flow.py",
    "run_external_agent_evals.py --tool deepeval",
}
REQUIRED_ADOPTION_COMMAND_FRAGMENTS = {
    "verify_clean_clone_adoption.py",
    "diagnose_adoption.py",
}


class PackVerificationError(RuntimeError):
    """Readable platform pack verification failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PackVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PackVerificationError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def assert_text_contains(path: Path, *needles: str) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise PackVerificationError(f"{path.relative_to(ROOT)} is missing required text: {missing}")


def verify_pack(pack_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    pack_dir = PACKS_DIR / pack_id
    pack_path = pack_dir / "pack.json"
    readme_path = pack_dir / "README.md"
    if not pack_path.exists() or not readme_path.exists():
        raise PackVerificationError(f"{pack_id} must include pack.json and README.md")

    pack = load_json(pack_path)
    if pack.get("schema_version") != "study-anything-platform-pack-v1":
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} has invalid schema_version")
    if pack.get("platform_id") != pack_id:
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} platform_id mismatch")
    if not pack.get("name") or not pack.get("integration_mode"):
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} must declare name and integration_mode")

    import_assets = pack.get("import_assets")
    if not isinstance(import_assets, list) or not import_assets:
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} must declare import_assets")
    for asset in import_assets:
        if not isinstance(asset, str) or not (ROOT / asset).exists():
            raise PackVerificationError(f"{pack_path.relative_to(ROOT)} references missing asset: {asset}")
    if "platform/study-anything-platform-tools.json" not in import_assets:
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} must reference the source manifest")

    commands = pack.get("local_verification_commands")
    if not isinstance(commands, list) or not commands:
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} must declare verification commands")
    command_text = "\n".join(str(command) for command in commands)
    for fragment in REQUIRED_ADOPTION_COMMAND_FRAGMENTS:
        if fragment not in command_text:
            raise PackVerificationError(
                f"{pack_path.relative_to(ROOT)} verification commands must include {fragment}"
            )
    for fragment in REQUIRED_COMMAND_FRAGMENTS:
        if fragment not in command_text and pack_id != "codex":
            raise PackVerificationError(
                f"{pack_path.relative_to(ROOT)} verification commands must include {fragment}"
            )
    if pack_id == "codex" and "run_skill_mode_demo.sh" not in command_text:
        raise PackVerificationError("Codex pack must keep the Skill Mode demo as its primary check")
    if pack_id == "kimi" and "verify_openai_compatible_gateway.py" not in command_text:
        raise PackVerificationError("Kimi pack must verify the OpenAI-compatible gateway dry-run flow")

    acceptance = set(str(item) for item in pack.get("acceptance_evidence", []))
    missing_acceptance = REQUIRED_ACCEPTANCE - acceptance
    if missing_acceptance:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} is missing acceptance evidence: {sorted(missing_acceptance)}"
        )

    expected_privacy = set(manifest.get("privacy_contract", {}).get("must_not_log_or_share", []))
    pack_privacy = set(str(item) for item in pack.get("must_not_log_or_share", []))
    if pack_privacy != expected_privacy:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} privacy contract drifted: {sorted(pack_privacy)}"
        )

    assert_text_contains(
        readme_path,
        "agent-audit",
        "agent-eval",
        "quality",
        "Obsidian",
        "learning package",
        "raw source",
    )
    return pack


def main() -> None:
    manifest = load_json(MANIFEST_PATH)
    if manifest.get("schema_version") != "study-anything-platform-tools-v1":
        raise PackVerificationError("Source platform manifest has an unexpected schema_version")

    found = {path.name for path in PACKS_DIR.iterdir() if path.is_dir()}
    missing = REQUIRED_PACKS - found
    if missing:
        raise PackVerificationError(f"Missing required platform packs: {sorted(missing)}")

    packs = {pack_id: verify_pack(pack_id, manifest) for pack_id in sorted(REQUIRED_PACKS)}
    assert_text_contains(
        PACKS_DIR / "README.md",
        "codex",
        "kimi",
        "workbuddy",
        "verify_platform_ecosystem_packs.py",
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "schema_version": "study-anything-platform-pack-v1",
                "packs": sorted(packs),
                "import_asset_count": sum(len(pack["import_assets"]) for pack in packs.values()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_ecosystem_packs failed: {exc}", file=sys.stderr)
        sys.exit(1)
