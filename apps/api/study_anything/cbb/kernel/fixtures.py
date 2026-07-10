"""Deterministic inputs and expected decisions for the CBB v1 kernel."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from study_anything.cbb.kernel.gate import evaluate_gate
from study_anything.cbb.protocol.canonical import model_payload
from study_anything.cbb.protocol.models import (
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION,
    TRUST_POLICY_SCHEMA_VERSION,
    ClaimBoundaryV1,
    DeliveryScope,
    EvidenceBundleV1,
    EvidenceItemV1,
    EvidenceRequirementV1,
    PrivacyBoundaryV1,
    QualifiedReconstructionV1,
    RiskBudgetV1,
    TrustPolicyV1,
)


FIXTURE_ROOT = Path("fixtures") / "cbb-v1-kernel"


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


def _claim(scope: DeliveryScope, text: str) -> ClaimBoundaryV1:
    return ClaimBoundaryV1(
        current_claim=text,
        maximum_scope=scope,
        not_claimed=[
            "production approval",
            "portable signed attestation",
            "customer outcome guarantee",
        ],
    )


def passing_inputs() -> tuple[TrustPolicyV1, EvidenceBundleV1, QualifiedReconstructionV1]:
    policy = TrustPolicyV1(
        schema_version=TRUST_POLICY_SCHEMA_VERSION,
        policy_id="cbb-policy:kernel-demo-001",
        subject_ref="artifact:kernel-demo-001",
        scenario_ref="scenario:controlled-customer-handoff",
        maximum_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
        hard_denies=[
            "ai_review_only_trust",
            "irreversible_external_effect",
            "production_mutation",
            "unbounded_real_user_exposure",
        ],
        risk_budget=RiskBudgetV1(
            level="medium",
            production_mutation_allowed=False,
            real_user_exposure_allowed=False,
            irreversible_external_effects_allowed=False,
        ),
        required_evidence=[
            EvidenceRequirementV1(
                evidence_type="failure_contract",
                required_for_scope=DeliveryScope.SANDBOX_ONLY,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="sandbox_receipt",
                required_for_scope=DeliveryScope.SANDBOX_ONLY,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="qualified_reconstruction",
                required_for_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="dual_loop_gate",
                required_for_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
                blocking=True,
            ),
        ],
        required_roles=["qualified_reviewer"],
        claim_boundary=_claim(
            DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
            "This policy evaluates a controlled customer handoff candidate only.",
        ),
        privacy=_privacy(),
        created_at="2026-06-28T00:00:00Z",
    )
    evidence = EvidenceBundleV1(
        schema_version=EVIDENCE_BUNDLE_SCHEMA_VERSION,
        bundle_id="cbb-evidence:kernel-demo-001",
        subject_ref=policy.subject_ref,
        policy_ref=policy.policy_id,
        evidence=[
            EvidenceItemV1(
                evidence_id="evidence:failure-contract-001",
                evidence_type="failure_contract",
                status="passed",
                source_schema_version="failure-contract-v1",
                source_ref="failure-contract.json",
                supported_scope=DeliveryScope.SANDBOX_ONLY,
                metadata={"metadata_only": True},
            ),
            EvidenceItemV1(
                evidence_id="evidence:sandbox-receipt-001",
                evidence_type="sandbox_receipt",
                status="passed",
                source_schema_version="sandbox-receipt-v1",
                source_ref="sandbox-receipt.json",
                supported_scope=DeliveryScope.SANDBOX_ONLY,
                metadata={"contained": True, "rollback_rehearsed": True},
            ),
            EvidenceItemV1(
                evidence_id="evidence:dual-loop-gate-001",
                evidence_type="dual_loop_gate",
                status="passed",
                source_schema_version="dual-loop-gate-receipt-v1",
                source_ref="dual-loop-gate-receipt.json",
                supported_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
                metadata={"both_loops_required": True},
            ),
        ],
        maximum_supported_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
        claim_boundary=_claim(
            DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
            "The evidence bundle supports controlled customer handoff only.",
        ),
        privacy=_privacy(),
        created_at="2026-06-28T00:00:00Z",
    )
    reconstruction = QualifiedReconstructionV1(
        schema_version=QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION,
        reconstruction_id="cbb-reconstruction:kernel-demo-001",
        policy_ref=policy.policy_id,
        reviewer_ref="reviewer:kernel-fixture",
        status="passed",
        qualified_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
        active_reconstruction=True,
        passive_attention_only=False,
        required_mrus_total=2,
        required_mrus_passed=2,
        missing_mru_refs=[],
        evidence_refs=["attention-reconstruction-summary.json"],
        observed_at="2026-06-28T00:00:00Z",
        valid_until="2026-09-26T00:00:00Z",
        claim_boundary=_claim(
            DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
            "The reviewer reconstructed the required boundary for this scope.",
        ),
        privacy=_privacy(),
    )
    return policy, evidence, reconstruction


def _validated_inputs(
    policy: dict[str, Any],
    evidence_bundle: dict[str, Any],
    qualified_reconstruction: dict[str, Any],
) -> tuple[TrustPolicyV1, EvidenceBundleV1, QualifiedReconstructionV1]:
    return (
        TrustPolicyV1.model_validate(policy),
        EvidenceBundleV1.model_validate(evidence_bundle),
        QualifiedReconstructionV1.model_validate(qualified_reconstruction),
    )


def build_kernel_cases() -> dict[str, dict[str, Any]]:
    base_policy, base_evidence, base_reconstruction = passing_inputs()
    base = {
        "policy": model_payload(base_policy),
        "evidence_bundle": model_payload(base_evidence),
        "qualified_reconstruction": model_payload(base_reconstruction),
    }
    payloads: dict[str, dict[str, Any]] = {"pass": deepcopy(base)}

    missing = deepcopy(base)
    missing["evidence_bundle"]["evidence"] = [
        item
        for item in missing["evidence_bundle"]["evidence"]
        if item["evidence_type"] != "dual_loop_gate"
    ]
    payloads["missing-evidence"] = missing

    failed = deepcopy(base)
    for item in failed["evidence_bundle"]["evidence"]:
        if item["evidence_type"] == "sandbox_receipt":
            item.update({"status": "failed", "supported_scope": "blocked"})
    payloads["failed-evidence"] = failed

    stale = deepcopy(base)
    stale["qualified_reconstruction"].update(
        {
            "status": "stale",
            "qualified_scope": "blocked",
            "active_reconstruction": False,
            "required_mrus_passed": 0,
            "missing_mru_refs": ["mru:rollback-boundary"],
            "valid_until": "2026-06-27T00:00:00Z",
        }
    )
    stale["qualified_reconstruction"]["claim_boundary"].update(
        {"maximum_scope": "blocked", "current_claim": "The reconstruction is stale."}
    )
    payloads["stale-reconstruction"] = stale

    hard_deny = deepcopy(base)
    hard_deny["evidence_bundle"]["evidence"].append(
        {
            "evidence_id": "evidence:hard-deny-production-mutation",
            "evidence_type": "hard_deny:production_mutation",
            "status": "passed",
            "source_schema_version": "cbb.hard-deny-signal.v1",
            "source_ref": "hard-deny-signal.json",
            "supported_scope": "blocked",
            "metadata": {"observed": True},
        }
    )
    payloads["hard-deny"] = hard_deny

    mismatch = deepcopy(base)
    mismatch["evidence_bundle"]["policy_ref"] = "cbb-policy:different"
    payloads["reference-mismatch"] = mismatch

    narrow = deepcopy(base)
    narrow["policy"]["claim_boundary"].update(
        {
            "maximum_scope": "internal_handoff",
            "current_claim": "This policy is intentionally limited to internal handoff.",
        }
    )
    for requirement in narrow["policy"]["required_evidence"]:
        if requirement["required_for_scope"] == "controlled_customer_handoff":
            requirement["required_for_scope"] = "internal_handoff"
    payloads["claim-boundary-narrowing"] = narrow

    output: dict[str, dict[str, Any]] = {}
    for case_id, inputs in payloads.items():
        policy, evidence, reconstruction = _validated_inputs(**inputs)
        decision = evaluate_gate(policy, evidence, reconstruction)
        output[case_id] = {
            "case_id": case_id,
            "inputs": inputs,
            "decision": model_payload(decision),
        }
    return output


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
        for case_id, payload in build_kernel_cases().items()
    }
