"""Runtime security boundary for the local-first HTTP API."""

from __future__ import annotations

from dataclasses import dataclass
import hmac
from typing import Mapping


API_SECURITY_SCHEMA_VERSION = "study-anything-api-security-v1"
AUTH_MODES = {"local_only", "token"}
LOOPBACK_BIND_HOSTS = {"127.0.0.1", "::1", "localhost"}
MIN_API_TOKEN_LENGTH = 32


class ApiSecurityConfigurationError(ValueError):
    """Raised when API exposure is broader than its authentication boundary."""


def _split_origins(value: str) -> tuple[str, ...]:
    return tuple(sorted({item.strip().rstrip("/") for item in value.split(",") if item.strip()}))


@dataclass(frozen=True)
class ApiSecurityConfig:
    app_env: str
    bind_host: str
    auth_mode: str
    api_token: str | None
    cors_origins: tuple[str, ...]

    @property
    def token_required(self) -> bool:
        return self.auth_mode == "token"

    def authorises(self, authorization: str | None) -> bool:
        if not self.token_required:
            return True
        if not authorization or not self.api_token:
            return False
        scheme, separator, credential = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer":
            return False
        return hmac.compare_digest(credential.strip(), self.api_token)

    def public_dict(self) -> dict[str, object]:
        return {
            "schema_version": API_SECURITY_SCHEMA_VERSION,
            "app_env": self.app_env,
            "bind_scope": "loopback" if self.bind_host in LOOPBACK_BIND_HOSTS else "network",
            "auth_mode": self.auth_mode,
            "token_required": self.token_required,
            "token_configured": bool(self.api_token),
            "cors_origin_count": len(self.cors_origins),
            "wildcard_cors_allowed": False,
            "credentialed_cors_allowed": False,
            "identity_mode": "local_operator_labels",
            "multi_tenant_authentication": False,
            "secret_values_included": False,
        }


def load_api_security_config(environ: Mapping[str, str]) -> ApiSecurityConfig:
    app_env = (environ.get("APP_ENV") or "development").strip().lower()
    bind_host = (environ.get("API_BIND_HOST") or "127.0.0.1").strip().lower()
    auth_mode = (environ.get("STUDY_ANYTHING_API_AUTH_MODE") or "local_only").strip().lower()
    api_token = (environ.get("STUDY_ANYTHING_API_TOKEN") or "").strip() or None
    cors_origins = _split_origins(environ.get("STUDY_ANYTHING_CORS_ORIGINS") or "")

    if auth_mode not in AUTH_MODES:
        raise ApiSecurityConfigurationError(
            "STUDY_ANYTHING_API_AUTH_MODE must be local_only or token."
        )
    if "*" in cors_origins:
        raise ApiSecurityConfigurationError(
            "Wildcard CORS is not allowed. List trusted origins explicitly."
        )
    if auth_mode == "local_only" and bind_host not in LOOPBACK_BIND_HOSTS:
        raise ApiSecurityConfigurationError(
            "A non-loopback API_BIND_HOST requires STUDY_ANYTHING_API_AUTH_MODE=token."
        )
    if app_env == "production" and auth_mode != "token":
        raise ApiSecurityConfigurationError(
            "APP_ENV=production requires STUDY_ANYTHING_API_AUTH_MODE=token."
        )
    if auth_mode == "token" and (api_token is None or len(api_token) < MIN_API_TOKEN_LENGTH):
        raise ApiSecurityConfigurationError(
            f"Token auth requires STUDY_ANYTHING_API_TOKEN with at least {MIN_API_TOKEN_LENGTH} characters."
        )

    return ApiSecurityConfig(
        app_env=app_env,
        bind_host=bind_host,
        auth_mode=auth_mode,
        api_token=api_token,
        cors_origins=cors_origins,
    )
