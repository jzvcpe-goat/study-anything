#!/usr/bin/env python3
"""Verify Agentic proposals cannot self-authorize policy or delivery changes."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.agentic.fixtures import (  # noqa: E402
    ISSUED_AT,
    PROPOSER_REF,
    SIGNER_REF,
    build_agentic_evolution_cases,
    fixture_private_key,
)
from study_anything.cbb.agentic.signing import (  # noqa: E402
    evolution_envelope_payload,
    sign_evolution_envelope,
    verify_evolution_receipt,
)
from study_anything.cbb.protocol.models import (  # noqa: E402
    PROTOCOL_MODELS,
    EvolutionDecisionStatus,
    EvolutionGateDecisionV1,
    EvolutionGateReceiptV1,
)


REPORT_SCHEMA_VERSION = "cbb-evolution-gate-verification-v1"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-evolution-gate.json"


def _rejected(fn: Callable[[], object], expected: str) -> bool:
    try:
        fn()
    except ValueError as exc:
        return expected in str(exc)
    return False


def _resign_with_decision(
    receipt: EvolutionGateReceiptV1,
    decision: EvolutionGateDecisionV1,
    *,
    signer_id: str = SIGNER_REF,
) -> EvolutionGateReceiptV1:
    envelope = evolution_envelope_payload(receipt)
    envelope["decision"] = decision.model_dump(mode="json")
    provenance = sign_evolution_envelope(
        envelope,
        decision,
        private_key=fixture_private_key(),
        signer_id=signer_id,
        key_id="fixture-agentic-evolution-key-1",
        created_at=receipt.issued_at,
        expires_at=receipt.provenance.expires_at,
        replay_nonce=receipt.provenance.replay_nonce,
        evolution_receipt_id=receipt.evolution_receipt_id,
    )
    return EvolutionGateReceiptV1.model_validate(
        {**envelope, "provenance": provenance.model_dump(mode="json")}
    )


def build_report() -> dict[str, Any]:
    cases = build_agentic_evolution_cases()
    results: list[dict[str, Any]] = []
    for case_id, case in sorted(cases.items()):
        receipt = EvolutionGateReceiptV1.model_validate(case["receipt"])
        verification = verify_evolution_receipt(receipt, now=ISSUED_AT)
        if not verification.passed:
            raise ValueError(f"fixture {case_id} failed verification: {verification.reasons}")
        actual_status = receipt.decision.status.value
        if actual_status != case["expected_status"]:
            raise ValueError(
                f"fixture {case_id} status drifted: {actual_status} != {case['expected_status']}"
            )
        results.append(
            {
                "case_id": case_id,
                "status": actual_status,
                "candidate_state": receipt.decision.candidate_state,
                "automatic_apply_performed": receipt.automatic_apply_performed,
            }
        )

    approved = EvolutionGateReceiptV1.model_validate(
        cases["approved-local-candidate"]["receipt"]
    )
    malicious_decision = EvolutionGateDecisionV1(
        status=EvolutionDecisionStatus.NEEDS_EVIDENCE,
        candidate_state="pending",
        proposal_digest_sha256=approved.decision.proposal_digest_sha256,
        reasons=["malicious:under_degraded"],
        automatic_apply_allowed=False,
        production_apply_allowed=False,
        trust_kernel_mutation_performed=False,
        release_performed=False,
        tool_or_memory_authority_used_as_final_basis=False,
        explicit_maintainer_apply_required=True,
    )
    under_degraded = _resign_with_decision(approved, malicious_decision)

    signature_tamper = deepcopy(approved.model_dump(mode="json"))
    signature = signature_tamper["provenance"]["signature"]
    signature_tamper["provenance"]["signature"] = (
        "A" if signature[0] != "A" else "B"
    ) + signature[1:]
    tampered_receipt = EvolutionGateReceiptV1.model_validate(signature_tamper)

    automatic_apply = deepcopy(approved.model_dump(mode="json"))
    automatic_apply["automatic_apply_performed"] = True

    checks = {
        "canonical_schema_registered": "cbb.evolution-gate-receipt.v1"
        in PROTOCOL_MODELS,
        "approved_stops_at_local_candidate": approved.decision.candidate_state
        == "local_candidate"
        and not approved.decision.automatic_apply_allowed
        and not approved.decision.production_apply_allowed
        and not approved.automatic_apply_performed,
        "hard_deny_change_blocked": cases["hard-deny-change-blocked"]["receipt"][
            "decision"
        ]["status"]
        == "block",
        "tool_authority_expansion_blocked": cases[
            "tool-authority-expansion-blocked"
        ]["receipt"]["decision"]["status"]
        == "block",
        "self_authorization_blocked": cases["self-authorization-blocked"]["receipt"][
            "decision"
        ]["status"]
        == "block",
        "poisoned_memory_not_usable": cases["poisoned-memory-needs-evidence"][
            "receipt"
        ]["decision"]["status"]
        == "needs_evidence",
        "missing_human_reconstruction_not_approved": cases[
            "missing-human-reconstruction"
        ]["receipt"]["decision"]["status"]
        == "needs_evidence",
        "valid_signature_cannot_override_replay": "deterministic_gate"
        in verify_evolution_receipt(under_degraded, now=ISSUED_AT).reasons,
        "signature_tamper_detected": "signature"
        in verify_evolution_receipt(tampered_receipt, now=ISSUED_AT).reasons,
        "local_revocation_enforced": "not_revoked"
        in verify_evolution_receipt(
            approved,
            now=ISSUED_AT,
            revoked_handles=[approved.provenance.revocation.handle],
        ).reasons,
        "proposer_cannot_sign_approved_candidate": _rejected(
            lambda: _resign_with_decision(
                approved,
                approved.decision,
                signer_id=PROPOSER_REF,
            ),
            "authorize its own",
        ),
        "automatic_apply_state_rejected": _rejected(
            lambda: EvolutionGateReceiptV1.model_validate(automatic_apply),
            "automatic_apply_performed",
        ),
        "receipt_grants_no_delivery_scope": (
            approved.claim_boundary.maximum_scope.value == "blocked"
            and approved.provenance.claim_boundary.maximum_scope.value == "blocked"
        ),
    }
    if not all(checks.values()):
        raise ValueError(
            "evolution gate verification failed: "
            + ", ".join(name for name, passed in checks.items() if not passed)
        )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "case_count": len(results),
        "cases": results,
        "checks": checks,
        "invariants": [
            "Agentic tool and memory output is supporting evidence only",
            "protected boundary changes fail closed",
            "the proposer cannot provide its own human authorization",
            "every approval requires replay, canary, rollback, reconstruction, risk owner, and maintainer controls",
            "a valid local signature cannot override deterministic evolution replay",
            "approved candidates are not automatically applied and grant no delivery scope",
        ],
        "claim_boundary": (
            "This verifies a local deterministic proposal gate and local signature. It does "
            "not apply policy, prove production safety, establish third-party identity, or "
            "complete an independent audit."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_patch_included": False,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "automatic_policy_application_performed": False,
            "production_mutation_performed": False,
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
    serialized = json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output = Path(args.output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    elif not output.is_file() or output.read_text(encoding="utf-8") != serialized:
        raise SystemExit(
            "evolution gate report is stale; run python3 "
            "scripts/verify_cbb_evolution_gate.py --write"
        )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
