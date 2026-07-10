#!/usr/bin/env python3
"""Verify that CBB Protocol v1 provenance fails closed under object tampering."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.provenance.fixtures import (  # noqa: E402
    FIXTURE_NOW,
    build_provenance_cases,
)
from study_anything.cbb.provenance.signing import (  # noqa: E402
    OfflineProvenancePackageV1,
    verify_offline_package,
)


REPORT_SCHEMA_VERSION = "cbb-v1-tamper-cases-verification-v1"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-v1-tamper-cases.json"
EXPECTED_FAILED_CHECKS = {
    "tampered-policy": {"policy_digest", "deterministic_gate"},
    "tampered-evidence": {"evidence_digest", "deterministic_gate"},
    "tampered-reconstruction": {"reconstruction_digest", "deterministic_gate"},
    "tampered-decision": {"decision_digest", "deterministic_gate"},
    "tampered-receipt": {"receipt_envelope_digest"},
    "tampered-signature": {"signature"},
    "wrong-public-key": {"signature"},
}


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_report() -> dict[str, Any]:
    cases = build_provenance_cases()
    results: list[dict[str, Any]] = []
    for case_id, expected_failed in EXPECTED_FAILED_CHECKS.items():
        package = OfflineProvenancePackageV1.model_validate(cases[case_id]["package"])
        result = verify_offline_package(package, now=FIXTURE_NOW)
        if result.passed:
            raise RuntimeError(f"{case_id}: tampered package unexpectedly passed")
        if not expected_failed.issubset(result.reasons):
            raise RuntimeError(
                f"{case_id}: expected failures {sorted(expected_failed)}, got {result.reasons}"
            )
        results.append(
            {
                "case_id": case_id,
                "status": result.status,
                "failed_checks": list(result.reasons),
            }
        )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "case_count": len(results),
        "cases": results,
        "changed_byte_invalidates_trust": True,
        "claim_boundary": (
            "This deterministic fixture suite demonstrates fail-closed verification for "
            "selected canonical object, signature, and public-key tampering. It is not a "
            "complete cryptographic audit or proof against every implementation defect."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")
    report_path = Path(args.report)
    content = _json_text(build_report())
    if args.write:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(content, encoding="utf-8")
    elif not report_path.is_file() or report_path.read_text(encoding="utf-8") != content:
        raise SystemExit(
            "CBB v1 tamper report is stale; run verify_cbb_v1_tamper_cases.py --write"
        )
    print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
