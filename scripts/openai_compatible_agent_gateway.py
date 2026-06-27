#!/usr/bin/env python3
"""User-owned HTTP agent gateway for OpenAI-compatible chat-completion APIs."""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
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
AUTO_MODES = {"", "auto"}
UPSTREAM_MODES = {"upstream", "openai", "openai-compatible", "openai_compatible"}
UPSTREAM_REQUIRED_ENV = (
    "AGENT_LLM_BASE_URL",
    "AGENT_LLM_API_KEY",
    "AGENT_LLM_MODEL",
)
SENSITIVE_URL_KEYS = {
    "api_key",
    "apikey",
    "access_key",
    "access_token",
    "auth",
    "authorization",
    "bearer",
    "client_secret",
    "key",
    "password",
    "secret",
    "token",
}
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
CONTRACT_ONLY_RECOVERY_STEPS = [
    "python3 scripts/verify_openai_compatible_gateway.py --contract-only",
    "python3 scripts/verify_agent_gateway_hardening.py --contract-only",
    "python3 scripts/verify_external_agent_adapter_hardening.py --contract-only",
]


def _privacy_contract() -> dict[str, Any]:
    return {
        "study_anything_stores_model_keys": False,
        "gateway_keeps_keys_in_environment": True,
        "raw_authorization_returned": False,
        "raw_task_payload_returned_in_errors": False,
    }


def _gateway_mode() -> str:
    return _env("AGENT_GATEWAY_MODE", "auto").lower()


def _missing_upstream_config() -> list[str]:
    return [name for name in UPSTREAM_REQUIRED_ENV if not _env(name)]


def _configuration_help() -> list[str]:
    return [
        "Set AGENT_LLM_BASE_URL, AGENT_LLM_API_KEY, and AGENT_LLM_MODEL for upstream mode.",
        "Or run with --dry-run / AGENT_GATEWAY_MODE=dry_run for a zero-configuration local demo.",
        "If WorkBuddy, Kimi Work, Codex, or another platform Agent is your model exit, let that Agent call Study Anything directly instead of running this gateway long-term.",
    ]


def _redact_diagnostic_text(text: str) -> str:
    value = text or ""
    value = re.sub(
        r"(?i)\b(authorization\s*[:=]\s*(?:bearer\s+)?)[A-Za-z0-9._~+/=-]{8,}",
        r"\1<redacted>",
        value,
    )
    value = re.sub(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b", "sk-<redacted>", value)
    value = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|credential)\s*[:=]\s*['\"]?[^\s,'\"}]+",
        r"\1=<redacted>",
        value,
    )
    value = re.sub(r"/Users/[^\s,'\"<>]+", "<local-path>", value)
    value = re.sub(r"/private/tmp/[^\s,'\"<>]+", "<temp-path>", value)
    value = re.sub(r"/tmp/[^\s,'\"<>]+", "<temp-path>", value)
    value = re.sub(r"/private/var/folders/[^\s,'\"<>]+", "<temp-path>", value)
    value = re.sub(r"/var/folders/[^\s,'\"<>]+", "<temp-path>", value)
    return value[:1000]


def _upstream_failure_help() -> list[str]:
    return [
        "The gateway process is running, but its upstream model exit did not return a usable response.",
        "Check gateway health first: curl http://127.0.0.1:8787/health",
        "If /health reports mode=dry_run, register that dry-run endpoint for a zero-key local demo.",
        "If /health reports mode=upstream, verify AGENT_LLM_BASE_URL, AGENT_LLM_API_KEY, AGENT_LLM_MODEL, and AGENT_LLM_TIMEOUT_SECONDS inside the gateway process.",
        "If WorkBuddy, Kimi Work, Codex, or another platform Agent owns your model credentials, prefer letting that Agent call Study Anything directly.",
    ]


def _http_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    return _redact_diagnostic_text(body)[:500]


def _upstream_http_failure_message(status_code: int, detail: str) -> str:
    lines = [f"Upstream LLM returned HTTP {status_code}."]
    if detail:
        lines.append(f"Redacted upstream response: {detail}")
    if status_code in {401, 403}:
        lines.extend(
            [
                "This usually means the gateway's upstream key, account, or model permission is not valid.",
                "Check AGENT_LLM_API_KEY and confirm the key belongs to the provider configured by AGENT_LLM_BASE_URL.",
            ]
        )
    elif status_code == 404:
        lines.extend(
            [
                "This usually means AGENT_LLM_BASE_URL or AGENT_LLM_MODEL does not match the upstream provider.",
                "Use a base URL ending at the API root, for example https://api.example.com/v1.",
            ]
        )
    elif status_code == 429:
        lines.extend(
            [
                "The upstream provider reported rate limit, quota, or billing exhaustion.",
                "Wait and retry, choose another user-owned Agent exit, or switch to dry_run for local validation.",
            ]
        )
    elif 500 <= status_code <= 599:
        lines.extend(
            [
                "The upstream provider returned a server-side error.",
                "Retry later, test the provider endpoint directly, or switch to dry_run to isolate Study Anything.",
            ]
        )
    else:
        lines.append("Check the upstream provider configuration and retry.")
    return "\n".join(lines)


