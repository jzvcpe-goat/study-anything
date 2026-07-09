from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT

from study_anything.api import main as api_main
from study_anything.core.api_security import (
    ApiSecurityConfigurationError,
    load_api_security_config,
)


REPO_ROOT = ROOT.parents[1]


class ApiSecurityTests(unittest.TestCase):
    def test_local_default_is_loopback_only_without_cors(self) -> None:
        config = load_api_security_config({})

        self.assertEqual(config.auth_mode, "local_only")
        self.assertEqual(config.bind_host, "127.0.0.1")
        self.assertEqual(config.cors_origins, ())
        self.assertFalse(config.public_dict()["wildcard_cors_allowed"])
        self.assertFalse(config.public_dict()["multi_tenant_authentication"])

    def test_network_or_production_exposure_requires_token_auth(self) -> None:
        with self.assertRaisesRegex(ApiSecurityConfigurationError, "non-loopback"):
            load_api_security_config({"API_BIND_HOST": "0.0.0.0"})
        with self.assertRaisesRegex(ApiSecurityConfigurationError, "APP_ENV=production"):
            load_api_security_config({"APP_ENV": "production"})

    def test_token_mode_rejects_missing_or_weak_token(self) -> None:
        with self.assertRaisesRegex(ApiSecurityConfigurationError, "at least 32"):
            load_api_security_config({"STUDY_ANYTHING_API_AUTH_MODE": "token"})
        with self.assertRaisesRegex(ApiSecurityConfigurationError, "at least 32"):
            load_api_security_config(
                {
                    "STUDY_ANYTHING_API_AUTH_MODE": "token",
                    "STUDY_ANYTHING_API_TOKEN": "short",
                }
            )

    def test_wildcard_cors_is_rejected(self) -> None:
        with self.assertRaisesRegex(ApiSecurityConfigurationError, "Wildcard CORS"):
            load_api_security_config({"STUDY_ANYTHING_CORS_ORIGINS": "*"})

    def test_token_middleware_protects_api_but_keeps_health_public(self) -> None:
        token = "local-test-token-" + "x" * 32
        with patch.dict(
            os.environ,
            {
                "STUDY_ANYTHING_API_AUTH_MODE": "token",
                "STUDY_ANYTHING_API_TOKEN": token,
                "API_BIND_HOST": "127.0.0.1",
            },
            clear=False,
        ):
            client = TestClient(api_main.create_app())

        with client:
            health = client.get("/v1/health")
            missing = client.get("/v1/system/integrations")
            wrong = client.get(
                "/v1/system/integrations",
                headers={"Authorization": "Bearer wrong-token-value-that-is-long-enough"},
            )
            allowed = client.get(
                "/v1/system/integrations",
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["api_security"]["token_required"])
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(missing.headers["www-authenticate"], "Bearer")
        self.assertNotIn(token, json.dumps(missing.json()))

    def test_cors_allows_only_explicit_origin_without_credentials(self) -> None:
        with patch.dict(
            os.environ,
            {"STUDY_ANYTHING_CORS_ORIGINS": "https://trusted.example"},
            clear=False,
        ):
            client = TestClient(api_main.create_app())

        with client:
            trusted = client.options(
                "/v1/system/integrations",
                headers={
                    "Origin": "https://trusted.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
            untrusted = client.options(
                "/v1/system/integrations",
                headers={
                    "Origin": "https://evil.example",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(trusted.headers.get("access-control-allow-origin"), "https://trusted.example")
        self.assertNotIn("access-control-allow-credentials", trusted.headers)
        self.assertNotIn("access-control-allow-origin", untrusted.headers)

    def test_system_status_redacts_local_data_path(self) -> None:
        with TestClient(api_main.create_app()) as client:
            response = client.get("/v1/system/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data_dir"], "<local-data-dir>")
        self.assertFalse(response.json()["data_dir_path_included"])

    def test_check_env_blocks_unsafe_network_config_and_accepts_token_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "API_BIND_HOST=0.0.0.0",
                        "STUDY_ANYTHING_API_AUTH_MODE=local_only",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            blocked = subprocess.run(
                [sys.executable, "scripts/check_env.py", "--env", str(env_path), "--json"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            env_path.write_text(
                "\n".join(
                    [
                        "APP_ENV=production",
                        "API_BIND_HOST=0.0.0.0",
                        "STUDY_ANYTHING_API_AUTH_MODE=token",
                        "STUDY_ANYTHING_API_TOKEN=" + "t" * 40,
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            allowed = subprocess.run(
                [sys.executable, "scripts/check_env.py", "--env", str(env_path), "--json"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        blocked_payload = json.loads(blocked.stdout)
        self.assertEqual(blocked.returncode, 1)
        self.assertIn(
            "network_bind_requires_token_auth",
            {item["code"] for item in blocked_payload["problems"]},
        )
        self.assertNotIn(str(env_path), blocked.stdout)
        self.assertEqual(allowed.returncode, 1)
        allowed_payload = json.loads(allowed.stdout)
        self.assertNotIn(
            "network_bind_requires_token_auth",
            {item["code"] for item in allowed_payload["problems"]},
        )
        self.assertNotIn(
            "missing_or_weak_api_token",
            {item["code"] for item in allowed_payload["problems"]},
        )


if __name__ == "__main__":
    unittest.main()
