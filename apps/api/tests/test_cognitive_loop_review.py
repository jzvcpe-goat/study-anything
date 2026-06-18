from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT

from study_anything.core.cognitive_loop_contracts import write_default_contract_files
from study_anything.core.cognitive_loop_review import (
    MAX_REVIEW_FINDINGS,
    REVIEW_ARTIFACT_SCHEMA_VERSION,
    CognitiveLoopReviewError,
    ReviewChange,
    build_review_artifact,
    load_pr_summary_changes,
    render_review_artifact_html,
    validate_review_artifact,
)


REPO_ROOT = ROOT.parents[1]


class CognitiveLoopReviewTests(unittest.TestCase):
    def _tmp_root(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory(prefix="study-anything-review-test-")

    def test_review_artifact_is_advisory_and_private(self) -> None:
        with self._tmp_root() as tmp:
            root = Path(tmp)
            write_default_contract_files(root)
            changes = [
                ReviewChange(
                    file_path="apps/api/study_anything/core/auth_guard.py",
                    status="M",
                    diff_ref="git:main...HEAD:apps/api/study_anything/core/auth_guard.py",
                    insertions=12,
                    deletions=2,
                )
            ]

            report = build_review_artifact(
                root,
                changes=changes,
                base_ref="main",
                head_ref="HEAD",
                generated_at="2026-06-18T00:00:00Z",
            )
            html = render_review_artifact_html(report)

        self.assertEqual(report["schema_version"], REVIEW_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(report["review_run"]["security_gate"]["blocking"], False)
        self.assertEqual(report["review_run"]["security_gate"]["merge_blocked"], False)
        self.assertEqual(report["review_run"]["decision"]["merge_blocked"], False)
        self.assertEqual(report["review_run"]["metrics"]["raw_diff_included"], False)
        self.assertEqual(report["review_run"]["metrics"]["file_contents_included"], False)
        self.assertEqual(report["review_run"]["metrics"]["model_keys_stored"], False)
        self.assertEqual(report["privacy"]["agent_endpoints_included"], False)
        self.assertEqual(report["risk_mapping"]["source"], ".cognitive-loop/risk.yaml")
        self.assertIn("Cognitive Loop Code Review", html)
        self.assertIn("Merge Blocked", html)

    def test_fake_reviewer_caps_findings_to_five(self) -> None:
        with self._tmp_root() as tmp:
            root = Path(tmp)
            write_default_contract_files(root)
            changes = [
                ReviewChange(
                    file_path=f"scripts/review_fixture_{index}.py",
                    status="M",
                    diff_ref=f"git:main...HEAD:scripts/review_fixture_{index}.py",
                )
                for index in range(8)
            ]

            report = build_review_artifact(
                root,
                changes=changes,
                base_ref="main",
                head_ref="HEAD",
                generated_at="2026-06-18T00:01:00Z",
            )

        findings = report["review_run"]["findings"]
        self.assertEqual(len(findings), MAX_REVIEW_FINDINGS)
        self.assertTrue(
            all(
                {"file_path", "diff_ref", "risk_level", "confidence", "verification_command"}.issubset(finding)
                for finding in findings
            )
        )

    def test_pr_summary_rejects_raw_diff_fields(self) -> None:
        with self._tmp_root() as tmp:
            root = Path(tmp)
            raw_summary = root / "summary.json"
            raw_summary.write_text(
                json.dumps({"raw_diff": "raw diff body", "changed_files": []}),
                encoding="utf-8",
            )

            with self.assertRaises(CognitiveLoopReviewError):
                load_pr_summary_changes(raw_summary)

    def test_pr_summary_metadata_mode_builds_review_run(self) -> None:
        with self._tmp_root() as tmp:
            root = Path(tmp)
            write_default_contract_files(root)
            summary = root / "summary.json"
            summary.write_text(
                json.dumps(
                    {
                        "changed_files": [
                            {
                                "path": "docs/cognitive-loop-code-review.md",
                                "status": "M",
                                "insertions": 7,
                                "deletions": 1,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            changes = load_pr_summary_changes(summary, base_ref="main", head_ref="feature")
            report = build_review_artifact(
                root,
                changes=changes,
                source="pr_summary",
                base_ref="main",
                head_ref="feature",
                generated_at="2026-06-18T00:02:00Z",
            )

        validate_review_artifact(report)
        self.assertEqual(report["review_run"]["source"], "pr_summary")
        self.assertEqual(report["review_run"]["metrics"]["changed_file_count"], 1)

    def test_cli_generates_json_and_html_for_real_git_diff(self) -> None:
        with self._tmp_root() as tmp:
            root = Path(tmp)
            write_default_contract_files(root)
            (root / "README.md").write_text("# Review CLI test\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.local"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Review Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "branch", "-M", "main"], cwd=root, check=True)
            subprocess.run(["git", "switch", "-c", "feature"], cwd=root, check=True, stdout=subprocess.PIPE)
            target = root / "scripts" / "review_cli_fixture.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("print('fixture')\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "change"], cwd=root, check=True, stdout=subprocess.PIPE)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "cognitive_loop_review.py"),
                    "--root",
                    str(root),
                    "--base",
                    "main",
                    "--head",
                    "HEAD",
                    "--html",
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            )

            json_path = root / ".cognitive-loop" / "events" / "cognitive-loop-review.json"
            html_path = root / ".cognitive-loop" / "artifacts" / "cognitive-loop-review.html"
            report = json.loads(json_path.read_text(encoding="utf-8"))
            html = html_path.read_text(encoding="utf-8")

        self.assertIn("wrote:", completed.stdout)
        self.assertEqual(report["schema_version"], REVIEW_ARTIFACT_SCHEMA_VERSION)
        self.assertIn("Cognitive Loop Code Review", html)
        self.assertFalse(report["review_run"]["security_gate"]["blocking"])


if __name__ == "__main__":
    unittest.main()
