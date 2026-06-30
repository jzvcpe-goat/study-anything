#!/usr/bin/env python3
"""Verify generated platform plugin packs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import PurePosixPath
from typing import Any

from generate_platform_plugin_packs import PLATFORMS, ROOT, SCHEMA_VERSION, SPECS


SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/[^\s'\"<>]+"),
    re.compile(r"/private/var/folders/[A-Za-z0-9._-]+/[^\s'\"<>]+"),
    re.compile(r"/private/tmp/[A-Za-z0-9._-]+/[^\s'\"<>]+"),
)
FORBIDDEN_PATH_PARTS = {".git", ".env", ".venv", "data", "__pycache__"}
REQUIRED_ARCHIVE_FILES = ("manifest.json", "PLUGIN_PACK_README.md")
REQUIRED_IMPORT_ASSETS = {
    "codex": {
        "skills/study-anything/SKILL.md",
        "platform/packs/codex/pack.json",
    },
    "kimi": {
        "platform/generated/study-anything-openai-tools.json",
        "platform/generated/study-anything-platform-openapi.json",
        "platform/packs/kimi/pack.json",
    },
    "workbuddy": {
        "scripts/workbuddy_learning_flow.py",
        "platform/schemas/workbuddy-learning-input-v1.schema.json",
        "platform/schemas/workbuddy-learning-output-v1.schema.json",
        "platform/generated/study-anything-platform-openapi.json",
        "platform/packs/workbuddy/pack.json",
    },
    "hermes": {
        "skills/study-anything/SKILL.md",
        "platform/generated/study-anything-platform-openapi.json",
        "platform/packs/hermes/pack.json",
        "docs/use-with-hermes.md",
    },
}


class PluginPackVerificationError(RuntimeError):
    """Readable plugin-pack verification failure."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json_bytes(data: bytes, name: str) -> dict[str, Any]:
    try:
        return json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise PluginPackVerificationError(f"{name} is not valid UTF-8 JSON: {exc}") from exc


