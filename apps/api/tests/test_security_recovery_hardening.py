from __future__ import annotations

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_security_recovery_hardening",
    REPO_ROOT / "scripts" / "verify_security_recovery_hardening.py",
)
assert SPEC is not None and SPEC.loader is not None
security_recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(security_recovery)


class SecurityRecoveryHardeningReportTests(unittest.TestCase):
    def test_python_version_error_payload_is_machine_readable(self) -> None:
        payload = security_recovery.python_version_error_payload("3.9.6")

        self.assertEqual(payload["schema_version"], "security-recovery-hardening-error-v1")
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["python_version"], "3.9.6")
        self.assertIn(".venv/bin/python", " ".join(payload["next_steps"]))
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secrets_recorded"])

    def test_python_version_preflight_prints_json_before_api_imports(self) -> None:
        stderr = io.StringIO()

        with (
            patch.object(security_recovery.sys, "version_info", (3, 9, 6)),
            patch.object(security_recovery.sys, "version", "3.9.6 test"),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as raised:
                security_recovery.ensure_supported_python()

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["python_version"], "3.9.6")

    def test_failure_report_classifies_backup_manifest_failure(self) -> None:
        report = security_recovery.failure_report(
            security_recovery.SecurityRecoveryHardeningError(
                "Checksum mismatch for backup manifest payload at /Users/example/project/backups/payload.txt"
            )
        )

        self.assertEqual(report["classification"], "backup_manifest_hardening_failed")
        self.assertIn("backup manifest", " ".join(report["next_steps"]).lower())
        self.assertIn("<local-path>", json.dumps(report, ensure_ascii=False, sort_keys=True))

    def test_failure_report_classifies_sync_restore_privacy_failure(self) -> None:
        report = security_recovery.failure_report(
            security_recovery.SecurityRecoveryHardeningError(
                "Sync restore preview returned plaintext for security recovery passphrase"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "sync_restore_privacy_failed")
        self.assertIn("<private-passphrase>", serialized)
        self.assertNotIn("security recovery passphrase", serialized)
        self.assertFalse(report["privacy"]["passphrases_included"])

    def test_failure_report_redacts_private_recovery_values(self) -> None:
        report = security_recovery.failure_report(
            security_recovery.SecurityRecoveryHardeningError(
                "Sync restore preview leaked private values: "
                "security-recovery-user@example.com "
                "Private recovery source text. "
                "Private recovery answer. "
                "http://127.0.0.1:8787/private-token "
                "path=/Users/example/project token=supersecret123"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "sync_restore_privacy_failed")
        self.assertIn("<private-user>", serialized)
        self.assertIn("<private-source-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<private-agent-endpoint>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("security-recovery-user@example.com", serialized)
        self.assertNotIn("Private recovery source text", serialized)
        self.assertNotIn("Private recovery answer", serialized)
        self.assertNotIn("private-token", serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("supersecret123", serialized)


if __name__ == "__main__":
    unittest.main()
