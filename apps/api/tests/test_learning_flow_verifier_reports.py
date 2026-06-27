from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_script_with_env(name: str, env: dict[str, str]):
    spec = importlib.util.spec_from_file_location(
        f"{name}_env_test",
        REPO_ROOT / "scripts" / f"{name}.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, env, clear=True):
        spec.loader.exec_module(module)
    return module


full_api = load_script("verify_full_api_flow")
mock_http_agent = load_script("verify_mock_http_agent_flow")
agent_eval = load_script("verify_agent_eval_flow")
platform_lesson = load_script("verify_platform_lesson_flow")
importer_lesson = load_script("verify_importer_lesson_flow")
ecosystem_eval = load_script("verify_platform_ecosystem_eval_flow")
platform_agent_tools = load_script("verify_platform_agent_tools")


LOCAL_HOME_FIXTURE = "/Users/" + "example"


class LearningFlowVerifierReportTests(unittest.TestCase):
    def test_flow_verifiers_read_env_file_api_port_when_no_explicit_api_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text('export API_PORT="18080" # local override\n', encoding="utf-8")
            env = {"STUDY_ANYTHING_ENV_FILE": str(env_file)}

            modules = [
                load_script_with_env("verify_full_api_flow", env),
                load_script_with_env("verify_agent_eval_flow", env),
                load_script_with_env("verify_mock_http_agent_flow", env),
                load_script_with_env("verify_platform_lesson_flow", env),
                load_script_with_env("verify_importer_lesson_flow", env),
                load_script_with_env("verify_platform_agent_tools", env),
                load_script_with_env("verify_platform_ecosystem_eval_flow", env),
                load_script_with_env("verify_falkordb_flow", env),
            ]

        self.assertEqual(
            {module.API_BASE for module in modules},
            {"http://127.0.0.1:18080"},
        )

    def test_full_api_report_classifies_localhost_socket_block(self) -> None:
        report = full_api.failure_report(
            RuntimeError(
                "verify_full_api_flow cannot reach Study Anything at http://127.0.0.1:8000. "
                "The current runner appears to block localhost sockets."
            )
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["classification"], "localhost_socket_blocked")
        self.assertIn("normal terminal", " ".join(report["next_steps"]))
        self.assertFalse(report["privacy"]["real_model_keys_included"])

    def test_full_api_human_failure_is_actionable_and_redacted(self) -> None:
        report = full_api.failure_report(
            RuntimeError(
                "verify_full_api_flow cannot reach Study Anything at http://127.0.0.1:8000. "
                "The current runner appears to block localhost sockets."
            )
        )

        message = full_api.format_failure_for_human(report)

        self.assertIn("verify_full_api_flow failed:", message)
        self.assertIn("classification: localhost_socket_blocked", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("./scripts/launch_skill_mode.sh", message)

    def test_full_api_report_redacts_private_smoke_data(self) -> None:
        local_home = "/Users/" + "example"
        secret = "sk-" + "proj-abcdefghijklmnop"
        report = full_api.failure_report(
            RuntimeError(
                "Agent eval required gates failed for smoke-user with "
                "A launch smoke test should create a quiz, grade an answer, and update mastery. "
                "The system uses source evidence to update mastery. "
                f"path={local_home}/project token=supersecret123 {secret}"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "agent_eval_failed")
        self.assertIn("<private-user>", serialized)
        self.assertIn("<private-source-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertIn("sk-<redacted>", serialized)
        self.assertNotIn("smoke-user", serialized)
        self.assertNotIn("launch smoke test", serialized.lower())
        self.assertNotIn("source evidence", serialized.lower())
        self.assertNotIn(local_home, serialized)
        self.assertNotIn("supersecret123", serialized)

    def test_mock_http_agent_report_classifies_agent_gateway_failure(self) -> None:
        report = mock_http_agent.failure_report(
            RuntimeError("502 Bad Gateway from configured HTTP Agent endpoint")
        )

        self.assertEqual(report["classification"], "agent_gateway_unreachable")
        self.assertIn("curl http://127.0.0.1:8787/health", " ".join(report["next_steps"]))

    def test_mock_http_agent_human_failure_names_classification_and_steps(self) -> None:
        report = mock_http_agent.failure_report(
            RuntimeError("502 Bad Gateway from configured HTTP Agent endpoint")
        )

        message = mock_http_agent.format_failure_for_human(report)

        self.assertIn("verify_mock_http_agent_flow failed:", message)
        self.assertIn("classification: agent_gateway_unreachable", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("curl http://127.0.0.1:8787/health", message)

    def test_mock_http_agent_report_redacts_private_agent_data(self) -> None:
        api_query_name = "api_" + "key"
        report = mock_http_agent.failure_report(
            RuntimeError(
                "Mock HTTP Agent is not healthy for http-agent-smoke-user with "
                "A user-owned agent should generate a quiz, grade an answer, and synthesize an insight. "
                "The agent follows the source-bound task contract. "
                f"path={LOCAL_HOME_FIXTURE}/project?{api_query_name}=supersecret123 token=othersecret456"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "agent_health_failed")
        self.assertIn("<private-user>", serialized)
        self.assertIn("<private-source-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("api_key=<redacted>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("http-agent-smoke-user", serialized)
        self.assertNotIn("user-owned agent should", serialized.lower())
        self.assertNotIn("source-bound task contract", serialized.lower())
        self.assertNotIn(LOCAL_HOME_FIXTURE, serialized)
        self.assertNotIn("supersecret123", serialized)
        self.assertNotIn("othersecret456", serialized)

    def test_agent_eval_report_classifies_required_gate_failure(self) -> None:
        report = agent_eval.failure_report(
            RuntimeError("Required native eval gates failed: [{'id': 'source_bound', 'status': 'fail'}]")
        )

        self.assertEqual(report["classification"], "agent_eval_failed")
        self.assertIn("required native gates", " ".join(report["next_steps"]))
        self.assertFalse(report["privacy"]["real_model_keys_included"])

    def test_agent_eval_human_failure_is_actionable_and_redacted(self) -> None:
        report = agent_eval.failure_report(
            RuntimeError("Required native eval gates failed: [{'id': 'source_bound', 'status': 'fail'}]")
        )

        message = agent_eval.format_failure_for_human(report)

        self.assertIn("verify_agent_eval_flow failed:", message)
        self.assertIn("classification: agent_eval_failed", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("agent-eval artifact/report", message)
        self.assertIn("Do not publish raw source", message)

    def test_agent_eval_report_redacts_private_eval_data(self) -> None:
        report = agent_eval.failure_report(
            RuntimeError(
                "Eval artifact leaked private data for agent-eval-smoke-user: "
                "Private Agent Eval Smoke / Private source text for eval smoke must never appear in eval artifacts. "
                f"Private eval smoke answer. path={LOCAL_HOME_FIXTURE}/project?token=supersecret123"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "privacy_leak")
        self.assertIn("<private-user>", serialized)
        self.assertIn("<private-title>", serialized)
        self.assertIn("<private-source-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("agent-eval-smoke-user", serialized)
        self.assertNotIn("Private Agent Eval Smoke", serialized)
        self.assertNotIn("Private source text", serialized)
        self.assertNotIn("Private eval smoke answer", serialized)
        self.assertNotIn(LOCAL_HOME_FIXTURE, serialized)
        self.assertNotIn("supersecret123", serialized)

    def test_platform_lesson_report_classifies_privacy_leak(self) -> None:
        report = platform_lesson.failure_report(
            platform_lesson.LessonVerificationError(
                "second-brain handoff strict privacy boundary leaked private data: ['private answer']"
            )
        )

        self.assertEqual(report["classification"], "privacy_leak")
        self.assertIn("Do not share the raw transcript", " ".join(report["next_steps"]))
        self.assertFalse(report["privacy"]["raw_enrichment_text_included"])

    def test_platform_lesson_human_failure_is_actionable_and_redacted(self) -> None:
        report = platform_lesson.failure_report(
            platform_lesson.LessonVerificationError(
                "Lesson did not complete for platform-lesson-smoke-user with "
                "Private lesson source text about retrieval practice must not leak into redacted evidence. "
                f"path={LOCAL_HOME_FIXTURE}/project token=supersecret123"
            )
        )

        message = platform_lesson.format_failure_for_human(report)

        self.assertIn("verify_platform_lesson_flow failed:", message)
        self.assertIn("classification: learning_flow_incomplete", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("session events", message)
        self.assertIn("<private-user>", message)
        self.assertIn("<private-source-text>", message)
        self.assertIn("<local-path>", message)
        self.assertIn("token=<redacted>", message)
        self.assertNotIn("platform-lesson-smoke-user", message)
        self.assertNotIn(LOCAL_HOME_FIXTURE, message)
        self.assertNotIn("supersecret123", message)

    def test_platform_lesson_report_redacts_private_lesson_data(self) -> None:
        report = platform_lesson.failure_report(
            platform_lesson.LessonVerificationError(
                "Lesson did not complete for platform-lesson-smoke-user with "
                "Private lesson source text about retrieval practice must not leak into redacted evidence. "
                "Private video-slice enrichment about desirable difficulty must not leak into shared evidence. "
                "Private learner answer: retrieval practice strengthens recall by forcing active reconstruction. "
                f"path={LOCAL_HOME_FIXTURE}/project secret=supersecret123"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "learning_flow_incomplete")
        self.assertIn("<private-user>", serialized)
        self.assertIn("<private-source-text>", serialized)
        self.assertIn("<private-enrichment-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("secret=<redacted>", serialized)
        self.assertNotIn("platform-lesson-smoke-user", serialized)
        self.assertNotIn("Private lesson source text", serialized)
        self.assertNotIn("Private video-slice enrichment", serialized)
        self.assertNotIn("Private learner answer", serialized)
        self.assertNotIn(LOCAL_HOME_FIXTURE, serialized)
        self.assertNotIn("supersecret123", serialized)

    def test_importer_lesson_report_classifies_fixture_problem(self) -> None:
        report = importer_lesson.failure_report(
            importer_lesson.ImporterLessonVerificationError(
                f"Cannot read fixture {LOCAL_HOME_FIXTURE}/project/fixtures/notebooklm.json: missing"
            )
        )

        self.assertEqual(report["classification"], "fixture_unavailable")
        self.assertIn("--fixture <path>", " ".join(report["next_steps"]))
        self.assertIn("<local-path>", json.dumps(report, ensure_ascii=False, sort_keys=True))

    def test_importer_lesson_report_redacts_private_fixture_text(self) -> None:
        report = importer_lesson.failure_report(
            importer_lesson.ImporterLessonVerificationError(
                "Agent eval report raw fixture boundary leaked private data: "
                "Private fixture web excerpt: retrieval practice improves durable recall. "
                "The lesson should connect source-bound ideas to review. "
                f"path={LOCAL_HOME_FIXTURE}/project token=supersecret123"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "privacy_leak")
        self.assertIn("<private-fixture-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("Private fixture web excerpt", serialized)
        self.assertNotIn("source-bound ideas to review", serialized)
        self.assertNotIn(LOCAL_HOME_FIXTURE, serialized)
        self.assertNotIn("supersecret123", serialized)

    def test_importer_lesson_human_failure_is_actionable_and_redacted(self) -> None:
        report = importer_lesson.failure_report(
            importer_lesson.ImporterLessonVerificationError(
                f"Cannot read fixture {LOCAL_HOME_FIXTURE}/project/fixtures/notebooklm.json: missing"
            )
        )

        message = importer_lesson.format_failure_for_human(report)

        self.assertIn("verify_importer_lesson_flow failed:", message)
        self.assertIn("classification: fixture_unavailable", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("--fixture <path>", message)
        self.assertIn("<local-path>", message)
        self.assertNotIn(LOCAL_HOME_FIXTURE, message)

    def test_ecosystem_eval_report_classifies_retrieval_unhealthy(self) -> None:
        report = ecosystem_eval.failure_report(
            ecosystem_eval.VerificationError(
                "Retrieval must be healthy for the ecosystem eval flow. "
                "Use STUDY_ANYTHING_RETRIEVAL_BACKEND=memory for local Skill Mode."
            )
        )

        self.assertEqual(report["classification"], "retrieval_unhealthy")
        self.assertIn("STUDY_ANYTHING_RETRIEVAL_BACKEND=memory", " ".join(report["next_steps"]))
        self.assertTrue(report["privacy"]["external_eval_stdout_stderr_redacted"])

    def test_ecosystem_eval_human_failure_is_actionable_and_redacted(self) -> None:
        report = ecosystem_eval.failure_report(
            ecosystem_eval.VerificationError(
                "deepeval external eval failed.\n"
                "stdout:\nPrivate importer note: AI PM learning improves with retrieval evidence.\n"
                "stderr:\nPrivate platform browser/video context: the learner needs a term map. "
                "Private " + "answer: source evidence plus feedback makes recall more durable. "
                f"path={LOCAL_HOME_FIXTURE}/project?api_key=supersecret123"
            )
        )

        message = ecosystem_eval.format_failure_for_human(report)

        self.assertIn("verify_platform_ecosystem_eval_flow failed:", message)
        self.assertIn("classification: external_eval_failed", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("run_external_agent_evals.py", message)
        self.assertIn("<private-importer-text>", message)
        self.assertIn("<private-platform-context>", message)
        self.assertIn("<private-answer>", message)
        self.assertIn("<local-path>", message)
        self.assertIn("api_key=<redacted>", message)
        self.assertNotIn("Private importer note", message)
        self.assertNotIn("Private platform browser/video context", message)
        self.assertNotIn("Private answer", message)
        self.assertNotIn(LOCAL_HOME_FIXTURE, message)
        self.assertNotIn("supersecret123", message)

    def test_ecosystem_eval_report_redacts_external_eval_stdout_stderr(self) -> None:
        local_home = LOCAL_HOME_FIXTURE
        report = ecosystem_eval.failure_report(
            ecosystem_eval.VerificationError(
                "deepeval external eval failed.\n"
                "stdout:\nPrivate importer note: AI PM learning improves when concepts, source evidence, glossary terms, feedback, and spaced review are connected.\n"
                "stderr:\nPrivate platform browser/video context: the learner needs a term map for retrieval practice, mastery deltas, and source-grounded synthesis. "
                "Private " + "answer: source evidence plus feedback makes recall more durable. "
                f"path={local_home}/project?api_key=supersecret123"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "external_eval_failed")
        self.assertIn("<private-importer-text>", serialized)
        self.assertIn("<private-platform-context>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("api_key=<redacted>", serialized)
        self.assertNotIn("Private importer note", serialized)
        self.assertNotIn("Private platform browser/video context", serialized)
        self.assertNotIn("Private answer", serialized)
        self.assertNotIn(local_home, serialized)
        self.assertNotIn("supersecret123", serialized)

    def test_platform_agent_tools_report_classifies_manifest_failure(self) -> None:
        report = platform_agent_tools.failure_report(
            platform_agent_tools.VerificationError(
                "Platform manifest is missing required tools: ['study_anything_run']"
            )
        )

        self.assertEqual(report["classification"], "manifest_invalid")
        self.assertIn("generate_platform_agent_assets.py", " ".join(report["next_steps"]))

    def test_platform_agent_tools_human_failure_is_actionable(self) -> None:
        report = platform_agent_tools.failure_report(
            platform_agent_tools.VerificationError(
                "Platform manifest is missing required tools: ['study_anything_run']"
            )
        )

        message = platform_agent_tools.format_failure_for_human(report)

        self.assertIn("verify_platform_agent_tools failed:", message)
        self.assertIn("classification: manifest_invalid", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("generate_platform_agent_assets.py", message)

    def test_platform_agent_tools_report_redacts_private_tool_smoke_data(self) -> None:
        report = platform_agent_tools.failure_report(
            platform_agent_tools.VerificationError(
                "Platform evidence leaked private data: "
                "Private platform tool smoke source text must stay out of audit artifacts. "
                "Private enrichment web and video context must stay out of redacted evidence. "
                "Private platform tool smoke answer. "
                f"platform-tools-smoke-user path={LOCAL_HOME_FIXTURE}/project token=supersecret123"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "privacy_leak")
        self.assertIn("<private-source-text>", serialized)
        self.assertIn("<private-enrichment-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<private-user>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("Private platform tool smoke source", serialized)
        self.assertNotIn("Private enrichment web and video", serialized)
        self.assertNotIn("Private platform tool smoke answer", serialized)
        self.assertNotIn("platform-tools-smoke-user", serialized)
        self.assertNotIn(LOCAL_HOME_FIXTURE, serialized)
        self.assertNotIn("supersecret123", serialized)

    def test_skill_cli_human_failure_is_actionable_and_redacted(self) -> None:
        skill_cli = load_script("verify_skill_cli_flow")
        report = skill_cli.failure_report(
            skill_cli.SkillCliFlowError(
                "Connection refused for skill-smoke-user with "
                "A learning loop should bind a question to its source, grade a grounded answer, "
                "update mastery, and synthesize a reusable insight. "
                f"path={LOCAL_HOME_FIXTURE}/project token=supersecret123"
            )
        )

        message = skill_cli.format_failure_for_human(report)

        self.assertIn("verify_skill_cli_flow failed:", message)
        self.assertIn("classification: api_unreachable", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("./scripts/launch_skill_mode.sh", message)
        self.assertIn("<private-user>", message)
        self.assertIn("<private-source-text>", message)
        self.assertIn("<local-path>", message)
        self.assertIn("token=<redacted>", message)
        self.assertNotIn("skill-smoke-user", message)
        self.assertNotIn(LOCAL_HOME_FIXTURE, message)
        self.assertNotIn("supersecret123", message)


if __name__ == "__main__":
    unittest.main()
