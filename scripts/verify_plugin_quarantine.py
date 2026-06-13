#!/usr/bin/env python3
"""Verify plugin quarantine, trust policy, and explicit install approval."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.api import main as api_main  # noqa: E402
from study_anything.core.plugin_registry import PluginRegistry  # noqa: E402
from study_anything.core.plugin_trust import compute_plugin_source_digest  # noqa: E402


SCHEMA_VERSION = "plugin-quarantine-verification-v1"


class PluginQuarantineError(RuntimeError):
    """Readable plugin quarantine verification failure."""


def write_plugin(
    root: Path,
    plugin_id: str,
    *,
    permissions: list[str] | None = None,
    value: str = "plugin",
) -> Path:
    plugin_dir = root / plugin_id
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "schemaVersion": "plugin-manifest-v1",
                "id": plugin_id,
                "name": plugin_id.replace("-", " ").title(),
                "version": "0.1.0",
                "apiVersion": "0.1",
                "entrypoint": "plugin.py",
                "hooks": ["exporter"],
                "permissions": permissions or ["read:sessions"],
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text(f"VALUE = {value!r}\n", encoding="utf-8")
    return plugin_dir


def client_for(install_dir: Path, quarantine_dir: Path) -> tuple[TestClient, ExitStack]:
    stack = ExitStack()
    stack.enter_context(patch.object(api_main, "plugins", PluginRegistry([install_dir])))
    stack.enter_context(patch.object(api_main, "plugin_install_dir", install_dir))
    stack.enter_context(patch.object(api_main, "plugin_quarantine_dir", quarantine_dir))
    return TestClient(api_main.create_app()), stack


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PluginQuarantineError(message)


def verify_api_quarantine(root: Path) -> dict[str, Any]:
    source = write_plugin(root / "source", "quarantine-plugin", permissions=["read:sessions", "network:http"])
    install_dir = root / "installed"
    quarantine_dir = root / "quarantine"
    client, stack = client_for(install_dir, quarantine_dir)
    with stack, client:
        policy = client.get("/v1/plugins/trust-policy")
        preview = client.post("/v1/plugins/preview", json={"source_path": str(source)})
        validation = client.post("/v1/plugins/validate-package", json={"source_path": str(source)})
        quarantined = client.post(
            "/v1/plugins/install",
            json={
                "source_path": str(source),
                "confirmed_permissions": ["network:http", "read:sessions"],
            },
        )
        listed_after_quarantine = client.get("/v1/plugins")

    require(policy.status_code == 200, policy.text)
    require(policy.json()["default_install_action"] == "quarantine", "Trust policy default action drifted.")
    require(preview.status_code == 200, preview.text)
    require(preview.json()["default_action"] == "quarantine", "Preview default action drifted.")
    require(validation.status_code == 200, validation.text)
    require(
        validation.json()["default_install_action"] == "quarantine",
        "Package validation default action drifted.",
    )
    require(quarantined.status_code == 200, quarantined.text)
    quarantine_body = quarantined.json()
    require(quarantine_body["schema_version"] == "plugin-install-result-v1", "Install result schema drifted.")
    require(quarantine_body["lifecycle_status"] == "quarantined", "Plugin was not quarantined by default.")
    require(quarantine_body["manual_approval_required"] is True, "Quarantine must require manual approval.")
    require(quarantine_body["entrypoints_executed"] is False, "Quarantine must not execute plugin code.")
    require((quarantine_dir / "quarantine-plugin" / "plugin.py").exists(), "Quarantine copy missing.")
    require(not (install_dir / "quarantine-plugin").exists(), "Plugin leaked into install dir during quarantine.")
    require(listed_after_quarantine.json() == [], "Quarantined plugin should not appear as installed.")

    client, stack = client_for(install_dir, quarantine_dir)
    with stack, client:
        installed = client.post(
            "/v1/plugins/install",
            json={
                "source_path": str(source),
                "confirmed_permissions": ["network:http", "read:sessions"],
                "approve_install": True,
                "approval_note": "verifier approval",
            },
        )
        listed_after_install = client.get("/v1/plugins")

    require(installed.status_code == 200, installed.text)
    install_body = installed.json()
    require(install_body["lifecycle_status"] == "installed", "Approved install did not install.")
    require(install_body["manual_approval_recorded"] is True, "Approved install did not record approval.")
    require((install_dir / "quarantine-plugin" / "plugin.py").exists(), "Installed plugin copy missing.")
    require(
        listed_after_install.json()[0]["manifest"]["plugin_id"] == "quarantine-plugin",
        "Installed plugin was not discoverable.",
    )
    return {
        "policy_schema": policy.json()["schema_version"],
        "preview_status": preview.json()["status"],
        "validation_schema": validation.json()["schema_version"],
        "quarantine_schema": quarantine_body["schema_version"],
        "quarantine_lifecycle": quarantine_body["lifecycle_status"],
        "install_lifecycle": install_body["lifecycle_status"],
        "installed_plugin_count": len(listed_after_install.json()),
    }


def verify_blocked_digest(root: Path) -> dict[str, Any]:
    source_root = root / "blocked-source"
    source = write_plugin(source_root, "blocked-plugin")
    source_digest = compute_plugin_source_digest(source)
    (source_root / "registry.json").write_text(
        json.dumps(
            {
                "schemaVersion": "plugin-registry-v1",
                "plugins": [
                    {
                        "id": "blocked-plugin",
                        "name": "Blocked Plugin",
                        "version": "0.1.0",
                        "path": "blocked-plugin",
                        "sourceDigest": "sha256:" + "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    install_dir = root / "blocked-installed"
    quarantine_dir = root / "blocked-quarantine"
    client, stack = client_for(install_dir, quarantine_dir)
    with stack, client:
        preview = client.post("/v1/plugins/preview", json={"source_path": str(source)})
        response = client.post(
            "/v1/plugins/install",
            json={
                "source_path": str(source),
                "confirmed_permissions": ["read:sessions"],
                "approve_install": True,
            },
        )
    require(preview.status_code == 200, preview.text)
    require(
        preview.json()["trust"]["install_recommendation"] == "do_not_install",
        "Digest mismatch should produce do_not_install.",
    )
    require(response.status_code == 409, response.text)
    require("trust policy blocks" in response.json()["detail"], "Blocked install returned wrong error.")
    require(not (install_dir / "blocked-plugin").exists(), "Blocked plugin copied to install dir.")
    require(not (quarantine_dir / "blocked-plugin").exists(), "Blocked plugin copied to quarantine dir.")
    return {
        "source_digest": source_digest,
        "registry_status": preview.json()["trust"]["registry_status"],
        "install_recommendation": preview.json()["trust"]["install_recommendation"],
        "blocked_status": response.status_code,
    }


def verify_cli_quarantine(root: Path) -> dict[str, Any]:
    source = write_plugin(root / "cli-source", "cli-plugin")
    install_dir = root / "cli-installed"
    quarantine_dir = root / "cli-quarantine"
    quarantined = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "install_local_plugin.py"),
            str(source),
            "--destination",
            str(install_dir),
            "--quarantine-destination",
            str(quarantine_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if quarantined.returncode != 0:
        raise PluginQuarantineError(
            f"CLI quarantine failed:\n{quarantined.stdout}\n{quarantined.stderr}"
        )
    payload = json.loads(quarantined.stdout)
    require(payload["lifecycle_status"] == "quarantined", "CLI did not quarantine by default.")
    require((quarantine_dir / "cli-plugin" / "plugin.py").exists(), "CLI quarantine copy missing.")
    require(not (install_dir / "cli-plugin").exists(), "CLI default copied into install dir.")

    installed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "install_local_plugin.py"),
            str(source),
            "--destination",
            str(install_dir),
            "--quarantine-destination",
            str(quarantine_dir),
            "--approve-install",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if installed.returncode != 0:
        raise PluginQuarantineError(
            f"CLI approved install failed:\n{installed.stdout}\n{installed.stderr}"
        )
    install_payload = json.loads(installed.stdout)
    require(install_payload["lifecycle_status"] == "installed", "CLI approved install failed.")
    require((install_dir / "cli-plugin" / "plugin.py").exists(), "CLI approved copy missing.")
    return {
        "schema_version": payload["schema_version"],
        "lifecycle_status": payload["lifecycle_status"],
        "approved_lifecycle_status": install_payload["lifecycle_status"],
        "entrypoints_executed": payload["entrypoints_executed"],
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-plugin-quarantine-") as tmpdir:
        root = Path(tmpdir)
        api = verify_api_quarantine(root)
        blocked = verify_blocked_digest(root)
        cli = verify_cli_quarantine(root)
    print(
        json.dumps(
            {
                "status": "ok",
                "schema_version": SCHEMA_VERSION,
                "api": api,
                "blocked_digest": blocked,
                "cli": cli,
                "privacy": {
                    "entrypoints_executed_during_preview": False,
                    "entrypoints_executed_during_quarantine": False,
                    "remote_code_downloads_allowed": False,
                    "raw_secrets_allowed": False,
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_plugin_quarantine failed: {exc}", file=sys.stderr)
        sys.exit(1)
