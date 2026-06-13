from __future__ import annotations

import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.agent_registry import AgentRegistry, AgentRouter
from study_anything.core.store import InMemorySessionStore
from study_anything.core.workflow import LearningWorkflow
from study_anything.core.workspace import LocalWorkspaceStore


class AgentEvalPolicyTests(unittest.TestCase):
    def _client(self, root: Path) -> tuple[TestClient, ExitStack]:
        stack = ExitStack()
        registry = AgentRegistry(root / "agents.json")
        workflow = LearningWorkflow(AgentRouter(registry))
        stack.enter_context(patch.object(api_main, "store", InMemorySessionStore()))
        stack.enter_context(patch.object(api_main, "agent_registry", registry))
        stack.enter_context(patch.object(api_main, "workflow", workflow))
        stack.enter_context(
            patch.object(api_main, "workspace_store", LocalWorkspaceStore(root / "workspaces.json"))
        )
        return TestClient(api_main.create_app()), stack

    def test_eval_policy_is_redacted_and_external_tools_are_optional(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                response = client.get("/v1/evals/policy")

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["schema_version"], "agent-eval-policy-v1")
        self.assertIs(body["native_fast_gate"]["required_for_release"], True)
        self.assertEqual(
            body["native_fast_gate"]["required_tasks"],
            ["quiz.generate", "answer.grade", "insight.synthesize"],
        )
        adapter_ids = {item["adapter_id"] for item in body["external_adapters"]}
        self.assertEqual(adapter_ids, {"promptfoo", "deepeval", "langchain-agentevals", "ragas"})
        self.assertTrue(all(item["required_for_release"] is False for item in body["external_adapters"]))
        self.assertEqual(len(body["fixtures"]), 2)
        self.assertIs(body["privacy"]["real_model_keys_stored_by_study_anything"], False)
        serialized = json.dumps(body, ensure_ascii=False)
        self.assertNotIn("sk-proj", serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)

    def test_agent_eval_report_covers_invocation_quality_exports_and_privacy(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                session = client.post(
                    "/v1/sessions",
                    json={"user_id": "eval-report-user", "use_demo_agent": True},
                ).json()
                session_id = session["session_id"]
                private_source = "Private report source text should never appear in eval reports."
                private_answer = "Private report answer should never appear in eval reports."
                client.post(
                    f"/v1/sessions/{session_id}/reading",
                    json={
                        "source_type": "local_text",
                        "reference": "demo://agent-eval-report",
                        "title": "Private report title",
                        "text": private_source,
                    },
                )
                client.post(
                    f"/v1/sessions/{session_id}/teaching-layers",
                    json={"layers": ["overview", "glossary"], "language": "zh"},
                )
                running = client.post(f"/v1/sessions/{session_id}/run").json()
                quiz_id = running["quiz_items"][0]["item_id"]
                client.post(
                    f"/v1/sessions/{session_id}/answers",
                    json={"answers": {quiz_id: private_answer}},
                )
                response = client.get(f"/v1/sessions/{session_id}/agent-eval/report")

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["schema_version"], "agent-eval-report-v1")
        self.assertEqual(body["policy_schema_version"], "agent-eval-policy-v1")
        self.assertEqual(body["native_fast_gate"]["status"], "pass")
        self.assertTrue(str(body["status"]).startswith("pass"))
        dimensions = {item["dimension_id"]: item for item in body["dimensions"]}
        for required in [
            "agent_invocation_coverage",
            "trajectory_coverage",
            "teaching_quality",
            "privacy_redaction",
        ]:
            self.assertEqual(dimensions[required]["status"], "pass", required)
            self.assertIs(dimensions[required]["required"], True)
        self.assertIn(dimensions["retrieval_grounding"]["status"], {"not_evaluated", "pass"})
        self.assertEqual(dimensions["export_readiness"]["status"], "pass")
        adapter_ids = {item["adapter_id"] for item in body["adapter_readiness"]}
        self.assertEqual(adapter_ids, {"promptfoo", "deepeval", "langchain-agentevals", "ragas"})
        self.assertTrue(all(item["required_for_release"] is False for item in body["adapter_readiness"]))
        serialized = json.dumps(body, ensure_ascii=False)
        self.assertNotIn(private_source, serialized)
        self.assertNotIn(private_answer, serialized)
        self.assertNotIn("Private report title", serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)

    def test_agent_eval_report_returns_404_for_missing_session(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                response = client.get("/v1/sessions/missing/agent-eval/report")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
