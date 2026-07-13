"""Deterministic acceptance checks for the paired benchmark harness."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping, cast

from pydantic import ValidationError

from study_anything.cbb.benchmark.fixtures import pilot_assets
from study_anything.cbb.benchmark.economics import human_evidence_status
from study_anything.cbb.benchmark.metrics import (
    arm_metrics,
    build_result,
    confirmatory_power_analysis,
    cost_effect_analysis,
    exact_mcnemar_p_value,
    mcnemar_required_pairs,
    pairwise_analysis,
    wilcoxon_signed_rank,
    wilson_interval,
)
from study_anything.cbb.benchmark.models import (
    AblationObservationV1,
    AblationVariant,
    BenchmarkArm,
    BenchmarkResultV1,
    BenchmarkSource,
    BlindedAdjudicationReceiptV1,
    ClearanceDisposition,
    DecisionToolTraceV1,
    HumanReviewSessionV1,
    PairedRunV1,
    ReviewExecutionProvenanceV1,
    ReviewerDecisionV1,
    ScorerExecutionReceiptV1,
)
from study_anything.cbb.benchmark.runner import (
    fixture_decision,
    fixture_tool_trace,
    run_benchmark,
    tool_trace_digest,
)
from study_anything.cbb.protocol.canonical import assert_safe_metadata, canonical_sha256
from study_anything.cbb.protocol.models import DeliveryScope


def _load_json(path: Path) -> dict[str, Any]:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    assert_safe_metadata(payload, label=path.name)
    return payload


def _load_lines(path: Path, model_type: type[Any]) -> list[Any]:
    return [
        model_type.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_mechanism(root: Path) -> tuple[Path, BenchmarkResultV1]:
    output = root / "pilot"
    return output, run_benchmark(output)


def _rejects(model_type: type[Any], payload: Mapping[str, Any], expected: str) -> bool:
    try:
        model_type.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        return expected in str(exc)
    return False


def fairness_report() -> dict[str, Any]:
    with TemporaryDirectory(prefix="delivery-clearance-fairness-") as temp:
        output, _ = _run_mechanism(Path(temp))
        runs = _load_lines(output / "paired-runs.jsonl", PairedRunV1)
        cases = {case.case_id: case for case, _ in pilot_assets()}
        candidates = {case.case_id: candidate for case, candidate in pilot_assets()}

        checks = {
            "all_40_cases_have_four_arms": len(runs) == 40
            and all(len(run.decisions) == 4 for run in runs),
            "same_candidate_digest": all(
                run.candidate_digest_sha256
                == canonical_sha256(candidates[run.case_id])
                == cases[run.case_id].candidate_digest_sha256
                for run in runs
            ),
            "same_model_and_version": all(
                len({(item.model_ref, item.model_version) for item in run.decisions}) == 1
                for run in runs
            ),
            "same_context": all(
                len({item.context_digest_sha256 for item in run.decisions}) == 1 for run in runs
            ),
            "same_tool_permissions": all(
                len({tuple(item.tool_permission_ids) for item in run.decisions}) == 1
                for run in runs
            ),
            "same_budget": all(
                len(
                    {json.dumps(item.budget.model_dump(), sort_keys=True) for item in run.decisions}
                )
                == 1
                for run in runs
            ),
            "native_control_not_weakened": all(
                run.fairness.native_control_not_weakened for run in runs
            ),
            "fixed_seed_where_supported": all(
                len({item.random_seed for item in run.decisions}) == 1 for run in runs
            ),
        }

        sample = runs[0].model_dump(mode="json")
        model_drift = deepcopy(sample)
        model_drift["decisions"][0]["model_version"] = "different-version"
        tool_drift = deepcopy(sample)
        tool_drift["decisions"][0]["tool_permission_ids"] = ["read_candidate_metadata"]
        context_drift = deepcopy(sample)
        context_drift["decisions"][0]["context_digest_sha256"] = "0" * 64
        budget_drift = deepcopy(sample)
        budget_drift["decisions"][0]["budget"]["max_input_tokens"] += 1
        negative_checks = {
            "model_drift_rejected": _rejects(PairedRunV1, model_drift, "model or version differs"),
            "tool_drift_rejected": _rejects(PairedRunV1, tool_drift, "tool permissions differ"),
            "context_drift_rejected": _rejects(PairedRunV1, context_drift, "context differs"),
            "budget_drift_rejected": _rejects(PairedRunV1, budget_drift, "resource budget differs"),
        }
        failed = sorted(
            name for name, passed in {**checks, **negative_checks}.items() if not passed
        )
        if failed:
            raise RuntimeError(f"benchmark fairness checks failed: {failed}")
        report = {
            "schema_version": "benchmark-fairness-verification-v1",
            "status": "pass",
            "paired_run_count": len(runs),
            "checks": checks,
            "negative_checks": negative_checks,
            "claim_boundary": "Fairness validation proves parity of recorded inputs, not efficacy.",
        }
        assert_safe_metadata(report, label="fairness report")
        return report


def isolation_report() -> dict[str, Any]:
    with TemporaryDirectory(prefix="delivery-clearance-isolation-") as temp:
        output, _ = _run_mechanism(Path(temp))
        runs = _load_lines(output / "paired-runs.jsonl", PairedRunV1)
        traces = _load_lines(output / "tool-call-traces.jsonl", DecisionToolTraceV1)
        packets = [_load_json(path) for path in sorted((output / "cases").glob("*.json"))]
        external = [
            decision
            for run in runs
            for decision in run.decisions
            if decision.arm == BenchmarkArm.EXTERNAL_CLEARANCE
        ]
        all_artifacts_safe = True
        for path in output.rglob("*"):
            if not path.is_file():
                continue
            try:
                if path.suffix == ".json":
                    assert_safe_metadata(
                        json.loads(path.read_text(encoding="utf-8")), label=path.name
                    )
                elif path.suffix == ".jsonl":
                    for line in path.read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            assert_safe_metadata(json.loads(line), label=path.name)
                else:
                    assert_safe_metadata(path.read_text(encoding="utf-8"), label=path.name)
            except ValueError:
                all_artifacts_safe = False

        checks = {
            "reviewer_packets_exclude_reference_decision": all(
                "reference" not in packet and "case_class" not in packet for packet in packets
            ),
            "reviewer_packets_exclude_hidden_tests": all(
                packet["hidden_tests_included"] is False for packet in packets
            ),
            "reviewer_packets_include_responsibility_boundaries": all(
                packet.get("candidate", {}).get("intended_recipient_role")
                == "local-project-owner"
                and packet.get("candidate", {}).get("risk_owner_role")
                == "local-project-owner"
                and packet.get("candidate", {}).get("prohibited_use_codes")
                == ["customer-handoff", "production-execution"]
                for packet in packets
            ),
            "reviewer_packets_exclude_official_scorer_result": all(
                packet.get("official_scorer_result_included") is False
                and packet.get("candidate", {}).get("official_scorer_result_included") is False
                and "scorer_outcome" not in packet.get("candidate", {})
                and "scorer_execution_origin" not in packet.get("candidate", {})
                and "official_scorer_executed" not in packet.get("candidate", {})
                and "scorer_trace_digest_sha256" not in packet.get("candidate", {})
                and all(
                    item.get("evidence_type") != "scorer-result"
                    for item in packet.get("candidate", {}).get("visible_evidence", [])
                )
                for packet in packets
            ),
            "oracle_directory_not_copied_to_run_output": not (output / "oracle").exists(),
            "external_gate_not_producer_modifiable": all(
                not item.producing_agent_can_modify_final_gate for item in external
            ),
            "external_gate_forbids_self_approval": all(
                not item.producing_agent_can_approve_own_output for item in external
            ),
            "labels_and_hidden_tests_withheld": all(
                not item.hidden_labels_accessible and not item.hidden_tests_accessible
                for run in runs
                for item in run.decisions
            ),
            "isolated_workspaces_and_memories": all(
                run.fairness.isolated_workspaces and run.fairness.isolated_memories for run in runs
            ),
            "artifacts_pass_metadata_safety_scan": all_artifacts_safe,
            "every_tool_call_has_metadata_trace": len(traces)
            == sum(len(run.decisions) for run in runs)
            and sum(len(trace.calls) for trace in traces)
            == sum(decision.usage.tool_calls for run in runs for decision in run.decisions),
            "tool_trace_digests_verify": all(
                trace.trace_digest_sha256 == tool_trace_digest(trace) for trace in traces
            ),
            "tool_traces_exclude_raw_arguments_and_outputs": all(
                not call.raw_arguments_included and not call.raw_output_included
                for trace in traces
                for call in trace.calls
            ),
        }

        sample = external[0].model_dump(mode="json")
        self_approval = deepcopy(sample)
        self_approval["producing_agent_can_approve_own_output"] = True
        relabeled_observed = deepcopy(sample)
        relabeled_observed["evidence_origin"] = "observed_agent_run"
        relabeled_observed["execution_trace_digest_sha256"] = "a" * 64
        negative_checks = {
            "external_self_approval_rejected": _rejects(
                ReviewerDecisionV1, self_approval, "forbids self-approval"
            ),
            "fixture_harness_cannot_claim_observed_execution": _rejects(
                ReviewerDecisionV1,
                relabeled_observed,
                "mechanism fixture harness cannot claim observed execution",
            ),
        }
        failed = sorted(
            name for name, passed in {**checks, **negative_checks}.items() if not passed
        )
        if failed:
            raise RuntimeError(f"benchmark isolation checks failed: {failed}")
        report = {
            "schema_version": "benchmark-isolation-verification-v1",
            "status": "pass",
            "reviewer_packet_count": len(packets),
            "checks": checks,
            "negative_checks": negative_checks,
            "claim_boundary": (
                "Isolation prevents producer self-clearance in the reference harness; it is not a "
                "production sandbox certification."
            ),
        }
        assert_safe_metadata(report, label="isolation report")
        return report


def metrics_report() -> dict[str, Any]:
    with TemporaryDirectory(prefix="delivery-clearance-metrics-") as temp:
        output, result = _run_mechanism(Path(temp))
        runs = _load_lines(output / "paired-runs.jsonl", PairedRunV1)
        sessions = _load_lines(output / "human-review-sessions.jsonl", HumanReviewSessionV1)
        traces = _load_lines(output / "tool-call-traces.jsonl", DecisionToolTraceV1)
        _load_lines(output / "ablation-runs.jsonl", AblationObservationV1)
        power_output = _load_json(output / "power-analysis.json")
        cost_effect_output = _load_json(output / "cost-effect-analysis.json")
        statistical_output = _load_json(output / "statistical-analysis.json")
        cases = [case for case, _ in pilot_assets()]
        rebuilt = build_result(
            cases,
            runs,
            human_review_sessions=sessions,
            run_evidence_basis="mechanism_fixture",
            candidate_evidence_basis="mechanism_fixture",
            reference_evidence_basis="mechanism_fixture",
            tool_trace_count=len(traces),
            tool_trace_coverage_complete=result.tool_trace_coverage_complete,
            ablation_evidence_basis="mechanism_fixture",
            ablation_variant_count=len(AblationVariant),
            ablation_complete=True,
            manifest_digest_sha256=result.source_manifest_digest_sha256,
            paired_runs_digest_sha256=result.paired_runs_digest_sha256,
            generated_at=result.generated_at,
        )

        dangerous_run = next(
            run
            for run in runs
            if not next(
                case for case in cases if case.case_id == run.case_id
            ).reference.release_authorized
        )
        altered_payload = dangerous_run.model_dump(mode="json")
        for decision in altered_payload["decisions"]:
            if decision["arm"] == BenchmarkArm.NATIVE.value:
                decision["release_authorized"] = True
                decision["disposition"] = ClearanceDisposition.CLEARED.value
                decision["approved_scope"] = DeliveryScope.PERSONAL_LOCAL.value
                decision["reason_codes"] = ["synthetic-false-clearance-for-metric-test"]
        altered_run = PairedRunV1.model_validate(altered_payload)
        known_metrics = {item.arm: item for item in arm_metrics(cases, [altered_run])}
        known_pair = pairwise_analysis(
            cases,
            [altered_run],
            baseline=BenchmarkArm.NATIVE,
            comparison=BenchmarkArm.EXTERNAL_CLEARANCE,
        )
        zero_twenty = wilson_interval(0, 20)
        wilcoxon_w, wilcoxon_p = wilcoxon_signed_rank([1.0, 2.0, 3.0, 4.0])
        required_80 = mcnemar_required_pairs(0.20, 0.05, power=0.80)
        required_90 = mcnemar_required_pairs(0.20, 0.05, power=0.90)
        expected_power = confirmatory_power_analysis(
            cases,
            runs,
            empirical_interpretation_allowed=False,
        )
        expected_cost_effect = cost_effect_analysis(
            cases,
            runs,
            result=result,
            cost_basis_counts={
                "synthetic_fixture": sum(len(run.decisions) for run in runs)
            },
            human_review_sessions=sessions,
        )
        mechanism_human_status = human_evidence_status(
            [case.case_id for case in cases],
            sessions,
            [],
        )
        checks = {
            "metrics_reproduce_from_paired_runs": rebuilt == result,
            "known_false_clearance_count": (
                known_metrics[BenchmarkArm.NATIVE].false_clearance_count == 1
            ),
            "known_scope_expansion_count": (
                known_metrics[BenchmarkArm.NATIVE].scope_expansion_count == 1
            ),
            "dangerous_only_mcnemar_pair": (
                known_pair.mcnemar_b == 1 and known_pair.mcnemar_c == 0
            ),
            "exact_mcnemar_known_value": abs(exact_mcnemar_p_value(8, 0) - 0.0078125) < 1e-12,
            "wilson_interval_nonzero_upper_bound": zero_twenty[0] == 0.0 and zero_twenty[1] > 0,
            "wilcoxon_known_direction": wilcoxon_w == 0.0 and 0 <= wilcoxon_p <= 1,
            "review_compression_calculated": result.review_compression_ratio is not None,
            "all_four_arm_metrics_present": {item.arm for item in result.arm_metrics}
            == set(BenchmarkArm),
            "power_analysis_reproduces_from_paired_runs": power_output
            == expected_power,
            "cost_effect_reproduces_from_paired_runs": cost_effect_output
            == expected_cost_effect,
            "power_target_is_monotonic": required_80 is not None
            and required_90 is not None
            and required_90 > required_80,
            "analysis_digests_bind_outputs": statistical_output["power_analysis_ref"][
                "digest_sha256"
            ]
            == canonical_sha256(power_output)
            and statistical_output["cost_effect_analysis_ref"]["digest_sha256"]
            == canonical_sha256(cost_effect_output),
            "mechanism_costs_not_interpreted_as_economic_evidence": not cost_effect_output[
                "recorded_monetary_cost_complete"
            ],
            "economic_plan_is_explicit_and_unpriced": cost_effect_output[
                "economic_evaluation_plan"
            ]["schema_version"]
            == "review-economic-evaluation-plan-v1"
            and cost_effect_output["economic_evaluation_plan"][
                "reviewer_time_value_usd_per_hour"
            ]
            is None
            and cost_effect_output["economic_evaluation_plan"][
                "delivery_delay_value_usd_per_hour"
            ]
            is None,
            "human_review_increment_is_paired": cost_effect_output["human_review"][
                "completed_pair_count"
            ]
            == 40
            and cost_effect_output["human_review"]["pair_coverage_complete"],
            "mechanism_human_sessions_do_not_count_as_real_evidence": not mechanism_human_status[
                "ready_for_incremental_economic_evaluation"
            ]
            and mechanism_human_status["integrity"]["non_observed_session_count"]
            == 80,
        }
        tampered_payload = result.model_dump(mode="json")
        tampered_payload["arm_metrics"][0]["false_clearance_count"] += 1
        tampered_result = BenchmarkResultV1.model_validate(tampered_payload)
        negative_checks = {
            "recomputation_detects_tampered_metric": tampered_result != rebuilt,
        }
        failed = sorted(
            name for name, passed in {**checks, **negative_checks}.items() if not passed
        )
        if failed:
            raise RuntimeError(f"benchmark metrics checks failed: {failed}")
        report = {
            "schema_version": "benchmark-metrics-verification-v1",
            "status": "pass",
            "checks": checks,
            "negative_checks": negative_checks,
            "methods": {
                "mcnemar": "two-sided exact on dangerous pairs",
                "rate_intervals": "95 percent Wilson score",
                "effect_interval": "paired bootstrap",
                "time_and_cost": "Wilcoxon signed-rank when nonzero differences exist",
                "power": "pilot-informed paired McNemar planning approximation",
                "cost_effect": (
                    "paired incremental safety, resource, opportunity-cost, and human-review "
                    "strategy deltas"
                ),
            },
            "claim_boundary": "Metric correctness does not establish an observed treatment effect.",
        }
        assert_safe_metadata(report, label="metrics report")
        return report


def reproducibility_report() -> dict[str, Any]:
    with TemporaryDirectory(prefix="delivery-clearance-reproducibility-") as temp:
        root = Path(temp)
        first, _ = _run_mechanism(root / "first")
        second, _ = _run_mechanism(root / "second")
        first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
        second_files = sorted(
            path.relative_to(second) for path in second.rglob("*") if path.is_file()
        )
        byte_identical = first_files == second_files and all(
            (first / relative).read_bytes() == (second / relative).read_bytes()
            for relative in first_files
        )

        resumed, _ = _run_mechanism(root / "resumed")
        run_path = resumed / "paired-runs.jsonl"
        original_lines = run_path.read_text(encoding="utf-8").splitlines()
        run_path.write_text("\n".join(original_lines[:7]) + "\n", encoding="utf-8")
        run_benchmark(resumed, resume=True)
        resumed_runs = _load_lines(run_path, PairedRunV1)
        resume_keys = [run.resume_key for run in resumed_runs]
        checks = {
            "fresh_runs_are_byte_identical": byte_identical,
            "fresh_runs_have_same_file_inventory": first_files == second_files,
            "resume_restores_40_paired_runs": len(resumed_runs) == 40,
            "resume_does_not_duplicate_trials": len(resume_keys) == len(set(resume_keys)),
            "resume_preserves_paired_run_bytes": run_path.read_bytes()
            == (first / "paired-runs.jsonl").read_bytes(),
        }
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            raise RuntimeError(f"benchmark reproducibility checks failed: {failed}")
        report = {
            "schema_version": "benchmark-reproducibility-verification-v1",
            "status": "pass",
            "artifact_file_count": len(first_files),
            "checks": checks,
            "claim_boundary": (
                "Deterministic mechanism artifacts are reproducible; model-provider runs require "
                "their own immutable trace provenance."
            ),
        }
        assert_safe_metadata(report, label="reproducibility report")
        return report


def claim_boundary_report() -> dict[str, Any]:
    with TemporaryDirectory(prefix="delivery-clearance-claim-boundary-") as temp:
        output, result = _run_mechanism(Path(temp))
        report_markdown = (output / "benchmark-report.md").read_text(encoding="utf-8")
        forged = result.model_dump(mode="json")
        forged["status"] = "pilot_complete"
        observed_claim_without_observation_rejected = _rejects(
            BenchmarkResultV1, forged, "pilot_complete requires observed Agent runs"
        )

        observed_case_dir = Path(temp) / "observed-cases"
        observed_candidate_dir = Path(temp) / "observed-candidates"
        observed_case_dir.mkdir()
        observed_candidate_dir.mkdir()
        observed_decisions: list[ReviewerDecisionV1] = []
        observed_traces: list[DecisionToolTraceV1] = []
        observed_provenance: list[ReviewExecutionProvenanceV1] = []
        observed_scorers: list[ScorerExecutionReceiptV1] = []
        observed_adjudications: list[BlindedAdjudicationReceiptV1] = []
        for case_index, (fixture_case, fixture_candidate) in enumerate(pilot_assets()):
            observed_environment_digest = canonical_sha256(
                {
                    "case_id": fixture_case.case_id,
                    "test_acquired_artifact_manifest": True,
                }
            )
            candidate_payload = fixture_candidate.model_dump(mode="json")
            candidate_payload.update(
                {
                    "evidence_origin": "observed_agent_run",
                    "source_snapshot_digest_sha256": observed_environment_digest,
                    "scorer_execution_origin": "observed_official_scorer",
                    "official_scorer_executed": True,
                }
            )
            scorer_payload = {
                "schema_version": "scorer-execution-receipt-v1",
                "receipt_id": f"scorer:{fixture_case.case_id}",
                "suite_id": fixture_case.suite_id,
                "case_id": fixture_case.case_id,
                "benchmark_id": fixture_case.source.benchmark_id.value,
                "upstream_task_id": fixture_case.source.upstream_task_id,
                "subject_digest_sha256": candidate_payload["subject_digest_sha256"],
                "source_environment_digest_sha256": observed_environment_digest,
                "scorer_source_uri": fixture_case.source.scorer_source_uri,
                "scorer_source_revision": fixture_case.source.scorer_source_revision,
                "official_scorer_ref": fixture_case.source.official_scorer_ref,
                "dependency_lock_digest_sha256": canonical_sha256(
                    {"case_id": fixture_case.case_id, "dependency_lock": "verifier-fixture"}
                ),
                "asset_manifest_digest_sha256": canonical_sha256(
                    {"case_id": fixture_case.case_id, "assets": "verifier-fixture"}
                ),
                "runtime_image_digests_sha256": [],
                "command_digest_sha256": canonical_sha256(
                    {"case_id": fixture_case.case_id, "command": "withheld"}
                ),
                "scorer_output_digest_sha256": canonical_sha256(
                    {"case_id": fixture_case.case_id, "output": "withheld"}
                ),
                "outcome": candidate_payload["scorer_outcome"],
                "numeric_reward": (
                    1.0
                    if candidate_payload["scorer_outcome"] == "passed"
                    else 0.0
                )
                if fixture_case.source.benchmark_id
                in {BenchmarkSource.TUA_BENCH, BenchmarkSource.TAU_BENCH}
                else None,
                "utility_passed": (
                    candidate_payload["scorer_outcome"] == "passed"
                    or candidate_payload["scorer_outcome"] == "security_violation"
                )
                if fixture_case.source.benchmark_id == BenchmarkSource.AGENTDOJO
                else None,
                "security_passed": (
                    candidate_payload["scorer_outcome"] != "security_violation"
                )
                if fixture_case.source.benchmark_id == BenchmarkSource.AGENTDOJO
                else None,
                "exit_code": 0,
                "official_scorer_executed": True,
                "started_at": "2026-07-12T00:00:00Z",
                "completed_at": "2026-07-12T00:00:01Z",
                "raw_scorer_output_included": False,
                "raw_hidden_tests_included": False,
                "privacy": candidate_payload["privacy"],
            }
            scorer = ScorerExecutionReceiptV1.model_validate(
                {
                    **scorer_payload,
                    "trace_digest_sha256": canonical_sha256(scorer_payload),
                }
            )
            observed_scorers.append(scorer)
            candidate_payload["scorer_trace_digest_sha256"] = scorer.trace_digest_sha256
            for evidence in candidate_payload["evidence"]:
                if evidence["evidence_type"] == "scorer-result":
                    evidence["evidence_ref"] = f"scorer-receipt:{scorer.receipt_id}"
                    evidence["evidence_digest_sha256"] = scorer.trace_digest_sha256
            observed_candidate = fixture_candidate.model_validate(candidate_payload)
            case_payload = fixture_case.model_dump(mode="json")
            case_payload["source"].update(
                {
                    "environment_digest_sha256": observed_environment_digest,
                    "environment_digest_basis": "acquired_artifact_digests",
                }
            )
            case_payload["candidate_digest_sha256"] = canonical_sha256(observed_candidate)
            adjudication_payload = {
                "schema_version": "blinded-adjudication-receipt-v1",
                "receipt_id": f"adjudication:{fixture_case.case_id}",
                "suite_id": fixture_case.suite_id,
                "case_id": fixture_case.case_id,
                "candidate_digest_sha256": canonical_sha256(observed_candidate),
                "scorer_receipt_digest_sha256": scorer.trace_digest_sha256,
                "adjudication_protocol_digest_sha256": canonical_sha256(
                    {"protocol": "verifier-blinded-adjudication-v1"}
                ),
                "disposition": case_payload["reference"]["disposition"],
                "release_authorized": case_payload["reference"]["release_authorized"],
                "maximum_scope": case_payload["reference"]["maximum_scope"],
                "rationale_codes": case_payload["reference"]["rationale_codes"],
                "adjudicator_role": "verifier-fixture-adjudicator",
                "qualification_scope": "personal_local",
                "arm_decisions_accessible": False,
                "arm_identities_accessible": False,
                "raw_adjudication_notes_included": False,
                "started_at": "2026-07-12T00:00:01Z",
                "completed_at": "2026-07-12T00:00:02Z",
                "privacy": candidate_payload["privacy"],
            }
            adjudication = BlindedAdjudicationReceiptV1.model_validate(
                {
                    **adjudication_payload,
                    "trace_digest_sha256": canonical_sha256(adjudication_payload),
                }
            )
            observed_adjudications.append(adjudication)
            case_payload["reference"].update(
                {
                    "adjudication_basis": (
                        "observed_official_scorer_plus_blinded_clearance_adjudication"
                    ),
                    "adjudication_trace_digest_sha256": adjudication.trace_digest_sha256,
                }
            )
            observed_case = fixture_case.model_validate(case_payload)
            (observed_case_dir / f"{fixture_case.case_id}.json").write_text(
                json.dumps(observed_case.model_dump(mode="json"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (observed_candidate_dir / f"{fixture_case.case_id}.json").write_text(
                json.dumps(observed_candidate.model_dump(mode="json"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            for arm in BenchmarkArm:
                decision = fixture_decision(
                    observed_case,
                    observed_candidate,
                    arm=arm,
                    case_index=case_index,
                    trial_index=0,
                )
                trace_payload = fixture_tool_trace(
                    observed_case,
                    observed_candidate,
                    arm=arm,
                    case_index=case_index,
                    trial_index=0,
                ).model_dump(mode="json")
                trace_payload.update(
                    {
                        "evidence_origin": "observed_agent_run",
                        "model_ref": "observed-test-model",
                        "model_version": "observed-test-version",
                    }
                )
                trace_payload.pop("trace_digest_sha256")
                observed_trace = DecisionToolTraceV1.model_validate(
                    {
                        **trace_payload,
                        "trace_digest_sha256": canonical_sha256(trace_payload),
                    }
                )
                observed_traces.append(observed_trace)
                payload = decision.model_dump(mode="json")
                payload.update(
                    {
                        "evidence_origin": "observed_agent_run",
                        "tool_trace_digest_sha256": observed_trace.trace_digest_sha256,
                        "model_ref": "observed-test-model",
                        "model_version": "observed-test-version",
                        "harness_ref": f"observed-test-harness:{decision.arm.value}",
                    }
                )
                provenance_payload = {
                    "schema_version": "review-execution-provenance-v1",
                    "decision_id": payload["decision_id"],
                    "suite_id": payload["suite_id"],
                    "case_id": payload["case_id"],
                    "trial_index": payload["trial_index"],
                    "arm": payload["arm"],
                    "evidence_origin": "observed_agent_run",
                    "candidate_digest_sha256": payload["candidate_digest_sha256"],
                    "context_digest_sha256": payload["context_digest_sha256"],
                    "model_ref": payload["model_ref"],
                    "model_version": payload["model_version"],
                    "harness_ref": payload["harness_ref"],
                    "arm_protocol_digest_sha256": canonical_sha256(
                        {"arm": payload["arm"], "verifier_fixture": True}
                    ),
                    "prompt_digest_sha256": canonical_sha256(
                        {"case_id": payload["case_id"], "prompt": "withheld"}
                    ),
                    "structured_response_digest_sha256": canonical_sha256(
                        {"decision_id": payload["decision_id"], "response": "withheld"}
                    ),
                    "workspace_identity_digest_sha256": canonical_sha256(
                        {"decision_id": payload["decision_id"], "workspace": "isolated"}
                    ),
                    "provider_thread_id_digest_sha256": canonical_sha256(
                        {"decision_id": payload["decision_id"], "thread": "withheld"}
                    ),
                    "event_stream_digest_sha256": canonical_sha256(
                        {"decision_id": payload["decision_id"], "events": "withheld"}
                    ),
                    "stderr_digest_sha256": canonical_sha256(
                        {"decision_id": payload["decision_id"], "stderr": "withheld"}
                    ),
                    "tool_trace_digest_sha256": observed_trace.trace_digest_sha256,
                    "budget": payload["budget"],
                    "usage": payload["usage"],
                    "cached_input_tokens": 0,
                    "reasoning_output_tokens": 0,
                    "cost_basis": "estimated",
                    "raw_prompt_included": False,
                    "raw_model_output_included": False,
                    "raw_event_stream_included": False,
                    "raw_stderr_included": False,
                    "privacy": payload["privacy"],
                }
                provenance = ReviewExecutionProvenanceV1.model_validate(
                    {
                        **provenance_payload,
                        "trace_digest_sha256": canonical_sha256(provenance_payload),
                    }
                )
                observed_provenance.append(provenance)
                payload["execution_trace_digest_sha256"] = provenance.trace_digest_sha256
                observed_decisions.append(ReviewerDecisionV1.model_validate(payload))
        observed_input = Path(temp) / "observed-decisions.jsonl"
        observed_input.write_text(
            "\n".join(
                json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
                for item in observed_decisions
            )
            + "\n",
            encoding="utf-8",
        )
        observed_trace_input = Path(temp) / "observed-tool-traces.jsonl"
        observed_trace_input.write_text(
            "\n".join(
                json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
                for item in observed_traces
            )
            + "\n",
            encoding="utf-8",
        )
        observed_provenance_input = Path(temp) / "observed-execution-provenance.jsonl"
        observed_provenance_input.write_text(
            "\n".join(
                json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
                for item in observed_provenance
            )
            + "\n",
            encoding="utf-8",
        )
        observed_scorer_input = Path(temp) / "observed-scorer-receipts.jsonl"
        observed_scorer_input.write_text(
            "\n".join(
                json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
                for item in observed_scorers
            )
            + "\n",
            encoding="utf-8",
        )
        observed_adjudication_input = Path(temp) / "observed-adjudication-receipts.jsonl"
        observed_adjudication_input.write_text(
            "\n".join(
                json.dumps(item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
                for item in observed_adjudications
            )
            + "\n",
            encoding="utf-8",
        )
        incomplete = run_benchmark(
            Path(temp) / "observed-incomplete",
            mode="observed",
            observed_case_dir=observed_case_dir,
            observed_candidate_dir=observed_candidate_dir,
            observed_decisions_path=observed_input,
            observed_tool_traces_path=observed_trace_input,
            observed_execution_provenance_path=observed_provenance_input,
            observed_scorer_receipts_path=observed_scorer_input,
            observed_adjudication_receipts_path=observed_adjudication_input,
        )
        checks = {
            "mechanism_status_is_not_pilot_complete": result.status
            == "mechanism_rehearsal_complete",
            "mechanism_banner_is_prominent": "MECHANISM REHEARSAL ONLY" in report_markdown,
            "maximum_scope_is_personal_local": result.claim_boundary.maximum_scope
            == DeliveryScope.PERSONAL_LOCAL,
            "observed_decisions_without_human_and_ablation_are_incomplete": incomplete.status
            == "pilot_incomplete",
            "confirmatory_significance_not_claimed": "confirmatory statistical significance"
            in result.claim_boundary.not_claimed,
            "customer_and_production_not_claimed": {
                "customer delivery validation",
                "production approval",
            }.issubset(set(result.claim_boundary.not_claimed)),
        }
        negative_checks = {
            "fixture_cannot_be_relabelled_pilot_complete": observed_claim_without_observation_rejected,
        }
        failed = sorted(
            name for name, passed in {**checks, **negative_checks}.items() if not passed
        )
        if failed:
            raise RuntimeError(f"benchmark claim-boundary checks failed: {failed}")
        report = {
            "schema_version": "benchmark-claim-boundary-verification-v1",
            "status": "pass",
            "checks": checks,
            "negative_checks": negative_checks,
            "allowed_v0_1_statement": (
                "The benchmark harness completed a reproducible 40-case mechanism rehearsal. "
                "Observed effect estimates remain pending."
            ),
            "prohibited_statement": "Delivery Clearance is proven effective for all AI delivery.",
        }
        assert_safe_metadata(report, label="claim boundary report")
        return report


def write_or_check_report(
    *,
    path: Path,
    build: Callable[[], dict[str, Any]],
    write: bool,
) -> dict[str, Any]:
    report = build()
    content = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    elif not path.is_file() or path.read_text(encoding="utf-8") != content:
        raise RuntimeError(f"verifier report is stale: {path.name}; run the verifier with --write")
    return report
