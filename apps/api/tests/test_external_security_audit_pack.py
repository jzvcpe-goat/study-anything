from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_external_security_audit_pack as generator  # noqa: E402
import verify_external_security_audit_pack as verifier  # noqa: E402


class ExternalSecurityAuditPackTests(unittest.TestCase):
    def test_pack_is_deterministic_and_audit_ready_only(self) -> None:
        first = generator.build_outputs()
        second = generator.build_outputs()

        self.assertEqual(first, second)
        manifest, _, archive, _ = first
        self.assertEqual(manifest["status"], "ready_for_independent_audit")
        self.assertFalse(manifest["independence"]["audit_completed"])
        self.assertFalse(manifest["independence"]["self_certification_allowed"])
        self.assertEqual(len(manifest["scope_area_ids"]), 7)
        self.assertEqual(manifest["archive"]["bytes"], len(archive))

    def test_archive_has_one_safe_root(self) -> None:
        with zipfile.ZipFile(generator.ARCHIVE_PATH) as archive:
            names = archive.namelist()

        self.assertTrue(names)
        self.assertTrue(
            all(name.startswith(f"{generator.ARCHIVE_ROOT}/") for name in names)
        )
        self.assertTrue(all(".." not in Path(name).parts for name in names))

    def test_self_certified_audit_status_is_rejected(self) -> None:
        manifest = generator.build_outputs()[0]
        invalid = deepcopy(manifest)
        invalid["status"] = "audit_passed"
        invalid["independence"]["audit_completed"] = True

        with self.assertRaises(verifier.ExternalAuditPackVerificationError):
            verifier.validate_manifest(invalid)

    def test_checked_in_pack_verifies_offline(self) -> None:
        report = verifier.verify()

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            report["package"]["status"],
            "ready_for_independent_audit",
        )
        self.assertFalse(report["independence"]["audit_completed"])
        self.assertFalse(report["privacy"]["external_network_calls_performed"])


if __name__ == "__main__":
    unittest.main()
