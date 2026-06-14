#!/usr/bin/env python3
"""Verify Study Anything adoption from GitHub Release assets.

This verifier is intentionally one layer above ``verify_external_adoption.py``:
it proves an outside operator can start from a public GitHub Release page,
download the published zip assets, validate their digests, and then replay the
platform adoption pack without trusting a local development worktree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "release-asset-adoption-proof-v1"
EVIDENCE_SCHEMA_VERSION = "release-asset-adoption-v1"
FIXTURE_SCHEMA_VERSION = "release-asset-adoption-fixture-v1"
ADOPTION_PACK_SCHEMA_VERSION = "study-anything-platform-adoption-pack-v1"
PUBLISHED_IMAGE_SCHEMA_VERSION = "published-image-evidence-v1"
DEFAULT_REPO = "jzvcpe-goat/study-anything"
DEFAULT_TAG = "v0.3.24-alpha"
PACK_ROOT = "study-anything-platform-adoption-pack"
REQUIRED_ASSETS = {
    "study-anything-platform-adoption-pack.zip": "platform_adoption_pack",
    "study-anything-published-image-evidence.zip": "published_image_evidence",
    "study-anything-adopter-evidence-archive.zip": "adopter_evidence_archive",
    "study-anything-platform-feedback-package.zip": "platform_feedback_package",
}
REQUIRED_PACK_PATHS = {
    "manifest.json",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-published-image-evidence.zip",
    "platform/generated/study-anything-adopter-evidence-archive.json",
    "platform/generated/study-anything-release-asset-adoption.json",
    "platform/generated/study-anything-release-asset-adoption.md",
    "platform/generated/study-anything-release-asset-adoption.zip",
    "platform/generated/study-anything-release-asset-adoption.sha256",
    "scripts/generate_release_asset_adoption.py",
    "scripts/verify_release_asset_adoption.py",
    "docs/release-asset-adoption.md",
    "fixtures/release-asset-adoption/asset-only-pass.json",
    "scripts/verify_external_adoption.py",
    "scripts/verify_published_image_evidence.py",
    "scripts/verify_published_image_launch.py",
    "docs/adoption.md",
    "docs/github-launch.md",
    "docs/ecosystem-submission.md",
    "docs/published-image-evidence.md",
    "platform/packs/kimi/README.md",
    "platform/packs/codex/README.md",
    "platform/packs/workbuddy/README.md",
}
CLASSIFICATIONS = {
    "release_asset_adoption_ready",
    "release_asset_missing",
    "release_asset_digest_mismatch",
    "release_asset_pack_corrupted",
    "release_asset_published_evidence_missing",
    "release_asset_network_unavailable",
    "release_asset_runtime_failed",
}
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "Private platform browser/video context",
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
    "full_support_bundle_payload",
]


class ReleaseAssetAdoptionError(RuntimeError):
    """Readable release-asset adoption failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReleaseAssetAdoptionError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseAssetAdoptionError(f"JSON object expected: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_redacted(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if "/Users/" in serialized:
        leaks.append("local absolute path")
    if leaks:
        raise ReleaseAssetAdoptionError(f"Release asset adoption proof leaked private data: {leaks}")


def run(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    env: dict[str, str] | None = None,
    required: bool = True,
) -> subprocess.CompletedProcess[str]:
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
        raise ReleaseAssetAdoptionError(
            f"Command timed out after {timeout_seconds}s: {' '.join(command)}\n"
            f"stdout:\n{exc.stdout or ''}\n"
            f"stderr:\n{exc.stderr or ''}"
        ) from exc
    if required and completed.returncode != 0:
        raise ReleaseAssetAdoptionError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def json_from_stdout(label: str, stdout: str) -> dict[str, Any]:
    stripped = stdout.strip()
    candidates = [stripped]
    candidates.extend(line for line in reversed(stripped.splitlines()) if line.strip().startswith("{"))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ReleaseAssetAdoptionError(f"Could not parse {label} JSON output: {stdout}")


def release_api_url(repo: str, tag: str) -> str:
    return f"https://api.github.com/repos/{repo}/releases/tags/{tag}"


def fetch_json(url: str, timeout_seconds: int) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "study-anything-release-asset-adoption"})
    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ReleaseAssetAdoptionError(f"Could not fetch release metadata: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseAssetAdoptionError("GitHub release metadata must be a JSON object.")
    return payload


def download(url: str, target: Path, timeout_seconds: int) -> None:
    req = Request(url, headers={"User-Agent": "study-anything-release-asset-adoption"})
    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            target.write_bytes(response.read())
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ReleaseAssetAdoptionError(f"Could not download {target.name}: {exc}") from exc


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
        if fixture.get("schema_version") != FIXTURE_SCHEMA_VERSION:
            raise ReleaseAssetAdoptionError("Release asset adoption fixture schema drifted.")
        return fixture.get("release") or {}
    return fetch_json(release_api_url(args.repo, args.tag), args.network_timeout_seconds)


def asset_records(release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ReleaseAssetAdoptionError("Release metadata is missing assets.")
    records = {
        str(asset.get("name")): asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("name")
    }
    return records


def materialize_assets(args: argparse.Namespace, release: dict[str, Any], asset_dir: Path) -> dict[str, Any]:
    asset_dir.mkdir(parents=True, exist_ok=True)
    records = asset_records(release)
    missing = sorted(name for name in REQUIRED_ASSETS if name not in records and not (asset_dir / name).is_file())
    if missing:
        raise ReleaseAssetAdoptionError(f"Release is missing required assets: {missing}")
    results: dict[str, Any] = {}
    for name, asset_type in REQUIRED_ASSETS.items():
        path = asset_dir / name
        record = records.get(name) or {}
        if not path.is_file():
            url = record.get("browser_download_url")
            if not isinstance(url, str) or not url:
                raise ReleaseAssetAdoptionError(f"Release asset {name} has no download URL.")
            download(url, path, args.network_timeout_seconds)
        actual = sha256_file(path)
        expected = digest_from_asset(record)
        if expected and actual != expected:
            raise ReleaseAssetAdoptionError(f"Release asset digest mismatch for {name}.")
        results[name] = {
            "asset_type": asset_type,
            "bytes": path.stat().st_size,
            "sha256": actual,
            "github_digest_verified": bool(expected),
        }
    return results


def extract_adoption_pack(asset_dir: Path, work_root: Path) -> Path:
    pack = asset_dir / "study-anything-platform-adoption-pack.zip"
    try:
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if roots != {PACK_ROOT}:
                raise ReleaseAssetAdoptionError(f"Unexpected adoption pack root: {sorted(roots)}")
            archive.extractall(work_root)
    except zipfile.BadZipFile as exc:
        raise ReleaseAssetAdoptionError("Release adoption pack zip is corrupted.") from exc
    return work_root / PACK_ROOT


def require_pack_path(pack_root: Path, relative_path: str) -> Path:
    target = (pack_root / relative_path).resolve()
    try:
        target.relative_to(pack_root.resolve())
    except ValueError as exc:
        raise ReleaseAssetAdoptionError(f"Unsafe path in release asset pack: {relative_path}") from exc
    if not target.is_file():
        raise ReleaseAssetAdoptionError(f"Release adoption pack missing required file: {relative_path}")
    return target


def validate_pack(pack_root: Path, asset_dir: Path) -> dict[str, Any]:
    for relative_path in REQUIRED_PACK_PATHS:
        require_pack_path(pack_root, relative_path)
    manifest = read_json(require_pack_path(pack_root, "manifest.json"))
    if manifest.get("schema_version") != ADOPTION_PACK_SCHEMA_VERSION:
        raise ReleaseAssetAdoptionError("Release adoption pack schema drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    missing = sorted(path for path in REQUIRED_PACK_PATHS if path != "manifest.json" and path not in paths)
    if missing:
        raise ReleaseAssetAdoptionError(f"Release adoption pack manifest missing files: {missing}")
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            continue
        archive_path = str(item.get("archive_path"))
        if not archive_path.startswith(f"{PACK_ROOT}/"):
            raise ReleaseAssetAdoptionError(f"Unsafe archive path in adoption pack manifest: {archive_path}")
        relative_path = archive_path.split("/", 1)[1]
        file_path = require_pack_path(pack_root, relative_path)
        if item.get("sha256") != sha256_file(file_path):
            raise ReleaseAssetAdoptionError(f"Release adoption pack file hash drifted: {relative_path}")
    published = read_json(
        require_pack_path(pack_root, "platform/generated/study-anything-published-image-evidence.json")
    )
    if published.get("schema_version") != PUBLISHED_IMAGE_SCHEMA_VERSION:
        raise ReleaseAssetAdoptionError("Published image evidence is missing or wrong schema.")
    return {
        "schema_version": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "file_count": len(manifest.get("files", [])),
        "tool_count": len(manifest.get("required_tool_names", [])),
        "archive_sha256": sha256_file(asset_dir / "study-anything-platform-adoption-pack.zip"),
        "published_image_evidence_schema": published.get("schema_version"),
        "no_frontend_required": manifest.get("no_frontend_required"),
        "real_model_keys_stored_by_study_anything": manifest.get("real_model_keys_stored_by_study_anything"),
    }


def run_pack_verifiers(pack_root: Path, asset_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    python = args.python or sys.executable
    published = run(
        [
            python,
            str(pack_root / "scripts" / "verify_published_image_evidence.py"),
            "--pack-root",
            str(pack_root),
        ],
        cwd=pack_root,
        timeout_seconds=args.timeout_seconds,
    )
    result: dict[str, Any] = {"published_image_evidence": json_from_stdout("published_image_evidence", published.stdout)}
    if args.runtime == "metadata-only":
        result["runtime"] = {"mode": "metadata-only", "status": "skipped"}
        return result
    if args.runtime == "published-image":
        command = [
            python,
            str(pack_root / "scripts" / "verify_published_image_launch.py"),
            "--tag",
            args.tag,
            "--pull-timeout-seconds",
            str(args.pull_timeout_seconds),
            "--allow-pull-timeout-report",
        ]
        if args.skip_pull:
            command.append("--skip-pull")
        completed = run(command, cwd=pack_root, timeout_seconds=args.timeout_seconds)
        result["runtime"] = json_from_stdout("published_image_launch", completed.stdout)
        return result
    external = run(
        [
            python,
            str(ROOT / "scripts" / "verify_external_adoption.py"),
            "--pack",
            str(asset_dir / "study-anything-platform-adoption-pack.zip"),
            "--copy-worktree",
            "--repo",
            str(ROOT),
            "--python",
            python,
        ],
        cwd=ROOT,
        timeout_seconds=args.timeout_seconds,
    )
    external_payload = json_from_stdout("external_adoption", external.stdout)
    result["runtime"] = {
        "schema_version": external_payload.get("schema_version"),
        "status": external_payload.get("status"),
        "elapsed_seconds": external_payload.get("elapsed_seconds"),
        "within_target_minutes": external_payload.get("within_target_minutes"),
        "runtime": (external_payload.get("runtime") or {}).get("runtime"),
        "pack_version": (external_payload.get("pack") or {}).get("version"),
        "tool_count": (external_payload.get("pack") or {}).get("tool_count"),
        "privacy": external_payload.get("privacy"),
    }
    return result


def classification_from_fixture(args: argparse.Namespace) -> str | None:
    if not args.fixture:
        return None
    fixture = read_json(Path(args.fixture))
    classification = fixture.get("classification")
    if classification not in CLASSIFICATIONS:
        raise ReleaseAssetAdoptionError(f"Unknown release asset fixture classification: {classification}")
    if classification != "release_asset_adoption_ready" and args.expect_failure:
        return str(classification)
    return str(classification)


def build_proof(
    *,
    args: argparse.Namespace,
    release: dict[str, Any],
    assets: dict[str, Any],
    pack: dict[str, Any],
    verifiers: dict[str, Any],
    elapsed: float,
    asset_dir: Path,
) -> dict[str, Any]:
    release_url = release.get("html_url") or f"https://github.com/{args.repo}/releases/tag/{args.tag}"
    proof = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "classification": "release_asset_adoption_ready",
        "tag": args.tag,
        "repo": args.repo,
        "release_url": release_url,
        "elapsed_seconds": round(elapsed, 3),
        "asset_dir_mode": "provided" if args.asset_dir else "temporary",
        "asset_count": len(assets),
        "assets": assets,
        "pack": pack,
        "verifiers": verifiers,
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "support_bundle_private_payload_included": False,
            "local_absolute_paths_included": False,
            "automatic_upload": False,
        },
        "acceptance": {
            "evidence_schema": EVIDENCE_SCHEMA_VERSION,
            "fixture_schema": FIXTURE_SCHEMA_VERSION,
            "required_assets": sorted(REQUIRED_ASSETS),
            "runtime": args.runtime,
        },
    }
    if args.include_asset_dir:
        proof["debug_asset_dir"] = str(asset_dir)
    assert_redacted(proof)
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--asset-dir")
    parser.add_argument("--release-json")
    parser.add_argument("--fixture")
    parser.add_argument("--runtime", choices=["metadata-only", "published-image", "skill-mode"], default="metadata-only")
    parser.add_argument("--skip-pull", action="store_true")
    parser.add_argument("--expect-failure", action="store_true")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--include-asset-dir", action="store_true")
    parser.add_argument("--python")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--network-timeout-seconds", type=int, default=60)
    parser.add_argument("--pull-timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    fixture_classification = classification_from_fixture(args)
    if fixture_classification and args.expect_failure and fixture_classification != "release_asset_adoption_ready":
        print(
            dump_json(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "expected_failure",
                    "classification": fixture_classification,
                    "tag": args.tag,
                    "repo": args.repo,
                }
            )
        )
        return

    started = time.monotonic()
    work_root = Path(tempfile.mkdtemp(prefix="study-anything-release-asset-adoption-"))
    asset_dir = Path(args.asset_dir).resolve() if args.asset_dir else work_root / "assets"
    try:
        release = load_release_metadata(args)
        assets = materialize_assets(args, release, asset_dir)
        pack_root = extract_adoption_pack(asset_dir, work_root)
        pack = validate_pack(pack_root, asset_dir)
        verifiers = run_pack_verifiers(pack_root, asset_dir, args)
        proof = build_proof(
            args=args,
            release=release,
            assets=assets,
            pack=pack,
            verifiers=verifiers,
            elapsed=time.monotonic() - started,
            asset_dir=asset_dir,
        )
        print(dump_json(proof))
    finally:
        if not args.keep and not args.asset_dir:
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_asset_adoption failed: {exc}", file=sys.stderr)
        sys.exit(1)
