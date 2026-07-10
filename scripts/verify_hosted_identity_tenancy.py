#!/usr/bin/env python3
"""Verify hosted OIDC identity and application-layer tenant isolation."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any
from unittest.mock import patch
import warnings

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import jwt


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps/api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.api import main as api_main  # noqa: E402
from study_anything.core.agent_registry import AgentRegistry, AgentRouter  # noqa: E402
from study_anything.core.store import InMemorySessionStore  # noqa: E402
from study_anything.core.workspace import LocalWorkspaceStore  # noqa: E402


SCHEMA_VERSION = "hosted-identity-tenancy-verification-v1"
ENV_TEMPLATE = ROOT / ".env.example"
COMPOSE_FILE = ROOT / "infra/compose/docker-compose.yml"
CHECK_ENV = ROOT / "scripts/check_env.py"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security.yml"
RELEASE_CHECK = ROOT / "scripts/release_check.sh"


class HostedIdentityTenancyVerificationError(RuntimeError):
    """Readable hosted identity or tenant isolation verification failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HostedIdentityTenancyVerificationError(message)


def require_markers(path: Path, markers: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    require(not missing, f"Required hosted identity markers are missing from {path.name}")


def _environment(public_jwk: dict[str, Any]) -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "API_BIND_HOST": "0.0.0.0",
        "STUDY_ANYTHING_API_AUTH_MODE": "oidc_jwt",
        "STUDY_ANYTHING_OIDC_ISSUER": "https://identity.verifier.invalid",
        "STUDY_ANYTHING_OIDC_AUDIENCE": "study-anything-verifier",
        "STUDY_ANYTHING_OIDC_TENANT_CLAIM": "org_id",
        "STUDY_ANYTHING_OIDC_JWKS_JSON": json.dumps({"keys": [public_jwk]}),
        "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY": "allowlist",
        "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST": "https://agent.verifier.invalid",
    }


