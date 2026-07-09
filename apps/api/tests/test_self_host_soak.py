from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "self_host_soak.py"


def load_script():
    spec = importlib.util.spec_from_file_location("self_host_soak", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


soak = load_script()


class FakeHealthResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.body


class SelfHostSoakTests(unittest.TestCase):
    def build(self, samples, *, ratio=0.9, consecutive=1):
        return soak.build_receipt(
            samples,
            api_base="http://127.0.0.1:8000",
            interval_seconds=1,
            min_success_ratio=ratio,
            max_consecutive_failures=consecutive,
            started_at="2026-07-09T00:00:00Z",
            finished_at="2026-07-09T00:00:05Z",
        )

    def test_healthy_window_passes_with_metadata_only_receipt(self) -> None:
        receipt = self.build(
            [soak.SoakSample(True, latency, "healthy") for latency in (10, 20, 15)],
            ratio=1.0,
            consecutive=0,
        )

        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["sampling"]["success_ratio"], 1.0)
        self.assertEqual(receipt["latency_ms"]["p50"], 15)
        self.assertEqual(receipt["endpoint"]["scope"], "loopback")
        self.assertFalse(receipt["privacy"]["health_response_body_included"])
        self.assertFalse(receipt["privacy"]["api_token_included"])

    def test_success_ratio_and_consecutive_failures_block_independently(self) -> None:
        ratio_blocked = self.build(
            [soak.SoakSample(True, 10, "healthy"), soak.SoakSample(False, 20, "timeout")],
            ratio=0.75,
            consecutive=1,
        )
        run_blocked = self.build(
            [
                soak.SoakSample(False, 20, "unavailable"),
                soak.SoakSample(False, 21, "unavailable"),
                soak.SoakSample(True, 10, "healthy"),
            ],
            ratio=0.5,
            consecutive=1,
        )

        self.assertIn("success_ratio_below_threshold", ratio_blocked["blocked_reasons"])
        self.assertNotIn("consecutive_failure_budget_exceeded", ratio_blocked["blocked_reasons"])
        self.assertIn("consecutive_failure_budget_exceeded", run_blocked["blocked_reasons"])

    def test_recovery_after_authentication_failure_is_recorded(self) -> None:
        receipt = self.build(
            [
                soak.SoakSample(False, 4, "authentication_failed"),
                soak.SoakSample(True, 5, "healthy"),
            ],
            ratio=0.5,
            consecutive=1,
        )

        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["sampling"]["recovery_count"], 1)
        self.assertTrue(receipt["sampling"]["recovered_after_failure"])
        self.assertEqual(
            receipt["sampling"]["failure_categories"]["authentication_failed"], 1
        )

    def test_receipt_never_serializes_endpoint_or_secret(self) -> None:
        receipt = soak.build_receipt(
            [soak.SoakSample(False, 4, "authentication_failed")],
            api_base="https://private.example.invalid:8443/path?token=verification-secret-value",
            interval_seconds=1,
            min_success_ratio=1.0,
            max_consecutive_failures=0,
            started_at="2026-07-09T00:00:00Z",
            finished_at="2026-07-09T00:00:01Z",
        )
        serialized = json.dumps(receipt)

        self.assertNotIn("private.example.invalid", serialized)
        self.assertNotIn("verification-secret-value", serialized)
        self.assertEqual(receipt["endpoint"]["scope"], "network")
        self.assertTrue(receipt["endpoint"]["tls_enabled"])

    def test_probe_discards_health_body_and_classifies_auth_failure(self) -> None:
        sensitive_body = b'{"status":"ok","detail":"raw source body"}'
        with patch.object(
            soak, "open_health_request", return_value=FakeHealthResponse(sensitive_body)
        ):
            healthy = soak.probe_health(
                "http://127.0.0.1:8000", token="verification-secret-value", timeout_seconds=1
            )
        with patch.object(
            soak,
            "open_health_request",
            side_effect=HTTPError(
                "http://127.0.0.1:8000/v1/health", 401, "unauthorized", {}, None
            ),
        ):
            denied = soak.probe_health(
                "http://127.0.0.1:8000", token="verification-secret-value", timeout_seconds=1
            )

        self.assertTrue(healthy.success)
        self.assertEqual(denied.category, "authentication_failed")
        serialized = json.dumps(self.build([healthy, denied]))
        self.assertNotIn("raw source body", serialized)
        self.assertNotIn("verification-secret-value", serialized)

    def test_probe_rejects_redirects_instead_of_forwarding_authorization(self) -> None:
        with patch.object(
            soak,
            "open_health_request",
            side_effect=HTTPError(
                "http://127.0.0.1:8000/v1/health", 302, "redirect", {}, None
            ),
        ):
            sample = soak.probe_health(
                "http://127.0.0.1:8000", token="verification-secret-value", timeout_seconds=1
            )

        self.assertFalse(sample.success)
        self.assertEqual(sample.category, "http_error")
        self.assertIsNone(soak.NoRedirectHandler().redirect_request())

    def test_token_prefers_environment_and_output_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("STUDY_ANYTHING_API_TOKEN=file-token\n", encoding="utf-8")
            with patch.dict("os.environ", {"STUDY_ANYTHING_API_TOKEN": "environment-token"}):
                self.assertEqual(soak.api_token(env_file), "environment-token")
            target = Path(tmp_dir) / "receipt.json"
            receipt = self.build([soak.SoakSample(True, 5, "healthy")])
            soak.write_receipt(target, receipt)
            self.assertEqual(json.loads(target.read_text())["schema_version"], soak.SCHEMA_VERSION)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_network_token_transport_requires_explicit_confirmation(self) -> None:
        self.assertTrue(
            soak.token_transport_allowed(
                "http://127.0.0.1:8000", token="local-token", allow_network_token=False
            )
        )
        self.assertTrue(
            soak.token_transport_allowed(
                "https://private.example.invalid", token=None, allow_network_token=False
            )
        )
        self.assertFalse(
            soak.token_transport_allowed(
                "https://private.example.invalid",
                token="local-token",
                allow_network_token=False,
            )
        )
        self.assertTrue(
            soak.token_transport_allowed(
                "https://private.example.invalid",
                token="local-token",
                allow_network_token=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
