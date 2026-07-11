#!/usr/bin/env python3
"""Verify post-delivery receipts, trust degradation, and local revocation effects."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.outcomes.evaluator import (  # noqa: E402
    OutcomeEvaluationError,
    evaluate_delivery_outcome,
    revocation_registry_updates,
)
from study_anything.cbb.outcomes.fixtures import (  # noqa: E402
    EXPIRES_AT,
    ISSUED_AT,
    build_outcome_cases,
    fixture_private_key,
)
from study_anything.cbb.outcomes.signing import (  # noqa: E402
    sign_outcome_envelope,
    verify_outcome_receipt,
    verify_outcome_source_binding,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    CanonicalProtocolError,
    assert_safe_metadata,
    model_payload,
)
from study_anything.cbb.protocol.models import (  # noqa: E402
    DeliveryOutcomeReceiptV1,
    DeliveryScope,
    OutcomeEventV1,
    PostDeliverySamplingV1,
    RollbackOutcomeV1,
    scope_is_at_most,
)
from study_anything.cbb.provenance.fixtures import (  # noqa: E402
    signed_package,
    unsigned_package,
)
from study_anything.cbb.provenance.signing import verify_offline_package  # noqa: E402


REPORT_SCHEMA_VERSION = "cbb-v1-outcome-verification-v1"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-v1-outcomes.json"


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _rejected(fn: Callable[[], object], expected: str) -> bool:
    try:
        fn()
    except (CanonicalProtocolError, OutcomeEvaluationError, ValueError) as exc:
        return expected in str(exc)
    return False


def _rebuild(case: dict[str, Any]) -> DeliveryOutcomeReceiptV1:
    inputs = case["inputs"]
    return evaluate_delivery_outcome(
        signed_package(),
        sampling=PostDeliverySamplingV1.model_validate(inputs["sampling"]),
        events=[OutcomeEventV1.model_validate(item) for item in inputs["events"]],
        rollback=RollbackOutcomeV1.model_validate(inputs["rollback"]),
        recipe_ref=inputs["recipe_ref"],
        issued_at=inputs["issued_at"],
        private_key=fixture_private_key(),
        signer_id="fixture-local-outcome-signer",
        key_id="fixture-outcome-ed25519-key-1",
        expires_at=EXPIRES_AT,
        replay_nonce=f"outcome-replay-nonce:{case['case_id']}",
    )


def build_report() -> dict[str, Any]:
    cases = build_outcome_cases()
    results: list[dict[str, Any]] = []
    for case_id in sorted(cases):
        case = cases[case_id]
        receipt = DeliveryOutcomeReceiptV1.model_validate(case["receipt"])
        rebuilt = _rebuild(case)
        if rebuilt != receipt:
            raise RuntimeError(f"{case_id}: deterministic outcome receipt drifted")
        if verify_outcome_source_binding(signed_package(), receipt):
            raise RuntimeError(f"{case_id}: source clearance binding drifted")
        outcome_verification = verify_outcome_receipt(
            signed_package(),
            receipt,
            now=ISSUED_AT,
        )
        if not outcome_verification.passed:
            raise RuntimeError(
                f"{case_id}: outcome signature failed: {outcome_verification.reasons}"
            )
        expected = case["expected"]
        actual = {
            "status": receipt.status,
            "action": receipt.trust_update.action.value,
            "resulting_scope": receipt.trust_update.resulting_scope.value,
            "source_clearance_revoked": (receipt.trust_update.source_clearance_revoked),
            "recipe_state": receipt.trust_update.recipe_state,
        }
        if actual != expected:
            raise RuntimeError(f"{case_id}: expected {expected}, got {actual}")
        if not scope_is_at_most(
            receipt.trust_update.resulting_scope,
            receipt.source_approved_scope,
        ):
            raise RuntimeError(f"{case_id}: outcome increased source scope")
        results.append({"case_id": case_id, **actual})

    package = signed_package()
    source_handle = package.receipt_provenance.revocation.handle
    sample_case = cases["monitored-no-adverse-signal"]["inputs"]
    revoked_source_rejected = _rejected(
        lambda: evaluate_delivery_outcome(
            package,
            sampling=PostDeliverySamplingV1.model_validate(sample_case["sampling"]),
            events=[OutcomeEventV1.model_validate(item) for item in sample_case["events"]],
            rollback=RollbackOutcomeV1.model_validate(sample_case["rollback"]),
            recipe_ref=sample_case["recipe_ref"],
            issued_at=sample_case["issued_at"],
            private_key=fixture_private_key(),
            signer_id="fixture-local-outcome-signer",
            key_id="fixture-outcome-ed25519-key-1",
            expires_at=EXPIRES_AT,
            replay_nonce="outcome-replay-nonce:revoked-source",
            revoked_handles=[source_handle],
        ),
        "not_revoked",
    )
    unsigned_source_rejected = _rejected(
        lambda: evaluate_delivery_outcome(
            unsigned_package(),
            sampling=PostDeliverySamplingV1.model_validate(sample_case["sampling"]),
            events=[OutcomeEventV1.model_validate(item) for item in sample_case["events"]],
            rollback=RollbackOutcomeV1.model_validate(sample_case["rollback"]),
            recipe_ref=sample_case["recipe_ref"],
            issued_at=sample_case["issued_at"],
            private_key=fixture_private_key(),
            signer_id="fixture-local-outcome-signer",
            key_id="fixture-outcome-ed25519-key-1",
            expires_at=EXPIRES_AT,
            replay_nonce="outcome-replay-nonce:unsigned-source",
        ),
        "locally_signed",
    )

    revoked_receipt = DeliveryOutcomeReceiptV1.model_validate(
        cases["claim-violation-revokes"]["receipt"]
    )
    revocation_updates = revocation_registry_updates(
        revoked_receipt,
        package,
        now=ISSUED_AT,
    )
    revoked_verification = verify_offline_package(
        package,
        now=ISSUED_AT,
        revoked_handles=revocation_updates,
    )
    revocation_blocks_original = (
        revoked_verification.status == "fail" and "not_revoked" in revoked_verification.reasons
    )

    inflated = deepcopy(cases["monitored-no-adverse-signal"]["receipt"])
    inflated["trust_update"]["resulting_scope"] = "production_candidate"
    inflated["claim_boundary"]["maximum_scope"] = "production_candidate"
    scope_increase_rejected = _rejected(
        lambda: DeliveryOutcomeReceiptV1.model_validate(inflated),
        "cannot increase",
    )

    pass_count = deepcopy(cases["monitored-no-adverse-signal"]["receipt"])
    pass_count["trust_update"]["accumulated_pass_count"] = 500
    pass_count_inflation_rejected = _rejected(
        lambda: DeliveryOutcomeReceiptV1.model_validate(pass_count),
        "Extra inputs are not permitted",
    )

    affected = deepcopy(cases["affected-party-challenge-freezes"]["receipt"])
    affected["trust_update"]["affected_party_follow_up_required"] = False
    affected_party_bypass_rejected = _rejected(
        lambda: DeliveryOutcomeReceiptV1.model_validate(affected),
        "affected-party challenge requires follow-up",
    )

    failed_rollback = deepcopy(cases["failed-rollback-revokes"]["receipt"])
    failed_rollback["status"] = "frozen"
    failed_rollback["trust_update"].update(
        {
            "action": "freeze_recipe",
            "recipe_state": "frozen",
            "source_clearance_revoked": False,
            "revoked_clearance_handles": [],
        }
    )
    failed_rollback_bypass_rejected = _rejected(
        lambda: DeliveryOutcomeReceiptV1.model_validate(failed_rollback),
        "failed rollback must revoke",
    )

    source_tamper = deepcopy(cases["monitored-no-adverse-signal"]["receipt"])
    source_tamper["source_delivery_receipt_digest_sha256"] = "0" * 64
    tampered_receipt = DeliveryOutcomeReceiptV1.model_validate(source_tamper)
    source_binding_tamper_detected = verify_outcome_source_binding(
        package,
        tampered_receipt,
    ) == ("source_delivery_receipt_digest_sha256",)
    outcome_signature_tamper_detected = (
        verify_outcome_receipt(package, tampered_receipt, now=ISSUED_AT).status == "fail"
    )

    revoked_outcome_verification = verify_outcome_receipt(
        package,
        revoked_receipt,
        now=ISSUED_AT,
        revoked_outcome_handles=[revoked_receipt.outcome_provenance.revocation.handle],
    )
    outcome_receipt_revocation_enforced = (
        revoked_outcome_verification.status == "fail"
        and "not_revoked" in revoked_outcome_verification.reasons
    )

    secret_like_metadata_rejected = _rejected(
        lambda: assert_safe_metadata(
            {
                **model_payload(revoked_receipt),
                "api_key": "sk-0123456789abcdefghijkl",
            }
        ),
        "forbidden field",
    )

    near_miss_inputs = cases["near-miss-narrows-scope"]["inputs"]
    resolved_event_payload = deepcopy(near_miss_inputs["events"][0])
    resolved_event_payload["status"] = "resolved"
    resolved_event_payload["resolution_refs"] = ["resolution:near-miss-corrected"]
    resolved_receipt = evaluate_delivery_outcome(
        package,
        sampling=PostDeliverySamplingV1.model_validate(near_miss_inputs["sampling"]),
        events=[OutcomeEventV1.model_validate(resolved_event_payload)],
        rollback=RollbackOutcomeV1.model_validate(near_miss_inputs["rollback"]),
        recipe_ref=near_miss_inputs["recipe_ref"],
        issued_at=ISSUED_AT,
        private_key=fixture_private_key(),
        signer_id="fixture-local-outcome-signer",
        key_id="fixture-outcome-ed25519-key-1",
        expires_at=EXPIRES_AT,
        replay_nonce="outcome-replay-nonce:resolved-adverse-check",
    )
    resolved_adverse_not_clean = (
        resolved_receipt.status == "degraded"
        and resolved_receipt.trust_update.action.value == "narrow_scope"
    )

    late_issued_at = "2026-09-28T00:00:00Z"
    late_receipt = evaluate_delivery_outcome(
        package,
        sampling=PostDeliverySamplingV1.model_validate(near_miss_inputs["sampling"]),
        events=[OutcomeEventV1.model_validate(item) for item in near_miss_inputs["events"]],
        rollback=RollbackOutcomeV1.model_validate(near_miss_inputs["rollback"]),
        recipe_ref=near_miss_inputs["recipe_ref"],
        issued_at=late_issued_at,
        private_key=fixture_private_key(),
        signer_id="fixture-local-outcome-signer",
        key_id="fixture-outcome-ed25519-key-1",
        expires_at="2026-10-28T00:00:00Z",
        replay_nonce="outcome-replay-nonce:expired-source-history-check",
    )
    expired_source_history_recordable = (
        "not_expired" in verify_offline_package(package, now=late_issued_at).reasons
        and late_receipt.source_verification.clearance_valid_at
        == package.receipt_provenance.created_at
        and verify_outcome_receipt(package, late_receipt, now=late_issued_at).passed
    )

    under_degradation = deepcopy(cases["near-miss-narrows-scope"]["receipt"])
    original_outcome_provenance = under_degradation.pop("outcome_provenance")
    under_degradation["trust_update"]["policy_reconstruction_required"] = False
    forged_provenance = sign_outcome_envelope(
        under_degradation,
        source_package_digest_sha256=package.receipt_provenance.package_digest_sha256,
        private_key=fixture_private_key(),
        signer_id="fixture-local-outcome-signer",
        key_id="fixture-outcome-ed25519-key-1",
        created_at=under_degradation["issued_at"],
        expires_at=original_outcome_provenance["expires_at"],
        replay_nonce="outcome-replay-nonce:under-degradation-check",
        outcome_receipt_id=under_degradation["outcome_receipt_id"],
        maximum_scope=DeliveryScope.SANDBOX_ONLY,
    )
    forged_receipt = DeliveryOutcomeReceiptV1.model_validate(
        {
            **under_degradation,
            "outcome_provenance": forged_provenance.model_dump(mode="json"),
        }
    )
    forged_verification = verify_outcome_receipt(package, forged_receipt, now=ISSUED_AT)
    deterministic_replay_enforced = (
        forged_verification.status == "fail"
        and "deterministic_trust_update" in forged_verification.reasons
    )

    checks = {
        "revoked_source_rejected": revoked_source_rejected,
        "unsigned_source_rejected": unsigned_source_rejected,
        "revocation_blocks_original_clearance": revocation_blocks_original,
        "scope_increase_rejected": scope_increase_rejected,
        "pass_count_inflation_rejected": pass_count_inflation_rejected,
        "affected_party_bypass_rejected": affected_party_bypass_rejected,
        "failed_rollback_bypass_rejected": failed_rollback_bypass_rejected,
        "source_binding_tamper_detected": source_binding_tamper_detected,
        "outcome_signature_tamper_detected": outcome_signature_tamper_detected,
        "outcome_receipt_revocation_enforced": outcome_receipt_revocation_enforced,
        "secret_like_metadata_rejected": secret_like_metadata_rejected,
        "resolved_adverse_not_clean": resolved_adverse_not_clean,
        "expired_source_history_recordable": expired_source_history_recordable,
        "deterministic_replay_enforced": deterministic_replay_enforced,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"CBB v1 outcome checks failed: {failed}")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "case_count": len(results),
        "cases": results,
        "checks": checks,
        "invariants": [
            "post-delivery evidence can maintain, narrow, freeze, or revoke trust",
            "post-delivery evidence can never increase the source clearance scope",
            "failed rollback and substantiated claim violations revoke source clearance",
            "resolved adverse events cannot restore the previous clearance ceiling",
            "verification replays the deterministic trust action instead of trusting a signature",
            "expired source clearance can be referenced historically but cannot regain authority",
            "open affected-party challenges freeze delivery and require follow-up",
            "elapsed time and accumulated pass count never increase trust",
            "revocation handles make the original signed package fail offline verification",
            "outcome receipts are locally signed and independently revocable",
        ],
        "claim_boundary": (
            "This verifies deterministic metadata-only outcome and local trust-degradation "
            "semantics. It does not prove customer success, global revocation, production "
            "safety, legal compliance, third-party signer identity, or independent audit "
            "completion."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_customer_payload_included": False,
            "personal_identity_included": False,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "production_mutation_performed": False,
            "automatic_policy_mutation_performed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")
    output = Path(args.output)
    serialized = _json_text(build_report())
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    elif not output.is_file() or output.read_text(encoding="utf-8") != serialized:
        raise SystemExit(
            "CBB v1 outcome report is stale; run python3 scripts/verify_cbb_v1_outcomes.py --write"
        )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
