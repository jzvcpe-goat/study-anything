#!/usr/bin/env python3
"""Generate and verify the external platform handoff checklist."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-platform-handoff-checklist.json"
SUBMISSION = ROOT / "platform" / "ecosystem-submission.json"
ADOPTION_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.json"
PACKS_DIR = ROOT / "platform" / "packs"
VERSION = "v0.3.31-alpha"
SCHEMA_VERSION = "platform-handoff-checklist-v1"
PRIVATE_NEEDLES = (
    "sk-proj-",
    "bearer ",
    "api_key",
    "secret_access_key",
    "raw private source text",
    "learner answer:",
    "http://127.0.0.1:8787/",
)
REQUIRED_PLATFORM_IDS = {
    "codex-skill",
    "generic-openapi-tools",
    "kimi-compatible",
    "workbuddy-style-http",
}
PACK_BY_PLATFORM = {
    "codex": "codex-skill",
    "kimi": "kimi-compatible",
    "workbuddy": "workbuddy-style-http",
}
REQUIRED_HANDOFF_COMMANDS = (
    "python3 scripts/verify_platform_handoff_checklist.py --check",
    "python3 scripts/verify_cognitive_loop_pack_extract_smoke.py --check",
    "python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check",
    "python3 scripts/generate_platform_feedback_package.py --check",
)
REQUIRED_HANDOFF_ASSETS = (
    "platform/ecosystem-submission.json",
    "platform/generated/study-anything-platform-adoption-pack.zip",
    "platform/generated/study-anything-platform-bundle.json",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
    "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json",
    "platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json",
    "platform/generated/study-anything-platform-feedback-package.json",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-release-asset-bootstrap.json",
    "platform/generated/study-anything-adopter-evidence-archive.json",
)


class PlatformHandoffChecklistError(RuntimeError):
    """Readable platform handoff checklist verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PlatformHandoffChecklistError(f"Cannot read {relative_path(path)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PlatformHandoffChecklistError(f"{relative_path(path)} is not valid JSON: {exc}") from exc


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def reject_private_text(value: str, *, label: str) -> None:
    lowered = value.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle in lowered]
    if leaked:
        raise PlatformHandoffChecklistError(f"{label} contains private or secret-like text: {leaked}")


def require_file(path: str) -> None:
    if not (ROOT / path).exists():
        raise PlatformHandoffChecklistError(f"Required handoff asset is missing: {path}")


def submission_by_platform(submission: dict[str, Any]) -> dict[str, dict[str, Any]]:
    platforms = submission.get("submissions") or submission.get("platforms")
    if not isinstance(platforms, list):
        raise PlatformHandoffChecklistError("ecosystem-submission platforms must be a list.")
    by_id = {
        str(item.get("platform_id")): item
        for item in platforms
        if isinstance(item, dict) and item.get("platform_id")
    }
    missing = REQUIRED_PLATFORM_IDS - set(by_id)
    if missing:
        raise PlatformHandoffChecklistError(f"ecosystem-submission missing platforms: {sorted(missing)}")
    return by_id


def verify_adoption_manifest() -> dict[str, Any]:
    manifest = load_json(ADOPTION_PACK)
    if manifest.get("schema_version") != "study-anything-platform-adoption-pack-v1":
        raise PlatformHandoffChecklistError("Adoption pack manifest schema drifted.")
    if manifest.get("version") != VERSION:
        raise PlatformHandoffChecklistError("Adoption pack version drifted.")
    if manifest.get("no_frontend_required") is not True:
        raise PlatformHandoffChecklistError("Adoption pack must remain no-frontend required.")
    if manifest.get("real_model_keys_stored_by_study_anything") is not False:
        raise PlatformHandoffChecklistError("Study Anything must not store real model keys.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    self_references = {
        str(ADOPTION_PACK.relative_to(ROOT)),
        "platform/generated/study-anything-platform-adoption-pack.zip",
    }
    missing = [asset for asset in REQUIRED_HANDOFF_ASSETS if asset not in self_references and asset not in paths]
    if missing:
        raise PlatformHandoffChecklistError(f"Adoption pack manifest is missing handoff assets: {missing}")
    return manifest


