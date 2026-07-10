from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from _path import ROOT  # noqa: F401

from study_anything.core.sync_package import (
    SyncPackageError,
    build_sync_payload,
    decrypt_sync_package,
    encrypt_sync_package,
    inspect_sync_package,
    preview_sync_restore,
    sync_status,
)
from study_anything.core.workflow import Answer, Mastery, new_session, submit_answers, submit_reading


class SyncPackageTests(unittest.TestCase):
    def test_encrypted_export_round_trips_without_plaintext_envelope_leakage(self) -> None:
        state = new_session("private-sync-user@example.com")
        state = submit_reading(
            state,
            source_type="local_text",
            reference="demo://sync",
            title="Private Sync Title",
            text="Private source prose that belongs only to the learner.",
        )
        state = replace(
            submit_answers(
                state,
                [Answer(item_id="q1", text="Private learner answer.")],
            ),
            stage="completed",
            mastery=Mastery(level=0.75, bloom="apply"),
            insights=["Private synthesized insight."],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "agent_registry.json").write_text(
                json.dumps(
                    {
                        "providers": [
                            {
                                "provider_id": "agent-private",
                                "endpoint": "http://127.0.0.1:8787/private-agent",
                                "metadata": {"api_key": "agent-secret"},
                            }
                        ],
                        "defaults": {},
                    }
                ),
                encoding="utf-8",
            )
            (data_dir / "workspace_state.json").write_text(
                json.dumps({"workspaces": {"ws_private": {"name": "Private Workspace"}}}),
                encoding="utf-8",
            )
            (data_dir / "pmf_interests.json").write_text(
                json.dumps([{"intent_id": "pmf-private"}]),
                encoding="utf-8",
            )

            payload = build_sync_payload(
                sessions=[state],
                data_dir=data_dir,
                plugin_statuses=[],
            )
            export = encrypt_sync_package(
                payload,
                passphrase="correct horse battery staple",
            )

        serialized_export = json.dumps(export.public_dict(), ensure_ascii=False)
        self.assertEqual(export.payload_summary.session_count, 1)
        self.assertEqual(export.payload_summary.agent_provider_count, 1)
        self.assertEqual(export.payload_summary.workspace_count, 1)
        self.assertEqual(export.payload_summary.pmf_interest_count, 1)
        self.assertNotIn("private-sync-user@example.com", serialized_export)
        self.assertNotIn("Private source prose", serialized_export)
        self.assertNotIn("Private learner answer", serialized_export)
        self.assertNotIn("Private synthesized insight", serialized_export)
        self.assertNotIn("127.0.0.1:8787/private-agent", serialized_export)
        self.assertNotIn("agent-secret", serialized_export)

        inspected = inspect_sync_package(
            export.package,
            passphrase="correct horse battery staple",
        )
        inspected_text = json.dumps(inspected, ensure_ascii=False)
        self.assertEqual(inspected["payload_summary"]["session_count"], 1)
        self.assertFalse(inspected["privacy"]["plaintext_returned"])
        self.assertNotIn("Private source prose", inspected_text)

        decrypted = decrypt_sync_package(
            export.package,
            passphrase="correct horse battery staple",
        )
        decrypted_text = json.dumps(decrypted, ensure_ascii=False)
        self.assertIn("Private source prose", decrypted_text)
        self.assertIn("127.0.0.1:8787/private-agent", decrypted_text)

    def test_wrong_passphrase_fails_without_plaintext(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = build_sync_payload(sessions=[], data_dir=Path(tmpdir))
            export = encrypt_sync_package(payload, passphrase="correct passphrase")

        with self.assertRaises(SyncPackageError):
            decrypt_sync_package(export.package, passphrase="wrong passphrase")

    def test_rejects_sync_package_with_excessive_kdf_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = build_sync_payload(sessions=[], data_dir=Path(tmpdir))
            export = encrypt_sync_package(payload, passphrase="correct passphrase")
        package = dict(export.package)
        package["kdf"] = dict(package["kdf"], iterations=2_000_001)

        with self.assertRaisesRegex(SyncPackageError, "iterations are invalid"):
            decrypt_sync_package(package, passphrase="correct passphrase")

    def test_restore_preview_is_non_destructive_and_count_only(self) -> None:
        current = new_session("restore-preview-current@example.com")
        current = submit_reading(
            current,
            source_type="local_text",
            reference="demo://restore-current",
            title="Private Current Title",
            text="Private current source text.",
        )
        incoming = new_session("restore-preview-new@example.com")
        incoming = submit_reading(
            incoming,
            source_type="local_text",
            reference="demo://restore-incoming",
            title="Private Incoming Title",
            text="Private incoming source text.",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            payload = build_sync_payload(sessions=[current, incoming], data_dir=Path(tmpdir))
            export = encrypt_sync_package(payload, passphrase="preview passphrase")

        preview = preview_sync_restore(
            export.package,
            passphrase="preview passphrase",
            current_sessions=[current],
        )
        preview_text = json.dumps(preview, ensure_ascii=False)

        self.assertEqual(preview["schema_version"], "sync-restore-preview-v1")
        self.assertFalse(preview["restore_api_enabled"])
        self.assertFalse(preview["destructive_restore"])
        self.assertEqual(preview["changes"]["sessions_to_add"], 1)
        self.assertEqual(preview["changes"]["sessions_to_overwrite"], 1)
        self.assertEqual(preview["changes"]["current_sessions_after_restore"], 2)
        self.assertEqual(preview["conflicts"]["session_id_conflicts"], 1)
        self.assertEqual(len(preview["conflicts"]["conflict_session_hashes"]), 1)
        self.assertFalse(preview["privacy"]["plaintext_returned"])
        self.assertFalse(preview["privacy"]["source_text_returned"])
        self.assertNotIn("restore-preview-current@example.com", preview_text)
        self.assertNotIn("Private Current Title", preview_text)
        self.assertNotIn("Private current source text", preview_text)
        self.assertNotIn("Private incoming source text", preview_text)
        self.assertNotIn(current.session_id, preview_text)
        self.assertNotIn(incoming.session_id, preview_text)

    def test_status_keeps_hosted_sync_disabled(self) -> None:
        status = sync_status()

        self.assertTrue(status["encrypted_package_supported"])
        self.assertFalse(status["hosted_sync_enabled"])
        self.assertFalse(status["raw_passphrase_stored"])
        self.assertFalse(status["commercial_boundary"]["billing_enabled"])


if __name__ == "__main__":
    unittest.main()
