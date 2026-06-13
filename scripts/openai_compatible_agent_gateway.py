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
- teach.overview: return a JSON object in content with summary and key_points.
- teach.glossary: return a JSON array in content with terms and plain-language explanations.
- teach.examples: return a JSON object in content with examples.
- quiz.generate: return a concise focus phrase in content.
- answer.grade: return score from 0 to 1 and short feedback grounded in the source.
- insight.synthesize: return a concise reusable insight in content.
- note.scribe: return concise Markdown notes in content.
- source.verify: explain whether the reference supports verification and include score from 0 to 1.
- memory.retrieve: return concise relevant memory hints in content.
- embedding.create: return concise source terms in content.
"""

DRY_RUN_MODES = {"dry-run", "dry_run", "mock", "test"}
GATEWAY_CAPABILITIES = [
    "teach.overview",
    "teach.glossary",
    "teach.examples",
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
    "note.scribe",
    "source.verify",
    "memory.retrieve",
    "embedding.create",
]


def _privacy_contract() -> dict[str, Any]:
    return {
        "study_anything_stores_model_keys": False,
        "gateway_keeps_keys_in_environment": True,
        "raw_authorization_returned": False,
        "raw_task_payload_returned_in_errors": False,
    }


def _gateway_mode() -> str:
    return _env("AGENT_GATEWAY_MODE", "upstream").lower()


def _is_dry_run() -> bool:
    return _gateway_mode() in DRY_RUN_MODES


def _source_terms(task: dict[str, Any]) -> list[str]:
    source = task.get("source") or {}
    values = [
        str(source.get("title") or ""),
        str(source.get("reference") or ""),
        str(source.get("text") or ""),
        str((task.get("constraints") or {}).get("prompt") or ""),
    ]
    answers = task.get("answers") or []
    if isinstance(answers, list):
        values.extend(
            str(answer.get("text") or "") for answer in answers if isinstance(answer, dict)
        )
    words = [
        word.strip(".,!?;:()[]{}").lower()
        for word in " ".join(values).split()
        if word.strip()
    ]
    terms = [word for word in words if len(word) > 5]
    return terms[:4] or ["source", "evidence", "mastery"]


def _citations_for(task: dict[str, Any]) -> list[dict[str, Any]]:
    source = task.get("source") or {}
    if not isinstance(source, dict) or not source.get("reference"):
        return []
    return [
        {
            "reference": source.get("reference"),
            "excerpt_hash": source.get("excerpt_hash"),
        }
    ]


def _dry_run_result(task: dict[str, Any]) -> dict[str, Any]:
    task_type = str(task.get("task_type") or "")
    source = task.get("source") or {}
    if not isinstance(source, dict):
        source = {}
    constraints = task.get("constraints") or {}
    if not isinstance(constraints, dict):
        constraints = {}
    terms = _source_terms(task)
    title = str(source.get("title") or "the source")
    result: dict[str, Any] = {
        "status": "ok",
        "content": "Focus on " + ", ".join(terms),
        "citations": _citations_for(task),
        "confidence": 0.93,
        "metadata": {
            "gateway_mode": "dry_run",
            "provider": "openai-compatible",
            "terms": terms,
        },
    }
    if task_type == "teach.overview":
        result["content"] = {
            "summary": f"{title} explains {', '.join(terms)}.",
            "key_points": [f"Connect {term} back to the cited source." for term in terms],
            "learner_level": constraints.get("level", "beginner"),
        }
    elif task_type == "teach.glossary":
        result["content"] = [
            {
                "term": term,
                "plain_language": f"{term} is a key idea in this source.",
                "technical_definition": (
                    f"{term} should be interpreted inside the cited source context."
                ),
                "example": f"Use {term} when explaining the source-backed relationship.",
            }
            for term in terms
        ]
    elif task_type == "teach.examples":
        result["content"] = {
            "examples": [
                f"Restate {term} as a concrete learner-facing example tied to the source."
                for term in terms
            ],
            "mode": constraints.get("example_mode", "mixed"),
        }
    elif task_type == "answer.grade":
        result["score"] = 0.84 if task.get("answers") else 0.0
        result["feedback"] = "Dry-run gateway graded the answer as source-grounded."
        result["content"] = result["feedback"]
    elif task_type == "insight.synthesize":
        mastery = constraints.get("mastery_level", 0.0)
        result["content"] = f"{title} is linked to mastery level {float(mastery):.1f}."
    elif task_type == "note.scribe":
        result["content"] = f"# {title}\n\n- Review source evidence around {', '.join(terms)}."
    elif task_type == "source.verify":
        result["content"] = "Dry-run gateway accepted the source reference."
        result["score"] = 1.0 if source.get("reference") else 0.0
    elif task_type == "memory.retrieve":
        result["content"] = {
            "hints": [
                f"Previous learning should connect {term} to source evidence." for term in terms
            ]
        }
    elif task_type == "embedding.create":
        result["content"] = ",".join(terms)
        result["metadata"]["embedding_terms"] = terms
    return result


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


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if 0 <= number <= 1:
        return number
    return None


def _normalise_agent_result(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Harden upstream model output into the Study Anything AgentResult contract."""

    normalised = dict(result)
    source = task.get("source") or {}
    if not isinstance(source, dict):
        source = {}

    if source.get("reference"):
        normalised["citations"] = [
            {
                "reference": source.get("reference"),
                "excerpt_hash": source.get("excerpt_hash"),
            }
        ]
    else:
        citations = normalised.get("citations")
        normalised["citations"] = [
            {
                "reference": item.get("reference"),
                "excerpt_hash": item.get("excerpt_hash"),
            }
            for item in citations
            if isinstance(citations, list) and isinstance(item, dict)
        ] if isinstance(citations, list) else []

    metadata = normalised.get("metadata")
    normalised["metadata"] = metadata if isinstance(metadata, dict) else {}

    confidence = _coerce_float(normalised.get("confidence"))
    if confidence is not None:
        normalised["confidence"] = confidence
    elif "confidence" in normalised:
        normalised.pop("confidence")

    score = _coerce_float(normalised.get("score"))
    if score is not None:
        normalised["score"] = score
    elif "score" in normalised:
        normalised.pop("score")
    if (
        task.get("task_type") == "answer.grade"
        and normalised.get("status") == "ok"
        and "score" not in normalised
    ):
        normalised["score"] = 0.5 if task.get("answers") else 0.0
        normalised["metadata"]["normalization_warning"] = "missing_score_defaulted"

    feedback = normalised.get("feedback")
    if feedback is not None and not isinstance(feedback, str):
        normalised["feedback"] = str(feedback)
    if task.get("task_type") == "answer.grade" and not normalised.get("feedback"):
        normalised["feedback"] = str(
            normalised.get("content") or "Agent returned a normalized grade."
        )

    return normalised


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

    result = _normalise_agent_result(task, result)
    usage = upstream.get("usage") or {}
    if isinstance(result["metadata"], dict) and isinstance(usage, dict):
        result["metadata"]["tokens"] = {
            "prompt": usage.get("prompt_tokens"),
            "completion": usage.get("completion_tokens"),
            "total": usage.get("total_tokens"),
        }
    return result


