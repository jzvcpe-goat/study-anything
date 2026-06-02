from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "launch_self_host.sh"


class SelfHostLaunchTests(unittest.TestCase):
    def run_launch(self, **overrides: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (root / ".env").write_text("APP_ENV=development\n", encoding="utf-8")
            log_file = root / "commands.log"

            self.write_stub(
                bin_dir / "docker",
                """
                printf 'docker %s\\n' "$*" >> "$LOG_FILE"
                exit 0
                """,
            )
            self.write_stub(bin_dir / "curl", "exit 0")
            self.write_stub(
                bin_dir / "python3",
                """
                printf 'python3 %s\\n' "$*" >> "$LOG_FILE"
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "LOG_FILE": str(log_file),
                }
            )
            env.update(overrides)
            completed = subprocess.run(
                ["sh", str(SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                self.fail(
                    f"launch_self_host.sh exited {completed.returncode}\n"
                    f"stdout:\n{completed.stdout}\n"
                    f"stderr:\n{completed.stderr}"
                )
            return completed.stdout + "\n--- commands ---\n" + log_file.read_text(encoding="utf-8")

    @staticmethod
    def write_stub(path: Path, body: str) -> None:
        path.write_text("#!/usr/bin/env sh\n" + textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(0o755)

    def test_default_launch_builds_from_source(self) -> None:
        output = self.run_launch()
        self.assertIn("Building Study Anything API and Web images from this source checkout.", output)
        self.assertIn(
            "docker compose --env-file .env -f infra/compose/docker-compose.yml up -d --build",
            output,
        )
        self.assertNotIn("docker pull", output)
        self.assertNotIn("docker-compose.images.yml", output)

    def test_published_launch_pulls_images_sequentially_without_building(self) -> None:
        output = self.run_launch(USE_PUBLISHED_IMAGES="true")
        api_pull = (
            "docker pull --quiet "
            "ghcr.io/jzvcpe-goat/study-anything/api:v0.2.1-alpha"
        )
        web_pull = (
            "docker pull --quiet "
            "ghcr.io/jzvcpe-goat/study-anything/web:v0.2.1-alpha"
        )
        self.assertLess(output.index(api_pull), output.index(web_pull))
        self.assertIn(
            "docker compose --env-file .env -f infra/compose/docker-compose.yml "
            "-f infra/compose/docker-compose.images.yml up -d",
            output,
        )
        self.assertNotIn("up -d --build", output)

    def test_published_launch_accepts_image_overrides_and_profile(self) -> None:
        output = self.run_launch(
            USE_PUBLISHED_IMAGES="yes",
            STACK_PROFILE="smoke",
            STUDY_ANYTHING_API_IMAGE="registry.example/study-api:test",
            STUDY_ANYTHING_WEB_IMAGE="registry.example/study-web:test",
        )
        self.assertIn("docker pull --quiet registry.example/study-api:test", output)
        self.assertIn("docker pull --quiet registry.example/study-web:test", output)
        self.assertIn("--profile smoke up -d", output)

    def test_published_launch_can_use_cached_images_without_pull(self) -> None:
        output = self.run_launch(
            USE_PUBLISHED_IMAGES="true",
            PULL_PUBLISHED_IMAGES="false",
        )
        self.assertIn("Skipping published image pulls because PULL_PUBLISHED_IMAGES=false.", output)
        self.assertNotIn("docker pull", output)


if __name__ == "__main__":
    unittest.main()
