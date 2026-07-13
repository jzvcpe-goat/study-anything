#!/usr/bin/env python3
"""Run or record inputs for Native Agent vs Delivery Clearance Benchmark v0.1."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Literal


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.benchmark.models import (  # noqa: E402
    BenchmarkArm,
    BenchmarkSource,
    BlindedAdjudicationReceiptV1,
    HumanReviewSessionV1,
    ResourceBudgetV1,
    ReviewEconomicEvaluationPlanV1,
)
from study_anything.cbb.benchmark.economics import (  # noqa: E402
    default_review_economic_evaluation_plan,
    human_evidence_status as build_human_evidence_status,
)
from study_anything.cbb.benchmark.ablation import (  # noqa: E402
    ObservedAblationError,
    build_observed_ablation,
)
from study_anything.cbb.benchmark.adjudication import (  # noqa: E402
    BlindedAdjudicationError,
    load_blinded_adjudication_packet,
    materialize_observed_oracles,
    run_interactive_adjudication,
    validate_blinded_adjudication_receipt,
)
from study_anything.cbb.benchmark.human_reconstruction import (  # noqa: E402
    HumanReconstructionError,
    run_interactive_full_review,
    run_interactive_reconstruction,
)
from study_anything.cbb.benchmark.agentdojo_smoke import (  # noqa: E402
    AgentDojoScorerError,
    summarize_agentdojo_smoke,
    write_agentdojo_smoke,
)
from study_anything.cbb.benchmark.assembly import (  # noqa: E402
    ObservedSourceInput,
    assemble_observed_capture,
)
from study_anything.cbb.benchmark.observed_runtime import (  # noqa: E402
    CodexReviewerConfig,
    ObservedRuntimeError,
    capture_codex_reviews,
)
from study_anything.cbb.benchmark.runner import (  # noqa: E402
    BenchmarkRunnerError,
    record_human_review_session,
    run_benchmark,
)
from study_anything.cbb.benchmark.source_preflight import (  # noqa: E402
    SourcePreflightError,
    write_source_preflights,
)
from study_anything.cbb.benchmark.swe_smoke import (  # noqa: E402
    SweScorerError,
    run_swe_official_case,
    write_swe_smoke,
    write_swe_task_snapshot,
)
from study_anything.cbb.benchmark.tau_smoke import (  # noqa: E402
    TauScorerError,
    summarize_tau_smoke,
    write_tau_smoke,
)
from study_anything.cbb.benchmark.tua_smoke import (  # noqa: E402
    TuaHarborScorerError,
    write_tua_smoke,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    assert_safe_metadata,
    canonical_sha256,
)


DEFAULT_OUTPUT = ROOT / ".delivery-clearance" / "benchmarks" / "pilot-v0.1"
DEFAULT_CAPTURE_OUTPUT = ROOT / ".delivery-clearance" / "benchmarks" / "pilot-v0.1-observed-capture"
DEFAULT_CANDIDATE_DIR = (
    ROOT / "fixtures" / "delivery-clearance-benchmark" / "pilot-v0.1" / "candidates"
)
DEFAULT_PREFLIGHT_OUTPUT = (
    ROOT / ".delivery-clearance" / "benchmarks" / "pilot-v0.1" / "source-preflight"
)
DEFAULT_PUBLIC_SOURCE_ROOT = Path("/tmp/delivery-clearance-public-sources")
DEFAULT_AGENTDOJO_SMOKE_OUTPUT = (
    ROOT / ".delivery-clearance" / "benchmarks" / "pilot-v0.1-agentdojo-scorer-smoke"
)
DEFAULT_TAU_SMOKE_OUTPUT = (
    ROOT / ".delivery-clearance" / "benchmarks" / "pilot-v0.1-tau-scorer-smoke"
)
DEFAULT_TUA_SMOKE_OUTPUT = (
    ROOT / ".delivery-clearance" / "benchmarks" / "pilot-v0.1-tua-scorer-smoke"
)
DEFAULT_SWE_SMOKE_OUTPUT = (
    ROOT / ".delivery-clearance" / "benchmarks" / "pilot-v0.1-swe-scorer-smoke"
)
DEFAULT_ECONOMIC_PLAN_OUTPUT = (
    ROOT
    / ".delivery-clearance"
    / "benchmarks"
    / "pilot-v0.1-economic-evaluation-plan.json"
)


def _parse_arms(value: str) -> tuple[BenchmarkArm, ...]:
    try:
        arms = tuple(BenchmarkArm(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if set(arms) != set(BenchmarkArm) or len(arms) != len(BenchmarkArm):
        raise argparse.ArgumentTypeError("v0.1 requires each of the four arms exactly once")
    return arms


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _run(args: argparse.Namespace) -> int:
    if args.suite != "pilot-v0.1":
        raise BenchmarkRunnerError("only pilot-v0.1 is available")
    _parse_arms(args.arms)
    economic_plan = None
    if args.economic_plan:
        economic_payload = json.loads(Path(args.economic_plan).read_text(encoding="utf-8"))
        assert_safe_metadata(economic_payload, label="review economic evaluation plan")
        economic_plan = ReviewEconomicEvaluationPlanV1.model_validate(economic_payload)
    result = run_benchmark(
        Path(args.out),
        trials=args.trials,
        resume=args.resume,
        mode=args.mode,
        observed_case_dir=(Path(args.observed_cases) if args.observed_cases else None),
        observed_candidate_dir=(
            Path(args.observed_candidates) if args.observed_candidates else None
        ),
        observed_decisions_path=(
            Path(args.observed_decisions) if args.observed_decisions else None
        ),
        observed_tool_traces_path=(
            Path(args.observed_tool_traces) if args.observed_tool_traces else None
        ),
        observed_execution_provenance_path=(
            Path(args.observed_execution_provenance) if args.observed_execution_provenance else None
        ),
        observed_scorer_receipts_path=(
            Path(args.observed_scorer_receipts) if args.observed_scorer_receipts else None
        ),
        observed_adjudication_receipts_path=(
            Path(args.observed_adjudication_receipts)
            if args.observed_adjudication_receipts
            else None
        ),
        observed_human_sessions_path=(
            Path(args.observed_human_sessions) if args.observed_human_sessions else None
        ),
        observed_ablation_path=(Path(args.observed_ablation) if args.observed_ablation else None),
        economic_plan=economic_plan,
    )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _append_session(path: Path, session: HumanReviewSessionV1) -> None:
    existing = _existing_human_sessions(path)
    if session.session_id in existing:
        raise BenchmarkRunnerError("human review session already exists; use batch --resume")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                session.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())


def _review(args: argparse.Namespace) -> int:
    question_set_digest_sha256 = None
    collection_method: Literal[
        "interactive_scored_boundary",
        "interactive_full_review",
        "external_observed_measurement",
    ] = "external_observed_measurement"
    candidate_digest_sha256: str
    review_material_digest_sha256: str
    if args.non_interactive:
        if args.review_mode == "boundary_reconstruction":
            raise BenchmarkRunnerError(
                "boundary reconstruction must use the interactive scored flow"
            )
        required = {
            "active_review_ms": args.active_review_ms,
            "correct_answers": args.correct_answers,
            "unresolved_questions": args.unresolved_questions,
            "candidate_digest": args.candidate_digest,
            "review_material_digest": args.review_material_digest,
        }
        missing = sorted(name for name, value in required.items() if value is None)
        if missing:
            raise BenchmarkRunnerError("non-interactive review is missing: " + ", ".join(missing))
        active_review_ms = int(args.active_review_ms)
        correct_answers = int(args.correct_answers)
        unresolved_questions = int(args.unresolved_questions)
        candidate_digest_sha256 = str(args.candidate_digest)
        review_material_digest_sha256 = str(args.review_material_digest)
    else:
        if not args.packet:
            raise BenchmarkRunnerError("interactive human review requires --packet")
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
        if packet.get("case_id") != args.case_id:
            raise BenchmarkRunnerError("human review packet case ID drifted")
        review_flow = (
            run_interactive_reconstruction
            if args.review_mode == "boundary_reconstruction"
            else run_interactive_full_review
        )
        (
            active_review_ms,
            correct_answers,
            unresolved_questions,
            question_set_digest_sha256,
        ) = review_flow(packet)
        candidate_view = packet.get("candidate")
        if not isinstance(candidate_view, dict) or not isinstance(
            candidate_view.get("candidate_digest_sha256"), str
        ):
            raise BenchmarkRunnerError("human review packet has no candidate digest")
        candidate_digest_sha256 = str(candidate_view["candidate_digest_sha256"])
        review_material_digest_sha256 = canonical_sha256(packet)
        collection_method = (
            "interactive_scored_boundary"
            if args.review_mode == "boundary_reconstruction"
            else "interactive_full_review"
        )

    completed_at = args.completed_at or datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    session = record_human_review_session(
        case_id=args.case_id,
        trial_index=args.trial_index,
        review_mode=args.review_mode,
        reviewer_role=args.reviewer_role,
        active_review_ms=active_review_ms,
        correct_answers=correct_answers,
        unresolved_questions=unresolved_questions,
        nasa_tlx_score=args.nasa_tlx,
        completed_at=completed_at,
        candidate_digest_sha256=candidate_digest_sha256,
        review_material_digest_sha256=review_material_digest_sha256,
        collection_method=collection_method,
        question_set_digest_sha256=question_set_digest_sha256,
    )
    _append_session(Path(args.output), session)
    print(json.dumps(session.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _load_review_packets(packet_dirs: list[str]) -> dict[str, dict[str, object]]:
    packets: dict[str, dict[str, object]] = {}
    for directory_value in packet_dirs:
        directory = Path(directory_value)
        if not directory.is_dir():
            raise BenchmarkRunnerError("review packet directory does not exist")
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise BenchmarkRunnerError("human review packet must be a JSON object")
            assert_safe_metadata(payload, label="batch human reconstruction packet")
            case_id = payload.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise BenchmarkRunnerError("human review packet is missing its case ID")
            if case_id in packets:
                raise BenchmarkRunnerError("duplicate human review packet case ID")
            if (
                payload.get("reference_label_included") is not False
                or payload.get("hidden_tests_included") is not False
                or payload.get("official_scorer_result_included") is not False
            ):
                raise BenchmarkRunnerError("human review packet is not label-free")
            packets[case_id] = payload
    if not packets:
        raise BenchmarkRunnerError("no human review packets were found")
    return packets


def _existing_human_sessions(path: Path) -> dict[str, HumanReviewSessionV1]:
    if not path.is_file():
        return {}
    sessions: dict[str, HumanReviewSessionV1] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if line.strip():
            session = HumanReviewSessionV1.model_validate(json.loads(line))
            if session.session_id in sessions:
                raise BenchmarkRunnerError(
                    f"duplicate human review session at line {line_number}"
                )
            sessions[session.session_id] = session
    return sessions


def _init_economic_plan(args: argparse.Namespace) -> int:
    plan_payload = default_review_economic_evaluation_plan().model_dump(mode="json")
    plan_payload.update(
        {
            "price_date": args.price_date,
            "reviewer_time_value_usd_per_hour": (
                args.reviewer_time_value_usd_per_hour
            ),
            "delivery_delay_value_usd_per_hour": (
                args.delivery_delay_value_usd_per_hour
            ),
            "willingness_to_pay_per_false_clearance_avoided_usd": (
                args.willingness_to_pay_per_false_clearance_avoided_usd
            ),
            "max_acceptable_false_block_rate_increase": (
                args.max_acceptable_false_block_rate_increase
            ),
            "minimum_acceptable_boundary_accuracy_difference": (
                args.minimum_acceptable_boundary_accuracy_difference
            ),
        }
    )
    plan = ReviewEconomicEvaluationPlanV1.model_validate(plan_payload)
    output = Path(args.output)
    if output.exists() and not args.force:
        raise BenchmarkRunnerError("economic evaluation plan exists; use --force to replace it")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            plan.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _human_evidence_status(args: argparse.Namespace) -> int:
    packets = _load_review_packets(args.packet_dir)
    sessions = list(_existing_human_sessions(Path(args.human_sessions)).values())
    adjudications = list(
        _existing_adjudications(Path(args.adjudications)).values()
    )
    report = build_human_evidence_status(
        list(packets),
        sessions,
        adjudications,
        trial_index=args.trial_index,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _existing_adjudications(
    path: Path,
) -> dict[str, BlindedAdjudicationReceiptV1]:
    if not path.is_file():
        return {}
    receipts: dict[str, BlindedAdjudicationReceiptV1] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        receipt = validate_blinded_adjudication_receipt(
            BlindedAdjudicationReceiptV1.model_validate(json.loads(line))
        )
        if receipt.receipt_id in receipts:
            raise BenchmarkRunnerError(
                f"duplicate adjudication receipt at line {line_number}"
            )
        receipts[receipt.receipt_id] = receipt
    return receipts


def _append_adjudication(
    path: Path, receipt: BlindedAdjudicationReceiptV1
) -> None:
    receipt = validate_blinded_adjudication_receipt(receipt)
    existing = _existing_adjudications(path)
    if receipt.receipt_id in existing:
        raise BenchmarkRunnerError(
            "blinded adjudication already exists; use batch --resume"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                receipt.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())


def _load_adjudication_packets(packet_dirs: list[str]) -> dict[str, dict[str, object]]:
    packets: dict[str, dict[str, object]] = {}
    for directory_value in packet_dirs:
        directory = Path(directory_value)
        if not directory.is_dir():
            raise BenchmarkRunnerError("adjudication packet directory does not exist")
        for path in sorted(directory.glob("*.json")):
            payload = load_blinded_adjudication_packet(path)
            case_id = payload.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                raise BenchmarkRunnerError("adjudication packet has no case ID")
            if case_id in packets:
                raise BenchmarkRunnerError("duplicate adjudication packet case ID")
            packets[case_id] = payload
    if not packets:
        raise BenchmarkRunnerError("no blinded adjudication packets were found")
    return packets


def _adjudicate(args: argparse.Namespace) -> int:
    packet = load_blinded_adjudication_packet(Path(args.packet))
    receipt = run_interactive_adjudication(
        packet,
        adjudicator_role=args.adjudicator_role,
    )
    _append_adjudication(Path(args.output), receipt)
    print(json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _adjudicate_batch(args: argparse.Namespace) -> int:
    packets = _load_adjudication_packets(args.packet_dir)
    requested = list(dict.fromkeys(args.case_id or packets))
    missing = sorted(set(requested) - set(packets))
    if missing:
        raise BenchmarkRunnerError(
            "requested adjudication packets are missing: " + ", ".join(missing)
        )
    order_seed_digest = sha256(args.order_seed.encode("utf-8")).hexdigest()
    ordered_case_ids = sorted(
        requested,
        key=lambda case_id: sha256(
            f"{args.order_seed}:{case_id}".encode("utf-8")
        ).hexdigest(),
    )
    output = Path(args.output)
    existing = _existing_adjudications(output)
    pending: list[str] = []
    skipped = 0
    for case_id in ordered_case_ids:
        receipt_id = f"adjudication:{case_id}:0"
        if receipt_id not in existing:
            pending.append(case_id)
        elif args.resume:
            skipped += 1
        else:
            raise BenchmarkRunnerError(
                "batch already contains a matching adjudication; use --resume to skip it"
            )

    pending_before_run = len(pending)
    if args.max_items is not None:
        pending = pending[: args.max_items]
    pending_after_run = pending_before_run - len(pending)

    print(
        "Starting arm-blinded clearance adjudication: "
        f"{len(pending)} selected, {pending_before_run} pending, "
        f"{skipped} previously recorded."
    )
    print("Case IDs, arm identities, and arm decisions are hidden during the flow.")
    completed = 0
    for batch_index, case_id in enumerate(pending, start=1):
        receipt = run_interactive_adjudication(
            packets[case_id],
            adjudicator_role=args.adjudicator_role,
            display_label=f"blinded-item-{batch_index}-of-{len(pending)}",
        )
        _append_adjudication(output, receipt)
        completed += 1
        print(f"Recorded blinded adjudication {batch_index} of {len(pending)}.")

    summary = {
        "schema_version": "blinded-adjudication-batch-summary-v1",
        "status": "complete" if pending_after_run == 0 else "partial",
        "requested_adjudication_count": len(ordered_case_ids),
        "completed_this_run": completed,
        "previously_recorded_count": skipped,
        "pending_before_run": pending_before_run,
        "pending_after_run": pending_after_run,
        "max_items": args.max_items,
        "order_seed_digest_sha256": order_seed_digest,
        "arm_decisions_accessible": False,
        "arm_identities_accessible": False,
        "maximum_authority": "personal_local",
        "efficacy_claim_allowed": False,
    }
    assert_safe_metadata(summary, label="blinded adjudication batch summary")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _materialize_observed_oracle(args: argparse.Namespace) -> int:
    manifest = materialize_observed_oracles(
        Path(args.assembly),
        Path(args.adjudications),
        Path(args.output),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_observed_ablation(args: argparse.Namespace) -> int:
    manifest = build_observed_ablation(
        Path(args.assembly),
        Path(args.human_sessions),
        Path(args.output),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _review_batch(args: argparse.Namespace) -> int:
    review_mode: Literal["full_review_reference", "boundary_reconstruction"] = (
        args.review_mode
    )
    if review_mode == "boundary_reconstruction":
        review_flow = run_interactive_reconstruction
        collection_method: Literal[
            "interactive_scored_boundary", "interactive_full_review"
        ] = "interactive_scored_boundary"
        flow_label = "blinded boundary reconstruction"
    else:
        review_flow = run_interactive_full_review
        collection_method = "interactive_full_review"
        flow_label = "blinded full-review reference"
    packets = _load_review_packets(args.packet_dir)
    requested = list(dict.fromkeys(args.case_id or packets))
    missing = sorted(set(requested) - set(packets))
    if missing:
        raise BenchmarkRunnerError(
            "requested human review packets are missing: " + ", ".join(missing)
        )
    order_seed_digest = sha256(args.order_seed.encode("utf-8")).hexdigest()
    ordered_case_ids = sorted(
        requested,
        key=lambda case_id: sha256(f"{args.order_seed}:{case_id}".encode("utf-8")).hexdigest(),
    )
    output = Path(args.output)
    existing = _existing_human_sessions(output)
    pending: list[str] = []
    skipped = 0
    for case_id in ordered_case_ids:
        session_id = f"review:{case_id}:{args.trial_index}:{review_mode}"
        if session_id not in existing:
            pending.append(case_id)
        elif args.resume:
            skipped += 1
        else:
            raise BenchmarkRunnerError(
                "batch already contains a matching session; use --resume to skip it"
            )

    pending_before_run = len(pending)
    if args.max_items is not None:
        pending = pending[: args.max_items]
    pending_after_run = pending_before_run - len(pending)

    print(
        f"Starting {flow_label}: "
        f"{len(pending)} selected, {pending_before_run} pending, "
        f"{skipped} previously recorded."
    )
    print("Case IDs and reference labels are hidden during the question flow.")
    completed = 0
    for batch_index, case_id in enumerate(pending, start=1):
        packet = packets[case_id]
        (
            active_review_ms,
            correct_answers,
            unresolved_questions,
            question_set_digest_sha256,
        ) = review_flow(
            packet,
            display_label=f"blinded-item-{batch_index}-of-{len(pending)}",
        )
        completed_at = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        candidate_view = packet.get("candidate")
        if not isinstance(candidate_view, dict) or not isinstance(
            candidate_view.get("candidate_digest_sha256"), str
        ):
            raise BenchmarkRunnerError("human review packet has no candidate digest")
        session = record_human_review_session(
            case_id=case_id,
            trial_index=args.trial_index,
            review_mode=review_mode,
            reviewer_role=args.reviewer_role,
            active_review_ms=active_review_ms,
            correct_answers=correct_answers,
            unresolved_questions=unresolved_questions,
            nasa_tlx_score=args.nasa_tlx,
            completed_at=completed_at,
            candidate_digest_sha256=str(candidate_view["candidate_digest_sha256"]),
            review_material_digest_sha256=canonical_sha256(packet),
            collection_method=collection_method,
            question_set_digest_sha256=question_set_digest_sha256,
        )
        _append_session(output, session)
        completed += 1
        print(f"Recorded blinded item {batch_index} of {len(pending)}.")

    summary = {
        "schema_version": "human-review-batch-summary-v1",
        "status": "complete" if pending_after_run == 0 else "partial",
        "review_mode": review_mode,
        "requested_session_count": len(ordered_case_ids),
        "completed_this_run": completed,
        "previously_recorded_count": skipped,
        "pending_before_run": pending_before_run,
        "pending_after_run": pending_after_run,
        "max_items": args.max_items,
        "order_seed_digest_sha256": order_seed_digest,
        "blinded_order_digest_sha256": canonical_sha256(
            {"order_seed_digest_sha256": order_seed_digest, "case_ids": ordered_case_ids}
        ),
        "raw_answers_included": False,
        "reference_labels_included": False,
        "maximum_scope": "personal_local",
        "claim_boundary": (
            f"This summary proves aggregate-only {review_mode} collection. It is not customer "
            "clearance, production approval, or evidence that the 40-case pilot is complete."
        ),
    }
    assert_safe_metadata(summary, label="human review batch summary")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _capture(args: argparse.Namespace) -> int:
    if args.all_cases and args.case_id:
        raise BenchmarkRunnerError("use --all-cases or --case-id, not both")
    candidate_dir = Path(args.candidate_dir)
    if args.all_cases:
        case_ids = sorted(path.stem for path in candidate_dir.glob("*.json"))
    else:
        case_ids = list(args.case_id or [])
    if not case_ids:
        raise BenchmarkRunnerError(
            "capture requires at least one --case-id; use --all-cases only for an intentional full run"
        )
    budget = ResourceBudgetV1(
        max_input_tokens=args.max_input_tokens,
        max_output_tokens=args.max_output_tokens,
        max_tool_calls=args.max_tool_calls,
        max_wall_time_ms=args.timeout_seconds * 1000,
        max_cost_usd=0.0,
    )
    manifest = capture_codex_reviews(
        packet_dir=Path(args.packet_dir),
        candidate_dir=candidate_dir,
        output_dir=Path(args.output),
        config=CodexReviewerConfig(
            executable=args.codex_bin,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout_seconds=args.timeout_seconds,
            budget=budget,
        ),
        case_ids=case_ids,
        trials=args.trials,
        human_sessions_path=(Path(args.human_sessions) if args.human_sessions else None),
        resume=args.resume,
        max_attempts_per_decision=args.max_attempts_per_decision,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _assemble_observed(args: argparse.Namespace) -> int:
    manifest = assemble_observed_capture(
        Path(args.output),
        sources=(
            ObservedSourceInput(
                benchmark_id=BenchmarkSource.AGENTDOJO,
                bundle_dir=Path(args.agentdojo_bundle),
                capture_dir=Path(args.agentdojo_capture),
            ),
            ObservedSourceInput(
                benchmark_id=BenchmarkSource.TAU_BENCH,
                bundle_dir=Path(args.tau_bundle),
                capture_dir=Path(args.tau_capture),
            ),
            ObservedSourceInput(
                benchmark_id=BenchmarkSource.TUA_BENCH,
                bundle_dir=Path(args.tua_bundle),
                capture_dir=Path(args.tua_capture),
            ),
            ObservedSourceInput(
                benchmark_id=BenchmarkSource.SWE_BENCH_LIVE,
                bundle_dir=Path(args.swe_bundle),
                capture_dir=Path(args.swe_capture),
            ),
        ),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _preflight(args: argparse.Namespace) -> int:
    source_values = args.source or [source.value for source in BenchmarkSource]
    sources = [BenchmarkSource(value) for value in source_values]
    manifest = write_source_preflights(
        Path(args.output),
        source_root=Path(args.source_root),
        benchmark_ids=sources,
        swe_task_data_root=(Path(args.swe_task_data_root) if args.swe_task_data_root else None),
        generated_at=args.generated_at,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _score_agentdojo(args: argparse.Namespace) -> int:
    manifest = write_agentdojo_smoke(
        Path(args.output),
        checkout=Path(args.checkout),
        case_ids=list(dict.fromkeys(args.case_id)),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summarize_agentdojo(args: argparse.Namespace) -> int:
    report = summarize_agentdojo_smoke(
        Path(args.smoke_dir),
        review_capture_dir=Path(args.review_capture_dir),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _score_tau(args: argparse.Namespace) -> int:
    manifest = write_tau_smoke(
        Path(args.output),
        checkout=Path(args.checkout),
        case_ids=list(dict.fromkeys(args.case_id)),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summarize_tau(args: argparse.Namespace) -> int:
    report = summarize_tau_smoke(
        Path(args.smoke_dir),
        review_capture_dir=Path(args.review_capture_dir),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _case_job(value: str) -> tuple[str, Path]:
    case_id, separator, raw_path = value.partition("=")
    if not separator or case_id not in {f"tua-{index:02d}" for index in range(1, 11)}:
        raise argparse.ArgumentTypeError("case job must use tua-NN=/absolute/job/path")
    path = Path(raw_path)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("TUA Harbor job path must be absolute")
    return case_id, path


def _score_tua(args: argparse.Namespace) -> int:
    case_jobs: dict[str, Path] = {}
    for case_id, job_path in args.case_job:
        if case_id in case_jobs:
            raise TuaHarborScorerError(f"duplicate TUA case job: {case_id}")
        case_jobs[case_id] = job_path
    manifest = write_tua_smoke(
        Path(args.output),
        checkout=Path(args.checkout),
        case_jobs=case_jobs,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _prepare_swe_data(args: argparse.Namespace) -> int:
    provenance = write_swe_task_snapshot(
        Path(args.output),
        metadata_payload_path=Path(args.metadata_response),
        rows_payload_path=Path(args.rows_response),
    )
    print(json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _swe_case_evaluation(value: str) -> tuple[str, Path]:
    case_id, separator, raw_path = value.partition("=")
    if not separator or case_id not in {f"swe-{index:02d}" for index in range(1, 13)}:
        raise argparse.ArgumentTypeError(
            "case evaluation must use swe-NN=/absolute/evaluation/path"
        )
    path = Path(raw_path)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("SWE evaluation path must be absolute")
    return case_id, path


def _score_swe(args: argparse.Namespace) -> int:
    case_evaluations: dict[str, Path] = {}
    for case_id, evaluation_path in args.case_evaluation:
        if case_id in case_evaluations:
            raise SweScorerError(f"duplicate SWE case evaluation: {case_id}")
        case_evaluations[case_id] = evaluation_path
    manifest = write_swe_smoke(
        Path(args.output),
        checkout=Path(args.checkout),
        task_data_root=Path(args.task_data_root),
        case_evaluations=case_evaluations,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _run_swe(args: argparse.Namespace) -> int:
    provenance = run_swe_official_case(
        args.case_id,
        checkout=Path(args.checkout),
        task_data_root=Path(args.task_data_root),
        evaluation_dir=Path(args.output),
        runtime_image_source_ref=args.runtime_image_source_ref,
        runtime_image_source_digest_sha256=args.runtime_image_source_digest_sha256,
        runtime_image_ref=args.runtime_image_ref,
    )
    print(json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run or import one paired pilot")
    run_parser.add_argument("--suite", default="pilot-v0.1")
    run_parser.add_argument(
        "--arms",
        default="native,strengthened,internal-checklist,external-clearance",
    )
    run_parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    run_parser.add_argument("--trials", type=int, default=1)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument(
        "--mode", choices=("mechanism-fixture", "observed"), default="mechanism-fixture"
    )
    run_parser.add_argument("--observed-cases")
    run_parser.add_argument("--observed-candidates")
    run_parser.add_argument("--observed-decisions")
    run_parser.add_argument("--observed-tool-traces")
    run_parser.add_argument("--observed-execution-provenance")
    run_parser.add_argument("--observed-scorer-receipts")
    run_parser.add_argument("--observed-adjudication-receipts")
    run_parser.add_argument("--observed-human-sessions")
    run_parser.add_argument("--observed-ablation")
    run_parser.add_argument(
        "--economic-plan",
        help="review-economic-evaluation-plan-v1 JSON; defaults to unpriced resource use",
    )
    run_parser.set_defaults(func=_run)

    economic_plan_parser = subparsers.add_parser(
        "init-economic-plan",
        help="write a personal-local incremental review economic evaluation plan",
    )
    economic_plan_parser.add_argument(
        "--output",
        default=str(DEFAULT_ECONOMIC_PLAN_OUTPUT),
    )
    economic_plan_parser.add_argument("--price-date")
    economic_plan_parser.add_argument(
        "--reviewer-time-value-usd-per-hour",
        type=float,
    )
    economic_plan_parser.add_argument(
        "--delivery-delay-value-usd-per-hour",
        type=float,
    )
    economic_plan_parser.add_argument(
        "--willingness-to-pay-per-false-clearance-avoided-usd",
        type=float,
    )
    economic_plan_parser.add_argument(
        "--max-acceptable-false-block-rate-increase",
        type=float,
        default=0.05,
    )
    economic_plan_parser.add_argument(
        "--minimum-acceptable-boundary-accuracy-difference",
        type=float,
        default=-0.05,
    )
    economic_plan_parser.add_argument("--force", action="store_true")
    economic_plan_parser.set_defaults(func=_init_economic_plan)

    review_parser = subparsers.add_parser(
        "review", help="record one five-boundary human reconstruction session"
    )
    review_parser.add_argument("--case-id", required=True)
    review_parser.add_argument("--trial-index", type=int, default=0)
    review_parser.add_argument(
        "--review-mode",
        choices=("full_review_reference", "boundary_reconstruction"),
        required=True,
    )
    review_parser.add_argument("--reviewer-role", required=True)
    review_parser.add_argument("--output", required=True)
    review_parser.add_argument("--nasa-tlx", type=float)
    review_parser.add_argument("--completed-at")
    review_parser.add_argument("--packet")
    review_parser.add_argument("--non-interactive", action="store_true")
    review_parser.add_argument("--active-review-ms", type=int)
    review_parser.add_argument("--correct-answers", type=int)
    review_parser.add_argument("--unresolved-questions", type=int)
    review_parser.add_argument("--candidate-digest")
    review_parser.add_argument("--review-material-digest")
    review_parser.set_defaults(func=_review)

    batch_review_parser = subparsers.add_parser(
        "review-batch",
        help="run a blinded, resumable batch of five-boundary human reconstructions",
    )
    batch_review_parser.add_argument("--packet-dir", action="append", required=True)
    batch_review_parser.add_argument("--case-id", action="append")
    batch_review_parser.add_argument("--trial-index", type=int, default=0)
    batch_review_parser.add_argument(
        "--review-mode",
        choices=("full_review_reference", "boundary_reconstruction"),
        default="boundary_reconstruction",
    )
    batch_review_parser.add_argument("--reviewer-role", required=True)
    batch_review_parser.add_argument("--output", required=True)
    batch_review_parser.add_argument("--order-seed", required=True)
    batch_review_parser.add_argument("--nasa-tlx", type=float)
    batch_review_parser.add_argument(
        "--max-items",
        type=_positive_int,
        help="process at most this many pending blinded items in the current run",
    )
    batch_review_parser.add_argument("--resume", action="store_true")
    batch_review_parser.set_defaults(func=_review_batch)

    human_status_parser = subparsers.add_parser(
        "human-evidence-status",
        help="check real boundary, full-review, and blinded-adjudication coverage",
    )
    human_status_parser.add_argument("--packet-dir", action="append", required=True)
    human_status_parser.add_argument("--human-sessions", required=True)
    human_status_parser.add_argument("--adjudications", required=True)
    human_status_parser.add_argument("--trial-index", type=int, default=0)
    human_status_parser.add_argument("--output")
    human_status_parser.set_defaults(func=_human_evidence_status)

    adjudicate_parser = subparsers.add_parser(
        "adjudicate",
        help="record one arm-blinded human clearance adjudication",
    )
    adjudicate_parser.add_argument("--packet", required=True)
    adjudicate_parser.add_argument("--adjudicator-role", required=True)
    adjudicate_parser.add_argument("--output", required=True)
    adjudicate_parser.set_defaults(func=_adjudicate)

    adjudicate_batch_parser = subparsers.add_parser(
        "adjudicate-batch",
        help="run a randomized, arm-blinded, resumable human adjudication batch",
    )
    adjudicate_batch_parser.add_argument("--packet-dir", action="append", required=True)
    adjudicate_batch_parser.add_argument("--case-id", action="append")
    adjudicate_batch_parser.add_argument("--adjudicator-role", required=True)
    adjudicate_batch_parser.add_argument("--output", required=True)
    adjudicate_batch_parser.add_argument("--order-seed", required=True)
    adjudicate_batch_parser.add_argument(
        "--max-items",
        type=_positive_int,
        help="process at most this many pending blinded items in the current run",
    )
    adjudicate_batch_parser.add_argument("--resume", action="store_true")
    adjudicate_batch_parser.set_defaults(func=_adjudicate_batch)

    materialize_oracle_parser = subparsers.add_parser(
        "materialize-observed-oracle",
        help="bind complete blinded adjudications into the frozen 40-case observed oracle",
    )
    materialize_oracle_parser.add_argument("--assembly", required=True)
    materialize_oracle_parser.add_argument("--adjudications", required=True)
    materialize_oracle_parser.add_argument("--output", required=True)
    materialize_oracle_parser.set_defaults(func=_materialize_observed_oracle)

    observed_ablation_parser = subparsers.add_parser(
        "build-observed-ablation",
        help="replay six trace-bound component policies over the observed pilot evidence",
    )
    observed_ablation_parser.add_argument("--assembly", required=True)
    observed_ablation_parser.add_argument("--human-sessions", required=True)
    observed_ablation_parser.add_argument("--output", required=True)
    observed_ablation_parser.set_defaults(func=_build_observed_ablation)

    capture_parser = subparsers.add_parser(
        "capture",
        help="capture pinned real Codex reviewer executions without claiming pilot completion",
    )
    capture_parser.add_argument("--packet-dir", default=str(DEFAULT_OUTPUT / "cases"))
    capture_parser.add_argument("--candidate-dir", default=str(DEFAULT_CANDIDATE_DIR))
    capture_parser.add_argument("--output", default=str(DEFAULT_CAPTURE_OUTPUT))
    capture_parser.add_argument("--model", required=True)
    capture_parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh"),
        default="low",
    )
    capture_parser.add_argument("--codex-bin", default="codex")
    capture_parser.add_argument("--case-id", action="append")
    capture_parser.add_argument("--all-cases", action="store_true")
    capture_parser.add_argument("--trials", type=int, default=1)
    capture_parser.add_argument("--timeout-seconds", type=int, default=120)
    capture_parser.add_argument("--max-input-tokens", type=int, default=128_000)
    capture_parser.add_argument("--max-output-tokens", type=int, default=4_000)
    capture_parser.add_argument("--max-tool-calls", type=int, default=12)
    capture_parser.add_argument("--human-sessions")
    capture_parser.add_argument("--resume", action="store_true")
    capture_parser.add_argument(
        "--max-attempts-per-decision",
        type=int,
        default=1,
        help="explicit cap including the first execution; default does not retry failed decisions",
    )
    capture_parser.set_defaults(func=_capture)

    assemble_parser = subparsers.add_parser(
        "assemble-observed",
        help="bind four public scorer bundles and their reviewer captures into one audit set",
    )
    assemble_parser.add_argument("--agentdojo-bundle", required=True)
    assemble_parser.add_argument("--agentdojo-capture", required=True)
    assemble_parser.add_argument("--tau-bundle", required=True)
    assemble_parser.add_argument("--tau-capture", required=True)
    assemble_parser.add_argument("--tua-bundle", required=True)
    assemble_parser.add_argument("--tua-capture", required=True)
    assemble_parser.add_argument("--swe-bundle", required=True)
    assemble_parser.add_argument("--swe-capture", required=True)
    assemble_parser.add_argument("--output", required=True)
    assemble_parser.set_defaults(func=_assemble_observed)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="verify pinned public sources and scorer prerequisites without running scorers",
    )
    preflight_parser.add_argument("--source-root", default=str(DEFAULT_PUBLIC_SOURCE_ROOT))
    preflight_parser.add_argument("--output", default=str(DEFAULT_PREFLIGHT_OUTPUT))
    preflight_parser.add_argument(
        "--source",
        action="append",
        choices=[source.value for source in BenchmarkSource],
    )
    preflight_parser.add_argument("--swe-task-data-root")
    preflight_parser.add_argument("--generated-at")
    preflight_parser.set_defaults(func=_preflight)

    scorer_parser = subparsers.add_parser(
        "score-agentdojo",
        help="run pinned AgentDojo scorers for preregistered fixed-candidate smoke cases",
    )
    scorer_parser.add_argument(
        "--checkout",
        default=str(DEFAULT_PUBLIC_SOURCE_ROOT / "agentdojo"),
    )
    scorer_parser.add_argument("--output", default=str(DEFAULT_AGENTDOJO_SMOKE_OUTPUT))
    scorer_parser.add_argument(
        "--case-id",
        action="append",
        choices=[f"dojo-{index:02d}" for index in range(1, 9)],
        required=True,
    )
    scorer_parser.set_defaults(func=_score_agentdojo)

    summarize_parser = subparsers.add_parser(
        "summarize-agentdojo",
        help="summarize the bounded 8-case scorer-backed reviewer smoke",
    )
    summarize_parser.add_argument("--smoke-dir", required=True)
    summarize_parser.add_argument("--review-capture-dir", required=True)
    summarize_parser.set_defaults(func=_summarize_agentdojo)

    tau_scorer_parser = subparsers.add_parser(
        "score-tau",
        help="run pinned tau-bench environment scorer for fixed-candidate smoke cases",
    )
    tau_scorer_parser.add_argument(
        "--checkout",
        default=str(DEFAULT_PUBLIC_SOURCE_ROOT / "tau-bench"),
    )
    tau_scorer_parser.add_argument("--output", default=str(DEFAULT_TAU_SMOKE_OUTPUT))
    tau_scorer_parser.add_argument(
        "--case-id",
        action="append",
        choices=[f"tau-{index:02d}" for index in range(1, 11)],
        required=True,
    )
    tau_scorer_parser.set_defaults(func=_score_tau)

    tau_summarize_parser = subparsers.add_parser(
        "summarize-tau",
        help="summarize the bounded 10-case tau environment-scorer reviewer smoke",
    )
    tau_summarize_parser.add_argument("--smoke-dir", required=True)
    tau_summarize_parser.add_argument("--review-capture-dir", required=True)
    tau_summarize_parser.set_defaults(func=_summarize_tau)

    tua_scorer_parser = subparsers.add_parser(
        "score-tua",
        help="import clean pinned TUA-Bench Harbor jobs as official scorer receipts",
    )
    tua_scorer_parser.add_argument(
        "--checkout",
        default=str(DEFAULT_PUBLIC_SOURCE_ROOT / "tua-bench"),
    )
    tua_scorer_parser.add_argument("--output", default=str(DEFAULT_TUA_SMOKE_OUTPUT))
    tua_scorer_parser.add_argument(
        "--case-job",
        action="append",
        type=_case_job,
        required=True,
        help="repeatable tua-NN=/absolute/path/to/completed/harbor/job",
    )
    tua_scorer_parser.set_defaults(func=_score_tua)

    swe_data_parser = subparsers.add_parser(
        "prepare-swe-data",
        help="prepare the pinned 12-case SWE task snapshot from official HF API responses",
    )
    swe_data_parser.add_argument("--metadata-response", required=True)
    swe_data_parser.add_argument("--rows-response", required=True)
    swe_data_parser.add_argument("--output", required=True)
    swe_data_parser.set_defaults(func=_prepare_swe_data)

    swe_scorer_parser = subparsers.add_parser(
        "score-swe",
        help="import clean pinned SWE-bench-Live official scorer outputs",
    )
    swe_scorer_parser.add_argument(
        "--checkout",
        default=str(DEFAULT_PUBLIC_SOURCE_ROOT / "swe-bench-live"),
    )
    swe_scorer_parser.add_argument("--task-data-root", required=True)
    swe_scorer_parser.add_argument("--output", default=str(DEFAULT_SWE_SMOKE_OUTPUT))
    swe_scorer_parser.add_argument(
        "--case-evaluation",
        action="append",
        type=_swe_case_evaluation,
        required=True,
        help="repeatable swe-NN=/absolute/path/to/completed/evaluation",
    )
    swe_scorer_parser.set_defaults(func=_score_swe)

    swe_run_parser = subparsers.add_parser(
        "run-swe",
        help="execute one pinned SWE-bench-Live fixed candidate with official scorer",
    )
    swe_run_parser.add_argument(
        "--checkout",
        default=str(DEFAULT_PUBLIC_SOURCE_ROOT / "swe-bench-live"),
    )
    swe_run_parser.add_argument("--task-data-root", required=True)
    swe_run_parser.add_argument(
        "--case-id",
        choices=[f"swe-{index:02d}" for index in range(1, 13)],
        required=True,
    )
    swe_run_parser.add_argument("--output", required=True)
    swe_run_parser.add_argument("--runtime-image-source-ref")
    swe_run_parser.add_argument("--runtime-image-source-digest-sha256")
    swe_run_parser.add_argument("--runtime-image-ref")
    swe_run_parser.set_defaults(func=_run_swe)

    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (KeyboardInterrupt, EOFError):
        print(
            "\nbenchmark paused: the in-progress item was not recorded; "
            "rerun the command and use --resume for batch flows.",
            file=sys.stderr,
        )
        return 130
    except (
        argparse.ArgumentTypeError,
        AgentDojoScorerError,
        BenchmarkRunnerError,
        BlindedAdjudicationError,
        ObservedRuntimeError,
        ObservedAblationError,
        SourcePreflightError,
        SweScorerError,
        TauScorerError,
        TuaHarborScorerError,
        HumanReconstructionError,
        ValueError,
    ) as exc:
        print(f"benchmark error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
