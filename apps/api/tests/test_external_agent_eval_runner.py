from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _path import ROOT  # noqa: F401


class ExternalAgentEvalRunnerTests(unittest.TestCase):
    def test_promptfoo_runner_invokes_pinned_external_tool(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            log_path = tmp / "npx-args.json"
            fake_npx = tmp / "npx"
            fake_npx.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                f"open({str(log_path)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
                "print('fake promptfoo ok')\n",
                encoding="utf-8",
            )
            fake_npx.chmod(fake_npx.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{tmp}{os.pathsep}{env.get('PATH', '')}"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[3]
                        / "scripts"
                        / "run_external_agent_evals.py"
                    ),
                    "--tool",
                    "promptfoo",
                    "--api-base",
                    "http://127.0.0.1:8000",
                    "--session-id",
                    "session-for-promptfoo",
                    "--required",
                    "--timeout-seconds",
                    "10",
                ],
                cwd=Path(__file__).resolve().parents[3],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["status"], "ok")
            args = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertIn("promptfoo@0.121.15", args)
            self.assertIn("evals/promptfoo/agent-eval-artifact.yaml", args)
            self.assertIn("apiBase=http://127.0.0.1:8000", args)
            self.assertIn("sessionId=session-for-promptfoo", args)


if __name__ == "__main__":
    unittest.main()
