#!/usr/bin/env python3
"""Verify paired benchmark contracts, schemas, and the 40-case fixture manifest."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.benchmark.adapters import PILOT_SUITE_ID  # noqa: E402
from study_anything.cbb.benchmark.fixtures import (  # noqa: E402
    pilot_assets,
    pilot_manifest,
    swe_second_selection_amendment,
    swe_selection_amendment,
    swe_third_selection_amendment,
    tua_selection_amendment,
)
from study_anything.cbb.benchmark.economics import (  # noqa: E402
    default_review_economic_evaluation_plan,
)
from study_anything.cbb.benchmark.models import (  # noqa: E402
    BENCHMARK_MODELS,
    BenchmarkSelectionAmendmentV1,
    BenchmarkCaseV1,
    BenchmarkSource,
    BlindedAdjudicationReceiptV1,
    CandidateDeliveryV1,
    HumanReviewSessionV1,
    ReviewExecutionProvenanceV1,
    ScorerExecutionReceiptV1,
    SourcePreflightReceiptV1,
    SupersededReviewAttemptV1,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    CanonicalProtocolError,
    assert_safe_metadata,
    pretty_json,
    schema_text,
)
from study_anything.cbb.protocol.models import StrictProtocolModel  # noqa: E402


SCHEMA_ROOT = ROOT / "platform" / "schemas" / "cbb"
FIXTURE_ROOT = ROOT / "fixtures" / "delivery-clearance-benchmark" / PILOT_SUITE_ID
REPORT_PATH = ROOT / "platform" / "generated" / "delivery-clearance-benchmark-contracts.json"
SUPPORTING_RECEIPT_MODELS: dict[str, type[StrictProtocolModel]] = {
    "benchmark-selection-amendment-v1": BenchmarkSelectionAmendmentV1,
    "blinded-adjudication-receipt-v1": BlindedAdjudicationReceiptV1,
    "review-execution-provenance-v1": ReviewExecutionProvenanceV1,
    "scorer-execution-receipt-v1": ScorerExecutionReceiptV1,
    "source-preflight-receipt-v1": SourcePreflightReceiptV1,
    "superseded-review-attempt-v1": SupersededReviewAttemptV1,
    "human-review-session-v1": HumanReviewSessionV1,
}


def _rejects(action: Any, expected: str) -> bool:
    try:
        action()
    except (CanonicalProtocolError, ValidationError, ValueError) as exc:
        return expected in str(exc)
    return False


def _negative_checks() -> dict[str, bool]:
    case, candidate = pilot_assets()[0]
    case_payload = case.model_dump(mode="json")
    candidate_payload = candidate.model_dump(mode="json")
    amendment_payload = tua_selection_amendment().model_dump(mode="json")

    leaked_label = deepcopy(candidate_payload)
    leaked_label["reference_label_included"] = True

    extra_field = deepcopy(candidate_payload)
    extra_field["oracle_decision"] = "cleared"

    unsafe_path = deepcopy(candidate_payload)
    unsafe_path["task_summary_code"] = "/Users/example/private/project"

    mismatched_case = deepcopy(case_payload)
    mismatched_case["case_class"] = "dangerous"

    relabeled_observed_candidate = deepcopy(candidate_payload)
    relabeled_observed_candidate["evidence_origin"] = "observed_agent_run"
    relabeled_observed_candidate["scorer_execution_origin"] = "observed_official_scorer"
    for evidence in relabeled_observed_candidate["evidence"]:
        if evidence["evidence_type"] == "scorer-result":
            evidence["evidence_ref"] = "observed-scorer:test"

    relabeled_observed_reference = deepcopy(case_payload)
    relabeled_observed_reference["reference"]["adjudication_basis"] = (
        "observed_official_scorer_plus_blinded_clearance_adjudication"
    )

    duplicate_prohibited_use = deepcopy(candidate_payload)
    duplicate_prohibited_use["prohibited_use_codes"] = [
        "customer-handoff",
        "customer-handoff",
    ]

    outcome_selected_amendment = deepcopy(amendment_payload)
    outcome_selected_amendment["model_arm_outcomes_used"] = True

    reordered_amendment = deepcopy(amendment_payload)
    reordered_amendment["replacement_pool_task_ids"] = list(
        reversed(reordered_amendment["replacement_pool_task_ids"])
    )

    checks = {
        "candidate_rejects_reference_label": _rejects(
            lambda: CandidateDeliveryV1.model_validate(leaked_label),
            "reference_label_included",
        ),
        "candidate_rejects_extra_oracle_field": _rejects(
            lambda: CandidateDeliveryV1.model_validate(extra_field),
            "Extra inputs are not permitted",
        ),
        "candidate_rejects_local_absolute_path": _rejects(
            lambda: assert_safe_metadata(unsafe_path, label="candidate"),
            "secret-like",
        ),
        "case_rejects_label_mismatch": _rejects(
            lambda: BenchmarkCaseV1.model_validate(mismatched_case),
            "case class and frozen reference authority disagree",
        ),
        "candidate_rejects_untraced_observed_scorer": _rejects(
            lambda: CandidateDeliveryV1.model_validate(relabeled_observed_candidate),
            "requires scorer execution and trace digest",
        ),
        "case_rejects_untraced_observed_adjudication": _rejects(
            lambda: BenchmarkCaseV1.model_validate(relabeled_observed_reference),
            "requires an adjudication trace",
        ),
        "candidate_rejects_duplicate_prohibited_uses": _rejects(
            lambda: CandidateDeliveryV1.model_validate(duplicate_prohibited_use),
            "duplicate prohibited uses",
        ),
        "amendment_rejects_model_outcome_selection": _rejects(
            lambda: BenchmarkSelectionAmendmentV1.model_validate(outcome_selected_amendment),
            "Input should be False",
        ),
        "amendment_rejects_reordered_pool": _rejects(
            lambda: BenchmarkSelectionAmendmentV1.model_validate(reordered_amendment),
            "replacement pool must use ascending task IDs",
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"benchmark contract negative checks failed: {failed}")
    return checks


def build_report() -> dict[str, Any]:
    assets = pilot_assets()
    manifest = pilot_manifest()
    source_counts = {
        source.value: sum(case.source.benchmark_id == source for case, _ in assets)
        for source in BenchmarkSource
    }
    report = {
        "schema_version": "benchmark-contracts-verification-v1",
        "status": "pass",
        "suite_id": PILOT_SUITE_ID,
        "contract_schemas": sorted(BENCHMARK_MODELS),
        "supporting_receipt_schemas": sorted(SUPPORTING_RECEIPT_MODELS),
        "case_count": len(assets),
        "safe_case_count": manifest["safe_case_count"],
        "dangerous_case_count": manifest["dangerous_case_count"],
        "source_counts": source_counts,
        "selection_amendments": {
            "count": 4,
            "replacement_count": (
                len(swe_selection_amendment().replacements)
                + len(swe_second_selection_amendment().replacements)
                + len(swe_third_selection_amendment().replacements)
                + len(tua_selection_amendment().replacements)
            ),
            "model_arm_outcomes_used": False,
            "safe_dangerous_balance_changed": False,
        },
        "label_isolation": {
            "oracle_and_candidate_files_separate": True,
            "candidate_reference_label_included": False,
            "candidate_hidden_tests_included": False,
        },
        "negative_checks": _negative_checks(),
        "claim_boundary": manifest["claim_boundary"],
        "privacy": manifest["privacy"],
    }
    assert_safe_metadata(report, label="benchmark contract report")
    return report


def expected_outputs() -> dict[Path, str]:
    outputs = {
        SCHEMA_ROOT / f"{schema_version}.schema.json": schema_text(model_type)
        for schema_version, model_type in {
            **BENCHMARK_MODELS,
            **SUPPORTING_RECEIPT_MODELS,
        }.items()
    }
    for case, candidate in pilot_assets():
        outputs[FIXTURE_ROOT / "oracle" / f"{case.case_id}.json"] = pretty_json(case)
        outputs[FIXTURE_ROOT / "candidates" / f"{case.case_id}.json"] = pretty_json(candidate)
    outputs[FIXTURE_ROOT / "benchmark-manifest.json"] = pretty_json(pilot_manifest())
    outputs[FIXTURE_ROOT / "economic-evaluation-plan.json"] = pretty_json(
        default_review_economic_evaluation_plan()
    )
    outputs[FIXTURE_ROOT / "selection-amendments" / "tua-source-feasibility-1.json"] = pretty_json(
        tua_selection_amendment()
    )
    outputs[FIXTURE_ROOT / "selection-amendments" / "swe-source-feasibility-1.json"] = pretty_json(
        swe_selection_amendment()
    )
    outputs[FIXTURE_ROOT / "selection-amendments" / "swe-source-feasibility-2.json"] = pretty_json(
        swe_second_selection_amendment()
    )
    outputs[FIXTURE_ROOT / "selection-amendments" / "swe-source-feasibility-3.json"] = pretty_json(
        swe_third_selection_amendment()
    )
    outputs[REPORT_PATH] = (
        json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")

    outputs = expected_outputs()
    if args.write:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    else:
        stale = [
            path.relative_to(ROOT).as_posix()
            for path, expected in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            raise SystemExit(
                "Benchmark contract artifacts are stale. Run: "
                "python3 scripts/verify_benchmark_contracts.py --write\n" + "\n".join(stale)
            )
    print(json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
