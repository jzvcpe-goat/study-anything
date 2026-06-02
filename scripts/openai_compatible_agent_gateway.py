#!/usr/bin/env python3
"""User-owned HTTP agent gateway for OpenAI-compatible chat-completion APIs."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


SYSTEM_PROMPT = """\
You are the reasoning layer for Study Anything, a source-bound learning system.
Return one JSON object only. Never wrap JSON in Markdown.

Required output fields:
- status: "ok", "needs_human", or "error"
- content: concise task output
- citations: source citations when a source reference exists
- confidence: number from 0 to 1
- metadata: JSON object

Task rules:
- quiz.generate: return a concise focus phrase in content.
- answer.grade: return score from 0 to 1 and short feedback grounded in the source.
- insight.synthesize: return a concise reusable insight in content.
- source.verify: explain whether the reference supports verification and include score from 0 to 1.
- embedding.create: return concise source terms in content.
"""


class GatewayConfigurationError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _chat_completions_url() -> str:
    base_url = _env("AGENT_LLM_BASE_URL")
    if not base_url:
        raise GatewayConfigurationError("AGENT_LLM_BASE_URL is required.")
    return f"{base_url.rstrip('/')}/chat/completions"


def _api_key() -> str:
    api_key = _env("AGENT_LLM_API_KEY")
    if not api_key:
        raise GatewayConfigurationError("AGENT_LLM_API_KEY is required.")
    return api_key


def _model() -> str:
    model = _env("AGENT_LLM_MODEL")
    if not model:
        raise GatewayConfigurationError("AGENT_LLM_MODEL is required.")
    return model


def _clean_json_content(content: str) -> str:
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1]).strip()
    return value


def _invoke_upstream(task: dict[str, Any]) -> dict[str, Any]:
    request_body: dict[str, Any] = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(task, ensure_ascii=False, sort_keys=True),
            },
        ],
        "response_format": {"type": "json_object"},
    }
    extra_body = _env("AGENT_LLM_EXTRA_BODY_JSON")
    if extra_body:
        values = json.loads(extra_body)
        if not isinstance(values, dict):
            raise GatewayConfigurationError("AGENT_LLM_EXTRA_BODY_JSON must be a JSON object.")
        request_body.update(values)

    request = urllib.request.Request(
        _chat_completions_url(),
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=int(_env("AGENT_LLM_TIMEOUT_SECONDS", "120")),
        ) as response:
            upstream = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Upstream LLM returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Upstream LLM is unavailable.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Upstream LLM returned malformed JSON.") from exc

    try:
        content = upstream["choices"][0]["message"]["content"]
        result = json.loads(_clean_json_content(content))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Upstream LLM did not return a structured agent result.") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Upstream LLM agent result must be a JSON object.")

    source = task.get("source") or {}
    if source.get("reference") and not result.get("citations"):
        result["citations"] = [
            {
                "reference": source["reference"],
                "excerpt_hash": source.get("excerpt_hash"),
            }
        ]
    result.setdefault("metadata", {})
    usage = upstream.get("usage") or {}
    if isinstance(result["metadata"], dict) and isinstance(usage, dict):
        result["metadata"]["tokens"] = {
            "prompt": usage.get("prompt_tokens"),
            "completion": usage.get("completion_tokens"),
            "total": usage.get("total_tokens"),
        }
    return result


class OpenAICompatibleAgentHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        try:
            payload = {
                "status": "ok",
                "provider": "openai-compatible",
                "model": _model(),
                "configured": bool(_chat_completions_url() and _api_key()),
            }
        except GatewayConfigurationError as exc:
            self._send({"status": "error", "message": str(exc)}, status_code=503)
            return
        self._send(payload)

    def do_POST(self) -> None:
        if self.path != "/invoke":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            task = json.loads(self.rfile.read(length))
            if not isinstance(task, dict):
                raise ValueError("Agent task must be a JSON object.")
            result = _invoke_upstream(task)
        except (GatewayConfigurationError, ValueError, json.JSONDecodeError) as exc:
            self._send({"status": "error", "message": str(exc)}, status_code=400)
            return
        except RuntimeError as exc:
            self._send({"status": "error", "message": str(exc)}, status_code=502)
            return
        self._send(result)

    def _send(self, payload: dict[str, Any], *, status_code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()
    HTTPServer((args.host, args.port), OpenAICompatibleAgentHandler).serve_forever()


if __name__ == "__main__":
    main()
