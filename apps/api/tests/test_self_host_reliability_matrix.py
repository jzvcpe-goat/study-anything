from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "self_host_reliability_matrix.py"


def load_script():
    script_dir = str(SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("self_host_reliability_matrix", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


matrix = load_script()


class SelfHostReliabilityMatrixTests(unittest.TestCase):
    def build(self, *, mode="source-build", status="pass", soak=None):
        return matrix.build_receipt(
            mode=mode,
            status=status,
            started_at="2026-07-09T00:00:00Z",
            finished_at="2026-07-09T02:00:00Z",
            samples_requested=721,
            interval_seconds=10,
            fault_after_seconds=600,
            fault_duration_seconds=45,
            soak=soak,
            api_flow_completed=status == "pass",
            source_build_completed=mode == "source-build" and status == "pass",
            image_pull_completed=mode == "published-image" and status == "pass",
            restart_attempted=status == "pass",
            restart_completed=status == "pass",
            session_recovery_completed=status == "pass",
            source_revision_sha="a" * 40 if mode == "source-build" else None,
            source_worktree_dirty=False if mode == "source-build" else None,
            published_image_digest=(
                "sha256:" + "b" * 64 if mode == "published-image" and status == "pass" else None
            ),
            failure_phase=None if status == "pass" else "startup",
            failure_category=None if status == "pass" else "api_health_timeout",
            tag="main" if mode == "published-image" else None,
        )

    def test_passing_receipt_records_real_elapsed_restart_recovery(self) -> None:
        receipt = self.build(
            soak={"sampling": {"recovered_after_failure": True}, "status": "pass"}
        )

        self.assertEqual(receipt["status"], "pass")
        self.assertTrue(receipt["schedule"]["real_elapsed_time_required"])
        self.assertFalse(receipt["schedule"]["accelerated_clock_used"])
        self.assertTrue(receipt["runtime"]["controlled_restart_completed"])
        self.assertTrue(receipt["runtime"]["recovery_after_failure_observed"])
        self.assertTrue(receipt["runtime"]["pre_restart_session_recovery_completed"])
        self.assertEqual(receipt["runtime"]["source_revision_sha"], "a" * 40)

    def test_blocked_receipt_excludes_raw_failure_output(self) -> None:
        receipt = self.build(mode="published-image", status="blocked")
        serialized = json.dumps(receipt)

        self.assertEqual(receipt["status"], "blocked")
        self.assertFalse(receipt["failure"]["raw_error_included"])
        self.assertFalse(receipt["failure"]["command_output_included"])
        self.assertNotIn("/Users/private", serialized)
        self.assertNotIn("Bearer verification-secret", serialized)

    def test_receipt_file_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "matrix.json"
            matrix.write_receipt(target, self.build(status="blocked"))

            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(target.read_text())["status"], "blocked")

    def test_compose_override_is_used_only_for_published_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("COMPOSE_PROJECT_NAME=fixture\n", encoding="utf-8")
            source = matrix.compose(env_file, "source-build", "ps")
            published = matrix.compose(env_file, "published-image", "ps")

        self.assertNotIn(str(matrix.IMAGE_COMPOSE_FILE), source)
        self.assertIn(str(matrix.IMAGE_COMPOSE_FILE), published)

    def test_published_start_allows_missing_dependency_images_to_pull(self) -> None:
        self.assertEqual(matrix.compose_up_args("source-build"), ["up", "--build", "-d", "api"])
        self.assertEqual(matrix.compose_up_args("published-image"), ["up", "-d", "api"])
        self.assertNotIn("never", matrix.compose_up_args("published-image"))

    def test_image_digest_parser_excludes_repository_reference(self) -> None:
        completed = matrix.subprocess.CompletedProcess(
            [],
            0,
            '["registry.example/private/api@sha256:' + "c" * 64 + '"]\n',
            "",
        )
        with mock.patch.object(matrix, "run_command", return_value=completed):
            digest = matrix.inspect_image_digest("registry.example/private/api:main")

        self.assertEqual(digest, "sha256:" + "c" * 64)


if __name__ == "__main__":
    unittest.main()
