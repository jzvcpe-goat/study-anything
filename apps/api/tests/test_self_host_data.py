from __future__ import annotations

import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from self_host_data import (  # noqa: E402
    SCHEMA_VERSION,
    compose_volume_name,
    file_record,
    parse_env,
    restore_env_snapshot,
    safe_backup_member_path,
    verify_manifest,
    wait_for_postgres,
    write_manifest,
)


class SelfHostDataTests(unittest.TestCase):
    def test_parse_env_ignores_comments_and_unquotes_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text("# comment\nA=one\nB='two'\nC=\"three\"\n", encoding="utf-8")
            self.assertEqual(parse_env(path), {"A": "one", "B": "two", "C": "three"})

    def test_compose_volume_name_uses_rendered_physical_name(self) -> None:
        config = {"volumes": {"study_anything_data": {"name": "compose_study_anything_data"}}}
        self.assertEqual(
            compose_volume_name(config, "study_anything_data"),
            "compose_study_anything_data",
        )
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            compose_volume_name(config, "missing")

    def test_verify_manifest_rejects_tampered_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            payload = backup_dir / "payload.txt"
            payload.write_text("original", encoding="utf-8")
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "files": [file_record(backup_dir, payload, role="test")],
            }
            write_manifest(backup_dir, manifest)
            self.assertEqual(verify_manifest(backup_dir), manifest)

            payload.write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Checksum mismatch"):
                verify_manifest(backup_dir)
            with self.assertRaisesRegex(RuntimeError, "payload.txt"):
                verify_manifest(backup_dir)

    def test_verify_manifest_rejects_unsafe_paths_and_invalid_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            payload = backup_dir / "payload.txt"
            payload.write_text("original", encoding="utf-8")
            valid = file_record(backup_dir, payload, role="test")

            cases = [
                {"path": "../escape.txt", "sha256": valid["sha256"]},
                {"path": "/tmp/escape.txt", "sha256": valid["sha256"]},
                {"path": "nested\\escape.txt", "sha256": valid["sha256"]},
                {"path": "payload.txt", "sha256": "not-a-digest"},
            ]
            for record in cases:
                write_manifest(
                    backup_dir,
                    {"schema_version": SCHEMA_VERSION, "files": [record]},
                )
                with self.assertRaises(RuntimeError):
                    verify_manifest(backup_dir)

            write_manifest(
                backup_dir,
                {"schema_version": SCHEMA_VERSION, "files": [valid, valid]},
            )
            with self.assertRaisesRegex(RuntimeError, "Duplicate backup file"):
                verify_manifest(backup_dir)

    def test_safe_backup_member_path_stays_inside_backup_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            self.assertEqual(
                safe_backup_member_path(backup_dir, "volumes/study_anything_data.tar.gz"),
                (backup_dir / "volumes" / "study_anything_data.tar.gz").resolve(),
            )
            with self.assertRaisesRegex(RuntimeError, "Unsafe backup file path"):
                safe_backup_member_path(backup_dir, "../env.snapshot")

    def test_file_record_rejects_files_outside_backup_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            outside = root / "outside.txt"
            outside.write_text("private", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "inside the backup directory"):
                file_record(backup_dir, outside, role="outside")

    def test_restore_env_snapshot_requires_explicit_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            (backup_dir / "env.snapshot").write_text("VALUE=backup\n", encoding="utf-8")
            env_file = root / ".env"
            env_file.write_text("VALUE=current\n", encoding="utf-8")

            restore_env_snapshot(backup_dir, env_file, restore_env=False)
            self.assertEqual(env_file.read_text(encoding="utf-8"), "VALUE=current\n")

            restore_env_snapshot(backup_dir, env_file, restore_env=True)
            self.assertEqual(env_file.read_text(encoding="utf-8"), "VALUE=backup\n")
            self.assertEqual(stat.S_IMODE(env_file.stat().st_mode), 0o600)

    def test_manifest_file_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            write_manifest(backup_dir, {"schema_version": SCHEMA_VERSION, "files": []})
            manifest = backup_dir / "manifest.json"
            self.assertEqual(json.loads(manifest.read_text()), {"schema_version": 1, "files": []})
            self.assertEqual(stat.S_IMODE(manifest.stat().st_mode), 0o600)

    @patch("self_host_data.run")
    def test_wait_for_postgres_does_not_recreate_running_service(self, run_mock) -> None:
        run_mock.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=b"container-id\n"),
            subprocess.CompletedProcess([], 0, stdout=b"accepting connections\n"),
        ]

        wait_for_postgres(Path(".env"), {"POSTGRES_USER": "study", "POSTGRES_DB": "study_anything"})

        commands = [call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertIn("ps", commands[0])
        self.assertNotIn("up", commands[0])
        self.assertIn("pg_isready", commands[1])


if __name__ == "__main__":
    unittest.main()
