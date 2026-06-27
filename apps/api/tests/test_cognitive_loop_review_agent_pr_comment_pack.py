from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT


REPO_ROOT = ROOT.parents[1]
RECEIPT_CLI = REPO_ROOT / "scripts" / "cognitive_loop_review_agent_receipt.py"
COMMENT_CLI = REPO_ROOT / "scripts" / "cognitive_loop_review_agent_pr_comment.py"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_cognitive_loop_review_agent_pr_comment_pack.py"
REPORT_FIXTURES = REPO_ROOT / "fixtures" / "review-agent"
BAD_COMMENT_PACK = REPO_ROOT / "fixtures" / "review-agent-pr-comments" / "raw-diff-leak.json"


class CognitiveLoopReviewAgentPrCommentPackTests(unittest.TestCase):
    def build_receipt(self, tmp: Path) -> Path:
        receipt_path = tmp / "receipt.json"
        subprocess.run(
            [
                sys.executable,
                str(RECEIPT_CLI),
                "build",
                "--report",
                str(REPORT_FIXTURES / "needs-review.json"),
                "--provider-id",
                "ci-fixture-review-agent",
                "--provider-label",
                "CI fixture Review Agent",
                "--execution-surface",
                "ci",
                "--pr-ref",
                "PR-149",
                "--commit-sha",
                "61f9424d74d721b5bd0a6b139be8268c47fbfe72",
                "--base-ref",
                "main",
                "--head-ref",
                "codex/review-agent-pr-comment-pack",
                "--generated-at",
                "2026-06-18T00:00:00+00:00",
                "--output",
                str(receipt_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        return receipt_path

    def test_comment_pack_cli_builds_bilingual_metadata_only_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-pr-comment-") as tmp_name:
            tmp = Path(tmp_name)
            receipt_path = self.build_receipt(tmp)
            comment_path = tmp / "comment-pack.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(COMMENT_CLI),
                    "build",
                    "--receipt",
                    str(receipt_path),
                    "--generated-at",
                    "2026-06-18T00:00:00+00:00",
                    "--output",
                    str(comment_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            )
            pack = json.loads(comment_path.read_text(encoding="utf-8"))

        self.assertIn("cognitive-loop-review-agent-pr-comment-pack-v1", completed.stdout)
        self.assertEqual(pack["status"], "pass")
        self.assertEqual(pack["decision_summary"]["decision"], "needs-review")
        self.assertEqual(pack["checks_summary"]["conclusion"], "neutral")
        self.assertIn("Decision:", pack["comments"]["markdown_en"])
        self.assertIn("决策：", pack["comments"]["markdown_zh"])
        self.assertIn("needs-review", pack["decision_summary"]["labels_to_add"])
        serialized = json.dumps(pack, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("diff --git", serialized)
        self.assertNotIn("subprocess.run(user_command", serialized)
        self.assertFalse(pack["privacy"]["raw_diff_included"])
        self.assertFalse(pack["privacy"]["finding_evidence_included"])
        self.assertFalse(pack["privacy"]["report_summary_included"])

    def test_comment_pack_cli_rejects_raw_diff_leak(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(COMMENT_CLI),
                "validate",
                "--comment-pack",
                str(BAD_COMMENT_PACK),
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("diff --git", completed.stderr)

    def test_pr_comment_pack_verifier_generates_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-pr-comment-pack-") as tmp_name:
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

        self.assertIn("cognitive-loop-review-agent-pr-comment-pack-verification-v1", completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["comment_pack_count"], 3)
        self.assertEqual(
            set(report["quality_gates"]["decision_path_coverage"]),
            {"approved", "needs-review", "needs-fix"},
        )
        self.assertEqual(
            set(report["quality_gates"]["checks_conclusion_coverage"]),
            {"success", "neutral", "failure"},
        )
        self.assertEqual(report["quality_gates"]["bilingual_markdown_comments"], "pass")
        self.assertEqual(report["quality_gates"]["privacy_leak_rejection"], "pass")


if __name__ == "__main__":
    unittest.main()
