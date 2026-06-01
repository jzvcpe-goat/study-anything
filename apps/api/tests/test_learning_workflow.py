from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from study_anything.core.agent_registry import AgentRegistry, AgentRouter
from study_anything.core.knowledge_graph import KnowledgeGraphProjection, ProjectionResult
from study_anything.core.workflow import (
    Answer,
    LearningWorkflow,
    new_session,
    submit_answers,
    submit_reading,
)


class RecordingGraphSink:
    enabled = True

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.projections: list[KnowledgeGraphProjection] = []

    def project(self, projection: KnowledgeGraphProjection) -> ProjectionResult:
        if self.fail:
            raise RuntimeError("redis://user:secret@example.invalid")
        self.projections.append(projection)
        return ProjectionResult(session_id=projection.session_id)


class LearningWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = AgentRegistry()
        self.registry.set_demo_defaults("local-user")
        self.workflow = LearningWorkflow(AgentRouter(self.registry))

    def test_full_learning_loop_reaches_completed(self) -> None:
        state = new_session("local-user")
        state = submit_reading(
            state,
            source_type="local_text",
            reference="demo://source",
            title="Grounded Learning",
            text="Grounded learning systems connect questions to sources and update mastery.",
        )

        state = self.workflow.run(state)

        self.assertEqual(state.stage, "awaiting_answers")
        self.assertEqual(len(state.quiz_items), 1)

        quiz = state.quiz_items[0]
        state = submit_answers(
            state,
            [Answer(item_id=quiz.item_id, text="The workflow grounds questions in sources.")],
        )
        state = self.workflow.run(state)

        self.assertEqual(state.stage, "completed")
        self.assertEqual(state.mastery.level, 0.5)
        self.assertTrue(any(event.type == "mastery.upgrade" for event in state.events))

    def test_missing_source_reference_triggers_hitl(self) -> None:
        state = new_session("local-user")
        state = submit_reading(
            state,
            source_type="local_text",
            reference="",
            title="Unverified Source",
            text="A reading without a reference cannot support source-bound quizzes.",
        )

        state = self.workflow.run(state)

        self.assertEqual(state.stage, "interrupted")
        self.assertEqual(state.hitl_interrupts[-1].kind, "source.verification_required")

    def test_discard_marks_session(self) -> None:
        state = self.workflow.discard(new_session("local-user"))

        self.assertEqual(state.stage, "discarded")
        self.assertTrue(state.discarded)
        self.assertEqual(state.events[-1].type, "card.discarded")

    def test_mastery_projects_allowlisted_topology_fields(self) -> None:
        graph_sink = RecordingGraphSink()
        workflow = LearningWorkflow(AgentRouter(self.registry), knowledge_graph_sink=graph_sink)
        state = new_session("local-user")
        state = submit_reading(
            state,
            source_type="local_text",
            reference="demo://source",
            title="Private title",
            text="Private reading prose",
        )
        state = workflow.run(state)
        state = submit_answers(
            state,
            [Answer(item_id=state.quiz_items[0].item_id, text="Private answer")],
        )

        state = workflow.run(state)

        self.assertEqual(state.stage, "completed")
        self.assertEqual(len(graph_sink.projections), 1)
        self.assertNotIn("Private", str(graph_sink.projections[0]))
        self.assertTrue(any(event.type == "knowledge_graph.projected" for event in state.events))

    def test_graph_failure_does_not_block_learning_or_leak_details(self) -> None:
        workflow = LearningWorkflow(
            AgentRouter(self.registry),
            knowledge_graph_sink=RecordingGraphSink(fail=True),
        )
        state = new_session("local-user")
        state = submit_reading(
            state,
            source_type="local_text",
            reference="demo://source",
            title="Graph failure",
            text="Learning must complete while an optional graph is unavailable.",
        )
        state = workflow.run(state)
        state = submit_answers(
            state,
            [Answer(item_id=state.quiz_items[0].item_id, text="Continue the workflow.")],
        )

        state = workflow.run(state)

        self.assertEqual(state.stage, "completed")
        graph_events = [
            event for event in state.events if event.type == "knowledge_graph.projection_failed"
        ]
        self.assertEqual(len(graph_events), 1)
        self.assertEqual(graph_events[0].payload, {"status": "unavailable"})
        self.assertNotIn("secret", str(graph_events[0]))


if __name__ == "__main__":
    unittest.main()