def _upstream_failure_payload(exc: RuntimeError) -> dict[str, Any]:
    return {
        "status": "error",
        "message": _redact_diagnostic_text(str(exc)),
        "diagnostic_code": "upstream_unavailable",
        "mode": "upstream",
        "next_steps": _upstream_failure_help(),
        "privacy": _privacy_contract(),
    }


def _dry_run_reason(mode: str, missing: list[str]) -> str:
    if mode in DRY_RUN_MODES:
        return "explicit dry-run mode"
    if missing:
        return "missing upstream config"
    return "auto mode"


def _dry_run_health_payload() -> dict[str, Any]:
    mode = _gateway_mode()
    missing = _missing_upstream_config()
    return {
        "status": "ok",
        "provider": "openai-compatible",
        "mode": "dry_run",
        "dry_run_reason": _dry_run_reason(mode, missing),
        "model": "dry-run-deterministic",
        "configured": True,
        "upstream_configured": not missing,
        "missing_upstream_env": missing,
        "next_steps": [] if mode in DRY_RUN_MODES else _configuration_help(),
        "capabilities": GATEWAY_CAPABILITIES,
        "privacy": _privacy_contract(),
    }


def _is_dry_run() -> bool:
    mode = _gateway_mode()
    if mode in DRY_RUN_MODES:
        return True
    if mode in AUTO_MODES and _missing_upstream_config():
        return True
    return False


def _startup_diagnostics(host: str, port: int) -> tuple[bool, list[str]]:
    mode = _gateway_mode()
    missing = _missing_upstream_config()
    endpoint = f"http://{host}:{port}"
    lines = [
        "Study Anything OpenAI-compatible Agent Gateway",
        f"- health: {endpoint}/health",
        f"- invoke: {endpoint}/invoke",
    ]
    if _is_dry_run():
        reason = _dry_run_reason(mode, missing)
        lines.extend(
            [
                f"- mode: dry_run ({reason})",
                "- model: dry-run-deterministic",
                "- note: no API key is required and no model cost will be incurred.",
            ]
        )
        if missing:
            lines.append(f"- missing upstream env: {', '.join(missing)}")
        return True, lines

    if mode not in UPSTREAM_MODES:
        lines.append(f"- error: unsupported AGENT_GATEWAY_MODE={mode!r}")
        lines.extend(f"- next: {step}" for step in _configuration_help())
        return False, lines

    if missing:
        lines.extend(
            [
                "- mode: upstream",
                f"- error: missing upstream env: {', '.join(missing)}",
            ]
        )
        lines.extend(f"- next: {step}" for step in _configuration_help())
        return False, lines

    safe_base_url = _redact_base_url_for_diagnostics(_env("AGENT_LLM_BASE_URL"))
    try:
        _chat_completions_url()
        _upstream_timeout_seconds()
    except GatewayConfigurationError as exc:
        lines.extend(
            [
                "- mode: upstream",
                f"- base_url: {safe_base_url}",
                f"- error: {exc}",
            ]
        )
        lines.extend(f"- next: {step}" for step in _configuration_help())
        return False, lines

    lines.extend(
        [
            "- mode: upstream",
            f"- base_url: {safe_base_url}",
            f"- model: {_env('AGENT_LLM_MODEL')}",
            "- secret: AGENT_LLM_API_KEY is loaded from environment and will not be logged.",
        ]
    )
    return True, lines


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


def _redact_base_url_for_diagnostics(base_url: str) -> str:
    """Return a useful upstream URL display string without credentials."""

    value = base_url.strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
    except ValueError:
        return "<invalid-url>"
    if not parts.scheme or not parts.netloc:
        return value.split("?", 1)[0]

    host = parts.hostname or ""
    netloc = host
    if parts.username or parts.password:
        netloc = f"<redacted>@{host}"
    try:
        port = parts.port
    except ValueError:
        host_port = parts.netloc.rsplit("@", 1)[-1]
        netloc = f"<redacted>@{host_port}" if parts.username or parts.password else host_port
    else:
        if port is not None:
            netloc = f"{netloc}:{port}"

    query_pairs = []
    for key, item_value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in SENSITIVE_URL_KEYS or item_value.startswith("sk-"):
            query_pairs.append((key, "<redacted>"))
        else:
            query_pairs.append((key, item_value))
    query = urlencode(query_pairs).replace("%3Credacted%3E", "<redacted>")
    return urlunsplit((parts.scheme, netloc, parts.path, query, ""))


def _chat_completions_url() -> str:
    base_url = _env("AGENT_LLM_BASE_URL")
    if not base_url:
        raise GatewayConfigurationError("AGENT_LLM_BASE_URL is required.")
    try:
        parts = urlsplit(base_url)
    except ValueError as exc:
        raise GatewayConfigurationError("AGENT_LLM_BASE_URL must be a valid URL.") from exc
    if not parts.scheme or not parts.netloc:
        raise GatewayConfigurationError(
            "AGENT_LLM_BASE_URL must include a scheme and host, for example https://api.example.com/v1."
        )
    try:
        _ = parts.port
    except ValueError as exc:
        raise GatewayConfigurationError(
            "AGENT_LLM_BASE_URL has an invalid port. Replace placeholders like host:port with a real upstream URL."
        ) from exc
    if parts.username or parts.password or parts.query:
        raise GatewayConfigurationError(
            "AGENT_LLM_BASE_URL must not include credentials or query parameters. Put secrets in AGENT_LLM_API_KEY."
        )
    path = parts.path.rstrip("/")
    if not path.endswith("/chat/completions"):
        path = f"{path}/chat/completions"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


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


