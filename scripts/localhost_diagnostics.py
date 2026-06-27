#!/usr/bin/env python3
"""Shared localhost diagnostics for adoption and platform verifier scripts."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
SECRET_QUERY_KEYS = {
    "api-key",
    "api_key",
    "apikey",
    "access_key",
    "access_token",
    "accesstoken",
    "auth",
    "authorization",
    "bearer",
    "client_secret",
    "clientsecret",
    "cookie",
    "credential",
    "key",
    "password",
    "secret",
    "token",
    "x-api-key",
}


def _parse_env_file_value(raw_value: str) -> str:
    value = raw_value.strip()
    if value.startswith(("'", '"')):
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            return value[1:end]
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def read_env_file_value(env_path: Path, key: str) -> str | None:
    try:
        content = env_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None
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
            return _parse_env_file_value(raw_value)
    return None


def api_base_from_env_file(env_path: Path) -> str | None:
    api_port = read_env_file_value(env_path, "API_PORT")
    if api_port is None or not api_port.isdigit():
        return None
    port = int(api_port)
    if not 1 <= port <= 65535:
        return None
    return f"http://127.0.0.1:{port}"


def normalise_api_base(value: str) -> str:
    """Normalize common copy-paste API base inputs for verifier scripts."""

    base = value.strip()
    if not base:
        return base
    if "://" not in base and base.startswith(("127.", "localhost", "[::1]", "0.0.0.0")):
        base = f"http://{base}"
    parsed = urlparse(base)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        path = parsed.path.rstrip("/")
        if path in {"/health", "/v1/health"}:
            path = ""
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")).rstrip("/")
    return base.rstrip("/")


def resolve_api_base(
    *,
    default: str = DEFAULT_API_BASE,
    env_file: Path | None = None,
) -> str:
    """Resolve the API base for verifier scripts without surprising .env drift.

    Verifier scripts historically preferred API_BASE, so keep that precedence.
    When neither explicit env var is present, follow .env API_PORT before falling
    back to the default local API port.
    """

    explicit = os.getenv("API_BASE") or os.getenv("STUDY_ANYTHING_API_BASE")
    if explicit:
        return normalise_api_base(explicit)
    configured_env_file = Path(os.getenv("STUDY_ANYTHING_ENV_FILE") or env_file or DEFAULT_ENV_FILE)
    return normalise_api_base(api_base_from_env_file(configured_env_file) or default)


def is_local_url(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.hostname or "") in LOCAL_HOSTS


def error_text(exc: BaseException) -> str:
    reason = getattr(exc, "reason", None)
    if reason is not None and reason is not exc:
        return f"{exc} {reason}"
    return str(exc)


def redact_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    hostname = parsed.hostname or ""
    netloc = hostname
    if parsed.username or parsed.password:
        netloc = f"<redacted>@{hostname}"
    try:
        port = parsed.port
    except ValueError:
        host_port = parsed.netloc.rsplit("@", 1)[-1]
        netloc = f"<redacted>@{host_port}" if parsed.username or parsed.password else host_port
    else:
        if port is not None:
            netloc = f"{netloc}:{port}"
    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower().replace("_", "-")
        if (
            normalized_key in SECRET_QUERY_KEYS
            or normalized_key.replace("-", "") in SECRET_QUERY_KEYS
            or value.startswith("sk-")
        ):
            query_pairs.append((key, "<redacted>"))
        else:
            query_pairs.append((key, value))
    query = urlencode(query_pairs).replace("%3Credacted%3E", "<redacted>")
    return urlunparse((parsed.scheme, netloc, parsed.path, "", query, ""))


def redact_diagnostic(text: str) -> str:
    redacted = re.sub(
        r"https?://[^\s\"'<>]+",
        lambda match: redact_url(match.group(0)),
        text or "",
    )
    redacted = re.sub(r"/Users/[^\s\"']+", "<local-path>", redacted)
    redacted = re.sub(r"/private/tmp/[^\s\"']+", "<temp-path>", redacted)
    redacted = re.sub(r"/tmp/[^\s\"']+", "<temp-path>", redacted)
    redacted = re.sub(r"/private/var/folders/[^\s\"']+", "<temp-path>", redacted)
    redacted = re.sub(r"/var/folders/[^\s\"']+", "<temp-path>", redacted)
    redacted = re.sub(
        r"(?i)\b(authorization\s*[:=]\s*(?:bearer\s+)?)[A-Za-z0-9._~+/=-]{8,}",
        r"\1<redacted>",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(api[_-]?key|apikey|x[_-]?api[_-]?key|access[_-]?token|accesstoken|authorization|auth|bearer|client[_-]?secret|clientsecret|cookie|credential|secret|token|password)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}",
        r"\1=<redacted>",
        redacted,
    )
    return re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", redacted)


def is_localhost_socket_blocked(exc: BaseException) -> bool:
    text = error_text(exc)
    lowered = text.lower()
    return (
        "operation not permitted" in lowered
        or "errno 1" in lowered
        or "permissionerror" in lowered
        or "permission denied" in lowered
        or "errno 13" in lowered
    )


def format_api_unreachable(api_base: str, exc: BaseException, *, verifier: str) -> str:
    display_api_base = redact_diagnostic(api_base)
    display_error = redact_diagnostic(error_text(exc))
    if is_local_url(api_base) and is_localhost_socket_blocked(exc):
        return "\n".join(
            [
                f"{verifier} cannot reach Study Anything at {display_api_base}.",
                "The current runner appears to block localhost sockets, so this is a runner/environment limit rather than a Study Anything API failure.",
                f"Diagnostic: {display_error}",
                "Run the verifier from a normal terminal or host shell that permits localhost sockets, then retry:",
                "  ./scripts/launch_skill_mode.sh",
                f"  API_BASE={display_api_base} python3 scripts/{verifier}.py",
                "Use .venv/bin/python instead of python3 if your system Python is older than 3.11.",
                "If the API is already running somewhere else, pass it explicitly:",
                f"  API_BASE=http://host:port python3 scripts/{verifier}.py",
            ]
        )
    if isinstance(exc, URLError):
        return f"Cannot reach Study Anything at {display_api_base}: {display_error}"
    return f"Cannot reach Study Anything at {display_api_base}: {display_error}"


def format_localhost_listen_blocked(*, verifier: str, host: str = "127.0.0.1") -> str:
    return "\n".join(
        [
            f"{verifier} cannot allocate a local port on {host}.",
            "The current runner appears to block localhost listening sockets, so Docker/Skill Mode smoke tests cannot start here.",
            "Run this verifier from a normal terminal or host shell that permits localhost sockets.",
            "If Study Anything is already running elsewhere, use the verifier mode that accepts API_BASE or --api-base.",
            "Use .venv/bin/python instead of python3 if your system Python is older than 3.11.",
        ]
    )


def verifier_name_from_file(path: str) -> str:
    return os.path.basename(path).removesuffix(".py")
