#!/usr/bin/env python3
"""Verify external-adopter attestation intake without inventing adopter evidence."""

from __future__ import annotations

import argparse
from base64 import urlsafe_b64encode
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_cbb_adoption_audit_assets import expected_outputs  # noqa: E402
from study_anything.cbb.adoption.attestation_fixtures import (  # noqa: E402
    EVALUATED_AT,
    build_adoption_attestation_cases,
    external_case,
)
from study_anything.cbb.adoption.attestation_intake import (  # noqa: E402
    adoption_attestation_digest,
    adoption_attestation_payload,
    evaluate_external_adoption_attestation,
)
from study_anything.cbb.adoption.attestation_models import (  # noqa: E402
    ExternalAdoptionAttestationEnvelopeV1,
    ExternalAdoptionAttestationReceiptV1,
    ExternalAdoptionAttestationV1,
    ExternalAdoptionExpectedScopeV1,
    TrustedAdopterIdentityV1,
)
from study_anything.cbb.adoption.evaluator import (  # noqa: E402
    evaluate_controlled_adoption,
)
from study_anything.cbb.adoption.models import ControlledAdoptionReceiptV1  # noqa: E402
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    CanonicalProtocolError,
    assert_safe_metadata,
    canonical_sha256,
)
from study_anything.cbb.provenance.fixtures import signed_package  # noqa: E402


REPORT_PATH = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-cbb-external-adoption-attestation.json"
)


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _rejected(fn: Callable[[], object], expected: str) -> bool:
    try:
        fn()
    except (CanonicalProtocolError, ValueError) as exc:
        return expected in str(exc)
    return False


