"""Outbound destination policy for user-owned HTTP Agent gateways."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import Mapping
import urllib.parse


AGENT_ENDPOINT_POLICY_SCHEMA_VERSION = "agent-endpoint-policy-v1"
AGENT_ENDPOINT_POLICY_MODES = {"operator", "allowlist"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class AgentEndpointPolicyError(ValueError):
    """Raised when an HTTP Agent endpoint is outside the configured trust boundary."""


def _origin(value: str) -> str:
    parts = urllib.parse.urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise AgentEndpointPolicyError("Agent endpoint must be an HTTP(S) URL.")
    try:
        port = parts.port
    except ValueError as exc:
        raise AgentEndpointPolicyError("Agent endpoint contains an invalid port.") from exc
    host = parts.hostname.lower().rstrip(".")
    host_text = f"[{host}]" if ":" in host else host
    default_port = 80 if parts.scheme == "http" else 443
    port_text = f":{port}" if port is not None and port != default_port else ""
    return f"{parts.scheme.lower()}://{host_text}{port_text}"


def _is_loopback_host(host: str) -> bool:
    normalized = host.lower().rstrip(".")
    if normalized in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _parse_allowlist(value: str) -> tuple[str, ...]:
    origins: set[str] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        parts = urllib.parse.urlsplit(item)
        if parts.path not in {"", "/"} or parts.query or parts.fragment:
            raise AgentEndpointPolicyError(
                "Agent endpoint allowlist entries must be exact origins without paths or queries."
            )
        if parts.username or parts.password:
            raise AgentEndpointPolicyError("Agent endpoint allowlist must not contain credentials.")
        origin = _origin(item)
        if parts.scheme == "http" and not _is_loopback_host(parts.hostname or ""):
            raise AgentEndpointPolicyError(
                "Non-loopback Agent allowlist origins must use HTTPS."
            )
        origins.add(origin)
    return tuple(sorted(origins))


@dataclass(frozen=True)
class AgentEndpointPolicy:
    mode: str = "operator"
    allowed_origins: tuple[str, ...] = ()

    def validate(self, endpoint: str) -> None:
        if self.mode == "operator":
            return
        if self.mode != "allowlist":
            raise AgentEndpointPolicyError("Unknown Agent endpoint policy mode.")
        if _origin(endpoint) not in self.allowed_origins:
            raise AgentEndpointPolicyError(
                "HTTP Agent endpoint is outside the configured origin allowlist."
            )

    def public_dict(self) -> dict[str, object]:
        return {
            "schema_version": AGENT_ENDPOINT_POLICY_SCHEMA_VERSION,
            "mode": self.mode,
            "allowed_origin_count": len(self.allowed_origins),
            "redirects_allowed": False,
            "allowed_origins_returned": False,
            "operator_mode_is_hosted_ssrf_boundary": False,
        }


def load_agent_endpoint_policy(environ: Mapping[str, str]) -> AgentEndpointPolicy:
    app_env = (environ.get("APP_ENV") or "development").strip().lower()
    default_mode = "allowlist" if app_env == "production" else "operator"
    mode = (environ.get("STUDY_ANYTHING_AGENT_ENDPOINT_POLICY") or default_mode).strip().lower()
    if mode not in AGENT_ENDPOINT_POLICY_MODES:
        raise AgentEndpointPolicyError(
            "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY must be operator or allowlist."
        )
    allowed_origins = _parse_allowlist(
        environ.get("STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST") or ""
    )
    if app_env == "production" and mode != "allowlist":
        raise AgentEndpointPolicyError(
            "APP_ENV=production requires STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=allowlist."
        )
    if mode == "allowlist" and not allowed_origins:
        raise AgentEndpointPolicyError(
            "Allowlist mode requires STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST."
        )
    return AgentEndpointPolicy(mode=mode, allowed_origins=allowed_origins)
