#!/usr/bin/env python3
"""Small standard-library CLI for the Study Anything public API."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


DEFAULT_API_PORT = "8000"
DEFAULT_API_BASE = f"http://127.0.0.1:{DEFAULT_API_PORT}"
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_DERIVED_SESSION_TITLE = "Untitled Study Session"
DEFAULT_LOCAL_AGENT_ENDPOINT = "http://127.0.0.1:8787/invoke"
DEFAULT_ENRICHMENT_REFERENCE = "local://enrichment/cli"
DEFAULT_ENRICHMENT_TITLE = "Learning Enrichment"
MAX_DERIVED_TITLE_CHARS = 72
CONTRACT_ONLY_RECOVERY_STEPS = [
    "python3 scripts/verify_openai_compatible_gateway.py --contract-only",
    "python3 scripts/verify_agent_gateway_hardening.py --contract-only",
    "python3 scripts/verify_external_agent_adapter_hardening.py --contract-only",
]
DEFAULT_HTTP_AGENT_CAPABILITIES = [
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
AUTO_AGENT_MODE_REQUIRED_CAPABILITIES = [
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
    "source.verify",
]
SECRET_QUERY_KEYS = (
    "api_key",
    "apikey",
    "access_token",
    "accesstoken",
    "authorization",
    "auth",
    "bearer",
    "client_secret",
    "clientsecret",
    "cookie",
    "credential",
    "key",
    "password",
    "secret",
    "token",
)
SECRET_VALUE_PATTERNS = [
    (
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
        "sk-<redacted>",
    ),
    (
        re.compile(
            r"(?i)\b(authorization\s*[:=]\s*(?:bearer\s+)?)[A-Za-z0-9._~+/=-]{8,}"
        ),
        r"\1<redacted>",
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|apikey|x[_-]?api[_-]?key|access[_-]?token|accesstoken|authorization|auth|bearer|client[_-]?secret|clientsecret|cookie|credential|token|secret|password)\s*[:=]\s*['\"]?[^\s,'\"}]+"
        ),
        r"\1=<redacted>",
    ),
]
LOCAL_PATH_PATTERNS = [
    re.compile(r"/Users/[^\s,'\"<>]+"),
    re.compile(r"/private/tmp/[^\s,'\"<>]+"),
    re.compile(r"/tmp/[^\s,'\"<>]+"),
    re.compile(r"/private/var/folders/[^\s,'\"<>]+"),
    re.compile(r"/var/folders/[^\s,'\"<>]+"),
]


class StudyAnythingError(RuntimeError):
    """Readable CLI failure."""


def _choices_from_argparse_message(message: str) -> list[str]:
    if "(choose from " not in message:
        return []
    choices_text = message.split("(choose from ", 1)[1].rstrip(")")
    return [item.strip().strip("'\"") for item in choices_text.split(",") if item.strip()]


def format_cli_parse_failure(message: str) -> str:
    missing_option_value = re.search(r"argument (--[A-Za-z0-9_-]+): expected one argument", message)
    if missing_option_value:
        option = missing_option_value.group(1)
        examples = {
            "--session": [
                "Use a real session id after --session.",
                "Example: python3 scripts/study_anything_cli.py teach --session session-123 --layer overview",
                "Find sessions: python3 scripts/study_anything_cli.py sessions",
            ],
            "--session-id": [
                "Use a real session id after --session-id.",
                "Example: python3 scripts/study_anything_cli.py mastery --session-id session-123",
                "Find sessions: python3 scripts/study_anything_cli.py sessions",
            ],
            "--provider-id": [
                "Use a real Agent provider id after --provider-id.",
                "Example: python3 scripts/study_anything_cli.py agent-test --provider-id provider-123",
                "Find providers: python3 scripts/study_anything_cli.py agents",
            ],
            "--api-base": [
                "Use the Study Anything API base URL after --api-base.",
                "Example: python3 scripts/study_anything_cli.py --api-base http://127.0.0.1:8000 health",
                "Start local Skill Mode first if needed: ./scripts/launch_skill_mode.sh",
            ],
            "--text-file": [
                "Use a UTF-8 file path after --text-file, or '-' for stdin.",
                "Example: python3 scripts/study_anything_cli.py start --text-file ./notes/source.txt",
                "Inline text also works: python3 scripts/study_anything_cli.py start --text 'Paste source text here.'",
            ],
            "--endpoint": [
                "Use an HTTP Agent invoke endpoint after --endpoint.",
                "Example: python3 scripts/study_anything_cli.py agent-add-http --endpoint http://127.0.0.1:8787/invoke --set-default",
                "Zero-key gateway: python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
            ],
        }
        lines = [f"Missing value for {option}."]
        lines.extend(examples.get(option, ["Run the same command with --help to see the expected value."]))
        return "\n".join(lines)
    invalid_choice = re.search(r"invalid choice: '([^']+)'", message)
    if invalid_choice:
        command = invalid_choice.group(1)
        choices = _choices_from_argparse_message(message)
        suggestion = difflib.get_close_matches(command, choices, n=1)
        lines = [f"Unknown command: {command}."]
        if suggestion:
            lines.append(
                f"Did you mean: python3 scripts/study_anything_cli.py {suggestion[0]} --help"
            )
        lines.extend(
            [
                "Useful first-run commands:",
                "1. python3 scripts/study_anything_cli.py health",
                "2. python3 scripts/study_anything_cli.py start --text 'Paste source text here.'",
                "3. python3 scripts/study_anything_cli.py agent-add-http --set-default",
            ]
        )
        return "\n".join(lines)
    if "the following arguments are required: command" in message:
        return "\n".join(
            [
                "Missing command.",
                "Useful first-run commands:",
                "1. python3 scripts/study_anything_cli.py health",
                "2. python3 scripts/study_anything_cli.py demo",
                "3. python3 scripts/study_anything_cli.py start --text 'Paste source text here.'",
                "Run python3 scripts/study_anything_cli.py --help for all commands.",
            ]
        )
    if "the following arguments are required:" in message:
        return "\n".join(
            [
                f"Missing required argument: {message}",
                "Run the same command with --help to see the required arguments.",
                "Common examples:",
                "1. python3 scripts/study_anything_cli.py start --text 'Paste source text here.'",
                "2. python3 scripts/study_anything_cli.py answer --session session-123 --text 'My answer.'",
            ]
        )
    if "unrecognized arguments:" in message:
        return "\n".join(
            [
                f"Unrecognized CLI argument: {message}",
                "Run the command with --help and check whether the value should be positional.",
                "For session commands, both SESSION_ID and --session SESSION_ID are supported.",
            ]
        )
    return "\n".join(
        [
            f"CLI arguments could not be parsed: {message}",
            "Run python3 scripts/study_anything_cli.py --help or the subcommand with --help.",
        ]
    )


class StudyAnythingArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise StudyAnythingError(format_cli_parse_failure(message))


def normalise_global_options(argv: Optional[list[str]] = None) -> list[str]:
    """Accept global flags before or after the subcommand.

    argparse only accepts root options before the subcommand. New users often type
    commands as ``study_anything_cli.py mastery SESSION --json``; normalize that
    into the equivalent root-option form before parsing.
    """

    values = list(sys.argv[1:] if argv is None else argv)
    lifted: list[str] = []
    remaining: list[str] = []
    index = 0
    while index < len(values):
        value = values[index]
        if value == "--json":
            lifted.append(value)
            index += 1
            continue
        if value == "--api-base":
            if index + 1 >= len(values) or values[index + 1].startswith("--"):
                raise StudyAnythingError(
                    format_cli_parse_failure("argument --api-base: expected one argument")
                )
            lifted.append(value)
            lifted.append(values[index + 1])
            index += 2
            continue
        if value.startswith("--api-base="):
            lifted.append(value)
            index += 1
            continue
        remaining.append(value)
        index += 1
    return lifted + remaining


def _decode_error_detail(detail: str) -> Dict[str, Any]:
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        return {"raw": detail}
    return payload if isinstance(payload, dict) else {"raw": detail}


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def redact_diagnostic_text(text: str, *, limit: int | None = None) -> str:
    redacted = text
    redacted = re.sub(
        r"https?://[^\s'\"<>]+",
        lambda match: redact_url_for_display(match.group(0)),
        redacted,
    )
    for pattern, replacement in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    for pattern in LOCAL_PATH_PATTERNS:
        redacted = pattern.sub("<local-path>", redacted)
    if limit is None:
        return redacted
    return _response_preview(redacted, limit=limit)


def cli_error_classification(message: str) -> str:
    lowered = message.lower()
    if "block localhost sockets" in lowered or "operation not permitted" in lowered or "permission denied" in lowered:
        return "localhost_socket_blocked"
    if "cannot reach study anything" in lowered or "did not respond before the cli timeout" in lowered:
        return "api_unreachable"
    if "agent endpoint must not contain inline credentials" in lowered:
        return "agent_endpoint_contains_secret"
    if "api base" in lowered and "must not contain inline credentials" in lowered:
        return "api_base_contains_secret"
    if "api base" in lowered and "must not include query parameters" in lowered:
        return "api_base_contains_secret"
    if "cannot read" in lowered or "not utf-8" in lowered:
        return "file_input_error"
    if "api returned http" in lowered:
        if "agent" in lowered or "provider" in lowered:
            return "agent_api_error"
        return "api_error"
    if (
        "unknown command" in lowered
        or "missing command" in lowered
        or "missing required argument" in lowered
        or "unrecognized cli argument" in lowered
        or "missing value for" in lowered
    ):
        return "cli_usage_error"
    return "cli_error"


def cli_error_next_steps(classification: str) -> list[str]:
    common = [
        "python3 scripts/study_anything_cli.py --help",
        "./scripts/run_skill_mode_demo.sh",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run Study Anything from a normal terminal or host environment that permits localhost access.",
            *CONTRACT_ONLY_RECOVERY_STEPS,
            "./scripts/launch_skill_mode.sh",
            "python3 scripts/study_anything_cli.py --api-base http://host:port health",
        ],
        "api_unreachable": [
            "./scripts/launch_skill_mode.sh",
            "python3 scripts/study_anything_cli.py health",
            "python3 scripts/study_anything_cli.py --api-base http://host:port health",
        ],
        "agent_endpoint_contains_secret": [
            "Keep model/API keys inside your own gateway or platform Agent.",
            "python3 scripts/study_anything_cli.py agent-add-http --endpoint http://127.0.0.1:8787/invoke --set-default",
            "python3 scripts/study_anything_cli.py agent-test",
        ],
        "api_base_contains_secret": [
            "Use only the Study Anything server root in --api-base, without credentials or query parameters.",
            "python3 scripts/study_anything_cli.py --api-base http://127.0.0.1:8000 health",
            "./scripts/launch_skill_mode.sh",
        ],
        "file_input_error": [
            "Check that the file exists and is UTF-8.",
            "Use --text-file - to read from stdin, or paste inline text with --text.",
        ],
        "agent_api_error": [
            "python3 scripts/study_anything_cli.py agents",
            "python3 scripts/study_anything_cli.py agent-test",
            "curl http://127.0.0.1:8787/health",
        ],
        "cli_usage_error": [
            "Run the same command with --help.",
            "List sessions with: python3 scripts/study_anything_cli.py sessions",
            "Start fresh with: python3 scripts/study_anything_cli.py start --text 'Paste source text here.'",
        ],
    }
    return matrix.get(classification, []) + common


def cli_error_payload(exc: BaseException) -> dict[str, Any]:
    diagnostic = redact_diagnostic_text(str(exc))
    classification = cli_error_classification(diagnostic)
    return {
        "schema_version": "study-anything-cli-error-v1",
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": cli_error_next_steps(classification),
        "privacy": {
            "local_absolute_paths_included": False,
            "secrets_recorded": False,
        },
    }


def argv_wants_json(argv: list[str]) -> bool:
    return "--json" in argv


def emit_cli_error(exc: BaseException, *, wants_json: bool) -> None:
    if wants_json:
        print(json.dumps(cli_error_payload(exc), ensure_ascii=False, sort_keys=True))
        return
    print(f"study-anything: {exc}", file=sys.stderr)


def _extract_api_error_message(detail: str) -> str:
    payload = _decode_error_detail(detail)
    nested = payload.get("detail")
    if isinstance(nested, str):
        nested_payload = _decode_error_detail(nested)
        return _first_text(
            nested_payload.get("message"),
            nested_payload.get("detail"),
            nested_payload.get("raw"),
            nested,
        )
    if isinstance(nested, list):
        messages: list[str] = []
        for item in nested[:4]:
            if not isinstance(item, dict):
                continue
            location = item.get("loc")
            location_text = ""
            if isinstance(location, list):
                location_text = ".".join(str(part) for part in location)
            message = _first_text(item.get("msg"), item.get("type"))
            if message:
                messages.append(f"{location_text}: {message}" if location_text else message)
        if messages:
            return "; ".join(messages)
    return _first_text(
        payload.get("message"),
        payload.get("detail"),
        payload.get("raw"),
        detail,
    )


def _session_id_from_api_path(path: str) -> str | None:
    parts = [part for part in urlsplit(path).path.split("/") if part]
    for index, part in enumerate(parts):
        if part == "sessions" and index + 1 < len(parts):
            session_id = unquote(parts[index + 1])
            if session_id and not _looks_like_placeholder_id(session_id, {"SESSION_ID"}):
                return session_id
    return None


def _format_api_http_failure(status_code: int, path: str, detail: str) -> str:
    message = _extract_api_error_message(detail)
    lowered = " ".join([path, message, detail]).lower()
    display_message = redact_diagnostic_text(message or detail)
    session_hint = _session_id_from_api_path(path) or "session-123"
    lines = [f"API returned HTTP {status_code} for {path}: {display_message}"]
    if status_code == 404 and "session not found" in lowered:
        lines.extend(
            [
                "The session id was not found in the current local Study Anything store.",
                "Try these checks:",
                "1. List local sessions: python3 scripts/study_anything_cli.py sessions",
                "2. Confirm you are using the same API/data directory that created the session.",
                "3. If you meant to start fresh, run: python3 scripts/study_anything_cli.py start --text 'Paste source text here.'",
            ]
        )
    elif status_code == 404 and ("provider" in lowered or "agent" in lowered):
        lines.extend(
            [
                "The Agent provider id was not found or is disabled.",
                "Try these checks:",
                "1. List providers: python3 scripts/study_anything_cli.py agents",
                "2. Add a local gateway: python3 scripts/study_anything_cli.py agent-add-http --label 'Local gateway' --set-default",
                "3. Test the default provider: python3 scripts/study_anything_cli.py agent-test",
            ]
        )
    elif status_code == 409:
        lines.extend(
            [
                "The request conflicts with the current session or runtime state.",
                "Try these checks:",
                f"1. Inspect the session: python3 scripts/study_anything_cli.py show --session {session_hint}",
                f"2. Check timeline events: python3 scripts/study_anything_cli.py events --session {session_hint}",
                f"3. Resume if the workflow is waiting: python3 scripts/study_anything_cli.py resume --session {session_hint}",
            ]
        )
    elif status_code == 422:
        lines.extend(
            [
                "The API rejected the request shape or an Agent output schema.",
                "Try these checks:",
                "1. Re-run the command with --help and verify required arguments.",
                "2. If this came from an HTTP Agent, run: python3 scripts/study_anything_cli.py agent-test",
                "3. Check docs/agent-contract.md for the required AgentResult fields.",
            ]
        )
    elif status_code == 503 and ("agent" in lowered or "configuration" in lowered or "provider" in lowered):
        lines.extend(
            [
                "Study Anything is running, but the configured Agent is not ready.",
                "Try these checks:",
                "1. List providers: python3 scripts/study_anything_cli.py agents",
                "2. Test the default provider: python3 scripts/study_anything_cli.py agent-test",
                "3. For the local gateway, check: curl http://127.0.0.1:8787/health",
            ]
        )
    else:
        lines.extend(
            [
                "Try these checks:",
                "1. Confirm the API is healthy: python3 scripts/study_anything_cli.py health",
                "2. Re-run the command with --help and verify the arguments.",
                "3. For local setup issues, run: python3 scripts/diagnose_adoption.py",
            ]
        )
    return "\n".join(lines)


def _format_agent_test_failure(status_code: int, detail: str) -> str:
    payload = _decode_error_detail(detail)
    nested = payload.get("detail")
    nested_payload = _decode_error_detail(nested) if isinstance(nested, str) else {}
    diagnostic_code = _first_text(
        payload.get("diagnostic_code"),
        nested_payload.get("diagnostic_code"),
    )
    message = _first_text(
        payload.get("message"),
        nested_payload.get("message"),
        payload.get("detail"),
        payload.get("raw"),
        detail,
    )
    returned_next_steps = payload.get("next_steps")
    if not isinstance(returned_next_steps, list):
        returned_next_steps = nested_payload.get("next_steps")
    safe_returned_next_steps = [
        redact_diagnostic_text(str(step))
        for step in returned_next_steps or []
        if isinstance(step, str) and step.strip()
    ][:6]
    low_level = " ".join([message, diagnostic_code, detail]).lower()
    if status_code in {502, 503} or any(
        marker in low_level
        for marker in (
            "bad gateway",
            "connection refused",
            "configuration_required",
            "upstream_unavailable",
            "upstream llm",
        )
    ):
        display_message = redact_diagnostic_text(message or detail)
        return "\n".join(
            [
                "Agent provider test failed because the user-owned Agent exit is not ready.",
                f"Original response: HTTP {status_code}: {display_message}",
                "Try these checks:",
                "1. curl http://127.0.0.1:8787/health",
                "2. Prove no-socket contracts in this sandbox:",
                *[f"   - {step}" for step in CONTRACT_ONLY_RECOVERY_STEPS],
                "3. Zero-key proof path: python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
                "4. Register that gateway: python3 scripts/study_anything_cli.py agent-add-http --set-default",
                "5. If /health reports upstream configuration is required, set AGENT_LLM_BASE_URL, AGENT_LLM_API_KEY, and AGENT_LLM_MODEL inside the gateway process, then restart it.",
                "6. If WorkBuddy / Kimi Work / Codex is your Agent exit, configure that Agent to call Study Anything directly and re-run agent-add-http with its endpoint.",
                *(
                    ["Agent-provided next steps:"]
                    + [f"- {step}" for step in safe_returned_next_steps]
                    if safe_returned_next_steps
                    else []
                ),
            ]
        )
    return f"API returned {status_code} for /v1/agents/test: {redact_diagnostic_text(detail)}"


def _format_api_unreachable_failure(reason: Any) -> str:
    display_base = redact_url_for_display(api_base())
    reason_text = str(reason).replace(api_base(), display_base)
    if (
        "Operation not permitted" in reason_text
        or "Errno 1" in reason_text
        or "Permission denied" in reason_text
        or "Errno 13" in reason_text
        or "PermissionError" in reason_text
    ):
        return "\n".join(
            [
                f"Cannot reach Study Anything at {display_base}: {reason_text}",
                "This runner appears to block localhost sockets.",
                "Try these checks:",
                "1. Prove no-socket contracts in this sandbox:",
                *[f"   - {step}" for step in CONTRACT_ONLY_RECOVERY_STEPS],
                "2. Run Study Anything from a normal terminal or host environment that permits localhost access.",
                "3. For the shortest full proof, run there: ./scripts/run_skill_mode_demo.sh",
                "4. Or start only the local API there: ./scripts/launch_skill_mode.sh",
                "5. If you use a different API URL, pass --api-base http://host:port before or after the subcommand.",
                "6. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py",
                "7. For Docker/self-host issues, run: ./scripts/doctor.sh",
            ]
        )
    if "timed out" in reason_text.lower() or isinstance(reason, TimeoutError):
        return "\n".join(
            [
                f"Study Anything at {display_base} did not respond before the CLI timeout: {reason_text}",
                "Try these checks:",
                "1. Check API health from another terminal: python3 scripts/study_anything_cli.py health",
                "2. Confirm the API port matches your launcher output, then pass --api-base http://host:port if needed.",
                "3. If the API just started, wait a few seconds and retry.",
                "4. For the shortest full proof, run: ./scripts/run_skill_mode_demo.sh",
                "5. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py",
                "6. For Docker/self-host issues, run: ./scripts/doctor.sh",
            ]
        )
    return "\n".join(
        [
            f"Cannot reach Study Anything at {display_base}: {reason_text}",
            "Try these checks:",
            "1. Run the zero-configuration demo: ./scripts/run_skill_mode_demo.sh",
            "2. Or start the local Skill Mode API: ./scripts/launch_skill_mode.sh",
            "3. Check API health: python3 scripts/study_anything_cli.py health",
            "4. If you use a different API URL, pass --api-base http://host:port before or after the subcommand.",
            "5. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py",
            "6. For Docker/self-host issues, run: ./scripts/doctor.sh",
        ]
    )


def _validate_url_port(parts: Any, *, label: str, example: str) -> None:
    try:
        port = parts.port
    except ValueError as exc:
        raise StudyAnythingError(
            f"{label} has an invalid port. Replace placeholders like host:port with a real port, "
            f"for example {example}."
        ) from exc
    if port == 0:
        raise StudyAnythingError(
            f"{label} port 0 is not usable for first-run CLI calls. Use a reachable port, "
            f"for example {example}."
        )


def _display_env_file_path(env_path: Path) -> str:
    return "<env-file>" if env_path.is_absolute() else str(env_path)


def _redact_env_file_error(text: str, env_path: Path) -> str:
    return text.replace(str(env_path), _display_env_file_path(env_path))


def _parse_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if value.startswith(("'", '"')):
        quote_char = value[0]
        quote_end = value.find(quote_char, 1)
        if quote_end != -1:
            return value[1:quote_end]
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def read_env_file_value(env_path: Path, key: str) -> str | None:
    try:
        content = env_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError as exc:
        raise StudyAnythingError(
            "\n".join(
                [
                    f"Cannot read {_display_env_file_path(env_path)} as UTF-8.",
                    "Try these checks:",
                    "1. Regenerate it: python3 scripts/setup_env.py --force --output .env",
                    "2. Or bypass it for this command: --api-base http://127.0.0.1:8000",
                ]
            )
        ) from exc
    except OSError as exc:
        raise StudyAnythingError(
            "\n".join(
                [
                    f"Cannot read {_display_env_file_path(env_path)}: {_redact_env_file_error(str(exc), env_path)}",
                    "Try these checks:",
                    "1. Run from the repository root or pass --api-base http://host:port.",
                    "2. Recreate local config: python3 scripts/setup_env.py --force --output .env",
                ]
            )
        ) from exc

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        if name.strip() == key:
            return _parse_env_value(raw_value)
    return None


def api_base_from_env_file(env_path: Path) -> str | None:
    api_port = read_env_file_value(env_path, "API_PORT")
    if api_port is None:
        return None
    if not api_port.isdigit():
        raise StudyAnythingError(
            "\n".join(
                [
                    f"Invalid API_PORT in {_display_env_file_path(env_path)}: {api_port!r}.",
                    "API_PORT must be a number from 1 to 65535.",
                    "Try these checks:",
                    "1. Edit .env and set API_PORT=8000, or another free port.",
                    "2. Recheck config: python3 scripts/check_env.py --env .env",
                    "3. Or bypass it for this command: --api-base http://127.0.0.1:8000",
                ]
            )
        )
    port = int(api_port)
    if not 1 <= port <= 65535:
        raise StudyAnythingError(
            "\n".join(
                [
                    f"Invalid API_PORT in {_display_env_file_path(env_path)}: {api_port!r}.",
                    "API_PORT must be between 1 and 65535.",
                    "Try these checks:",
                    "1. Edit .env and set API_PORT=8000, or another free port.",
                    "2. Recheck config: python3 scripts/check_env.py --env .env",
                    "3. Or bypass it for this command: --api-base http://127.0.0.1:8000",
                ]
            )
        )
    return f"http://127.0.0.1:{port}"


def normalise_api_base(value: str) -> str:
    base = value.strip()
    if not base:
        raise StudyAnythingError(
            "API base is empty. Use http://127.0.0.1:8000 or run ./scripts/launch_skill_mode.sh."
        )
    if "://" not in base:
        if base.startswith(("127.", "localhost", "[::1]", "0.0.0.0")):
            base = f"http://{base}"
        else:
            raise StudyAnythingError(
                "API base must include http:// or https:// unless it is a localhost address. "
                "For Skill Mode, use http://127.0.0.1:8000 or pass --api-base 127.0.0.1:8000."
            )
    parts = urlsplit(base)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise StudyAnythingError(
            "API base must be an HTTP URL, for example http://127.0.0.1:8000. "
            "If you pasted a health URL, use the server root instead."
        )
    _validate_url_port(
        parts,
        label="API base",
        example="http://127.0.0.1:8000",
    )
    if parts.username or parts.password:
        raise StudyAnythingError(
            "API base must not contain inline credentials. "
            "Study Anything local API auth, if enabled later, should be configured separately."
        )
    if parts.query or parts.fragment:
        raise StudyAnythingError(
            "API base must not include query parameters or fragments. "
            "Use the server root, for example http://127.0.0.1:8000."
        )
    path = parts.path.rstrip("/")
    if path in {"/health", "/v1/health"}:
        path = ""
    return urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")


def api_base() -> str:
    explicit_base = os.getenv("STUDY_ANYTHING_API_BASE") or os.getenv("API_BASE")
    if explicit_base:
        return normalise_api_base(explicit_base)
    env_path = Path(os.getenv("STUDY_ANYTHING_ENV_FILE") or DEFAULT_ENV_FILE)
    env_base = api_base_from_env_file(env_path)
    return normalise_api_base(env_base or DEFAULT_API_BASE)



def _response_preview(text: str, *, limit: int = 160) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _format_api_decode_failure(path: str, problem: str, detail: str = "") -> str:
    lines = [
        f"API response for {path} could not be decoded: {problem}",
        "This usually means --api-base points to the wrong service, a proxy returned an HTML/error page, or the API crashed before returning JSON.",
    ]
    if detail:
        lines.append(f"response preview: {redact_diagnostic_text(detail)}")
    lines.extend(
        [
            "Try these checks:",
            "1. Confirm the API base URL: python3 scripts/study_anything_cli.py health",
            "2. If your API uses a different port, pass --api-base http://host:port before or after the subcommand.",
            "3. For local setup issues, run: python3 scripts/diagnose_adoption.py",
        ]
    )
    return "\n".join(lines)


def decode_api_json_response(path: str, body: bytes) -> Any:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StudyAnythingError(
            _format_api_decode_failure(path, f"response was not UTF-8 text ({exc})")
        ) from exc
    if not text.strip():
        raise StudyAnythingError(_format_api_decode_failure(path, "response was empty"))
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise StudyAnythingError(
            _format_api_decode_failure(
                path,
                f"response was not valid JSON ({exc})",
                _response_preview(text),
            )
        ) from exc


def _api_shape_help(path: str, purpose: str) -> str:
    return "\n".join(
        [
            f"{purpose} from {path} did not match the expected API shape.",
            "This usually means --api-base points to another service, the API and CLI versions are mismatched, or the API returned a partial error payload.",
            "Try these checks:",
            "1. Check API health: python3 scripts/study_anything_cli.py health",
            "2. Confirm the CLI and API came from the same checkout or release bundle.",
            "3. For local setup issues, run: python3 scripts/diagnose_adoption.py",
        ]
    )


def require_json_object(value: Any, path: str, *, purpose: str = "API response") -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise StudyAnythingError(
        "\n".join(
            [
                _api_shape_help(path, purpose),
                f"expected: JSON object",
                f"actual: {type(value).__name__}",
            ]
        )
    )


def require_json_list(value: Any, path: str, *, purpose: str = "API response") -> list[Any]:
    if isinstance(value, list):
        return value
    raise StudyAnythingError(
        "\n".join(
            [
                _api_shape_help(path, purpose),
                f"expected: JSON array",
                f"actual: {type(value).__name__}",
            ]
        )
    )


def require_string_field(
    payload: Dict[str, Any],
    field: str,
    path: str,
    *,
    purpose: str = "API response",
) -> str:
    value = payload.get(field)
    if isinstance(value, str) and value.strip():
        return value
    raise StudyAnythingError(
        "\n".join(
            [
                _api_shape_help(path, purpose),
                f"missing required field: {field}",
            ]
        )
    )


def require_object_field(
    payload: Dict[str, Any],
    field: str,
    path: str,
    *,
    purpose: str = "API response",
) -> Dict[str, Any]:
    value = payload.get(field)
    if isinstance(value, dict):
        return value
    raise StudyAnythingError(
        "\n".join(
            [
                _api_shape_help(path, purpose),
                f"missing object field: {field}",
            ]
        )
    )


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{api_base()}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=15) as response:
            return decode_api_json_response(path, response.read())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if path == "/v1/agents/test":
            raise StudyAnythingError(_format_agent_test_failure(exc.code, detail)) from exc
        raise StudyAnythingError(_format_api_http_failure(exc.code, path, detail)) from exc
    except URLError as exc:
        raise StudyAnythingError(_format_api_unreachable_failure(exc.reason)) from exc
    except (TimeoutError, OSError) as exc:
        raise StudyAnythingError(_format_api_unreachable_failure(exc)) from exc


def post(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    return request(path, payload or {})


def display_path_for_error(path: str | Path, placeholder: str) -> str:
    value = Path(path)
    return f"<{placeholder}>" if value.is_absolute() else str(path)


def redact_path_in_text(text: str, path: str | Path, placeholder: str) -> str:
    value = Path(path)
    if not value.is_absolute():
        return text
    redacted = display_path_for_error(value, placeholder)
    return text.replace(str(value), redacted)


def load_json_file(path: str) -> Dict[str, Any]:
    display_path = display_path_for_error(path, "json-file")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            values = json.load(handle)
    except OSError as exc:
        raise StudyAnythingError(
            "\n".join(
                [
                    f"Cannot read JSON file {display_path}: {redact_path_in_text(str(exc), path, 'json-file')}",
                    "Check that the path exists, quote paths with spaces, and confirm you have read permission.",
                ]
            )
        ) from exc
    except UnicodeDecodeError as exc:
        raise StudyAnythingError(
            f"JSON file {display_path} is not UTF-8 text. Save it as UTF-8 and retry: {redact_path_in_text(str(exc), path, 'json-file')}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise StudyAnythingError(f"{display_path} is not valid JSON: {exc}") from exc
    if not isinstance(values, dict):
        raise StudyAnythingError(f"{display_path} must contain a JSON object.")
    return values


def parse_json_object_option(
    value: str,
    option: str,
    *,
    file_option: str | None = None,
    example: str = '{"key":"value"}',
) -> Dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        lines = [
            f"Cannot parse {option} as a JSON object: {exc}",
            "Wrap inline JSON in single quotes so your shell does not strip quotes.",
            f"Example: {option} '{example}'",
        ]
        if file_option:
            lines.append(f"For larger payloads, use {file_option} path/to/input.json.")
        raise StudyAnythingError("\n".join(lines)) from exc
    if not isinstance(parsed, dict):
        lines = [
            f"{option} must decode to a JSON object, got {type(parsed).__name__}.",
            f"Example: {option} '{example}'",
        ]
        if file_option:
            lines.append(f"For larger payloads, use {file_option} path/to/input.json.")
        raise StudyAnythingError("\n".join(lines))
    return parsed


def _looks_like_placeholder_id(value: Any, placeholders: set[str]) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().strip("<>").strip("{}").strip().upper().replace("-", "_")
    return normalized in placeholders


def _raise_text_file_placeholder_error(path: str, *, option: str, inline_option: str) -> None:
    raise StudyAnythingError(
        "\n".join(
            [
                f"{option} is still a placeholder: {path}.",
                "Use a real UTF-8 text file path, paste inline text, or read from stdin.",
                "Try one of these forms:",
                f"1. {option} ./notes/source.txt",
                f"2. {inline_option} 'Paste the source text here.'",
                f"3. {option} -",
            ]
        )
    )


def read_text_input_file(path: str, *, option: str, inline_option: str = "--text") -> str:
    if path == "-":
        return sys.stdin.read()
    if _looks_like_placeholder_id(path, {"PATH", "FILE", "TEXT_FILE", "TEXT_FILE_PATH"}):
        _raise_text_file_placeholder_error(path, option=option, inline_option=inline_option)
    display_path = display_path_for_error(path, "text-file")
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise StudyAnythingError(
            "\n".join(
                [
                    f"Cannot read {option} {display_path}: {redact_path_in_text(str(exc), path, 'text-file')}",
                    "Check that the path exists, quote paths with spaces, or use "
                    f"{option} - to paste from stdin.",
                ]
            )
        ) from exc
    except UnicodeDecodeError as exc:
        raise StudyAnythingError(
            f"{option} {display_path} is not UTF-8 text. "
            f"Save it as UTF-8 or paste with {inline_option}: {redact_path_in_text(str(exc), path, 'text-file')}"
        ) from exc


def write_output_file(path: str | Path, content: str, *, description: str = "output file") -> None:
    target = Path(path)
    display_path = display_path_for_error(target, "output-file")
    try:
        if target.parent != Path("."):
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        error_text = redact_path_in_text(str(exc), target, "output-file")
        error_text = redact_path_in_text(error_text, target.parent, "output-dir")
        raise StudyAnythingError(
            "\n".join(
                [
                    f"Cannot write {description} {display_path}: {error_text}",
                    "Choose a writable path, avoid using a file as a parent directory, or omit --output to print to stdout.",
                ]
            )
        ) from exc


def write_json_output_file(
    path: str | Path,
    payload: Any,
    *,
    description: str = "JSON output file",
) -> None:
    write_output_file(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        description=description,
    )


def print_wrote_path(path: str | Path, placeholder: str = "output-file") -> None:
    print(f"wrote: {display_path_for_error(path, placeholder)}")


def resolve_text_input(
    args: argparse.Namespace,
    *,
    text_attr: str = "text",
    file_attr: str = "text_file",
    text_option: str = "--text",
    file_option: str = "--text-file",
) -> str:
    text = getattr(args, text_attr, None)
    file_path = getattr(args, file_attr, None)
    if text and file_path:
        raise StudyAnythingError(f"Use either {text_option} or {file_option}, not both.")
    text = _positional_text(text)
    if file_path:
        text = read_text_input_file(file_path, option=file_option, inline_option=text_option)
    if not isinstance(text, str) or not text.strip():
        raise StudyAnythingError(
            f"Missing text. Pass {text_option} '...' or {file_option} ./notes/source.txt. "
            f"Use {file_option} - to read from stdin."
        )
    return text


def _positional_text(value: Any) -> str | None:
    if isinstance(value, list):
        return " ".join(str(part) for part in value if str(part).strip()).strip() or None
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _option_text(value: Any, *, default: str | None = None) -> str:
    text = _positional_text(value)
    if text is None:
        return "" if default is None else default
    return text


def resolve_answer_text_input(args: argparse.Namespace) -> str:
    positional = _positional_text(getattr(args, "answer_text", None))
    inline_text = _positional_text(getattr(args, "text", None))
    file_path = getattr(args, "text_file", None)
    if positional is not None and (inline_text is not None or file_path):
        raise StudyAnythingError(
            "Use positional ANSWER_TEXT, --text, or --text-file; choose only one answer input."
        )
    if positional is not None:
        return resolve_text_input(
            argparse.Namespace(text=positional, text_file=None),
            text_option="ANSWER_TEXT",
        )
    return resolve_text_input(args)


def resolve_source_text_input(args: argparse.Namespace) -> str:
    positional = _positional_text(getattr(args, "source_text", None))
    inline_text = _positional_text(getattr(args, "text", None))
    file_path = getattr(args, "text_file", None)
    title_parts = getattr(args, "title", None)
    if (
        positional is None
        and inline_text is None
        and not file_path
        and isinstance(title_parts, list)
        and len(title_parts) > 1
    ):
        args.title = title_parts[0]
        return _positional_text(title_parts[1:]) or ""
    if positional is not None and (inline_text is not None or file_path):
        raise StudyAnythingError(
            "Use positional SOURCE_TEXT, --text, or --text-file; choose only one source input."
        )
    if positional is not None:
        return resolve_text_input(
            argparse.Namespace(text=positional, text_file=None),
            text_option="SOURCE_TEXT",
        )
    return resolve_text_input(args)


def resolve_enrichment_text_input(args: argparse.Namespace) -> str:
    positional = _positional_text(getattr(args, "enrichment_text", None))
    inline_text = _positional_text(getattr(args, "text", None))
    file_path = getattr(args, "text_file", None)
    if positional is not None and (inline_text is not None or file_path):
        raise StudyAnythingError(
            "Use positional ENRICHMENT_TEXT, --text, or --text-file; choose only one enrichment input."
        )
    if positional is not None:
        return resolve_text_input(
            argparse.Namespace(text=positional, text_file=None),
            text_option="ENRICHMENT_TEXT",
        )
    return resolve_text_input(args)


def resolve_query_input(args: argparse.Namespace) -> str:
    positional = _positional_text(getattr(args, "query_terms", None))
    query = _positional_text(getattr(args, "query", None))
    if positional is not None and query:
        raise StudyAnythingError("Use positional QUERY or --query; choose only one query input.")
    resolved = positional if positional is not None else query
    if not isinstance(resolved, str) or not resolved.strip():
        raise StudyAnythingError("Missing query. Pass QUERY after the session id or use --query '...'.")
    return resolved


def _normalise_title_candidate(value: Any) -> str:
    text = _positional_text(value)
    if not isinstance(text, str):
        return ""
    title = " ".join(text.strip().split())
    if not title:
        return ""
    return redact_diagnostic_text(title, limit=MAX_DERIVED_TITLE_CHARS).strip()


def _title_from_reference(reference: Any) -> str:
    reference_text = _normalise_title_candidate(reference)
    if not reference_text:
        return ""
    try:
        parts = urlsplit(reference_text)
    except ValueError:
        parts = None
    if parts and parts.scheme:
        path_name = Path(parts.path).name if parts.path else ""
        candidate = _normalise_title_candidate(path_name or parts.netloc or reference_text)
        return candidate
    path_name = Path(reference_text).name if "/" in reference_text else reference_text
    return _normalise_title_candidate(path_name)


def resolve_title_input(
    args: argparse.Namespace,
    source_text: str,
    *,
    default_title: str = DEFAULT_DERIVED_SESSION_TITLE,
) -> str:
    explicit_title = _normalise_title_candidate(getattr(args, "title", None))
    if explicit_title:
        return explicit_title
    for line in source_text.splitlines():
        derived = _normalise_title_candidate(line)
        if derived:
            return derived
    reference_title = _title_from_reference(getattr(args, "reference", None))
    if reference_title:
        return reference_title
    return default_title


def resolve_optional_text_option(value: Any, *, default: str) -> str:
    text = _positional_text(value)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return default


def _query_has_secret_key(query: str) -> bool:
    for key, _value in parse_qsl(query, keep_blank_values=True):
        lowered = key.lower().replace("-", "_")
        if any(marker in lowered for marker in SECRET_QUERY_KEYS):
            return True
    return False


def redact_url_for_display(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return "<url>"
    if not parts.scheme or not parts.netloc:
        return value
    netloc = parts.netloc
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[1]
    query_pairs = []
    for key, raw_value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower().replace("-", "_")
        if any(marker in lowered for marker in SECRET_QUERY_KEYS):
            query_pairs.append((key, "<redacted>"))
        else:
            query_pairs.append((key, raw_value))
    query = urlencode(query_pairs)
    fragment = parts.fragment
    if fragment and any(marker in fragment.lower() for marker in SECRET_QUERY_KEYS):
        fragment = "<redacted>"
    return urlunsplit((parts.scheme, netloc, parts.path, query, fragment))


def normalise_http_agent_endpoint(value: str) -> str:
    endpoint = value.strip()
    if not endpoint:
        raise StudyAnythingError(
            "Agent endpoint is empty.\n"
            "Use a user-owned Agent endpoint such as http://127.0.0.1:8787/invoke.\n"
            "Zero-key local proof path:\n"
            "1. python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787\n"
            "2. python3 scripts/study_anything_cli.py agent-add-http --set-default"
        )
    if "://" not in endpoint:
        if endpoint.startswith(("127.", "localhost", "[::1]", "0.0.0.0")):
            endpoint = f"http://{endpoint}"
        else:
            raise StudyAnythingError(
                "Agent endpoint must include http:// or https://. "
                "For the local gateway, use http://127.0.0.1:8787/invoke. "
                "If this is a platform Agent, paste the HTTP endpoint it exposes to Study Anything."
            )
    parts = urlsplit(endpoint)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise StudyAnythingError(
            "Agent endpoint must be an HTTP URL, for example http://127.0.0.1:8787/invoke. "
            "Study Anything stores only the endpoint and capabilities; model credentials stay inside your Agent."
        )
    _validate_url_port(
        parts,
        label="Agent endpoint",
        example="http://127.0.0.1:8787/invoke",
    )
    if parts.username or parts.password:
        raise StudyAnythingError(
            "Agent endpoint must not contain inline credentials. "
            "Keep model/API secrets inside your own gateway or platform Agent.\n"
            "Use an endpoint without credentials, for example: http://127.0.0.1:8787/invoke\n"
            "Then test the default provider with: python3 scripts/study_anything_cli.py agent-test"
        )
    if _query_has_secret_key(parts.query):
        raise StudyAnythingError(
            "Agent endpoint must not contain secret-like query parameters. "
            "Keep model/API secrets inside your own gateway or platform Agent.\n"
            "Use an endpoint without API keys, for example: http://127.0.0.1:8787/invoke\n"
            "For zero-key validation, start: python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787"
        )
    if parts.query:
        raise StudyAnythingError(
            "Agent endpoint must not include query parameters. "
            "Copy the invoke URL without browser/debug parameters, for example: http://127.0.0.1:8787/invoke\n"
            "If your Agent needs credentials, keep them inside your gateway or platform Agent, not in the Study Anything endpoint.\n"
            "Then register it again: python3 scripts/study_anything_cli.py agent-add-http --endpoint http://127.0.0.1:8787/invoke --set-default"
        )
    if parts.fragment:
        raise StudyAnythingError(
            "Agent endpoint must not include URL fragments. "
            "HTTP clients do not send #... fragments to the gateway, so they cannot configure the Agent.\n"
            "Use the server endpoint without fragments, for example: http://127.0.0.1:8787/invoke\n"
            "Keep model/API secrets inside your own gateway or platform Agent."
        )
    path = parts.path
    if path in {"", "/"} or path.rstrip("/") == "/health":
        path = "/invoke"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def normalise_agent_capabilities(
    values: list[Any] | None,
    *,
    default: list[str] | None = None,
) -> list[str]:
    raw_values: list[Any] = []
    for value in values or []:
        if isinstance(value, list):
            raw_values.extend(value)
        else:
            raw_values.append(value)
    raw_text = " ".join(str(value).strip() for value in raw_values if str(value).strip())
    if not raw_text:
        return list(default or [])
    if re.search(r"(^|,)\s*(,|$)", raw_text):
        raise StudyAnythingError(
            "Agent capability is empty. Use values like quiz.generate, "
            "answer.grade, or omit --capability to use common learning capabilities."
        )
    capabilities: list[str] = []
    for capability in re.split(r"[\s,]+", raw_text):
        if not capability:
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]*", capability):
            raise StudyAnythingError(
                f"Agent capability {capability!r} is invalid. "
                "Use letters, numbers, dots, underscores, colons, or hyphens, "
                "for example quiz.generate."
            )
        if capability not in capabilities:
            capabilities.append(capability)
    if capabilities:
        return capabilities
    return list(default or [])


def normalise_agent_timeout(value: int) -> int:
    if value <= 0:
        raise StudyAnythingError(
            "Agent timeout must be a positive number of seconds. "
            "Use --timeout 15 for the local gateway."
        )
    if value > 300:
        raise StudyAnythingError(
            "Agent timeout is too large for first-run CLI checks. "
            "Use 300 seconds or less, then move long-running work into your own Agent."
        )
    return value


def default_http_agent_label(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    host = parts.hostname or parts.netloc or "HTTP Agent"
    netloc = parts.netloc or host
    if host in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}:
        return f"Local gateway ({netloc})"
    return f"HTTP Agent ({netloc})"


def is_default_local_agent_endpoint(endpoint: Any) -> bool:
    if not isinstance(endpoint, str) or not endpoint.strip():
        return False
    try:
        parts = urlsplit(endpoint.strip())
    except ValueError:
        return False
    host = parts.hostname or ""
    path = parts.path.rstrip("/") or "/invoke"
    return host in {"127.0.0.1", "localhost", "::1"} and parts.port == 8787 and path == "/invoke"


def first_unanswered_quiz(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    answers = session.get("answers") if isinstance(session.get("answers"), list) else []
    answered = {
        answer.get("item_id")
        for answer in answers
        if isinstance(answer, dict) and isinstance(answer.get("item_id"), str)
    }
    quiz_items = session.get("quiz_items") if isinstance(session.get("quiz_items"), list) else []
    for item in quiz_items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("item_id")
        if isinstance(item_id, str) and item_id.strip() and item_id not in answered:
            return item
    return None


def require_unanswered_quiz(session: Dict[str, Any], path: str, *, purpose: str) -> Dict[str, Any]:
    quiz = first_unanswered_quiz(session)
    if quiz:
        require_string_field(quiz, "item_id", path, purpose=purpose)
        return quiz
    session_hint = str(session.get("session_id") or _session_id_from_api_path(path) or "session-123")
    raise StudyAnythingError(
        "\n".join(
            [
                _api_shape_help(path, purpose),
                "missing required unanswered quiz item with item_id.",
                "Try these checks:",
                f"1. Inspect the session: python3 scripts/study_anything_cli.py show --session {session_hint}",
                f"2. Resume the workflow: python3 scripts/study_anything_cli.py resume --session {session_hint}",
                f"3. If the session is complete, run: python3 scripts/study_anything_cli.py mastery --session {session_hint}",
            ]
        )
    )


def session_summary(session: Dict[str, Any]) -> Dict[str, Any]:
    active_quiz = first_unanswered_quiz(session)
    source = session.get("source") or {}
    mastery = session.get("mastery") or {}
    open_hitl = [
        item for item in session.get("hitl_interrupts", []) if item.get("status") == "open"
    ]
    return {
        "session_id": session.get("session_id"),
        "stage": session.get("stage"),
        "source_title": source.get("title"),
        "mastery": {
            "level": mastery.get("level", 0.0),
            "bloom": mastery.get("bloom", "remember"),
        },
        "question": active_quiz,
        "grading_results": session.get("grading_results", []),
        "insights": session.get("insights", []),
        "open_hitl": open_hitl,
        "discarded": session.get("discarded", False),
    }


def is_agent_configuration_hitl(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    kind = str(item.get("kind") or "").lower()
    message = str(item.get("message") or "").lower()
    return kind.startswith("agent.") or "default agent" in message or "agent provider" in message


def session_next_steps(summary: Dict[str, Any]) -> list[str]:
    session_id = summary.get("session_id")
    if not session_id:
        return []
    if summary.get("discarded"):
        return [
            "Start a fresh session: python3 scripts/study_anything_cli.py start --text 'Paste source text here.'"
        ]
    open_hitl = summary.get("open_hitl") or []
    if open_hitl:
        current_hitl = open_hitl[0]
        task_id = current_hitl.get("task_id") if isinstance(current_hitl, dict) else "TASK_ID"
        if is_agent_configuration_hitl(current_hitl):
            return [
                "Inspect Agent setup: python3 scripts/study_anything_cli.py agents",
                "Register a local dry-run Agent if needed: python3 scripts/study_anything_cli.py agent-add-http --set-default",
                "Test the default Agent: python3 scripts/study_anything_cli.py agent-test",
                f"Resume after fixing Agent setup: python3 scripts/study_anything_cli.py resume --session {session_id}",
            ]
        return [
            "Inspect HITL tasks: python3 scripts/study_anything_cli.py hitl",
            f"Resolve the current task: python3 scripts/study_anything_cli.py resolve --session {session_id} --decision approve",
        ]
    question = summary.get("question")
    if isinstance(question, dict) and question.get("item_id"):
        return [
            f"Answer the quiz: python3 scripts/study_anything_cli.py answer {session_id} 'your answer'",
            f"Ask for a teaching layer: python3 scripts/study_anything_cli.py teach --session {session_id} --layer overview",
        ]
    stage = str(summary.get("stage") or "")
    if stage == "completed":
        return [
            f"Check mastery: python3 scripts/study_anything_cli.py mastery --session {session_id}",
            f"Review Agent evidence: python3 scripts/study_anything_cli.py agent-eval-report --session {session_id}",
            f"Export Obsidian notes: python3 scripts/study_anything_cli.py obsidian-export --session {session_id}",
        ]
    return [
        f"Resume workflow: python3 scripts/study_anything_cli.py resume --session {session_id}",
        f"Show events: python3 scripts/study_anything_cli.py events --session {session_id}",
    ]


def print_session(session: Dict[str, Any]) -> None:
    summary = session_summary(session)
    mastery = summary["mastery"]
    print(f"session: {summary['session_id']}")
    print(f"stage: {summary['stage']}")
    if summary["source_title"]:
        print(f"source: {summary['source_title']}")
    print(f"mastery: {mastery['level']} ({mastery['bloom']})")
    question = summary["question"]
    if question:
        print(f"question_id: {question.get('item_id', '-')}")
        print(f"question: {question.get('prompt', '-')}")
    for result in summary["grading_results"]:
        print(f"feedback: {result.get('feedback', '')} score={result.get('score', '')}")
    for insight in summary["insights"]:
        print(f"insight: {insight}")
    for item in summary["open_hitl"]:
        print(f"hitl: {item.get('task_id')} {item.get('kind')}: {item.get('message')}")
    if summary["discarded"]:
        print("discarded: yes")
    next_steps = session_next_steps(summary)
    if next_steps:
        print("next:")
        for step in next_steps:
            print(f"- {step}")


def print_rows(rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        print("none")
        return
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))


def agent_status_next_steps(status: Dict[str, Any]) -> list[str]:
    providers = [
        provider
        for provider in status.get("providers", [])
        if isinstance(provider, dict) and provider.get("enabled", True)
    ]
    defaults = status.get("defaults") if isinstance(status.get("defaults"), dict) else {}
    missing_defaults = [capability for capability, provider_id in defaults.items() if not provider_id]
    if not providers:
        return [
            "Run a zero-key demo: python3 scripts/study_anything_cli.py demo",
            "Start a local dry-run gateway: python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
            "Register it: python3 scripts/study_anything_cli.py agent-add-http --set-default",
        ]
    provider_id = str(providers[0].get("provider_id") or "PROVIDER_ID")
    if missing_defaults:
        return [
            f"Set this provider as default: python3 scripts/study_anything_cli.py agent-set-default {provider_id}",
            f"Test it: python3 scripts/study_anything_cli.py agent-test --provider-id {provider_id}",
        ]
    default_provider = next((value for value in defaults.values() if value), provider_id)
    return [
        f"Test the configured provider: python3 scripts/study_anything_cli.py agent-test --provider-id {default_provider}",
        "Start a lesson: python3 scripts/study_anything_cli.py start --text 'Paste source text here.'",
        "Force configured mode if you are debugging routing: python3 scripts/study_anything_cli.py start --text 'Paste source text here.' --agent-mode configured",
    ]


def select_agent_provider_for_test(status: Dict[str, Any]) -> str:
    providers = [
        provider
        for provider in status.get("providers", [])
        if isinstance(provider, dict) and provider.get("enabled", True)
    ]
    provider_ids = [str(provider.get("provider_id")) for provider in providers if provider.get("provider_id")]
    defaults = status.get("defaults") if isinstance(status.get("defaults"), dict) else {}
    default_ids = [str(provider_id) for provider_id in defaults.values() if provider_id]
    for provider_id in default_ids:
        if not provider_ids or provider_id in provider_ids:
            return provider_id
    if len(provider_ids) == 1:
        return provider_ids[0]
    if not provider_ids:
        raise StudyAnythingError(
            "\n".join(
                [
                    "No Agent provider is configured yet.",
                    "Try these checks:",
                    "1. Start a dry-run gateway: python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
                    "2. Register it: python3 scripts/study_anything_cli.py agent-add-http --set-default",
                    "3. Or run the zero-key demo path: python3 scripts/study_anything_cli.py demo",
                ]
            )
        )
    raise StudyAnythingError(
        "\n".join(
            [
                "Multiple Agent providers exist and no default provider is configured.",
                f"Choose one explicitly: python3 scripts/study_anything_cli.py agent-test --provider-id {provider_ids[0]}",
                f"Or set a default: python3 scripts/study_anything_cli.py agent-set-default {provider_ids[0]}",
                "List providers: python3 scripts/study_anything_cli.py agents",
            ]
        )
    )


def print_agent_status(status: Dict[str, Any], *, user_id: str = "local-user") -> None:
    providers = [
        provider for provider in status.get("providers", []) if isinstance(provider, dict)
    ]
    defaults = status.get("defaults") if isinstance(status.get("defaults"), dict) else {}
    print(f"schema: {status.get('schema_version', 'agent-v1')}")
    print(f"user: {user_id}")
    if providers:
        print("providers:")
        for provider in providers:
            capabilities = provider.get("capabilities") or []
            print(
                "- {provider_id} kind={kind} label={label} enabled={enabled} capabilities={count}".format(
                    provider_id=provider.get("provider_id", "-"),
                    kind=provider.get("kind", "-"),
                    label=redact_diagnostic_text(str(provider.get("label", "-"))),
                    enabled=provider.get("enabled", True),
                    count=len(capabilities) if isinstance(capabilities, list) else 0,
                )
            )
    else:
        print("providers: none")
    if defaults:
        configured = sum(1 for provider_id in defaults.values() if provider_id)
        print(f"defaults: {configured}/{len(defaults)} configured")
        missing = [capability for capability, provider_id in defaults.items() if not provider_id]
        if missing:
            print(f"missing_defaults: {', '.join(missing[:8])}")
    else:
        print("defaults: none")
    next_steps = agent_status_next_steps(status)
    if next_steps:
        print("next:")
        for step in next_steps:
            print(f"- {step}")


def print_agent_provider_created(
    provider: Dict[str, Any],
    *,
    defaults_configured: bool,
    capabilities: list[str],
) -> None:
    provider_id = str(provider.get("provider_id") or "PROVIDER_ID")
    print(f"provider: {provider_id}")
    print(f"kind: {provider.get('kind', '-')}")
    print(f"label: {redact_diagnostic_text(str(provider.get('label', '-')))}")
    if provider.get("endpoint"):
        print(f"endpoint: {redact_diagnostic_text(str(provider.get('endpoint')))}")
    print(f"capabilities: {len(capabilities)}")
    print(f"defaults_configured: {'yes' if defaults_configured else 'no'}")
    print("next:")
    if is_default_local_agent_endpoint(provider.get("endpoint")):
        print(
            "- Start the local dry-run gateway if it is not already running: "
            "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787"
        )
    if defaults_configured:
        print("- Test it: python3 scripts/study_anything_cli.py agent-test")
        print(
            "- Start a lesson: python3 scripts/study_anything_cli.py start --text 'Paste source text here.'"
        )
        print(
            "- Force configured mode if you are debugging routing: python3 scripts/study_anything_cli.py start --text 'Paste source text here.' --agent-mode configured"
        )
    else:
        print(f"- Test it: python3 scripts/study_anything_cli.py agent-test --provider-id {provider_id}")
        print(
            f"- Set it as default: python3 scripts/study_anything_cli.py agent-set-default {provider_id}"
        )


def print_agent_test_result(result: Dict[str, Any]) -> None:
    provider_id = str(result.get("provider_id") or "PROVIDER_ID")
    status = str(result.get("status") or "unknown")
    diagnostic_code = str(result.get("diagnostic_code") or "-")
    capabilities = result.get("capabilities")
    capability_count = len(capabilities) if isinstance(capabilities, list) else 0
    print(f"provider: {provider_id}")
    print(f"status: {status}")
    print(f"diagnostic_code: {diagnostic_code}")
    if result.get("latency_ms") is not None:
        print(f"latency_ms: {result.get('latency_ms')}")
    if result.get("message"):
        print(f"message: {redact_diagnostic_text(str(result.get('message')))}")
    print(f"capabilities: {capability_count}")
    privacy = result.get("privacy") if isinstance(result.get("privacy"), dict) else {}
    if privacy:
        print(
            "privacy: secrets_returned={secrets} endpoint_secrets_returned={endpoint} raw_task_payload_returned={raw}".format(
                secrets="yes" if privacy.get("secrets_returned") else "no",
                endpoint="yes" if privacy.get("endpoint_secrets_returned") else "no",
                raw="yes" if privacy.get("raw_task_payload_returned") else "no",
            )
        )
    print("next:")
    if status == "healthy":
        print(
            "- Start a lesson: python3 scripts/study_anything_cli.py start --text 'Paste source text here.'"
        )
        print(
            f"- Route all common learning capabilities here: python3 scripts/study_anything_cli.py agent-set-default {provider_id}"
        )
        print(
            "- Inspect providers: python3 scripts/study_anything_cli.py agents"
        )
        return
    if status in {"configuration_required", "unhealthy"}:
        print("- Check a local gateway: curl http://127.0.0.1:8787/health")
        print(
            "- Zero-key fallback: python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787"
        )
        print(
            "- Re-register the endpoint: python3 scripts/study_anything_cli.py agent-add-http --set-default"
        )
        print("- For a redacted diagnosis: python3 scripts/diagnose_adoption.py")
        return
    print("- List providers: python3 scripts/study_anything_cli.py agents")
    print(
        "- If you need a local demo Agent: python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787"
    )


def emit(args: argparse.Namespace, data: Any, *, session: bool = False) -> None:
    if session:
        data = require_json_object(data, "session command", purpose="Session response")
    if args.json:
        payload = session_summary(data) if session else data
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    elif session:
        print_session(data)
    elif isinstance(data, list):
        print_rows(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def create_session(args: argparse.Namespace) -> Dict[str, Any]:
    source_text = resolve_source_text_input(args)
    title = resolve_title_input(args, source_text)
    agent_mode = resolve_start_agent_mode(args)
    warn_auto_agent_fallback(args, agent_mode)
    session = require_json_object(
        post(
            "/v1/sessions",
            {
                "user_id": args.user_id,
                "track": args.track,
                "use_demo_agent": agent_mode == "demo",
            },
        ),
        "/v1/sessions",
        purpose="Session creation response",
    )
    session_id = require_string_field(
        session,
        "session_id",
        "/v1/sessions",
        purpose="Session creation response",
    )
    post(
        f"/v1/sessions/{quote(session_id)}/reading",
        {
            "source_type": args.source_type,
            "reference": _option_text(args.reference),
            "title": title,
            "text": source_text,
        },
    )
    return require_json_object(
        post(f"/v1/sessions/{quote(session_id)}/run"),
        f"/v1/sessions/{session_id}/run",
        purpose="Session run response",
    )


def cmd_health(args: argparse.Namespace) -> None:
    emit(args, request("/v1/health"))


def cmd_deployment_guide(args: argparse.Namespace) -> None:
    emit(args, request("/v1/deployment/guide"))


def cmd_commercial_readiness(args: argparse.Namespace) -> None:
    emit(args, request("/v1/commercial/readiness"))


def cmd_adoption_telemetry(args: argparse.Namespace) -> None:
    emit(args, request("/v1/adoption/telemetry"))


def cmd_pmf_readiness(args: argparse.Namespace) -> None:
    emit(args, request("/v1/pmf/readiness"))


def cmd_agents(args: argparse.Namespace) -> None:
    path = f"/v1/agents/status?{urlencode({'user_id': args.user_id})}"
    status = require_json_object(
        request(path),
        path,
        purpose="Agent status response",
    )
    if args.json:
        emit(args, status)
        return
    print_agent_status(status, user_id=args.user_id)


def cmd_agent_add_http(args: argparse.Namespace) -> None:
    capabilities = normalise_agent_capabilities(
        args.capability,
        default=DEFAULT_HTTP_AGENT_CAPABILITIES,
    )
    timeout = normalise_agent_timeout(args.timeout)
    endpoint_value = args.endpoint if args.endpoint is not None else args.endpoint_arg
    if args.endpoint is not None and args.endpoint_arg and args.endpoint != args.endpoint_arg:
        raise StudyAnythingError(
            "Use either positional AGENT_ENDPOINT or --endpoint, not both with different values."
        )
    if endpoint_value is None:
        endpoint_value = DEFAULT_LOCAL_AGENT_ENDPOINT
    endpoint = normalise_http_agent_endpoint(endpoint_value)
    label_text = _option_text(args.label)
    label = label_text.strip() if label_text.strip() else default_http_agent_label(endpoint)
    provider = require_json_object(
        post(
            "/v1/agents/providers",
            {
                "kind": "http_agent",
                "label": label,
                "endpoint": endpoint,
                "capabilities": capabilities,
                "timeout_seconds": timeout,
            },
        ),
        "/v1/agents/providers",
        purpose="Agent provider creation response",
    )
    provider_id = require_string_field(
        provider,
        "provider_id",
        "/v1/agents/providers",
        purpose="Agent provider creation response",
    )
    if args.set_default:
        for capability in capabilities:
            post(
                "/v1/agents/defaults",
                {
                    "user_id": args.user_id,
                    "capability": capability,
                    "provider_id": provider_id,
                },
            )
    if args.json:
        emit(args, provider)
        return
    print_agent_provider_created(
        provider,
        defaults_configured=args.set_default,
        capabilities=capabilities,
    )


def cmd_agent_test(args: argparse.Namespace) -> None:
    provider_id = args.provider_id
    if not provider_id:
        path = f"/v1/agents/status?{urlencode({'user_id': args.user_id})}"
        status = require_json_object(
            request(path),
            path,
            purpose="Agent status response",
        )
        provider_id = select_agent_provider_for_test(status)
    result = require_json_object(
        post("/v1/agents/test", {"provider_id": provider_id}),
        "/v1/agents/test",
        purpose="Agent test response",
    )
    if args.json:
        emit(args, result)
        return
    print_agent_test_result(result)


def cmd_agent_set_default(args: argparse.Namespace) -> None:
    custom_capabilities = normalise_agent_capabilities(args.capability, default=[])
    if custom_capabilities:
        capabilities = custom_capabilities
    else:
        capabilities = list(DEFAULT_HTTP_AGENT_CAPABILITIES)
    if args.all and custom_capabilities:
        capabilities = list(dict.fromkeys(DEFAULT_HTTP_AGENT_CAPABILITIES + custom_capabilities))
    provider_id = args.provider_id
    if not provider_id:
        path = f"/v1/agents/status?{urlencode({'user_id': args.user_id})}"
        agent_status = require_json_object(
            request(path),
            path,
            purpose="Agent status response",
        )
        provider_id = select_agent_provider_for_test(agent_status)
    status: Dict[str, Any] = {}
    for capability in capabilities:
        status = require_json_object(
            post(
                "/v1/agents/defaults",
                {
                    "user_id": args.user_id,
                    "capability": capability,
                    "provider_id": provider_id,
                },
            ),
            "/v1/agents/defaults",
            purpose="Agent defaults response",
        )
    if args.json:
        emit(args, status)
        return
    print(f"default_provider: {provider_id}")
    print(f"updated_capabilities: {', '.join(capabilities)}")
    print_agent_status(status, user_id=args.user_id)


def cmd_plugin_sdk(args: argparse.Namespace) -> None:
    emit(args, request("/v1/plugins/sdk"))


def cmd_plugin_capabilities(args: argparse.Namespace) -> None:
    emit(args, request("/v1/plugins/capabilities"))


def cmd_plugin_validate(args: argparse.Namespace) -> None:
    emit(args, post("/v1/plugins/validate-package", {"source_path": args.source_path}))


def cmd_sessions(args: argparse.Namespace) -> None:
    sessions = require_json_list(
        request("/v1/sessions"),
        "/v1/sessions",
        purpose="Sessions list response",
    )
    if args.json:
        emit(
            args,
            [
                session_summary(
                    require_json_object(item, "/v1/sessions", purpose="Sessions list item")
                )
                for item in sessions
            ],
        )
        return
    if not sessions:
        print("none")
        print("next:")
        print("- Start a zero-key demo: python3 scripts/study_anything_cli.py demo")
        print("- Start from your own source: python3 scripts/study_anything_cli.py start --text 'Paste source text here.'")
        return
    for session in sessions:
        session = require_json_object(session, "/v1/sessions", purpose="Sessions list item")
        summary = session_summary(session)
        print(
            f"{summary['session_id']} stage={summary['stage']} "
            f"mastery={summary['mastery']['level']} source={summary['source_title'] or '-'}"
        )


def cmd_show(args: argparse.Namespace) -> None:
    path = f"/v1/sessions/{quote(args.session_id)}"
    emit(
        args,
        require_json_object(request(path), path, purpose="Session response"),
        session=True,
    )


def cmd_start(args: argparse.Namespace) -> None:
    emit(args, create_session(args), session=True)


def cmd_answer(args: argparse.Namespace) -> None:
    answer_text = resolve_answer_text_input(args)
    session_path = f"/v1/sessions/{quote(args.session_id)}"
    session = require_json_object(
        request(session_path),
        session_path,
        purpose="Session response",
    )
    item_id = _option_text(args.item_id)
    if not item_id:
        quiz = require_unanswered_quiz(
            session,
            session_path,
            purpose="Session quiz response",
        )
        item_id = require_string_field(
            quiz,
            "item_id",
            session_path,
            purpose="Session quiz response",
        )
    answer_path = f"/v1/sessions/{quote(args.session_id)}/answers"
    completed = require_json_object(
        post(
            answer_path,
            {"answers": {item_id: answer_text}},
        ),
        answer_path,
        purpose="Answer submission response",
    )
    emit(args, completed, session=True)


def cmd_resume(args: argparse.Namespace) -> None:
    path = f"/v1/sessions/{quote(args.session_id)}/resume"
    emit(
        args,
        require_json_object(post(path), path, purpose="Session resume response"),
        session=True,
    )


def cmd_mastery(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/mastery"))


def cmd_events(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/events"))


def cmd_agent_audit(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/agent-audit"))


def cmd_agent_eval(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/agent-eval/artifact"))


def cmd_eval_policy(args: argparse.Namespace) -> None:
    emit(args, request("/v1/evals/policy"))


def cmd_agent_eval_report(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/agent-eval/report"))


def cmd_retrieval_status(args: argparse.Namespace) -> None:
    emit(args, request("/v1/retrieval/status"))


def cmd_retrieval_rebuild(args: argparse.Namespace) -> None:
    emit(args, post(f"/v1/sessions/{quote(args.session_id)}/retrieval/rebuild"))


def cmd_retrieval_search(args: argparse.Namespace) -> None:
    query = urlencode({"q": resolve_query_input(args), "limit": args.limit})
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/retrieval/search?{query}"))


def cmd_retrieval_eval(args: argparse.Namespace) -> None:
    query = urlencode({"q": resolve_query_input(args), "limit": args.limit})
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/retrieval/eval?{query}"))


def cmd_retrieval_import(args: argparse.Namespace) -> None:
    agent_mode = "demo" if args.session_id else resolve_start_agent_mode(args)
    warn_auto_agent_fallback(args, agent_mode)
    payload = {
        "source_session_id": args.source_session_id,
        "query": _option_text(args.query),
        "limit": args.limit,
        "user_id": args.user_id,
        "track": args.track,
        "use_demo_agent": agent_mode == "demo",
    }
    if args.session_id:
        response_path = f"/v1/sessions/{quote(args.session_id)}/retrieval/context-package"
        response = require_json_object(
            post(
                response_path,
                payload,
            ),
            response_path,
            purpose="Retrieval import response",
        )
    else:
        response_path = "/v1/sessions/from-retrieval"
        response = require_json_object(
            post(response_path, payload),
            response_path,
            purpose="Retrieval import response",
        )
    if args.session and isinstance(response, dict) and isinstance(response.get("session"), dict):
        print_session(response["session"])
        return
    emit(args, response)


def cmd_enrich(args: argparse.Namespace) -> None:
    enrichment_text = resolve_enrichment_text_input(args)
    enrichment_reference = resolve_optional_text_option(
        getattr(args, "reference", None),
        default=DEFAULT_ENRICHMENT_REFERENCE,
    )
    enrichment_title = resolve_title_input(
        args,
        enrichment_text,
        default_title=DEFAULT_ENRICHMENT_TITLE,
    )
    metadata: Dict[str, Any] = {}
    if args.metadata_json:
        metadata = parse_json_object_option(
            args.metadata_json,
            "--metadata-json",
            example='{"source":"browser"}',
        )
    payload = {
        "title": _option_text(args.bundle_title, default="Learning Enrichment Bundle"),
        "reference": _option_text(args.bundle_reference),
        "items": [
            {
                "source_type": args.source_type,
                "reference": enrichment_reference,
                "title": enrichment_title,
                "text": enrichment_text,
                "locator": _option_text(args.locator, default="cli-selection"),
                "provenance": {
                    "collector": "study-anything-cli",
                    "capture_method": args.capture_method,
                    "source_owner": "user",
                },
                "redaction_policy": args.redaction_policy,
                "metadata": metadata,
            }
        ],
    }
    emit(args, post(f"/v1/sessions/{quote(args.session_id)}/enrichment", payload))


def cmd_context_validate(args: argparse.Namespace) -> None:
    package = load_json_file(args.package)
    emit(args, post("/v1/context-packages/validate", {"package": package}))


def _importer_inputs(args: argparse.Namespace) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    if args.input_file:
        values.update(load_json_file(args.input_file))
    if args.input_json:
        values.update(
            parse_json_object_option(
                args.input_json,
                "--input-json",
                file_option="--input-file",
                example='{"url":"https://example.test"}',
            )
        )
    return values


def cmd_importer_run(args: argparse.Namespace) -> None:
    run_path = f"/v1/importers/{quote(args.plugin_id)}/run"
    run = require_json_object(
        post(
            run_path,
            {
                "inputs": _importer_inputs(args),
                "confirmed_permissions": args.confirm_permission,
                "allow_network": args.allow_network,
                "include_text": True,
            },
        ),
        run_path,
        purpose="Importer run response",
    )
    package = run.get("package")
    if not isinstance(package, dict):
        raise StudyAnythingError(
            "\n".join(
                [
                    _api_shape_help(run_path, "Importer run response"),
                    "missing object field: package",
                ]
            )
        )
    if args.output:
        write_json_output_file(args.output, package, description="importer package output file")
    response: Any = run
    if args.session_id:
        response_path = f"/v1/sessions/{quote(args.session_id)}/context-package"
        response = require_json_object(
            post(
                response_path,
                {"package": package},
            ),
            response_path,
            purpose="Context package import response",
        )
    elif args.create_session:
        agent_mode = resolve_start_agent_mode(args)
        warn_auto_agent_fallback(args, agent_mode)
        response_path = "/v1/sessions/from-context-package"
        response = require_json_object(
            post(
                response_path,
                {
                    "package": package,
                    "user_id": args.user_id,
                    "track": args.track,
                    "use_demo_agent": agent_mode == "demo",
                },
            ),
            response_path,
            purpose="Context package session response",
        )
    if args.session and isinstance(response, dict) and isinstance(response.get("session"), dict):
        print_session(response["session"])
        return
    if args.output and response is run and not args.json:
        print_wrote_path(args.output)
        return
    emit(args, response)


def cmd_context_import(args: argparse.Namespace) -> None:
    package = load_json_file(args.package)
    if args.session_id:
        response_path = f"/v1/sessions/{quote(args.session_id)}/context-package"
        response = require_json_object(
            post(
                response_path,
                {"package": package},
            ),
            response_path,
            purpose="Context package import response",
        )
    else:
        agent_mode = resolve_start_agent_mode(args)
        warn_auto_agent_fallback(args, agent_mode)
        response_path = "/v1/sessions/from-context-package"
        response = require_json_object(
            post(
                response_path,
                {
                    "package": package,
                    "user_id": args.user_id,
                    "track": args.track,
                    "use_demo_agent": agent_mode == "demo",
                },
            ),
            response_path,
            purpose="Context package session response",
        )
    if args.session and not args.json:
        session = response.get("session")
        if isinstance(session, dict):
            print_session(session)
            return
    emit(args, response)


def cmd_teach(args: argparse.Namespace) -> None:
    layers = args.layer or ["overview", "glossary"]
    payload = {
        "layers": layers,
        "language": _option_text(args.language, default="zh"),
        "level": _option_text(args.level, default="beginner"),
        "max_terms": args.max_terms,
        "example_mode": _option_text(args.example_mode, default="mixed"),
    }
    emit(args, post(f"/v1/sessions/{quote(args.session_id)}/teaching-layers", payload))


def cmd_quality_eval(args: argparse.Namespace) -> None:
    emit(args, request(f"/v1/sessions/{quote(args.session_id)}/agent-eval/quality"))


def cmd_obsidian_export(args: argparse.Namespace) -> None:
    path = f"/v1/sessions/{quote(args.session_id)}/exports/obsidian"
    export = require_json_object(
        request(path),
        path,
        purpose="Obsidian export response",
    )
    if args.output:
        write_output_file(
            args.output,
            str(export.get("markdown") or ""),
            description="Obsidian Markdown output file",
        )
        if not args.json:
            print_wrote_path(args.output)
            return
    if args.markdown and not args.json:
        print(str(export.get("markdown") or ""))
        return
    emit(args, export)


def cmd_enrichment_artifact(args: argparse.Namespace) -> None:
    path = f"/v1/sessions/{quote(args.session_id)}/exports/enrichment-artifact"
    export = require_json_object(
        request(path),
        path,
        purpose="Enrichment artifact export response",
    )
    content_key = "html" if args.html else "markdown"
    if args.output:
        write_output_file(
            args.output,
            str(export.get(content_key) or ""),
            description=f"enrichment {content_key} output file",
        )
        if not args.json:
            print_wrote_path(args.output)
            return
    if args.markdown and not args.json:
        print(str(export.get("markdown") or ""))
        return
    if args.html and not args.json:
        print(str(export.get("html") or ""))
        return
    emit(args, export)


def cmd_learning_package(args: argparse.Namespace) -> None:
    path = f"/v1/sessions/{quote(args.session_id)}/exports/learning-package"
    package = require_json_object(
        request(path),
        path,
        purpose="Learning package export response",
    )
    if args.output:
        write_json_output_file(args.output, package, description="learning package output file")
        if not args.json:
            print_wrote_path(args.output)
            return
    emit(args, package)


def cmd_second_brain_handoff(args: argparse.Namespace) -> None:
    path = f"/v1/sessions/{quote(args.session_id)}/exports/second-brain-handoff"
    handoff = require_json_object(
        request(path),
        path,
        purpose="Second-brain handoff response",
    )
    if args.archive_dir:
        archive_dir = Path(args.archive_dir)
        archive_value = handoff.get("local_archive")
        archive = {} if archive_value is None else archive_value
        if not isinstance(archive, dict):
            raise StudyAnythingError(
                "\n".join(
                    [
                        _api_shape_help(path, "Second-brain handoff response"),
                        "missing object field: local_archive",
                    ]
                )
            )
        manifest = archive.get("manifest") or {}
        files = archive.get("files") or []
        if not isinstance(files, list):
            raise StudyAnythingError(
                "\n".join(
                    [
                        _api_shape_help(path, "Second-brain handoff response"),
                        "local_archive.files must be a list.",
                    ]
                )
            )
        for item in files:
            if not isinstance(item, dict):
                continue
            relative_path = Path(str(item.get("path") or ""))
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise StudyAnythingError(f"Unsafe archive path returned by API: {relative_path}")
            target = archive_dir / relative_path
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise StudyAnythingError(
                    "Cannot create archive directory "
                    f"{display_path_for_error(target.parent, 'archive-dir')}: "
                    f"{redact_path_in_text(str(exc), target.parent, 'archive-dir')}"
                ) from exc
            write_output_file(
                target,
                str(item.get("content") or ""),
                description="second-brain archive file",
            )
        manifest_path = archive_dir / "manifest.json"
        write_json_output_file(
            manifest_path,
            manifest,
            description="second-brain archive manifest",
        )
        if not args.json:
            print_wrote_path(archive_dir, "archive-dir")
            return
    if args.obsidian_markdown and not args.json:
        obsidian_value = handoff.get("obsidian")
        obsidian = {} if obsidian_value is None else obsidian_value
        if not isinstance(obsidian, dict):
            raise StudyAnythingError("Second-brain handoff did not return an Obsidian note.")
        print(str(obsidian.get("markdown") or ""))
        return
    if args.archive_manifest and not args.json:
        archive_value = handoff.get("local_archive")
        archive = {} if archive_value is None else archive_value
        if not isinstance(archive, dict):
            raise StudyAnythingError(
                "\n".join(
                    [
                        _api_shape_help(path, "Second-brain handoff response"),
                        "missing object field: local_archive",
                    ]
                )
            )
        print(json.dumps(archive.get("manifest") or {}, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if args.output:
        write_json_output_file(args.output, handoff, description="second-brain handoff output file")
        if not args.json:
            print_wrote_path(args.output)
            return
    emit(args, handoff)


def cmd_hitl(args: argparse.Namespace) -> None:
    emit(args, request("/v1/hitl"))


def _open_hitl_tasks_from_session(session: Dict[str, Any]) -> list[Dict[str, Any]]:
    open_hitl = session.get("open_hitl")
    if not isinstance(open_hitl, list):
        open_hitl = session.get("hitl_interrupts")
    tasks: list[Dict[str, Any]] = []
    if not isinstance(open_hitl, list):
        return tasks
    for item in open_hitl:
        if not isinstance(item, dict):
            continue
        if item.get("status", "open") != "open":
            continue
        if not isinstance(item.get("task_id"), str) or not item.get("task_id"):
            continue
        tasks.append(item)
    return tasks


def resolve_hitl_task_id(args: argparse.Namespace) -> str:
    if args.task_id:
        return args.task_id
    path = f"/v1/sessions/{quote(args.session_id)}"
    session = require_json_object(
        request(path),
        path,
        purpose="Session response",
    )
    tasks = _open_hitl_tasks_from_session(session)
    if len(tasks) == 1:
        return str(tasks[0]["task_id"])
    if not tasks:
        raise StudyAnythingError(
            "\n".join(
                [
                    f"No open human-review task was found for session {args.session_id}.",
                    "Try these checks:",
                    f"1. Inspect the session: python3 scripts/study_anything_cli.py show --session {args.session_id}",
                    "2. List all open tasks: python3 scripts/study_anything_cli.py hitl",
                    f"3. Resume if the workflow is waiting: python3 scripts/study_anything_cli.py resume --session {args.session_id}",
                ]
            )
        )
    task_list = ", ".join(str(item.get("task_id")) for item in tasks[:5])
    first_task_id = str(tasks[0].get("task_id"))
    raise StudyAnythingError(
        "\n".join(
            [
                f"Multiple open human-review tasks exist for session {args.session_id}: {task_list}.",
                f"Choose one explicitly: python3 scripts/study_anything_cli.py resolve {first_task_id} --session {args.session_id} --decision approve",
                "Or inspect all open tasks: python3 scripts/study_anything_cli.py hitl",
            ]
        )
    )


def cmd_resolve(args: argparse.Namespace) -> None:
    task_id = resolve_hitl_task_id(args)
    note = _positional_text(args.note) or "Resolved from CLI."
    payload: Dict[str, Any] = {"note": note}
    if args.decision:
        payload["decision"] = args.decision
    resolved = post(
        f"/v1/hitl/{quote(task_id)}/resolve",
        {"session_id": args.session_id, "payload": payload},
    )
    emit(args, resolved, session=True)


def cmd_discard(args: argparse.Namespace) -> None:
    if not args.yes:
        raise StudyAnythingError("Discard requires explicit approval. Re-run with --yes.")
    emit(args, post(f"/v1/sessions/{quote(args.session_id)}/discard"), session=True)


def cmd_demo(args: argparse.Namespace) -> None:
    args.user_id = args.user_id or "skill-demo-user"
    args.track = "ACADEMIC"
    args.agent_mode = "demo"
    args.source_type = "local_text"
    args.reference = "demo://skill-cli"
    args.title = "Study Anything CLI Demo"
    args.text = (
        "A learning loop should bind a question to its source, grade a grounded answer, "
        "update mastery, and synthesize a reusable insight."
    )
    session = create_session(args)
    quiz = require_unanswered_quiz(
        session,
        "demo session",
        purpose="Demo session response",
    )
    args.session_id = require_string_field(
        session,
        "session_id",
        "demo session",
        purpose="Demo session response",
    )
    args.item_id = require_string_field(
        quiz,
        "item_id",
        "demo session",
        purpose="Demo quiz response",
    )
    args.text = "The learning loop uses source evidence to grade an answer and update mastery."
    cmd_answer(args)


def cmd_lesson(args: argparse.Namespace) -> None:
    source_text = resolve_source_text_input(args)
    title = resolve_title_input(args, source_text)
    agent_mode = resolve_start_agent_mode(args)
    warn_auto_agent_fallback(args, agent_mode)
    enrichment_text = None
    if args.enrichment_text or args.enrichment_text_file:
        enrichment_text = resolve_text_input(
            args,
            text_attr="enrichment_text",
            file_attr="enrichment_text_file",
            text_option="--enrichment-text",
            file_option="--enrichment-text-file",
        )
    session = require_json_object(
        post(
            "/v1/sessions",
            {
                "user_id": args.user_id,
                "track": args.track,
                "use_demo_agent": agent_mode == "demo",
            },
        ),
        "/v1/sessions",
        purpose="Lesson session creation response",
    )
    session_id = require_string_field(
        session,
        "session_id",
        "/v1/sessions",
        purpose="Lesson session creation response",
    )
    post(
        f"/v1/sessions/{quote(session_id)}/reading",
        {
            "source_type": args.source_type,
            "reference": _option_text(args.reference),
            "title": title,
            "text": source_text,
        },
    )
    if enrichment_text:
        post(
            f"/v1/sessions/{quote(session_id)}/enrichment",
            {
                "title": _option_text(args.enrichment_bundle_title, default="Lesson Enrichment Bundle"),
                "items": [
                    {
                        "source_type": args.enrichment_source_type,
                        "reference": _option_text(args.enrichment_reference),
                        "title": _option_text(args.enrichment_title, default="Lesson Enrichment"),
                        "text": enrichment_text,
                        "locator": _option_text(args.enrichment_locator, default="cli-selection"),
                        "provenance": {
                            "collector": "study-anything-cli",
                            "capture_method": args.enrichment_capture_method,
                            "source_owner": "user",
                        },
                        "redaction_policy": "reference_only",
                    }
                ],
            },
        )
    teaching_path = f"/v1/sessions/{quote(session_id)}/teaching-layers"
    teaching = require_json_object(
        post(
            teaching_path,
            {
                "layers": args.layer or ["overview", "glossary"],
                "language": _option_text(args.language, default="zh"),
                "level": _option_text(args.level, default="beginner"),
            },
        ),
        teaching_path,
        purpose="Teaching layer response",
    )
    run_path = f"/v1/sessions/{quote(session_id)}/run"
    running = require_json_object(
        post(run_path),
        run_path,
        purpose="Lesson run response",
    )
    quiz = require_unanswered_quiz(
        running,
        run_path,
        purpose="Lesson run response",
    )
    item_id = require_string_field(
        quiz,
        "item_id",
        run_path,
        purpose="Lesson run response",
    )
    answer_path = f"/v1/sessions/{quote(session_id)}/answers"
    completed = require_json_object(
        post(
            answer_path,
            {"answers": {item_id: _positional_text(args.answer) or ""}},
        ),
        answer_path,
        purpose="Lesson answer submission response",
    )
    audit_path = f"/v1/sessions/{quote(session_id)}/agent-audit"
    artifact_path = f"/v1/sessions/{quote(session_id)}/agent-eval/artifact"
    quality_path = f"/v1/sessions/{quote(session_id)}/agent-eval/quality"
    report_path = f"/v1/sessions/{quote(session_id)}/agent-eval/report"
    obsidian_path = f"/v1/sessions/{quote(session_id)}/exports/obsidian"
    package_path = f"/v1/sessions/{quote(session_id)}/exports/learning-package"
    audit = require_json_object(
        request(audit_path),
        audit_path,
        purpose="Agent audit response",
    )
    artifact = require_json_object(
        request(artifact_path),
        artifact_path,
        purpose="Agent eval artifact response",
    )
    quality = require_json_object(
        request(quality_path),
        quality_path,
        purpose="Agent eval quality response",
    )
    report = require_json_object(
        request(report_path),
        report_path,
        purpose="Agent eval report response",
    )
    obsidian = require_json_object(
        request(obsidian_path),
        obsidian_path,
        purpose="Obsidian export response",
    )
    package = require_json_object(
        request(package_path),
        package_path,
        purpose="Learning package export response",
    )
    result = {
        "status": "ok" if completed.get("stage") == "completed" else "needs_review",
        "session": session_summary(completed),
        "teaching_schema": teaching.get("schema_version"),
        "agent_audit_status": audit.get("status"),
        "agent_eval_schema": artifact.get("schema_version"),
        "agent_eval_report_schema": report.get("schema_version"),
        "agent_eval_report_status": report.get("status"),
        "quality_status": quality.get("status"),
        "quality_schema": quality.get("schema_version"),
        "obsidian_schema": obsidian.get("schema_version"),
        "obsidian_filename": obsidian.get("filename"),
        "learning_package_schema": package.get("schema_version"),
        "learning_package_filename": package.get("filename"),
    }
    if args.json:
        emit(args, result)
        return
    print(f"session: {session_id}")
    print(f"stage: {completed.get('stage')}")
    print(f"agent_audit: {audit.get('status')}")
    print(f"quality: {quality.get('status')} ({quality.get('quality_score')})")
    print(f"obsidian: {obsidian.get('filename')}")
    print(f"learning_package: {package.get('filename')}")


def add_session_id(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("session_id", nargs="?", metavar="SESSION_ID", help="Study session id")
    parser.add_argument(
        "--session",
        dest="session_id_alias",
        help="Study session id alias for users who prefer named arguments.",
    )
    parser.add_argument(
        "--session-id",
        dest="session_id_named_alias",
        help="Study session id alias that matches the public API field name.",
    )


def add_session_output_or_id(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--session",
        nargs="?",
        const=True,
        default=False,
        metavar="SESSION_ID",
        help=(
            "Print a compact session summary. When SESSION_ID is provided, expand that existing "
            "session; equivalent to --session-id SESSION_ID plus summary output."
        ),
    )


def normalise_session_id_arg(args: argparse.Namespace) -> None:
    if not hasattr(args, "session_id_alias"):
        return
    positional = getattr(args, "session_id", None)
    aliases = [
        value
        for value in (
            getattr(args, "session_id_alias", None),
            getattr(args, "session_id_named_alias", None),
        )
        if value
    ]
    if getattr(args, "command", "") == "resolve" and _looks_like_placeholder_id(
        getattr(args, "task_id", None),
        {"TASK_ID"},
    ):
        session_hint = next(
            (
                value
                for value in [*aliases, positional]
                if isinstance(value, str)
                and value
                and not _looks_like_placeholder_id(value, {"SESSION_ID"})
            ),
            None,
        )
        _raise_task_placeholder_error(str(args.task_id), session_id=session_hint)
    if (
        getattr(args, "command", "") == "resolve"
        and not aliases
        and getattr(args, "task_id", None)
        and positional
    ):
        raise StudyAnythingError(
            "\n".join(
                [
                    "Resolve received both TASK_ID and SESSION_ID as positional values, which is ambiguous.",
                    "Use one of these forms:",
                    "1. Resolve the only open task for a session: python3 scripts/study_anything_cli.py resolve session-123 --decision approve",
                    "2. Resolve a specific task: python3 scripts/study_anything_cli.py resolve task-123 --session session-123 --decision approve",
                    "3. Inspect open tasks first: python3 scripts/study_anything_cli.py hitl",
                ]
            )
        )
    if aliases:
        unique_aliases = set(aliases)
        if len(unique_aliases) > 1:
            raise StudyAnythingError(
                "Use only one session id value. --session and --session-id were different."
            )
        alias = aliases[0]
        trailing_text_attrs = {
            "answer": "answer_text",
            "enrich": "enrichment_text",
            "retrieval-search": "query_terms",
            "retrieval-eval": "query_terms",
        }
        trailing_text_attr = trailing_text_attrs.get(getattr(args, "command", ""))
        if trailing_text_attr and positional and positional != alias:
            existing_text = getattr(args, trailing_text_attr, None)
            if isinstance(existing_text, list):
                setattr(args, trailing_text_attr, [positional, *existing_text])
            elif existing_text:
                setattr(args, trailing_text_attr, f"{positional} {existing_text}")
            else:
                setattr(args, trailing_text_attr, positional)
            positional = None
        if positional and positional != alias:
            raise StudyAnythingError(
                "Use either positional SESSION_ID, --session, or --session-id, not multiple different values."
            )
        args.session_id = alias
    elif getattr(args, "command", "") == "resolve" and not positional and getattr(args, "task_id", None):
        args.session_id = args.task_id
        args.task_id = None
    if not getattr(args, "session_id", None):
        raise StudyAnythingError(
            "Missing session id. Pass SESSION_ID after the command, --session SESSION_ID, or --session-id SESSION_ID."
        )
    if _looks_like_placeholder_id(getattr(args, "session_id", None), {"SESSION_ID"}):
        _raise_session_placeholder_error(str(args.session_id))


def normalise_session_output_or_id_arg(args: argparse.Namespace) -> None:
    if not hasattr(args, "session"):
        return
    session_value = getattr(args, "session", False)
    if not isinstance(session_value, str):
        return
    existing = getattr(args, "session_id", None)
    if existing and existing != session_value:
        raise StudyAnythingError(
            "Use only one session id value. --session and --session-id were different."
        )
    if _looks_like_placeholder_id(session_value, {"SESSION_ID"}):
        _raise_session_placeholder_error(session_value)
    args.session_id = session_value
    args.session = True


def _raise_session_placeholder_error(value: str) -> None:
    raise StudyAnythingError(
        "\n".join(
            [
                f"Session id is still a placeholder: {value}.",
                "Use a real session id from a previous command.",
                "Try these checks:",
                "1. Start a new session: python3 scripts/study_anything_cli.py start --text 'Paste source text here.'",
                "2. Or list existing sessions: python3 scripts/study_anything_cli.py sessions",
                "3. Then rerun the command with the actual session id.",
            ]
        )
    )


def _raise_task_placeholder_error(value: str, *, session_id: Optional[str] = None) -> None:
    session_form = (
        f"python3 scripts/study_anything_cli.py resolve --session {session_id} --decision approve"
        if session_id
        else "python3 scripts/study_anything_cli.py resolve --session session-123 --decision approve"
    )
    specific_form = (
        f"python3 scripts/study_anything_cli.py resolve task-123 --session {session_id} --decision approve"
        if session_id
        else "python3 scripts/study_anything_cli.py resolve task-123 --session session-123 --decision approve"
    )
    raise StudyAnythingError(
        "\n".join(
            [
                f"Human-review task id is still a placeholder: {value}.",
                "Use a real task id from the HITL queue, or omit TASK_ID when a session has exactly one open task.",
                "Try these checks:",
                "1. List open tasks: python3 scripts/study_anything_cli.py hitl",
                f"2. Resolve the only open task for a session: {session_form}",
                f"3. Resolve a specific task: {specific_form}",
            ]
        )
    )


def _raise_provider_placeholder_error(value: str) -> None:
    raise StudyAnythingError(
        "\n".join(
            [
                f"Agent provider id is still a placeholder: {value}.",
                "Use a real provider id, or let the CLI select the default provider.",
                "Try these checks:",
                "1. List providers: python3 scripts/study_anything_cli.py agents",
                "2. Test the default or only provider: python3 scripts/study_anything_cli.py agent-test",
                "3. Set the default or only provider: python3 scripts/study_anything_cli.py agent-set-default",
            ]
        )
    )


def normalise_provider_id_arg(args: argparse.Namespace) -> None:
    if not hasattr(args, "provider_id_alias"):
        return
    alias = getattr(args, "provider_id_alias", None)
    positional = getattr(args, "provider_id", None)
    if alias:
        if positional and positional != alias:
            raise StudyAnythingError(
                "Use either positional PROVIDER_ID or --provider-id, not both with different values."
            )
        args.provider_id = alias
    if _looks_like_placeholder_id(getattr(args, "provider_id", None), {"PROVIDER_ID"}):
        _raise_provider_placeholder_error(str(args.provider_id))
    if not getattr(args, "provider_id", None):
        if getattr(args, "provider_id_optional", False):
            return
        raise StudyAnythingError(
            "Missing provider id. Pass PROVIDER_ID after the command or use --provider-id PROVIDER_ID."
    )


def default_agent_capabilities_configured(status: Dict[str, Any]) -> bool:
    defaults = status.get("defaults") if isinstance(status.get("defaults"), dict) else {}
    return all(defaults.get(capability) for capability in AUTO_AGENT_MODE_REQUIRED_CAPABILITIES)


def missing_auto_agent_defaults(status: Dict[str, Any]) -> list[str]:
    defaults = status.get("defaults") if isinstance(status.get("defaults"), dict) else {}
    return [
        capability
        for capability in AUTO_AGENT_MODE_REQUIRED_CAPABILITIES
        if not defaults.get(capability)
    ]


def has_user_agent_configuration(status: Dict[str, Any]) -> bool:
    providers = status.get("providers") if isinstance(status.get("providers"), list) else []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        if not provider.get("enabled", True):
            continue
        if provider.get("kind") != "fake_agent":
            return True
    defaults = status.get("defaults") if isinstance(status.get("defaults"), dict) else {}
    return any(
        provider_id and provider_id != "fake-deterministic"
        for provider_id in defaults.values()
    )


def suggest_agent_provider_id_for_default(status: Dict[str, Any]) -> str:
    defaults = status.get("defaults") if isinstance(status.get("defaults"), dict) else {}
    for provider_id in defaults.values():
        if provider_id and provider_id != "fake-deterministic":
            return str(provider_id)
    providers = status.get("providers") if isinstance(status.get("providers"), list) else []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        if not provider.get("enabled", True):
            continue
        provider_id = provider.get("provider_id")
        if provider_id and provider_id != "fake-deterministic" and provider.get("kind") != "fake_agent":
            return str(provider_id)
    return "PROVIDER_ID"


def resolve_start_agent_mode(args: argparse.Namespace) -> str:
    agent_mode = getattr(args, "agent_mode", "auto")
    if agent_mode != "auto":
        return agent_mode
    path = f"/v1/agents/status?{urlencode({'user_id': args.user_id})}"
    status = require_json_object(
        request(path),
        path,
        purpose="Agent status response",
    )
    missing_defaults = missing_auto_agent_defaults(status)
    args.auto_agent_missing_defaults = missing_defaults
    args.auto_agent_has_user_configuration = has_user_agent_configuration(status)
    args.auto_agent_suggested_provider_id = suggest_agent_provider_id_for_default(status)
    if not missing_defaults:
        return "configured"
    return "demo"


def warn_auto_agent_fallback(args: argparse.Namespace, agent_mode: str) -> None:
    if getattr(args, "json", False):
        return
    if getattr(args, "agent_mode", "auto") != "auto" or agent_mode != "demo":
        return
    if not getattr(args, "auto_agent_has_user_configuration", False):
        return
    missing = getattr(args, "auto_agent_missing_defaults", []) or []
    lines = [
        "study-anything: auto Agent mode fell back to the zero-key demo because default Agent routing is incomplete.",
    ]
    if missing:
        lines.append(f"missing defaults: {', '.join(missing)}")
    provider_id = getattr(args, "auto_agent_suggested_provider_id", "PROVIDER_ID") or "PROVIDER_ID"
    lines.extend(
        [
            "fix: python3 scripts/study_anything_cli.py agents",
            f"then: python3 scripts/study_anything_cli.py agent-set-default {provider_id}",
        ]
    )
    print("\n".join(lines), file=sys.stderr)


def add_agent_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--agent-mode",
        choices=["auto", "demo", "configured"],
        default="auto",
        help=(
            "auto uses configured Agent defaults when enough learning capabilities are routed; "
            "otherwise it uses the zero-key demo agent."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = StudyAnythingArgumentParser(description=__doc__)
    parser.add_argument("--api-base", help="Override STUDY_ANYTHING_API_BASE for this command")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=StudyAnythingArgumentParser,
    )

    health = subparsers.add_parser("health", help="Check API health")
    health.set_defaults(func=cmd_health)

    deployment_guide = subparsers.add_parser(
        "deployment-guide",
        help="Show first-run launch paths, diagnostics, and platform-agent privacy boundaries",
    )
    deployment_guide.set_defaults(func=cmd_deployment_guide)

    commercial_readiness = subparsers.add_parser(
        "commercial-readiness",
        help="Show OSS/local-first commercial readiness, hosted-service contracts, and launch limits",
    )
    commercial_readiness.set_defaults(func=cmd_commercial_readiness)

    adoption_telemetry = subparsers.add_parser(
        "adoption-telemetry",
        help="Show local aggregate adoption telemetry without private learning content",
    )
    adoption_telemetry.set_defaults(func=cmd_adoption_telemetry)

    pmf_readiness = subparsers.add_parser(
        "pmf-readiness",
        help="Show local PMF readiness and hosted-service boundary status",
    )
    pmf_readiness.set_defaults(func=cmd_pmf_readiness)

    agents = subparsers.add_parser("agents", help="List configured agent providers")
    agents.add_argument("--user-id", default="local-user")
    agents.set_defaults(func=cmd_agents)

    add_http = subparsers.add_parser("agent-add-http", help="Configure a user-owned HTTP agent")
    add_http.add_argument(
        "endpoint_arg",
        nargs="?",
        metavar="AGENT_ENDPOINT",
        help="Agent endpoint; equivalent to --endpoint URL",
    )
    add_http.add_argument(
        "--label",
        nargs="+",
        help="Display name; defaults to a label derived from --endpoint",
    )
    add_http.add_argument(
        "--endpoint",
        help=f"Agent endpoint; defaults to {DEFAULT_LOCAL_AGENT_ENDPOINT}",
    )
    add_http.add_argument("--capability", action="append", nargs="+", default=[])
    add_http.add_argument("--timeout", type=int, default=15)
    add_http.add_argument("--user-id", default="local-user")
    add_http.add_argument("--set-default", action="store_true")
    add_http.set_defaults(func=cmd_agent_add_http)

    test_agent = subparsers.add_parser("agent-test", help="Run an agent health check")
    test_agent.add_argument("provider_id", nargs="?", metavar="PROVIDER_ID")
    test_agent.add_argument("--provider-id", dest="provider_id_alias", help="Agent provider id")
    test_agent.add_argument("--user-id", default="local-user")
    test_agent.set_defaults(func=cmd_agent_test, provider_id_optional=True)

    set_agent_default = subparsers.add_parser(
        "agent-set-default",
        help="Set an Agent provider as the default for learning capabilities",
    )
    set_agent_default.add_argument("provider_id", nargs="?", metavar="PROVIDER_ID")
    set_agent_default.add_argument("--provider-id", dest="provider_id_alias", help="Agent provider id")
    set_agent_default.add_argument("--user-id", default="local-user")
    set_agent_default.add_argument(
        "--capability",
        action="append",
        nargs="+",
        default=[],
        help="Capability to route to this provider; repeat for multiple capabilities.",
    )
    set_agent_default.add_argument(
        "--all",
        action="store_true",
        help="Route all common learning capabilities to this provider. This is now the default when no --capability is passed.",
    )
    set_agent_default.set_defaults(func=cmd_agent_set_default, provider_id_optional=True)

    plugin_sdk = subparsers.add_parser("plugin-sdk", help="Show the public Plugin SDK contract")
    plugin_sdk.set_defaults(func=cmd_plugin_sdk)

    plugin_capabilities = subparsers.add_parser(
        "plugin-capabilities",
        help="Show installed plugin hooks, capabilities, trust, and runtime contracts",
    )
    plugin_capabilities.set_defaults(func=cmd_plugin_capabilities)

    plugin_validate = subparsers.add_parser(
        "plugin-validate",
        help="Validate a local plugin package without installing or executing it",
    )
    plugin_validate.add_argument("source_path")
    plugin_validate.set_defaults(func=cmd_plugin_validate)

    sessions = subparsers.add_parser("sessions", help="List learning sessions")
    sessions.set_defaults(func=cmd_sessions)

    show = subparsers.add_parser("show", help="Inspect one learning session")
    add_session_id(show)
    show.set_defaults(func=cmd_show)

    start = subparsers.add_parser("start", help="Start a source-bound learning session")
    start.add_argument(
        "source_text",
        nargs="*",
        metavar="SOURCE_TEXT",
        help="Source text to study; equivalent to --text '...'",
    )
    start.add_argument(
        "--title",
        nargs="+",
        help="Optional source title; defaults to the first source line or reference.",
    )
    start.add_argument("--text", nargs="+", help="Source text to study")
    start.add_argument("--text-file", help="Read source text from a UTF-8 file, or '-' for stdin")
    start.add_argument("--reference", nargs="+", default="local://cli")
    start.add_argument("--source-type", default="local_text")
    start.add_argument("--user-id", default="local-user")
    start.add_argument("--track", default="ACADEMIC")
    add_agent_mode_argument(start)
    start.set_defaults(func=cmd_start)

    answer = subparsers.add_parser("answer", help="Submit one quiz answer")
    add_session_id(answer)
    answer.add_argument(
        "answer_text",
        nargs="*",
        metavar="ANSWER_TEXT",
        help="Answer text; equivalent to --text '...'",
    )
    answer.add_argument("--item-id", nargs="+")
    answer.add_argument("--text", nargs="+", help="Answer text")
    answer.add_argument("--text-file", help="Read answer text from a UTF-8 file, or '-' for stdin")
    answer.set_defaults(func=cmd_answer)

    resume = subparsers.add_parser("resume", help="Resume a learning workflow")
    add_session_id(resume)
    resume.set_defaults(func=cmd_resume)

    mastery = subparsers.add_parser("mastery", help="Show session mastery")
    add_session_id(mastery)
    mastery.set_defaults(func=cmd_mastery)

    events = subparsers.add_parser("events", help="Show session events")
    add_session_id(events)
    events.set_defaults(func=cmd_events)

    agent_audit = subparsers.add_parser("agent-audit", help="Show redacted Agent invocation proof")
    add_session_id(agent_audit)
    agent_audit.set_defaults(func=cmd_agent_audit)

    agent_eval = subparsers.add_parser("agent-eval", help="Show redacted Agent eval artifact")
    add_session_id(agent_eval)
    agent_eval.set_defaults(func=cmd_agent_eval)

    eval_policy = subparsers.add_parser("eval-policy", help="Show Agent eval maturity policy")
    eval_policy.set_defaults(func=cmd_eval_policy)

    agent_eval_report = subparsers.add_parser(
        "agent-eval-report",
        help="Show redacted Agent eval maturity report",
    )
    add_session_id(agent_eval_report)
    agent_eval_report.set_defaults(func=cmd_agent_eval_report)

    retrieval_status = subparsers.add_parser("retrieval-status", help="Show retrieval adapter status")
    retrieval_status.set_defaults(func=cmd_retrieval_status)

    retrieval_rebuild = subparsers.add_parser(
        "retrieval-rebuild",
        help="Rebuild the retrieval index for a session",
    )
    add_session_id(retrieval_rebuild)
    retrieval_rebuild.set_defaults(func=cmd_retrieval_rebuild)

    retrieval_search = subparsers.add_parser(
        "retrieval-search",
        help="Search a rebuilt retrieval index for one session",
    )
    add_session_id(retrieval_search)
    retrieval_search.add_argument(
        "query_terms",
        nargs="*",
        metavar="QUERY",
        help="Search query; equivalent to --query '...'",
    )
    retrieval_search.add_argument("--query", nargs="+")
    retrieval_search.add_argument("--limit", type=int, default=5)
    retrieval_search.set_defaults(func=cmd_retrieval_search)

    retrieval_eval = subparsers.add_parser(
        "retrieval-eval",
        help="Show redacted retrieval/context quality gates",
    )
    add_session_id(retrieval_eval)
    retrieval_eval.add_argument(
        "query_terms",
        nargs="*",
        metavar="QUERY",
        help="Evaluation query; equivalent to --query '...'",
    )
    retrieval_eval.add_argument("--query", nargs="+")
    retrieval_eval.add_argument("--limit", type=int, default=5)
    retrieval_eval.set_defaults(func=cmd_retrieval_eval)

    retrieval_import = subparsers.add_parser(
        "retrieval-import",
        help="Create or expand a session from retrieval results",
    )
    retrieval_import.add_argument("--source-session-id", required=True)
    retrieval_import.add_argument("--query", nargs="+", required=True)
    retrieval_import.add_argument("--limit", type=int, default=5)
    retrieval_import.add_argument("--session-id", help="Expand an existing session instead of creating one")
    retrieval_import.add_argument("--user-id", default="retrieval-import-user")
    retrieval_import.add_argument("--track")
    add_agent_mode_argument(retrieval_import)
    add_session_output_or_id(retrieval_import)
    retrieval_import.set_defaults(func=cmd_retrieval_import)

    enrich = subparsers.add_parser("enrich", help="Attach one enrichment item to a session")
    add_session_id(enrich)
    enrich.add_argument(
        "enrichment_text",
        nargs="*",
        metavar="ENRICHMENT_TEXT",
        help="Enrichment text; equivalent to --text '...'",
    )
    enrich.add_argument("--source-type", default="web")
    enrich.add_argument(
        "--reference",
        nargs="+",
        help=f"Enrichment source reference; defaults to {DEFAULT_ENRICHMENT_REFERENCE}",
    )
    enrich.add_argument(
        "--title",
        nargs="+",
        help="Optional enrichment title; defaults to the first enrichment line or reference.",
    )
    enrich.add_argument("--text", nargs="+", help="Enrichment text")
    enrich.add_argument("--text-file", help="Read enrichment text from a UTF-8 file, or '-' for stdin")
    enrich.add_argument("--locator", nargs="+")
    enrich.add_argument("--capture-method", default="manual_excerpt")
    enrich.add_argument(
        "--redaction-policy",
        choices=["reference_only", "hash_and_locator", "summary_only"],
        default="reference_only",
    )
    enrich.add_argument("--metadata-json")
    enrich.add_argument("--bundle-title", nargs="+", default="Learning Enrichment Bundle")
    enrich.add_argument("--bundle-reference", nargs="+")
    enrich.set_defaults(func=cmd_enrich)

    context_validate = subparsers.add_parser(
        "context-validate",
        help="Validate a Learning Context Package JSON file",
    )
    context_validate.add_argument("package", help="Path to learning-context-package-v1 JSON")
    context_validate.set_defaults(func=cmd_context_validate)

    importer_run = subparsers.add_parser(
        "importer-run",
        help="Run a confirmed local importer plugin and optionally create or expand a session",
    )
    importer_run.add_argument("plugin_id")
    importer_run.add_argument("--input-file", help="JSON object passed to build_context_package")
    importer_run.add_argument("--input-json", help="JSON object passed to build_context_package")
    importer_run.add_argument(
        "--confirm-permission",
        action="append",
        default=[],
        help="Manifest permission to confirm; repeat for every requested permission",
    )
    importer_run.add_argument("--allow-network", action="store_true")
    importer_run.add_argument("--output", help="Write the generated Learning Context Package JSON")
    importer_run.add_argument("--session-id", help="Expand an existing session with the generated package")
    importer_run.add_argument("--create-session", action="store_true")
    importer_run.add_argument("--user-id", default="importer-run-user")
    importer_run.add_argument("--track")
    add_agent_mode_argument(importer_run)
    add_session_output_or_id(importer_run)
    importer_run.set_defaults(func=cmd_importer_run)

    context_import = subparsers.add_parser(
        "context-import",
        help="Create or expand a session from a Learning Context Package JSON file",
    )
    context_import.add_argument("package", help="Path to learning-context-package-v1 JSON")
    context_import.add_argument("--session-id", help="Expand an existing session instead of creating one")
    context_import.add_argument("--user-id", default="context-import-user")
    context_import.add_argument("--track")
    add_agent_mode_argument(context_import)
    add_session_output_or_id(context_import)
    context_import.set_defaults(func=cmd_context_import)

    teach = subparsers.add_parser("teach", help="Generate source-bound teaching layers")
    add_session_id(teach)
    teach.add_argument("--layer", action="append", choices=["overview", "glossary", "examples", "scribe"])
    teach.add_argument("--language", nargs="+", default="zh")
    teach.add_argument("--level", nargs="+", default="beginner")
    teach.add_argument("--max-terms", type=int, default=8)
    teach.add_argument("--example-mode", nargs="+", default="mixed")
    teach.set_defaults(func=cmd_teach)

    quality_eval = subparsers.add_parser("quality-eval", help="Show deterministic teaching-quality gates")
    add_session_id(quality_eval)
    quality_eval.set_defaults(func=cmd_quality_eval)

    obsidian_export = subparsers.add_parser("obsidian-export", help="Export an Obsidian markdown note")
    add_session_id(obsidian_export)
    obsidian_export.add_argument("--markdown", action="store_true", help="Print only Markdown")
    obsidian_export.add_argument("--output", help="Write Markdown to a path")
    obsidian_export.set_defaults(func=cmd_obsidian_export)

    enrichment_artifact = subparsers.add_parser(
        "enrichment-artifact",
        help="Export a redacted Markdown/HTML enrichment micro-lesson",
    )
    add_session_id(enrichment_artifact)
    enrichment_artifact.add_argument("--markdown", action="store_true", help="Print only Markdown")
    enrichment_artifact.add_argument("--html", action="store_true", help="Print only HTML")
    enrichment_artifact.add_argument("--output", help="Write Markdown or HTML to a path")
    enrichment_artifact.set_defaults(func=cmd_enrichment_artifact)

    package_export = subparsers.add_parser("package-export", help="Export a portable learning package")
    add_session_id(package_export)
    package_export.add_argument("--output", help="Write package JSON to a path")
    package_export.set_defaults(func=cmd_learning_package)

    second_brain = subparsers.add_parser(
        "second-brain-handoff",
        help="Export a redacted Obsidian/NotebookLM/local archive handoff",
    )
    add_session_id(second_brain)
    second_brain.add_argument("--output", help="Write full handoff JSON to a path")
    second_brain.add_argument("--archive-dir", help="Write local archive files and manifest to a directory")
    second_brain.add_argument("--obsidian-markdown", action="store_true", help="Print only the redacted Obsidian note")
    second_brain.add_argument("--archive-manifest", action="store_true", help="Print only the local archive manifest")
    second_brain.set_defaults(func=cmd_second_brain_handoff)

    hitl = subparsers.add_parser("hitl", help="List open human-review tasks")
    hitl.set_defaults(func=cmd_hitl)

    resolve = subparsers.add_parser("resolve", help="Resolve a human-review task")
    resolve.add_argument("task_id", nargs="?", metavar="TASK_ID")
    add_session_id(resolve)
    resolve.add_argument(
        "--decision",
        choices=["approve", "reject", "skip"],
        help="Optional structured decision stored with the HITL resolution payload.",
    )
    resolve.add_argument("--note", nargs="+", default="Resolved from CLI.")
    resolve.set_defaults(func=cmd_resolve)

    discard = subparsers.add_parser("discard", help="Discard a session with explicit approval")
    add_session_id(discard)
    discard.add_argument("--yes", action="store_true")
    discard.set_defaults(func=cmd_discard)

    demo = subparsers.add_parser("demo", help="Complete a deterministic local demo")
    demo.add_argument("--user-id", default="skill-demo-user")
    demo.set_defaults(func=cmd_demo)

    lesson = subparsers.add_parser("lesson", help="Complete one source-bound learning lesson")
    lesson.add_argument(
        "source_text",
        nargs="*",
        metavar="SOURCE_TEXT",
        help="Source text to study; equivalent to --text '...'",
    )
    lesson.add_argument(
        "--title",
        nargs="+",
        help="Optional source title; defaults to the first source line or reference.",
    )
    lesson.add_argument("--text", nargs="+", help="Source text to study")
    lesson.add_argument("--text-file", help="Read source text from a UTF-8 file, or '-' for stdin")
    lesson.add_argument("--reference", nargs="+", default="local://lesson")
    lesson.add_argument("--source-type", default="local_text")
    lesson.add_argument("--answer", nargs="+", required=True)
    lesson.add_argument("--user-id", default="lesson-user")
    lesson.add_argument("--track", default="ACADEMIC")
    add_agent_mode_argument(lesson)
    lesson.add_argument("--layer", action="append", choices=["overview", "glossary", "examples", "scribe"])
    lesson.add_argument("--language", nargs="+", default="zh")
    lesson.add_argument("--level", nargs="+", default="beginner")
    lesson.add_argument("--enrichment-text", nargs="+")
    lesson.add_argument("--enrichment-text-file", help="Read enrichment text from a UTF-8 file, or '-' for stdin")
    lesson.add_argument("--enrichment-source-type", default="web")
    lesson.add_argument("--enrichment-reference", nargs="+", default="https://example.test/lesson-enrichment")
    lesson.add_argument("--enrichment-title", nargs="+", default="Lesson Enrichment")
    lesson.add_argument("--enrichment-locator", nargs="+")
    lesson.add_argument("--enrichment-capture-method", default="manual_excerpt")
    lesson.add_argument("--enrichment-bundle-title", nargs="+", default="Lesson Enrichment Bundle")
    lesson.set_defaults(func=cmd_lesson)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(normalise_global_options(argv))
    if args.api_base:
        os.environ["STUDY_ANYTHING_API_BASE"] = args.api_base
    normalise_session_id_arg(args)
    normalise_session_output_or_id_arg(args)
    normalise_provider_id_arg(args)
    args.func(args)


if __name__ == "__main__":
    wants_json = argv_wants_json(sys.argv[1:])
    try:
        main()
    except StudyAnythingError as exc:
        emit_cli_error(exc, wants_json=wants_json)
        sys.exit(1)
