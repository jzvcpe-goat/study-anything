"""Study Anything adapter for Cognitive Loop learning gates.

The adapter keeps Cognitive Loop evidence metadata-only while still using the
Study Anything learning workflow internally. Project events and decision cards
become bounded Learning Context Packages; completed learning state is projected
back as Cognitive Loop MasteryRecord/LoopRun evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from .agent_audit import build_agent_audit
from .agent_eval import build_agent_eval_artifact
from .agent_registry import AgentRegistry, AgentRouter
from .cognitive_loop_contracts import (
    LoopRun,
    MasteryRecord,
    validate_decision_card,
    validate_loop_run,
    validate_mastery_record,
    validate_project_event,
)
from .learning_context import LEARNING_CONTEXT_SCHEMA_VERSION, validate_learning_context_package
from .learning_package import build_learning_package_export
from .second_brain_handoff import SECOND_BRAIN_HANDOFF_SCHEMA_VERSION, build_second_brain_handoff
from .security import hash_user_id
from .workflow import Answer, LearningState, LearningWorkflow, submit_answers, submit_enrichment


COGNITIVE_LOOP_STUDY_ADAPTER_SCHEMA_VERSION = "cognitive-loop-study-anything-adapter-v1"

_FORBIDDEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bdiff --git\b"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
)
_FORBIDDEN_LITERALS = (
    "Private raw diff",
    "Private source text",
    "learner answer:",
    "AGENT_ENDPOINT=http",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
)


class CognitiveLoopLearningAdapterError(RuntimeError):
    """Readable Study Anything adapter failure."""


def build_learning_context_from_cognitive_loop(
    *,
    project_event: Mapping[str, Any],
    decision_card: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Build a bounded Learning Context Package from public Cognitive Loop DTOs."""

    event = validate_project_event(project_event)
    decision = validate_decision_card(decision_card)
    if event.project_id != decision.project_id:
        raise CognitiveLoopLearningAdapterError("ProjectEvent and DecisionCard project_id must match.")
    if event.event_id not in decision.event_ids:
        raise CognitiveLoopLearningAdapterError("DecisionCard must reference the ProjectEvent.")

    topic = _subject_from_event(event.public_dict(), decision.public_dict())
    text = "\n".join(
        [
            f"Cognitive Loop event summary: {event.summary}",
            f"Decision: {decision.title}",
            f"Decision summary: {decision.summary}",
            f"Risk level: {decision.risk.get('level')} score {decision.risk.get('score')}",
            f"Human mastery gate: {decision.human_mastery_gate.get('status')}",
            "Learning task: explain the decision, risk, verification, and rollback path without raw diffs.",
        ]
    )
    package = {
        "schema_version": LEARNING_CONTEXT_SCHEMA_VERSION,
        "package_id": f"cl-study-{_short_hash(decision.decision_id)}",
        "title": f"Cognitive Loop Learning Gate: {decision.title}",
        "reference": f"cognitive-loop://decision/{decision.decision_id}",
        "producer": "cognitive-loop-study-anything-adapter",
        "language": "zh",
        "track": "ENGINEERING",
        "created_at": generated_at,
        "metadata": {
            "adapter": "study-anything",
            "project_id": event.project_id,
            "project_event_id": event.event_id,
            "decision_card_id": decision.decision_id,
            "source_mode": "bounded_public_summary",
            "raw_diff_included": False,
            "source_body_included": False,
        },
        "items": [
            {
                "item_id": f"cl-context-{_short_hash(event.event_id + decision.decision_id)}",
                "source_type": "markdown_note",
                "reference": f"cognitive-loop://event/{event.event_id}",
                "title": topic,
                "text": text,
                "locator": f"decision={decision.decision_id}",
                "provenance": {
                    "collector": "cognitive-loop-adapter",
                    "capture_method": "manual_excerpt",
                    "source_owner": "user",
                    "collected_at": generated_at,
                    "platform": "study-anything",
                },
                "redaction_policy": "summary_only",
                "metadata": {
                    "target": event.target or "",
                    "event_type": event.event_type,
                    "risk_level": str(decision.risk.get("level")),
                    "verification_status": str(decision.verification.get("status")),
                },
            }
        ],
    }
    validated = validate_learning_context_package(package)
    return validated.public_dict(include_text=True)


