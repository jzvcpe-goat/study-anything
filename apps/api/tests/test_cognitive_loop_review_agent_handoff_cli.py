from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT


REPO_ROOT = ROOT.parents[1]
CLI = REPO_ROOT / "scripts" / "cognitive_loop_review_agent_handoff.py"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_cognitive_loop_review_agent_handoff_cli.py"
FIXTURE_DIR = REPO_ROOT / "fixtures" / "review-agent"


def run(args: list[str], *, cwd: Path, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if expect_success and completed.returncode != 0:
        raise AssertionError(f"Command failed: {args}\nstdout={completed.stdout}\nstderr={completed.stderr}")
    if not expect_success and completed.returncode == 0:
        raise AssertionError(f"Command unexpectedly passed: {args}")
    return completed


def init_temp_repo(root: Path) -> None:
    run(["git", "init", "-q"], cwd=root)
    run(["git", "config", "user.email", "review-agent@example.invalid"], cwd=root)
    run(["git", "config", "user.name", "Review Agent Fixture"], cwd=root)
    source = root / "lesson.py"
    source.write_text("def label(value):\n    return str(value)\n", encoding="utf-8")
    run(["git", "add", "lesson.py"], cwd=root)
    run(["git", "commit", "-q", "-m", "base"], cwd=root)
    source.write_text("def label(value):\n    if value is None:\n        return 'missing'\n    return str(value)\n", encoding="utf-8")


class CognitiveLoopReviewAgentHandoffCliTests(unittest.TestCase):
    def test_prepare_outputs_ephemeral_request_with_diff(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-handoff-test-") as tmp:
            repo = Path(tmp)
            init_temp_repo(repo)
            completed = run(
                [
                    sys.executable,
                    str(CLI),
                    "prepare",
                    "--root",
                    str(repo),
                    "--pr-id",
                    "unit-pr",
                    "--title",
                    "Unit handoff",
                ],
                cwd=REPO_ROOT,
            )
            request = json.loads(completed.stdout)

        self.assertEqual(request["schema_version"], "cognitive-loop-review-agent-handoff-request-v1")
        self.assertIn("diff --git", request["review_input"]["git_diff"])
        self.assertEqual(request["review_input"]["changed_files"], ["lesson.py"])
        self.assertFalse(request["privacy_boundary"]["study_anything_may_persist_raw_diff"])
        self.assertFalse(request["privacy_boundary"]["safe_to_commit"])

    def test_prepare_refuses_repo_output_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-handoff-test-") as tmp:
            repo = Path(tmp)
            init_temp_repo(repo)
            completed = run(
                [
                    sys.executable,
                    str(CLI),
                    "prepare",
                    "--root",
                    str(repo),
                    "--output-dir",
                    str(repo / "handoff"),
                ],
                cwd=REPO_ROOT,
                expect_success=False,
            )

        self.assertIn("Refusing to write raw-diff handoff material", completed.stderr)

    def test_validate_accepts_and_rejects_review_agent_reports(self) -> None:
        accepted = run(
            [
                sys.executable,
                str(CLI),
                "validate",
                "--report",
                str(FIXTURE_DIR / "needs-review.json"),
            ],
            cwd=REPO_ROOT,
        )
        accepted_summary = json.loads(accepted.stdout)
        self.assertEqual(accepted_summary["status"], "pass")
        self.assertEqual(accepted_summary["report_summary"]["decision"], "needs-review")
        self.assertTrue(accepted_summary["privacy"]["validation_summary_safe_to_store"])

        rejected = run(
            [
                sys.executable,
                str(CLI),
                "validate",
                "--report",
                str(FIXTURE_DIR / "invalid-low-confidence-final.json"),
            ],
            cwd=REPO_ROOT,
            expect_success=False,
        )
        self.assertIn("final finding confidence", rejected.stderr)

    def test_handoff_cli_verifier_generates_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-handoff-report-") as tmp:
            output = Path(tmp) / "report.json"
            completed = run(
                [
                    sys.executable,
                    str(VERIFY_SCRIPT),
                    "--write",
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
            )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertIn("cognitive-loop-review-agent-handoff-cli-v1", completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["prepare"]["repo_output_default_refusal"], "pass")
        self.assertFalse(report["privacy"]["raw_diff_written_to_platform_generated"])
        self.assertEqual(report["validate"]["invalid_low_confidence_rejected"], "pass")


if __name__ == "__main__":
    unittest.main()
