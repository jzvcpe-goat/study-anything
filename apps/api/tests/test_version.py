from __future__ import annotations

from importlib.metadata import version

from fastapi.testclient import TestClient

from study_anything import __version__
from study_anything.api.main import app


def test_api_version_matches_package_metadata() -> None:
    assert __version__ == version("study-anything")


def test_public_status_reports_package_version() -> None:
    with TestClient(app) as client:
        health = client.get("/v1/health")
        system = client.get("/v1/system/status")

    assert health.status_code == 200
    assert system.status_code == 200
    assert health.json()["version"] == __version__
    assert system.json()["version"] == __version__
