from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from study_anything.core.agent_registry import AgentRegistry, AgentRouter
from study_anything.core.security import REDACTED, redact_mapping
from study_anything.core.tracing import OMITTED, LangfuseTraceSink, TraceSink, sanitize_trace_metadata
from study_anything.core.workflow import LearningWorkflow, new_session, submit_reading


class RecordingTraceSink(TraceSink):
    enabled = True

    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def capture_event(
        self,
        *,
        name: str,
        session_id: str,
        user_hash: str,
        metadata: dict[str, object] | None = None,
    ) -> str:
        self.events.append(
            {
                "name": name,
                "session_id": session_id,
                "user_hash": user_hash,
                "metadata": metadata or {},
            }
        )
        return f"trace-{len(self.events)}"


class FakeObservation:
    trace_id = "langfuse-trace"

    def end(self) -> None:
        return None


class FakeLangfuseClient:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.metadata: dict[str, object] | None = None

    def start_observation(self, **values: object) -> FakeObservation:
        if self.should_fail:
            raise RuntimeError("tracing unavailable")
        self.metadata = values.get("metadata")  # type: ignore[assignment]
        return FakeObservation()


class TracingTests(unittest.TestCase):
    def test_recursive_secret_redaction(self) -> None:
        redacted = redact_mapping(
            {
                "nested": {"api_token": "secret", "safe": "ok"},
                "items": [{"password": "secret"}],
            }
        )

        self.assertEqual(redacted["nested"]["api_token"], REDACTED)  # type: ignore[index]
        self.assertEqual(redacted["items"][0]["password"], REDACTED)  # type: ignore[index]

    def test_secret_looking_values_are_redacted_even_under_safe_keys(self) -> None:
        redacted = redact_mapping(
            {
                "note": "sk-proj-agentVerifierSecretToken000000",
                "headers": {"safe": "Bearer agentVerifierSecretToken000000"},
                "safe": "plain value",
            }
        )

        self.assertEqual(redacted["note"], REDACTED)
        self.assertEqual(redacted["headers"]["safe"], REDACTED)  # type: ignore[index]
        self.assertEqual(redacted["safe"], "plain value")

    def test_trace_metadata_omits_learning_prose(self) -> None:
        sanitized = sanitize_trace_metadata(
            {
                "source_title": "Private reading title",
                "insight": "Private synthesis",
                "message": "Private HITL prose",
                "api_token": "secret",
                "level": 0.5,
                "node": "synthesist_node",
                "agent": {"provider_id": "private-agent", "metadata": {"terms": ["private"]}},
            }
        )

        self.assertEqual(sanitized["source_title"], OMITTED)
        self.assertEqual(sanitized["insight"], OMITTED)
        self.assertEqual(sanitized["message"], OMITTED)
        self.assertEqual(sanitized["api_token"], REDACTED)
        self.assertEqual(sanitized["level"], 0.5)
        self.assertEqual(sanitized["node"], "synthesist_node")
        self.assertEqual(sanitized["agent"]["provider_id"], "private-agent")  # type: ignore[index]
        self.assertEqual(sanitized["agent"]["metadata"], OMITTED)  # type: ignore[index]

    def test_workflow_events_receive_trace_ids(self) -> None:
        sink = RecordingTraceSink()
        registry = AgentRegistry()
        registry.set_demo_defaults("local-user")
        workflow = LearningWorkflow(AgentRouter(registry), trace_sink=sink)
        state = new_session("local-user", trace_sink=sink)
        state = submit_reading(
            state,
            source_type="local_text",
            reference="demo://source",
            title="Private title",
            text="Private reading body.",
            trace_sink=sink,
        )

        state = workflow.run(state)

        self.assertGreater(len(sink.events), 2)
        self.assertTrue(all(event.trace_id for event in state.events))

    def test_langfuse_v4_observation_is_sanitized(self) -> None:
        client = FakeLangfuseClient()
        sink = LangfuseTraceSink(client=client)

        trace_id = sink.capture_event(
            name="insight.generated",
            session_id="session",
            user_hash="hash",
            metadata={"insight": "Private insight", "level": 0.5},
        )

        self.assertEqual(trace_id, "langfuse-trace")
        self.assertEqual(client.metadata, {"insight": OMITTED, "level": 0.5})

    def test_langfuse_failure_does_not_interrupt_learning(self) -> None:
        sink = LangfuseTraceSink(client=FakeLangfuseClient(should_fail=True))

        self.assertIsNone(
            sink.capture_event(
                name="session.created",
                session_id="session",
                user_hash="hash",
            )
        )


if __name__ == "__main__":
    unittest.main()
