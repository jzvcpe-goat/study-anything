#!/usr/bin/env python3
"""Verify the public platform plugin download index."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

from generate_platform_plugin_downloads import (
    MARKDOWN_PATH,
    PLATFORMS,
    REPORT_PATH,
    ROOT,
    SCHEMA_VERSION,
    build_report,
)
from verify_platform_plugin_packs import verify_platform


FORBIDDEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/private/(?:tmp|var/folders)/[^\s\"']+"),
)
FORBIDDEN_LITERALS = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


class PlatformPluginDownloadVerificationError(RuntimeError):
    """Readable platform plugin download verification failure."""


def load_json(path: Any) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PlatformPluginDownloadVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlatformPluginDownloadVerificationError(f"{path.relative_to(ROOT)} must contain a JSON object.")
    return payload


def reject_private_text(payload: Any, *, label: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PlatformPluginDownloadVerificationError(f"{label} contains private or secret-like text: {leaks}")


def verify_report() -> dict[str, Any]:
    expected = build_report()
    actual = load_json(REPORT_PATH)
    if actual != expected:
        raise PlatformPluginDownloadVerificationError(
            f"{REPORT_PATH.relative_to(ROOT)} is stale. Run python3 scripts/generate_platform_plugin_downloads.py."
        )
    if actual.get("schema_version") != SCHEMA_VERSION:
        raise PlatformPluginDownloadVerificationError("Download index schema drifted.")
    downloads = actual.get("downloads")
    if not isinstance(downloads, list) or {item.get("platform_id") for item in downloads} != set(PLATFORMS):
        raise PlatformPluginDownloadVerificationError("Download index must include Codex, Kimi, and WorkBuddy.")
    required_names = set(actual.get("required_release_asset_names") or [])
    expected_names = {
        asset["asset_name"]
        for item in downloads
        for asset in (item.get("release_assets") or {}).values()
        if isinstance(asset, dict)
    }
    if required_names != expected_names:
        raise PlatformPluginDownloadVerificationError("Download index required release assets drifted.")
    for item in downloads:
        assets = item.get("release_assets") or {}
        for asset in assets.values():
            if not isinstance(asset, dict):
                raise PlatformPluginDownloadVerificationError("Download asset records must be objects.")
            if not str(asset.get("release_download_url") or "").startswith("https://github.com/"):
                raise PlatformPluginDownloadVerificationError("Download assets must use GitHub release URLs.")
            if not re.fullmatch(r"[a-f0-9]{64}", str(asset.get("sha256") or "")):
                raise PlatformPluginDownloadVerificationError("Download asset sha256 must be a hex digest.")
    reject_private_text(actual, label=REPORT_PATH.relative_to(ROOT).as_posix())
    return actual


def verify_markdown(report: dict[str, Any]) -> None:
    markdown = MARKDOWN_PATH.read_text(encoding="utf-8")
    if SCHEMA_VERSION not in markdown:
        raise PlatformPluginDownloadVerificationError("Download Markdown missing schema version.")
    for asset_name in report.get("required_release_asset_names", []):
        if str(asset_name) not in markdown:
            raise PlatformPluginDownloadVerificationError(f"Download Markdown missing asset {asset_name}.")
    reject_private_text({"markdown": markdown}, label=MARKDOWN_PATH.relative_to(ROOT).as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Accepted for consistency")
    args = parser.parse_args()
    del args
    for platform_id in PLATFORMS:
        verify_platform(platform_id)
    report = verify_report()
    verify_markdown(report)
    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "pass",
                "platforms": list(PLATFORMS),
                "release_asset_count": len(report.get("required_release_asset_names") or []),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_plugin_downloads failed: {exc}", file=sys.stderr)
        sys.exit(1)
