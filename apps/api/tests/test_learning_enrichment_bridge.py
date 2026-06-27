from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from _path import ROOT  # noqa: F401


REPO = ROOT.parents[1]
SCRIPT = REPO / "scripts" / "verify_learning_enrichment_bridge.py"
PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
SPEC = importlib.util.spec_from_file_location("verify_learning_enrichment_bridge", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
learning_enrichment_bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(learning_enrichment_bridge)


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


class LearningEnrichmentBridgeTests(unittest.TestCase):
    def test_python_version_error_payload_is_machine_readable(self) -> None:
        payload = learning_enrichment_bridge.python_version_error_payload("3.9.6")

        self.assertEqual(payload["schema_version"], "learning-enrichment-bridge-error-v1")
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["python_version"], "3.9.6")
        self.assertIn(".venv/bin/python", " ".join(payload["next_steps"]))
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secrets_recorded"])

    def test_python_version_preflight_prints_json_before_api_imports(self) -> None:
        stderr = io.StringIO()

        with (
            patch.object(learning_enrichment_bridge.sys, "version_info", (3, 9, 6)),
            patch.object(learning_enrichment_bridge.sys, "version", "3.9.6 test"),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as raised:
                learning_enrichment_bridge.ensure_supported_python()

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["python_version"], "3.9.6")

    def test_source_tree_report_covers_operator_bridge(self) -> None:
        completed = run_script()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "learning-enrichment-bridge-verification-v1")
        self.assertEqual(report["version"], "v0.3.29-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            set(report["context_contract"]["source_types"]),
            {"app_context", "document", "markdown_note", "obsidian_note", "video_slice", "web"},
        )
        self.assertFalse(report["context_contract"]["public_dict_includes_text"])
        html = report["exports"]["html_artifact"]
        self.assertEqual(html["article_schema"], "learning-enrichment-artifact-v1")
        self.assertFalse(html["contains_script_tag"])
        self.assertIn("Source Map", html["headings"])
        self.assertEqual(report["exports"]["notebooklm_bridge"]["manual_steps"], 4)
        self.assertFalse(report["exports"]["notebooklm_bridge"]["official_notebooklm_api_required"])
        self.assertFalse(report["privacy_assertions"]["learner_answers_in_strict_handoff"])
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])

    def test_report_is_current_after_pack_generation(self) -> None:
        completed = run_script("--check")

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_pack_report_validates_copy_ready_bridge_assets(self) -> None:
        completed = run_script("--pack", str(PACK))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["adoption_pack"]["included"])
        self.assertEqual(report["adoption_pack"]["version"], "v0.3.29-alpha")

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "scripts").mkdir()
            completed = run_script("--pack-root", str(root))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Required bridge asset is missing", completed.stderr)
        self.assertIn("Next steps:", completed.stderr)

    def test_extracted_pack_contains_bridge_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-bridge-pack-test-") as tmp:
            with zipfile.ZipFile(PACK) as archive:
                archive.extractall(tmp)
            pack_root = Path(tmp) / "study-anything-platform-adoption-pack"
            manifest = json.loads((pack_root / "manifest.json").read_text(encoding="utf-8"))

        paths = {item["path"] for item in manifest["files"]}
        self.assertIn("scripts/verify_learning_enrichment_bridge.py", paths)
        self.assertIn("platform/generated/study-anything-learning-enrichment-bridge.json", paths)
        self.assertIn(
            "learning-enrichment-bridge-verification-v1",
            manifest["acceptance"]["must_verify"],
        )

    def test_cli_failure_formatter_is_actionable_and_redacted(self) -> None:
        message = learning_enrichment_bridge.format_cli_failure(
            RuntimeError(
                "learning enrichment fixture failed at /private/tmp/study-anything/enrichment.json "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            )
        )

        self.assertIn("verify_learning_enrichment_bridge failed", message)
        self.assertIn("Next steps:", message)
        self.assertIn("verify_learning_enrichment_bridge.py --write", message)
        self.assertIn("verify_learning_enrichment_bridge.py --check", message)
        self.assertIn("generate_platform_adoption_pack.py", message)
        self.assertIn("docs/learning-enrichment.md", message)
        self.assertIn("docs/notebooklm-bridge.md", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/tmp", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)


if __name__ == "__main__":
    unittest.main()
