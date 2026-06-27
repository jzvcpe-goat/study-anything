from __future__ import annotations

import importlib.util
import json
import subprocess
import unittest

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


falkordb_flow = load_script("verify_falkordb_flow")
backup_restore = load_script("verify_backup_restore_drill")


class FullStackVerifierReportTests(unittest.TestCase):
    def test_falkordb_report_classifies_disabled_graph(self) -> None:
        report = falkordb_flow.failure_report(
            RuntimeError("FalkorDB did not become healthy: {'status': 'disabled'}")
        )

        self.assertEqual(report["classification"], "graph_disabled")
        self.assertIn("FALKORDB_ENABLED=true", " ".join(report["next_steps"]))

    def test_falkordb_report_redacts_private_graph_values(self) -> None:
        report = falkordb_flow.failure_report(
            RuntimeError(
                "Private source prose leaked into topology for graph-smoke-user: "
                "Private reading prose must stay outside the graph projection. "
                "The source is projected only through an allowlisted DTO. "
                "path=/Users/example/project token=supersecret123"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "privacy_leak")
        self.assertIn("<private-user>", serialized)
        self.assertIn("<private-source-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("graph-smoke-user", serialized)
        self.assertNotIn("Private reading prose", serialized)
        self.assertNotIn("allowlisted DTO", serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("supersecret123", serialized)

    def test_backup_restore_report_classifies_docker_missing(self) -> None:
        report = backup_restore.failure_report(
            FileNotFoundError("No such file or directory: 'docker'")
        )

        self.assertEqual(report["classification"], "docker_missing")
        self.assertIn("Install Docker", " ".join(report["next_steps"]))

    def test_backup_restore_report_redacts_called_process_output(self) -> None:
        exc = subprocess.CalledProcessError(
            1,
            ["docker", "compose", "--project-name", "study_anything_drill_12345", "up", "-d"],
            output="using /Users/example/project/.env",
            stderr="token=supersecret123 sk-proj-abcdefghijklmnop /tmp/study-anything-restore-drill-abc",
        )
        report = backup_restore.failure_report(exc)
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "docker_compose_up_failed")
        self.assertIn("<compose-project>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("<temp-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertIn("sk-<redacted>", serialized)
        self.assertNotIn("study_anything_drill_12345", serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("/tmp/study-anything", serialized)
        self.assertNotIn("supersecret123", serialized)

    def test_backup_restore_cli_failure_is_actionable_and_redacted(self) -> None:
        report = backup_restore.failure_report(
            RuntimeError(
                "Docker daemon failed at /Users/example/project/.env "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop"
            )
        )
        message = backup_restore.format_cli_failure(report)

        self.assertIn("verify_backup_restore_drill failed:", message)
        self.assertIn(f"classification: {report['classification']}", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("python3 scripts/verify_backup_restore_drill.py --no-build", message)
        self.assertIn("<local-path>", message)
        self.assertIn("Authorization: Bearer sk-<redacted>", message)
        self.assertNotIn("/Users/example", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop", message)


if __name__ == "__main__":
    unittest.main()
