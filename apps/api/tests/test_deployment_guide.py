from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from study_anything.api.main import create_app
from fastapi.testclient import TestClient


class DeploymentGuideApiTests(unittest.TestCase):
    def test_deployment_guide_is_redacted_and_actionable(self) -> None:
        client = TestClient(create_app())

        response = client.get("/v1/deployment/guide")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema_version"], "deployment-guide-v1")
        self.assertTrue(payload["no_frontend_required"])
        entrypoints = {item["id"]: item for item in payload["entrypoints"]}
        self.assertIn("skill_mode", entrypoints)
        self.assertIn("docker_source", entrypoints)
        self.assertIn("published_image", entrypoints)
        self.assertIn("./scripts/launch_skill_mode.sh", entrypoints["skill_mode"]["commands"])
        self.assertFalse(payload["privacy"]["real_model_keys_stored_by_study_anything"])
        forbidden = " ".join(payload["privacy"]["must_not_log_or_share"])
        self.assertIn("API keys", forbidden)
        self.assertIn("raw source text", forbidden)


if __name__ == "__main__":
    unittest.main()
