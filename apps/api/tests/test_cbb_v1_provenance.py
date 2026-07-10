from __future__ import annotations

from copy import deepcopy
import builtins
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from _path import ROOT  # noqa: F401

from study_anything.cbb.protocol.models import DeliveryScope
from study_anything.cbb.provenance.fixtures import (
    FIXTURE_NOW,
    build_provenance_cases,
    signed_package,
    unsigned_package,
)
from study_anything.cbb.provenance.signing import (
    OfflineProvenancePackageV1,
    ProvenanceDependencyError,
    ProvenanceKeyError,
    _crypto_types,
    build_offline_package,
    generate_private_key,
    load_private_key,
    sign_provenance,
    verify_offline_package,
)


REPO = Path(__file__).resolve().parents[3]


class CBBV1ProvenanceTests(unittest.TestCase):
    def test_signed_package_verifies_offline(self) -> None:
        result = verify_offline_package(signed_package(), now=FIXTURE_NOW)
        self.assertTrue(result.passed, result.reasons)
        self.assertEqual(result.approved_scope, "controlled_customer_handoff")

    def test_unsigned_expired_revoked_and_replayed_packages_fail(self) -> None:
        unsigned = verify_offline_package(unsigned_package(), now=FIXTURE_NOW)
        self.assertFalse(unsigned.passed)
        self.assertIn("locally_signed", unsigned.reasons)
        self.assertEqual(
            unsigned_package().claim_boundary.maximum_scope,
            DeliveryScope.BLOCKED,
        )

        package = signed_package()
        expired = verify_offline_package(package, now="2026-09-27T00:00:00Z")
        self.assertIn("not_expired", expired.reasons)
        revoked = verify_offline_package(
            package,
            now=FIXTURE_NOW,
            revoked_handles={package.receipt_provenance.revocation.handle},
        )
        self.assertIn("not_revoked", revoked.reasons)

        ledger: set[str] = set()
        first = verify_offline_package(
            package,
            now=FIXTURE_NOW,
            seen_nonces=ledger,
            consume_nonce=True,
        )
        second = verify_offline_package(
            package,
            now=FIXTURE_NOW,
            seen_nonces=ledger,
            consume_nonce=True,
        )
        self.assertTrue(first.passed)
        self.assertIn("replay_nonce_unused", second.reasons)

    def test_every_tamper_fixture_fails_closed(self) -> None:
        cases = build_provenance_cases()
        for case_id in (
            "tampered-policy",
            "tampered-evidence",
            "tampered-reconstruction",
            "tampered-decision",
            "tampered-receipt",
            "tampered-signature",
            "wrong-public-key",
        ):
            with self.subTest(case_id=case_id):
                package = OfflineProvenancePackageV1.model_validate(cases[case_id]["package"])
                result = verify_offline_package(package, now=FIXTURE_NOW)
                self.assertFalse(result.passed)

    def test_secret_like_metadata_fails_without_echoing_input(self) -> None:
        payload = signed_package().model_dump(mode="json")
        provenance = payload["receipt_provenance"]
        provenance["signer"]["signer_id"] = "sk-0123456789abcdefghijkl"
        payload["delivery_trust_receipt"]["provenance"] = deepcopy(provenance)
        package = OfflineProvenancePackageV1.model_validate(payload)
        result = verify_offline_package(package, now=FIXTURE_NOW)
        self.assertEqual(result.reasons, ("safe_metadata",))
        self.assertNotIn("0123456789", repr(result))

    def test_signing_cannot_expand_gate_scope(self) -> None:
        package = signed_package()
        unsigned = unsigned_package().receipt_provenance
        with self.assertRaisesRegex(ValueError, "cannot expand"):
            sign_provenance(
                unsigned,
                package.trust_policy,
                package.evidence_bundle,
                package.qualified_reconstruction,
                package.gate_decision,
                package.delivery_trust_receipt,
                object(),
                signer_id="fixture",
                key_id="fixture",
                maximum_scope=DeliveryScope.PRODUCTION_CANDIDATE,
            )

    def test_signer_can_narrow_but_not_reexpand_package_scope(self) -> None:
        package = unsigned_package()
        with tempfile.TemporaryDirectory() as directory:
            key_path = Path(directory) / "local.ed25519"
            generate_private_key(key_path)
            provenance = sign_provenance(
                package.receipt_provenance,
                package.trust_policy,
                package.evidence_bundle,
                package.qualified_reconstruction,
                package.gate_decision,
                package.delivery_trust_receipt,
                load_private_key(key_path),
                signer_id="fixture",
                key_id="fixture",
                maximum_scope=DeliveryScope.INTERNAL_HANDOFF,
            )
        narrowed = build_offline_package(
            package.trust_policy,
            package.evidence_bundle,
            package.qualified_reconstruction,
            package.gate_decision,
            package.delivery_trust_receipt,
            provenance,
        )
        result = verify_offline_package(narrowed, now=FIXTURE_NOW)
        self.assertTrue(result.passed, result.reasons)
        self.assertEqual(result.approved_scope, "internal_handoff")
        payload = narrowed.model_dump(mode="json")
        payload["claim_boundary"]["maximum_scope"] = "controlled_customer_handoff"
        with self.assertRaisesRegex(ValueError, "expands signer scope"):
            OfflineProvenancePackageV1.model_validate(payload)

    def test_private_keys_are_owner_only_and_never_packaged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            key_path = Path(directory) / "local.ed25519"
            generate_private_key(key_path)
            self.assertEqual(stat.S_IMODE(key_path.stat().st_mode), 0o600)
            load_private_key(key_path)
            key_path.chmod(0o644)
            with self.assertRaisesRegex(ProvenanceKeyError, "owner-only"):
                load_private_key(key_path)

        payload = json.dumps(signed_package().model_dump(mode="json"), sort_keys=True)
        self.assertNotIn("BEGIN PRIVATE KEY", payload)
        self.assertIn('"private_key_material_included": false', payload)

    def test_missing_crypto_dependency_fails_with_install_hint(self) -> None:
        original_import = builtins.__import__

        def blocked_import(name: str, *args: object, **kwargs: object) -> object:
            if name.startswith("cryptography"):
                raise ImportError("fixture blocks optional dependency")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=blocked_import):
            with self.assertRaisesRegex(ProvenanceDependencyError, "optional 'crypto'"):
                _crypto_types()

    def test_cli_keygen_sign_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "local.ed25519"
            package = root / "package.json"
            fixture = REPO / "fixtures" / "cbb-v1-contracts" / "pass.json"
            commands = [
                [
                    sys.executable,
                    str(REPO / "scripts" / "cbb_provenance.py"),
                    "keygen",
                    "--private-key",
                    str(key),
                    "--acknowledge-local-identity-only",
                ],
                [
                    sys.executable,
                    str(REPO / "scripts" / "cbb_provenance.py"),
                    "sign",
                    "--input",
                    str(fixture),
                    "--private-key",
                    str(key),
                    "--signer-id",
                    "local-test-signer",
                    "--key-id",
                    "local-test-key",
                    "--output",
                    str(package),
                ],
                [
                    sys.executable,
                    str(REPO / "scripts" / "cbb_provenance.py"),
                    "verify",
                    "--input",
                    str(package),
                    "--now",
                    FIXTURE_NOW,
                ],
            ]
            for command in commands:
                completed = subprocess.run(
                    command,
                    cwd=REPO,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_cli_failure_does_not_echo_key_path_or_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / "local.ed25519"
            key.write_bytes(b"existing")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts" / "cbb_provenance.py"),
                    "keygen",
                    "--private-key",
                    str(key),
                    "--acknowledge-local-identity-only",
                ],
                cwd=REPO,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertNotIn(str(key), completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertIn("key_target_exists", completed.stderr)

    def test_required_verifiers_pass(self) -> None:
        for script in (
            "verify_cbb_v1_provenance.py",
            "verify_cbb_v1_tamper_cases.py",
        ):
            completed = subprocess.run(
                [sys.executable, str(REPO / "scripts" / script), "--check"],
                cwd=REPO,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
