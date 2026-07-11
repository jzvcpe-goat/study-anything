"""Synthetic fixtures for external-adoption attestation intake."""

from __future__ import annotations

from base64 import urlsafe_b64encode
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from study_anything.cbb.adoption.attestation_intake import (
    adoption_attestation_digest,
    adoption_attestation_payload,
    adoption_attestation_ready_receipt,
    evaluate_external_adoption_attestation,
)
from study_anything.cbb.adoption.attestation_models import (
    AdoptionAttestationSourceClass,
    AdoptionDetachedSignatureV1,
    AdopterTrustRecordV1,
    ExternalAdoptionAttestationBindingV1,
    ExternalAdoptionAttestationEnvelopeV1,
    ExternalAdoptionAttestationReceiptV1,
    ExternalAdoptionAttestationV1,
    ExternalAdoptionExpectedScopeV1,
    ExternalAdoptionObservationV1,
)
from study_anything.cbb.adoption.models import (
    AdoptionBindingV1,
    AdoptionEffectBoundaryV1,
    AdoptionEvidenceClass,
    AdoptionMode,
    AdoptionObservationKind,
    ControlledAdoptionCaseV1,
)
from study_anything.cbb.outcomes.fixtures import build_outcome_cases
from study_anything.cbb.protocol.canonical import (
    canonical_sha256,
    model_payload,
    schema_text,
)
from study_anything.cbb.protocol.models import DeliveryScope, PrivacyBoundaryV1
from study_anything.cbb.provenance.fixtures import signed_package


FIXTURE_ROOT = Path("fixtures") / "cbb-external-adoption-attestation"
PINNED_SCOPE_COMMIT = "cc9a5aa1f5739cd667addfa774d6301f7873efda"
OBSERVED_AT = "2026-07-15T00:00:00Z"
COMPLETED_AT = "2026-07-15T01:00:00Z"
SUBMITTED_AT = "2026-07-15T02:00:00Z"
EVALUATED_AT = "2026-07-15T03:00:00Z"


def _b64url(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def fixture_private_key() -> Any:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(
            b"delivery-clearance-external-adoption-attestation-fixture"
        ).digest()
    )


def _public_key_bytes(private_key: Any) -> bytes:
    from cryptography.hazmat.primitives import serialization

    return cast(
        bytes,
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    )


def _privacy() -> PrivacyBoundaryV1:
    return PrivacyBoundaryV1(
        metadata_only=True,
        raw_source_text_included=False,
        raw_report_text_included=False,
        raw_customer_payload_included=False,
        attention_stream_included=False,
        model_prompts_included=False,
        model_credentials_included=False,
        cookies_or_bearer_tokens_included=False,
        signed_urls_included=False,
        production_mutation_performed=False,
        automatic_customer_send_performed=False,
    )


def _conformance_digest(root: Path) -> str:
    payload = json.loads(
        (
            root
            / "platform"
            / "generated"
            / "study-anything-cbb-v1-conformance-pack.json"
        ).read_text(encoding="utf-8")
    )
    return str(payload["archive_sha256"])


def external_case(root: Path) -> ControlledAdoptionCaseV1:
    package = signed_package()
    outcome = build_outcome_cases()["monitored-no-adverse-signal"]["receipt"]
    return ControlledAdoptionCaseV1(
        schema_version="cbb.controlled-adoption-case.v1",
        case_id="external-canary-observation",
        evidence_class=AdoptionEvidenceClass.EXTERNAL_ADOPTER,
        adoption_mode=AdoptionMode.CANARY,
        observation_kind=AdoptionObservationKind.PASS,
        binding=AdoptionBindingV1(
            release_scope_commit=PINNED_SCOPE_COMMIT,
            protocol_version="1.0.0",
            source_package_ref=package.package_id,
            source_package_digest_sha256=(
                package.receipt_provenance.package_digest_sha256
            ),
            source_delivery_receipt_ref=package.delivery_trust_receipt.receipt_id,
            source_clearance_revocation_handle=(
                package.receipt_provenance.revocation.handle
            ),
            source_approved_scope=package.gate_decision.approved_scope,
            conformance_pack_sha256=_conformance_digest(root),
        ),
        effect_boundary=AdoptionEffectBoundaryV1(
            requested_scope=DeliveryScope.INTERNAL_HANDOFF,
            real_user_exposure_observed=False,
            external_effect_observed=False,
            production_mutation_performed=False,
            automatic_customer_send_performed=False,
        ),
        operator_reconstruction_present=True,
        risk_owner_reacceptance_present=True,
        source_revoked_before_observation=False,
        reopen_requested=False,
        real_adopter_evidence_claimed=True,
        outcome_receipt=outcome,
        observed_at=OBSERVED_AT,
        privacy=_privacy(),
    )


