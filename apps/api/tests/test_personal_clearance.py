from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from pydantic import ValidationError

from _path import ROOT  # noqa: F401

from study_anything.cbb.personal.audit import (
    ARTIFACT_FILENAMES,
    ARTIFACT_RELATIVE_DIR,
    CONFIG_RELATIVE_PATH,
    PersonalClearanceError,
    audit_project,
    default_config,
    initialize_project,
    load_config,
    verify_project_clearance,
    write_audit_artifacts,
)
from study_anything.cbb.personal.models import PersonalClearanceConfigV1
from study_anything.cbb.protocol.models import DeliveryScope


EVALUATED_AT = "2026-07-11T12:00:00Z"
VERIFIED_AT = "2026-07-11T12:05:00Z"


class PersonalClearanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self._git("init")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _git(self, *args: str) -> None:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())

    def _complete_config(self, *, checks: list[dict[str, object]] | None = None) -> None:
        payload = default_config("personal-test").model_dump(mode="json")
        payload.update(
            {
                "purpose": "Audit one exact local development candidate.",
                "non_goals": ["No external delivery or production use."],
                "critical_failure_path": "A required local verification can fail.",
                "rollback_trigger": "Any failed check or unexpected project-state mutation.",
                "rollback_strategy": "Discard the candidate and return to the last Git state.",
            }
        )
        if checks is not None:
            payload["checks"] = checks
        config = PersonalClearanceConfigV1.model_validate(payload)
        config_path = self.root / CONFIG_RELATIVE_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (config_path.parent / ".gitignore").write_text("/artifacts/\n", encoding="utf-8")

    def _allowed_audit(self) -> None:
        _, artifacts = audit_project(
            self.root,
            execute_checks=True,
            accept_responsibility=True,
            evaluated_at=EVALUATED_AT,
        )
        self.assertEqual(artifacts.receipt.status, "allow")
        self.assertEqual(artifacts.receipt.approved_scope, DeliveryScope.PERSONAL_LOCAL)
        write_audit_artifacts(self.root, artifacts)

    def test_init_starts_blocked_with_trackable_config_and_ignored_artifacts(self) -> None:
        config_path = initialize_project(self.root)
        self.assertEqual(config_path.relative_to(self.root), CONFIG_RELATIVE_PATH)
        self.assertIn("TODO:", config_path.read_text(encoding="utf-8"))
        self.assertEqual(
            (config_path.parent / ".gitignore").read_text(encoding="utf-8"),
            "/artifacts/\n",
        )
        _, artifacts = audit_project(
            self.root,
            execute_checks=False,
            accept_responsibility=False,
            evaluated_at=EVALUATED_AT,
        )
        self.assertEqual(artifacts.receipt.status, "needs_evidence")
        self.assertEqual(artifacts.receipt.approved_scope, DeliveryScope.BLOCKED)

    def test_explicit_checks_and_responsibility_allow_only_personal_local(self) -> None:
        self._complete_config()
        self._allowed_audit()
        verified = verify_project_clearance(self.root, verified_at=VERIFIED_AT)
        self.assertEqual(verified["status"], "pass")
        self.assertEqual(verified["approved_scope"], "personal_local")

    def test_missing_responsibility_never_allows(self) -> None:
        self._complete_config()
        _, artifacts = audit_project(
            self.root,
            execute_checks=True,
            accept_responsibility=False,
            evaluated_at=EVALUATED_AT,
        )
        self.assertEqual(artifacts.receipt.status, "needs_evidence")
        self.assertIn("risk_owner_acceptance", artifacts.receipt.missing_evidence_types)

    def test_failed_check_blocks(self) -> None:
        self._complete_config(
            checks=[
                {
                    "check_id": "required-failure",
                    "argv": ["git", "rev-parse", "--verify", "refs/heads/does-not-exist"],
                    "timeout_seconds": 30,
                    "required": True,
                }
            ]
        )
        _, artifacts = audit_project(
            self.root,
            execute_checks=True,
            accept_responsibility=True,
            evaluated_at=EVALUATED_AT,
        )
        self.assertEqual(artifacts.receipt.status, "block")
        self.assertIn("evidence_failed:configured_checks", artifacts.receipt.reasons)

    def test_check_that_mutates_project_is_a_hard_deny(self) -> None:
        self._complete_config(
            checks=[
                {
                    "check_id": "mutating-check",
                    "argv": [
                        "python3",
                        "-c",
                        "from pathlib import Path; Path('mutation.txt').write_text('changed')",
                    ],
                    "timeout_seconds": 30,
                    "required": True,
                }
            ]
        )
        _, artifacts = audit_project(
            self.root,
            execute_checks=True,
            accept_responsibility=True,
            evaluated_at=EVALUATED_AT,
        )
        self.assertEqual(artifacts.receipt.status, "block")
        self.assertTrue(artifacts.receipt.project_state_mutated_during_checks)
        self.assertIn(
            "hard_deny:audit_check_mutated_project",
            artifacts.receipt.reasons,
        )

    def test_state_change_and_expiry_invalidate_receipt(self) -> None:
        self._complete_config()
        self._allowed_audit()
        (self.root / "changed-after-clearance.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(PersonalClearanceError, "project_state_current"):
            verify_project_clearance(self.root, verified_at=VERIFIED_AT)

        (self.root / "changed-after-clearance.txt").unlink()
        with self.assertRaisesRegex(PersonalClearanceError, "receipt_not_expired"):
            verify_project_clearance(self.root, verified_at="2026-07-13T12:00:00Z")

    def test_config_change_invalidates_receipt(self) -> None:
        self._complete_config()
        self._allowed_audit()
        config_path = self.root / CONFIG_RELATIVE_PATH
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        payload["purpose"] = "Audit a different local development candidate."
        config_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(PersonalClearanceError, "config_current"):
            verify_project_clearance(self.root, verified_at=VERIFIED_AT)

    def test_missing_critical_artifact_blocks_verification(self) -> None:
        self._complete_config()
        self._allowed_audit()
        evidence_path = (
            self.root / ARTIFACT_RELATIVE_DIR / ARTIFACT_FILENAMES["evidence"]
        )
        evidence_path.unlink()

        with self.assertRaisesRegex(
            PersonalClearanceError,
            "required artifact is missing: evidence-bundle.json",
        ):
            verify_project_clearance(self.root, verified_at=VERIFIED_AT)

    def test_old_receipt_replay_after_new_audit_is_rejected(self) -> None:
        self._complete_config()
        self._allowed_audit()
        receipt_path = self.root / ARTIFACT_RELATIVE_DIR / ARTIFACT_FILENAMES["receipt"]
        old_receipt = receipt_path.read_text(encoding="utf-8")

        (self.root / "new-state.txt").write_text("new state\n", encoding="utf-8")
        _, updated = audit_project(
            self.root,
            execute_checks=True,
            accept_responsibility=True,
            evaluated_at="2026-07-11T12:10:00Z",
        )
        write_audit_artifacts(self.root, updated)
        receipt_path.write_text(old_receipt, encoding="utf-8")

        with self.assertRaisesRegex(PersonalClearanceError, "receipt_bound_to_subject"):
            verify_project_clearance(self.root, verified_at="2026-07-11T12:15:00Z")

    def test_tamper_and_scope_expansion_are_rejected(self) -> None:
        self._complete_config()
        self._allowed_audit()
        receipt_path = self.root / ARTIFACT_RELATIVE_DIR / ARTIFACT_FILENAMES["receipt"]
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload["policy_digest_sha256"] = "0" * 64
        receipt_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(PersonalClearanceError, "policy_digest_matches"):
            verify_project_clearance(self.root, verified_at=VERIFIED_AT)

        expanded = deepcopy(default_config("personal-test").model_dump(mode="json"))
        expanded["maximum_scope"] = "controlled_customer_handoff"
        with self.assertRaises(ValidationError):
            PersonalClearanceConfigV1.model_validate(expanded)

    def test_artifacts_never_include_local_absolute_path_or_raw_output(self) -> None:
        self._complete_config()
        self._allowed_audit()
        output_dir = self.root / ARTIFACT_RELATIVE_DIR
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in output_dir.glob("*.json")
        )
        self.assertNotIn(str(self.root), combined)
        self.assertNotIn("raw stdout", combined.lower())
        self.assertNotIn("raw stderr", combined.lower())

        report = (output_dir / ARTIFACT_FILENAMES["html"]).read_text(
            encoding="utf-8"
        )
        self.assertIn("table-layout: fixed", report)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", report)
        self.assertIn("overflow-wrap: anywhere", report)

    def test_secret_like_config_is_rejected_before_execution(self) -> None:
        self._complete_config()
        config_path = self.root / CONFIG_RELATIVE_PATH
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        payload["purpose"] = "credential " + "sk-" + ("x" * 24)
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(PersonalClearanceError, "secret-like"):
            load_config(self.root)


if __name__ == "__main__":
    unittest.main()
