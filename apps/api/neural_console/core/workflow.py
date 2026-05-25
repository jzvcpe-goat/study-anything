"""Deterministic alpha learning workflow.

The public API mirrors the planned LangGraph workflow. The alpha executor is
pure Python so the project can be tested without external services.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from .agent_registry import (
    AgentCapability,
    AgentConfigurationRequired,
    AgentProviderUnavailable,
    AgentResult,
    AgentResultInvalid,
    AgentRouter,
    AgentTask,
)
from .events import NeuralEvent, utc_now
from .security import hash_user_id, sha256_text


@dataclass(frozen=True)
class ReadingSource:
    source_type: str
    reference: str
    title: str
    text: str
    excerpt_hash: str
    verified: bool = False


@dataclass(frozen=True)
class QuizItem:
    item_id: str
    prompt: str
    source_ref: str
    excerpt_hash: str
    rubric: str


@dataclass(frozen=True)
class Answer:
    item_id: str
    text: str


@dataclass(frozen=True)
class GradingResult:
    item_id: str
    score: float
    feedback: str
    reward: float


@dataclass(frozen=True)
class Mastery:
    level: float = 0.0
    bloom: str = "remember"


@dataclass(frozen=True)
class HitlInterrupt:
    task_id: str
    kind: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "open"


@dataclass(frozen=True)
class LearningState:
    session_id: str
    user_id: str
    user_hash: str
    track: str = "ACADEMIC"
    stage: str = "created"
    source: Optional[ReadingSource] = None
    quiz_items: List[QuizItem] = field(default_factory=list)
    answers: List[Answer] = field(default_factory=list)
    grading_results: List[GradingResult] = field(default_factory=list)
    mastery: Mastery = field(default_factory=Mastery)
    insights: List[str] = field(default_factory=list)
    scribe_log: List[str] = field(default_factory=list)
    hitl_interrupts: List[HitlInterrupt] = field(default_factory=list)
    events: List[NeuralEvent] = field(default_factory=list)
    audit_log: List[Dict[str, Any]] = field(default_factory=list)
    discarded: bool = False
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("user_id", None)
        return data


def new_session(user_id: str, track: str = "ACADEMIC") -> LearningState:
    session_id = str(uuid4())
    user_hash = hash_user_id(user_id)
    state = LearningState(session_id=session_id, user_id=user_id, user_hash=user_hash, track=track)
    return append_event(
        state,
        event_type="session.created",
        node="initialize_session",
        payload={"track": track},
    )


def append_event(
    state: LearningState,
    *,
    event_type: str,
    node: str,
    payload: Optional[Dict[str, Any]] = None,
    severity: str = "info",
) -> LearningState:
    event = NeuralEvent.create(
        session_id=state.session_id,
        user_hash=state.user_hash,
        event_type=event_type,
        node=node,
        payload=payload or {},
        severity=severity,
    )
    audit = {
        "timestamp": event.created_at,
        "event_type": event_type,
        "node": node,
        "severity": severity,
        "payload": payload or {},
    }
    return replace(
        state,
        events=state.events + [event],
        audit_log=state.audit_log + [audit],
        updated_at=utc_now(),
    )


def submit_reading(
    state: LearningState,
    *,
    source_type: str,
    reference: str,
    title: str,
    text: str,
) -> LearningState:
    excerpt_hash = sha256_text(text[:2000])
    source = ReadingSource(
        source_type=source_type,
        reference=reference,
        title=title,
        text=text,
        excerpt_hash=excerpt_hash,
        verified=bool(reference.strip()),
    )
    next_state = replace(state, source=source, stage="reading_submitted")
    return append_event(
        next_state,
        event_type="reading.submitted",
        node="initialize_session",
        payload={"source_type": source_type, "has_reference": bool(reference.strip())},
    )


def submit_answers(state: LearningState, answers: Iterable[Answer]) -> LearningState:
    next_state = replace(state, answers=list(answers), stage="answers_submitted")
    return append_event(
        next_state,
        event_type="answers.submitted",
        node="quiz_grader",
        payload={"answer_count": len(next_state.answers)},
    )


class LearningWorkflow:
    NODE_ORDER = (
        "initialize_session",
        "architect_node",
        "gap_filler",
        "quiz_generator",
        "quiz_grader",
        "mastery_evaluator",
        "synthesist_node",
        "scribe_node",
        "incubation_detector",
    )

    def __init__(self, agent_router: AgentRouter) -> None:
        self.agent_router = agent_router

    def run(self, state: LearningState) -> LearningState:
        current = state
        for node_name in self.NODE_ORDER:
            current = getattr(self, node_name)(current)
            if current.hitl_interrupts and current.hitl_interrupts[-1].status == "open":
                return current
            if current.stage in {"awaiting_answers", "completed", "discarded"}:
                if node_name in {"quiz_generator", "incubation_detector"}:
                    return current
        return current

    def initialize_session(self, state: LearningState) -> LearningState:
        return append_event(
            state,
            event_type="node.completed",
            node="initialize_session",
            payload={"stage": state.stage},
        )

    def architect_node(self, state: LearningState) -> LearningState:
        if state.source is None:
            return self._interrupt(
                state,
                kind="reading.required",
                message="Add a reading source before running the learning workflow.",
                node="architect_node",
            )
        return append_event(
            replace(state, stage="architected"),
            event_type="node.completed",
            node="architect_node",
            payload={"source_title": state.source.title},
        )

    def gap_filler(self, state: LearningState) -> LearningState:
        if state.source is None:
            return state
        if not state.source.verified:
            return self._interrupt(
                state,
                kind="source.verification_required",
                message="The source needs a reference before quiz generation.",
                node="gap_filler",
                payload={"title": state.source.title},
            )
        return append_event(
            replace(state, stage="source_verified"),
            event_type="source.verified",
            node="gap_filler",
            payload={"excerpt_hash": state.source.excerpt_hash},
        )

    def quiz_generator(self, state: LearningState) -> LearningState:
        if state.quiz_items:
            return state
        if state.source is None:
            return state
        try:
            agent_result = self.agent_router.invoke(
                user_id=state.user_id,
                capability=AgentCapability.QUIZ_GENERATE,
                task=AgentTask(
                    task_type=AgentCapability.QUIZ_GENERATE.value,
                    session_id=state.session_id,
                    track=state.track,
                    source=asdict(state.source),
                    constraints={
                        "max_items": 1,
                        "source_bound": True,
                        "output_hint": "Return a concise focus phrase in content.",
                    },
                ),
            )
        except (AgentConfigurationRequired, AgentProviderUnavailable, AgentResultInvalid) as exc:
            return self._interrupt(
                state,
                kind="agent.configuration_required",
                message=str(exc),
                node="quiz_generator",
            )
        if agent_result.status != "ok":
            return self._interrupt_from_agent(state, agent_result, node="quiz_generator")
        focus = str(agent_result.content).replace("Focus on ", "").strip() or state.source.title
        quiz = QuizItem(
            item_id=str(uuid4()),
            prompt=f"Using the source, explain the key relationship around {focus}.",
            source_ref=state.source.reference,
            excerpt_hash=state.source.excerpt_hash,
            rubric="Ground the answer in the cited source and state one implication.",
        )
        next_state = replace(state, quiz_items=[quiz], stage="awaiting_answers")
        return append_event(
            next_state,
            event_type="quiz.generated",
            node="quiz_generator",
            payload={"count": 1, "agent": agent_result.public_metadata()},
        )

    def quiz_grader(self, state: LearningState) -> LearningState:
        if not state.answers:
            return state
        if state.grading_results:
            return state
        results: List[GradingResult] = []
        agent_events: List[dict[str, Any]] = []
        for answer in state.answers:
            try:
                agent_result = self.agent_router.invoke(
                    user_id=state.user_id,
                    capability=AgentCapability.ANSWER_GRADE,
                    task=AgentTask(
                        task_type=AgentCapability.ANSWER_GRADE.value,
                        session_id=state.session_id,
                        track=state.track,
                        source=asdict(state.source) if state.source else None,
                        quiz_items=[asdict(item) for item in state.quiz_items],
                        answers=[asdict(answer)],
                        rubric=next(
                            (item.rubric for item in state.quiz_items if item.item_id == answer.item_id),
                            None,
                        ),
                        constraints={"score_range": [0, 1], "require_source_grounding": True},
                    ),
                )
            except (AgentConfigurationRequired, AgentProviderUnavailable, AgentResultInvalid) as exc:
                return self._interrupt(
                    state,
                    kind="agent.configuration_required",
                    message=str(exc),
                    node="quiz_grader",
                )
            if agent_result.status != "ok":
                return self._interrupt_from_agent(state, agent_result, node="quiz_grader")
            score = agent_result.score if agent_result.score is not None else 0.0
            results.append(
                GradingResult(
                    item_id=answer.item_id,
                    score=score,
                    feedback=str(agent_result.feedback or agent_result.content),
                    reward=score,
                )
            )
            agent_events.append(agent_result.public_metadata())
        next_state = replace(state, grading_results=results, stage="graded")
        return append_event(
            next_state,
            event_type="answers.graded",
            node="quiz_grader",
            payload={
                "count": len(results),
                "average": self._average(result.score for result in results),
                "agents": agent_events,
            },
        )

    def mastery_evaluator(self, state: LearningState) -> LearningState:
        if not state.grading_results:
            return state
        average = self._average(result.score for result in state.grading_results)
        increment = 0.5 if average >= 0.7 else 0.0
        level = min(6.0, state.mastery.level + increment)
        bloom = "understand" if level >= 0.5 else "remember"
        next_state = replace(state, mastery=Mastery(level=level, bloom=bloom), stage="mastery_evaluated")
        return append_event(
            next_state,
            event_type="mastery.upgrade" if increment else "mastery.unchanged",
            node="mastery_evaluator",
            payload={"level": level, "bloom": bloom, "average_score": average},
        )

    def synthesist_node(self, state: LearningState) -> LearningState:
        if not state.grading_results:
            return state
        try:
            agent_result = self.agent_router.invoke(
                user_id=state.user_id,
                capability=AgentCapability.INSIGHT_SYNTHESIZE,
                task=AgentTask(
                    task_type=AgentCapability.INSIGHT_SYNTHESIZE.value,
                    session_id=state.session_id,
                    track=state.track,
                    source=asdict(state.source) if state.source else None,
                    quiz_items=[asdict(item) for item in state.quiz_items],
                    answers=[asdict(answer) for answer in state.answers],
                    constraints={
                        "mastery_level": state.mastery.level,
                        "mastery_bloom": state.mastery.bloom,
                    },
                ),
            )
        except (AgentConfigurationRequired, AgentProviderUnavailable, AgentResultInvalid) as exc:
            return self._interrupt(
                state,
                kind="agent.configuration_required",
                message=str(exc),
                node="synthesist_node",
            )
        if agent_result.status != "ok":
            return self._interrupt_from_agent(state, agent_result, node="synthesist_node")
        insight = str(agent_result.content)
        next_state = replace(state, insights=state.insights + [insight], stage="synthesized")
        return append_event(
            next_state,
            event_type="insight.generated",
            node="synthesist_node",
            payload={"insight": insight, "agent": agent_result.public_metadata()},
        )

    def scribe_node(self, state: LearningState) -> LearningState:
        if not state.grading_results:
            return state
        note = f"{utc_now()} session={state.session_id} mastery={state.mastery.level:.1f}"
        next_state = replace(state, scribe_log=state.scribe_log + [note], stage="scribed")
        return append_event(
            next_state,
            event_type="scribe.logged",
            node="scribe_node",
            payload={"entries": len(next_state.scribe_log)},
        )

    def incubation_detector(self, state: LearningState) -> LearningState:
        if not state.grading_results:
            return state
        low_rewards = [result for result in state.grading_results if result.reward < 0.3]
        if len(low_rewards) >= 2:
            return self._interrupt(
                state,
                kind="incubation.triggered",
                message="Low reward streak detected; schedule a 24h incubation window.",
                node="incubation_detector",
            )
        next_state = replace(state, stage="completed")
        return append_event(
            next_state,
            event_type="session.completed",
            node="incubation_detector",
            payload={"discarded": state.discarded},
        )

    def discard(self, state: LearningState) -> LearningState:
        next_state = replace(state, discarded=True, stage="discarded")
        return append_event(
            next_state,
            event_type="card.discarded",
            node="scribe_node",
            payload={"session_id": state.session_id},
        )

    def resolve_hitl(self, state: LearningState, task_id: str, payload: Dict[str, Any]) -> LearningState:
        interrupts: List[HitlInterrupt] = []
        found = False
        for interrupt in state.hitl_interrupts:
            if interrupt.task_id == task_id:
                found = True
                interrupts.append(replace(interrupt, status="resolved", payload={**interrupt.payload, **payload}))
            else:
                interrupts.append(interrupt)
        if not found:
            raise KeyError(f"Unknown HITL task: {task_id}")
        return append_event(
            replace(state, hitl_interrupts=interrupts),
            event_type="hitl.resolved",
            node="hitl",
            payload={"task_id": task_id},
        )

    def _interrupt(
        self,
        state: LearningState,
        *,
        kind: str,
        message: str,
        node: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> LearningState:
        interrupt = HitlInterrupt(
            task_id=str(uuid4()),
            kind=kind,
            message=message,
            payload=payload or {},
        )
        next_state = replace(
            state,
            hitl_interrupts=state.hitl_interrupts + [interrupt],
            stage="interrupted",
        )
        return append_event(
            next_state,
            event_type="hitl.interrupt",
            node=node,
            payload={"kind": kind, "task_id": interrupt.task_id, "message": message},
            severity="warning",
        )

    def _interrupt_from_agent(
        self,
        state: LearningState,
        result: AgentResult,
        *,
        node: str,
    ) -> LearningState:
        return self._interrupt(
            state,
            kind=f"agent.{result.status}",
            message=str(result.feedback or result.content or "Agent requested human review."),
            node=node,
            payload={"agent": result.public_metadata(), "citations": list(result.citations)},
        )

    @staticmethod
    def _average(values: Iterable[float]) -> float:
        items = list(values)
        if not items:
            return 0.0
        return sum(items) / len(items)