def expected_scope(root: Path) -> ExternalAdoptionExpectedScopeV1:
    case = external_case(root)
    binding = case.binding
    return ExternalAdoptionExpectedScopeV1(
        binding=ExternalAdoptionAttestationBindingV1(
            repository="jzvcpe-goat/study-anything",
            release_scope_commit=binding.release_scope_commit,
            protocol_version=binding.protocol_version,
            conformance_pack_sha256=binding.conformance_pack_sha256,
            source_package_digest_sha256=binding.source_package_digest_sha256,
            source_delivery_receipt_ref=binding.source_delivery_receipt_ref,
            source_clearance_revocation_handle=(
                binding.source_clearance_revocation_handle
            ),
            source_approved_scope=binding.source_approved_scope,
            adoption_case_id=case.case_id,
            adoption_case_sha256=canonical_sha256(case.model_dump(mode="json")),
        ),
        trusted_adopters=[],
        repository_actor_refs=[
            "jzvcpe-goat",
            "study-anything-maintainers",
            "repository-maintainer",
        ],
    )


def _signed_envelope(
    root: Path,
    case_id: str,
    *,
    source_class: AdoptionAttestationSourceClass = (
        AdoptionAttestationSourceClass.SYNTHETIC_FIXTURE
    ),
    binding_override: dict[str, Any] | None = None,
    organization_ref: str = "organization:synthetic-adopter-fixture",
    human_observer_ref: str = "human:synthetic-adopter-observer",
    externally_attested_identity: bool = False,
) -> ExternalAdoptionAttestationEnvelopeV1:
    scope = expected_scope(root)
    binding_payload = model_payload(scope.binding)
    if binding_override:
        binding_payload.update(binding_override)
    envelope_id = f"external-adoption-attestation:{case_id}"
    case = external_case(root)
    attestation = ExternalAdoptionAttestationV1(
        binding=ExternalAdoptionAttestationBindingV1.model_validate(binding_payload),
        adoption_mode=case.adoption_mode,
        observation_kind=case.observation_kind,
        requested_scope=case.effect_boundary.requested_scope,
        outcome_receipt_ref=(
            case.outcome_receipt.outcome_receipt_id
            if case.outcome_receipt is not None
            else None
        ),
        observation=ExternalAdoptionObservationV1(
            observed_at=OBSERVED_AT,
            completed_at=COMPLETED_AT,
            observed_delivery_count=1,
            adverse_event_count=0,
            rollback_exercised=False,
            revocation_exercised=False,
        ),
        signature_ref=f"detached:{envelope_id}",
        privacy=_privacy(),
    )
    private_key = fixture_private_key()
    public_key = _public_key_bytes(private_key)
    fingerprint = hashlib.sha256(public_key).hexdigest()
    detached = AdoptionDetachedSignatureV1(
        algorithm="ed25519",
        public_key_encoding="ed25519-raw-base64url",
        public_key=_b64url(public_key),
        public_key_fingerprint_sha256=fingerprint,
        signed_payload_sha256=adoption_attestation_digest(attestation),
        signature=_b64url(private_key.sign(adoption_attestation_payload(attestation))),
    )
    trust = AdopterTrustRecordV1(
        organization_ref=organization_ref,
        human_observer_ref=human_observer_ref,
        public_key_fingerprint_sha256=fingerprint,
        identity_status=(
            "externally_attested"
            if externally_attested_identity
            else "synthetic_fixture"
        ),
        independence_attestation_ref=(
            "external:self-asserted-untrusted"
            if externally_attested_identity
            else "fixture-only:no-external-identity"
        ),
        independent_from_repository=externally_attested_identity,
        fixture_only=not externally_attested_identity,
    )
    return ExternalAdoptionAttestationEnvelopeV1(
        schema_version="cbb.external-adoption-attestation-envelope.v1",
        envelope_id=envelope_id,
        source_class=source_class,
        attestation=attestation,
        detached_signature=detached,
        adopter_trust=trust,
        submitted_at=SUBMITTED_AT,
        privacy=_privacy(),
    )


