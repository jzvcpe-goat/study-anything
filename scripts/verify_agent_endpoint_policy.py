#!/usr/bin/env python3
"""Verify the configured outbound boundary for user-owned HTTP Agents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps/api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.core.agent_endpoint_policy import (  # noqa: E402
    AgentEndpointPolicyError,
    load_agent_endpoint_policy,
)
from study_anything.core.agent_registry import (  # noqa: E402
    AgentRegistry,
    _NoAgentRedirectHandler,
)


SCHEMA_VERSION = "agent-endpoint-policy-verification-v1"
ENV_TEMPLATE = ROOT / ".env.example"
COMPOSE_FILE = ROOT / "infra/compose/docker-compose.yml"
CHECK_ENV = ROOT / "scripts/check_env.py"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security.yml"
RELEASE_CHECK = ROOT / "scripts/release_check.sh"


class AgentEndpointPolicyVerificationError(RuntimeError):
    """Readable Agent endpoint policy verification failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AgentEndpointPolicyVerificationError(message)


def require_markers(path: Path, markers: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    require(not missing, f"Required Agent endpoint policy markers are missing from {path.name}")


def verify() -> dict[str, Any]:
    local_policy = load_agent_endpoint_policy({"APP_ENV": "development"})
    require(local_policy.mode == "operator", "Local policy must default to operator mode")

    production_policy = load_agent_endpoint_policy(
        {
            "APP_ENV": "production",
            "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY": "allowlist",
            "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST": "https://agent.example",
        }
    )
    production_policy.validate("https://agent.example/invoke")
    blocked_other_origin = False
    try:
        production_policy.validate("https://other.example/invoke")
    except AgentEndpointPolicyError:
        blocked_other_origin = True
    require(blocked_other_origin, "Allowlist mode accepted an untrusted origin")

    blocked_insecure_origin = False
    try:
        load_agent_endpoint_policy(
            {
                "APP_ENV": "production",
                "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST": "http://agent.example",
            }
        )
    except AgentEndpointPolicyError:
        blocked_insecure_origin = True
    require(blocked_insecure_origin, "Production allowlist accepted non-loopback HTTP")

    registry = AgentRegistry(endpoint_policy=production_policy)
    provider = registry.configure_provider(
        kind="http_agent",
        label="Policy verifier Agent",
        endpoint="https://agent.example/invoke",
        capabilities=["source.verify"],
    )
    require(provider.enabled, "Allowed Agent provider was not registered")
    public_policy = registry.status("verifier-user")["endpoint_policy"]
    require(public_policy["allowed_origin_count"] == 1, "Public policy count is invalid")
    require(public_policy["allowed_origins_returned"] is False, "Allowlist origins were exposed")
    require(public_policy["redirects_allowed"] is False, "Redirect policy is not closed")
    require(
        _NoAgentRedirectHandler().redirect_request() is None,
        "HTTP Agent redirect handler must reject redirects",
    )

    env_markers = (
        "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=operator",
        "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST=",
    )
    require_markers(ENV_TEMPLATE, env_markers)
    require_markers(COMPOSE_FILE, tuple(marker.split("=")[0] for marker in env_markers))
    require_markers(
        CHECK_ENV,
        (
            "production_agent_allowlist_required",
            "empty_agent_endpoint_allowlist",
            "invalid_agent_endpoint_allowlist_origin",
        ),
    )
    gate_marker = "verify_agent_endpoint_policy.py --check"
    require_markers(SECURITY_WORKFLOW, (gate_marker,))
    require_markers(RELEASE_CHECK, (gate_marker,))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "policy": {
            "local_default": "operator",
            "production_required": "allowlist",
            "exact_origin_match": True,
            "non_loopback_https_required": True,
            "redirects_rejected": True,
            "allowed_origins_returned": False,
        },
        "integration": {
            "env_template": True,
            "compose_passthrough": True,
            "preflight_diagnostics": True,
            "scheduled_security_gate": True,
            "release_gate": True,
        },
        "privacy": {
            "metadata_only": True,
            "allowed_origins_included": False,
            "local_absolute_paths_included": False,
            "environment_values_included": False,
            "secrets_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "This verifies configured exact-origin egress policy and redirect rejection. "
            "It is not hosted identity, tenant isolation, network-layer egress enforcement, "
            "or a certification against a compromised allowed Agent gateway."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        report = verify()
    except (AgentEndpointPolicyError, AgentEndpointPolicyVerificationError, OSError) as exc:
        print(f"verify_agent_endpoint_policy failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
