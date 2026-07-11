from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[3]
CONSUMER = ROOT / "conformance" / "python" / "cbb_v1_consumer.py"
SUMMARY = ROOT / "platform" / "generated" / "study-anything-cbb-v1-conformance-pack.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-v1-external-consumer.json"
ARCHIVE = ROOT / "platform" / "generated" / "study-anything-cbb-v1-conformance-pack.zip"


class CbbV1ConformanceTests(unittest.TestCase):
    def run_check(self, script: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed

    def test_conformance_pack_is_current(self) -> None:
        self.run_check("generate_cbb_v1_conformance_pack.py")
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        self.assertEqual(summary["schema_count"], 8)
        self.assertEqual(summary["vector_counts"]["kernel"], 7)
        self.assertEqual(summary["vector_counts"]["provenance"], 12)
        self.assertEqual(summary["vector_counts"]["outcomes"], 5)
        self.assertEqual(summary["vector_counts"]["evolution"], 6)
        self.assertFalse(summary["study_anything_runtime_required_by_consumer"])

    def test_independent_consumer_verifier_passes(self) -> None:
        self.run_check("verify_cbb_v1_external_consumer.py")
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pass")
        self.assertFalse(report["consumer"]["study_anything_imported"])
        self.assertTrue(report["checks"]["tampered_pack_fails_closed"])
        self.assertTrue(report["checks"]["consumer_rejects_authority_extensions"])

    def test_consumer_has_no_reference_package_or_network_import(self) -> None:
        tree = ast.parse(CONSUMER.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse(
            imports.intersection(
                {
                    "httpx",
                    "openai",
                    "pydantic",
                    "requests",
                    "socket",
                    "study_anything",
                    "subprocess",
                    "urllib",
                }
            )
        )

    def test_archive_is_single_root_and_contains_no_private_key(self) -> None:
        with zipfile.ZipFile(ARCHIVE) as archive:
            names = archive.namelist()
            self.assertEqual({name.split("/", 1)[0] for name in names}, {"delivery-clearance-cbb-v1-conformance"})
            self.assertFalse(any("private_key" in name.lower() for name in names))
            self.assertFalse(any(name.endswith((".pem", ".key")) for name in names))
            self.assertEqual(len(names), json.loads(SUMMARY.read_text())["archive_entry_count"])


if __name__ == "__main__":
    unittest.main()
