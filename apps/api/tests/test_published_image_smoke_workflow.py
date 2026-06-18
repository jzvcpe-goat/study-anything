from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "published-image-smoke.yml"


class PublishedImageSmokeWorkflowTests(unittest.TestCase):
    def test_workflow_is_strict_remote_runtime_smoke(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("name: published-image-smoke", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("tag:", text)
        self.assertIn("docker manifest inspect", text)
        self.assertIn("scripts/verify_published_image_launch.py", text)
        self.assertIn("--pull-timeout-seconds", text)
        self.assertIn("--timeout", text)
        self.assertNotIn("--allow-pull-timeout-report", text)
        self.assertNotIn("--manifest-only", text)


if __name__ == "__main__":
    unittest.main()
