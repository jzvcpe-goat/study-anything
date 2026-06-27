from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = ROOT.parents[1]
VERIFIER_PATH = REPO / "scripts" / "verify_importer_runtime_retrieval_flow.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_importer_runtime_retrieval_flow",
    VERIFIER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class ImporterRuntimeRetrievalVerifierTests(unittest.TestCase):
    def test_failure_formatter_is_actionable_and_redacted(self) -> None:
        local_home = "/Users/" + "james"
        secret = "sk-" + "proj-private-importer-token"
        message = verifier.format_cli_failure(
            verifier.VerificationError(
                f"Cannot reach {local_home}/importer api_key={secret}"
            )
        )

        self.assertIn("verify_importer_runtime_retrieval_flow failed:", message)
        self.assertIn("classification: api_unreachable", message)
        self.assertIn("Next steps:", message)
        self.assertIn("STUDY_ANYTHING_RETRIEVAL_BACKEND=memory", message)
        self.assertIn("launch_skill_mode.sh", message)
        self.assertNotIn(local_home, message)
        self.assertNotIn(secret, message)
        self.assertIn("<redacted>", message)

    def test_failure_report_classifies_retrieval_unhealthy(self) -> None:
        report = verifier.failure_report(
            verifier.VerificationError(
                "Retrieval is not healthy. For local smoke, start the API with "
                "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory; for full stack, enable LanceDB."
            )
        )

        self.assertEqual(report["classification"], "retrieval_unhealthy")
        self.assertIn("STUDY_ANYTHING_RETRIEVAL_BACKEND=memory", " ".join(report["next_steps"]))
        self.assertFalse(report["privacy"]["real_model_keys_included"])

    def test_failure_report_redacts_default_learning_inputs(self) -> None:
        local_home = "/Users/" + "example"
        report = verifier.failure_report(
            verifier.VerificationError(
                "Lesson did not complete for importer-runtime-retrieval-smoke-user with "
                "AI product learning improves when a learner connects overall product intent, "
                "technical vocabulary, source evidence, feedback, and spaced review. "
                "The lesson connects source evidence to feedback and review. "
                f"path={local_home}/project token=supersecret123"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "learning_flow_incomplete")
        self.assertIn("<private-user>", serialized)
        self.assertIn("<private-source-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("importer-runtime-retrieval-smoke-user", serialized)
        self.assertNotIn("AI product learning improves", serialized)
        self.assertNotIn("The lesson connects source evidence", serialized)
        self.assertNotIn(local_home, serialized)
        self.assertNotIn("supersecret123", serialized)


if __name__ == "__main__":
    unittest.main()