def _upstream_timeout_seconds() -> int:
    raw_timeout = _env("AGENT_LLM_TIMEOUT_SECONDS", "120")
    try:
        timeout = int(raw_timeout)
    except ValueError as exc:
        raise GatewayConfigurationError(
            "AGENT_LLM_TIMEOUT_SECONDS must be an integer number of seconds."
        ) from exc
    if timeout <= 0:
        raise GatewayConfigurationError("AGENT_LLM_TIMEOUT_SECONDS must be greater than 0.")
    return timeout


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
        try:
            values = json.loads(extra_body)
        except json.JSONDecodeError as exc:
            raise GatewayConfigurationError(
                "AGENT_LLM_EXTRA_BODY_JSON must be a valid JSON object."
            ) from exc
        if not isinstance(values, dict):
            raise GatewayConfigurationError("AGENT_LLM_EXTRA_BODY_JSON must be a JSON object.")
        request_body.update(values)

    timeout = _upstream_timeout_seconds()
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
        with urllib.request.urlopen(request, timeout=timeout) as response:
            upstream = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(_upstream_http_failure_message(exc.code, _http_error_detail(exc))) from exc
    except urllib.error.URLError as exc:
        diagnostic = _redact_diagnostic_text(str(getattr(exc, "reason", exc)))
        raise RuntimeError(f"Upstream LLM is unavailable. Diagnostic: {diagnostic}") from exc
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
            self._send(_dry_run_health_payload())
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
                    "next_steps": _configuration_help(),
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
        except GatewayConfigurationError as exc:
            self._send(
                {
                    "status": "error",
                    "message": str(exc),
                    "diagnostic_code": "configuration_required",
                    "next_steps": _configuration_help(),
                    "privacy": _privacy_contract(),
                },
                status_code=503,
            )
            return
        except (ValueError, json.JSONDecodeError) as exc:
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
            self._send(_upstream_failure_payload(exc), status_code=502)
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the deterministic local agent without upstream model credentials.",
    )
    args = parser.parse_args()
    if args.dry_run:
        os.environ["AGENT_GATEWAY_MODE"] = "dry_run"
    ok, lines = _startup_diagnostics(args.host, args.port)
    for line in lines:
        print(line, file=sys.stderr, flush=True)
    if not ok:
        sys.exit(2)
    try:
        server = HTTPServer((args.host, args.port), OpenAICompatibleAgentHandler)
    except OSError as exc:
        alternate_port = args.port + 1
        alternate_command = (
            "python3 scripts/openai_compatible_agent_gateway.py "
            f"--host {args.host} --port {alternate_port}"
        )
        if args.dry_run:
            alternate_command += " --dry-run"
        alternate_endpoint = f"http://{args.host}:{alternate_port}/invoke"
        if exc.errno == errno.EADDRINUSE:
            print(
                f"Study Anything gateway port is already in use: {args.host}:{args.port}.",
                file=sys.stderr,
                flush=True,
            )
            print(
                "Set --port to a free port, or stop the process currently using this port.",
                file=sys.stderr,
                flush=True,
            )
            print(f"Try: {alternate_command}", file=sys.stderr, flush=True)
            print(
                "Then register the matching endpoint: "
                "python3 scripts/study_anything_cli.py agent-add-http "
                f"--endpoint {alternate_endpoint} --set-default",
                file=sys.stderr,
                flush=True,
            )
        elif exc.errno in {errno.EPERM, errno.EACCES}:
            print(
                f"Study Anything gateway cannot listen on {args.host}:{args.port} from this runner.",
                file=sys.stderr,
                flush=True,
            )
            print(
                "This usually means the current agent sandbox blocks localhost listening sockets.",
                file=sys.stderr,
                flush=True,
            )
            print(
                "Run from a normal terminal or host shell, then retry the same gateway command.",
                file=sys.stderr,
                flush=True,
            )
            print(
                "To prove no-socket contracts in this sandbox, run:",
                file=sys.stderr,
                flush=True,
            )
            for step in CONTRACT_ONLY_RECOVERY_STEPS:
                print(f"  - {step}", file=sys.stderr, flush=True)
            print(
                "These contract-only checks do not replace the runtime gateway smoke on a host terminal.",
                file=sys.stderr,
                flush=True,
            )
            print(
                "For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                f"Study Anything gateway failed to bind {args.host}:{args.port}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            print(
                "Try another --port, then run python3 scripts/diagnose_adoption.py if it still fails.",
                file=sys.stderr,
                flush=True,
            )
        sys.exit(2)
    server.serve_forever()


if __name__ == "__main__":
    main()
