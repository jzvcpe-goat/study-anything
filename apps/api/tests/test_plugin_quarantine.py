from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "verify_plugin_quarantine.py"

sys.path.insert(0, str(REPO / "scripts"))
SPEC = importlib.util.spec_from_file_location("verify_plugin_quarantine", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
plugin_quarantine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin_quarantine)


class PluginQuarantineVerifierTests(unittest.TestCase):
    def test_python_version_error_payload_is_machine_readable(self) -> None:
        payload = plugin_quarantine.python_version_error_payload("3.9.6")

        self.assertEqual(payload["schema_version"], "plugin-quarantine-error-v1")
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["python_version"], "3.9.6")
        self.assertIn(".venv/bin/python", " ".join(payload["next_steps"]))
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secrets_recorded"])

    def test_python_version_preflight_prints_json_before_api_imports(self) -> None:
        stderr = io.StringIO()

        with (
            patch.object(plugin_quarantine.sys, "version_info", (3, 9, 6)),
            patch.object(plugin_quarantine.sys, "version", "3.9.6 test"),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as raised:
                plugin_quarantine.ensure_supported_python()

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["python_version"], "3.9.6")

    def test_cli_failure_formatter_is_actionable_and_redacted(self) -> None:
        message = plugin_quarantine.format_cli_failure(
            RuntimeError(
                "plugin install failed at /private/tmp/study-anything/plugin "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            )
        )

        self.assertIn("verify_plugin_quarantine failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("verify_plugin_quarantine.py", message)
        self.assertIn("install_local_plugin.py", message)
        self.assertIn("docs/plugin-registry.md", message)
        self.assertIn("Do not approve unknown plugins", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/tmp", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)


if __name__ == "__main__":
    unittest.main()