def load_sidecar(platform_id: str) -> dict[str, Any]:
    path = SPECS[platform_id].sidecar_json
    if not path.exists():
        raise PluginPackVerificationError(f"Missing plugin pack sidecar: {path.relative_to(ROOT)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PluginPackVerificationError(f"Invalid sidecar JSON {path.relative_to(ROOT)}: {exc}") from exc


def assert_manifest_shape(platform_id: str, manifest: dict[str, Any], source: str) -> None:
    spec = SPECS[platform_id]
    expected = {
        "schema_version": SCHEMA_VERSION,
        "platform_id": platform_id,
        "package_type": spec.package_type,
        "name": spec.package_name,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise PluginPackVerificationError(
                f"{source} {key} drifted: expected {value!r}, got {manifest.get(key)!r}"
            )
    for key in [
        "entrypoints",
        "import_assets",
        "local_runtime",
        "verification_commands",
        "privacy_boundaries",
        "known_limitations",
        "files",
    ]:
        if key not in manifest:
            raise PluginPackVerificationError(f"{source} missing required key: {key}")


def assert_safe_archive_path(path: str) -> None:
    posix = PurePosixPath(path)
    if posix.is_absolute() or ".." in posix.parts:
        raise PluginPackVerificationError(f"Unsafe archive path: {path}")
    if any(part in FORBIDDEN_PATH_PARTS for part in posix.parts):
        raise PluginPackVerificationError(f"Forbidden archive path part in: {path}")


def assert_no_private_text(name: str, data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            raise PluginPackVerificationError(
                f"{name} contains forbidden private-looking text: {match.group(0)[:80]}"
            )


def verify_archive(platform_id: str, sidecar: dict[str, Any]) -> None:
    spec = SPECS[platform_id]
    if not spec.archive_path.exists():
        raise PluginPackVerificationError(f"Missing plugin pack archive: {spec.archive_path.relative_to(ROOT)}")
    archive_data = spec.archive_path.read_bytes()
    archive_hash = sha256_bytes(archive_data)
    expected_hash = sidecar.get("archive", {}).get("sha256")
    if archive_hash != expected_hash:
        raise PluginPackVerificationError(
            f"{spec.archive_path.relative_to(ROOT)} sha256 drifted: {archive_hash} != {expected_hash}"
        )
    if not spec.sha256_path.exists():
        raise PluginPackVerificationError(f"Missing sha256 sidecar: {spec.sha256_path.relative_to(ROOT)}")
    expected_sha_text = f"{archive_hash}  {spec.package_name}.zip\n"
    if spec.sha256_path.read_text(encoding="utf-8") != expected_sha_text:
        raise PluginPackVerificationError(f"{spec.sha256_path.relative_to(ROOT)} content drifted.")

    with zipfile.ZipFile(spec.archive_path) as archive:
        names = archive.namelist()
        if not names:
            raise PluginPackVerificationError(f"{spec.archive_path.name} is empty.")
        roots = {name.split("/", 1)[0] for name in names}
        if roots != {spec.archive_root}:
            raise PluginPackVerificationError(
                f"{spec.archive_path.name} must have exactly one root {spec.archive_root!r}; got {sorted(roots)}"
            )
        for name in names:
            assert_safe_archive_path(name)
        for required in REQUIRED_ARCHIVE_FILES:
            archive_name = f"{spec.archive_root}/{required}"
            if archive_name not in names:
                raise PluginPackVerificationError(f"{spec.archive_path.name} missing {required}")

        archive_manifest = load_json_bytes(
            archive.read(f"{spec.archive_root}/manifest.json"),
            f"{spec.archive_path.name}:manifest.json",
        )
        assert_manifest_shape(platform_id, archive_manifest, f"{spec.archive_path.name}:manifest.json")
        sidecar_without_archive = dict(sidecar)
        sidecar_without_archive.pop("archive", None)
        if archive_manifest != sidecar_without_archive:
            raise PluginPackVerificationError(f"{spec.archive_path.name} manifest does not match sidecar content.")

        file_records = archive_manifest.get("files", [])
        if not isinstance(file_records, list) or not file_records:
            raise PluginPackVerificationError(f"{spec.archive_path.name} has no file records.")
        file_paths = {str(record.get("path")) for record in file_records if isinstance(record, dict)}
        missing_assets = REQUIRED_IMPORT_ASSETS[platform_id] - file_paths
        if missing_assets:
            raise PluginPackVerificationError(f"{spec.archive_path.name} missing import assets: {sorted(missing_assets)}")
        for asset in archive_manifest.get("import_assets", []):
            if asset not in file_paths:
                raise PluginPackVerificationError(f"{spec.archive_path.name} import asset not bundled: {asset}")

        for record in file_records:
            if not isinstance(record, dict):
                raise PluginPackVerificationError(f"{spec.archive_path.name} has malformed file record.")
            archive_path = str(record.get("archive_path", ""))
            if archive_path not in names:
                raise PluginPackVerificationError(f"{spec.archive_path.name} missing file: {archive_path}")
            data = archive.read(archive_path)
            if sha256_bytes(data) != record.get("sha256"):
                raise PluginPackVerificationError(f"{archive_path} hash drifted.")
            assert_no_private_text(archive_path, data)
        assert_no_private_text(f"{spec.archive_path.name}:PLUGIN_PACK_README.md", archive.read(f"{spec.archive_root}/PLUGIN_PACK_README.md"))


def verify_platform(platform_id: str) -> None:
    sidecar = load_sidecar(platform_id)
    assert_manifest_shape(platform_id, sidecar, f"{platform_id} sidecar")
    verify_archive(platform_id, sidecar)
    print(f"ok    {SPECS[platform_id].package_name} is import-ready")


def parse_platforms(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return PLATFORMS
    unknown = sorted(set(values) - set(PLATFORMS))
    if unknown:
        raise PluginPackVerificationError(f"Unknown platforms: {unknown}")
    return tuple(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Run verification; accepted for consistency")
    parser.add_argument("--platform", action="append", choices=PLATFORMS, help="Verify only one platform pack")
    args = parser.parse_args()
    for platform_id in parse_platforms(args.platform):
        verify_platform(platform_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_plugin_packs failed: {exc}", file=sys.stderr)
        sys.exit(1)
