from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from neural_console.core.agent_registry import AgentRegistry, AgentRouter
from neural_console.core.workflow import Answer, LearningWorkflow, new_session, submit_answers, submit_reading


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


if __name__ == "__main__":
    unittest.main()
