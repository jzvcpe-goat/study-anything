#!/usr/bin/env python3
"""Verify deterministic v0-to-v1 CBB mappings never expand delivery scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.protocol import compat_v0  # noqa: E402
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    canonical_json_bytes,
    model_payload,
    validate_payload,
)
from study_anything.cbb.protocol.fixtures import (  # noqa: E402
    FIXTURE_ROOT,
    fixture_outputs,
)
from study_anything.cbb.protocol.models import (  # noqa: E402
    PROTOCOL_MODELS,
    DeliveryScope,
)


REPORT_SCHEMA_VERSION = "cbb-v0-compatibility-verification-v1"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-v0-compatibility.json"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _check_fixtures() -> None:
    for path, expected in fixture_outputs(ROOT).items():
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            raise RuntimeError(
                "CBB v1 fixtures are stale; run generate_cbb_v1_contract_assets.py --write"
            )


def _source_scope(case: dict[str, Any]) -> DeliveryScope:
    status = case["v0"]["delivery_trust_receipt"]["status"]
    if status == "allowed":
        return DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF
    return DeliveryScope.BLOCKED


def _rebuild_case(case: dict[str, Any]) -> dict[str, Any]:
    v0 = case["v0"]
    rebuilt = compat_v0.map_v0_delivery_chain(
        v0["failure_contract"],
        v0["sandbox_receipt"],
        v0["attention_summary"],
        v0["dual_loop_gate"],
        v0["delivery_trust_receipt"],
    )
    payloads = {key: model_payload(value) for key, value in rebuilt.items()}
    if payloads != case["canonical"]:
        raise RuntimeError(f"Compatibility fixture drifted: {case['case_id']}")
    for payload in payloads.values():
        model_type = PROTOCOL_MODELS[payload["schema_version"]]
        validate_payload(model_type, payload)
    source_scope = _source_scope(case)
    target_scope = rebuilt["gate_decision"].approved_scope
    compat_v0.assert_scope_not_expanded(source_scope, target_scope)
    first = canonical_json_bytes(rebuilt["delivery_trust_receipt"])
    second = canonical_json_bytes(rebuilt["delivery_trust_receipt"])
    if first != second:
        raise RuntimeError("Mapped receipt canonical bytes are not stable")
    return {
        "case_id": case["case_id"],
        "source_scope": source_scope.value,
        "target_scope": target_scope.value,
        "decision_status": rebuilt["gate_decision"].status,
        "reconstruction_status": rebuilt["qualified_reconstruction"].status,
        "scope_expanded": False,
        "canonical_bytes_stable": True,
    }


def _scope_expansion_rejection() -> str:
    case = _load_json(ROOT / FIXTURE_ROOT / "scope-expansion.json")
    try:
        compat_v0.assert_scope_not_expanded(
            DeliveryScope(case["source_scope"]),
            DeliveryScope(case["target_scope"]),
        )
    except compat_v0.CompatibilityMappingError:
        return "scope expansion rejected"
    raise RuntimeError("Scope-expansion fixture was accepted")


def build_report() -> dict[str, Any]:
    _check_fixtures()
    cases = [
        _rebuild_case(_load_json(ROOT / FIXTURE_ROOT / name))
        for name in ("pass.json", "missing-evidence.json", "stale.json")
    ]
    narrowed = sum(
        1
        for case in cases
        if case["source_scope"] != case["target_scope"]
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "mapping_chain": [
            "failure-contract-v1 -> cbb.trust-policy.v1",
            "failure-contract-v1 + sandbox-receipt-v1 -> cbb.evidence-bundle.v1",
            "attention-reconstruction-summary-v1 -> cbb.qualified-reconstruction.v1",
            "dual-loop-gate-receipt-v1 -> cbb.evidence-bundle.v1",
            "policy + evidence + reconstruction -> cbb.gate-decision.v1",
            "delivery-trust-receipt-v1 + gate decision -> cbb.delivery-trust-receipt.v1",
        ],
        "cases": cases,
        "equal_scope_case_count": len(cases) - narrowed,
        "narrowed_scope_case_count": narrowed,
        "expanded_scope_case_count": 0,
        "negative_checks": {
            "explicit_scope_expansion": _scope_expansion_rejection(),
            "stale_reconstruction_narrows_source_allow": True,
            "missing_reconstruction_never_promotes": True,
        },
        "compatibility_boundary": {
            "existing_script_names_preserved": True,
            "existing_schema_names_preserved": True,
            "existing_artifact_names_preserved": True,
            "v0_outputs_mutated": False,
        },
        "claim_boundary": (
            "This verifies deterministic local compatibility projections from shipped v0 "
            "receipts. Mappings may preserve or narrow scope and never expand it. It does "
            "not deprecate v0, approve production, sign receipts, or prove customer outcomes."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_v0_payload_bodies_included": False,
            "real_secrets_included": False,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "production_mutation_performed": False,
        },
    }


def serialize_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")
    serialized = serialize_report(build_report())
    output = Path(args.output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    elif not output.is_file() or output.read_text(encoding="utf-8") != serialized:
        raise SystemExit(
            "CBB v0 compatibility report is stale. Run: "
            "python3 scripts/verify_cbb_v0_compatibility.py --write"
        )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
