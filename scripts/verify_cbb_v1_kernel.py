#!/usr/bin/env python3
"""Verify deterministic CBB Protocol v1 trust-kernel decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.kernel.fixtures import (  # noqa: E402
    build_kernel_cases,
    fixture_outputs,
)
from study_anything.cbb.kernel.gate import evaluate_gate  # noqa: E402
from study_anything.cbb.protocol.canonical import model_payload  # noqa: E402
from study_anything.cbb.protocol.models import (  # noqa: E402
    EvidenceBundleV1,
    QualifiedReconstructionV1,
    TrustPolicyV1,
)


REPORT_SCHEMA_VERSION = "cbb-v1-kernel-verification-v1"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-v1-kernel.json"
EXPECTED = {
    "pass": ("allow", "controlled_customer_handoff"),
    "missing-evidence": ("needs_evidence", "blocked"),
    "failed-evidence": ("block", "blocked"),
    "stale-reconstruction": ("needs_evidence", "blocked"),
    "hard-deny": ("block", "blocked"),
    "reference-mismatch": ("block", "blocked"),
    "claim-boundary-narrowing": ("allow", "internal_handoff"),
}


def _json_text(payload: Any) -> str:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def _verify_case(case_id: str, case: dict[str, Any]) -> dict[str, Any]:
    inputs = case["inputs"]
    policy = TrustPolicyV1.model_validate(inputs["policy"])
    evidence = EvidenceBundleV1.model_validate(inputs["evidence_bundle"])
    reconstruction = QualifiedReconstructionV1.model_validate(inputs["qualified_reconstruction"])
    first = evaluate_gate(policy, evidence, reconstruction)
    second = evaluate_gate(policy, evidence, reconstruction)
    actual = model_payload(first)
    if actual != model_payload(second):
        raise RuntimeError(f"{case_id}: kernel output is not deterministic")
    if actual != case["decision"]:
        raise RuntimeError(f"{case_id}: stored decision drifted")
    expected_status, expected_scope = EXPECTED[case_id]
    if actual["status"] != expected_status or actual["approved_scope"] != expected_scope:
        raise RuntimeError(f"{case_id}: decision outcome drifted")

    if case_id == "missing-evidence" and "dual_loop_gate" not in actual["missing_evidence_types"]:
        raise RuntimeError("missing-evidence: dual_loop_gate was not reported")
    if case_id == "failed-evidence" and "evidence_failed:sandbox_receipt" not in actual["reasons"]:
        raise RuntimeError("failed-evidence: failed sandbox did not block")
    if (
        case_id == "stale-reconstruction"
        and "qualified_reconstruction" not in actual["missing_evidence_types"]
    ):
        raise RuntimeError("stale-reconstruction: stale evidence was not requested")
    if case_id == "hard-deny" and actual["hard_denies_triggered"] != ["production_mutation"]:
        raise RuntimeError("hard-deny: production mutation deny was not triggered")
    if case_id == "reference-mismatch" and "evidence_policy_ref_mismatch" not in actual["reasons"]:
        raise RuntimeError("reference-mismatch: cross-receipt mismatch was not blocked")

    return {
        "case_id": case_id,
        "status": actual["status"],
        "approved_scope": actual["approved_scope"],
        "reasons": actual["reasons"],
        "hard_denies_triggered": actual["hard_denies_triggered"],
        "missing_evidence_types": actual["missing_evidence_types"],
    }


def build_report() -> dict[str, Any]:
    cases = build_kernel_cases()
    results = [_verify_case(case_id, cases[case_id]) for case_id in sorted(cases)]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed",
        "kernel": {
            "deterministic": True,
            "model_calls": False,
            "retrieval": False,
            "network": False,
            "tool_execution": False,
            "production_mutation": False,
        },
        "verified_properties": [
            "hard denies block every release scope",
            "missing or stale required evidence cannot authorize delivery",
            "failed evidence blocks instead of degrading to an approval",
            "cross-receipt reference mismatches block",
            "claim boundaries can narrow but never expand authority",
            "identical canonical inputs produce identical decisions",
        ],
        "cases": results,
        "fixture_count": len(cases),
    }


def _expected_outputs(report_path: Path) -> dict[Path, str]:
    return {
        **fixture_outputs(ROOT),
        report_path: _json_text(build_report()),
    }


def _write_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _check_outputs(outputs: dict[Path, str]) -> None:
    stale = [
        str(path.relative_to(ROOT))
        for path, expected in outputs.items()
        if not path.exists() or path.read_text(encoding="utf-8") != expected
    ]
    if stale:
        raise RuntimeError(
            "CBB v1 kernel assets are stale; run "
            "verify_cbb_v1_kernel.py --write: " + ", ".join(stale)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")
    outputs = _expected_outputs(Path(args.report))
    if args.write:
        _write_outputs(outputs)
    else:
        _check_outputs(outputs)
    print(_json_text(build_report()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
