from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]


SPEC = importlib.util.spec_from_file_location(
    "localhost_diagnostics",
    REPO_ROOT / "scripts" / "localhost_diagnostics.py",
)
assert SPEC is not None and SPEC.loader is not None
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)


class LocalhostDiagnosticsTests(unittest.TestCase):
    def test_resolve_api_base_reads_env_file_api_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text('export API_PORT="18080" # local override\n', encoding="utf-8")

            with patch.dict(
                os.environ,
                {"STUDY_ANYTHING_ENV_FILE": str(env_file)},
                clear=True,
            ):
                self.assertEqual(diagnostics.resolve_api_base(), "http://127.0.0.1:18080")

    def test_resolve_api_base_keeps_api_base_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("API_PORT=18080\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "STUDY_ANYTHING_ENV_FILE": str(env_file),
                    "API_BASE": "http://127.0.0.1:19090",
                    "STUDY_ANYTHING_API_BASE": "http://127.0.0.1:19191",
                },
                clear=True,
            ):
                self.assertEqual(diagnostics.resolve_api_base(), "http://127.0.0.1:19090")

    def test_resolve_api_base_normalises_scheme_less_localhost(self) -> None:
        with patch.dict(os.environ, {"API_BASE": "127.0.0.1:19090"}, clear=True):
            self.assertEqual(diagnostics.resolve_api_base(), "http://127.0.0.1:19090")

    def test_resolve_api_base_normalises_health_url_to_service_root(self) -> None:
        with patch.dict(
            os.environ,
            {"API_BASE": "http://127.0.0.1:19090/v1/health"},
            clear=True,
        ):
            self.assertEqual(diagnostics.resolve_api_base(), "http://127.0.0.1:19090")

    def test_resolve_api_base_strips_query_and_fragment_from_explicit_base(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        with patch.dict(
            os.environ,
            {"API_BASE": f"http://127.0.0.1:19090?token={secret}#debug"},
            clear=True,
        ):
            self.assertEqual(diagnostics.resolve_api_base(), "http://127.0.0.1:19090")

    def test_localhost_socket_block_has_normal_terminal_recovery(self) -> None:
        message = diagnostics.format_api_unreachable(
            "http://127.0.0.1:8000",
            URLError(OSError(1, "Operation not permitted")),
            verifier="verify_platform_lesson_flow",
        )

        self.assertIn("block localhost sockets", message)
        self.assertIn("normal terminal", message)
        self.assertIn("./scripts/launch_skill_mode.sh", message)
        self.assertIn(".venv/bin/python", message)
        self.assertIn("API_BASE=http://host:port", message)

    def test_localhost_socket_block_redacts_secret_api_base_and_error(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        message = diagnostics.format_api_unreachable(
            f"http://user:secret@127.0.0.1:8000?token={secret}",
            URLError(
                OSError(
                    1,
                    "Operation not permitted with Authorization: Bearer "
                    f"{secret} at /private/tmp/study-anything/socket.log",
                )
            ),
            verifier="verify_platform_lesson_flow",
        )

        self.assertIn("http://<redacted>@127.0.0.1:8000?token=<redacted>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertIn("<temp-path>", message)
        self.assertNotIn(secret, message)
        self.assertNotIn("user:secret", message)
        self.assertNotIn("/private/tmp", message)

    def test_localhost_permission_denied_has_normal_terminal_recovery(self) -> None:
        message = diagnostics.format_api_unreachable(
            "http://localhost:8000",
            URLError(OSError(13, "Permission denied")),
            verifier="verify_platform_lesson_flow",
        )

        self.assertIn("block localhost sockets", message)
        self.assertIn("normal terminal", message)
        self.assertIn("./scripts/launch_skill_mode.sh", message)

    def test_lowercase_permission_denied_has_normal_terminal_recovery(self) -> None:
        message = diagnostics.format_api_unreachable(
            "http://localhost:8000",
            URLError("permission denied"),
            verifier="verify_platform_lesson_flow",
        )

        self.assertIn("block localhost sockets", message)
        self.assertIn("normal terminal", message)

    def test_remote_url_keeps_standard_reachability_error(self) -> None:
        message = diagnostics.format_api_unreachable(
            "https://study-anything.example",
            URLError("connection refused"),
            verifier="verify_platform_lesson_flow",
        )

        self.assertIn("Cannot reach Study Anything", message)
        self.assertNotIn("normal terminal", message)

    def test_remote_url_standard_error_is_redacted(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        message = diagnostics.format_api_unreachable(
            f"https://user:secret@study-anything.example/api?api_key={secret}",
            URLError(
                "connection refused with Authorization: Bearer "
                f"{secret} at /Users/james/private/source.txt"
            ),
            verifier="verify_platform_lesson_flow",
        )

        self.assertIn("Cannot reach Study Anything", message)
        self.assertIn("https://<redacted>@study-anything.example/api?api_key=<redacted>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertIn("<local-path>", message)
        self.assertNotIn(secret, message)
        self.assertNotIn("user:secret", message)
        self.assertNotIn("/Users/james", message)

    def test_redact_diagnostic_redacts_camel_case_url_secret_queries(self) -> None:
        message = diagnostics.redact_diagnostic(
            "Cannot reach "
            "https://study-anything.example/api?"
            "apiKey=plainsecret123&x-api-key=plainsecret456&"
            "accessToken=plainsecret789&clientSecret=plainsecret000"
        )

        self.assertIn("apiKey=<redacted>", message)
        self.assertIn("x-api-key=<redacted>", message)
        self.assertIn("accessToken=<redacted>", message)
        self.assertIn("clientSecret=<redacted>", message)
        self.assertNotIn("plainsecret123", message)
        self.assertNotIn("plainsecret456", message)
        self.assertNotIn("plainsecret789", message)
        self.assertNotIn("plainsecret000", message)

    def test_redact_diagnostic_redacts_authorization_assignment_text(self) -> None:
        message = diagnostics.redact_diagnostic(
            "gateway failed with authorization=BearerSecret123456 and cookie=sessionsecret789"
        )

        self.assertIn("authorization=<redacted>", message)
        self.assertIn("cookie=<redacted>", message)
        self.assertNotIn("BearerSecret123456", message)
        self.assertNotIn("sessionsecret789", message)

    def test_redact_diagnostic_handles_log_punctuation_after_port(self) -> None:
        message = diagnostics.redact_diagnostic(
            "Cannot reach http://user:secret@127.0.0.1:9. "
            "Authorization: Bearer sk-proj-abcdefghijklmnop123456"
        )

        self.assertIn("http://<redacted>@127.0.0.1", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("user:secret", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)

    def test_localhost_listen_block_has_normal_terminal_recovery(self) -> None:
        message = diagnostics.format_localhost_listen_blocked(
            verifier="verify_published_image_launch"
        )

        self.assertIn("cannot allocate a local port", message)
        self.assertIn("normal terminal", message)
        self.assertIn("--api-base", message)
        self.assertIn(".venv/bin/python", message)


if __name__ == "__main__":
    unittest.main()
