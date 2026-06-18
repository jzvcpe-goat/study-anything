from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT


REPO_ROOT = ROOT.parents[1]
BUNDLE_CLI = REPO_ROOT / "scripts" / "cognitive_loop_review_agent_acceptance_bundle.py"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_cognitive_loop_review_agent_acceptance_bundle.py"
REPORT_FIXTURES = REPO_ROOT / "fixtures" / "review-agent"
BAD_BUNDLE = REPO_ROOT / "fixtures" / "review-agent-acceptance-bundles" / "raw-diff-leak"


class CognitiveLoopReviewAgentAcceptanceBundleTests(unittest.TestCase):
    def test_acceptance_bundle_cli_builds_metadata_only_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-acceptance-") as tmp_name:
            output_dir = Path(tmp_name) / "bundle"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(BUNDLE_CLI),
                    "build",
                    "--report",
                    str(REPORT_FIXTURES / "needs-fix.json"),
                    "--output-dir",
                    str(output_dir),
                    "--provider-id",
                    "ci-fixture-review-agent",
                    "--provider-label",
                    "CI fixture Review Agent",
                    "--execution-surface",
                    "ci",
                    "--pr-ref",
                    "PR-150",
                    "--commit-sha",
                    "f59614c1dece86a27b739631bde5050cd529b9a8",
                    "--base-ref",
                    "main",
                    "--head-ref",
                    "codex/review-agent-acceptance-bundle",
                    "--generated-at",
                    "2026-06-18T00:00:00+00:00",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            )
            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            summary = (output_dir / "SUMMARY.md").read_text(encoding="utf-8")
            for filename in (
                "manifest.json",
                "SUMMARY.md",
                "review-agent-ci-receipt.json",
                "review-agent-pr-comment-pack.json",
            ):
                self.assertTrue((output_dir / filename).is_file(), filename)

        self.assertIn("cognitive-loop-review-agent-acceptance-bundle-v1", completed.stdout)
        self.assertEqual(manifest["status"], "pass")
        self.assertEqual(manifest["decision_summary"]["decision"], "needs-fix")
        self.assertTrue(manifest["decision_summary"]["should_block_merge"])
        self.assertIn("Decision:", summary)
        self.assertIn("Privacy:", summary)
        serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True) + summary
        self.assertNotIn("diff --git", serialized)
        self.assertNotIn("subprocess.run(user_command", serialized)
        self.assertFalse(manifest["privacy"]["raw_diff_included"])
        self.assertFalse(manifest["privacy"]["raw_handoff_material_written"])
        self.assertFalse(manifest["privacy"]["report_summary_included"])

    def test_acceptance_bundle_cli_rejects_raw_diff_manifest(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(BUNDLE_CLI),
                "validate",
                "--bundle-dir",
                str(BAD_BUNDLE),
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("diff --git", completed.stderr)

    def test_acceptance_bundle_verifier_generates_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-acceptance-report-") as tmp_name:
            output = Path(tmp_name) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY_SCRIPT),
                    "--write",
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertIn("cognitive-loop-review-agent-acceptance-bundle-verification-v1", completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["bundle_count"], 3)
        self.assertEqual(
            set(report["quality_gates"]["decision_path_coverage"]),
            {"approved", "needs-review", "needs-fix"},
        )
        self.assertEqual(report["quality_gates"]["metadata_only_bundle"], "pass")
        self.assertEqual(report["quality_gates"]["privacy_leak_rejection"], "pass")


if __name__ == "__main__":
    unittest.main()