def _invoke_agent(task: dict[str, Any]) -> dict[str, Any]:
    _validate_agent_task(task)
    if _is_dry_run():
        return _dry_run_result(task)
    return _invoke_upstream(task)


def _validate_agent_task(task: dict[str, Any]) -> None:
    task_type = task.get("task_type")
    if task_type not in GATEWAY_CAPABILITIES:
        raise ValueError("Agent task_type is unsupported or missing.")
    session_id = task.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        raise ValueError("Agent session_id must be a string when present.")
    for collection_name in ("quiz_items", "answers"):
        values = task.get(collection_name, [])
        if values is not None and not isinstance(values, list):
            raise ValueError(f"Agent {collection_name} must be a list when present.")
    for mapping_name in ("source", "constraints", "metadata"):
        values = task.get(mapping_name)
        if values is not None and not isinstance(values, dict):
            raise ValueError(f"Agent {mapping_name} must be an object when present.")


class OpenAICompatibleAgentHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        if _is_dry_run():
            self._send(
                {
                    "status": "ok",
                    "provider": "openai-compatible",
                    "mode": "dry_run",
                    "model": "dry-run-deterministic",
                    "configured": True,
                    "capabilities": GATEWAY_CAPABILITIES,
                    "privacy": _privacy_contract(),
                }
            )
            return
        try:
            payload = {
                "status": "ok",
                "provider": "openai-compatible",
                "mode": "upstream",
                "model": _model(),
                "configured": bool(_chat_completions_url() and _api_key()),
                "capabilities": GATEWAY_CAPABILITIES,
                "privacy": _privacy_contract(),
            }
        except GatewayConfigurationError as exc:
            self._send(
                {
                    "status": "error",
                    "message": str(exc),
                    "diagnostic_code": "configuration_required",
                    "privacy": _privacy_contract(),
                },
                status_code=503,
            )
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
            result = _invoke_agent(task)
        except (GatewayConfigurationError, ValueError, json.JSONDecodeError) as exc:
            self._send(
                {
                    "status": "error",
                    "message": str(exc),
                    "diagnostic_code": "invalid_agent_task",
                    "privacy": _privacy_contract(),
                },
                status_code=400,
            )
            return
        except RuntimeError as exc:
            self._send(
                {
                    "status": "error",
                    "message": str(exc),
                    "diagnostic_code": "upstream_unavailable",
                    "privacy": _privacy_contract(),
                },
                status_code=502,
            )
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
