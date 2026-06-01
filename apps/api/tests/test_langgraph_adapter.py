from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from study_anything.core.agent_registry import AgentRegistry, AgentRouter
from study_anything.core.langgraph_adapter import (
    LangGraphCheckpointResource,
    LangGraphLearningWorkflow,
    build_learning_workflow,
    langgraph_available,
)
from study_anything.core.workflow import Answer, LearningWorkflow, new_session, submit_answers, submit_reading


class LangGraphAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = AgentRegistry()
        self.registry.set_demo_defaults("local-user")
        self.router = AgentRouter(self.registry)

    @unittest.skipUnless(langgraph_available(), "LangGraph is not installed.")
    def test_compiled_graph_reaches_completed(self) -> None:
        workflow = LangGraphLearningWorkflow(self.router)
        state = submit_reading(
            new_session("local-user"),
            source_type="local_text",
            reference="demo://langgraph",
            title="LangGraph Learning",
            text="A checkpointed graph should preserve the source-bound learning workflow.",
        )

        state = workflow.run(state)
        self.assertEqual(state.stage, "awaiting_answers")

        state = submit_answers(
            state,
            [Answer(item_id=state.quiz_items[0].item_id, text="The graph preserves workflow state.")],
        )
        state = workflow.run(state)

        self.assertEqual(state.stage, "completed")
        self.assertEqual(state.mastery.level, 0.5)

    @unittest.skipUnless(langgraph_available(), "LangGraph is not installed.")
    def test_memory_checkpoint_resource(self) -> None:
        resource = LangGraphCheckpointResource(backend="memory")

        self.assertEqual(resource.backend, "memory")
        self.assertIsNotNone(resource.saver)
        resource.close()

    def test_postgres_checkpoint_requires_database_url(self) -> None:
        with self.assertRaises(ValueError):
            LangGraphCheckpointResource(backend="postgres")

    def test_rejects_unknown_checkpoint_backend(self) -> None:
        with self.assertRaises(ValueError):
            LangGraphCheckpointResource(backend="unknown")

    def test_deterministic_engine_remains_available(self) -> None:
        workflow = build_learning_workflow(self.router, engine="deterministic")

        self.assertIsInstance(workflow, LearningWorkflow)
        self.assertEqual(workflow.engine, "deterministic")


if __name__ == "__main__":
    unittest.main()
