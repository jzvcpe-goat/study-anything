from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from study_anything.core.agent_endpoint_policy import (
    AgentEndpointPolicyError,
    load_agent_endpoint_policy,
)
from study_anything.core.agent_registry import AgentRegistry


class AgentEndpointPolicyTests(unittest.TestCase):
    def test_local_default_preserves_operator_owned_endpoints(self) -> None:
        policy = load_agent_endpoint_policy({"APP_ENV": "development"})
        registry = AgentRegistry(endpoint_policy=policy)

        provider = registry.configure_provider(
            kind="http_agent",
            label="Private Agent",
            endpoint="https://private-agent.example.test/invoke",
            capabilities=["quiz.generate"],
        )

        self.assertEqual(provider.endpoint, "https://private-agent.example.test/invoke")
        self.assertEqual(registry.status("local-user")["endpoint_policy"]["mode"], "operator")

    def test_production_requires_allowlist_mode(self) -> None:
        with self.assertRaisesRegex(AgentEndpointPolicyError, "requires"):
            load_agent_endpoint_policy(
                {
                    "APP_ENV": "production",
                    "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY": "operator",
                }
            )

        with self.assertRaisesRegex(AgentEndpointPolicyError, "ALLOWLIST"):
            load_agent_endpoint_policy({"APP_ENV": "production"})

    def test_allowlist_accepts_exact_origin_and_rejects_other_destination(self) -> None:
        policy = load_agent_endpoint_policy(
            {
                "APP_ENV": "production",
                "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST": "https://agent.example.test",
            }
        )
        registry = AgentRegistry(endpoint_policy=policy)

        provider = registry.configure_provider(
            kind="http_agent",
            label="Trusted Agent",
            endpoint="https://agent.example.test/custom/invoke",
            capabilities=["quiz.generate"],
        )

        self.assertEqual(provider.endpoint, "https://agent.example.test/custom/invoke")
        with self.assertRaisesRegex(AgentEndpointPolicyError, "outside"):
            registry.configure_provider(
                kind="http_agent",
                label="Untrusted Agent",
                endpoint="https://other.example.test/invoke",
                capabilities=["quiz.generate"],
            )

    def test_non_loopback_http_allowlist_origin_is_rejected(self) -> None:
        with self.assertRaisesRegex(AgentEndpointPolicyError, "HTTPS"):
            load_agent_endpoint_policy(
                {
                    "APP_ENV": "production",
                    "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST": "http://agent.example.test",
                }
            )

    def test_allowlist_entries_cannot_smuggle_paths(self) -> None:
        with self.assertRaisesRegex(AgentEndpointPolicyError, "exact origins"):
            load_agent_endpoint_policy(
                {
                    "APP_ENV": "production",
                    "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST": (
                        "https://agent.example.test/private/invoke"
                    ),
                }
            )


if __name__ == "__main__":
    unittest.main()
