from __future__ import annotations

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from _path import ROOT as API_ROOT  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "verify_adoption_telemetry",
    REPO_ROOT / "scripts" / "verify_adoption_telemetry.py",
)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class AdoptionTelemetryVerifierTests(unittest.TestCase):
    def test_runtime_failure_payload_is_machine_readable(self) -> None:
        payload = verifier.runtime_failure_payload(
            classification="python_dependency_missing",
            diagnostic="missing module at /Users/example/project token=secretToken123456",
            details={"missing_module": "tomllib"},
        )

        self.assertEqual(payload["schema_version"], "adoption-telemetry-error-v1")
        self.assertEqual(payload["classification"], "python_dependency_missing")
        self.assertEqual(payload["details"]["missing_module"], "tomllib")
        self.assertIn(".venv/bin/python", " ".join(payload["next_steps"]))
        serialized = json.dumps(payload, sort_keys=True)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("secretToken123456", serialized)

    def test_runtime_failure_prints_json(self) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                verifier.runtime_failure(
                    "verify_adoption_telemetry requires Python 3.11 or newer.",
                    classification="python_version_unsupported",
                    details={"python_version": "3.9.6"},
                )

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["details"]["python_version"], "3.9.6")

    def test_core_verifier_returns_safe_contracts(self) -> None:
        telemetry, readiness = verifier.verify_core()

        self.assertEqual(telemetry["schema_version"], "adoption-telemetry-v1")
        self.assertEqual(readiness["schema_version"], "pmf-readiness-v1")
        self.assertTrue(telemetry["adoption"]["tool_import_success"])
        self.assertTrue(telemetry["quality"]["agent_eval_passed"])
        self.assertFalse(telemetry["privacy"]["source_text_included"])
        self.assertFalse(telemetry["privacy"]["agent_endpoints_included"])

    def test_failure_formatter_is_actionable_and_redacted(self) -> None:
        local_home = "/Users/" + "james"
        secret = "sk-" + "proj-private-adoption-token"
        message = verifier.format_cli_failure(
            verifier.AdoptionTelemetryError(
                f"Cannot reach {local_home}/project with api_key={secret}"
            )
        )

        self.assertIn("verify_adoption_telemetry failed.", message)
        self.assertIn("Next steps:", message)
        self.assertIn("launch_skill_mode.sh", message)
        self.assertIn("generate_platform_adoption_pack.py", message)
        self.assertNotIn(local_home, message)
        self.assertNotIn(secret, message)
        self.assertIn("<redacted>", message)

    def test_main_uses_api_base_environment_when_argument_is_omitted(self) -> None:
        calls: list[str] = []

        def fake_verify_api(api_base: str):
            calls.append(api_base)
            return (
                {
                    "schema_version": "adoption-telemetry-v1",
                    "usage": {"sessions_total": 3},
                    "privacy": {
                        "source_text_included": False,
                        "answers_included": False,
                        "insights_included": False,
                        "raw_user_ids_included": False,
                        "agent_endpoints_included": False,
                        "api_keys_included": False,
                        "browser_video_app_context_included": False,
                        "aggregate_only": True,
                        "automatic_upload": False,
                    },
                },
                {
                    "schema_version": "pmf-readiness-v1",
                    "status": "needs_more_signal",
                    "privacy": {
                        "source_text_included": False,
                        "answers_included": False,
                        "insights_included": False,
                        "raw_user_ids_included": False,
                        "agent_endpoints_included": False,
                        "api_keys_included": False,
                        "browser_video_app_context_included": False,
                        "aggregate_only": True,
                        "automatic_upload": False,
                    },
                },
            )

        stdout = StringIO()
        with (
            patch.object(verifier.sys, "argv", ["verify_adoption_telemetry.py"]),
            patch.dict(verifier.os.environ, {"API_BASE": "http://127.0.0.1:18080"}, clear=True),
            patch.object(verifier, "verify_api", side_effect=fake_verify_api),
            patch("sys.stdout", stdout),
        ):
            verifier.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(calls, ["http://127.0.0.1:18080"])
        self.assertTrue(payload["api_checked"])
        self.assertEqual(payload["api"]["sessions_total"], 3)


if __name__ == "__main__":
    unittest.main()