def build_adoption_attestation_cases(root: Path) -> dict[str, dict[str, Any]]:
    scope = expected_scope(root)
    ready = adoption_attestation_ready_receipt(scope, evaluated_at=EVALUATED_AT)
    envelopes: dict[str, ExternalAdoptionAttestationEnvelopeV1] = {
        "synthetic-valid": _signed_envelope(root, "synthetic-valid"),
        "wrong-commit": _signed_envelope(
            root,
            "wrong-commit",
            binding_override={"release_scope_commit": "0" * 40},
        ),
        "wrong-case-digest": _signed_envelope(
            root,
            "wrong-case-digest",
            binding_override={"adoption_case_sha256": "1" * 64},
        ),
        "self-certified": _signed_envelope(
            root,
            "self-certified",
            source_class=AdoptionAttestationSourceClass.EXTERNAL_SHAPE_FIXTURE,
            organization_ref="jzvcpe-goat",
            human_observer_ref="repository-maintainer",
        ),
        "untrusted-external": _signed_envelope(
            root,
            "untrusted-external",
            source_class=AdoptionAttestationSourceClass.EXTERNAL_ATTESTATION,
            externally_attested_identity=True,
        ),
    }
    invalid_signature = deepcopy(
        model_payload(_signed_envelope(root, "invalid-signature"))
    )
    signature = invalid_signature["detached_signature"]["signature"]
    invalid_signature["detached_signature"]["signature"] = (
        ("A" if signature[0] != "A" else "B") + signature[1:]
    )
    envelopes["invalid-signature"] = (
        ExternalAdoptionAttestationEnvelopeV1.model_validate(invalid_signature)
    )

    result: dict[str, dict[str, Any]] = {
        "attestation-ready": {
            "case_id": "attestation-ready",
            "fixture_class": "no_external_attestation",
            "controlled_adoption_case": model_payload(external_case(root)),
            "expected_scope": model_payload(scope),
            "envelope": None,
            "receipt": model_payload(ready),
            "expected": {
                "state": ready.state.value,
                "real_adopter_evidence_accepted": False,
                "observation_execution_completed": False,
            },
        }
    }
    for case_id, envelope in envelopes.items():
        receipt = evaluate_external_adoption_attestation(
            scope,
            envelope,
            evaluated_at=EVALUATED_AT,
        )
        result[case_id] = {
            "case_id": case_id,
            "fixture_class": (
                "synthetic_signature_fixture"
                if envelope.source_class
                == AdoptionAttestationSourceClass.SYNTHETIC_FIXTURE
                else "synthetic_negative_external_shape"
            ),
            "controlled_adoption_case": model_payload(external_case(root)),
            "expected_scope": model_payload(scope),
            "envelope": model_payload(envelope),
            "receipt": model_payload(receipt),
            "expected": {
                "state": receipt.state.value,
                "real_adopter_evidence_accepted": False,
                "observation_execution_completed": False,
            },
        }
    return result


def asset_outputs(root: Path) -> dict[Path, str]:
    schema_dir = root / "platform" / "schemas" / "cbb"
    fixture_dir = root / FIXTURE_ROOT
    outputs = {
        schema_dir
        / "cbb.external-adoption-attestation-envelope.v1.schema.json": schema_text(
            ExternalAdoptionAttestationEnvelopeV1
        ),
        schema_dir
        / "cbb.external-adoption-attestation-receipt.v1.schema.json": schema_text(
            ExternalAdoptionAttestationReceiptV1
        ),
    }
    outputs.update(
        {
            fixture_dir / f"{case_id}.json": json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
            for case_id, payload in build_adoption_attestation_cases(root).items()
        }
    )
    return outputs
