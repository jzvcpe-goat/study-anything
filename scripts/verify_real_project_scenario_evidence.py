#!/usr/bin/env python3
"""Verify committed real-project scenario receipts and reviewer packets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.benchmark.human_reconstruction import (  # noqa: E402
    boundary_questions,
)
from study_anything.cbb.benchmark.project_scenarios import (  # noqa: E402
    RealProjectCheckReceiptV1,
    load_scenario_set,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    assert_safe_metadata,
    canonical_sha256,
)


SCENARIO_SET = ROOT / "docs" / "evaluation" / "real-project-v0.1-scenarios.json"
RESULT_ROOT = ROOT / "validation" / "results" / "real-project-v0.1"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not read real-project evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"real-project evidence is not an object: {path}")
    assert_safe_metadata(payload, label="committed real-project evidence")
    return payload


def verify() -> dict[str, Any]:
    scenario_set = load_scenario_set(SCENARIO_SET)
    committed_set = _read_json(RESULT_ROOT / "scenario-set.json")
    result = _read_json(RESULT_ROOT / "result.json")
    if canonical_sha256(committed_set) != canonical_sha256(scenario_set):
        raise RuntimeError("committed real-project scenario set drifted")
    expected_ids = {item.case_id for item in scenario_set.cases}
    result_cases = {
        item["case_id"]: item
        for item in result.get("cases", [])
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    if set(result_cases) != expected_ids:
        raise RuntimeError("real-project result coverage drifted")

    for scenario in scenario_set.cases:
        receipt_payload = _read_json(RESULT_ROOT / "check-receipts" / f"{scenario.case_id}.json")
        packet = _read_json(RESULT_ROOT / "reviewer-packets" / f"{scenario.case_id}.json")
        receipt = RealProjectCheckReceiptV1.model_validate(receipt_payload)
        case_result = result_cases[scenario.case_id]
        if (
            receipt.source_commit_sha != scenario.source_commit_sha
            or receipt.machine_gate_status != scenario.expected_machine_status
            or not receipt.oracle_match
            or receipt.git_visible_state_mutated
            or receipt.raw_stdout_included
            or receipt.raw_stderr_included
            or case_result.get("receipt_digest_sha256") != canonical_sha256(receipt)
            or case_result.get("reviewer_packet_digest_sha256") != canonical_sha256(packet)
            or case_result.get("release_authorized") is not False
        ):
            raise RuntimeError(f"real-project receipt binding failed: {scenario.case_id}")
        if (
            packet.get("suite_id") != scenario_set.suite_id
            or packet.get("reference_label_included") is not False
            or packet.get("hidden_tests_included") is not False
            or packet.get("official_scorer_result_included") is not False
            or len(boundary_questions(packet)) != 5
        ):
            raise RuntimeError(f"real-project reviewer packet drifted: {scenario.case_id}")

    if (
        result.get("status") != "pass"
        or result.get("case_count") != 4
        or result.get("blocked_case_count") != 3
        or result.get("ready_for_human_review_count") != 1
        or result.get("human_review_completed") is not False
        or result.get("release_authorized") is not False
        or result.get("maximum_scope_without_human_review") != "blocked"
        or not (RESULT_ROOT / "report.md").is_file()
    ):
        raise RuntimeError("real-project aggregate result drifted")

    verification = {
        "schema_version": "real-project-scenario-evidence-verification-v1",
        "status": "pass",
        "suite_id": scenario_set.suite_id,
        "case_count": len(expected_ids),
        "oracle_match_count": len(expected_ids),
        "blocked_case_count": 3,
        "ready_for_human_review_count": 1,
        "human_review_completed": False,
        "release_authorized": False,
        "maximum_scope": "blocked",
        "claim_boundary": (
            "This verifies committed metadata and bindings for one four-state project replay. "
            "It does not re-execute the historical checks or establish user effectiveness, "
            "customer readiness, production safety, or independent review."
        ),
    }
    assert_safe_metadata(verification, label="real-project evidence verification")
    return verification


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        raise SystemExit("Pass --check to verify committed real-project evidence.")
    print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
