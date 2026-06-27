from __future__ import annotations

import errno
import io
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]


SPEC = importlib.util.spec_from_file_location(
    "openai_compatible_agent_gateway",
    REPO_ROOT / "scripts" / "openai_compatible_agent_gateway.py",
)
assert SPEC is not None and SPEC.loader is not None
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class OpenAICompatibleAgentGatewayTests(unittest.TestCase):
    def test_invocation_keeps_key_in_gateway_and_adds_safe_usage(self) -> None:
        upstream = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "status": "ok",
                                "content": "Focus on retrieval practice",
                                "confidence": 0.9,
                                "metadata": {},
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
            },
        }
        task = {
            "task_type": "quiz.generate",
            "source": {
                "reference": "local://notes",
                "excerpt_hash": "excerpt-hash",
            },
        }
        captured_request = None

        def fake_urlopen(request: object, timeout: int) -> FakeResponse:
            nonlocal captured_request
            captured_request = request
            self.assertEqual(timeout, 120)
            return FakeResponse(upstream)

        with patch.dict(
            os.environ,
            {
                "AGENT_LLM_BASE_URL": "https://api.example.test/v1",
                "AGENT_LLM_API_KEY": "gateway-secret",
                "AGENT_LLM_MODEL": "example-model",
            },
            clear=True,
        ):
            with patch.object(gateway.urllib.request, "urlopen", fake_urlopen):
                result = gateway._invoke_upstream(task)

        assert captured_request is not None
        self.assertEqual(captured_request.full_url, "https://api.example.test/v1/chat/completions")
        self.assertEqual(captured_request.headers["Authorization"], "Bearer gateway-secret")
        self.assertEqual(result["citations"][0]["reference"], "local://notes")
        self.assertEqual(result["metadata"]["tokens"]["total"], 30)
        self.assertNotIn("gateway-secret", json.dumps(result))

    def test_json_fence_cleanup_supports_imperfect_models(self) -> None:
        self.assertEqual(
            gateway._clean_json_content('```json\n{"status":"ok"}\n```'),
            '{"status":"ok"}',
        )

    def test_upstream_result_is_normalised_before_api_validation(self) -> None:
        result = gateway._normalise_agent_result(
            {
                "task_type": "answer.grade",
                "source": {
                    "reference": "local://source",
                    "excerpt_hash": "hash-123",
                },
            },
            {
                "status": "ok",
                "content": "Good enough.",
                "citations": "local://source",
                "score": "0.82",
                "confidence": "0.76",
                "feedback": {"summary": "Grounded"},
                "metadata": "not an object",
            },
        )

        self.assertEqual(
            result["citations"],
            [{"reference": "local://source", "excerpt_hash": "hash-123"}],
        )
        self.assertEqual(result["score"], 0.82)
        self.assertEqual(result["confidence"], 0.76)
        self.assertEqual(result["feedback"], "{'summary': 'Grounded'}")
        self.assertEqual(result["metadata"], {})

    def test_answer_grade_missing_score_gets_conservative_default(self) -> None:
        result = gateway._normalise_agent_result(
            {
                "task_type": "answer.grade",
                "answers": [{"item_id": "q1", "text": "Learner answer"}],
                "source": {"reference": "local://source"},
            },
            {
                "status": "ok",
                "content": "The answer is partially grounded.",
                "citations": [],
                "metadata": {},
            },
        )

        self.assertEqual(result["score"], 0.5)
        self.assertEqual(result["feedback"], "The answer is partially grounded.")
        self.assertEqual(result["metadata"]["normalization_warning"], "missing_score_defaulted")

    def test_gateway_requires_private_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(gateway.GatewayConfigurationError, "AGENT_LLM_BASE_URL"):
                gateway._chat_completions_url()

    def test_chat_completions_url_accepts_full_endpoint_without_double_append(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AGENT_LLM_BASE_URL": "https://api.example.test/v1/chat/completions",
            },
            clear=True,
        ):
            self.assertEqual(
                gateway._chat_completions_url(),
                "https://api.example.test/v1/chat/completions",
            )

    def test_chat_completions_url_rejects_placeholder_port(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AGENT_LLM_BASE_URL": "https://api.example.test:port/v1",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(gateway.GatewayConfigurationError, "invalid port"):
                gateway._chat_completions_url()

    def test_chat_completions_url_rejects_credentials_and_query_without_leaking(self) -> None:
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        with patch.dict(
            os.environ,
            {
                "AGENT_LLM_BASE_URL": f"https://user:secret@api.example.test/v1?api_key={secret}",
            },
            clear=True,
        ):
            with self.assertRaises(gateway.GatewayConfigurationError) as context:
                gateway._chat_completions_url()

        message = str(context.exception)
        self.assertIn("must not include credentials or query parameters", message)
        self.assertNotIn("user:secret", message)
        self.assertNotIn(secret, message)

    def test_upstream_config_rejects_invalid_extra_body_as_configuration_error(self) -> None:
        task = {
            "task_type": "quiz.generate",
            "source": {"reference": "local://source"},
        }
        with patch.dict(
            os.environ,
            {
                "AGENT_LLM_BASE_URL": "https://api.example.test/v1",
                "AGENT_LLM_API_KEY": "gateway-secret",
                "AGENT_LLM_MODEL": "example-model",
                "AGENT_LLM_EXTRA_BODY_JSON": "{bad json",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                gateway.GatewayConfigurationError,
                "AGENT_LLM_EXTRA_BODY_JSON must be a valid JSON object",
            ):
                gateway._invoke_upstream(task)

    def test_upstream_config_rejects_invalid_timeout_as_configuration_error(self) -> None:
        task = {
            "task_type": "quiz.generate",
            "source": {"reference": "local://source"},
        }
        with patch.dict(
            os.environ,
            {
                "AGENT_LLM_BASE_URL": "https://api.example.test/v1",
                "AGENT_LLM_API_KEY": "gateway-secret",
                "AGENT_LLM_MODEL": "example-model",
                "AGENT_LLM_TIMEOUT_SECONDS": "soon",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                gateway.GatewayConfigurationError,
                "AGENT_LLM_TIMEOUT_SECONDS must be an integer",
            ):
                gateway._invoke_upstream(task)

    def test_upstream_http_error_is_actionable_and_redacted(self) -> None:
        secret = "sk-" + "proj-private-upstream-token"
        task = {
            "task_type": "quiz.generate",
            "source": {"reference": "local://source"},
        }
        body = json.dumps({"error": {"message": f"invalid api_key={secret}"}}).encode("utf-8")

        def fake_urlopen(_request: object, timeout: int) -> object:
            self.assertEqual(timeout, 120)
            raise gateway.urllib.error.HTTPError(
                "https://api.example.test/v1/chat/completions",
                401,
                "Unauthorized",
                hdrs=None,
                fp=io.BytesIO(body),
            )

        with patch.dict(
            os.environ,
            {
                "AGENT_LLM_BASE_URL": "https://api.example.test/v1",
                "AGENT_LLM_API_KEY": secret,
                "AGENT_LLM_MODEL": "example-model",
            },
            clear=True,
        ):
            with patch.object(gateway.urllib.request, "urlopen", fake_urlopen):
                with self.assertRaises(RuntimeError) as context:
                    gateway._invoke_upstream(task)

        message = str(context.exception)
        self.assertIn("HTTP 401", message)
        self.assertIn("AGENT_LLM_API_KEY", message)
        self.assertIn("key", message)
        self.assertNotIn(secret, message)
        self.assertIn("<redacted>", message)

    def test_dry_run_gateway_needs_no_private_configuration(self) -> None:
        task = {
            "task_type": "teach.glossary",
            "session_id": "dry-run",
            "source": {
                "reference": "local://dry-run",
                "title": "Dry Run Source",
                "text": "Retrieval practice and source evidence improve mastery.",
                "excerpt_hash": "dry-run-hash",
            },
        }
        with patch.dict(os.environ, {"AGENT_GATEWAY_MODE": "dry_run"}, clear=True):
            result = gateway._invoke_agent(task)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metadata"]["gateway_mode"], "dry_run")
        self.assertIsInstance(result["content"], list)
        self.assertEqual(result["citations"][0]["reference"], "local://dry-run")

    def test_auto_mode_without_upstream_config_uses_dry_run(self) -> None:
        task = {
            "task_type": "quiz.generate",
            "session_id": "auto-dry-run",
            "source": {"reference": "local://auto", "text": "Source evidence improves recall."},
        }
        with patch.dict(os.environ, {}, clear=True):
            result = gateway._invoke_agent(task)
            ok, lines = gateway._startup_diagnostics("127.0.0.1", 8787)

        self.assertTrue(ok)
        self.assertEqual(result["metadata"]["gateway_mode"], "dry_run")
        self.assertTrue(any("mode: dry_run" in line for line in lines))
        self.assertIn("AGENT_LLM_API_KEY", "\n".join(lines))

    def test_auto_dry_run_health_explains_missing_upstream_config(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            payload = gateway._dry_run_health_payload()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(payload["dry_run_reason"], "missing upstream config")
        self.assertFalse(payload["upstream_configured"])
        self.assertIn("AGENT_LLM_API_KEY", payload["missing_upstream_env"])
        self.assertTrue(any("AGENT_LLM_API_KEY" in step for step in payload["next_steps"]))
        self.assertFalse(payload["privacy"]["study_anything_stores_model_keys"])

    def test_explicit_dry_run_health_does_not_claim_upstream_setup_needed(self) -> None:
        with patch.dict(os.environ, {"AGENT_GATEWAY_MODE": "dry_run"}, clear=True):
            payload = gateway._dry_run_health_payload()

        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(payload["dry_run_reason"], "explicit dry-run mode")
        self.assertFalse(payload["upstream_configured"])
        self.assertEqual(payload["next_steps"], [])

    def test_gateway_bind_permission_error_is_actionable(self) -> None:
        stderr = io.StringIO()
        with patch.object(
            gateway,
            "HTTPServer",
            side_effect=OSError(errno.EPERM, "Operation not permitted"),
        ):
            with patch.object(sys, "argv", ["gateway", "--dry-run", "--port", "8787"]):
                with patch.object(sys, "stderr", stderr):
                    with self.assertRaises(SystemExit) as raised:
                        gateway.main()

        self.assertEqual(raised.exception.code, 2)
        output = stderr.getvalue()
        self.assertIn("cannot listen on 127.0.0.1:8787", output)
        self.assertIn("agent sandbox blocks localhost listening sockets", output)
        self.assertIn("normal terminal", output)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", output)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", output)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", output)
        self.assertIn("do not replace the runtime gateway smoke", output)
        self.assertIn("diagnose_adoption.py", output)

    def test_gateway_port_in_use_error_is_actionable(self) -> None:
        stderr = io.StringIO()
        with patch.object(
            gateway,
            "HTTPServer",
            side_effect=OSError(errno.EADDRINUSE, "Address already in use"),
        ):
            with patch.object(sys, "argv", ["gateway", "--dry-run", "--port", "8787"]):
                with patch.object(sys, "stderr", stderr):
                    with self.assertRaises(SystemExit) as raised:
                        gateway.main()

        self.assertEqual(raised.exception.code, 2)
        output = stderr.getvalue()
        self.assertIn("port is already in use: 127.0.0.1:8787", output)
        self.assertIn("--port", output)
        self.assertIn("--port 8788 --dry-run", output)
        self.assertIn("agent-add-http --endpoint http://127.0.0.1:8788/invoke --set-default", output)

    def test_explicit_upstream_mode_reports_missing_configuration(self) -> None:
        task = {"task_type": "quiz.generate", "source": {"reference": "local://upstream"}}
        with patch.dict(os.environ, {"AGENT_GATEWAY_MODE": "upstream"}, clear=True):
            ok, lines = gateway._startup_diagnostics("127.0.0.1", 8787)
            with self.assertRaisesRegex(gateway.GatewayConfigurationError, "AGENT_LLM_MODEL"):
                gateway._invoke_agent(task)

        self.assertFalse(ok)
        self.assertIn("missing upstream env", "\n".join(lines))
        self.assertIn("AGENT_LLM_API_KEY", "\n".join(lines))

    def test_upstream_startup_diagnostics_redacts_secrets_in_base_url(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AGENT_GATEWAY_MODE": "upstream",
                "AGENT_LLM_BASE_URL": (
                    "https://user:pass@api.example.test:8443/v1?"
                    "api_key=sk-secret123&region=us&token=visiblebad#debug-fragment"
                ),
                "AGENT_LLM_API_KEY": "gateway-secret",
                "AGENT_LLM_MODEL": "example-model",
            },
            clear=True,
        ):
            ok, lines = gateway._startup_diagnostics("127.0.0.1", 8787)

        output = "\n".join(lines)
        self.assertFalse(ok)
        self.assertIn("must not include credentials or query parameters", output)
        self.assertIn("https://<redacted>@api.example.test:8443/v1", output)
        self.assertIn("api_key=<redacted>", output)
        self.assertIn("token=<redacted>", output)
        self.assertIn("region=us", output)
        self.assertNotIn("user:pass", output)
        self.assertNotIn("sk-secret123", output)
        self.assertNotIn("visiblebad", output)
        self.assertNotIn("debug-fragment", output)
        self.assertNotIn("gateway-secret", output)

    def test_upstream_startup_diagnostics_reports_placeholder_port_without_leaking(self) -> None:
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        with patch.dict(
            os.environ,
            {
                "AGENT_GATEWAY_MODE": "upstream",
                "AGENT_LLM_BASE_URL": (
                    "https://user:secret@api.example.test:port/v1?"
                    f"api_key={secret}&region=us"
                ),
                "AGENT_LLM_API_KEY": "gateway-secret",
                "AGENT_LLM_MODEL": "example-model",
            },
            clear=True,
        ):
            ok, lines = gateway._startup_diagnostics("127.0.0.1", 8787)

        output = "\n".join(lines)
        self.assertFalse(ok)
        self.assertIn("invalid port", output)
        self.assertIn("https://<redacted>@api.example.test:port/v1", output)
        self.assertIn("api_key=<redacted>", output)
        self.assertIn("region=us", output)
        self.assertNotIn("user:secret", output)
        self.assertNotIn(secret, output)
        self.assertNotIn("gateway-secret", output)

    def test_gateway_health_declares_capabilities_and_privacy(self) -> None:
        self.assertIn("quiz.generate", gateway.GATEWAY_CAPABILITIES)
        privacy = gateway._privacy_contract()

        self.assertFalse(privacy["study_anything_stores_model_keys"])
        self.assertFalse(privacy["raw_authorization_returned"])

    def test_upstream_failure_payload_is_actionable_and_private(self) -> None:
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        payload = gateway._upstream_failure_payload(
            RuntimeError(
                "Upstream LLM is unavailable with "
                f"Authorization: Bearer {secret} at /Users/example/private.log"
            )
        )
        serialized = json.dumps(payload, sort_keys=True)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["diagnostic_code"], "upstream_unavailable")
        self.assertEqual(payload["mode"], "upstream")
        self.assertIn("curl http://127.0.0.1:8787/health", " ".join(payload["next_steps"]))
        self.assertIn("AGENT_LLM_API_KEY", " ".join(payload["next_steps"]))
        self.assertFalse(payload["privacy"]["raw_task_payload_returned_in_errors"])
        self.assertFalse(payload["privacy"]["raw_authorization_returned"])
        self.assertNotIn(secret, serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertIn("<local-path>", serialized)

    def test_gateway_rejects_invalid_agent_task_shape(self) -> None:
        with self.assertRaisesRegex(ValueError, "task_type"):
            gateway._validate_agent_task({"task_type": "unsupported"})
        with self.assertRaisesRegex(ValueError, "answers"):
            gateway._validate_agent_task({"task_type": "quiz.generate", "answers": {"bad": True}})
        with self.assertRaisesRegex(ValueError, "source"):
            gateway._validate_agent_task({"task_type": "quiz.generate", "source": "raw text"})

    def test_dry_run_gateway_grades_answers_with_score(self) -> None:
        task = {
            "task_type": "answer.grade",
            "session_id": "dry-run",
            "source": {"reference": "local://dry-run"},
            "answers": [{"item_id": "q1", "text": "A grounded answer."}],
        }
        with patch.dict(os.environ, {"AGENT_GATEWAY_MODE": "mock"}, clear=True):
            result = gateway._invoke_agent(task)

        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["score"], 0)
        self.assertIn("source-grounded", result["feedback"])


if __name__ == "__main__":
    unittest.main()