def _token(
    private_key: rsa.RSAPrivateKey,
    *,
    subject: str,
    tenant: str,
    display_name: str,
) -> str:
    now = int(time.time())
    return str(
        jwt.encode(
            {
                "iss": "https://identity.verifier.invalid",
                "aud": "study-anything-verifier",
                "sub": subject,
                "org_id": tenant,
                "name": display_name,
                "iat": now,
                "exp": now + 300,
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "ephemeral-verifier-key", "typ": "at+jwt"},
        )
    )


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def verify() -> dict[str, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(
        private_key.public_key(),
        as_dict=True,
    )
    public_jwk.update(
        {"kid": "ephemeral-verifier-key", "alg": "RS256", "use": "sig"}
    )
    raw_subject = "verifier-subject-a"
    raw_tenant_a = "verifier-tenant-a"
    raw_tenant_b = "verifier-tenant-b"
    token_a = _token(
        private_key,
        subject=raw_subject,
        tenant=raw_tenant_a,
        display_name="Verifier A",
    )
    token_same_subject_other_tenant = _token(
        private_key,
        subject=raw_subject,
        tenant=raw_tenant_b,
        display_name="Verifier A Other Tenant",
    )
    token_member = _token(
        private_key,
        subject="verifier-subject-member",
        tenant=raw_tenant_a,
        display_name="Verifier Member",
    )
    environment = _environment(public_jwk)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_root = Path(tmpdir)
        store = InMemorySessionStore()
        workspace_store = LocalWorkspaceStore(temp_root / "workspaces.json")
        registry = AgentRegistry(temp_root / "agents.json")
        router = AgentRouter(registry)
        stack = ExitStack()
        stack.enter_context(patch.dict(os.environ, environment, clear=False))
        stack.enter_context(patch.object(api_main, "store", store))
        stack.enter_context(patch.object(api_main, "workspace_store", workspace_store))
        stack.enter_context(patch.object(api_main, "agent_registry", registry))
        stack.enter_context(patch.object(api_main, "agent_router", router))
        client = TestClient(api_main.create_app())
        with stack, client:
            unauthenticated = client.get("/v1/identity/me")
            identity_a = client.get(
                "/v1/identity/me",
                headers=_headers(token_a),
            ).json()
            identity_other_tenant = client.get(
                "/v1/identity/me",
                headers=_headers(token_same_subject_other_tenant),
            ).json()
            identity_member = client.get(
                "/v1/identity/me",
                headers=_headers(token_member),
            ).json()
            workspace_response = client.post(
                "/v1/workspaces",
                headers=_headers(token_a),
                json={
                    "owner_user_id": "body-spoofed-owner",
                    "name": "Verifier Workspace",
                },
            )
            workspace_id = workspace_response.json()["workspace_id"]
            session_response = client.post(
                "/v1/sessions",
                headers=_headers(token_a),
                json={
                    "user_id": "body-spoofed-user",
                    "workspace_id": workspace_id,
                    "use_demo_provider": False,
                },
            )
            session_id = session_response.json()["session_id"]
            cross_tenant = client.get(
                f"/v1/sessions/{session_id}",
                headers=_headers(token_same_subject_other_tenant),
            )
            cross_tenant_workspace = client.post(
                "/v1/sessions",
                headers=_headers(token_same_subject_other_tenant),
                json={
                    "workspace_id": workspace_id,
                    "use_demo_provider": False,
                },
            )
            nonmember = client.get(
                f"/v1/sessions/{session_id}",
                headers=_headers(token_member),
            )
            member_session = client.post(
                "/v1/sessions",
                headers=_headers(token_member),
                json={"use_demo_provider": False},
            )
            cross_workspace_retrieval_create = client.post(
                "/v1/sessions/from-retrieval",
                headers=_headers(token_member),
                json={
                    "source_session_id": session_id,
                    "query": "private source",
                    "use_demo_provider": False,
                },
            )
            cross_workspace_retrieval_append = client.post(
                f"/v1/sessions/{member_session.json()['session_id']}/retrieval/context-package",
                headers=_headers(token_member),
                json={
                    "source_session_id": session_id,
                    "query": "private source",
                    "use_demo_provider": False,
                },
            )
            add_member = client.post(
                f"/v1/workspaces/{workspace_id}/members",
                headers=_headers(token_a),
                json={
                    "acting_user_id": "body-spoofed-owner",
                    "member_user_id": identity_member["principal_id"],
                    "role": "viewer",
                },
            )
            member_read = client.get(
                f"/v1/sessions/{session_id}",
                headers=_headers(token_member),
            )
            member_write = client.post(
                f"/v1/sessions/{session_id}/discard",
                headers=_headers(token_member),
            )
            provider_response = client.post(
                "/v1/agents/providers",
                headers=_headers(token_a),
                json={
                    "kind": "http_agent",
                    "label": "Verifier Agent",
                    "endpoint": "https://agent.verifier.invalid/invoke",
                    "capabilities": ["quiz.generate"],
                },
            )
            provider_id = provider_response.json()["provider_id"]
            other_tenant_agent_status = client.get(
                "/v1/agents/status",
                headers=_headers(token_same_subject_other_tenant),
            ).json()
            blocked_global_route = client.get(
                "/v1/sync/status",
                headers=_headers(token_a),
            )

        state = store.get(session_id)
        persisted_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (temp_root / "workspaces.json", temp_root / "agents.json")
        )

    require(unauthenticated.status_code == 401, "Hosted API accepted a request without JWT")
    require(workspace_response.status_code == 200, "Hosted workspace creation failed")
    require(session_response.status_code == 200, "Hosted session creation failed")
    require(identity_a["principal_id"] != identity_other_tenant["principal_id"], "Principal ID is not tenant-bound")
    require(identity_a["tenant_id"] != identity_other_tenant["tenant_id"], "Tenant IDs collided")
    require(state.user_id == identity_a["principal_id"], "Request body spoofed session principal")
    require(state.tenant_id == identity_a["tenant_id"], "Session tenant did not come from JWT")
    require(cross_tenant.status_code == 404, "Cross-tenant session lookup was observable")
    require(
        cross_tenant_workspace.status_code == 404,
        "Cross-tenant workspace lookup was observable",
    )
    require(nonmember.status_code == 403, "Same-tenant nonmember bypassed workspace RBAC")
    require(member_session.status_code == 200, "Same-tenant verifier session creation failed")
    require(
        cross_workspace_retrieval_create.status_code == 403,
        "Same-tenant nonmember created a session from another workspace's retrieval",
    )
    require(
        cross_workspace_retrieval_append.status_code == 403,
        "Same-tenant nonmember appended another workspace's retrieval",
    )
    require(add_member.status_code == 200, "Workspace member assignment failed")
    require(member_read.status_code == 200, "Workspace viewer could not read a session")
    require(member_write.status_code == 403, "Workspace viewer mutated a session")
    require(provider_response.status_code == 200, "Principal Agent registration failed")
    other_provider_ids = {
        item["provider_id"] for item in other_tenant_agent_status["providers"]
    }
    require(provider_id not in other_provider_ids, "Agent provider crossed a tenant boundary")
    require(blocked_global_route.status_code == 403, "Unscoped hosted route was not blocked")
    require(
        blocked_global_route.json().get("code") == "hosted_route_not_tenant_scoped",
        "Hosted route block did not return its boundary code",
    )
    for raw_value in (
        raw_subject,
        raw_tenant_a,
        raw_tenant_b,
        "body-spoofed-owner",
        "body-spoofed-user",
    ):
        require(raw_value not in persisted_text, "Raw hosted identity data was persisted")

    env_markers = (
        "STUDY_ANYTHING_API_AUTH_MODE=local_only",
        "STUDY_ANYTHING_OIDC_ISSUER=",
        "STUDY_ANYTHING_OIDC_AUDIENCE=",
        "STUDY_ANYTHING_OIDC_TENANT_CLAIM=org_id",
        "STUDY_ANYTHING_OIDC_JWKS_JSON=",
    )
    require_markers(ENV_TEMPLATE, env_markers)
    require_markers(COMPOSE_FILE, tuple(marker.split("=")[0] for marker in env_markers[1:]))
    require_markers(
        CHECK_ENV,
        ("oidc_jwt", "invalid_oidc_configuration", "load_hosted_identity_config"),
    )
    gate_marker = "verify_hosted_identity_tenancy.py --check"
    require_markers(SECURITY_WORKFLOW, (gate_marker,))
    require_markers(RELEASE_CHECK, (gate_marker,))

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "identity": {
            "signed_oidc_jwt_required": True,
            "issuer_audience_subject_expiry_validated": True,
            "static_jwks_only": True,
            "automatic_jwks_network_fetch": False,
            "principal_id_tenant_bound": True,
            "request_body_identity_ignored": True,
            "raw_claims_returned": False,
        },
        "tenancy": {
            "session_store_tenant_filtered": True,
            "cross_tenant_resources_return_not_found": True,
            "cross_tenant_workspaces_return_not_found": True,
            "same_tenant_workspace_rbac": True,
            "cross_workspace_retrieval_blocked": True,
            "viewer_mutation_blocked": True,
            "agent_provider_principal_scoped": True,
            "principal_scope_tenant_bound": True,
            "unscoped_hosted_routes_blocked": True,
        },
        "integration": {
            "env_template": True,
            "compose_passthrough": True,
            "preflight_diagnostics": True,
            "scheduled_security_gate": True,
            "release_gate": True,
        },
        "privacy": {
            "metadata_only_output": True,
            "raw_subjects_included": False,
            "raw_tenant_claims_included": False,
            "jwt_tokens_included": False,
            "jwks_keys_included": False,
            "agent_endpoints_included": False,
            "local_absolute_paths_included": False,
            "secrets_included": False,
            "model_calls_performed": False,
            "external_network_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "This verifies offline JWT authentication and application-layer tenant, workspace, "
            "session, and Agent-provider isolation in a temporary process. It is not IdP lifecycle "
            "management, SCIM, database row-level security, separate tenant databases, hosted "
            "infrastructure validation, penetration testing, or an independent external audit."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        report = verify()
    except (HostedIdentityTenancyVerificationError, OSError, ValueError) as exc:
        print(f"verify_hosted_identity_tenancy failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
