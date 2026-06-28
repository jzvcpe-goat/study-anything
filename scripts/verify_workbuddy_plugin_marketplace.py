#!/usr/bin/env python3
"""Verify the CodeBuddy/WorkBuddy marketplace plugin contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from generate_workbuddy_plugin_marketplace import (
    COMMAND_PATHS,
    MARKETPLACE_PATH,
    PLUGIN_MANIFEST_PATH,
    PLUGIN_ROOT,
    PLUGIN_SKILL_PATH,
    REPORT_PATH,
    ROOT,
    SCHEMA_VERSION,
    build_report,
    output_map,
)


FORBIDDEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/private/(?:tmp|var/folders)/[^\s\"']+"),
)
FORBIDDEN_LITERALS = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
    "Private source text:",
    "Private answer:",
)


class WorkBuddyPluginMarketplaceVerificationError(RuntimeError):
    """Readable marketplace verification failure."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise WorkBuddyPluginMarketplaceVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkBuddyPluginMarketplaceVerificationError(f"{path.relative_to(ROOT)} must be a JSON object.")
    return payload


def reject_private_text(label: str, text: str) -> None:
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in text]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(text))
    if leaks:
        raise WorkBuddyPluginMarketplaceVerificationError(f"{label} contains private or secret-like text: {leaks}")


def verify_generated_files_current() -> None:
    for path, expected in output_map().items():
        if not path.exists():
            raise WorkBuddyPluginMarketplaceVerificationError(f"Missing generated file: {path.relative_to(ROOT)}")
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            raise WorkBuddyPluginMarketplaceVerificationError(
                f"{path.relative_to(ROOT)} is stale. Run python3 scripts/generate_workbuddy_plugin_marketplace.py."
            )
        reject_private_text(path.relative_to(ROOT).as_posix(), actual)


def verify_marketplace() -> dict[str, Any]:
    marketplace = read_json(MARKETPLACE_PATH)
    if marketplace.get("name") != "study-anything":
        raise WorkBuddyPluginMarketplaceVerificationError("Marketplace name must be study-anything.")
    owner = marketplace.get("owner")
    if not isinstance(owner, dict) or not owner.get("name"):
        raise WorkBuddyPluginMarketplaceVerificationError("Marketplace must declare owner.name.")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        raise WorkBuddyPluginMarketplaceVerificationError("Marketplace must expose exactly one plugin.")
    plugin = plugins[0]
    if plugin.get("name") != "study-anything":
        raise WorkBuddyPluginMarketplaceVerificationError("Marketplace plugin name must be study-anything.")
    if plugin.get("source") != "./plugins/study-anything":
        raise WorkBuddyPluginMarketplaceVerificationError("Marketplace plugin source must be relative path ./plugins/study-anything.")
    if plugin.get("strict") is not True:
        raise WorkBuddyPluginMarketplaceVerificationError("Marketplace plugin must require strict plugin.json.")
    if plugin.get("commands") != ["commands"] or plugin.get("skills") != ["skills"]:
        raise WorkBuddyPluginMarketplaceVerificationError("Marketplace plugin must expose commands and skills directories.")
    return marketplace


def verify_plugin_manifest() -> dict[str, Any]:
    manifest = read_json(PLUGIN_MANIFEST_PATH)
    if manifest.get("name") != "study-anything":
        raise WorkBuddyPluginMarketplaceVerificationError("Plugin manifest name must be study-anything.")
    if manifest.get("commands") != ["commands"] or manifest.get("skills") != ["skills"]:
        raise WorkBuddyPluginMarketplaceVerificationError("Plugin manifest must expose commands and skills.")
    metadata = manifest.get("metadata") or {}
    contracts = metadata.get("tool_contracts") or {}
    if contracts.get("openapi") != "platform/generated/study-anything-platform-openapi.json":
        raise WorkBuddyPluginMarketplaceVerificationError("Plugin manifest must point to the OpenAPI import asset.")
    if contracts.get("local_http") != "http://127.0.0.1:8000":
        raise WorkBuddyPluginMarketplaceVerificationError("Plugin manifest must declare the local HTTP default.")
    if "planned" not in str(contracts.get("mcp") or ""):
        raise WorkBuddyPluginMarketplaceVerificationError("Plugin manifest must not falsely claim shipped MCP support.")
    return manifest


