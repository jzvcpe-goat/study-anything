#!/usr/bin/env python3
"""Verify the Web UI container can reach the API through its same-origin proxy."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


WEB_BASE = os.getenv("WEB_BASE", "http://127.0.0.1:5173").rstrip("/")
SYNC_TEST_PASSPHRASE = "web-smoke-local-passphrase"


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{WEB_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return json.loads(raw)
            return raw
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"{exc.code} {path}: {detail}") from exc


def assert_dict(value: Any, name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{name} did not return a JSON object: {value!r}")
    return value


def main() -> None:
    index = request("/")
    if "Study Anything" not in index:
        raise RuntimeError("Web index did not load Study Anything.")

    health = request("/v1/health")
    if health.get("status") != "ok":
        raise RuntimeError(f"Same-origin API proxy health is not ok: {health}")

    session = request("/v1/sessions", {"user_id": "web-smoke-user", "track": "ACADEMIC", "use_demo_agent": True})
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{session_id}/reading",
        {
            "source_type": "local_text",
            "reference": "demo://web-full-stack",
            "title": "Web Full Stack",
            "text": "The web container should proxy API calls and complete the source-bound learning loop.",
        },
    )
    running = request(f"/v1/sessions/{session_id}/run", {})
    quiz_id = running["quiz_items"][0]["item_id"]
    completed = request(
        f"/v1/sessions/{session_id}/answers",
        {"answers": {quiz_id: "The same-origin web proxy reaches the API container."}},
    )
    if completed["stage"] != "completed":
        raise RuntimeError(f"Expected completed stage, got {completed['stage']}")

    recovery = assert_dict(request("/v1/recovery/status"), "Recovery status")
    if recovery.get("schema_version") != "recovery-status-v1" or recovery.get("restore_api_enabled"):
        raise RuntimeError(f"Recovery status is not launch-safe: {recovery}")

    system = assert_dict(request("/v1/system/status"), "System status")
    if system.get("status") != "ok" or system.get("recovery", {}).get("schema_version") != "recovery-status-v1":
        raise RuntimeError(f"System status is missing launch readiness data: {system}")

    sync_status = assert_dict(request("/v1/sync/status"), "Sync status")
    if not sync_status.get("encrypted_package_supported") or sync_status.get("hosted_sync_enabled"):
        raise RuntimeError(f"Sync status violates local-first MVP boundary: {sync_status}")

    sync_export = assert_dict(
        request(
            "/v1/sync/export",
            {
                "passphrase": SYNC_TEST_PASSPHRASE,
                "include_pmf": True,
                "include_plugin_inventory": True,
            },
        ),
        "Sync export",
    )
    if sync_export.get("schema_version") != "sync-package-v1":
        raise RuntimeError(f"Unexpected sync package schema: {sync_export}")
    if not sync_export.get("privacy", {}).get("encrypted"):
        raise RuntimeError(f"Sync export must be encrypted: {sync_export}")
    sync_inspect = assert_dict(
        request(
            "/v1/sync/inspect",
            {"passphrase": SYNC_TEST_PASSPHRASE, "package": sync_export["package"]},
        ),
        "Sync inspect",
    )
    if sync_inspect.get("privacy", {}).get("plaintext_returned"):
        raise RuntimeError(f"Sync inspect must not return plaintext: {sync_inspect}")
    sync_restore_preview = assert_dict(
        request(
            "/v1/sync/restore-preview",
            {"passphrase": SYNC_TEST_PASSPHRASE, "package": sync_export["package"]},
        ),
        "Sync restore preview",
    )
    if sync_restore_preview.get("schema_version") != "sync-restore-preview-v1":
        raise RuntimeError(f"Unexpected sync restore preview schema: {sync_restore_preview}")
    if sync_restore_preview.get("restore_api_enabled") or sync_restore_preview.get("destructive_restore"):
        raise RuntimeError(f"Sync restore preview must stay non-destructive: {sync_restore_preview}")
    if sync_restore_preview.get("privacy", {}).get("plaintext_returned"):
        raise RuntimeError(f"Sync restore preview must not return plaintext: {sync_restore_preview}")
    serialized_preview = json.dumps(sync_restore_preview, ensure_ascii=False)
    if "web-smoke-user" in serialized_preview or session_id in serialized_preview:
        raise RuntimeError(f"Sync restore preview leaked private web smoke data: {sync_restore_preview}")

    plugins = request("/v1/plugins")
    if not isinstance(plugins, list) or not any(
        item.get("trust", {}).get("registry_status") == "digest_verified" for item in plugins if isinstance(item, dict)
    ):
        raise RuntimeError(f"Expected at least one registry-verified plugin: {plugins}")
    registry_review = assert_dict(request("/v1/plugins/registry-review"), "Plugin registry review")
    if registry_review.get("schema_version") != "plugin-registry-review-v1":
        raise RuntimeError(f"Plugin registry review schema mismatch: {registry_review}")
    if registry_review.get("remote_code_downloads_allowed") or registry_review.get("entrypoints_executed"):
        raise RuntimeError(f"Plugin registry review must stay metadata-only: {registry_review}")
    if registry_review.get("verified_count", 0) < 1:
        raise RuntimeError(f"Plugin registry review did not count verified plugins: {registry_review}")

    pmf = assert_dict(request("/v1/metrics/pmf"), "PMF metrics")
    if pmf.get("privacy", {}).get("raw_contact_stored") or not pmf.get("privacy", {}).get("local_only"):
        raise RuntimeError(f"PMF metrics must remain local and redacted: {pmf}")

    print(
        json.dumps(
            {
                "status": "ok",
                "web_base": WEB_BASE,
                "session_id": session_id,
                "stage": completed["stage"],
                "mastery": completed["mastery"],
                "recovery_schema": recovery["schema_version"],
                "restore_api_enabled": recovery["restore_api_enabled"],
                "sync_package_schema": sync_export["schema_version"],
                "sync_plaintext_returned": sync_inspect["privacy"]["plaintext_returned"],
                "sync_restore_preview_schema": sync_restore_preview["schema_version"],
                "plugin_registry_review_schema": registry_review["schema_version"],
                "registry_verified_plugins": sum(
                    1
                    for item in plugins
                    if isinstance(item, dict)
                    and item.get("trust", {}).get("registry_status") == "digest_verified"
                ),
                "pmf_completed_sessions": pmf["sessions"]["completed"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_full_stack_web failed: {exc}", file=sys.stderr)
        sys.exit(1)