def build_platform_rows(submission: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = submission_by_platform(submission)
    rows: list[dict[str, Any]] = []
    for pack_id, platform_id in sorted(PACK_BY_PLATFORM.items()):
        pack = load_json(PACKS_DIR / pack_id / "pack.json")
        submission_row = by_id[platform_id]
        import_assets = [str(item) for item in pack.get("import_assets", [])]
        commands = [str(item) for item in pack.get("local_verification_commands", [])]
        acceptance = set(str(item) for item in pack.get("acceptance_evidence", []))
        command_text = "\n".join(commands)
        for command in REQUIRED_HANDOFF_COMMANDS:
            if command not in command_text:
                raise PlatformHandoffChecklistError(f"{pack_id} pack is missing command: {command}")
        if "platform/generated/study-anything-platform-feedback-package.json" not in import_assets:
            raise PlatformHandoffChecklistError(f"{pack_id} pack must include the feedback package.")
        if "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json" not in import_assets:
            raise PlatformHandoffChecklistError(f"{pack_id} pack must include the extracted pack smoke report.")
        if "platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json" not in import_assets:
            raise PlatformHandoffChecklistError(f"{pack_id} pack must include the Review Agent workflow install smoke report.")
        if "platform_handoff_checklist.schema_version == platform-handoff-checklist-v1" not in acceptance:
            raise PlatformHandoffChecklistError(f"{pack_id} pack must include handoff checklist evidence.")
        if submission_row.get("no_frontend_required") is not True:
            raise PlatformHandoffChecklistError(f"{platform_id} must remain no-frontend required.")
        rows.append(
            {
                "pack_id": pack_id,
                "platform_id": platform_id,
                "integration_mode": pack.get("integration_mode"),
                "submission_integration_mode": submission_row.get("integration_mode"),
                "import_asset_count": len(import_assets),
                "verification_command_count": len(commands),
                "declares_extract_smoke": True,
                "declares_review_agent_workflow_install_smoke": True,
                "declares_feedback_package": True,
                "declares_handoff_checklist": True,
                "no_frontend_required": True,
            }
        )
    generic = by_id["generic-openapi-tools"]
    rows.append(
        {
            "pack_id": None,
            "platform_id": "generic-openapi-tools",
            "integration_mode": generic.get("integration_mode"),
            "submission_integration_mode": generic.get("integration_mode"),
            "import_asset_count": len(generic.get("import_assets", [])),
            "verification_command_count": len(generic.get("verification_commands", [])),
            "declares_extract_smoke": "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json"
            in set(str(item) for item in generic.get("import_assets", [])),
            "declares_review_agent_workflow_install_smoke": (
                "platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json"
                in set(str(item) for item in generic.get("import_assets", []))
            ),
            "declares_feedback_package": "platform/generated/study-anything-platform-feedback-package.json"
            in set(str(item) for item in generic.get("import_assets", [])),
            "declares_handoff_checklist": "platform/generated/study-anything-platform-handoff-checklist.json"
            in set(str(item) for item in generic.get("import_assets", [])),
            "no_frontend_required": generic.get("no_frontend_required") is True,
        }
    )
    if any(row["declares_handoff_checklist"] is not True for row in rows):
        raise PlatformHandoffChecklistError("Every handoff row must declare the handoff checklist.")
    return rows


def build_report() -> dict[str, Any]:
    submission = load_json(SUBMISSION)
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise PlatformHandoffChecklistError("Ecosystem submission schema drifted.")
    if submission.get("version") != VERSION:
        raise PlatformHandoffChecklistError("Ecosystem submission version drifted.")
    if submission.get("real_model_keys_stored_by_study_anything", False) is not False:
        raise PlatformHandoffChecklistError("Ecosystem submission must not store real model keys.")
    if submission.get("no_frontend_required", True) is not True:
        raise PlatformHandoffChecklistError("Ecosystem submission must stay no-frontend required.")
    adoption_manifest = verify_adoption_manifest()
    for asset in REQUIRED_HANDOFF_ASSETS:
        require_file(asset)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "purpose": (
            "Give external platform operators a copy-ready handoff checklist for importing, "
            "verifying, and escalating Study Anything without a standalone frontend."
        ),
        "handoff_assets": {
            "required_assets": list(REQUIRED_HANDOFF_ASSETS),
            "all_required_assets_present": True,
            "adoption_pack_file_count": len(adoption_manifest.get("files", [])),
            "adoption_pack_schema": adoption_manifest["schema_version"],
        },
        "platforms": build_platform_rows(submission),
        "checklist": [
            {
                "step_id": "extract_and_validate_pack",
                "operator_action": "Extract the adoption pack and run bundled schema consumer checks.",
                "command": "python3 scripts/verify_cognitive_loop_pack_extract_smoke.py --check",
                "blocks_release": True,
            },
            {
                "step_id": "install_review_agent_workflow",
                "operator_action": "Copy the Review Agent workflow from the adoption pack into .github/workflows and run the metadata-only install smoke.",
                "command": "python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check",
                "blocks_release": True,
            },
            {
                "step_id": "import_platform_assets",
                "operator_action": "Import the OpenAPI, OpenAI tools, or platform pack assets for the target host.",
                "assets": [
                    "platform/generated/study-anything-platform-openapi.json",
                    "platform/generated/study-anything-openai-tools.json",
                    "platform/packs/{codex,kimi,workbuddy}/pack.json",
                ],
                "blocks_release": True,
            },
            {
                "step_id": "run_static_acceptance",
                "operator_action": "Run ecosystem, platform-pack, and external-adoption verifiers.",
                "commands": [
                    "python3 scripts/verify_ecosystem_submission_pack.py",
                    "python3 scripts/verify_platform_ecosystem_packs.py",
                    "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --current-worktree",
                ],
                "blocks_release": True,
            },
            {
                "step_id": "choose_runtime_path",
                "operator_action": "Use Skill Mode first; use published images or source Compose only when needed.",
                "commands": [
                    "./scripts/launch_skill_mode.sh",
                    "USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh",
                    "./scripts/launch_self_host.sh",
                ],
                "blocks_release": False,
            },
            {
                "step_id": "connect_user_owned_agent",
                "operator_action": "Register a user-owned HTTP Agent endpoint outside Study Anything.",
                "secret_boundary": "Study Anything stores endpoint metadata and capabilities, not real model keys.",
                "blocks_release": False,
            },
            {
                "step_id": "collect_redacted_feedback",
                "operator_action": "If import fails, generate the local-only redacted feedback package and open a GitHub issue.",
                "command": "python3 scripts/generate_platform_feedback_package.py",
                "blocks_release": False,
            },
        ],
        "acceptance": {
            "minimum_command": "python3 scripts/verify_platform_handoff_checklist.py --check",
            "release_gate": "scripts/release_check.sh",
            "evidence": "platform_handoff_checklist.schema_version == platform-handoff-checklist-v1",
        },
        "privacy_assertions": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_stored_by_study_anything": False,
            "automatic_upload": False,
            "standalone_frontend_required": False,
            "browser_video_private_context_included": False,
            "report_is_redacted": True,
        },
    }
    reject_private_text(dump_json(report), label="platform handoff checklist report")
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
            raise SystemExit(f"Platform handoff checklist report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Platform handoff checklist report is stale. "
                "Run: python3 scripts/verify_platform_handoff_checklist.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_handoff_checklist failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
