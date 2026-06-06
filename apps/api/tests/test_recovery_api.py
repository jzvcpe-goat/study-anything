from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.recovery import recovery_status


class RecoveryStatusTests(unittest.TestCase):
    def test_recovery_status_is_read_only_and_does_not_leak_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "scripts").mkdir()
            (root / "scripts" / "self_host_data.py").write_text("# backup tool\n", encoding="utf-8")
            (root / ".gitignore").write_text("backups/\n.env\n", encoding="utf-8")

            status = recovery_status(root)

        serialized = json.dumps(status, sort_keys=True)
        self.assertEqual(status["schema_version"], "recovery-status-v1")
        self.assertEqual(status["status"], "ready")
        self.assertTrue(status["backup_supported"])
        self.assertTrue(status["restore_supported"])
        self.assertFalse(status["restore_api_enabled"])
        self.assertFalse(status["privacy"]["commit_safe"])
        self.assertTrue(status["safeguards"]["backups_gitignored"])
        self.assertNotIn(tmpdir, serialized)

    def test_recovery_api_uses_project_root_and_keeps_restore_off_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "scripts").mkdir()
            (root / "scripts" / "self_host_data.py").write_text("# backup tool\n", encoding="utf-8")
            (root / ".gitignore").write_text("backups/\n", encoding="utf-8")

            with patch.object(api_main, "project_root", root):
                with TestClient(api_main.create_app()) as client:
                    response = client.get("/v1/recovery/status")
                    system = client.get("/v1/system/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertFalse(response.json()["restore_api_enabled"])
        self.assertEqual(system.status_code, 200)
        self.assertEqual(system.json()["recovery"]["schema_version"], "recovery-status-v1")


if __name__ == "__main__":
    unittest.main()
