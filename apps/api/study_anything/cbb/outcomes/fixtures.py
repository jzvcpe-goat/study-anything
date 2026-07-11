"""Deterministic post-delivery outcome and trust-degradation fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from study_anything.cbb.outcomes.evaluator import evaluate_delivery_outcome
from study_anything.cbb.protocol.canonical import model_payload
from study_anything.cbb.protocol.models import (
    OutcomeEventType,
    OutcomeEventV1,
    OutcomeSeverity,
    PostDeliverySamplingV1,
    RollbackOutcomeV1,
)
from study_anything.cbb.provenance.fixtures import signed_package


FIXTURE_ROOT = Path("fixtures") / "cbb-v1-outcomes"
WINDOW_STARTED_AT = "2026-07-01T00:00:00Z"
WINDOW_ENDED_AT = "2026-07-10T00:00:00Z"
ISSUED_AT = "2026-07-11T00:00:00Z"
EXPIRES_AT = "2026-08-10T00:00:00Z"


def fixture_private_key() -> Any:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"cbb-v1-public-outcome-fixture-key").digest()
    )


def _sampling(case_id: str, *, complete: bool) -> PostDeliverySamplingV1:
    return PostDeliverySamplingV1(
        sampling_id=f"outcome-sampling:{case_id}",
        strategy="all_observed" if complete else "bounded_sample",
        window_started_at=WINDOW_STARTED_AT,
        window_ended_at=WINDOW_ENDED_AT,
        eligible_count=4 if complete else 25,
        sampled_count=4 if complete else 5,
        selection_ref=f"sampling-plan:{case_id}",
        coverage_complete=complete,
        limitations=[] if complete else ["bounded sample does not cover every delivery"],
    )


def _event(
    case_id: str,
    *,
    event_type: OutcomeEventType,
    severity: OutcomeSeverity,
    status: Literal["reported", "confirmed", "resolved", "disputed"],
    affected_party: bool = False,
    external_effect: bool = False,
    claim_violation: bool = False,
) -> OutcomeEventV1:
    return OutcomeEventV1(
        event_id=f"outcome-event:{case_id}",
        event_type=event_type,
        severity=severity,
        status=status,
        source_refs=[f"outcome-evidence:{case_id}"],
        affected_party_refs=([f"affected-party:{case_id}"] if affected_party else []),
        occurred_at="2026-07-08T12:00:00Z",
        external_effect_observed=external_effect,
        claim_boundary_violated=claim_violation,
        counter_evidence_refs=(
            [f"counter-evidence:{case_id}"]
            if event_type != OutcomeEventType.DELIVERY_OBSERVATION
            else []
        ),
        resolution_refs=[],
    )


def _rollback(
    *,
    required: bool = False,
    attempted: bool = False,
    status: Literal[
        "not_required",
        "not_attempted",
        "succeeded",
        "partial",
        "failed",
    ] = "not_required",
) -> RollbackOutcomeV1:
    return RollbackOutcomeV1(
        required=required,
        attempted=attempted,
        status=status,
        evidence_refs=([f"rollback-evidence:{status}"] if attempted else []),
    )


def _case(
    case_id: str,
    *,
    event: OutcomeEventV1,
    rollback: RollbackOutcomeV1,
    complete_sampling: bool,
) -> dict[str, Any]:
    package = signed_package()
    sampling = _sampling(case_id, complete=complete_sampling)
    receipt = evaluate_delivery_outcome(
        package,
        sampling=sampling,
        events=[event],
        rollback=rollback,
        recipe_ref="trust-recipe:metadata-only-demo",
        issued_at=ISSUED_AT,
        private_key=fixture_private_key(),
        signer_id="fixture-local-outcome-signer",
        key_id="fixture-outcome-ed25519-key-1",
        expires_at=EXPIRES_AT,
        replay_nonce=f"outcome-replay-nonce:{case_id}",
    )
    return {
        "case_id": case_id,
        "source": {
            "package_ref": package.package_id,
            "package_digest_sha256": package.receipt_provenance.package_digest_sha256,
            "delivery_receipt_ref": package.delivery_trust_receipt.receipt_id,
            "revocation_handle": package.receipt_provenance.revocation.handle,
        },
        "inputs": {
            "sampling": model_payload(sampling),
            "events": [model_payload(event)],
            "rollback": model_payload(rollback),
            "recipe_ref": "trust-recipe:metadata-only-demo",
            "issued_at": ISSUED_AT,
        },
        "receipt": model_payload(receipt),
        "expected": {
            "status": receipt.status,
            "action": receipt.trust_update.action.value,
            "resulting_scope": receipt.trust_update.resulting_scope.value,
            "source_clearance_revoked": (receipt.trust_update.source_clearance_revoked),
            "recipe_state": receipt.trust_update.recipe_state,
        },
    }


def build_outcome_cases() -> dict[str, dict[str, Any]]:
    return {
        "monitored-no-adverse-signal": _case(
            "monitored-no-adverse-signal",
            event=_event(
                "monitored-no-adverse-signal",
                event_type=OutcomeEventType.DELIVERY_OBSERVATION,
                severity=OutcomeSeverity.INFO,
                status="confirmed",
            ),
            rollback=_rollback(),
            complete_sampling=True,
        ),
        "near-miss-narrows-scope": _case(
            "near-miss-narrows-scope",
            event=_event(
                "near-miss-narrows-scope",
                event_type=OutcomeEventType.NEAR_MISS,
                severity=OutcomeSeverity.MEDIUM,
                status="confirmed",
            ),
            rollback=_rollback(),
            complete_sampling=False,
        ),
        "affected-party-challenge-freezes": _case(
            "affected-party-challenge-freezes",
            event=_event(
                "affected-party-challenge-freezes",
                event_type=OutcomeEventType.AFFECTED_PARTY_CHALLENGE,
                severity=OutcomeSeverity.MEDIUM,
                status="reported",
                affected_party=True,
            ),
            rollback=_rollback(),
            complete_sampling=False,
        ),
        "claim-violation-revokes": _case(
            "claim-violation-revokes",
            event=_event(
                "claim-violation-revokes",
                event_type=OutcomeEventType.CLAIM_VIOLATION,
                severity=OutcomeSeverity.HIGH,
                status="confirmed",
                affected_party=True,
                external_effect=True,
                claim_violation=True,
            ),
            rollback=_rollback(),
            complete_sampling=False,
        ),
        "failed-rollback-revokes": _case(
            "failed-rollback-revokes",
            event=_event(
                "failed-rollback-revokes",
                event_type=OutcomeEventType.INCIDENT,
                severity=OutcomeSeverity.MEDIUM,
                status="confirmed",
                external_effect=True,
            ),
            rollback=_rollback(required=True, attempted=True, status="failed"),
            complete_sampling=False,
        ),
    }


def fixture_outputs(root: Path) -> dict[Path, str]:
    fixture_dir = root / FIXTURE_ROOT
    return {
        fixture_dir / f"{case_id}.json": json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
        for case_id, payload in build_outcome_cases().items()
    }
