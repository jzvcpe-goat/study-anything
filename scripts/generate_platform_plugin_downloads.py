#!/usr/bin/env python3
"""Generate the public download index for platform plugin packs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from generate_platform_plugin_packs import PLATFORMS, ROOT, SCHEMA_VERSION as PACK_SCHEMA_VERSION, SPECS


OUTPUT_DIR = ROOT / "platform" / "generated"
REPORT_PATH = OUTPUT_DIR / "study-anything-platform-plugin-downloads.json"
MARKDOWN_PATH = OUTPUT_DIR / "study-anything-platform-plugin-downloads.md"
SCHEMA_VERSION = "platform-plugin-downloads-v1"
RELEASE_VERSION = "v0.3.31-alpha"
RELEASE_REPO = "jzvcpe-goat/study-anything"
RELEASE_URL = f"https://github.com/{RELEASE_REPO}/releases/tag/{RELEASE_VERSION}"

FORBIDDEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/private/(?:tmp|var/folders)/[^\s\"']+"),
)
FORBIDDEN_LITERALS = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "Private source text:",
    "Private answer:",
    "raw_source_text=",
    "learner_answer=",
)


class PlatformPluginDownloadsError(RuntimeError):
    """Readable platform plugin download index failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PlatformPluginDownloadsError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlatformPluginDownloadsError(f"{path.relative_to(ROOT)} must contain a JSON object.")
    return payload


def release_download_url(asset_name: str) -> str:
    return f"https://github.com/{RELEASE_REPO}/releases/download/{RELEASE_VERSION}/{asset_name}"


def public_file_ref(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PlatformPluginDownloadsError(f"Download asset is missing: {path.relative_to(ROOT)}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "asset_name": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "release_download_url": release_download_url(path.name),
    }


def platform_download(platform_id: str) -> dict[str, Any]:
    spec = SPECS[platform_id]
    sidecar = read_json(spec.sidecar_json)
    if sidecar.get("schema_version") != PACK_SCHEMA_VERSION:
        raise PlatformPluginDownloadsError(f"{spec.sidecar_json.relative_to(ROOT)} schema drifted.")
    if sidecar.get("platform_id") != platform_id:
        raise PlatformPluginDownloadsError(f"{spec.sidecar_json.relative_to(ROOT)} platform_id drifted.")
    archive_hash = sha256_file(spec.archive_path)
    if sidecar.get("archive", {}).get("sha256") != archive_hash:
        raise PlatformPluginDownloadsError(f"{spec.archive_path.relative_to(ROOT)} archive hash drifted.")
    expected_sha = f"{archive_hash}  {spec.archive_path.name}\n"
    if spec.sha256_path.read_text(encoding="utf-8") != expected_sha:
        raise PlatformPluginDownloadsError(f"{spec.sha256_path.relative_to(ROOT)} checksum drifted.")
    return {
        "platform_id": platform_id,
        "package_type": spec.package_type,
        "title": spec.title,
        "summary": spec.summary,
        "release_assets": {
            "manifest": public_file_ref(spec.sidecar_json),
            "archive": public_file_ref(spec.archive_path),
            "checksum": public_file_ref(spec.sha256_path),
        },
        "entrypoints": sidecar.get("entrypoints", []),
        "import_assets": sidecar.get("import_assets", []),
        "verification_commands": sidecar.get("verification_commands", []),
        "known_limitations": sidecar.get("known_limitations", []),
    }


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PlatformPluginDownloadsError(f"Platform plugin download index leaked private data: {leaks}")


def build_report() -> dict[str, Any]:
    downloads = [platform_download(platform_id) for platform_id in PLATFORMS]
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "release": {
            "repo": RELEASE_REPO,
            "tag": RELEASE_VERSION,
            "url": RELEASE_URL,
        },
        "purpose": (
            "Make the GitHub Release page a direct download surface for Codex, "
            "Kimi-compatible, and WorkBuddy-style platform plugin packs."
        ),
        "downloads": downloads,
        "required_release_asset_names": [
            asset["asset_name"]
            for item in downloads
            for asset in item["release_assets"].values()
        ],
        "commands": {
            "generate_plugin_packs": "python3 scripts/generate_platform_plugin_packs.py --check",
            "verify_plugin_packs": "python3 scripts/verify_platform_plugin_packs.py --check",
            "generate_download_index": "python3 scripts/generate_platform_plugin_downloads.py --check",
            "verify_download_index": "python3 scripts/verify_platform_plugin_downloads.py --check",
        },
        "privacy_assertions": {
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "real_model_keys_in_report": False,
            "local_absolute_paths_in_report": False,
            "automatic_upload": False,
            "marketplace_listing_claim": False,
        },
    }
    assert_no_leaks(report)
    return report


def markdown_report(report: dict[str, Any]) -> str:
    rows: list[str] = []
    for item in report["downloads"]:
        assets = item["release_assets"]
        rows.append(
            "| `{platform}` | `{archive}` | `{manifest}` | `{checksum}` |".format(
                platform=item["platform_id"],
                archive=assets["archive"]["asset_name"],
                manifest=assets["manifest"]["asset_name"],
                checksum=assets["checksum"]["asset_name"],
            )
        )
    commands = "\n".join(f"- `{command}`" for command in report["commands"].values())
    return f"""# Study Anything Platform Plugin Downloads

Schema: `{report['schema_version']}`
Version: `{report['version']}`
Status: `{report['status']}`

Use the GitHub Release page as the public download entrypoint:

`{report['release']['url']}`

These zip archives are import helpers for user-owned platform Agents. They do
not contain real model keys and still call a local or private Study Anything
runtime. CodeBuddy/WorkBuddy marketplace installation is provided separately by
`.codebuddy-plugin/marketplace.json` and `plugins/study-anything/`.

| Platform | Archive | Manifest | Checksum |
| --- | --- | --- | --- |
{chr(10).join(rows)}

## Verification

{commands}

## Privacy

No raw source text, learner answers, Agent endpoint secrets, real model keys,
local absolute paths, or private browser/app/video context are included.
"""


def build_outputs() -> tuple[str, str]:
    report = build_report()
    return dump_json(report), markdown_report(report)


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report, markdown = build_outputs()
    REPORT_PATH.write_text(report, encoding="utf-8")
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"wrote {MARKDOWN_PATH.relative_to(ROOT)}")


def check_outputs() -> None:
    expected_report, expected_markdown = build_outputs()
    expected = {
        REPORT_PATH: expected_report,
        MARKDOWN_PATH: expected_markdown,
    }
    missing: list[str] = []
    stale: list[str] = []
    for path, content in expected.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        if path.read_text(encoding="utf-8") != content:
            stale.append(str(path.relative_to(ROOT)))
    if missing or stale:
        raise PlatformPluginDownloadsError(
            "Platform plugin download index is stale. Run "
            "`python3 scripts/generate_platform_plugin_downloads.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform plugin download index is up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated download index is stale")
    args = parser.parse_args()
    if args.check:
        check_outputs()
    else:
        write_outputs()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_platform_plugin_downloads failed: {exc}", file=sys.stderr)
        sys.exit(1)
