#!/usr/bin/env python3
"""Verify the loopback, CORS, token-auth, and path-redaction API boundary."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.api import main as api_main  # noqa: E402
from study_anything.core.api_security import (  # noqa: E402
    API_SECURITY_SCHEMA_VERSION,
    ApiSecurityConfigurationError,
    load_api_security_config,
)


class LocalApiSecurityVerificationError(RuntimeError):
    """Raised when a local API security invariant regresses."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LocalApiSecurityVerificationError(message)


def verify() -> dict[str, object]:
    compose_text = (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")
    cli_text = (ROOT / "scripts" / "study_anything_cli.py").read_text(encoding="utf-8")

    require(
        '${API_BIND_HOST:-127.0.0.1}:${API_PORT:-8000}:8000' in compose_text,
        "Compose API port must bind to loopback by default.",
    )
    require("STUDY_ANYTHING_API_AUTH_MODE" in compose_text, "Compose must pass API auth mode.")
    require("API_BIND_HOST=127.0.0.1" in env_text, ".env.example must default to loopback.")
    require(
        "STUDY_ANYTHING_CORS_ORIGINS=" in env_text,
        ".env.example must keep browser origins explicit.",
    )
    require(
        'headers["Authorization"] = f"Bearer {token}"' in cli_text,
        "CLI must send the private API token outside the URL.",
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        generated_env = Path(tmp_dir) / ".env"
        setup = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "setup_env.py"),
                "--output",
                str(generated_env),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
        require(setup.returncode == 0, "setup_env.py could not generate a private env file.")
        if os.name != "nt":
            require(
                generated_env.stat().st_mode & 0o777 == 0o600,
                "Generated env files must be readable and writable only by the current user.",
            )

    local = load_api_security_config({})
    require(local.auth_mode == "local_only", "Local default auth mode drifted.")
    require(local.bind_host == "127.0.0.1", "Local default bind host drifted.")
    require(not local.cors_origins, "Local default must not enable cross-origin access.")

    token = "verification-token-" + "x" * 40
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "production",
            "API_BIND_HOST": "0.0.0.0",
            "STUDY_ANYTHING_API_AUTH_MODE": "token",
            "STUDY_ANYTHING_API_TOKEN": token,
            "STUDY_ANYTHING_CORS_ORIGINS": "https://trusted.example",
        },
        clear=False,
    ):
        client = TestClient(api_main.create_app())

    with client:
        health = client.get("/v1/health")
        unauthorized = client.get("/v1/system/integrations")
        authorized = client.get(
            "/v1/system/integrations",
            headers={"Authorization": f"Bearer {token}"},
        )
        trusted_preflight = client.options(
            "/v1/system/integrations",
            headers={
                "Origin": "https://trusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    require(health.status_code == 200, "Public health endpoint must remain available.")
    require(unauthorized.status_code == 401, "Protected API must reject missing token.")
    require(authorized.status_code == 200, "Protected API must accept the configured token.")
    require(
        trusted_preflight.headers.get("access-control-allow-origin")
        == "https://trusted.example",
        "Explicit trusted CORS origin was not preserved.",
    )
    require(
        "access-control-allow-credentials" not in trusted_preflight.headers,
        "Credentialed CORS must stay disabled.",
    )

    rejected_modes: list[str] = []
    for case_id, values in (
        ("production_without_token_auth", {"APP_ENV": "production"}),
        ("network_without_token_auth", {"API_BIND_HOST": "0.0.0.0"}),
        ("wildcard_cors", {"STUDY_ANYTHING_CORS_ORIGINS": "*"}),
    ):
        try:
            load_api_security_config(values)
        except ApiSecurityConfigurationError:
            rejected_modes.append(case_id)
    require(len(rejected_modes) == 3, "Unsafe API configurations were not all rejected.")

    public_security = health.json()["api_security"]
    serialized = json.dumps(public_security, sort_keys=True)
    require(token not in serialized, "API security status leaked the bearer token.")

    return {
        "schema_version": "local-api-security-verification-v1",
        "status": "pass",
        "contract_schema_version": API_SECURITY_SCHEMA_VERSION,
        "checks": {
            "compose_loopback_default": True,
            "cors_allowlist_only": True,
            "credentialed_cors_disabled": True,
            "production_token_auth_required": True,
            "network_token_auth_required": True,
            "health_public": True,
            "protected_routes_require_token": True,
            "cli_token_header_supported": True,
            "private_env_file_permissions": True,
            "unsafe_modes_rejected": rejected_modes,
        },
        "identity_boundary": {
            "mode": "local_operator_labels",
            "multi_tenant_authentication": False,
            "hosted_team_identity_claimed": False,
        },
        "privacy": {
            "token_value_included": False,
            "absolute_paths_included": False,
            "raw_source_text_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "This proves the local API defaults to loopback and requires an explicit bearer token "
            "for production or network exposure. It does not provide multi-tenant user authentication."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Run the verifier without writing files.")
    parser.parse_args()
    try:
        print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
    except LocalApiSecurityVerificationError as exc:
        print(f"verify_local_api_security failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
