#!/usr/bin/env python3
"""Generate and verify the GitHub launch operator guide proof."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-github-launch-operator-guide.json"
GITHUB_GUIDE = ROOT / "docs" / "github-launch.md"
RELEASE_CHECKLIST = ROOT / "docs" / "release-checklist.md"
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"
ECOSYSTEM_SUBMISSION = ROOT / "platform" / "ecosystem-submission.json"
ADOPTION_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.json"
LAUNCH_LEDGER = ROOT / "platform" / "generated" / "study-anything-launch-acceptance-ledger.json"
VERSION = "v0.3.31-alpha"
SCHEMA_VERSION = "github-launch-operator-guide-v1"
EVIDENCE = "github_launch_operator_guide.schema_version == github-launch-operator-guide-v1"
MINIMUM_COMMAND = "python3 scripts/verify_github_launch_operator_guide.py --check"

RELEASE_ASSETS = (
    "study-anything-platform-adoption-pack.zip",
    "study-anything-platform-feedback-package.zip",
    "study-anything-published-image-evidence.zip",
    "study-anything-release-asset-bootstrap.zip",
    "study-anything-platform-agent-replay.zip",
    "study-anything-adopter-evidence-archive.zip",
    "study-anything-codex-plugin-pack.json",
    "study-anything-codex-plugin-pack.zip",
    "study-anything-codex-plugin-pack.sha256",
    "study-anything-kimi-plugin-pack.json",
    "study-anything-kimi-plugin-pack.zip",
    "study-anything-kimi-plugin-pack.sha256",
    "study-anything-workbuddy-plugin-pack.json",
    "study-anything-workbuddy-plugin-pack.zip",
    "study-anything-workbuddy-plugin-pack.sha256",
)
REQUIRED_GUIDE_MARKERS = (
    "GitHub Release Guide",
    "Before Publishing A Release",
    "Machine-Readable Launch Acceptance",
    "Tag And Push",
    "GitHub Settings",
    "Release Notes",
    "What Is Intentionally Not Hosted Yet",
    "./scripts/release_check.sh",
    "python3 scripts/verify_launch_acceptance_ledger.py --check",
    MINIMUM_COMMAND,
    "platform/generated/study-anything-launch-acceptance-ledger.json",
    "platform/generated/study-anything-github-launch-operator-guide.json",
    "launch-acceptance-ledger-v1",
    SCHEMA_VERSION,
    "python3 scripts/verify_ecosystem_submission_pack.py",
    "python3 scripts/verify_platform_ecosystem_packs.py",
    "python3 scripts/generate_platform_adoption_pack.py --check",
    "python3 scripts/generate_platform_plugin_downloads.py --check",
    "python3 scripts/verify_platform_plugin_downloads.py --check",
    "python3 scripts/verify_external_adoption.py",
    "platform/generated/study-anything-platform-adoption-pack.zip",
    "platform/generated/study-anything-platform-plugin-downloads.json",
    "No managed cloud",
    "No billing",
    "No hosted Sync/Publish/Teams",
    "No marketplace payments",
    "Users bring their own agent",
)
REQUIRED_CHECKLIST_MARKERS = (
    "python3 scripts/verify_launch_acceptance_ledger.py --check",
    MINIMUM_COMMAND,
    SCHEMA_VERSION,
    "platform/generated/study-anything-github-launch-operator-guide.json",
    "study-anything-platform-adoption-pack.zip",
    "study-anything-platform-agent-replay.zip",
    "study-anything-codex-plugin-pack.zip",
    "study-anything-kimi-plugin-pack.zip",
    "study-anything-workbuddy-plugin-pack.zip",
)
PRIVATE_NEEDLES = (
    "sk-proj-",
    "secret_access_key",
    "bearer ",
    "raw private source text",
    "learner answer:",
    "http://127.0.0.1:8787/",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private source text:",
    "Private answer:",
)


class GitHubLaunchOperatorGuideError(RuntimeError):
    """Readable GitHub launch operator guide verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GitHubLaunchOperatorGuideError(f"Cannot read {relative_path(path)}: {exc}") from exc


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GitHubLaunchOperatorGuideError(f"Cannot read {relative_path(path)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GitHubLaunchOperatorGuideError(f"{relative_path(path)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GitHubLaunchOperatorGuideError(f"{relative_path(path)} must contain a JSON object.")
    return payload


def reject_private_text(payload: Any, *, label: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = serialized.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    if leaked:
        raise GitHubLaunchOperatorGuideError(f"{label} contains private or secret-like text: {leaked}")


def require_markers(path: Path, markers: tuple[str, ...]) -> dict[str, Any]:
    text = read_text(path)
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise GitHubLaunchOperatorGuideError(f"{relative_path(path)} is missing required launch text: {missing}")
    for asset in RELEASE_ASSETS:
        if asset not in text:
            raise GitHubLaunchOperatorGuideError(f"{relative_path(path)} must mention release asset {asset}.")
    reject_private_text({"path": relative_path(path), "text": text}, label=relative_path(path))
    return {
        "path": relative_path(path),
        "required_marker_count": len(markers),
        "release_asset_count": len(RELEASE_ASSETS),
        "status": "pass",
    }


def verify_release_check_registered() -> dict[str, Any]:
    text = read_text(RELEASE_CHECK)
    for command in (
        "scripts/verify_launch_acceptance_ledger.py --check",
        "scripts/verify_github_launch_operator_guide.py --check",
        "scripts/verify_release_stack_manifest_fixtures.py --check",
        "scripts/generate_platform_bundle_manifest.py --check",
        "scripts/generate_platform_adoption_pack.py --check",
        "scripts/generate_platform_plugin_downloads.py --check",
        "scripts/verify_platform_plugin_downloads.py --check",
    ):
        if command not in text:
            raise GitHubLaunchOperatorGuideError(f"release_check.sh missing {command}.")
    reject_private_text({"source": text}, label="release_check.sh")
    return {
        "path": relative_path(RELEASE_CHECK),
        "local_gate": "./scripts/release_check.sh",
        "minimum_command": MINIMUM_COMMAND,
        "status": "registered",
    }


def verify_launch_ledger() -> dict[str, Any]:
    report = load_json(LAUNCH_LEDGER)
    if report.get("schema_version") != "launch-acceptance-ledger-v1":
        raise GitHubLaunchOperatorGuideError("Launch acceptance ledger schema drifted.")
    if report.get("status") != "pass":
        raise GitHubLaunchOperatorGuideError("Launch acceptance ledger must pass.")
    assessment = report.get("launch_assessment") or {}
    expected = {
        "github_oss_launch": "ready",
        "platform_agent_distribution": "ready",
        "self_host_alpha": "ready",
        "standalone_frontend": "not_in_launch_path",
        "hosted_paid_services": "not_ready_before_pmf",
    }
    for key, value in expected.items():
        if assessment.get(key) != value:
            raise GitHubLaunchOperatorGuideError(f"Launch acceptance ledger assessment {key} drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_keys_stored_by_study_anything",
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_endpoint_secrets_in_report",
        "browser_video_private_context_in_report",
        "automatic_upload",
        "standalone_frontend_required",
    ):
        if privacy.get(key) is not False:
            raise GitHubLaunchOperatorGuideError(f"Launch ledger privacy_assertions.{key} must be false.")
    if privacy.get("report_is_redacted") is not True:
        raise GitHubLaunchOperatorGuideError("Launch ledger must be redacted.")
    reject_private_text(report, label=relative_path(LAUNCH_LEDGER))
    return {
        "path": relative_path(LAUNCH_LEDGER),
        "schema_version": report["schema_version"],
        "status": report["status"],
        "launch_assessment": expected,
    }


def verify_ecosystem_submission() -> dict[str, Any]:
    submission = load_json(ECOSYSTEM_SUBMISSION)
    acceptance = submission.get("acceptance") or {}
    commands = set(str(item) for item in acceptance.get("minimum_commands", []))
    if MINIMUM_COMMAND not in commands:
        raise GitHubLaunchOperatorGuideError("Ecosystem submission missing GitHub launch operator guide command.")
    must_prove = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    if SCHEMA_VERSION not in must_prove:
        raise GitHubLaunchOperatorGuideError("Ecosystem submission missing GitHub launch operator guide evidence.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    for asset in (
        "platform/generated/study-anything-github-launch-operator-guide.json",
        "scripts/verify_github_launch_operator_guide.py",
    ):
        if asset not in shared_assets:
            raise GitHubLaunchOperatorGuideError(f"Ecosystem submission missing shared asset {asset}.")
    platforms = submission.get("submissions") or submission.get("platforms")
    if not isinstance(platforms, list) or len(platforms) < 4:
        raise GitHubLaunchOperatorGuideError("Ecosystem submission must include platform rows.")
    for row in platforms:
        if not isinstance(row, dict):
            raise GitHubLaunchOperatorGuideError("Ecosystem platform rows must be objects.")
        platform_id = row.get("platform_id")
        import_assets = set(str(item) for item in row.get("import_assets", []))
        commands_text = "\n".join(str(item) for item in row.get("local_verification_commands", []))
        if "platform/generated/study-anything-github-launch-operator-guide.json" not in import_assets:
            raise GitHubLaunchOperatorGuideError(f"{platform_id} missing GitHub launch guide import asset.")
        if "scripts/verify_github_launch_operator_guide.py" not in import_assets:
            raise GitHubLaunchOperatorGuideError(f"{platform_id} missing GitHub launch guide verifier asset.")
        if "verify_github_launch_operator_guide.py --check" not in commands_text:
            raise GitHubLaunchOperatorGuideError(f"{platform_id} missing GitHub launch guide command.")
    reject_private_text(submission, label=relative_path(ECOSYSTEM_SUBMISSION))
    return {
        "path": relative_path(ECOSYSTEM_SUBMISSION),
        "schema_version": submission.get("schema_version"),
        "status": "ready",
        "platform_count": len(platforms),
    }


def verify_adoption_pack() -> dict[str, Any]:
    manifest = load_json(ADOPTION_PACK)
    if manifest.get("schema_version") != "study-anything-platform-adoption-pack-v1":
        raise GitHubLaunchOperatorGuideError("Adoption pack schema drifted.")
    if manifest.get("version") != VERSION:
        raise GitHubLaunchOperatorGuideError("Adoption pack version drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    for path in (
        "docs/github-launch.md",
        "docs/release-checklist.md",
        "docs/platform-plugin-downloads.md",
        "platform/generated/study-anything-github-launch-operator-guide.json",
        "platform/generated/study-anything-platform-plugin-downloads.json",
        "platform/generated/study-anything-platform-plugin-downloads.md",
        "scripts/verify_github_launch_operator_guide.py",
        "scripts/generate_platform_plugin_downloads.py",
        "scripts/verify_platform_plugin_downloads.py",
    ):
        if path not in paths:
            raise GitHubLaunchOperatorGuideError(f"Adoption pack manifest missing {path}.")
    if manifest.get("no_frontend_required") is not True:
        raise GitHubLaunchOperatorGuideError("Adoption pack must remain no-frontend required.")
    if manifest.get("real_model_keys_stored_by_study_anything") is not False:
        raise GitHubLaunchOperatorGuideError("Study Anything must not store real model keys.")
    reject_private_text(manifest, label=relative_path(ADOPTION_PACK))
    return {
        "path": relative_path(ADOPTION_PACK),
        "schema_version": manifest["schema_version"],
        "status": "ready",
        "file_count": manifest.get("file_count"),
        "no_frontend_required": True,
        "real_model_keys_stored_by_study_anything": False,
    }


def build_report() -> dict[str, Any]:
    docs = [
        require_markers(GITHUB_GUIDE, REQUIRED_GUIDE_MARKERS),
        require_markers(RELEASE_CHECKLIST, REQUIRED_CHECKLIST_MARKERS),
    ]
    release_check = verify_release_check_registered()
    launch_ledger = verify_launch_ledger()
    ecosystem_submission = verify_ecosystem_submission()
    adoption_pack = verify_adoption_pack()
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "purpose": (
            "Machine-readable proof that GitHub release operators have one local-first, "
            "platform-Agent-compatible launch path with redacted evidence and release assets."
        ),
        "guide_docs": docs,
        "release_assets": list(RELEASE_ASSETS),
        "release_sequence": [
            "Merge the release PR stack into main from oldest to newest after GitHub CI is green.",
            "Sync main and run ./scripts/release_check.sh from a clean checkout.",
            "Create and push the v0.3.31-alpha tag from the exact merge commit.",
            "Create a GitHub prerelease using docs/release-notes/v0.3.31-alpha.md.",
            "Attach release zips and checksum sidecars from platform/generated.",
            "Verify release asset adoption, cleanroom bootstrap, and platform Agent replay.",
            "Publish only redacted status/support evidence.",
        ],
        "launch_boundary": {
            "github_oss_launch": "ready",
            "platform_agent_distribution": "ready",
            "self_host_alpha": "ready",
            "standalone_frontend": "not_in_launch_path",
            "hosted_paid_services": "not_ready_before_pmf",
            "real_reasoning_runtime": "user_owned_agent",
        },
        "evidence_sources": {
            "release_check": release_check,
            "launch_ledger": launch_ledger,
            "ecosystem_submission": ecosystem_submission,
            "adoption_pack": adoption_pack,
        },
        "privacy_assertions": {
            "real_model_keys_stored_by_study_anything": False,
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "browser_video_private_context_in_report": False,
            "automatic_upload": False,
            "standalone_frontend_required": False,
            "report_is_redacted": True,
        },
        "acceptance": {
            "evidence": EVIDENCE,
            "minimum_command": MINIMUM_COMMAND,
            "blocks_release_check": True,
        },
    }
    reject_private_text(report, label="GitHub launch operator guide report")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail when the generated guide report is stale.")
    parser.add_argument("--write", action="store_true", help="Write the generated guide report.")
    args = parser.parse_args()
    if args.check and args.write:
        raise GitHubLaunchOperatorGuideError("Use only one of --check or --write.")

    report = build_report()
    rendered = dump_json(report)
    if args.write:
        REPORT.write_text(rendered, encoding="utf-8")
    elif args.check:
        try:
            existing = REPORT.read_text(encoding="utf-8")
        except OSError as exc:
            raise GitHubLaunchOperatorGuideError(f"Cannot read {relative_path(REPORT)}: {exc}") from exc
        if existing != rendered:
            raise GitHubLaunchOperatorGuideError(
                f"{relative_path(REPORT)} is stale. Run python3 scripts/verify_github_launch_operator_guide.py --write."
            )
    else:
        print(rendered, end="")
        return

    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "status": report["status"],
                "version": VERSION,
                "release_asset_count": len(report["release_assets"]),
                "github_oss_launch": report["launch_boundary"]["github_oss_launch"],
                "hosted_paid_services": report["launch_boundary"]["hosted_paid_services"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_github_launch_operator_guide failed: {exc}", file=sys.stderr)
        sys.exit(1)
