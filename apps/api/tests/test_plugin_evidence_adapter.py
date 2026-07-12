from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from _path import ROOT  # noqa: F401

from study_anything.cbb.plugin_evidence.evaluator import evaluate_plugin_evidence
from study_anything.cbb.plugin_evidence.fixtures import (
    EVALUATED_AT,
    fixture_bundles,
    fixture_payloads,
)
from study_anything.cbb.plugin_evidence.models import PluginEvidenceBundleV1
from study_anything.cbb.personal.audit import (
    CONFIG_RELATIVE_PATH,
    audit_project,
    default_config,
)
from study_anything.cbb.personal.models import PersonalClearanceConfigV1
from study_anything.cbb.protocol.canonical import pretty_json
from study_anything.cbb.protocol.models import DeliveryScope


class PluginEvidenceAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundles = fixture_bundles()

    def _decision(self, name: str):
        return evaluate_plugin_evidence(
            self.bundles[name],
            evaluated_at=EVALUATED_AT,
        )

    def test_narrow_bound_cases_allow_only_personal_local(self) -> None:
        for name in (
            "pass-local-read",
            "pass-bound-external-read",
            "pass-bound-local-write",
        ):
            with self.subTest(name=name):
                decision = self._decision(name)
                self.assertEqual(decision.status, "allow_personal_local")
                self.assertEqual(decision.approved_scope, DeliveryScope.PERSONAL_LOCAL)
                self.assertFalse(decision.customer_delivery_authorized)
                self.assertFalse(decision.production_authorized)
                self.assertFalse(decision.external_action_authorized)

    def test_manifest_only_never_becomes_delivery_evidence(self) -> None:
        decision = self._decision("needs-manifest-only")
        self.assertEqual(decision.status, "needs_evidence")
        self.assertEqual(decision.approved_scope, DeliveryScope.BLOCKED)
        self.assertFalse(decision.manifest_or_install_state_sufficient)
        self.assertIn("runtime_execution", decision.missing_evidence)
        self.assertIn("package_digest", decision.missing_evidence)

    def test_external_write_and_observed_external_mutation_hard_block(self) -> None:
        write = self._decision("block-external-write")
        mutation = self._decision("block-external-mutation")
        self.assertIn("hard_deny:external_write_capability", write.reasons)
        self.assertIn("hard_deny:external_mutation_observed", mutation.reasons)
        self.assertEqual(write.approved_scope, DeliveryScope.BLOCKED)
        self.assertEqual(mutation.approved_scope, DeliveryScope.BLOCKED)

    def test_ui_and_professional_outputs_require_native_domain_evidence(self) -> None:
        native = self._decision("needs-native-verification")
        domain = self._decision("needs-domain-evidence")
        self.assertIn("native_verification", native.missing_evidence)
        self.assertIn(
            "domain_evidence_and_qualified_reconstruction",
            domain.missing_evidence,
        )

    def test_mutable_external_inputs_expire(self) -> None:
        decision = self._decision("needs-fresh-external-input")
        self.assertEqual(decision.status, "needs_evidence")
        self.assertIn("external_input_freshness", decision.missing_evidence)

    def test_runtime_failure_and_credential_use_are_hard_denies(self) -> None:
        runtime = self._decision("block-runtime-failure")
        credentials = self._decision("block-credential-use")
        self.assertIn("hard_deny:runtime_failed", runtime.reasons)
        self.assertIn("hard_deny:credentials_used", credentials.reasons)

    def test_scope_expansion_is_rejected_by_contract(self) -> None:
        payload = deepcopy(fixture_payloads()["pass-local-read"])
        payload["requested_scope"] = "controlled_customer_handoff"
        with self.assertRaises(ValidationError):
            PluginEvidenceBundleV1.model_validate(payload)

    def test_decision_is_deterministic_for_same_bundle_and_time(self) -> None:
        first = self._decision("pass-local-read")
        second = self._decision("pass-local-read")
        self.assertEqual(first, second)

    def test_failed_runtime_dependency_check_is_a_hard_deny(self) -> None:
        payload = deepcopy(fixture_payloads()["pass-local-read"])
        payload["runtime"]["dependency_check"] = "failed"
        bundle = PluginEvidenceBundleV1.model_validate(payload)
        decision = evaluate_plugin_evidence(bundle, evaluated_at=EVALUATED_AT)
        self.assertEqual(decision.status, "block")
        self.assertIn("hard_deny:runtime_dependency_check_failed", decision.reasons)

    def test_irrelevant_missing_native_or_domain_state_does_not_crash(self) -> None:
        payload = deepcopy(fixture_payloads()["pass-local-read"])
        payload["native_verification"]["status"] = "missing"
        payload["domain_evidence"].update(
            {"status": "missing", "qualified_reconstruction": "missing"}
        )
        bundle = PluginEvidenceBundleV1.model_validate(payload)
        decision = evaluate_plugin_evidence(bundle, evaluated_at=EVALUATED_AT)
        self.assertEqual(decision.status, "allow_personal_local")

    def test_installed_adapter_composes_with_personal_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            completed = subprocess.run(
                ["git", "init"],
                cwd=root,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())

            now = datetime.now(timezone.utc).replace(microsecond=0)
            now_text = now.isoformat().replace("+00:00", "Z")
            valid_until = (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
            payload = deepcopy(fixture_payloads()["pass-local-read"])
            payload["observed_at"] = now_text
            payload["valid_until"] = valid_until
            payload["runtime"]["observed_at"] = now_text
            for item in payload["inputs"]:
                item["observed_at"] = now_text
            for item in payload["checks"]:
                item["observed_at"] = now_text

            evidence_path = root / ".delivery-clearance" / "plugin-evidence.json"
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text(pretty_json(payload), encoding="utf-8")

            config_payload = default_config("plugin-composition-test").model_dump(mode="json")
            config_payload.update(
                {
                    "purpose": "Audit one plugin-assisted local development candidate.",
                    "non_goals": ["No customer, external, or production delivery."],
                    "critical_failure_path": "Plugin evidence may be missing or outside scope.",
                    "rollback_trigger": "The plugin evidence gate returns a non-zero status.",
                    "rollback_strategy": "Keep the candidate blocked and inspect missing evidence.",
                    "checks": [
                        {
                            "check_id": "plugin-evidence",
                            "argv": [
                                "delivery-clearance-plugin-evidence",
                                ".delivery-clearance/plugin-evidence.json",
                            ],
                            "timeout_seconds": 60,
                            "required": True,
                        }
                    ],
                }
            )
            config = PersonalClearanceConfigV1.model_validate(config_payload)
            config_path = root / CONFIG_RELATIVE_PATH
            config_path.write_text(pretty_json(config), encoding="utf-8")
            (config_path.parent / ".gitignore").write_text(
                "/artifacts/\n",
                encoding="utf-8",
            )

            env_path = f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}"
            with patch.dict(os.environ, {"PATH": env_path}):
                _, allowed = audit_project(
                    root,
                    execute_checks=True,
                    accept_responsibility=True,
                    evaluated_at=now_text,
                )
            self.assertEqual(allowed.receipt.status, "allow")
            self.assertEqual(allowed.receipt.approved_scope, DeliveryScope.PERSONAL_LOCAL)

            payload["capabilities"] = ["local_read", "external_write"]
            evidence_path.write_text(pretty_json(payload), encoding="utf-8")
            with patch.dict(os.environ, {"PATH": env_path}):
                _, blocked = audit_project(
                    root,
                    execute_checks=True,
                    accept_responsibility=True,
                    evaluated_at=now_text,
                )
            self.assertEqual(blocked.receipt.status, "block")
            self.assertEqual(blocked.receipt.approved_scope, DeliveryScope.BLOCKED)


if __name__ == "__main__":
    unittest.main()