def _b64url(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _hermetic_external_path(
    cases: dict[str, dict[str, Any]],
) -> tuple[
    ExternalAdoptionExpectedScopeV1,
    ExternalAdoptionAttestationEnvelopeV1,
    bool,
    ControlledAdoptionReceiptV1,
    Any,
]:
    envelope_payload = deepcopy(cases["synthetic-valid"]["envelope"])
    envelope_payload["source_class"] = "external_attestation"
    envelope_payload["adopter_trust"].update(
        {
            "identity_status": "externally_attested",
            "independence_attestation_ref": "contract-test:pre-pinned-adopter",
            "independent_from_repository": True,
            "fixture_only": False,
        }
    )
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    fingerprint = hashlib.sha256(public_key).hexdigest()
    attestation = ExternalAdoptionAttestationV1.model_validate(
        envelope_payload["attestation"]
    )
    envelope_payload["detached_signature"].update(
        {
            "public_key": _b64url(public_key),
            "public_key_fingerprint_sha256": fingerprint,
            "signed_payload_sha256": adoption_attestation_digest(attestation),
            "signature": _b64url(
                private_key.sign(adoption_attestation_payload(attestation))
            ),
        }
    )
    envelope_payload["adopter_trust"]["public_key_fingerprint_sha256"] = fingerprint
    envelope = ExternalAdoptionAttestationEnvelopeV1.model_validate(envelope_payload)
    expected_payload = deepcopy(cases["synthetic-valid"]["expected_scope"])
    expected_payload["trusted_adopters"] = [
        TrustedAdopterIdentityV1(
            organization_ref=envelope.adopter_trust.organization_ref,
            human_observer_ref=envelope.adopter_trust.human_observer_ref,
            public_key_fingerprint_sha256=(
                envelope.adopter_trust.public_key_fingerprint_sha256
            ),
            independence_attestation_ref=(
                envelope.adopter_trust.independence_attestation_ref
            ),
        ).model_dump(mode="json")
    ]
    expected = ExternalAdoptionExpectedScopeV1.model_validate(expected_payload)
    attestation_receipt = evaluate_external_adoption_attestation(
        expected,
        envelope,
        evaluated_at=envelope.submitted_at,
    )
    case = external_case(ROOT)
    controlled_receipt = evaluate_controlled_adoption(
        signed_package(),
        case,
        expected_release_scope_commit=case.binding.release_scope_commit,
        expected_conformance_pack_sha256=case.binding.conformance_pack_sha256,
        external_attestation_expected_scope=expected,
        external_attestation_envelope=envelope,
    )
    path_passed = (
        attestation_receipt.state.value == "external_attestation_verified"
        and attestation_receipt.real_adopter_evidence_accepted
        and controlled_receipt.status.value == "observed"
        and controlled_receipt.real_adopter_evidence
        and controlled_receipt.external_attestation_receipt_ref
        == attestation_receipt.receipt_id
        and not controlled_receipt.customer_delivery_authorized
        and not controlled_receipt.production_authorized
    )
    return expected, envelope, path_passed, controlled_receipt, private_key


def build_report() -> dict[str, Any]:
    generated_current = all(
        path.exists() and path.read_text(encoding="utf-8") == content
        for path, content in expected_outputs().items()
    )
    cases = build_adoption_attestation_cases(ROOT)
    expected_states = {
        "attestation-ready": "attestation_ready",
        "synthetic-valid": "synthetic_validated",
        "wrong-commit": "rejected",
        "wrong-case-digest": "rejected",
        "self-certified": "rejected",
        "untrusted-external": "rejected",
        "invalid-signature": "rejected",
    }
    case_reports: list[dict[str, Any]] = []
    for case_id in sorted(cases):
        payload = cases[case_id]
        expected_scope = ExternalAdoptionExpectedScopeV1.model_validate(
            payload["expected_scope"]
        )
        receipt = ExternalAdoptionAttestationReceiptV1.model_validate(
            payload["receipt"]
        )
        if payload["envelope"] is not None:
            envelope = ExternalAdoptionAttestationEnvelopeV1.model_validate(
                payload["envelope"]
            )
            rebuilt = evaluate_external_adoption_attestation(
                expected_scope,
                envelope,
                evaluated_at=EVALUATED_AT,
            )
            if rebuilt != receipt:
                raise RuntimeError(f"{case_id}: adoption attestation receipt drifted")
        if receipt.state.value != expected_states[case_id]:
            raise RuntimeError(f"{case_id}: unexpected adoption attestation state")
        if (
            receipt.real_adopter_evidence_accepted
            or receipt.observation_execution_completed
            or receipt.delivery_authority_granted
            or receipt.production_authority_granted
        ):
            raise RuntimeError(f"{case_id}: fixture claimed external authority or evidence")
        case_reports.append(
            {
                "case_id": case_id,
                "state": receipt.state.value,
                "signature_verified": receipt.signature_verified,
                "external_identity_attested": receipt.external_identity_attested,
                "real_adopter_evidence_accepted": (
                    receipt.real_adopter_evidence_accepted
                ),
            }
        )

    external_source_forgery = deepcopy(cases["synthetic-valid"]["envelope"])
    external_source_forgery["source_class"] = "external_attestation"
    synthetic_to_external_rejected = _rejected(
        lambda: ExternalAdoptionAttestationEnvelopeV1.model_validate(
            external_source_forgery
        ),
        "attested identity",
    )

    contradictory_observation = deepcopy(cases["synthetic-valid"]["envelope"])
    contradictory_observation["attestation"]["observation"][
        "adverse_event_count"
    ] = 1
    contradictory_observation_rejected = _rejected(
        lambda: ExternalAdoptionAttestationEnvelopeV1.model_validate(
            contradictory_observation
        ),
        "passing external observation cannot report adverse events",
    )

    forged_fingerprint_payload = deepcopy(cases["synthetic-valid"]["envelope"])
    forged_fingerprint_payload["detached_signature"][
        "public_key_fingerprint_sha256"
    ] = "f" * 64
    forged_fingerprint_payload["adopter_trust"][
        "public_key_fingerprint_sha256"
    ] = "f" * 64
    forged_envelope = ExternalAdoptionAttestationEnvelopeV1.model_validate(
        forged_fingerprint_payload
    )
    forged_receipt = evaluate_external_adoption_attestation(
        ExternalAdoptionExpectedScopeV1.model_validate(
            cases["synthetic-valid"]["expected_scope"]
        ),
        forged_envelope,
        evaluated_at=EVALUATED_AT,
    )
    forged_fingerprint_rejected = (
        forged_receipt.state.value == "rejected"
        and "public_key_fingerprint_valid" in forged_receipt.blocking_reasons
    )

    fixture_key_external_payload = deepcopy(cases["synthetic-valid"]["envelope"])
    fixture_key_external_payload["source_class"] = "external_attestation"
    fixture_key_external_payload["adopter_trust"].update(
        {
            "identity_status": "externally_attested",
            "independence_attestation_ref": "contract-test:fixture-key-must-fail",
            "independent_from_repository": True,
            "fixture_only": False,
        }
    )
    fixture_key_external_envelope = ExternalAdoptionAttestationEnvelopeV1.model_validate(
        fixture_key_external_payload
    )
    fixture_key_expected_payload = deepcopy(
        cases["synthetic-valid"]["expected_scope"]
    )
    fixture_key_expected_payload["trusted_adopters"] = [
        TrustedAdopterIdentityV1(
            organization_ref=(
                fixture_key_external_envelope.adopter_trust.organization_ref
            ),
            human_observer_ref=(
                fixture_key_external_envelope.adopter_trust.human_observer_ref
            ),
            public_key_fingerprint_sha256=(
                fixture_key_external_envelope.adopter_trust.public_key_fingerprint_sha256
            ),
            independence_attestation_ref=(
                fixture_key_external_envelope.adopter_trust.independence_attestation_ref
            ),
        ).model_dump(mode="json")
    ]
    fixture_key_external_receipt = evaluate_external_adoption_attestation(
        ExternalAdoptionExpectedScopeV1.model_validate(fixture_key_expected_payload),
        fixture_key_external_envelope,
        evaluated_at=EVALUATED_AT,
    )
    known_fixture_key_rejected = (
        fixture_key_external_receipt.state.value == "rejected"
        and "known_fixture_public_key_rejected"
        in fixture_key_external_receipt.blocking_reasons
    )

    case = external_case(ROOT)
    missing_attestation_receipt = evaluate_controlled_adoption(
        signed_package(),
        case,
        expected_release_scope_commit=case.binding.release_scope_commit,
        expected_conformance_pack_sha256=case.binding.conformance_pack_sha256,
    )
    missing_attestation_blocks_external_case = (
        missing_attestation_receipt.status.value == "blocked"
        and not missing_attestation_receipt.real_adopter_evidence
        and "external_adopter_attestation_supported"
        in missing_attestation_receipt.reasons
    )

    (
        hermetic_expected,
        hermetic_envelope,
        hermetic_external_path_passed,
        hermetic_controlled_receipt,
        hermetic_private_key,
    ) = _hermetic_external_path(cases)
    controlled_receipt_material = {
        "case": case.model_dump(mode="json"),
        "checks": hermetic_controlled_receipt.checks,
        "status": hermetic_controlled_receipt.status.value,
        "resulting_scope": hermetic_controlled_receipt.resulting_scope.value,
        "external_attestation_receipt_ref": (
            hermetic_controlled_receipt.external_attestation_receipt_ref
        ),
        "external_attestation_receipt_sha256": (
            hermetic_controlled_receipt.external_attestation_receipt_sha256
        ),
    }
    controlled_receipt_binds_external_attestation = (
        hermetic_controlled_receipt.receipt_id
        == "controlled-adoption:"
        + canonical_sha256(controlled_receipt_material)[:32]
    )

    mismatched_expected_payload = hermetic_expected.model_dump(mode="json")
    mismatched_expected_payload["binding"]["adoption_case_sha256"] = "f" * 64
    mismatched_expected = ExternalAdoptionExpectedScopeV1.model_validate(
        mismatched_expected_payload
    )
    mismatched_controlled = evaluate_controlled_adoption(
        signed_package(),
        case,
        expected_release_scope_commit=case.binding.release_scope_commit,
        expected_conformance_pack_sha256=case.binding.conformance_pack_sha256,
        external_attestation_expected_scope=mismatched_expected,
        external_attestation_envelope=hermetic_envelope,
    )
    case_digest_mismatch_blocks_controlled_adoption = (
        mismatched_controlled.status.value == "blocked"
        and not mismatched_controlled.real_adopter_evidence
    )

    semantic_mismatch_payload = hermetic_envelope.model_dump(mode="json")
    semantic_mismatch_payload["attestation"]["requested_scope"] = "sandbox_only"
    semantic_attestation = ExternalAdoptionAttestationV1.model_validate(
        semantic_mismatch_payload["attestation"]
    )
    semantic_mismatch_payload["detached_signature"][
        "signed_payload_sha256"
    ] = adoption_attestation_digest(semantic_attestation)
    semantic_mismatch_payload["detached_signature"]["signature"] = _b64url(
        hermetic_private_key.sign(adoption_attestation_payload(semantic_attestation))
    )
    semantic_mismatch_envelope = (
        ExternalAdoptionAttestationEnvelopeV1.model_validate(
            semantic_mismatch_payload
        )
    )
    semantic_mismatch_controlled = evaluate_controlled_adoption(
        signed_package(),
        case,
        expected_release_scope_commit=case.binding.release_scope_commit,
        expected_conformance_pack_sha256=case.binding.conformance_pack_sha256,
        external_attestation_expected_scope=hermetic_expected,
        external_attestation_envelope=semantic_mismatch_envelope,
    )
    attestation_semantic_mismatch_blocks_controlled_adoption = (
        semantic_mismatch_controlled.status.value == "blocked"
        and not semantic_mismatch_controlled.real_adopter_evidence
    )

    secret_envelope = deepcopy(cases["synthetic-valid"]["envelope"])
    secret_envelope["api_key"] = "synthetic-secret-field"
    secret_like_metadata_rejected = _rejected(
        lambda: assert_safe_metadata(
            secret_envelope,
            label="external adoption attestation fixture",
        ),
        "forbidden field",
    )

    states = {item["case_id"]: item["state"] for item in case_reports}
    controlled_parameters = set(
        inspect.signature(evaluate_controlled_adoption).parameters
    )
    checks = {
        "generated_assets_current": generated_current,
        "seven_attestation_cases_replayed": len(case_reports) == 7,
        "attestation_states_remain_distinct": set(states.values())
        == {"attestation_ready", "synthetic_validated", "rejected"},
        "wrong_commit_rejected": states["wrong-commit"] == "rejected",
        "wrong_case_digest_rejected": states["wrong-case-digest"] == "rejected",
        "invalid_signature_rejected": states["invalid-signature"] == "rejected",
        "self_certification_rejected": states["self-certified"] == "rejected",
        "untrusted_external_identity_rejected": (
            states["untrusted-external"] == "rejected"
        ),
        "synthetic_to_external_source_forgery_rejected": (
            synthetic_to_external_rejected
        ),
        "contradictory_observation_rejected": contradictory_observation_rejected,
        "forged_public_key_fingerprint_rejected": forged_fingerprint_rejected,
        "known_fixture_public_key_rejected": known_fixture_key_rejected,
        "missing_attestation_blocks_external_case": (
            missing_attestation_blocks_external_case
        ),
        "case_digest_mismatch_blocks_controlled_adoption": (
            case_digest_mismatch_blocks_controlled_adoption
        ),
        "attestation_semantic_mismatch_blocks_controlled_adoption": (
            attestation_semantic_mismatch_blocks_controlled_adoption
        ),
        "hermetic_external_path_contract_passed": hermetic_external_path_passed,
        "controlled_receipt_binds_external_attestation": (
            controlled_receipt_binds_external_attestation
        ),
        "controlled_adoption_replays_envelope_not_receipt": (
            "external_attestation_expected_scope" in controlled_parameters
            and "external_attestation_envelope" in controlled_parameters
            and "external_attestation_receipt" not in controlled_parameters
        ),
        "secret_like_metadata_rejected": secret_like_metadata_rejected,
        "no_generated_fixture_claims_real_adopter_evidence": all(
            not item["real_adopter_evidence_accepted"] for item in case_reports
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": "cbb-external-adoption-attestation-verification-v1",
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "case_reports": case_reports,
        "adoption": {
            "coordination_issue_ref": None,
            "independent_external_adopter_assigned": False,
            "external_signed_attestation_received": False,
            "real_external_adopter_evidence_count": 0,
            "hermetic_external_path_contract_tested": (
                hermetic_external_path_passed
            ),
        },
        "claim_boundary": (
            "This verifies signature, identity, trust-root, case-binding, and Controlled "
            "Adoption integration behavior with synthetic fixtures and a hermetic path "
            "simulation. It does not identify an adopter, receive external evidence, "
            "authorize delivery, prove customer outcomes, or complete an independent audit."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "raw_customer_payload_included": False,
            "real_secrets_included": False,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "production_mutation_performed": False,
            "automatic_customer_send_performed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    data = _json_bytes(report)
    if args.check:
        if not REPORT_PATH.exists() or REPORT_PATH.read_bytes() != data:
            print(
                "verify_cbb_external_adoption_attestation failed: report is stale. "
                "Run without --check.",
                file=sys.stderr,
            )
            return 1
        print(data.decode("utf-8"), end="")
        return 0 if report["status"] == "pass" else 1
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_bytes(data)
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
