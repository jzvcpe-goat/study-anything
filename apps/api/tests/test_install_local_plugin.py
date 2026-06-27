from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_local_plugin.py"

INSTALL_SPEC = spec_from_file_location("install_local_plugin", INSTALL_SCRIPT)
assert INSTALL_SPEC is not None
install_local_plugin = module_from_spec(INSTALL_SPEC)
assert INSTALL_SPEC.loader is not None
INSTALL_SPEC.loader.exec_module(install_local_plugin)


def write_plugin(directory: Path, plugin_id: str = "local-test-plugin") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "plugin.json").write_text(
        json.dumps(
            {
                "schemaVersion": "plugin-manifest-v1",
                "id": plugin_id,
                "name": "Local Test Plugin",
                "version": "0.1.0",
                "apiVersion": "0.1",
                "entrypoint": "plugin.py",
                "hooks": ["exporter"],
                "capabilities": ["export.markdown"],
                "permissions": ["read:sessions"],
            }
        ),
        encoding="utf-8",
    )
    (directory / "plugin.py").write_text("# local test plugin\n", encoding="utf-8")
    return directory


def run_installer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALL_SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def stderr_json(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(completed.stderr)


def assert_no_local_paths(testcase: unittest.TestCase, text: str, tmpdir: str) -> None:
    testcase.assertNotIn(tmpdir, text)
    testcase.assertNotIn("/Users/", text)
    testcase.assertNotIn("/private/tmp/", text)
    testcase.assertNotIn("/private/var/folders/", text)


class InstallLocalPluginCliTests(unittest.TestCase):
    def test_api_runtime_import_is_deferred_until_after_cli_preflight(self) -> None:
        script = INSTALL_SCRIPT.read_text(encoding="utf-8")

        self.assertGreater(
            script.index("from study_anything.core.plugin_registry import PluginRegistry"),
            script.index("_ensure_supported_python()"),
        )

    def test_python_version_preflight_is_actionable(self) -> None:
        with (
            patch.object(install_local_plugin.sys, "version_info", (3, 10, 9)),
            patch.object(install_local_plugin.sys, "version", "3.10.9 test"),
        ):
            with self.assertRaises(install_local_plugin.PluginInstallCliError) as raised:
                install_local_plugin._ensure_supported_python()

        self.assertEqual(raised.exception.code, "python_version_unsupported")
        self.assertIn("Python 3.11", raised.exception.message)
        self.assertIn(".venv/bin/python", " ".join(raised.exception.next_steps))
        self.assertEqual(raised.exception.details["python_version"], "3.10.9")

    def test_missing_source_reports_actionable_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "does-not-exist"
            completed = run_installer(str(missing))

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        payload = stderr_json(completed)
        self.assertEqual(payload["schema_version"], "plugin-install-error-v1")
        self.assertEqual(payload["error_code"], "source_missing")
        self.assertEqual(payload["classification"], "source_missing")
        self.assertFalse(payload["entrypoints_executed"])
        self.assertIn("plugins/example-exporter", " ".join(payload["next_steps"]))
        self.assertTrue(payload["privacy"]["local_only"])
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secrets_recorded"])
        assert_no_local_paths(self, completed.stderr, tmpdir)
        self.assertEqual(payload["details"]["source"], "<local-plugin-source>")

    def test_manifest_missing_reports_expected_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "empty-plugin"
            source.mkdir()
            completed = run_installer(str(source))

        self.assertEqual(completed.returncode, 1)
        payload = stderr_json(completed)
        self.assertEqual(payload["error_code"], "manifest_missing")
        self.assertIn("plugin.json", payload["message"])
        self.assertTrue(str(payload["details"]["expected_manifest"]).endswith("plugin.json"))
        self.assertEqual(payload["details"]["source"], "<local-plugin-source>")
        assert_no_local_paths(self, completed.stderr, tmpdir)

    def test_invalid_manifest_reports_manifest_repair_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "broken-plugin"
            source.mkdir()
            (source / "plugin.json").write_text("{}", encoding="utf-8")
            completed = run_installer(str(source))

        self.assertEqual(completed.returncode, 1)
        payload = stderr_json(completed)
        self.assertEqual(payload["error_code"], "invalid_manifest")
        self.assertIn("Plugin manifest requires", payload["message"])
        self.assertIn("plugin.json", " ".join(payload["next_steps"]))

    def test_approve_install_requires_prior_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root / "source")
            install_dir = root / "installed"
            quarantine_dir = root / "quarantine"
            completed = run_installer(
                str(source),
                "--destination",
                str(install_dir),
                "--quarantine-destination",
                str(quarantine_dir),
                "--approve-install",
            )

        self.assertEqual(completed.returncode, 1)
        payload = stderr_json(completed)
        self.assertEqual(payload["error_code"], "quarantine_required")
        self.assertIn("Run without --approve-install", " ".join(payload["next_steps"]))
        self.assertEqual(payload["details"]["plugin_id"], "local-test-plugin")
        self.assertEqual(payload["details"]["quarantine_source"], "<plugin-quarantine-dir>/local-test-plugin")
        assert_no_local_paths(self, completed.stderr, tmpdir)

    def test_already_installed_reports_replace_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root / "source")
            install_dir = root / "installed"
            quarantine_dir = root / "quarantine"
            quarantined = run_installer(
                str(source),
                "--destination",
                str(install_dir),
                "--quarantine-destination",
                str(quarantine_dir),
            )
            installed = run_installer(
                str(source),
                "--destination",
                str(install_dir),
                "--quarantine-destination",
                str(quarantine_dir),
                "--approve-install",
            )
            second_install = run_installer(
                str(source),
                "--destination",
                str(install_dir),
                "--quarantine-destination",
                str(quarantine_dir),
                "--approve-install",
            )

        self.assertEqual(quarantined.returncode, 0)
        self.assertEqual(installed.returncode, 0)
        self.assertEqual(second_install.returncode, 1)
        payload = stderr_json(second_install)
        self.assertEqual(payload["error_code"], "plugin_already_present")
        self.assertIn("--replace", " ".join(payload["next_steps"]))
        assert_no_local_paths(self, second_install.stderr, tmpdir)

    def test_success_reports_redact_external_install_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root / "source")
            install_dir = root / "installed"
            quarantine_dir = root / "quarantine"
            completed = run_installer(
                str(source),
                "--destination",
                str(install_dir),
                "--quarantine-destination",
                str(quarantine_dir),
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "plugin-install-result-v1")
        self.assertEqual(payload["classification"], "plugin_quarantined")
        self.assertEqual(payload["destination_dir"], "<plugin-output-dir>")
        self.assertEqual(payload["install_dir"], "<plugin-install-dir>")
        self.assertEqual(payload["quarantine_dir"], "<plugin-quarantine-dir>")
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        assert_no_local_paths(self, completed.stdout, tmpdir)


if __name__ == "__main__":
    unittest.main()
