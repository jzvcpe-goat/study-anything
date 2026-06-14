#!/usr/bin/env python3
"""Standalone Study Anything release bootloader.

This file is designed to be copied out of a GitHub Release asset and run from
a clean directory. It uses only the Python standard library for metadata-only
checks. Runtime checks may download the matching source archive so the normal
repo scripts can launch Skill Mode or published-image smoke tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SCHEMA_VERSION = "release-cleanroom-bootstrap-v1"
DEFAULT_REPO = "jzvcpe-goat/study-anything"
DEFAULT_TAG = "v0.3.27-alpha"
PACK_ROOT = "study-anything-platform-adoption-pack"

REQUIRED_ASSETS = {
    "study-anything-platform-adoption-pack.zip": "platform_adoption_pack",
    "study-anything-published-image-evidence.zip": "published_image_evidence",
    "study-anything-adopter-evidence-archive.zip": "adopter_evidence_archive",
    "study-anything-platform-feedback-package.zip": "platform_feedback_package",
    "study-anything-release-asset-bootstrap.zip": "release_asset_bootstrap",
    "study-anything-platform-agent-replay.zip": "platform_agent_release_replay",
}

REQUIRED_REPLAY_TOOLS = [
    "study_anything_health",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
]

PLATFORM_ENTRYPOINTS = {
    "kimi": [
        "platform/generated/study-anything-openai-tools.json",
        "platform/generated/study-anything-platform-openapi.json",
        "platform/packs/kimi/README.md",
    ],
    "codex": [
        "skills/study-anything/SKILL.md",
        "platform/packs/codex/README.md",
        "scripts/study_anything_cli.py",
    ],
    "workbuddy": [
        "platform/generated/study-anything-platform-openapi.json",
        "platform/generated/study-anything-tool-catalog.md",
        "platform/packs/workbuddy/README.md",
    ],
    "generic-openapi": [
        "platform/generated/study-anything-platform-openapi.json",
        "platform/generated/study-anything-tool-catalog.md",
    ],
}

RECOVERY_PLAN = {
    "release_asset_missing": [
        "Open the GitHub Release page and confirm all six public zip assets are attached.",
        "Retry with --tag after the assets are uploaded.",
    ],
    "release_asset_digest_mismatch": [
        "Delete the downloaded asset directory and rerun the bootloader.",
        "If the mismatch repeats, recreate the GitHub Release asset from the matching tag commit.",
    ],
    "release_asset_pack_corrupted": [
        "Re-download study-anything-platform-adoption-pack.zip.",
        "Run the metadata-only bootloader path before trying a runtime path.",
    ],
    "tool_import_invalid": [
        "Regenerate platform tools and the adoption pack before submission.",
        "Check that OpenAI tools and OpenAPI operationIds contain the required Study Anything tools.",
    ],
    "platform_entrypoint_missing": [
        "Regenerate the adoption pack and confirm the selected platform README/import files exist.",
        "Try --platform generic-openapi if a platform-specific pack is temporarily missing.",
    ],
    "source_download_failed": [
        "Retry from a network that can download GitHub source archives.",
        "Pass --source-dir with a local checkout of the matching tag if downloads are blocked.",
    ],
    "runtime_launch_failed": [
        "Run metadata-only first, then retry with --runtime skill-mode or --runtime published-image.",
        "Attach the redacted issue body from this report to a GitHub issue.",
    ],
    "api_unavailable": [
        "Confirm the Study Anything API health endpoint is reachable.",
        "For Skill Mode, retry on an unused port or use --source-dir with a clean checkout.",
    ],
    "schema_mismatch": [
        "Confirm the release tag and runtime version match.",
        "Attach the redacted report to a GitHub issue so maintainers can reproduce it.",
    ],
    "privacy_leak": [
        "Do not share the report until the leaking field is removed.",
        "File a private maintainer note instead of a public issue if secrets were present.",
    ],
    "network_unavailable": [
        "Retry from another network or CI runner that can access GitHub release assets.",
        "Use --asset-dir with a safely mirrored copy of the release assets.",
    ],
    "cleanroom_bootstrap_failed": [
        "Run with --keep and inspect the temporary output directory.",
        "Attach only the redacted Markdown report to GitHub.",
    ],
}

FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "Private platform replay source text",
    "Private platform replay learner answer",
    "AGENT_ENDPOINT=http",
    "learner_answer=",
    "raw_source_text=",
    "sk-",
]


class CleanroomBootstrapError(RuntimeError):
    """Readable bootloader failure."""


def dump_json(payload: Any, *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CleanroomBootstrapError(f"Cannot read JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise CleanroomBootstrapError(f"JSON object expected: {path.name}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_api_url(repo: str, tag: str) -> str:
    return f"https://api.github.com/repos/{repo}/releases/tags/{quote(tag, safe='')}"


def source_zip_url(repo: str, tag: str) -> str:
    return f"https://github.com/{repo}/archive/refs/tags/{quote(tag, safe='')}.zip"


def fetch_json(url: str, timeout_seconds: int) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "study-anything-cleanroom-bootstrap"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise CleanroomBootstrapError(f"Could not fetch release metadata: {exc}") from exc
    if not isinstance(payload, dict):
        raise CleanroomBootstrapError("GitHub release metadata must be a JSON object.")
    return payload


def download(url: str, target: Path, timeout_seconds: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "study-anything-cleanroom-bootstrap"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            with target.open("wb") as handle:
                shutil.copyfileobj(response, handle)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CleanroomBootstrapError(f"Could not download {target.name}: {exc}") from exc


def digest_from_asset(asset: dict[str, Any]) -> str | None:
    digest = str(asset.get("digest") or "")
    if digest.startswith("sha256:"):
        return digest.removeprefix("sha256:")
    return None


def load_release_metadata(args: argparse.Namespace) -> dict[str, Any]:
    if args.release_json:
        return read_json(Path(args.release_json))
    if args.fixture:
        fixture = read_json(Path(args.fixture))
        if fixture.get("schema_version") != "release-asset-adoption-fixture-v1":
            raise CleanroomBootstrapError("Release fixture schema drifted.")
        release = fixture.get("release") or {}
        if not isinstance(release, dict):
            raise CleanroomBootstrapError("Release fixture is missing release metadata.")
        return release
    return fetch_json(release_api_url(args.repo, args.tag), args.network_timeout_seconds)


def classification_from_fixture(args: argparse.Namespace) -> str | None:
    if not args.fixture:
        return None
    fixture = read_json(Path(args.fixture))
    classification = fixture.get("classification")
    if classification and classification != "release_asset_adoption_ready":
        return str(classification)
    return None


def asset_records(release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise CleanroomBootstrapError("Release metadata is missing assets.")
    return {
        str(item.get("name")): item
        for item in assets
        if isinstance(item, dict) and item.get("name")
    }


def materialize_assets(args: argparse.Namespace, release: dict[str, Any], asset_dir: Path) -> dict[str, Any]:
    records = asset_records(release)
    missing = sorted(name for name in REQUIRED_ASSETS if name not in records and not (asset_dir / name).is_file())
    if missing:
        raise CleanroomBootstrapError(f"Release is missing required assets: {missing}")
    results: dict[str, Any] = {}
    asset_dir.mkdir(parents=True, exist_ok=True)
    for name, asset_type in REQUIRED_ASSETS.items():
        path = asset_dir / name
        record = records.get(name) or {}
        if not path.is_file():
            url = record.get("browser_download_url")
            if not isinstance(url, str) or not url:
                raise CleanroomBootstrapError(f"Release asset {name} has no download URL.")
            download(url, path, args.network_timeout_seconds)
        actual = sha256_file(path)
        expected = digest_from_asset(record)
        if expected and expected != actual:
            raise CleanroomBootstrapError(f"Release asset digest mismatch for {name}.")
        results[name] = {
            "asset_type": asset_type,
            "bytes": path.stat().st_size,
            "sha256": actual,
            "github_digest_verified": bool(expected),
        }
    return results


def safe_extract_zip(archive_path: Path, destination: Path) -> set[str]:
    destination.mkdir(parents=True, exist_ok=True)
    roots: set[str] = set()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                member_path = Path(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise CleanroomBootstrapError(f"Unsafe path in zip: {member.filename}")
                if member.filename and "/" in member.filename:
                    roots.add(member.filename.split("/", 1)[0])
            archive.extractall(destination)
    except zipfile.BadZipFile as exc:
        raise CleanroomBootstrapError(f"Zip is corrupted: {archive_path.name}") from exc
    return roots


def extract_adoption_pack(asset_dir: Path, work_root: Path) -> Path:
    roots = safe_extract_zip(asset_dir / "study-anything-platform-adoption-pack.zip", work_root)
    if roots != {PACK_ROOT}:
        raise CleanroomBootstrapError(f"Unexpected adoption pack root: {sorted(roots)}")
    return work_root / PACK_ROOT


def require_pack_path(pack_root: Path, relative_path: str) -> Path:
    target = (pack_root / relative_path).resolve()
    try:
        target.relative_to(pack_root.resolve())
    except ValueError as exc:
        raise CleanroomBootstrapError(f"Unsafe adoption pack path: {relative_path}") from exc
    if not target.is_file():
        raise CleanroomBootstrapError(f"Adoption pack missing required file: {relative_path}")
    return target


def tool_names_from_openai_tools(path: Path) -> set[str]:
    try:
        tools = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CleanroomBootstrapError("OpenAI tool manifest is not readable JSON.") from exc
    if not isinstance(tools, list):
        raise CleanroomBootstrapError("OpenAI tool manifest must be a list.")
    names: set[str] = set()
    for item in tools:
        if not isinstance(item, dict) or item.get("type") != "function":
            raise CleanroomBootstrapError("OpenAI tool manifest contains a malformed tool.")
        function = item.get("function")
        if not isinstance(function, dict) or not isinstance(function.get("parameters"), dict):
            raise CleanroomBootstrapError("OpenAI tool manifest contains a malformed function.")
        name = str(function.get("name") or "")
        if not name.startswith("study_anything_"):
            raise CleanroomBootstrapError(f"Unexpected OpenAI tool name: {name}")
        names.add(name)
    return names


def operation_ids_from_openapi(path: Path) -> tuple[set[str], int]:
    openapi = read_json(path)
    if openapi.get("openapi") != "3.1.0":
        raise CleanroomBootstrapError("OpenAPI manifest must be version 3.1.0.")
    if (openapi.get("components") or {}).get("securitySchemes"):
        raise CleanroomBootstrapError("OpenAPI manifest must not declare API-key security schemes.")
    operations: set[str] = set()
    paths = openapi.get("paths") or {}
    if not isinstance(paths, dict):
        raise CleanroomBootstrapError("OpenAPI paths must be an object.")
    for methods in paths.values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if isinstance(operation, dict) and operation.get("operationId"):
                operations.add(str(operation["operationId"]))
    return operations, len(paths)


def validate_adoption_pack(pack_root: Path, asset_dir: Path, platform_id: str) -> dict[str, Any]:
    manifest = read_json(require_pack_path(pack_root, "manifest.json"))
    if manifest.get("schema_version") != "study-anything-platform-adoption-pack-v1":
        raise CleanroomBootstrapError("Adoption pack schema drifted.")
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if not path:
            continue
        file_path = require_pack_path(pack_root, path)
        expected = str(item.get("sha256") or "")
        if expected and expected != sha256_file(file_path):
            raise CleanroomBootstrapError(f"Adoption pack file hash drifted: {path}")

    openai_tools = tool_names_from_openai_tools(
        require_pack_path(pack_root, "platform/generated/study-anything-openai-tools.json")
    )
    openapi_operations, openapi_path_count = operation_ids_from_openapi(
        require_pack_path(pack_root, "platform/generated/study-anything-platform-openapi.json")
    )
    required_tools = {str(item) for item in manifest.get("required_tool_names", [])}
    if not required_tools:
        raise CleanroomBootstrapError("Adoption pack manifest has no required tool names.")
    missing_openai = sorted(required_tools - openai_tools)
    missing_openapi = sorted(required_tools - openapi_operations)
    if missing_openai or missing_openapi:
        raise CleanroomBootstrapError(f"Tool import invalid: openai={missing_openai} openapi={missing_openapi}")
    missing_replay = sorted(name for name in REQUIRED_REPLAY_TOOLS if name not in openapi_operations)
    if missing_replay:
        raise CleanroomBootstrapError(f"Replay tool import invalid: {missing_replay}")

    platform_status: dict[str, Any] = {}
    for platform_name, entrypoints in PLATFORM_ENTRYPOINTS.items():
        missing = [path for path in entrypoints if not (pack_root / path).is_file()]
        platform_status[platform_name] = {
            "status": "ready" if not missing else "missing_entrypoint",
            "entrypoints": entrypoints,
            "missing": missing,
        }
    if platform_status[platform_id]["missing"]:
        raise CleanroomBootstrapError(
            f"Platform entrypoint missing for {platform_id}: {platform_status[platform_id]['missing']}"
        )

    return {
        "schema_version": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "file_count": len(manifest.get("files", [])),
        "tool_count": len(required_tools),
        "archive_sha256": sha256_file(asset_dir / "study-anything-platform-adoption-pack.zip"),
        "no_frontend_required": manifest.get("no_frontend_required"),
        "real_model_keys_stored_by_study_anything": manifest.get("real_model_keys_stored_by_study_anything"),
        "tool_import": {
            "status": "ready",
            "openai_tool_count": len(openai_tools),
            "openapi_operation_count": len(openapi_operations),
            "openapi_path_count": openapi_path_count,
            "required_replay_tools": list(REQUIRED_REPLAY_TOOLS),
            "platforms": platform_status,
        },
    }


def sanitize_text(text: str) -> str:
    text = re.sub(r"/Users/[^\s\"']+", "<local-path>", text)
    text = re.sub(r"/private/var/folders/[^\s\"']+", "<temp-path>", text)
    text = re.sub(r"/var/folders/[^\s\"']+", "<temp-path>", text)
    text = re.sub(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", r"\1=<redacted>", text)
    return text[:1200]


def classify_error(message: str) -> str:
    lowered = message.lower()
    if "missing required assets" in lowered or "missing required asset" in lowered:
        return "release_asset_missing"
    if "digest mismatch" in lowered:
        return "release_asset_digest_mismatch"
    if "zip is corrupted" in lowered or "badzipfile" in lowered:
        return "release_asset_pack_corrupted"
    if "entrypoint" in lowered:
        return "platform_entrypoint_missing"
    if "tool import" in lowered or "openapi" in lowered or "openai tool" in lowered:
        return "tool_import_invalid"
    if "source" in lowered and ("download" in lowered or "archive" in lowered):
        return "source_download_failed"
    if "runtime launch" in lowered or "launch_skill_mode" in lowered:
        return "runtime_launch_failed"
    if "api unavailable" in lowered or "connection refused" in lowered or "cannot reach" in lowered:
        return "api_unavailable"
    if "schema" in lowered or "did not return" in lowered or "did not contain" in lowered:
        return "schema_mismatch"
    if "privacy" in lowered or "leaked" in lowered:
        return "privacy_leak"
    if "could not fetch" in lowered or "could not download" in lowered:
        return "network_unavailable"
    return "cleanroom_bootstrap_failed"


def privacy_assertions() -> dict[str, bool]:
    return {
        "raw_source_text_included": False,
        "learner_answers_included": False,
        "agent_prompts_included": False,
        "agent_endpoint_secrets_included": False,
        "real_model_keys_included": False,
        "support_bundle_private_payload_included": False,
        "local_absolute_paths_included": False,
        "automatic_upload": False,
    }


def environment_summary(args: argparse.Namespace, work_root: Path) -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "runtime": args.runtime,
        "platform_profile": args.platform,
        "asset_dir_mode": "provided" if args.asset_dir else "temporary",
        "source_mode": "provided" if args.source_dir else ("downloaded" if args.runtime != "metadata-only" else "not_required"),
        "work_root_kept": bool(args.keep),
        "work_root": "<kept-output-dir>" if args.keep else "<temporary>",
    }


def assert_redacted(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", serialized):
        leaks.append("secret-looking assignment")
    if leaks:
        raise CleanroomBootstrapError(f"Cleanroom bootstrap report leaked private data: {leaks}")


def issue_body(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "## Study Anything cleanroom bootstrap issue",
            "",
            f"- tag: `{report.get('tag')}`",
            f"- platform: `{report.get('platform')}`",
            f"- runtime: `{(report.get('runtime') or {}).get('requested')}`",
            f"- status: `{report.get('status')}`",
            f"- classification: `{report.get('classification')}`",
            f"- schema: `{SCHEMA_VERSION}`",
            "",
            "### Diagnostic",
            str(report.get("diagnostic") or "No diagnostic.").strip(),
            "",
            "### Privacy checklist",
            "- raw source text included: false",
            "- learner answers included: false",
            "- real model keys included: false",
            "- local absolute paths included: false",
            "",
            "### Next steps tried",
            "- [ ] metadata-only bootloader",
            "- [ ] skill-mode replay",
            "- [ ] published-image replay",
        ]
    )


def markdown_report(report: dict[str, Any]) -> str:
    recovery = report.get("recovery_plan") or {}
    recovery_lines = []
    for classification, steps in recovery.items():
        recovery_lines.append(f"- `{classification}`")
        if isinstance(steps, list):
            recovery_lines.extend(f"  - {step}" for step in steps)
    return "\n".join(
        [
            "# Study Anything Cleanroom Bootstrap Report",
            "",
            f"- Schema: `{SCHEMA_VERSION}`",
            f"- Status: `{report.get('status')}`",
            f"- Classification: `{report.get('classification')}`",
            f"- Tag: `{report.get('tag')}`",
            f"- Platform: `{report.get('platform')}`",
            f"- Runtime: `{(report.get('runtime') or {}).get('requested')}`",
            "",
            "## Release Assets",
            f"- Asset count: `{(report.get('release_assets') or {}).get('asset_count')}`",
            f"- GitHub digest verified count: `{(report.get('release_assets') or {}).get('github_digest_verified_count')}`",
            "",
            "## Recovery",
            *recovery_lines,
            "",
            "## Issue Body",
            "```markdown",
            report.get("issue_body") or "",
            "```",
            "",
        ]
    )


def write_outputs(args: argparse.Namespace, report: dict[str, Any]) -> None:
    if not args.output_dir:
        return
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "study-anything-cleanroom-bootstrap-report.json"
    md_path = output_dir / "study-anything-cleanroom-bootstrap-report.md"
    json_path.write_text(dump_json(report, pretty=True), encoding="utf-8")
    md_path.write_text(markdown_report(report), encoding="utf-8")


def run_json_command(command: list[str], cwd: Path, timeout_seconds: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CleanroomBootstrapError(f"Runtime launch command timed out: {' '.join(command)}") from exc
    if completed.returncode != 0:
        stderr = sanitize_text(completed.stderr)
        stdout = sanitize_text(completed.stdout)
        raise CleanroomBootstrapError(
            f"Runtime launch command failed: {' '.join(command)} stdout={stdout} stderr={stderr}"
        )
    candidates = [completed.stdout.strip()]
    candidates.extend(line for line in reversed(completed.stdout.splitlines()) if line.strip().startswith("{"))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise CleanroomBootstrapError(f"Runtime command did not emit JSON: {' '.join(command)}")


def download_source_tree(args: argparse.Namespace, work_root: Path) -> Path:
    if args.source_dir:
        source_dir = Path(args.source_dir).resolve()
        if not (source_dir / "scripts" / "replay_platform_agent_from_release.py").is_file():
            raise CleanroomBootstrapError("Provided source directory is missing replay script.")
        return source_dir
    source_zip = work_root / "source.zip"
    download(source_zip_url(args.repo, args.tag), source_zip, args.network_timeout_seconds)
    source_root = work_root / "source"
    roots = safe_extract_zip(source_zip, source_root)
    dirs = [source_root / root for root in sorted(roots) if (source_root / root).is_dir()]
    if len(dirs) != 1:
        raise CleanroomBootstrapError(f"Source archive root is ambiguous: {sorted(roots)}")
    if not (dirs[0] / "scripts" / "replay_platform_agent_from_release.py").is_file():
        raise CleanroomBootstrapError("Downloaded source archive is missing replay script.")
    return dirs[0]


def runtime_replay(args: argparse.Namespace, asset_dir: Path, work_root: Path) -> dict[str, Any]:
    if args.runtime == "metadata-only":
        return {"mode": "metadata-only", "status": "skipped"}
    source_dir = download_source_tree(args, work_root)
    python = args.python or sys.executable
    if args.runtime == "published-image":
        payload = run_json_command(
            [
                python,
                "scripts/verify_published_image_launch.py",
                "--tag",
                args.tag,
                "--pull-timeout-seconds",
                str(args.pull_timeout_seconds),
                "--allow-pull-timeout-report",
            ],
            cwd=source_dir,
            timeout_seconds=args.timeout_seconds,
        )
        return {"mode": "published-image", "status": payload.get("status"), "payload": compact_runtime_payload(payload)}

    replay_runtime = "skill-mode" if args.runtime == "skill-mode" else "external-api"
    command = [
        python,
        "scripts/replay_platform_agent_from_release.py",
        "--repo",
        args.repo,
        "--tag",
        args.tag,
        "--asset-dir",
        str(asset_dir),
        "--platform",
        args.platform,
        "--runtime",
        replay_runtime,
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--request-timeout-seconds",
        str(args.request_timeout_seconds),
        "--network-timeout-seconds",
        str(args.network_timeout_seconds),
        "--pull-timeout-seconds",
        str(args.pull_timeout_seconds),
    ]
    if args.fixture:
        command.extend(["--fixture", args.fixture])
    if args.release_json:
        command.extend(["--release-json", args.release_json])
    if args.api_base:
        command.extend(["--api-base", args.api_base])
    if args.skip_pull:
        command.append("--skip-pull")
    payload = run_json_command(command, cwd=source_dir, timeout_seconds=args.timeout_seconds)
    classification = payload.get("classification")
    if classification not in {"platform_agent_replay_ready", "platform_agent_replay_metadata_ready"}:
        raise CleanroomBootstrapError(f"Platform replay failed: {classification}")
    return {"mode": args.runtime, "status": payload.get("status"), "payload": compact_runtime_payload(payload)}


def compact_runtime_payload(payload: dict[str, Any]) -> dict[str, Any]:
    replay = payload.get("replay") if isinstance(payload.get("replay"), dict) else {}
    learning_loop = replay.get("learning_loop") if isinstance(replay, dict) else None
    return {
        "schema_version": payload.get("schema_version"),
        "classification": payload.get("classification"),
        "status": payload.get("status"),
        "tool_call_count": replay.get("tool_call_count") if isinstance(replay, dict) else None,
        "learning_loop": learning_loop,
        "system_version": payload.get("system_version"),
        "api_image": payload.get("api_image"),
    }


def success_report(
    *,
    args: argparse.Namespace,
    release: dict[str, Any],
    assets: dict[str, Any],
    pack: dict[str, Any],
    runtime: dict[str, Any],
    elapsed: float,
    work_root: Path,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "classification": "cleanroom_bootstrap_ready",
        "tag": args.tag,
        "repo": args.repo,
        "release_url": release.get("html_url") or f"https://github.com/{args.repo}/releases/tag/{args.tag}",
        "platform": args.platform,
        "elapsed_seconds": round(elapsed, 3),
        "runtime": {"requested": args.runtime, **runtime},
        "release_assets": {
            "asset_count": len(assets),
            "github_digest_verified_count": sum(1 for item in assets.values() if item.get("github_digest_verified")),
            "required_assets": sorted(assets),
        },
        "adoption_pack": {
            "schema_version": pack.get("schema_version"),
            "version": pack.get("version"),
            "file_count": pack.get("file_count"),
            "tool_count": pack.get("tool_count"),
            "no_frontend_required": pack.get("no_frontend_required"),
            "real_model_keys_stored_by_study_anything": pack.get("real_model_keys_stored_by_study_anything"),
        },
        "tool_import": pack.get("tool_import"),
        "environment": environment_summary(args, work_root),
        "diagnostic": "Cleanroom bootloader completed.",
        "recovery_plan": {"cleanroom_bootstrap_ready": ["No action required."]},
        "privacy": privacy_assertions(),
        "acceptance": {
            "no_existing_repo_checkout_required": not bool(args.source_dir),
            "release_assets_verified": True,
            "platform_import_verified": True,
            "runtime_verified": args.runtime != "metadata-only" and runtime.get("status") == "ok",
        },
    }
    report["issue_body"] = issue_body(report)
    assert_redacted(report)
    return report


def failure_report(args: argparse.Namespace, classification: str, diagnostic: str, work_root: Path | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "expected_failure" if args.expect_failure else "blocked",
        "classification": classification,
        "tag": args.tag,
        "repo": args.repo,
        "platform": args.platform,
        "runtime": {"requested": args.runtime, "status": "not_verified"},
        "diagnostic": sanitize_text(diagnostic),
        "environment": environment_summary(args, work_root or Path(".")),
        "recovery_plan": {classification: RECOVERY_PLAN.get(classification, RECOVERY_PLAN["cleanroom_bootstrap_failed"])},
        "privacy": privacy_assertions(),
        "acceptance": {
            "no_existing_repo_checkout_required": not bool(args.source_dir),
            "release_assets_verified": False,
            "platform_import_verified": False,
            "runtime_verified": False,
        },
    }
    report["issue_body"] = issue_body(report)
    assert_redacted(report)
    return report


def run_bootloader(args: argparse.Namespace) -> dict[str, Any]:
    fixture_classification = classification_from_fixture(args)
    if fixture_classification and args.expect_failure and not args.asset_dir:
        return failure_report(args, fixture_classification, f"Expected failure fixture: {fixture_classification}")

    started = time.monotonic()
    work_root = Path(args.output_dir).resolve() if args.output_dir and args.keep else Path(
        tempfile.mkdtemp(prefix="study-anything-cleanroom-")
    )
    asset_dir = Path(args.asset_dir).resolve() if args.asset_dir else work_root / "assets"
    try:
        release = load_release_metadata(args)
        assets = materialize_assets(args, release, asset_dir)
        pack_root = extract_adoption_pack(asset_dir, work_root)
        pack = validate_adoption_pack(pack_root, asset_dir, args.platform)
        runtime = runtime_replay(args, asset_dir, work_root)
        report = success_report(
            args=args,
            release=release,
            assets=assets,
            pack=pack,
            runtime=runtime,
            elapsed=time.monotonic() - started,
            work_root=work_root,
        )
        write_outputs(args, report)
        return report
    except Exception as exc:
        classification = classify_error(str(exc))
        report = failure_report(args, classification, str(exc), work_root)
        write_outputs(args, report)
        if args.expect_failure:
            return report
        raise CleanroomBootstrapError(dump_json(report)) from exc
    finally:
        if not args.keep and not args.asset_dir:
            shutil.rmtree(work_root, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--asset-dir")
    parser.add_argument("--release-json")
    parser.add_argument("--fixture")
    parser.add_argument("--platform", choices=sorted(PLATFORM_ENTRYPOINTS), default="kimi")
    parser.add_argument(
        "--runtime",
        choices=["metadata-only", "skill-mode", "published-image", "external-api"],
        default="metadata-only",
    )
    parser.add_argument("--api-base")
    parser.add_argument("--source-dir")
    parser.add_argument("--output-dir")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--skip-pull", action="store_true")
    parser.add_argument("--expect-failure", action="store_true")
    parser.add_argument("--python")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--request-timeout-seconds", type=int, default=10)
    parser.add_argument("--network-timeout-seconds", type=int, default=60)
    parser.add_argument("--pull-timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    try:
        report = run_bootloader(args)
        print(dump_json(report))
    except Exception as exc:
        try:
            payload = json.loads(str(exc))
        except json.JSONDecodeError:
            payload = failure_report(args, classify_error(str(exc)), str(exc))
        print(dump_json(payload))
        if not args.expect_failure:
            sys.exit(1)


if __name__ == "__main__":
    main()
