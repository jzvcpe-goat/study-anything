#!/usr/bin/env python3
"""Verify deployment hardening evidence for external operator adoption."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "deployment-hardening-verification-v1"
RELEASE_VERSION = "v0.3.23-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-deployment-hardening.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"

PLATFORM_IDS = ("codex", "kimi", "workbuddy")
REQUIRED_PACK_COMMAND = "verify_deployment_hardening.py --check"
REQUIRED_EVIDENCE = "deployment_hardening.schema_version == deployment-hardening-verification-v1"
REQUIRED_FILES = [
    "README.md",
    "docs/adoption.md",
    "docs/self-hosting.md",
    "docs/github-launch.md",
    "docs/platform-agent-integrations.md",
    "docs/use-with-kimi.md",
    "scripts/launch_self_host.sh",
    "scripts/doctor.sh",
    "scripts/diagnose_adoption.py",
    "scripts/verify_published_image_launch.py",
    "scripts/verify_clean_clone_adoption.py",
    "scripts/setup_env.py",
    "scripts/check_env.py",
    "infra/compose/docker-compose.yml",
    "infra/compose/docker-compose.images.yml",
    "platform/ecosystem-submission.json",
    "platform/generated/study-anything-platform-adoption-pack.json",
    "platform/generated/study-anything-platform-bundle.json",
]
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "learner@example.com",
    "Private answer:",
    "raw source text returned",
    "Private platform browser/video context",
]


class DeploymentHardeningError(RuntimeError):
    """Readable deployment-hardening verification failure."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DeploymentHardeningError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DeploymentHardeningError(f"JSON object expected: {path}")
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise DeploymentHardeningError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise DeploymentHardeningError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise DeploymentHardeningError(
                    f"Adoption pack archive should have one root, got {sorted(roots)}"
                )
            archive.extractall(tmp_root)
        return tmp_root / next(iter(roots))
    return ROOT


