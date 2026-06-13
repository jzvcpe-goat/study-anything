from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "launch_self_host.sh"
PUBLISHED_IMAGE_SCRIPT = REPO_ROOT / "scripts" / "verify_published_image_launch.py"


class SelfHostLaunchTests(unittest.TestCase):
    def run_launch_process(self, **overrides: str) -> tuple[subprocess.CompletedProcess[str], str]:
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
            commands = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
            return completed, commands

    def run_launch(self, **overrides: str) -> str:
        completed, commands = self.run_launch_process(**overrides)
        if completed.returncode != 0:
            self.fail(
                f"launch_self_host.sh exited {completed.returncode}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        return completed.stdout + "\n--- commands ---\n" + commands

    @staticmethod
    def write_stub(path: Path, body: str) -> None:
        path.write_text("#!/usr/bin/env sh\n" + textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(0o755)

    def test_default_launch_builds_from_source(self) -> None:
        output = self.run_launch(ALLOW_NON_ASCII_DOCKER_BUILD="true")
        self.assertIn("Building Study Anything API image from this source checkout.", output)
        self.assertIn(
            "docker compose --env-file .env -f infra/compose/docker-compose.yml up -d --build",
            output,
        )
        self.assertNotIn("docker pull", output)
        self.assertNotIn("docker-compose.images.yml", output)

    def test_published_launch_pulls_images_sequentially_without_building(self) -> None:
        output = self.run_launch(USE_PUBLISHED_IMAGES="true")
        api_pull = (
            "docker pull "
            "ghcr.io/jzvcpe-goat/study-anything/api:v0.3.16-alpha"
        )
        self.assertIn(api_pull, output)
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
        )
        self.assertIn("docker pull registry.example/study-api:test", output)
        self.assertIn("--profile smoke up -d", output)

    def test_published_launch_can_use_cached_images_without_pull(self) -> None:
        output = self.run_launch(
            USE_PUBLISHED_IMAGES="true",
            PULL_PUBLISHED_IMAGES="false",
        )
        self.assertIn("Skipping published image pulls because PULL_PUBLISHED_IMAGES=false.", output)
        self.assertNotIn("docker pull", output)

    def test_non_ascii_source_path_has_actionable_diagnostic(self) -> None:
        completed, commands = self.run_launch_process(
            STUDY_ANYTHING_DOCKER_SOURCE_PATH="/tmp/学习系统"
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("checkout path contains non-ASCII characters", completed.stderr)
        self.assertIn("USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn(
            "ALLOW_NON_ASCII_DOCKER_BUILD=true ./scripts/launch_self_host.sh",
            completed.stderr,
        )
        self.assertNotIn("docker compose", commands)


class PublishedImageLaunchTests(unittest.TestCase):
    def _module(self):
        spec = spec_from_file_location("verify_published_image_launch", PUBLISHED_IMAGE_SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_default_expected_versions_accepts_raw_and_normalized_alpha_tag(self) -> None:
        module = self._module()

        self.assertEqual(
            module.default_expected_versions("v0.2.16-alpha"),
            {"0.2.16-alpha", "0.2.16a0"},
        )
        self.assertEqual(
            module.default_expected_versions("0.2.16-alpha"),
            {"0.2.16-alpha", "0.2.16a0"},
        )

    def test_pull_timeout_report_is_actionable(self) -> None:
        module = self._module()

        report = module.pull_timeout_report(
            tag="v0.2.16-alpha",
            api_image="ghcr.io/jzvcpe-goat/study-anything/api:v0.2.16-alpha",
            timeout_seconds=3,
            project_name="study_anything_published_test",
            manifest_evidence={
                "status": "ok",
                "platforms": ["linux/amd64", "linux/arm64"],
            },
        )

        self.assertEqual(report["status"], "blocked_by_local_ghcr_pull")
        self.assertIn("docker manifest inspect", report["next_steps"][0])
        self.assertEqual(report["manifest_evidence"]["status"], "ok")
        self.assertIn("GitHub Actions docker-images workflow succeeded", report["fallback_acceptance"]["acceptable_when"][0])


if __name__ == "__main__":
    unittest.main()
