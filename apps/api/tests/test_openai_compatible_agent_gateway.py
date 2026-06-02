from __future__ import annotations

import importlib.util
import json
import os
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

    def test_gateway_requires_private_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(gateway.GatewayConfigurationError, "AGENT_LLM_BASE_URL"):
                gateway._chat_completions_url()


if __name__ == "__main__":
    unittest.main()
