#!/usr/bin/env python3
"""Verify the committed real-Agent case set and optionally replay public inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.benchmark.human_reconstruction import (  # noqa: E402
    boundary_questions,
)
from study_anything.cbb.benchmark.real_agent_cases import (  # noqa: E402
    RealAgentCaseSetV1,
    build_real_agent_case_set,
    load_real_agent_protocol,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    assert_safe_metadata,
    canonical_sha256,
)


PROTOCOL_PATH = ROOT / "docs" / "evaluation" / "real-agent-v0.1-protocol.json"
RESULT_ROOT = ROOT / "validation" / "results" / "real-agent-v0.1"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not read real-Agent evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"real-Agent evidence is not an object: {path}")
    assert_safe_metadata(payload, label="committed real-Agent evidence")
    return payload


def verify(
    *,
    predictions_path: Path | None = None,
    results_path: Path | None = None,
    issue_response_dir: Path | None = None,
) -> dict[str, Any]:
    supplied = (predictions_path, results_path, issue_response_dir)
    if any(value is not None for value in supplied) and not all(
        value is not None for value in supplied
    ):
        raise RuntimeError(
            "source replay requires predictions, results, and issue responses together"
        )

    protocol = load_real_agent_protocol(PROTOCOL_PATH)
    case_set = RealAgentCaseSetV1.model_validate(_read_json(RESULT_ROOT / "case-set.json"))
    result = _read_json(RESULT_ROOT / "result.json")
    if case_set.protocol_digest_sha256 != canonical_sha256(protocol):
        raise RuntimeError("real-Agent case set protocol binding drifted")
    if (
        case_set.source_repository != protocol.source_repository
        or case_set.source_revision != protocol.source_revision
        or case_set.submission_path != protocol.submission_path
        or case_set.agent_name != protocol.agent_name
        or case_set.model_name != protocol.model_name
        or case_set.selection_seed != protocol.selection_seed
    ):
        raise RuntimeError("real-Agent case set source identity drifted")

    expected_count = protocol.passed_case_count + protocol.failed_case_count
    if len(case_set.cases) != expected_count:
        raise RuntimeError("real-Agent case count drifted")
    outcomes = [case.published_functional_outcome for case in case_set.cases]
    if outcomes.count("passed") != protocol.passed_case_count:
        raise RuntimeError("real-Agent passed stratum drifted")
    if outcomes.count("failed") != protocol.failed_case_count:
        raise RuntimeError("real-Agent failed stratum drifted")
    for outcome in ("passed", "failed"):
        repositories = [
            case.repository.lower()
            for case in case_set.cases
            if case.published_functional_outcome == outcome
        ]
        if len(repositories) != len(set(repositories)):
            raise RuntimeError(f"real-Agent {outcome} stratum repeats a repository")

    for case in case_set.cases:
        packet = _read_json(RESULT_ROOT / "reviewer-packets" / f"{case.case_id}.json")
        oracle = _read_json(RESULT_ROOT / "oracle" / f"{case.case_id}.json")
        candidate = packet.get("candidate")
        if not isinstance(candidate, dict):
            raise RuntimeError(f"real-Agent reviewer packet has no candidate: {case.case_id}")
        if (
            packet.get("suite_id") != case_set.suite_id
            or packet.get("reference_label_included") is not False
            or packet.get("hidden_tests_included") is not False
            or packet.get("official_scorer_result_included") is not False
            or packet.get("raw_candidate_payload_included") is not False
            or packet.get("raw_issue_body_included") is not False
            or packet.get("review_material_digest_sha256") != case.review_material_digest_sha256
            or candidate.get("candidate_digest_sha256") != case.candidate_patch_digest_sha256
            or len(boundary_questions(packet)) != 5
        ):
            raise RuntimeError(f"real-Agent reviewer packet binding failed: {case.case_id}")
        visible = candidate.get("visible_evidence")
        if not isinstance(visible, list):
            raise RuntimeError(f"real-Agent visible evidence is invalid: {case.case_id}")
        scorer_items = [
            item
            for item in visible
            if isinstance(item, dict) and item.get("evidence_type") == "scorer-result"
        ]
        if len(scorer_items) != 1 or any(
            item.get("status") != "missing"
            or item.get("summary_code") != "official-result-withheld-for-blinded-review"
            for item in scorer_items
        ):
            raise RuntimeError(f"real-Agent reviewer packet leaks scorer state: {case.case_id}")
        if (
            oracle.get("published_functional_outcome") != case.published_functional_outcome
            or oracle.get("candidate_patch_digest_sha256") != case.candidate_patch_digest_sha256
            or oracle.get("local_official_scorer_reexecuted") is not False
            or oracle.get("clearance_reference_status") != "pending_blinded_human_adjudication"
        ):
            raise RuntimeError(f"real-Agent oracle binding failed: {case.case_id}")

    if list(RESULT_ROOT.rglob("candidate.patch")) or list(RESULT_ROOT.rglob("issue.md")):
        raise RuntimeError("committed real-Agent result tree contains raw review material")
    if (
        result.get("status") != "pass"
        or result.get("case_count") != expected_count
        or result.get("published_passed_count") != protocol.passed_case_count
        or result.get("published_failed_count") != protocol.failed_case_count
        or result.get("source_material_verified_at_generation") is not True
        or result.get("local_official_scorer_reexecuted") is not False
        or result.get("paired_agent_review_completed") is not False
        or result.get("human_adjudication_completed") is not False
        or result.get("effectiveness_claim_allowed") is not False
        or result.get("release_authorized") is not False
        or result.get("case_set_digest_sha256") != canonical_sha256(case_set)
        or not (RESULT_ROOT / "report.zh-CN.md").is_file()
    ):
        raise RuntimeError("real-Agent aggregate result drifted")

    source_replay_performed = predictions_path is not None
    if source_replay_performed:
        assert predictions_path is not None
        assert results_path is not None
        assert issue_response_dir is not None
        with tempfile.TemporaryDirectory(prefix="real-agent-source-replay-") as temp:
            root = Path(temp)
            replay_result = build_real_agent_case_set(
                protocol=protocol,
                predictions_path=predictions_path,
                results_path=results_path,
                issue_response_dir=issue_response_dir,
                output_dir=root / "results",
                material_output_dir=root / "materials",
            )
            replay_set = RealAgentCaseSetV1.model_validate(
                _read_json(root / "results" / "case-set.json")
            )
            if canonical_sha256(replay_set) != canonical_sha256(case_set):
                raise RuntimeError("live public-source replay disagrees with committed case set")
            if replay_result.get("case_set_digest_sha256") != canonical_sha256(case_set):
                raise RuntimeError("live public-source replay digest disagrees")

    verification = {
        "schema_version": "real-agent-case-set-verification-v1",
        "status": "pass",
        "suite_id": protocol.suite_id,
        "case_count": expected_count,
        "published_passed_count": protocol.passed_case_count,
        "published_failed_count": protocol.failed_case_count,
        "distinct_repository_count": len({case.repository.lower() for case in case_set.cases}),
        "source_replay_performed": source_replay_performed,
        "raw_review_material_committed": False,
        "local_official_scorer_reexecuted": False,
        "paired_agent_review_completed": False,
        "human_adjudication_completed": False,
        "effectiveness_claim_allowed": False,
        "release_authorized": False,
        "claim_boundary": (
            "This verifies a frozen real-task, real-Agent-patch evaluation input. It does not "
            "establish Delivery Clearance effectiveness, customer readiness, production safety, "
            "or independent human review."
        ),
    }
    assert_safe_metadata(verification, label="real-Agent case-set verification")
    return verification


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--predictions")
    parser.add_argument("--results")
    parser.add_argument("--issue-responses")
    args = parser.parse_args()
    if not args.check:
        raise SystemExit("Pass --check to verify committed real-Agent evidence.")
    print(
        json.dumps(
            verify(
                predictions_path=(
                    Path(args.predictions).expanduser().resolve() if args.predictions else None
                ),
                results_path=(Path(args.results).expanduser().resolve() if args.results else None),
                issue_response_dir=(
                    Path(args.issue_responses).expanduser().resolve()
                    if args.issue_responses
                    else None
                ),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
