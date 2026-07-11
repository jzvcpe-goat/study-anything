"""Deterministic controlled-adoption fixtures bound to the Protocol v1 release."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from study_anything.cbb.adoption.evaluator import evaluate_controlled_adoption
from study_anything.cbb.adoption.models import (
    AdoptionBindingV1,
    AdoptionEffectBoundaryV1,
    AdoptionEvidenceClass,
    AdoptionMode,
    AdoptionObservationKind,
    ControlledAdoptionCaseV1,
    ControlledAdoptionReceiptV1,
)
from study_anything.cbb.outcomes.evaluator import evaluate_delivery_outcome
from study_anything.cbb.outcomes.fixtures import (
    EXPIRES_AT,
    ISSUED_AT,
    build_outcome_cases,
    fixture_private_key,
)
from study_anything.cbb.protocol.canonical import model_payload, schema_text
from study_anything.cbb.protocol.models import (
    DeliveryOutcomeReceiptV1,
    DeliveryScope,
    OutcomeEventV1,
    PostDeliverySamplingV1,
    PrivacyBoundaryV1,
    RollbackOutcomeV1,
)
from study_anything.cbb.provenance.fixtures import signed_package


FIXTURE_ROOT = Path("fixtures") / "cbb-controlled-adoption"
RELEASE_SCOPE_COMMIT = "1ada8ffa6318b91e38ec69bc5cd14dc294950518"
OBSERVED_AT = "2026-07-12T00:00:00Z"


def _conformance_digest(root: Path) -> str:
    summary_path = (
        root
        / "platform"
        / "generated"
        / "study-anything-cbb-v1-conformance-pack.json"
    )
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return str(payload["archive_sha256"])


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


def _binding(root: Path) -> AdoptionBindingV1:
    package = signed_package()
    return AdoptionBindingV1(
        release_scope_commit=RELEASE_SCOPE_COMMIT,
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
    )


def _rollback_succeeded_outcome() -> DeliveryOutcomeReceiptV1:
    package = signed_package()
    source = build_outcome_cases()["near-miss-narrows-scope"]["inputs"]
    rollback = RollbackOutcomeV1(
        required=True,
        attempted=True,
        status="succeeded",
        evidence_refs=["rollback-evidence:controlled-adoption:succeeded"],
    )
    return evaluate_delivery_outcome(
        package,
        sampling=PostDeliverySamplingV1.model_validate(source["sampling"]),
        events=[OutcomeEventV1.model_validate(item) for item in source["events"]],
        rollback=rollback,
        recipe_ref="trust-recipe:controlled-adoption",
        issued_at=ISSUED_AT,
        private_key=fixture_private_key(),
        signer_id="fixture-local-outcome-signer",
        key_id="fixture-outcome-ed25519-key-1",
        expires_at=EXPIRES_AT,
        replay_nonce="outcome-replay-nonce:controlled-adoption-rollback",
    )


def _outcomes() -> dict[str, DeliveryOutcomeReceiptV1]:
    cases = build_outcome_cases()
    return {
        "monitored": DeliveryOutcomeReceiptV1.model_validate(
            cases["monitored-no-adverse-signal"]["receipt"]
        ),
        "incident": DeliveryOutcomeReceiptV1.model_validate(
            cases["affected-party-challenge-freezes"]["receipt"]
        ),
        "rollback": _rollback_succeeded_outcome(),
        "revocation": DeliveryOutcomeReceiptV1.model_validate(
            cases["claim-violation-revokes"]["receipt"]
        ),
    }


def _case(
    root: Path,
    case_id: str,
    *,
    mode: AdoptionMode,
    kind: AdoptionObservationKind,
    requested_scope: DeliveryScope,
    outcome: DeliveryOutcomeReceiptV1 | None,
    source_revoked: bool = False,
    reopen_requested: bool = False,
    real_user_exposure: bool = False,
) -> ControlledAdoptionCaseV1:
    return ControlledAdoptionCaseV1(
        schema_version="cbb.controlled-adoption-case.v1",
        case_id=case_id,
        evidence_class=AdoptionEvidenceClass.SYNTHETIC_FIXTURE,
        adoption_mode=mode,
        observation_kind=kind,
        binding=_binding(root),
        effect_boundary=AdoptionEffectBoundaryV1(
            requested_scope=requested_scope,
            real_user_exposure_observed=real_user_exposure,
            external_effect_observed=(
                outcome is not None
                and any(event.external_effect_observed for event in outcome.events)
            ),
            production_mutation_performed=False,
            automatic_customer_send_performed=False,
        ),
        operator_reconstruction_present=True,
        risk_owner_reacceptance_present=False,
        source_revoked_before_observation=source_revoked,
        reopen_requested=reopen_requested,
        real_adopter_evidence_claimed=False,
        outcome_receipt=outcome,
        observed_at=OBSERVED_AT,
        privacy=_privacy(),
    )


def build_adoption_cases(root: Path) -> dict[str, dict[str, Any]]:
    outcomes = _outcomes()
    cases = {
        "shadow-pass": _case(
            root,
            "shadow-pass",
            mode=AdoptionMode.SHADOW,
            kind=AdoptionObservationKind.PASS,
            requested_scope=DeliveryScope.SANDBOX_ONLY,
            outcome=outcomes["monitored"],
        ),
        "dogfood-pass": _case(
            root,
            "dogfood-pass",
            mode=AdoptionMode.DOGFOOD,
            kind=AdoptionObservationKind.PASS,
            requested_scope=DeliveryScope.INTERNAL_HANDOFF,
            outcome=outcomes["monitored"],
        ),
        "canary-scope-expansion-blocked": _case(
            root,
            "canary-scope-expansion-blocked",
            mode=AdoptionMode.CANARY,
            kind=AdoptionObservationKind.BLOCK,
            requested_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
            outcome=outcomes["monitored"],
            real_user_exposure=True,
        ),
        "incident-freezes": _case(
            root,
            "incident-freezes",
            mode=AdoptionMode.DOGFOOD,
            kind=AdoptionObservationKind.INCIDENT,
            requested_scope=DeliveryScope.INTERNAL_HANDOFF,
            outcome=outcomes["incident"],
        ),
        "rollback-narrows": _case(
            root,
            "rollback-narrows",
            mode=AdoptionMode.DOGFOOD,
            kind=AdoptionObservationKind.ROLLBACK,
            requested_scope=DeliveryScope.INTERNAL_HANDOFF,
            outcome=outcomes["rollback"],
        ),
        "claim-violation-revokes": _case(
            root,
            "claim-violation-revokes",
            mode=AdoptionMode.DOGFOOD,
            kind=AdoptionObservationKind.REVOCATION,
            requested_scope=DeliveryScope.INTERNAL_HANDOFF,
            outcome=outcomes["revocation"],
        ),
        "reopen-requires-fresh-clearance": _case(
            root,
            "reopen-requires-fresh-clearance",
            mode=AdoptionMode.DOGFOOD,
            kind=AdoptionObservationKind.REOPEN,
            requested_scope=DeliveryScope.INTERNAL_HANDOFF,
            outcome=outcomes["revocation"],
            source_revoked=True,
            reopen_requested=True,
        ),
    }
    result: dict[str, dict[str, Any]] = {}
    conformance_digest = _conformance_digest(root)
    package = signed_package()
    for case_id, case in cases.items():
        receipt = evaluate_controlled_adoption(
            package,
            case,
            expected_release_scope_commit=RELEASE_SCOPE_COMMIT,
            expected_conformance_pack_sha256=conformance_digest,
            revoked_source_handles=(
                {case.binding.source_clearance_revocation_handle}
                if case.source_revoked_before_observation
                else set()
            ),
        )
        result[case_id] = {
            "case_id": case_id,
            "case": model_payload(case),
            "receipt": model_payload(receipt),
            "expected": {
                "status": receipt.status.value,
                "resulting_scope": receipt.resulting_scope.value,
                "authorization_delta": receipt.authorization_delta,
                "real_adopter_evidence": False,
            },
        }
    return result


def asset_outputs(root: Path) -> dict[Path, str]:
    schema_dir = root / "platform" / "schemas" / "cbb"
    fixture_dir = root / FIXTURE_ROOT
    outputs = {
        schema_dir / "cbb.controlled-adoption-case.v1.schema.json": schema_text(
            ControlledAdoptionCaseV1
        ),
        schema_dir / "cbb.controlled-adoption-receipt.v1.schema.json": schema_text(
            ControlledAdoptionReceiptV1
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
            for case_id, payload in build_adoption_cases(root).items()
        }
    )
    return outputs
