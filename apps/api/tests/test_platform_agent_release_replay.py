from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_platform_agent_replay.py"
REPLAY = REPO / "scripts" / "replay_platform_agent_from_release.py"
REPORT = REPO / "platform" / "generated" / "study-anything-platform-agent-replay.json"
MARKDOWN = REPO / "platform" / "generated" / "study-anything-platform-agent-replay.md"
ARCHIVE = REPO / "platform" / "generated" / "study-anything-platform-agent-replay.zip"
CHECKSUM = REPO / "platform" / "generated" / "study-anything-platform-agent-replay.sha256"

FORBIDDEN_MARKERS = (
    "sk-",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private platform replay source text",
    "Private platform replay learner answer",
    "AGENT_ENDPOINT=http",
    "/Users/",
)


def run_script(script: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def json_from_stdout(stdout: str) -> dict[str, object]:
    for line in reversed(stdout.strip().splitlines()):
        if line.strip().startswith("{"):
            payload = json.loads(line)
            if isinstance(payload, dict):
                return payload
    raise AssertionError(f"No JSON object found in stdout: {stdout}")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class MockStudyAnythingHandler(BaseHTTPRequestHandler):
    server_version = "StudyAnythingMock/1.0"

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/health":
            self._json(200, {"status": "ok", "version": "0.3.28-alpha"})
            return
        if self.path == "/v1/sessions/mock-session/mastery":
            if getattr(self.server, "schema_mismatch", False):
                self._json(200, {"bloom": "remember"})
            else:
                self._json(200, {"level": 0.5, "bloom": "understand"})
            return
        if self.path == "/v1/sessions/mock-session/agent-audit":
            self._json(
                200,
                {
                    "schema_version": "agent-audit-v1",
                    "status": "verified",
                    "observed_tasks": ["quiz.generate", "answer.grade", "insight.synthesize"],
                },
            )
            return
        if self.path == "/v1/sessions/mock-session/agent-eval/artifact":
            self._json(
                200,
                {
                    "schema_version": "agent-eval-artifact-v1",
                    "status": "ready_for_external_eval",
                    "trajectory": [
                        {"task_type": "quiz.generate"},
                        {"task_type": "answer.grade"},
                        {"task_type": "insight.synthesize"},
                    ],
                },
            )
            return
        self._json(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        if self.path == "/v1/sessions":
            self._json(200, {"status": "created", "session_id": "mock-session"})
            return
        if self.path == "/v1/sessions/mock-session/reading":
            self._json(200, {"status": "ok", "source": {"excerpt_hash": "mock-excerpt"}})
            return
        if self.path == "/v1/sessions/mock-session/run":
            self._json(200, {"stage": "awaiting_answers", "quiz_items": [{"item_id": "q1"}]})
            return
        if self.path == "/v1/sessions/mock-session/answers":
            self._json(200, {"stage": "completed"})
            return
        self._json(404, {"detail": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        return


class MockApiServer:
    def __init__(self, *, schema_mismatch: bool = False) -> None:
        self.port = free_port()
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), MockStudyAnythingHandler)
        self.server.schema_mismatch = schema_mismatch
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        return f"http://127.0.0.1:{self.port}"

    def __exit__(self, *_exc: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class PlatformAgentReleaseReplayTests(unittest.TestCase):
    def test_generator_check_passes(self) -> None:
        completed = run_script(GENERATOR, "--check")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("platform-agent release replay evidence is up to date", completed.stdout)

    def test_metadata_fixture_replay_passes_for_platform_profiles(self) -> None:
        for platform in ("kimi", "codex", "workbuddy", "generic-openapi"):
            with self.subTest(platform=platform):
                completed = run_script(
                    REPLAY,
                    "--fixture",
                    "fixtures/release-asset-adoption/asset-only-pass.json",
                    "--asset-dir",
                    "platform/generated",
                    "--platform",
                    platform,
                    "--runtime",
                    "metadata-only",
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                payload = json_from_stdout(completed.stdout)
                self.assertEqual(payload["schema_version"], "platform-agent-release-replay-v1")
                self.assertEqual(payload["classification"], "platform_agent_replay_metadata_ready")
                self.assertEqual(payload["platform"], platform)
                self.assertGreaterEqual(payload["release_assets"]["asset_count"], 6)
                self.assertEqual(len(payload["tool_import"]["required_tools"]), 8)

    def test_external_api_replay_calls_minimum_learning_tool_chain(self) -> None:
        with MockApiServer() as api_base:
            completed = run_script(
                REPLAY,
                "--fixture",
                "fixtures/release-asset-adoption/asset-only-pass.json",
                "--asset-dir",
                "platform/generated",
                "--platform",
                "kimi",
                "--runtime",
                "external-api",
                "--api-base",
                api_base,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)
        self.assertEqual(payload["classification"], "platform_agent_replay_ready")
        self.assertEqual(payload["replay"]["tool_call_count"], 8)
        self.assertEqual(
            [step["tool_name"] for step in payload["replay"]["steps"]],
            [
                "study_anything_health",
                "study_anything_create_session",
                "study_anything_add_reading",
                "study_anything_run",
                "study_anything_answer",
                "study_anything_mastery",
                "study_anything_agent_audit",
                "study_anything_agent_eval_artifact",
            ],
        )
        serialized = json.dumps(payload)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)
        for key, value in payload["privacy"].items():
            self.assertIs(value, False, key)

    def test_external_api_unavailable_can_be_expected_failure(self) -> None:
        port = free_port()
        completed = run_script(
            REPLAY,
            "--fixture",
            "fixtures/release-asset-adoption/asset-only-pass.json",
            "--asset-dir",
            "platform/generated",
            "--runtime",
            "external-api",
            "--api-base",
            f"http://127.0.0.1:{port}",
            "--expect-failure",
            "--request-timeout-seconds",
            "1",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)
        self.assertEqual(payload["status"], "expected_failure")
        self.assertEqual(payload["classification"], "api_unavailable")

    def test_schema_mismatch_can_be_expected_failure(self) -> None:
        with MockApiServer(schema_mismatch=True) as api_base:
            completed = run_script(
                REPLAY,
                "--fixture",
                "fixtures/release-asset-adoption/asset-only-pass.json",
                "--asset-dir",
                "platform/generated",
                "--runtime",
                "external-api",
                "--api-base",
                api_base,
                "--expect-failure",
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)
        self.assertEqual(payload["status"], "expected_failure")
        self.assertEqual(payload["classification"], "schema_mismatch")

    def test_report_markdown_and_checksum_are_public_only(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        markdown = MARKDOWN.read_text(encoding="utf-8")
        checksum = CHECKSUM.read_text(encoding="utf-8")

        self.assertEqual(report["schema_version"], "platform-agent-release-replay-v1")
        self.assertEqual(report["version"], "v0.3.28-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertRegex(report["archive"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertIn(report["archive"]["sha256"], checksum)
        self.assertTrue(ARCHIVE.is_file())
        self.assertIn("platform-agent-release-replay-v1", markdown)
        serialized = json.dumps(report) + markdown
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)
        for key, value in report["privacy_assertions"].items():
            self.assertIs(value, False, key)


if __name__ == "__main__":
    unittest.main()