def verify_plugin_files() -> None:
    if not PLUGIN_ROOT.is_dir():
        raise WorkBuddyPluginMarketplaceVerificationError("Plugin root is missing.")
    if not PLUGIN_SKILL_PATH.is_file():
        raise WorkBuddyPluginMarketplaceVerificationError("Plugin skill entrypoint is missing.")
    skill_text = PLUGIN_SKILL_PATH.read_text(encoding="utf-8")
    for needle in (
        "platform/generated/study-anything-platform-openapi.json",
        "http://127.0.0.1:8000",
        "MCP is a planned extension",
        "It must not store real model provider keys",
    ):
        if needle not in skill_text:
            raise WorkBuddyPluginMarketplaceVerificationError(f"Plugin skill missing boundary text: {needle}")
    for command, path in COMMAND_PATHS.items():
        if not path.is_file():
            raise WorkBuddyPluginMarketplaceVerificationError(f"Missing command file: {command}")
        text = path.read_text(encoding="utf-8")
        if "Study Anything" not in text:
            raise WorkBuddyPluginMarketplaceVerificationError(f"Command {command} must mention Study Anything.")
    if "verify_workbuddy_plugin_marketplace.py --check" not in COMMAND_PATHS["diagnose"].read_text(encoding="utf-8"):
        raise WorkBuddyPluginMarketplaceVerificationError("Diagnose command must include the marketplace verifier.")


def verify_openapi_asset() -> None:
    openapi_path = ROOT / "platform" / "generated" / "study-anything-platform-openapi.json"
    payload = read_json(openapi_path)
    if payload.get("openapi") != "3.1.0":
        raise WorkBuddyPluginMarketplaceVerificationError("OpenAPI import asset must be OpenAPI 3.1.0.")
    paths = payload.get("paths")
    if not isinstance(paths, dict) or len(paths) < 20:
        raise WorkBuddyPluginMarketplaceVerificationError("OpenAPI import asset does not expose enough Study Anything tools.")
    for required_path in ("/v1/health", "/v1/sessions", "/v1/sessions/{session_id}/run"):
        if required_path not in paths:
            raise WorkBuddyPluginMarketplaceVerificationError(f"OpenAPI import asset missing {required_path}.")


def verify_docs() -> None:
    docs_path = ROOT / "docs" / "use-with-workbuddy.md"
    text = docs_path.read_text(encoding="utf-8")
    for needle in (
        "/plugin marketplace add jzvcpe-goat/study-anything",
        "/plugin install study-anything@study-anything",
        "./START_HERE.command",
        "platform/generated/study-anything-platform-openapi.json",
        "python3 scripts/verify_workbuddy_plugin_marketplace.py --check",
    ):
        if needle not in text:
            raise WorkBuddyPluginMarketplaceVerificationError(f"WorkBuddy guide missing {needle}")
    reject_private_text(docs_path.relative_to(ROOT).as_posix(), text)


def verify_report() -> None:
    report = read_json(REPORT_PATH)
    expected = build_report()
    if report != expected:
        raise WorkBuddyPluginMarketplaceVerificationError(
            f"{REPORT_PATH.relative_to(ROOT)} is stale. Run python3 scripts/generate_workbuddy_plugin_marketplace.py."
        )
    if report.get("schema_version") != SCHEMA_VERSION or report.get("status") != "pass":
        raise WorkBuddyPluginMarketplaceVerificationError("Marketplace report schema/status drifted.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Accepted for consistency")
    args = parser.parse_args()
    del args
    verify_generated_files_current()
    marketplace = verify_marketplace()
    manifest = verify_plugin_manifest()
    verify_plugin_files()
    verify_openapi_asset()
    verify_docs()
    verify_report()
    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "pass",
                "marketplace": marketplace["name"],
                "plugin": manifest["name"],
                "commands": sorted(COMMAND_PATHS),
                "openapi_tools": 34,
                "mcp_runtime_shipped": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_workbuddy_plugin_marketplace failed: {exc}", file=sys.stderr)
        sys.exit(1)
