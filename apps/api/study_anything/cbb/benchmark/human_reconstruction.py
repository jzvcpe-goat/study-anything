"""Interactive, aggregate-only human boundary reconstruction for reviewer packets."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from time import monotonic
from typing import Any, Callable

from study_anything.cbb.protocol.canonical import assert_safe_metadata, canonical_sha256


@dataclass(frozen=True)
class ReconstructionOption:
    code: str
    label: str


@dataclass(frozen=True)
class ReconstructionQuestion:
    question_id: str
    prompt: str
    options: tuple[ReconstructionOption, ReconstructionOption, ReconstructionOption]
    expected_code: str


class HumanReconstructionError(ValueError):
    """Raised when a reviewer packet cannot support scored reconstruction."""


def _rotate_options(
    options: tuple[ReconstructionOption, ReconstructionOption, ReconstructionOption],
    *,
    case_id: str,
    question_id: str,
) -> tuple[ReconstructionOption, ReconstructionOption, ReconstructionOption]:
    offset = int.from_bytes(
        sha256(f"{case_id}:{question_id}".encode("utf-8")).digest()[:2], "big"
    ) % len(options)
    rotated = options[offset:] + options[:offset]
    return rotated[0], rotated[1], rotated[2]


def boundary_questions(packet: dict[str, Any]) -> tuple[ReconstructionQuestion, ...]:
    assert_safe_metadata(packet, label="human reconstruction packet")
    candidate = packet.get("candidate")
    if not isinstance(candidate, dict):
        raise HumanReconstructionError("reviewer packet is missing its candidate view")
    visible = candidate.get("visible_evidence")
    if not isinstance(visible, list):
        raise HumanReconstructionError("reviewer packet visible evidence is invalid")
    evidence = [item for item in visible if isinstance(item, dict)]
    blocking_failures = [
        str(item.get("summary_code"))
        for item in evidence
        if item.get("blocking") is True and item.get("status") != "passed"
    ]
    rollback = next(
        (
            str(item.get("summary_code"))
            for item in evidence
            if item.get("evidence_type") == "rollback-or-containment"
            and item.get("status") == "passed"
        ),
        "recovery-gap",
    )
    recipient = str(candidate.get("intended_recipient_role", "undeclared"))
    risk_owner = str(candidate.get("risk_owner_role", "undeclared"))
    prohibited = candidate.get("prohibited_use_codes")
    if not isinstance(prohibited, list) or not prohibited:
        raise HumanReconstructionError("reviewer packet has no prohibited-use boundary")
    failure_label = (
        ", ".join(sorted(blocking_failures))
        if blocking_failures
        else "no blocking failure appears in visible evidence"
    )
    failure_expected = "visible-blocking-failure" if blocking_failures else "no-visible-blocker"
    questions = (
        ReconstructionQuestion(
            question_id="delivery-scope",
            prompt="What is the maximum delivery scope supported by this packet?",
            options=(
                ReconstructionOption(
                    "declared-scope", str(candidate.get("target_scope", "undeclared"))
                ),
                ReconstructionOption("customer-scope", "customer handoff"),
                ReconstructionOption("production-scope", "production execution"),
            ),
            expected_code="declared-scope",
        ),
        ReconstructionQuestion(
            question_id="recipient-and-responsibility",
            prompt="Who receives the result, and who owns the residual risk?",
            options=(
                ReconstructionOption(
                    "declared-responsibility",
                    f"recipient={recipient}; risk owner={risk_owner}",
                ),
                ReconstructionOption("model-responsibility", "the producing model owns it"),
                ReconstructionOption("no-responsibility", "no responsible party is declared"),
            ),
            expected_code="declared-responsibility",
        ),
        ReconstructionQuestion(
            question_id="visible-failure-boundary",
            prompt="What is the most important visible failure boundary?",
            options=(
                ReconstructionOption(failure_expected, failure_label),
                ReconstructionOption("hidden-scorer", "assume the hidden scorer passed"),
                ReconstructionOption("global-correctness", "the artifact is globally correct"),
            ),
            expected_code=failure_expected,
        ),
        ReconstructionQuestion(
            question_id="recovery-boundary",
            prompt="What recovery or containment evidence is declared?",
            options=(
                ReconstructionOption("declared-recovery", rollback),
                ReconstructionOption("automatic-production-rollback", "automatic production rollback"),
                ReconstructionOption("no-recovery-needed", "no recovery is needed"),
            ),
            expected_code="declared-recovery",
        ),
        ReconstructionQuestion(
            question_id="prohibited-use-boundary",
            prompt="Which use remains prohibited even if this candidate is cleared?",
            options=(
                ReconstructionOption(
                    "declared-prohibited-uses", ", ".join(str(item) for item in prohibited)
                ),
                ReconstructionOption("unrestricted-use", "no use remains prohibited"),
                ReconstructionOption("global-release", "global release without a new receipt"),
            ),
            expected_code="declared-prohibited-uses",
        ),
    )
    case_id = str(packet.get("case_id", "unknown"))
    return tuple(
        replace(
            question,
            options=_rotate_options(
                question.options,
                case_id=case_id,
                question_id=question.question_id,
            ),
        )
        for question in questions
    )


def question_set_digest(
    questions: tuple[ReconstructionQuestion, ...],
    *,
    review_material_digest_sha256: str,
) -> str:
    return canonical_sha256(
        {
            "schema_version": "boundary-reconstruction-question-set-v1",
            "review_material_digest_sha256": review_material_digest_sha256,
            "questions": [
                {
                    "question_id": question.question_id,
                    "option_codes": [option.code for option in question.options],
                    "expected_code": question.expected_code,
                }
                for question in questions
            ],
        }
    )


def _ask_boundary_questions(
    questions: tuple[ReconstructionQuestion, ...],
    *,
    input_fn: Callable[[str], str],
    print_fn: Callable[[str], None],
) -> tuple[int, int]:
    correct = 0
    unresolved = 0
    for index, question in enumerate(questions, start=1):
        print_fn(f"{index}. {question.prompt}")
        for option_index, option in enumerate(question.options, start=1):
            print_fn(f"   {option_index}. {option.label}")
        while True:
            answer = input_fn("answer [1/2/3/u=unresolved]: ").strip().lower()
            if answer in {"1", "2", "3", "u"}:
                break
        if answer == "u":
            unresolved += 1
            continue
        selected = question.options[int(answer) - 1]
        correct += selected.code == question.expected_code
    return correct, unresolved


def full_review_material(packet: dict[str, Any]) -> dict[str, Any]:
    """Return all label-free delivery metadata without exposing case identity."""

    assert_safe_metadata(packet, label="full review packet")
    candidate = packet.get("candidate")
    if not isinstance(candidate, dict):
        raise HumanReconstructionError("reviewer packet is missing its candidate view")
    if (
        packet.get("reference_label_included") is not False
        or packet.get("hidden_tests_included") is not False
        or packet.get("official_scorer_result_included") is not False
    ):
        raise HumanReconstructionError("full review packet is not label-free")
    visible_evidence = candidate.get("visible_evidence")
    if not isinstance(visible_evidence, list):
        raise HumanReconstructionError("full review evidence is invalid")
    material = {
        "schema_version": "blinded-full-review-material-v1",
        "task_summary_code": candidate.get("task_summary_code"),
        "declared_risk_level": candidate.get("declared_risk_level"),
        "target_scope": candidate.get("target_scope"),
        "intended_recipient_role": candidate.get("intended_recipient_role"),
        "risk_owner_role": candidate.get("risk_owner_role"),
        "prohibited_use_codes": candidate.get("prohibited_use_codes"),
        "tool_permission_ids": candidate.get("tool_permission_ids"),
        "subject_digest_sha256": candidate.get("subject_digest_sha256"),
        "source_snapshot_digest_sha256": candidate.get("source_snapshot_digest_sha256"),
        "context_digest_sha256": candidate.get("context_digest_sha256"),
        "visible_evidence": [
            {
                "evidence_type": item.get("evidence_type"),
                "status": item.get("status"),
                "summary_code": item.get("summary_code"),
                "blocking": item.get("blocking"),
                "evidence_digest_sha256": item.get("evidence_digest_sha256"),
            }
            for item in visible_evidence
            if isinstance(item, dict)
        ],
        "arm_decisions_accessible": False,
        "official_scorer_result_accessible": False,
        "reference_label_accessible": False,
    }
    assert_safe_metadata(material, label="blinded full review material")
    return material


def run_interactive_reconstruction(
    packet: dict[str, Any],
    *,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    display_label: str | None = None,
) -> tuple[int, int, int, str]:
    questions = boundary_questions(packet)
    candidate = packet["candidate"]
    print_fn(f"Case: {display_label or packet.get('case_id', 'unknown')}")
    print_fn(
        "Boundary: "
        f"scope={candidate.get('target_scope')}; "
        f"recipient={candidate.get('intended_recipient_role')}; "
        f"risk_owner={candidate.get('risk_owner_role')}"
    )
    print_fn("Visible evidence:")
    for item in candidate.get("visible_evidence", []):
        if isinstance(item, dict):
            print_fn(
                f"- {item.get('evidence_type')}: {item.get('status')} / "
                f"{item.get('summary_code')}"
            )
    print_fn("Only aggregate correctness and elapsed time will be stored.")
    started = monotonic()
    correct, unresolved = _ask_boundary_questions(
        questions,
        input_fn=input_fn,
        print_fn=print_fn,
    )
    elapsed_ms = int((monotonic() - started) * 1000)
    return (
        elapsed_ms,
        correct,
        unresolved,
        question_set_digest(
            questions,
            review_material_digest_sha256=canonical_sha256(packet),
        ),
    )


def run_interactive_full_review(
    packet: dict[str, Any],
    *,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    display_label: str | None = None,
) -> tuple[int, int, int, str]:
    """Measure a full label-free metadata review followed by the same five questions."""

    questions = boundary_questions(packet)
    material = full_review_material(packet)
    print_fn(f"Full review: {display_label or 'blinded-item'}")
    print_fn(json.dumps(material, ensure_ascii=False, indent=2, sort_keys=True))
    print_fn("Arm decisions, official scorer outcome, and reference label remain hidden.")
    print_fn("Only aggregate correctness and elapsed time will be stored.")
    started = monotonic()
    input_fn("Press Enter after completing the full metadata review: ")
    correct, unresolved = _ask_boundary_questions(
        questions,
        input_fn=input_fn,
        print_fn=print_fn,
    )
    elapsed_ms = int((monotonic() - started) * 1000)
    return (
        elapsed_ms,
        correct,
        unresolved,
        question_set_digest(
            questions,
            review_material_digest_sha256=canonical_sha256(packet),
        ),
    )
