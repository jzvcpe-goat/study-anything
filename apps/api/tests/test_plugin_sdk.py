from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.plugin_registry import PluginRegistry
from study_anything.core.plugin_sdk import (
    plugin_capability_index,
    plugin_sdk_contract,
    validate_plugin_package,
)


PLUGIN_ROOT = ROOT.parents[1] / "plugins"


class PluginSdkTests(unittest.TestCase):
    def test_contract_lists_typed_hooks_and_privacy_boundary(self) -> None:
        contract = plugin_sdk_contract()
        hooks = {item["hook"]: item for item in contract["supported_hooks"]}

        self.assertEqual(contract["schema_version"], "plugin-sdk-v1")
        self.assertEqual(contract["manifest_schema_version"], "plugin-manifest-v1")
        self.assertIn("importer", hooks)
        self.assertIn("enrichment", hooks)
        self.assertIn("agent_tool", hooks)
        self.assertEqual(hooks["importer"]["output_contract"], "learning-context-package-v1")
        self.assertFalse(contract["remote_code_downloads_allowed"])
        self.assertFalse(contract["entrypoints_executed"])
        self.assertFalse(contract["privacy"]["secrets_allowed_in_registry"])

    def test_capability_index_is_metadata_only(self) -> None:
        index = plugin_capability_index(PluginRegistry([PLUGIN_ROOT]).discover())
        items = {item["plugin_id"]: item for item in index["items"]}

        self.assertEqual(index["schema_version"], "plugin-capability-index-v1")
        self.assertIn("example-enrichment-importer", items)
        self.assertIn("enrich.micro_lesson", items["example-enrichment-importer"]["capabilities"])
        self.assertIn("export.second_brain_handoff", items["example-exporter"]["capabilities"])
        self.assertGreaterEqual(index["hook_counts"]["importer"], 3)
        self.assertFalse(index["privacy"]["entrypoints_executed"])
        self.assertFalse(index["privacy"]["returns_plugin_source_code"])

    def test_validate_plugin_package_reports_contract_and_no_execution(self) -> None:
        report = validate_plugin_package(PLUGIN_ROOT / "example-exporter", PluginRegistry([PLUGIN_ROOT]))

        self.assertEqual(report["schema_version"], "plugin-package-validation-v1")
        self.assertEqual(report["status"], "valid")
        self.assertIn("export.second_brain_handoff", report["capabilities"])
        self.assertEqual(report["required_permission_confirmations"], ["read:sessions"])
        self.assertEqual(report["default_install_action"], "quarantine")
        self.assertTrue(report["quarantine_required_before_install"])
        self.assertFalse(report["execution_allowed_by_validation"])
        self.assertFalse(report["privacy"]["entrypoints_executed"])
        self.assertFalse(report["privacy"]["package_copied"])

    def test_validate_plugin_package_catches_missing_hook_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plugin_dir = root / "bad-exporter"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "plugin-manifest-v1",
                        "id": "bad-exporter",
                        "name": "Bad Exporter",
                        "version": "0.1.0",
                        "apiVersion": "0.1",
                        "entrypoint": "plugin.py",
                        "hooks": ["exporter"],
                        "permissions": [],
                    }
                ),
                encoding="utf-8",
            )
            (plugin_dir / "plugin.py").write_text("VALUE = 'bad'\n", encoding="utf-8")

            report = validate_plugin_package(plugin_dir, PluginRegistry([root]))

        self.assertEqual(report["status"], "invalid")
        self.assertIn("hook:exporter:missing_required_permissions:read:sessions", report["validation_errors"])
        self.assertFalse(report["installable_with_confirmation"])


class PluginSdkApiTests(unittest.TestCase):
    def test_sdk_capabilities_and_validate_endpoints(self) -> None:
        stack = ExitStack()
        stack.enter_context(patch.object(api_main, "plugins", PluginRegistry([PLUGIN_ROOT])))
        stack.enter_context(patch.object(api_main, "plugin_source_dirs", [PLUGIN_ROOT]))
        client = TestClient(api_main.create_app())

        with stack, client:
            sdk = client.get("/v1/plugins/sdk")
            capabilities = client.get("/v1/plugins/capabilities")
            validation = client.post(
                "/v1/plugins/validate-package",
                json={"source_path": "example-enrichment-importer"},
            )

        self.assertEqual(sdk.status_code, 200)
        self.assertEqual(sdk.json()["schema_version"], "plugin-sdk-v1")
        self.assertEqual(capabilities.status_code, 200)
        self.assertEqual(capabilities.json()["schema_version"], "plugin-capability-index-v1")
        self.assertEqual(validation.status_code, 200)
        self.assertEqual(validation.json()["status"], "valid")
        self.assertFalse(validation.json()["privacy"]["returns_agent_secrets"])


if __name__ == "__main__":
    unittest.main()
