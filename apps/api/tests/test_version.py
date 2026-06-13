from __future__ import annotations

from importlib.metadata import version
import unittest

from fastapi.testclient import TestClient
from packaging.version import Version

from study_anything import __version__
from study_anything.api.main import app


class VersionTests(unittest.TestCase):
    def test_api_version_matches_package_metadata(self) -> None:
        self.assertEqual(Version(__version__), Version(version("study-anything")))

    def test_public_status_reports_package_version(self) -> None:
        with TestClient(app) as client:
            health = client.get("/v1/health")
            system = client.get("/v1/system/status")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(system.status_code, 200)
        self.assertEqual(health.json()["version"], __version__)
        self.assertEqual(system.json()["version"], __version__)


if __name__ == "__main__":
    unittest.main()