def run_cognitive_loop_study_adapter(
    *,
    project_event: Mapping[str, Any],
    decision_card: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Run the local Study Anything loop and return redacted Cognitive Loop evidence."""

    event = validate_project_event(project_event)
    decision = validate_decision_card(decision_card)
    package_with_text = build_learning_context_from_cognitive_loop(
        project_event=event.public_dict(),
        decision_card=decision.public_dict(),
        generated_at=generated_at,
    )
    package = validate_learning_context_package(package_with_text)

    user_id = "cognitive-loop-adapter-user"
    registry = AgentRegistry()
    registry.set_demo_defaults(user_id)
    workflow = LearningWorkflow(AgentRouter(registry))
    state = LearningState(
        session_id=f"cl-study-session-{_short_hash(decision.decision_id)}",
        user_id=user_id,
        user_hash=hash_user_id(user_id),
        workspace_id=event.project_id,
        track=package.track or "ENGINEERING",
        created_at=generated_at,
        updated_at=generated_at,
    )
    state = submit_enrichment(
        state,
        items=package.enrichment_payload()["items"],
        title=package.title,
        reference=package.reference,
    )
    state = workflow.teaching_layers(state, layers=("overview", "glossary"))
    state = workflow.run(state)
    if state.stage != "awaiting_answers" or not state.quiz_items:
        raise CognitiveLoopLearningAdapterError(f"Expected quiz state, got {state.stage}.")
    answers = [
        Answer(
            item_id=item.item_id,
            text=(
                "This decision should be explained from the cited summary, with risk, "
                "verification, rollback, and human mastery gate made explicit."
            ),
        )
        for item in state.quiz_items
    ]
    state = submit_answers(state, answers)
    state = workflow.run(state)
    if state.stage != "completed":
        raise CognitiveLoopLearningAdapterError(f"Study Anything workflow did not complete: {state.stage}.")

    agent_audit = build_agent_audit(state, agent_status=registry.status(user_id))
    agent_eval = build_agent_eval_artifact(agent_audit)
    learning_package = build_learning_package_export(state)
    second_brain = build_second_brain_handoff(state)
    mastery_record = _mastery_record(
        project_id=event.project_id,
        decision_id=decision.decision_id,
        subject=_subject_from_event(event.public_dict(), decision.public_dict()),
        state=state,
        generated_at=generated_at,
    )
    loop_run = _loop_run(
        project_id=event.project_id,
        event_id=event.event_id,
        decision_id=decision.decision_id,
        mastery_record=mastery_record,
        generated_at=generated_at,
    )

    report = {
        "schema_version": COGNITIVE_LOOP_STUDY_ADAPTER_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "purpose": (
            "Prove that Cognitive Loop can use Study Anything as a local Learning Adapter: "
            "public ProjectEvent/DecisionCard metadata creates a source-bound learning context, "
            "a deterministic local learning loop completes, and mastery is projected back as "
            "Cognitive Loop evidence."
        ),
        "input_contracts": {
            "project_event_schema": event.schema_version,
            "decision_card_schema": decision.schema_version,
            "risk_level": decision.risk.get("level"),
            "human_gate_status": decision.human_mastery_gate.get("status"),
        },
        "learning_context": _public_package_summary(package),
        "study_anything_loop": {
            "stage": state.stage,
            "track": state.track,
            "event_count": len(state.events),
            "teaching_layer_count": len(state.teaching_layers),
            "quiz_item_count": len(state.quiz_items),
            "grading_result_count": len(state.grading_results),
            "insight_count": len(state.insights),
            "scribe_entry_count": len(state.scribe_log),
            "source_reference": state.source.reference if state.source else None,
            "source_excerpt_hash": state.source.excerpt_hash if state.source else None,
        },
        "agent_evidence": {
            "audit_schema": agent_audit.get("schema_version"),
            "audit_status": agent_audit.get("status"),
            "eval_schema": agent_eval.get("schema_version"),
            "eval_status": agent_eval.get("status"),
            "observed_tasks": agent_audit.get("observed_tasks"),
            "used_fake_agent": agent_audit.get("used_fake_agent"),
            "used_external_agent": agent_audit.get("used_external_agent"),
        },
        "cognitive_loop_projection": {
            "mastery_record": mastery_record.public_dict(),
            "loop_run": loop_run.public_dict(),
        },
        "exports": {
            "learning_package_schema": learning_package.get("schema_version"),
            "learning_package_embedded_in_cognitive_loop_evidence": False,
            "second_brain_handoff_schema": second_brain.get("schema_version"),
            "second_brain_contract": (second_brain.get("handoff_contract") or {}),
            "strict_handoff_excludes_learner_answers": (
                second_brain.get("privacy", {}).get("learner_answers_included") is False
            ),
        },
        "privacy": {
            "metadata_only_cognitive_loop_evidence": True,
            "raw_source_text_in_report": False,
            "raw_diff_in_report": False,
            "learner_answers_in_report": False,
            "grading_feedback_in_report": False,
            "agent_endpoints_in_report": False,
            "agent_metadata_in_report": False,
            "model_keys_in_report": False,
            "study_anything_stores_real_model_keys": False,
        },
        "next_steps": [
            "Expose this bridge through a Cognitive Loop CLI command.",
            "Let watcher-generated DecisionCards request a Study Anything mastery gate.",
            "Render the MasteryRecord in the future HTML Artifact console.",
        ],
    }
    _assert_no_private_text(report)
    validate_mastery_record(report["cognitive_loop_projection"]["mastery_record"])
    validate_loop_run(report["cognitive_loop_projection"]["loop_run"])
    return report


def _mastery_record(
    *,
    project_id: str,
    decision_id: str,
    subject: str,
    state: LearningState,
    generated_at: str,
) -> MasteryRecord:
    return MasteryRecord(
        record_id=f"mastery-{_short_hash(decision_id)}",
        project_id=project_id,
        subject=subject,
        level=state.mastery.level,
        bloom=state.mastery.bloom,
        evidence_refs=[
            f"learning-context:{_short_hash(state.source.reference if state.source else decision_id)}",
            "agent-audit:verified",
            "agent-eval-artifact:ready_for_external_eval",
        ],
        updated_at=generated_at,
    )


def _loop_run(
    *,
    project_id: str,
    event_id: str,
    decision_id: str,
    mastery_record: MasteryRecord,
    generated_at: str,
) -> LoopRun:
    return LoopRun(
        run_id=f"loop-study-{_short_hash(event_id + decision_id)}",
        project_id=project_id,
        objective="Use Study Anything to close the Cognitive Loop human mastery gate.",
        status="succeeded",
        started_at=generated_at,
        completed_at=generated_at,
        project_event_ids=[event_id],
        decision_card_ids=[decision_id],
        trace_refs=["study-anything-adapter:metadata-only"],
        artifact_refs=[
            f"mastery-record:{mastery_record.record_id}",
            "learning-package:learning-package-v1",
            f"second-brain-handoff:{SECOND_BRAIN_HANDOFF_SCHEMA_VERSION}",
        ],
    )


def _public_package_summary(package: Any) -> dict[str, Any]:
    public = package.public_dict(include_text=False)
    public["item_hashes"] = [item.excerpt_hash for item in package.items]
    return public


def _subject_from_event(event: Mapping[str, Any], decision: Mapping[str, Any]) -> str:
    target = str(event.get("target") or "").strip()
    title = str(decision.get("title") or "Cognitive Loop Decision").strip()
    if target:
        return f"{target}: {title}"
    return title


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _assert_no_private_text(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in _FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in _FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise CognitiveLoopLearningAdapterError(f"Study Anything adapter report leaked private data: {leaks}")
    if "text" in payload.get("learning_context", {}):
        raise CognitiveLoopLearningAdapterError("Learning context public summary must not include text.")
