"""Deterministic CBB Protocol v1 fixture builders."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from study_anything.cbb.protocol import compat_v0
from study_anything.cbb.protocol.canonical import model_payload
from study_anything.cbb.protocol.models import DeliveryScope
from study_anything.core import delivery_trust, dual_loop


FIXTURE_ROOT = Path("fixtures") / "cbb-v1-contracts"


def _v0_chain(
    *,
    attention_mode: str = "passed",
) -> tuple[dict[str, Any], dict[str, Any]]:
    failure_contract = dual_loop.failure_contract_demo()
    sandbox_receipt = dual_loop.sandbox_receipt_demo()
    attention_summary: dict[str, Any] | None
    if attention_mode == "missing":
        attention_summary = None
    else:
        attention_summary = dual_loop.attention_summary_demo(status="passed")
        if attention_mode == "stale":
            attention_summary["valid_until"] = "2026-06-27T00:00:00Z"
    gate_receipt = dual_loop.evaluate_dual_loop_gate(
        failure_contract,
        sandbox_receipt,
        attention_summary,
    )
    delivery_receipt = delivery_trust.build_delivery_trust_receipt(
        failure_contract,
        sandbox_receipt,
        gate_receipt,
        attention_summary,
    )
    canonical = compat_v0.map_v0_delivery_chain(
        failure_contract,
        sandbox_receipt,
        attention_summary,
        gate_receipt,
        delivery_receipt,
    )
    return (
        {
            "failure_contract": failure_contract,
            "sandbox_receipt": sandbox_receipt,
            "attention_summary": attention_summary,
            "dual_loop_gate": gate_receipt,
            "delivery_trust_receipt": delivery_receipt,
        },
        {key: model_payload(value) for key, value in canonical.items()},
    )


def _compatibility_case(case_id: str, attention_mode: str) -> dict[str, Any]:
    v0, canonical = _v0_chain(attention_mode=attention_mode)
    decision = canonical["gate_decision"]
    receipt = canonical["delivery_trust_receipt"]
    return {
        "case_id": case_id,
        "kind": "v0_compatibility",
        "v0": v0,
        "canonical": canonical,
        "expected": {
            "decision_status": decision["status"],
            "approved_scope": decision["approved_scope"],
            "receipt_status": receipt["status"],
            "scope_expansion_allowed": False,
        },
    }


def build_fixture_payloads() -> dict[str, dict[str, Any]]:
    pass_case = _compatibility_case("pass", "passed")
    missing_case = _compatibility_case("missing-evidence", "missing")
    stale_case = _compatibility_case("stale", "stale")

    hard_deny_payload = deepcopy(pass_case["canonical"]["gate_decision"])
    hard_deny_payload.update(
        {
            "status": "block",
            "approved_scope": DeliveryScope.BLOCKED.value,
            "reasons": ["hard_deny:production_mutation"],
            "hard_denies_triggered": ["production_mutation"],
            "missing_evidence_types": [],
        }
    )
    hard_deny_payload["claim_boundary"].update(
        {
            "current_claim": "The hard deny blocks every delivery scope.",
            "maximum_scope": DeliveryScope.BLOCKED.value,
        }
    )

    secret_payload = deepcopy(pass_case["canonical"]["trust_policy"])
    secret_payload["api_key"] = "fixture-redacted-value"

    malformed_payload = deepcopy(pass_case["canonical"]["trust_policy"])
    malformed_payload.pop("scenario_ref")
    malformed_payload["unexpected_authority"] = "limited_beta"

    naive_timestamp_payload = deepcopy(pass_case["canonical"]["trust_policy"])
    naive_timestamp_payload["created_at"] = "2026-06-28T00:00:00"

    invalid_state_payload = deepcopy(
        pass_case["canonical"]["qualified_reconstruction"]
    )
    invalid_state_payload["required_mrus_passed"] = (
        invalid_state_payload["required_mrus_total"] + 1
    )

    return {
        "pass.json": pass_case,
        "missing-evidence.json": missing_case,
        "hard-deny.json": {
            "case_id": "hard-deny",
            "kind": "canonical_valid",
            "model_schema_version": "cbb.gate-decision.v1",
            "payload": hard_deny_payload,
            "expected": {
                "status": "block",
                "approved_scope": "blocked",
                "hard_deny": "production_mutation",
            },
        },
        "stale.json": stale_case,
        "secret-like.json": {
            "case_id": "secret-like",
            "kind": "canonical_invalid",
            "model_schema_version": "cbb.trust-policy.v1",
            "payload": secret_payload,
            "expected_error": "forbidden field",
        },
        "malformed.json": {
            "case_id": "malformed",
            "kind": "canonical_invalid",
            "model_schema_version": "cbb.trust-policy.v1",
            "payload": malformed_payload,
            "expected_error": "validation error",
        },
        "naive-timestamp.json": {
            "case_id": "naive-timestamp",
            "kind": "canonical_invalid",
            "model_schema_version": "cbb.trust-policy.v1",
            "payload": naive_timestamp_payload,
            "expected_error": "String should match pattern",
        },
        "invalid-state.json": {
            "case_id": "invalid-state",
            "kind": "canonical_invalid",
            "model_schema_version": "cbb.qualified-reconstruction.v1",
            "payload": invalid_state_payload,
            "expected_error": "required MRUs passed cannot exceed required MRUs total",
        },
        "scope-expansion.json": {
            "case_id": "scope-expansion",
            "kind": "compatibility_invalid",
            "source_scope": "sandbox_only",
            "target_scope": "limited_beta",
            "expected_error": "scope expansion rejected",
        },
    }


def fixture_outputs(root: Path) -> dict[Path, str]:
    fixture_dir = root / FIXTURE_ROOT
    return {
        fixture_dir / name: json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
        for name, payload in build_fixture_payloads().items()
    }
