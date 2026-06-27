from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "verify_notebooklm_obsidian_bridge_hardening.py"

sys.path.insert(0, str(REPO / "scripts"))
SPEC = importlib.util.spec_from_file_location("verify_notebooklm_obsidian_bridge_hardening", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
bridge_hardening = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge_hardening)


class NotebookLMObsidianBridgeHardeningTests(unittest.TestCase):
    def test_python_version_error_payload_is_machine_readable(self) -> None:
        payload = bridge_hardening.python_version_error_payload("3.9.6")

        self.assertEqual(payload["schema_version"], "notebooklm-obsidian-bridge-error-v1")
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["python_version"], "3.9.6")
        self.assertIn(".venv/bin/python", " ".join(payload["next_steps"]))
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secrets_recorded"])

    def test_python_version_preflight_prints_json_before_api_imports(self) -> None:
        stderr = io.StringIO()

        with (
            patch.object(bridge_hardening.sys, "version_info", (3, 9, 6)),
            patch.object(bridge_hardening.sys, "version", "3.9.6 test"),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as raised:
                bridge_hardening.ensure_supported_python()

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["python_version"], "3.9.6")

    def test_cli_failure_formatter_is_actionable_and_redacted(self) -> None:
        message = bridge_hardening.format_cli_failure(
            RuntimeError(
                "bridge fixture failed at /private/tmp/study-anything/bridge.json "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            )
        )

        self.assertIn("verify_notebooklm_obsidian_bridge_hardening failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("verify_notebooklm_obsidian_bridge_hardening.py", message)
        self.assertIn("context-validate", message)
        self.assertIn("docs/notebooklm-bridge.md", message)
        self.assertIn("docs/second-brain-handoff.md", message)
        self.assertIn("Remove raw source text", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/tmp", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)

    def test_success_output_uses_repo_relative_fixture_path(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            payload["fixture"],
            "fixtures/notebooklm/notebooklm-style-context-package.json",
        )
        self.assertNotIn("/Users/", completed.stdout)
        self.assertNotIn("/private/tmp", completed.stdout)


if __name__ == "__main__":
    unittest.main()
