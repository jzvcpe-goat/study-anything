from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = ROOT.parents[1]
SCRIPT = REPO / "scripts" / "verify_agent_eval_marketplace_enforcement.py"
PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )


class AgentEvalMarketplaceEnforcementTests(unittest.TestCase):
    def test_source_tree_report_covers_external_judge_enforcement(self) -> None:
        completed = run_script()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "agent-eval-marketplace-enforcement-v1")
        self.assertEqual(report["version"], "v0.3.30-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["runner_contract"]["required_flag_blocks_non_ok"])
        self.assertTrue(report["runner_contract"]["timeout_flag_present"])
        promptfoo = report["runtime_diagnostics"]["promptfoo_missing_runtime"]
        self.assertEqual(promptfoo["optional_status"], "skipped")
        self.assertTrue(promptfoo["required_exit_nonzero"])
        adapter_ids = {item["adapter_id"] for item in report["external_judge_contracts"]}
        self.assertEqual(adapter_ids, {"promptfoo", "deepeval", "langchain-agentevals", "ragas"})
        self.assertFalse(
            report["privacy_assertions"]["real_model_or_judge_keys_stored_by_study_anything"]
        )
        self.assertFalse(report["privacy_assertions"]["judge_api_keys_in_report"])
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])
        serialized = json.dumps(report)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("Private answer:", serialized)
        self.assertNotIn("OPENAI_API_KEY=", serialized)

    def test_report_is_current_after_pack_generation(self) -> None:
        completed = run_script("--check")

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_pack_report_validates_copy_ready_enforcement_assets(self) -> None:
        completed = run_script("--pack", str(PACK))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["adoption_pack"]["included"])
        self.assertEqual(report["adoption_pack"]["version"], "v0.3.30-alpha")
        self.assertEqual(
            report["runtime_diagnostics"]["promptfoo_missing_runtime"]["optional_status"],
            "not_run_against_pack",
        )

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "scripts").mkdir()
            completed = run_script("--pack-root", str(root))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Required Agent eval enforcement asset is missing", completed.stderr)

    def test_extracted_pack_contains_enforcement_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-agent-eval-pack-test-") as tmp:
            with zipfile.ZipFile(PACK) as archive:
                archive.extractall(tmp)
            pack_root = Path(tmp) / "study-anything-platform-adoption-pack"
            manifest = json.loads((pack_root / "manifest.json").read_text(encoding="utf-8"))

        paths = {item["path"] for item in manifest["files"]}
        self.assertIn("scripts/verify_agent_eval_marketplace_enforcement.py", paths)
        self.assertIn(
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            paths,
        )
        self.assertIn(
            "agent-eval-marketplace-enforcement-v1",
            manifest["acceptance"]["must_verify"],
        )


if __name__ == "__main__":
    unittest.main()
