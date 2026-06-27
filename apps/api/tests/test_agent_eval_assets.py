from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "verify_agent_eval_assets.py"

sys.path.insert(0, str(REPO / "scripts"))
SPEC = importlib.util.spec_from_file_location("verify_agent_eval_assets", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
agent_eval_assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent_eval_assets)


class AgentEvalAssetsVerifierTests(unittest.TestCase):
    def test_runtime_failure_payload_classifies_python_version(self) -> None:
        payload = agent_eval_assets.runtime_failure_payload(
            classification="python_version_unsupported",
            diagnostic=(
                "verify_agent_eval_assets requires Python 3.11 at "
                "/Users/james/private/repo with Authorization: Bearer "
                "sk-proj-abcdefghijklmnop123456"
            ),
            details={"python_version": "3.9.6"},
        )
        serialized = str(payload)

        self.assertEqual(payload["schema_version"], "agent-eval-assets-error-v1")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertIn(".venv/bin/python scripts/verify_agent_eval_assets.py", payload["next_steps"])
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secrets_recorded"])
        self.assertIn("<local-path>", serialized)
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertNotIn("/Users/james", serialized)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", serialized)

    def test_cli_failure_formatter_is_actionable_and_redacted(self) -> None:
        message = agent_eval_assets.format_cli_failure(
            RuntimeError(
                "eval asset drift at /private/tmp/study-anything/eval.json "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            )
        )

        self.assertIn("verify_agent_eval_assets failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("verify_agent_eval_assets.py", message)
        self.assertIn("verify_agent_eval_baseline.py", message)
        self.assertIn("generate_platform_agent_assets.py --check", message)
        self.assertIn("docs/agent-eval.md", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/tmp", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)


if __name__ == "__main__":
    unittest.main()