def safe_relative(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise DeploymentHardeningError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise DeploymentHardeningError(f"Required deployment asset is missing: {relative_path}")
    return target


def assert_contains(root: Path, relative_path: str, *needles: str) -> str:
    target = require_file(root, relative_path)
    text = target.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise DeploymentHardeningError(f"{relative_path} is missing required text: {missing}")
    return text


def assert_no_sensitive_text(report_text: str) -> None:
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(report_text):
            raise DeploymentHardeningError("Deployment report contains secret-like text.")
    for literal in FORBIDDEN_LITERALS:
        if literal in report_text:
            raise DeploymentHardeningError(f"Deployment report contains forbidden literal: {literal}")


def verify_required_files(root: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for relative_path in REQUIRED_FILES:
        if relative_path == "platform/generated/study-anything-platform-adoption-pack.json":
            if safe_relative(root, "manifest.json").is_file():
                files.append({"path": "manifest.json", "status": "present"})
                continue
        require_file(root, relative_path)
        files.append({"path": relative_path, "status": "present"})
    return files


def verify_launch_script(root: Path) -> dict[str, Any]:
    text = assert_contains(
        root,
        "scripts/launch_self_host.sh",
        RELEASE_VERSION,
        "USE_PUBLISHED_IMAGES",
        "PULL_PUBLISHED_IMAGES",
        "STUDY_ANYTHING_API_IMAGE",
        "docker-compose.images.yml",
        "path_has_non_ascii",
        "ALLOW_NON_ASCII_DOCKER_BUILD",
        "docker info",
        "API did not become healthy",
    )
    if "up -d --build" not in text:
        raise DeploymentHardeningError("launch_self_host.sh must keep source-build path explicit.")
    return {
        "script": "scripts/launch_self_host.sh",
        "published_image_default_tag": RELEASE_VERSION,
        "supports_published_images": True,
        "supports_cached_image_skip": True,
        "guards_non_ascii_source_builds": True,
        "source_build_requires_explicit_bypass_for_non_ascii": True,
    }


def verify_doctor(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/doctor.sh",
        RELEASE_VERSION,
        "docker compose version",
        "docker daemon is running",
        "check_port",
        "AGENT_HTTP_GATEWAY_URL",
        "USE_PUBLISHED_IMAGES=true",
        "PULL_PUBLISHED_IMAGES=false",
        "Recovery commands",
    )
    return {
        "script": "scripts/doctor.sh",
        "checks": [
            "docker",
            "docker_compose",
            "docker_daemon",
            "env_file",
            "non_ascii_source_path",
            "ports",
            "api_health",
            "agent_gateway_hint",
            "plugin_install_dir",
        ],
    }


def verify_diagnostics(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/diagnose_adoption.py",
        RELEASE_VERSION,
        "adoption-diagnostic-plan-v1",
        "check_ghcr_manifest",
        "check_agent_endpoint",
        "published_image_smoke",
        "ghcr_manifest",
        "do_not_include",
    )
    return {
        "script": "scripts/diagnose_adoption.py",
        "schema": "adoption-diagnostic-plan-v1",
        "covers": [
            "env_file",
            "localhost_api",
            "docker_daemon",
            "ghcr_manifest",
            "agent_endpoint",
            "provider_capabilities",
        ],
    }


def verify_published_image_smoke(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/verify_published_image_launch.py",
        RELEASE_VERSION,
        "blocked_by_local_ghcr_pull",
        "fallback_acceptance",
        "linux/amd64",
        "linux/arm64",
        "--allow-pull-timeout-report",
        "--skip-pull",
        "verify_full_api_flow.py",
    )
    return {
        "script": "scripts/verify_published_image_launch.py",
        "schema_when_pull_blocks": "blocked_by_local_ghcr_pull",
        "required_platforms": ["linux/amd64", "linux/arm64"],
        "fallback_is_acceptance_when_ci_manifest_and_release_check_pass": True,
    }


def verify_clean_clone(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/verify_clean_clone_adoption.py",
        "run_skill_mode_demo",
        "gateway_dry_run",
        "teaching_layers",
        "agent_audit_eval",
        "promptfoo",
    )
    return {
        "script": "scripts/verify_clean_clone_adoption.py",
        "default_runtime": "skill-mode",
        "checks": [
            "clean_clone",
            "env_generation",
            "skill_mode_demo",
            "gateway_dry_run",
            "teaching_layers",
            "agent_audit_eval",
        ],
    }


def verify_compose(root: Path) -> dict[str, Any]:
    base = assert_contains(root, "infra/compose/docker-compose.yml", "api:", "app-postgres:")
    images = assert_contains(
        root,
        "infra/compose/docker-compose.images.yml",
        "STUDY_ANYTHING_API_IMAGE",
        "ghcr.io/jzvcpe-goat/study-anything/api",
    )
    if "build:" not in base:
        raise DeploymentHardeningError("Base compose file should retain source build config.")
    if "image:" not in images:
        raise DeploymentHardeningError("Published-image compose override must declare image.")
    return {
        "source_compose": "infra/compose/docker-compose.yml",
        "published_image_override": "infra/compose/docker-compose.images.yml",
        "source_build_and_published_image_paths_are_separate": True,
    }


def verify_docs(root: Path) -> dict[str, Any]:
    docs = {
        "README.md": [
            RELEASE_VERSION,
            "USE_PUBLISHED_IMAGES=true",
            "verify_published_image_launch.py",
            "non-ASCII",
        ],
        "docs/self-hosting.md": [
            RELEASE_VERSION,
            "Skill Mode",
            "USE_PUBLISHED_IMAGES=true",
            "PULL_PUBLISHED_IMAGES=false",
            "non-ASCII",
        ],
        "docs/adoption.md": [
            RELEASE_VERSION,
            "clean-clone",
            "published-image",
            "allow-pull-timeout-report",
        ],
        "docs/github-launch.md": [
            RELEASE_VERSION,
            "docker manifest inspect",
            "verify_published_image_launch.py",
            "allow-pull-timeout-report",
        ],
        "docs/use-with-kimi.md": [
            "study_anything_deployment_guide",
            "Skill Mode",
            "published",
        ],
        "docs/platform-agent-integrations.md": [
            "deployment guide",
            "published GHCR images",
            "diagnostics",
        ],
    }
    for path, needles in docs.items():
        assert_contains(root, path, *needles)
    return {"checked_docs": sorted(docs), "operator_docs_are_copyable": True}


def verify_platform_packs(root: Path) -> dict[str, Any]:
    platforms: dict[str, Any] = {}
    for platform_id in PLATFORM_IDS:
        path = f"platform/packs/{platform_id}/pack.json"
        pack = read_json(require_file(root, path))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        if REQUIRED_PACK_COMMAND not in commands:
            raise DeploymentHardeningError(f"{path} is missing deployment hardening command.")
        if REQUIRED_EVIDENCE not in evidence:
            raise DeploymentHardeningError(f"{path} is missing deployment hardening evidence.")
        platforms[platform_id] = {
            "command_declared": True,
            "acceptance_evidence_declared": True,
        }
    return platforms


def verify_generated_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("version") != RELEASE_VERSION:
        raise DeploymentHardeningError("Generated adoption pack version drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    required = {
        "scripts/verify_deployment_hardening.py",
        "platform/generated/study-anything-deployment-hardening.json",
        "docs/release-notes/v0.3.23-alpha.md",
    }
    missing = required - paths
    if missing:
        raise DeploymentHardeningError(f"Generated adoption pack missing deployment files: {sorted(missing)}")
    acceptance = manifest.get("acceptance") or {}
    must_verify = set(str(item) for item in acceptance.get("must_verify", []))
    if SCHEMA_VERSION not in must_verify:
        raise DeploymentHardeningError("Adoption pack must_verify missing deployment hardening schema.")
    return {
        "schema": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "deployment_assets_included": len(required),
    }


def verify_submission(root: Path) -> dict[str, Any]:
    submission = read_json(require_file(root, "platform/ecosystem-submission.json"))
    if submission.get("version") != RELEASE_VERSION:
        raise DeploymentHardeningError("Ecosystem submission version drifted.")
    shared_assets = set(str(asset) for asset in submission.get("shared_assets", []))
    required_assets = {
        "scripts/verify_deployment_hardening.py",
        "platform/generated/study-anything-deployment-hardening.json",
        "docs/self-hosting.md",
    }
    missing_assets = required_assets - shared_assets
    if missing_assets:
        raise DeploymentHardeningError(f"Ecosystem submission missing assets: {sorted(missing_assets)}")
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(command) for command in acceptance.get("minimum_commands", []))
    if REQUIRED_PACK_COMMAND not in command_text:
        raise DeploymentHardeningError("Ecosystem submission missing deployment hardening command.")
    must_prove = set(str(item) for item in acceptance.get("must_prove", []))
    if not any(SCHEMA_VERSION in item for item in must_prove):
        raise DeploymentHardeningError("Ecosystem submission must_prove missing deployment hardening.")
    return {
        "schema": submission.get("schema_version"),
        "version": submission.get("version"),
        "shared_assets_included": len(required_assets),
    }


def build_report(root: Path) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "checked_assets": verify_required_files(root),
        "deployment_modes": [
            {
                "id": "skill_mode",
                "recommended_for": "external platform agents and first-run users",
                "command": "./scripts/launch_skill_mode.sh",
                "source_build_required": False,
            },
            {
                "id": "published_image",
                "recommended_for": "Docker users who want to avoid local builds",
                "command": "USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh",
                "source_build_required": False,
            },
            {
                "id": "source_build",
                "recommended_for": "contributors changing the API image",
                "command": "./scripts/launch_self_host.sh",
                "source_build_required": True,
            },
        ],
        "launch_script": verify_launch_script(root),
        "doctor": verify_doctor(root),
        "diagnostics": verify_diagnostics(root),
        "published_image_smoke": verify_published_image_smoke(root),
        "clean_clone_adoption": verify_clean_clone(root),
        "compose": verify_compose(root),
        "operator_docs": verify_docs(root),
        "platform_packs": verify_platform_packs(root),
        "adoption_pack": verify_generated_pack(root),
        "ecosystem_submission": verify_submission(root),
        "operator_commands": {
            "prepare_env": "python3 scripts/setup_env.py",
            "doctor": "./scripts/doctor.sh",
            "skill_mode": "./scripts/launch_skill_mode.sh",
            "published_image": f"USE_PUBLISHED_IMAGES=true STUDY_ANYTHING_IMAGE_TAG={RELEASE_VERSION} ./scripts/launch_self_host.sh",
            "published_image_cached": "USE_PUBLISHED_IMAGES=true PULL_PUBLISHED_IMAGES=false ./scripts/launch_self_host.sh",
            "source_build": "./scripts/launch_self_host.sh",
            "diagnose": "python3 scripts/diagnose_adoption.py",
            "manifest": f"docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:{RELEASE_VERSION}",
            "published_image_smoke": f"python3 scripts/verify_published_image_launch.py --tag {RELEASE_VERSION} --pull-timeout-seconds 180 --allow-pull-timeout-report",
            "clean_clone": "python3 scripts/verify_clean_clone_adoption.py --repo .",
        },
        "failure_classes": [
            "docker_missing_or_daemon_unreachable",
            "docker_compose_missing",
            "port_conflict",
            "non_ascii_source_build_path",
            "ghcr_manifest_unavailable",
            "published_image_pull_timeout",
            "api_health_timeout",
            "agent_endpoint_unreachable",
            "provider_defaults_missing",
        ],
        "privacy_assertions": {
            "real_model_keys_stored_by_study_anything": False,
            "agent_endpoint_secrets_in_report": False,
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "browser_video_private_context_in_report": False,
            "report_is_redacted": True,
        },
    }
    assert_no_sensitive_text(dump_json(report))
    return report


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def check_report(path: Path, payload: dict[str, Any]) -> None:
    expected = dump_json(payload)
    if not path.exists():
        raise DeploymentHardeningError(f"Deployment hardening report is missing: {path}")
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        raise DeploymentHardeningError(
            f"Deployment hardening report is stale. Run {Path(__file__).name} --write."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--write", action="store_true", help="Write the generated report.")
    parser.add_argument("--check", action="store_true", help="Require the generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-deploy-hardening-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        report = build_report(root)

    output = Path(args.output)
    if args.write:
        write_report(output, report)
    if args.check:
        check_report(output, report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_deployment_hardening failed: {exc}", file=sys.stderr)
        sys.exit(1)
