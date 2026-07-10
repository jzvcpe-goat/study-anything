from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import jwt

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.agent_registry import AgentRegistry, AgentRouter
from study_anything.core.store import InMemorySessionStore
from study_anything.core.workspace import LocalWorkspaceStore


class HostedTenancyApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(
            cls.private_key.public_key(),
            as_dict=True,
        )
        cls.public_jwk.update({"kid": "hosted-test", "alg": "RS256", "use": "sig"})

    def environment(self) -> dict[str, str]:
        return {
            "APP_ENV": "production",
            "API_BIND_HOST": "0.0.0.0",
            "STUDY_ANYTHING_API_AUTH_MODE": "oidc_jwt",
            "STUDY_ANYTHING_OIDC_ISSUER": "https://identity.example.test",
            "STUDY_ANYTHING_OIDC_AUDIENCE": "study-anything-api",
            "STUDY_ANYTHING_OIDC_TENANT_CLAIM": "org_id",
            "STUDY_ANYTHING_OIDC_JWKS_JSON": json.dumps({"keys": [self.public_jwk]}),
            "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY": "allowlist",
            "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST": "https://agent.example.test",
        }

    def token(self, *, subject: str, tenant: str, name: str) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "iss": "https://identity.example.test",
                "aud": "study-anything-api",
                "sub": subject,
                "org_id": tenant,
                "name": name,
                "iat": now,
                "exp": now + 600,
            },
            self.private_key,
            algorithm="RS256",
            headers={"kid": "hosted-test", "typ": "at+jwt"},
        )

    def _client(
        self,
        root: Path,
    ) -> tuple[TestClient, ExitStack, InMemorySessionStore, AgentRegistry]:
        stack = ExitStack()
        store = InMemorySessionStore()
        registry = AgentRegistry(root / "agents.json")
        stack.enter_context(patch.dict(os.environ, self.environment(), clear=False))
        stack.enter_context(patch.object(api_main, "store", store))
        stack.enter_context(
            patch.object(api_main, "workspace_store", LocalWorkspaceStore(root / "workspaces.json"))
        )
        stack.enter_context(patch.object(api_main, "agent_registry", registry))
        stack.enter_context(patch.object(api_main, "agent_router", AgentRouter(registry)))
        return TestClient(api_main.create_app()), stack, store, registry

    @staticmethod
    def headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_oidc_principal_enforces_tenant_workspace_and_route_boundaries(self) -> None:
        token_a = self.token(subject="alice", tenant="tenant-a", name="Alice")
        token_b = self.token(subject="bob", tenant="tenant-b", name="Bob")
        token_c = self.token(subject="carol", tenant="tenant-a", name="Carol")
        with tempfile.TemporaryDirectory() as tmpdir:
            client, stack, store, _ = self._client(Path(tmpdir))
            with stack, client:
                self.assertEqual(client.get("/v1/identity/me").status_code, 401)
                identity_a = client.get(
                    "/v1/identity/me", headers=self.headers(token_a)
                ).json()
                identity_c = client.get(
                    "/v1/identity/me", headers=self.headers(token_c)
                ).json()
                workspace = client.post(
                    "/v1/workspaces",
                    headers=self.headers(token_a),
                    json={"owner_user_id": "spoofed-owner", "name": "Tenant A Course"},
                ).json()
                created = client.post(
                    "/v1/sessions",
                    headers=self.headers(token_a),
                    json={
                        "user_id": "spoofed-user",
                        "workspace_id": workspace["workspace_id"],
                        "use_demo_provider": False,
                    },
                )
                session_id = created.json()["session_id"]

                cross_tenant = client.get(
                    f"/v1/sessions/{session_id}", headers=self.headers(token_b)
                )
                cross_tenant_workspace_create = client.post(
                    "/v1/sessions",
                    headers=self.headers(token_b),
                    json={
                        "workspace_id": workspace["workspace_id"],
                        "use_demo_provider": False,
                    },
                )
                cross_tenant_workspace_member = client.post(
                    f"/v1/workspaces/{workspace['workspace_id']}/members",
                    headers=self.headers(token_b),
                    json={
                        "member_user_id": identity_c["principal_id"],
                        "role": "viewer",
                    },
                )
                same_tenant_non_member = client.get(
                    f"/v1/sessions/{session_id}", headers=self.headers(token_c)
                )
                member_session = client.post(
                    "/v1/sessions",
                    headers=self.headers(token_c),
                    json={"use_demo_provider": False},
                )
                cross_workspace_retrieval_create = client.post(
                    "/v1/sessions/from-retrieval",
                    headers=self.headers(token_c),
                    json={
                        "source_session_id": session_id,
                        "query": "private source",
                        "use_demo_provider": False,
                    },
                )
                cross_workspace_retrieval_append = client.post(
                    f"/v1/sessions/{member_session.json()['session_id']}/retrieval/context-package",
                    headers=self.headers(token_c),
                    json={
                        "source_session_id": session_id,
                        "query": "private source",
                        "use_demo_provider": False,
                    },
                )
                added = client.post(
                    f"/v1/workspaces/{workspace['workspace_id']}/members",
                    headers=self.headers(token_a),
                    json={
                        "acting_user_id": "spoofed-owner",
                        "member_user_id": identity_c["principal_id"],
                        "role": "viewer",
                    },
                )
                viewer_read = client.get(
                    f"/v1/sessions/{session_id}", headers=self.headers(token_c)
                )
                viewer_write = client.post(
                    f"/v1/sessions/{session_id}/reading",
                    headers=self.headers(token_c),
                    json={"title": "Denied", "text": "Denied", "reference": "test://denied"},
                )
                blocked_global = client.get(
                    "/v1/sync/status", headers=self.headers(token_a)
                )

        self.assertEqual(created.status_code, 200)
        self.assertEqual(store.get(session_id).user_id, identity_a["principal_id"])
        self.assertEqual(store.get(session_id).tenant_id, identity_a["tenant_id"])
        self.assertEqual(cross_tenant.status_code, 404)
        self.assertEqual(cross_tenant_workspace_create.status_code, 404)
        self.assertEqual(cross_tenant_workspace_member.status_code, 404)
        self.assertEqual(same_tenant_non_member.status_code, 403)
        self.assertEqual(member_session.status_code, 200)
        self.assertEqual(cross_workspace_retrieval_create.status_code, 403)
        self.assertEqual(cross_workspace_retrieval_append.status_code, 403)
        self.assertEqual(added.status_code, 200)
        self.assertEqual(viewer_read.status_code, 200)
        self.assertEqual(viewer_write.status_code, 403)
        self.assertEqual(blocked_global.status_code, 403)
        self.assertEqual(blocked_global.json()["code"], "hosted_route_not_tenant_scoped")
        self.assertNotIn("tenant-a", json.dumps(identity_a))
        self.assertNotIn("alice", json.dumps(identity_a))

    def test_agent_providers_are_principal_scoped_in_hosted_mode(self) -> None:
        token_a = self.token(subject="alice", tenant="tenant-a", name="Alice")
        token_c = self.token(subject="carol", tenant="tenant-a", name="Carol")
        token_same_subject_other_tenant = self.token(
            subject="alice",
            tenant="tenant-b",
            name="Alice B",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            client, stack, _, _ = self._client(Path(tmpdir))
            with stack, client:
                provider = client.post(
                    "/v1/agents/providers",
                    headers=self.headers(token_a),
                    json={
                        "kind": "http_agent",
                        "label": "Alice Agent",
                        "endpoint": "https://agent.example.test/invoke",
                        "capabilities": ["quiz.generate"],
                    },
                )
                provider_id = provider.json()["provider_id"]
                status_a = client.get(
                    "/v1/agents/status", headers=self.headers(token_a)
                ).json()
                status_c = client.get(
                    "/v1/agents/status", headers=self.headers(token_c)
                ).json()
                status_other_tenant = client.get(
                    "/v1/agents/status",
                    headers=self.headers(token_same_subject_other_tenant),
                ).json()
                cross_principal_invoke = client.post(
                    f"/v1/agents/{provider_id}/invoke",
                    headers=self.headers(token_c),
                    json={"task_type": "quiz.generate", "session_id": "test"},
                )

        self.assertEqual(provider.status_code, 200)
        self.assertEqual(provider.json()["scope"], "principal")
        self.assertIn(provider_id, {item["provider_id"] for item in status_a["providers"]})
        self.assertNotIn(provider_id, {item["provider_id"] for item in status_c["providers"]})
        self.assertNotIn(
            provider_id,
            {item["provider_id"] for item in status_other_tenant["providers"]},
        )
        self.assertEqual(cross_principal_invoke.status_code, 400)
        self.assertTrue(all("scope_id" not in item for item in status_a["providers"]))
        self.assertFalse(status_a["scope_id_included"])
        self.assertTrue(status_a["scope_applied"])


if __name__ == "__main__":
    unittest.main()
