#!/usr/bin/env python3
"""Verify CBB protocol contracts and metadata-only boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import cbb_protocol, dual_loop  # noqa: E402


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-protocol-contracts.json"

SCHEMA_FILES = [
    (
        ROOT / "platform" / "schemas" / "cbb" / "claim-boundary-v1.schema.json",
        cbb_protocol.CLAIM_BOUNDARY_SCHEMA_VERSION,
    ),
    (
        ROOT / "platform" / "schemas" / "cbb" / "trust-root-v1.schema.json",
        cbb_protocol.TRUST_ROOT_SCHEMA_VERSION,
    ),
    (
        ROOT
        / "platform"
        / "schemas"
        / "cbb"
        / "reviewer-reconstruction-receipt-v1.schema.json",
        cbb_protocol.REVIEWER_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION,
    ),
    (
        ROOT / "platform" / "schemas" / "cbb" / "risk-owner-scope-v1.schema.json",
        cbb_protocol.RISK_OWNER_SCOPE_SCHEMA_VERSION,
    ),
    (
        ROOT / "platform" / "schemas" / "cbb" / "delivery-decision-receipt-v1.schema.json",
        cbb_protocol.DELIVERY_DECISION_RECEIPT_SCHEMA_VERSION,
    ),
]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _schema_report() -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    for path, schema_version in SCHEMA_FILES:
        if not path.is_file():
            raise RuntimeError(f"CBB schema missing: {path}")
        payload = _load_json(path)
        if payload.get("$id") != schema_version:
            raise RuntimeError(f"CBB schema id drifted for {path}")
        if payload.get("properties", {}).get("schema_version", {}).get("const") != schema_version:
            raise RuntimeError(f"CBB schema_version const drifted for {path}")
        reports.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "schema_version": schema_version,
                "sha256": dual_loop.sha256_text(path.read_text(encoding="utf-8")),
            }
        )
    return reports


def _exercise_positive_contracts() -> dict[str, str]:
    claim = cbb_protocol.validate_claim_boundary(cbb_protocol.claim_boundary_demo())
    trust = cbb_protocol.validate_trust_root(cbb_protocol.trust_root_demo())
    reviewer = cbb_protocol.validate_reviewer_reconstruction_receipt(
        cbb_protocol.reviewer_reconstruction_demo()
    )
    scope = cbb_protocol.validate_risk_owner_scope(cbb_protocol.risk_owner_scope_demo())
    decision = cbb_protocol.validate_delivery_decision_receipt(
        cbb_protocol.evaluate_cbb_gate(claim, trust, reviewer, scope)
    )
    for label, payload in {
        "claim_boundary": claim,
        "trust_root": trust,
        "reviewer_reconstruction": reviewer,
        "risk_owner_scope": scope,
        "delivery_decision": decision,
    }.items():
        dual_loop.assert_metadata_only(payload, label=label)
    return {
        "claim_boundary": claim["schema_version"],
        "trust_root": trust["schema_version"],
        "reviewer_reconstruction": reviewer["schema_version"],
        "risk_owner_scope": scope["schema_version"],
        "delivery_decision": decision["schema_version"],
    }


def _capture_rejection(
    label: str,
    validator: Any,
    payload: Mapping[str, Any],
) -> tuple[str, str]:
    try:
        validator(payload)
    except Exception as exc:  # noqa: BLE001 - verifier records deterministic rejection reason.
        message = str(exc)
        if "private-looking data" in message:
            message = "private-looking data rejected"
        return label, message
    raise RuntimeError(f"Expected CBB negative check to fail: {label}")


def _exercise_negative_contracts() -> dict[str, str]:
    checks = dict(
        [
            _capture_rejection(
                "missing_claim_boundary_rejected",
                cbb_protocol.validate_claim_boundary,
                cbb_protocol.claim_boundary_demo(missing=True),
            ),
            _capture_rejection(
                "ai_review_only_trust_rejected",
                cbb_protocol.validate_trust_root,
                cbb_protocol.trust_root_demo(ai_review_only=True),
            ),
            _capture_rejection(
                "reviewer_not_qualified_rejected",
                cbb_protocol.validate_reviewer_reconstruction_receipt,
                cbb_protocol.reviewer_reconstruction_demo(qualified=False),
            ),
            _capture_rejection(
                "recipient_risk_unknown_rejected",
                cbb_protocol.validate_risk_owner_scope,
                cbb_protocol.risk_owner_scope_demo(recipient_risk_known=False),
            ),
        ]
    )
    forbidden_field = cbb_protocol.claim_boundary_demo()
    forbidden_field["api_key"] = "fixture-value"
    checks.update(
        [
            _capture_rejection(
                "forbidden_api_key_field_rejected",
                cbb_protocol.validate_claim_boundary,
                forbidden_field,
            )
        ]
    )
    return checks


def build_report() -> dict[str, Any]:
    contracts = _exercise_positive_contracts()
    negative_checks = _exercise_negative_contracts()
    report = {
        "schema_version": cbb_protocol.CBB_PROTOCOL_CONTRACTS_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "artifact_contracts": contracts,
        "schema_files": _schema_report(),
        "negative_checks": negative_checks,
        "trust_rules": {
            "claim_boundary_required": True,
            "risk_owner_scope_required": True,
            "reviewer_active_reconstruction_required": True,
            "ai_review_only_forbidden": True,
            "deterministic_kernel_required": True,
            "production_mutation_blocked": True,
            "model_calls_forbidden_in_v0_1": True,
        },
        "privacy": {
            **cbb_protocol.CBB_PRIVACY_FLAGS,
            "metadata_only_verifier": True,
            "raw_customer_payload_included": False,
            "real_customer_data_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "claim_boundary": {
            "current_claim": (
                "CBB protocol contracts are valid for local deterministic reference "
                "implementation checks."
            ),
            "not_claimed": [
                "production customer trust",
                "legal certification",
                "security certification",
                "general model correctness",
            ],
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cbb_protocol_contracts.py --check",
            "schema_dir": "platform/schemas/cbb",
        },
    }
    dual_loop.assert_metadata_only(report, label="cbb-protocol-contracts-report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    report = build_report()
    serialized = cbb_protocol.dump_json(report)
    output = Path(args.output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"CBB protocol contracts report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "CBB protocol contracts report is out of date. "
                "Run: python3 scripts/verify_cbb_protocol_contracts.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
