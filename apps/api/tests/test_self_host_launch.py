from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "launch_self_host.sh"
SKILL_MODE_SCRIPT = REPO_ROOT / "scripts" / "launch_skill_mode.sh"
DOCTOR_SCRIPT = REPO_ROOT / "scripts" / "doctor.sh"
STOP_SKILL_MODE_SCRIPT = REPO_ROOT / "scripts" / "stop_skill_mode.sh"
STOP_SELF_HOST_SCRIPT = REPO_ROOT / "scripts" / "stop_self_host.sh"
RUN_SKILL_MODE_DEMO_SCRIPT = REPO_ROOT / "scripts" / "run_skill_mode_demo.sh"
PUBLISHED_IMAGE_SCRIPT = REPO_ROOT / "scripts" / "verify_published_image_launch.py"
BACKUP_RESTORE_SCRIPT = REPO_ROOT / "scripts" / "verify_backup_restore_drill.py"


class SelfHostLaunchTests(unittest.TestCase):
    def run_launch_process(
        self,
        env_content: str = "APP_ENV=development\n",
        **overrides: str,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (root / ".env").write_text(env_content, encoding="utf-8")
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

    def run_doctor_process(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env"
            env_file.write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(bin_dir / "python3", "exit 0")
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "Docker Compose version v2.27.0\\n"
                  exit 0
                fi
                case "$*" in
                  *" config") exit 0 ;;
                esac
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ENV_FILE": str(env_file),
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            env.update(overrides)
            return subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

    def test_default_launch_builds_from_source(self) -> None:
        output = self.run_launch(ALLOW_NON_ASCII_DOCKER_BUILD="true")
        self.assertIn("Building Study Anything API image from this source checkout.", output)
        self.assertIn(
            "docker compose --env-file .env -f infra/compose/docker-compose.yml up -d --build",
            output,
        )
        self.assertNotIn("docker pull", output)
        self.assertNotIn("docker-compose.images.yml", output)
        self.assertIn("Next steps:", output)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:8000 health", output)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:8000 demo", output)
        self.assertIn("AGENT_GATEWAY_MODE=dry_run", output)
        self.assertIn("agent-add-http --set-default", output)

    def test_published_launch_pulls_images_sequentially_without_building(self) -> None:
        output = self.run_launch(USE_PUBLISHED_IMAGES="true")
        api_pull = (
            "docker pull "
            "ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha"
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

    def test_self_host_success_uses_configured_api_port_in_next_steps(self) -> None:
        output = self.run_launch(ALLOW_NON_ASCII_DOCKER_BUILD="true", API_PORT="18080")

        self.assertIn("API health:http://127.0.0.1:18080/v1/health", output)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:18080 health", output)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:18080 demo", output)

    def test_self_host_success_uses_env_file_api_port_in_health_and_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env.custom"
            env_file.write_text(
                'APP_ENV=development\nexport API_PORT="18081" # local override\n',
                encoding="utf-8",
            )
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
                    "ENV_FILE": str(env_file),
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            commands = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
            output = completed.stdout + "\n--- commands ---\n" + commands

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Waiting for Study Anything API at http://127.0.0.1:18081/v1/health", output)
        self.assertIn("API health:http://127.0.0.1:18081/v1/health", output)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:18081 health", output)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:18081 demo", output)
        self.assertIn(f"python3 scripts/check_env.py --env {env_file}", commands)
        self.assertIn(f"docker compose --env-file {env_file}", commands)
        self.assertNotIn("http://127.0.0.1:8000/v1/health", output)

    def test_invalid_self_host_api_port_fails_before_docker_with_recovery_hint(self) -> None:
        completed, commands = self.run_launch_process(
            ALLOW_NON_ASCII_DOCKER_BUILD="true",
            API_PORT="not-a-port",
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Invalid API_PORT=not-a-port for self-host launch", completed.stderr)
        self.assertIn("API_PORT must be a number from 1 to 65535", completed.stderr)
        self.assertIn("unset API_PORT && ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("API_PORT=8012 ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertNotIn("docker ", commands)

    def test_invalid_app_postgres_port_fails_before_docker_with_recovery_hint(self) -> None:
        completed, commands = self.run_launch_process(
            ALLOW_NON_ASCII_DOCKER_BUILD="true",
            APP_POSTGRES_PORT="not-a-port",
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Invalid APP_POSTGRES_PORT=not-a-port for App Postgres", completed.stderr)
        self.assertIn("APP_POSTGRES_PORT must be a number from 1 to 65535", completed.stderr)
        self.assertIn("unset APP_POSTGRES_PORT && ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("APP_POSTGRES_PORT=5433 ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("./scripts/doctor.sh", completed.stderr)
        self.assertNotIn("docker ", commands)

    def test_invalid_full_profile_port_fails_before_docker_with_recovery_hint(self) -> None:
        completed, commands = self.run_launch_process(
            ALLOW_NON_ASCII_DOCKER_BUILD="true",
            STACK_PROFILE="full",
            LANGFUSE_PORT="0",
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Invalid LANGFUSE_PORT=0 for Langfuse web", completed.stderr)
        self.assertIn("LANGFUSE_PORT must be between 1 and 65535", completed.stderr)
        self.assertIn("unset LANGFUSE_PORT && ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("LANGFUSE_PORT=3000 ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("./scripts/doctor.sh", completed.stderr)
        self.assertNotIn("docker ", commands)

    def test_duplicate_full_profile_host_ports_fail_before_docker_with_recovery_hint(self) -> None:
        completed, commands = self.run_launch_process(
            ALLOW_NON_ASCII_DOCKER_BUILD="true",
            STACK_PROFILE="full",
            API_PORT="8000",
            LANGFUSE_PORT="8000",
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "Duplicate host port 8000 for active self-host profile full",
            completed.stderr,
        )
        self.assertIn("API_PORT, LANGFUSE_PORT", completed.stderr)
        self.assertIn("STACK_PROFILE=core ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("./scripts/doctor.sh", completed.stderr)
        self.assertNotIn("docker ", commands)

    def test_core_profile_ignores_inactive_full_profile_port_duplicates(self) -> None:
        output = self.run_launch(
            ALLOW_NON_ASCII_DOCKER_BUILD="true",
            STACK_PROFILE="core",
            API_PORT="8000",
            LANGFUSE_PORT="8000",
        )

        self.assertIn("docker compose --env-file .env -f infra/compose/docker-compose.yml up -d --build", output)
        self.assertNotIn("--profile full", output)

    def test_doctor_invalid_api_port_is_a_blocking_issue(self) -> None:
        completed = self.run_doctor_process(API_PORT="not-a-port")
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1)
        self.assertIn("miss  API_PORT=not-a-port is not a valid TCP port", output)
        self.assertIn("Recovery: unset API_PORT && ./scripts/launch_skill_mode.sh", output)
        self.assertIn("Alternate: API_PORT=8012 ./scripts/launch_skill_mode.sh", output)
        self.assertIn("skipping API port availability check", output)
        self.assertNotIn("not a numeric port for API", output)
        self.assertIn("Doctor found", output)
        self.assertIn("blocking issue", output)
        self.assertIn(
            "Recommended next step: unset API_PORT && ./scripts/launch_skill_mode.sh",
            output,
        )

    def test_unsupported_stack_profile_has_actionable_recovery_hint(self) -> None:
        completed, commands = self.run_launch_process(
            ALLOW_NON_ASCII_DOCKER_BUILD="true",
            STACK_PROFILE="everything",
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Unsupported STACK_PROFILE=everything", completed.stderr)
        self.assertIn("Use one of: core, smoke, full", completed.stderr)
        self.assertIn("core  - API and Postgres only", completed.stderr)
        self.assertIn("STACK_PROFILE=smoke ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("STACK_PROFILE=full ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertIn("python3 scripts/check_env.py", commands)
        self.assertNotIn("docker ", commands)
        self.assertNotIn("up -d", commands)

    def test_doctor_unsupported_stack_profile_is_a_blocking_issue(self) -> None:
        completed = self.run_doctor_process(API_PORT="8000", STACK_PROFILE="everything")
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1)
        self.assertIn("miss  Unsupported STACK_PROFILE=everything", output)
        self.assertIn("Use one of: core, smoke, full", output)
        self.assertIn("Recovery: unset STACK_PROFILE && ./scripts/launch_self_host.sh", output)
        self.assertIn("Smoke path: STACK_PROFILE=smoke ./scripts/launch_self_host.sh", output)
        self.assertIn("Doctor found", output)
        self.assertIn("blocking issue", output)
        self.assertIn(
            "Recommended next step: unset STACK_PROFILE && ./scripts/launch_self_host.sh",
            output,
        )

    def test_doctor_env_validation_failure_is_blocking_but_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env"
            env_file.write_text(
                "APP_ENV=production\nNEXTAUTH_SECRET=change-me-nextauth-secret\n",
                encoding="utf-8",
            )
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "scripts/check_env.py" ]; then
                  printf "fail  NEXTAUTH_SECRET is still a default or placeholder value.\\n" >&2
                  printf "      Recovery: python3 scripts/setup_env.py --force --output %s\\n" "$3" >&2
                  exit 1
                fi
                if [ "${1:-}" = "-" ]; then
                  printf "%s\\n" "$4"
                  exit 0
                fi
                exit 0
                """,
            )
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "Docker Compose version v2.27.0\\n"
                  exit 0
                fi
                case "$*" in
                  *" config") exit 0 ;;
                esac
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ENV_FILE": str(env_file),
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1)
        self.assertIn("failed environment validation", output)
        self.assertIn("NEXTAUTH_SECRET is still a default or placeholder value", output)
        self.assertIn("Recovery: python3 scripts/check_env.py --env", output)
        self.assertIn("Regenerate local secrets: python3 scripts/setup_env.py --force", output)
        self.assertIn("Port checks for STACK_PROFILE=core", output)
        self.assertIn("Doctor found", output)
        self.assertIn("blocking issue", output)

    def test_doctor_warns_when_python_runtime_is_too_old(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env"
            env_file.write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  printf "3.10.13\\n"
                  exit 2
                fi
                if [ "${1:-}" = "-" ]; then
                  printf "%s\\n" "$4"
                  exit 0
                fi
                if [ "${1:-}" = "scripts/check_env.py" ]; then
                  printf "ok    .env is valid for APP_ENV=development.\\n"
                  exit 0
                fi
                exit 0
                """,
            )
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "Docker Compose version v2.27.0\\n"
                  exit 0
                fi
                case "$*" in
                  *" config") exit 0 ;;
                esac
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ENV_FILE": str(env_file),
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                    "STUDY_ANYTHING_PYTHON": "python3",
                }
            )
            completed = subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 0)
        self.assertIn("warn  Python runtime is older than 3.11", output)
        self.assertIn("python3 (3.10.13)", output)
        self.assertIn("PYTHON_BIN=/path/to/python3.11 ./scripts/launch_skill_mode.sh", output)
        self.assertIn("USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh", output)
        self.assertIn("Doctor found no blocking issues.", output)

    def test_doctor_redacts_local_command_paths(self) -> None:
        completed = self.run_doctor_process(API_PORT="8012", STACK_PROFILE="core")
        output = completed.stdout + completed.stderr

        self.assertIn("ok    docker: <temp-path>", output)
        self.assertIn("ok    curl: <temp-path>", output)
        self.assertNotIn("/private/var/folders", output)
        self.assertNotIn("/var/folders", output)

    def test_doctor_rejects_wrong_service_on_api_health_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env"
            env_file.write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(
                bin_dir / "curl",
                """
                printf '{"status":"ok","service":"other-app","token":"supersecret123","path":"/Users/james/private"}\\n'
                exit 0
                """,
            )
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  printf "3.11.9\\n"
                  exit 0
                fi
                if [ "${1:-}" = "scripts/check_env.py" ]; then
                  printf "ok    <env-file> is valid for APP_ENV=development.\\n"
                  exit 0
                fi
                exit 0
                """,
            )
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "Docker Compose version v2.27.0\\n"
                  exit 0
                fi
                case "$*" in
                  *" config") exit 0 ;;
                esac
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ENV_FILE": str(env_file),
                    "API_PORT": "18080",
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1)
        self.assertIn("miss  API health responded at http://127.0.0.1:18080/v1/health", output)
        self.assertIn("does not look like Study Anything", output)
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", output)
        self.assertIn("lsof -nP -iTCP:18080 -sTCP:LISTEN", output)
        self.assertIn('"token":"<redacted>"', output)
        self.assertIn("<local-path>", output)
        self.assertNotIn("supersecret123", output)
        self.assertNotIn("/Users/james", output)

    def test_doctor_warns_when_local_agent_gateway_is_unhealthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env"
            env_file.write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(
                bin_dir / "curl",
                """
                url=""
                for arg do
                  url="$arg"
                done
                case "$url" in
                  http://127.0.0.1:18080/v1/health)
                    printf '{"status":"ok","version":"0.3.29"}\\n'
                    exit 0
                    ;;
                  http://127.0.0.1:8787/health)
                    printf '{"status":"error","diagnostic_code":"configuration_required","message":"AGENT_LLM_API_KEY=sk-proj-abcdefghijklmnop123456 missing","path":"/Users/james/private"}\\n'
                    exit 0
                    ;;
                esac
                exit 7
                """,
            )
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "-" ]; then
                  cat >/dev/null
                  printf "%s\\n" "${4:-}"
                  exit 0
                fi
                if [ "${1:-}" = "-c" ]; then
                  printf "3.11.9\\n"
                  exit 0
                fi
                if [ "${1:-}" = "scripts/check_env.py" ]; then
                  printf "ok    <env-file> is valid for APP_ENV=development.\\n"
                  exit 0
                fi
                exit 0
                """,
            )
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "Docker Compose version v2.27.0\\n"
                  exit 0
                fi
                case "$*" in
                  *" config") exit 0 ;;
                esac
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ENV_FILE": str(env_file),
                    "API_PORT": "18080",
                    "AGENT_HTTP_GATEWAY_URL": "127.0.0.1:8787/invoke",
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 0, output)
        self.assertIn("ok    API health responds at http://127.0.0.1:18080/v1/health", output)
        self.assertIn("warn  HTTP Agent gateway responded at http://127.0.0.1:8787/health", output)
        self.assertIn("not healthy yet", output)
        self.assertIn("AGENT_GATEWAY_MODE=dry_run", output)
        self.assertIn("agent-add-http --set-default", output)
        self.assertIn("diagnose_adoption.py", output)
        self.assertIn("AGENT_LLM_API_KEY=<redacted>", output)
        self.assertIn("<local-path>", output)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", output)
        self.assertNotIn("/Users/james", output)

    def test_doctor_probes_zero_zero_zero_zero_agent_gateway_on_loopback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env"
            env_file.write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(
                bin_dir / "curl",
                """
                url=""
                for arg do
                  url="$arg"
                done
                case "$url" in
                  http://127.0.0.1:18080/v1/health)
                    printf '{"status":"ok","version":"0.3.29"}\\n'
                    exit 0
                    ;;
                  http://127.0.0.1:8787/health)
                    printf '{"status":"ok","mode":"dry_run"}\\n'
                    exit 0
                    ;;
                  http://0.0.0.0:8787/health)
                    printf "doctor should not probe 0.0.0.0 as a client URL\\n" >&2
                    exit 22
                    ;;
                esac
                exit 7
                """,
            )
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  printf "3.11.9\\n"
                  exit 0
                fi
                if [ "${1:-}" = "-" ]; then
                  cat >/dev/null
                  printf "%s\\n" "${4:-}"
                  exit 0
                fi
                if [ "${1:-}" = "scripts/check_env.py" ]; then
                  printf "ok    <env-file> is valid for APP_ENV=development.\\n"
                  exit 0
                fi
                exit 0
                """,
            )
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "Docker Compose version v2.27.0\\n"
                  exit 0
                fi
                case "$*" in
                  *" config") exit 0 ;;
                esac
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ENV_FILE": str(env_file),
                    "API_PORT": "18080",
                    "AGENT_HTTP_GATEWAY_URL": "0.0.0.0:8787/invoke",
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 0, output)
        self.assertIn("ok    API health responds at http://127.0.0.1:18080/v1/health", output)
        self.assertIn("ok    HTTP Agent gateway responds at http://127.0.0.1:8787/health", output)
        self.assertNotIn("doctor should not probe 0.0.0.0", output)

    def test_doctor_redacts_non_ascii_source_path(self) -> None:
        completed = self.run_doctor_process(
            ALLOW_NON_ASCII_DOCKER_BUILD="false",
            API_PORT="8012",
            STACK_PROFILE="core",
            STUDY_ANYTHING_DOCKER_SOURCE_PATH="/Users/example/学习系统",
        )
        output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Docker source build path contains non-ASCII characters", output)
        self.assertIn("<local-path>", output)
        self.assertNotIn("/Users/example", output)

    def test_doctor_honors_study_anything_env_file_exported_api_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env.custom"
            env_file.write_text(
                'APP_ENV=development\nexport API_PORT="18082" # local override\n',
                encoding="utf-8",
            )
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  printf "3.12.0\\n"
                  exit 0
                fi
                if [ "${1:-}" = "scripts/check_env.py" ]; then
                  printf "ok    <env-file> is valid for APP_ENV=development.\\n"
                  exit 0
                fi
                if [ "${1:-}" = "-" ]; then
                  if [ "${3:-}" = "API_PORT" ]; then
                    printf "18082\\n"
                  else
                    printf "%s\\n" "${4:-}"
                  fi
                  exit 0
                fi
                exit 0
                """,
            )
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "Docker Compose version v2.27.0\\n"
                  exit 0
                fi
                case "$*" in
                  *" config") exit 0 ;;
                esac
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_ENV_FILE": str(env_file),
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 0, output)
        self.assertIn("port 18082 for API (API_PORT) is available", output)
        self.assertIn("http://127.0.0.1:18082/v1/health", output)

    def test_doctor_redacts_docker_socket_and_secret_like_error_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env"
            env_file.write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(bin_dir / "python3", "exit 0")
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "info" ]; then
                  printf "permission denied Authorization: Bearer supersecret123 AGENT_LLM_API_KEY=sk-proj-example123456789012345 while connecting to unix:///Users/example/.docker/run/docker.sock via https://user:secret@example.test/simple\\n" >&2
                  exit 1
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                    "ENV_FILE": str(env_file),
                    "AGENT_HTTP_GATEWAY_URL": "https://user:secret@example.test/invoke?token=supersecret123",
                }
            )
            completed = subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 1)
        self.assertIn("docker socket is not accessible", output)
        self.assertIn("Authorization: Bearer <redacted>", output)
        self.assertIn("AGENT_LLM_API_KEY=<redacted>", output)
        self.assertIn("https://<redacted>@example.test/simple", output)
        self.assertIn("https://<redacted>@example.test/invoke?token=<redacted>", output)
        self.assertIn("<local-path>", output)
        self.assertNotIn("/Users/example", output)
        self.assertNotIn("sk-proj-example", output)
        self.assertNotIn("user:secret", output)
        self.assertNotIn("supersecret123", output)

    def test_doctor_blocks_agent_gateway_url_with_inline_secret_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env"
            env_file.write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  printf "3.11.9\\n"
                  exit 0
                fi
                if [ "${1:-}" = "-" ]; then
                  cat >/dev/null
                  printf "%s\\n" "${4:-}"
                  exit 0
                fi
                if [ "${1:-}" = "scripts/check_env.py" ]; then
                  printf "ok    <env-file> is valid for APP_ENV=development.\\n"
                  exit 0
                fi
                exit 0
                """,
            )
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "Docker Compose version v2.27.0\\n"
                  exit 0
                fi
                case "$*" in
                  *" config") exit 0 ;;
                esac
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ENV_FILE": str(env_file),
                    "API_PORT": "18080",
                    "STACK_PROFILE": "core",
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                    "AGENT_HTTP_GATEWAY_URL": (
                        "https://user:secret@example.test/invoke?"
                        "token=sk-proj-abcdefghijklmnop123456"
                    ),
                }
            )
            completed = subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1)
        self.assertIn("AGENT_HTTP_GATEWAY_URL must not contain inline credentials", output)
        self.assertIn("https://<redacted>@example.test/invoke?token=<redacted>", output)
        self.assertIn("Move model/API credentials into your private gateway", output)
        self.assertIn("AGENT_HTTP_GATEWAY_URL=http://host.docker.internal:8787", output)
        self.assertIn("AGENT_GATEWAY_MODE=dry_run", output)
        self.assertNotIn("user:secret", output)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", output)

    def test_doctor_blocks_agent_gateway_url_with_camel_case_secret_query_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            env_file = root / ".env"
            env_file.write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(bin_dir / "lsof", "exit 1")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  printf "3.11.9\\n"
                  exit 0
                fi
                if [ "${1:-}" = "-" ]; then
                  cat >/dev/null
                  printf "%s\\n" "${4:-}"
                  exit 0
                fi
                if [ "${1:-}" = "scripts/check_env.py" ]; then
                  printf "ok    <env-file> is valid for APP_ENV=development.\\n"
                  exit 0
                fi
                exit 0
                """,
            )
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "Docker Compose version v2.27.0\\n"
                  exit 0
                fi
                case "$*" in
                  *" config") exit 0 ;;
                esac
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ENV_FILE": str(env_file),
                    "API_PORT": "18080",
                    "STACK_PROFILE": "core",
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                    "AGENT_HTTP_GATEWAY_URL": (
                        "https://agent.example.test/invoke?"
                        "apiKey=plainsecret123&accessToken=toksecret456"
                    ),
                }
            )
            completed = subprocess.run(
                ["sh", str(DOCTOR_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = completed.stdout + completed.stderr

        self.assertEqual(completed.returncode, 1)
        self.assertIn("AGENT_HTTP_GATEWAY_URL must not contain inline credentials", output)
        self.assertIn("apiKey=<redacted>", output)
        self.assertIn("accessToken=<redacted>", output)
        self.assertIn("Move model/API credentials into your private gateway", output)
        self.assertNotIn("plainsecret123", output)
        self.assertNotIn("toksecret456", output)

    def test_published_launch_can_use_cached_images_without_pull(self) -> None:
        output = self.run_launch(
            USE_PUBLISHED_IMAGES="true",
            PULL_PUBLISHED_IMAGES="false",
        )
        self.assertIn("Skipping published image pulls because PULL_PUBLISHED_IMAGES=false.", output)
        self.assertNotIn("docker pull", output)

    def test_published_image_pull_failure_has_actionable_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (root / ".env").write_text("APP_ENV=development\n", encoding="utf-8")
            log_file = root / "commands.log"
            self.write_stub(bin_dir / "python3", "exit 0")
            self.write_stub(bin_dir / "curl", "exit 0")
            self.write_stub(
                bin_dir / "docker",
                """
                printf 'docker %s\\n' "$*" >> "$LOG_FILE"
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "pull" ]; then
                  printf "Error response from daemon: Get https://user:secret@ghcr.io/v2/?token=supersecret123: no such host\\n" >&2
                  exit 1
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "LOG_FILE": str(log_file),
                    "USE_PUBLISHED_IMAGES": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            commands = log_file.read_text(encoding="utf-8")

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Published Study Anything image pull failed", completed.stderr)
        self.assertIn("ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha", completed.stderr)
        self.assertIn("no such host", completed.stderr)
        self.assertIn("https://<redacted>@ghcr.io/v2/?token=<redacted>", completed.stderr)
        self.assertIn("docker manifest inspect", completed.stderr)
        self.assertIn("PULL_PUBLISHED_IMAGES=false", completed.stderr)
        self.assertIn("./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertIn("docker pull ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha", commands)
        self.assertNotIn("up -d", commands)
        self.assertNotIn("user:secret", completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)

    def test_non_ascii_source_path_has_actionable_diagnostic(self) -> None:
        completed, commands = self.run_launch_process(
            STUDY_ANYTHING_DOCKER_SOURCE_PATH="/tmp/学习系统"
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("checkout path contains non-ASCII characters", completed.stderr)
        self.assertIn("Current path: <temp-path>", completed.stderr)
        self.assertIn("USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn(
            "ALLOW_NON_ASCII_DOCKER_BUILD=true ./scripts/launch_self_host.sh",
            completed.stderr,
        )
        self.assertNotIn("/tmp/学习系统", completed.stderr)
        self.assertNotIn("docker compose", commands)

    def test_missing_docker_command_has_actionable_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (root / ".env").write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(bin_dir / "python3", "exit 0")
            self.write_stub(
                bin_dir / "dirname",
                """
                if [ "${1:-}" = "--" ]; then
                  shift
                fi
                path="${1:-.}"
                case "$path" in
                  */*) printf "%s\\n" "${path%/*}" ;;
                  *) printf ".\\n" ;;
                esac
                """,
            )
            self.write_stub(bin_dir / "grep", "exit 1")

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:/bin"
            completed = subprocess.run(
                ["/bin/sh", str(SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Docker command was not found in PATH.", completed.stderr)
        self.assertIn("Install Docker Desktop or Docker Engine", completed.stderr)
        self.assertIn("./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)

    def test_missing_docker_compose_plugin_has_actionable_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (root / ".env").write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(bin_dir / "python3", "exit 0")
            self.write_stub(
                bin_dir / "dirname",
                """
                if [ "${1:-}" = "--" ]; then
                  shift
                fi
                path="${1:-.}"
                case "$path" in
                  */*) printf "%s\\n" "${path%/*}" ;;
                  *) printf ".\\n" ;;
                esac
                """,
            )
            self.write_stub(bin_dir / "grep", "exit 1")
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  printf "docker: 'compose' is not a docker command. Authorization: Bearer supersecret123 via https://user:secret@example.test/simple\\n" >&2
                  exit 1
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:/bin"
            completed = subprocess.run(
                ["/bin/sh", str(SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Docker Compose v2 plugin is not available", completed.stderr)
        self.assertIn("docker: 'compose' is not a docker command", completed.stderr)
        self.assertIn("Authorization: Bearer <redacted>", completed.stderr)
        self.assertIn("https://<redacted>@example.test/simple", completed.stderr)
        self.assertIn("docker compose version", completed.stderr)
        self.assertIn("./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertNotIn("user:secret", completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)

    def test_docker_socket_permission_failure_has_actionable_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (root / ".env").write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(bin_dir / "python3", "exit 0")
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "info" ]; then
                  printf "permission denied Authorization: Bearer supersecret123 AGENT_LLM_API_KEY=sk-proj-example123456789012345 while trying to connect to the docker API at unix:///Users/example/.docker/run/docker.sock via https://user:secret@example.test/simple\\n" >&2
                  exit 1
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Docker socket is not accessible", completed.stderr)
        self.assertIn("Authorization: Bearer <redacted>", completed.stderr)
        self.assertIn("AGENT_LLM_API_KEY=<redacted>", completed.stderr)
        self.assertIn("https://<redacted>@example.test/simple", completed.stderr)
        self.assertIn("<local-path>", completed.stderr)
        self.assertIn("active Docker context", completed.stderr)
        self.assertIn("./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertNotIn("/Users/example", completed.stderr)
        self.assertNotIn("sk-proj-example", completed.stderr)
        self.assertNotIn("user:secret", completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)

    def test_docker_daemon_unavailable_has_actionable_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (root / ".env").write_text("APP_ENV=development\n", encoding="utf-8")
            self.write_stub(bin_dir / "python3", "exit 0")
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "info" ]; then
                  printf "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?\\n" >&2
                  exit 1
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Docker daemon is not running", completed.stderr)
        self.assertIn("./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)

    def test_compose_up_failure_has_actionable_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            log_file = root / "commands.log"
            self.write_stub(bin_dir / "python3", "exit 0")
            self.write_stub(bin_dir / "curl", "exit 0")
            self.write_stub(
                bin_dir / "docker",
                """
                printf 'docker %s\\n' "$*" >> "$LOG_FILE"
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                case "$*" in
                  *"up -d --build"*)
                    printf "Error response from daemon: driver failed programming external connectivity: bind: address already in use Authorization: Bearer supersecret123 path=/Users/example/project\\n" >&2
                    exit 1
                    ;;
                esac
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "LOG_FILE": str(log_file),
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                }
            )
            completed = subprocess.run(
                ["sh", str(SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            commands = log_file.read_text(encoding="utf-8")

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Docker Compose failed to start the Study Anything stack.", completed.stderr)
        self.assertIn("Stack profile: core", completed.stderr)
        self.assertIn("address already in use", completed.stderr)
        self.assertIn("Authorization: Bearer <redacted>", completed.stderr)
        self.assertIn("<local-path>", completed.stderr)
        self.assertIn("docker compose --env-file .env -f infra/compose/docker-compose.yml ps", completed.stderr)
        self.assertIn("logs --tail=200 api app-postgres", completed.stderr)
        self.assertIn("./scripts/doctor.sh", completed.stderr)
        self.assertIn("API_PORT=8012 ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertIn("up -d --build", commands)
        self.assertNotIn("/Users/example", completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)

    def test_api_health_timeout_has_actionable_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            log_file = root / "commands.log"
            self.write_stub(bin_dir / "python3", "exit 0")
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(
                bin_dir / "docker",
                """
                printf 'docker %s\\n' "$*" >> "$LOG_FILE"
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "LOG_FILE": str(log_file),
                    "ALLOW_NON_ASCII_DOCKER_BUILD": "true",
                    "SELF_HOST_API_HEALTH_ATTEMPTS": "1",
                    "SELF_HOST_API_HEALTH_INTERVAL_SECONDS": "0",
                }
            )
            completed = subprocess.run(
                ["sh", str(SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn(
            "API did not become healthy at http://127.0.0.1:8000/v1/health after 1 attempts.",
            completed.stderr,
        )
        self.assertIn("API container exited", completed.stderr)
        self.assertIn("docker compose --env-file .env -f infra/compose/docker-compose.yml ps", completed.stderr)
        self.assertIn("logs --tail=200 api app-postgres", completed.stderr)
        self.assertIn("./scripts/doctor.sh", completed.stderr)
        self.assertIn("API_PORT=8012 ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)

    def test_skill_mode_dependency_failure_prints_concise_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            venv_dir = root / ".venv"
            bin_dir = root / "bin"
            (venv_dir / "bin").mkdir(parents=True)
            bin_dir.mkdir()
            self.write_stub(bin_dir / "curl", "exit 22")
            self.write_stub(
                venv_dir / "bin" / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  case "${2:-}" in
                    *"fastapi, langgraph, uvicorn"*) exit 1 ;;
                    *"import setuptools"*) exit 0 ;;
                    *) exit 0 ;;
                  esac
                fi
                if [ "${1:-}" = "-m" ] && [ "${2:-}" = "pip" ]; then
                  printf 'WARNING: Retrying after connection broken by NewConnectionError\\n'
                  printf 'Failed to establish a new connection: [Errno 8] nodename nor servname provided at https://user:secret@example.test/simple/pkg token=supersecret123 /Users/james/private/source.txt\\n'
                  printf 'ERROR: No matching distribution found for setuptools>=40.8.0\\n'
                  exit 1
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_DATA_DIR": str(data_dir),
                    "STUDY_ANYTHING_VENV": str(venv_dir),
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Study Anything dependency installation failed.", completed.stderr)
        self.assertIn("Relevant pip output", completed.stderr)
        self.assertIn("No matching distribution found", completed.stderr)
        self.assertIn("PIP_INDEX_URL", completed.stderr)
        self.assertIn("Full pip log:", completed.stderr)
        self.assertNotIn("WARNING: Retrying", completed.stderr)
        self.assertIn("https://<redacted>@example.test/simple/pkg", completed.stderr)
        self.assertIn("token=<redacted>", completed.stderr)
        self.assertIn("<local-path>", completed.stderr)
        self.assertNotIn("user:secret", completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)
        self.assertNotIn("/Users/james", completed.stderr)


class StopSelfHostTests(unittest.TestCase):
    @staticmethod
    def write_stub(path: Path, body: str) -> None:
        path.write_text("#!/usr/bin/env sh\n" + textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(0o755)

    def test_missing_docker_command_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            self.write_stub(
                bin_dir / "dirname",
                """
                if [ "${1:-}" = "--" ]; then
                  shift
                fi
                path="${1:-.}"
                case "$path" in
                  */*) printf "%s\\n" "${path%/*}" ;;
                  *) printf ".\\n" ;;
                esac
                """,
            )
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:/bin"
            completed = subprocess.run(
                ["/bin/sh", str(STOP_SELF_HOST_SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Docker command was not found", completed.stderr)
        self.assertIn("Failure classification: docker_cli_missing", completed.stderr)
        self.assertIn("./scripts/stop_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)

    def test_docker_socket_permission_failure_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "info" ]; then
                  printf "permission denied Authorization: Bearer supersecret123 AGENT_LLM_API_KEY=sk-proj-example123456789012345 while trying to connect to the docker API at unix:///Users/example/.docker/run/docker.sock via https://user:secret@example.test/simple\\n" >&2
                  exit 1
                fi
                exit 0
                """,
            )
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
            completed = subprocess.run(
                ["sh", str(STOP_SELF_HOST_SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Docker socket is not accessible", completed.stderr)
        self.assertIn("Failure classification: docker_socket_permission_denied", completed.stderr)
        self.assertIn("active Docker context", completed.stderr)
        self.assertIn("./scripts/stop_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertIn("Authorization: Bearer <redacted>", completed.stderr)
        self.assertIn("AGENT_LLM_API_KEY=<redacted>", completed.stderr)
        self.assertIn("https://<redacted>@example.test/simple", completed.stderr)
        self.assertIn("<local-path>", completed.stderr)
        self.assertNotIn("/Users/example", completed.stderr)
        self.assertNotIn("sk-proj-example", completed.stderr)
        self.assertNotIn("user:secret", completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)

    def test_docker_daemon_unavailable_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            self.write_stub(
                bin_dir / "docker",
                """
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "info" ]; then
                  printf "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?\\n" >&2
                  exit 1
                fi
                exit 0
                """,
            )
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
            completed = subprocess.run(
                ["sh", str(STOP_SELF_HOST_SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Docker daemon is not running", completed.stderr)
        self.assertIn("Failure classification: docker_daemon_unavailable", completed.stderr)
        self.assertIn("./scripts/stop_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)

    def test_success_uses_env_file_when_present(self) -> None:
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
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )
            env = os.environ.copy()
            env.update({"PATH": f"{bin_dir}:/usr/bin:/bin", "LOG_FILE": str(log_file)})
            completed = subprocess.run(
                ["sh", str(STOP_SELF_HOST_SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            commands = log_file.read_text(encoding="utf-8")

        self.assertEqual(completed.returncode, 0)
        self.assertIn("--env-file .env", commands)
        self.assertIn("--profile full --profile smoke down", commands)

    def test_success_honors_custom_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            custom_env = root / "dev.selfhost.env"
            custom_env.write_text("APP_ENV=development\n", encoding="utf-8")
            log_file = root / "commands.log"
            self.write_stub(
                bin_dir / "docker",
                """
                printf 'docker %s\\n' "$*" >> "$LOG_FILE"
                if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "info" ]; then
                  exit 0
                fi
                exit 0
                """,
            )
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "LOG_FILE": str(log_file),
                    "ENV_FILE": str(custom_env),
                }
            )
            completed = subprocess.run(
                ["sh", str(STOP_SELF_HOST_SCRIPT)],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            commands = log_file.read_text(encoding="utf-8")

        self.assertEqual(completed.returncode, 0)
        self.assertIn(f"--env-file {custom_env}", commands)
        self.assertNotIn("--env-file .env", commands)
        self.assertIn("--profile full --profile smoke down", commands)


class PublishedImageLaunchTests(unittest.TestCase):
    def _module(self):
        spec = spec_from_file_location("verify_published_image_launch", PUBLISHED_IMAGE_SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_parse_env_accepts_shell_style_overrides(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        'export COMPOSE_PROJECT_NAME="study_anything_published" # local override',
                        'export API_PORT="18080" # local override',
                        "CALLBACK_URL=https://example.test/callback#keep-fragment",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            values = module.parse_env(env_file)

        self.assertEqual(values["COMPOSE_PROJECT_NAME"], "study_anything_published")
        self.assertEqual(values["API_PORT"], "18080")
        self.assertEqual(values["CALLBACK_URL"], "https://example.test/callback#keep-fragment")

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
        self.assertEqual(report["classification"], "blocked_by_local_ghcr_pull")
        self.assertIn("docker manifest inspect", report["next_steps"][0])
        self.assertEqual(report["manifest_evidence"]["status"], "ok")
        self.assertIn("GitHub Actions docker-images workflow succeeded", report["fallback_acceptance"]["acceptable_when"][0])

    def test_skip_pull_uses_cached_only_compose_policy(self) -> None:
        module = self._module()

        self.assertEqual(module.compose_up_args(skip_pull=False), ("up", "-d", "api"))
        self.assertEqual(
            module.compose_up_args(skip_pull=True),
            ("up", "--pull", "never", "-d", "api"),
        )

    def test_cached_image_missing_report_is_actionable(self) -> None:
        module = self._module()

        report = module.cached_image_missing_report(
            tag="v0.3.29-alpha",
            api_image="ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
            project_name="study_anything_published_test",
            stderr="No such image: ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
            manifest_evidence={"status": "ok", "platforms": ["linux/amd64", "linux/arm64"]},
        )

        self.assertEqual(report["status"], "cached_image_missing")
        self.assertEqual(report["classification"], "cached_image_missing")
        self.assertIn("docker pull", report["next_steps"][0])
        self.assertEqual(report["manifest_evidence"]["status"], "ok")

    def test_compose_up_timeout_report_is_actionable(self) -> None:
        module = self._module()

        report = module.compose_up_timeout_report(
            tag="v0.3.29-alpha",
            api_image="ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
            timeout_seconds=2,
            project_name="study_anything_published_test",
            manifest_evidence={"status": "ok", "platforms": ["linux/amd64", "linux/arm64"]},
        )

        self.assertEqual(report["status"], "compose_up_timeout")
        self.assertEqual(report["classification"], "compose_up_timeout")
        self.assertEqual(report["timeout_seconds"], 2)
        self.assertIn("--manifest-only", report["next_steps"][1])

    def test_manifest_only_report_marks_runtime_unverified(self) -> None:
        module = self._module()

        report = module.manifest_only_report(
            tag="v0.3.29-alpha",
            api_image="ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
            manifest_evidence={"status": "ok", "platforms": ["linux/amd64", "linux/arm64"]},
        )

        self.assertEqual(report["status"], "manifest_available_runtime_unverified")
        self.assertEqual(report["classification"], "manifest_available_runtime_unverified")
        self.assertIn("does not start the container", report["diagnostic"])

    def test_free_port_permission_failure_is_actionable(self) -> None:
        module = self._module()

        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def bind(self, _address: tuple[str, int]) -> None:
                raise OSError(1, "Operation not permitted")

        with patch.object(module.socket, "socket", return_value=FakeSocket()):
            with self.assertRaisesRegex(RuntimeError, "normal terminal"):
                module.free_port()

    def test_free_port_permission_denied_failure_is_actionable(self) -> None:
        module = self._module()

        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def bind(self, _address: tuple[str, int]) -> None:
                raise OSError(13, "Permission denied")

        with patch.object(module.socket, "socket", return_value=FakeSocket()):
            with self.assertRaisesRegex(RuntimeError, "normal terminal"):
                module.free_port()

    def test_published_image_failure_report_handles_missing_docker(self) -> None:
        module = self._module()

        report = module.failure_report(
            exc=FileNotFoundError("No such file or directory: 'docker'"),
            tag="v0.3.29-alpha",
            api_image="ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["classification"], "docker_missing")
        self.assertIn("Docker Desktop", " ".join(report["next_steps"]))
        self.assertIn("manifest-only", " ".join(report["next_steps"]))
        self.assertFalse(report["privacy"]["real_model_keys_included"])

    def test_published_image_manifest_failure_with_missing_docker_is_classified_as_docker_missing(self) -> None:
        module = self._module()

        report = module.failure_report(
            exc=RuntimeError(
                "Published image manifest is not ready: "
                "{'status': 'unavailable', 'reason': 'docker_missing'}"
            ),
            tag="v0.3.29-alpha",
            api_image="ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
        )

        self.assertEqual(report["classification"], "docker_missing")
        self.assertIn("Docker Desktop", " ".join(report["next_steps"]))

    def test_published_image_failure_report_redacts_docker_socket_and_secret_like_text(self) -> None:
        module = self._module()
        exc = subprocess.CalledProcessError(
            1,
            ["docker", "compose", "up"],
            output=f"using checkout {REPO_ROOT}\n",
            stderr=(
                "permission denied while trying to connect to the Docker daemon "
                "at unix:///Users/example/.docker/run/docker.sock token=supersecret123\n"
            ),
        )

        report = module.failure_report(
            exc=exc,
            tag="v0.3.29-alpha",
            api_image="ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
            project_name="study_anything_published_test",
        )
        serialized = json.dumps(report)

        self.assertEqual(report["classification"], "docker_socket_permission_denied")
        self.assertEqual(report["project"], "study_anything_published_test")
        self.assertIn("active Docker context", " ".join(report["next_steps"]))
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn(str(REPO_ROOT), serialized)
        self.assertNotIn("supersecret123", serialized)

    def test_published_image_failure_context_uses_cli_tag_and_image(self) -> None:
        module = self._module()

        tag, image = module.failure_context_from_argv(
            [
                "--tag",
                "v9.9.9-alpha",
                "--api-image=registry.example/study-api:test",
            ]
        )

        self.assertEqual(tag, "v9.9.9-alpha")
        self.assertEqual(image, "registry.example/study-api:test")


class BackupRestoreDrillTests(unittest.TestCase):
    def _module(self):
        spec = spec_from_file_location("verify_backup_restore_drill", BACKUP_RESTORE_SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_parse_env_accepts_shell_style_overrides(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        'export COMPOSE_PROJECT_NAME="study_anything_drill" # local override',
                        'export API_PORT="18081" # local override',
                        "POSTGRES_USER=study # local user",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            values = module.parse_env(env_file)

        self.assertEqual(values["COMPOSE_PROJECT_NAME"], "study_anything_drill")
        self.assertEqual(values["API_PORT"], "18081")
        self.assertEqual(values["POSTGRES_USER"], "study")

    def test_free_port_permission_failure_is_actionable(self) -> None:
        module = self._module()

        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def bind(self, _address: tuple[str, int]) -> None:
                raise OSError(1, "Operation not permitted")

        with patch.object(module.socket, "socket", return_value=FakeSocket()):
            with self.assertRaisesRegex(RuntimeError, "normal terminal"):
                module.free_port()

    def test_free_port_permission_denied_failure_is_actionable(self) -> None:
        module = self._module()

        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def bind(self, _address: tuple[str, int]) -> None:
                raise OSError(13, "Permission denied")

        with patch.object(module.socket, "socket", return_value=FakeSocket()):
            with self.assertRaisesRegex(RuntimeError, "normal terminal"):
                module.free_port()


class SkillModeLaunchTests(unittest.TestCase):
    @staticmethod
    def write_stub(path: Path, body: str) -> None:
        path.write_text("#!/usr/bin/env sh\n" + textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(0o755)

    def test_local_bind_permission_failure_has_recovery_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            venv_bin = root / "venv" / "bin"
            bin_dir.mkdir()
            venv_bin.mkdir(parents=True)
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(
                venv_bin / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "-m" ]; then
                  printf "INFO:     Started server process [12345]\\n"
                  printf "ERROR:    [Errno 1] error while attempting to bind on address ('127.0.0.1', 18080): operation not permitted\\n"
                  exit 1
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_VENV": str(root / "venv"),
                    "STUDY_ANYTHING_DATA_DIR": str(root / "data"),
                    "API_PORT": "18080",
                    "SKILL_API_HEALTH_ATTEMPTS": "1",
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("could not bind to 127.0.0.1:18080", completed.stderr)
        self.assertIn("normal terminal", completed.stderr)
        self.assertIn("API_PORT", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)

    def test_invalid_skill_mode_api_port_fails_before_runtime_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            venv_dir = root / "venv"
            env = os.environ.copy()
            env.update(
                {
                    "STUDY_ANYTHING_VENV": str(venv_dir),
                    "STUDY_ANYTHING_DATA_DIR": str(data_dir),
                    "API_PORT": "not-a-port",
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Invalid API_PORT=not-a-port for Skill Mode", completed.stderr)
        self.assertIn("API_PORT must be a number from 1 to 65535", completed.stderr)
        self.assertIn("unset API_PORT && ./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertNotIn("Creating Skill Mode virtual environment", completed.stdout)

    def test_local_bind_permission_denied_has_recovery_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            venv_bin = root / "venv" / "bin"
            bin_dir.mkdir()
            venv_bin.mkdir(parents=True)
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(
                venv_bin / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "-m" ]; then
                  printf "INFO:     Started server process [12345]\\n"
                  printf "ERROR:    [Errno 13] error while attempting to bind on address ('127.0.0.1', 18080): permission denied\\n"
                  exit 1
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_VENV": str(root / "venv"),
                    "STUDY_ANYTHING_DATA_DIR": str(root / "data"),
                    "API_PORT": "18080",
                    "SKILL_API_HEALTH_ATTEMPTS": "1",
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("could not bind to 127.0.0.1:18080", completed.stderr)
        self.assertIn("normal terminal", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)

    def test_python_version_failure_has_recovery_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "-" ]; then
                  cat >/dev/null
                  exit 1
                fi
                if [ "${1:-}" = "-c" ]; then
                  case "${2:-}" in
                    *"print(sys.version.split()[0])"*)
                      printf "3.10.9\\n"
                      exit 0
                      ;;
                  esac
                fi
                exit 1
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_VENV": str(root / "venv"),
                    "STUDY_ANYTHING_DATA_DIR": str(root / "data"),
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Python 3.11 or newer is required for Skill Mode", completed.stderr)
        self.assertIn("found 3.10.9", completed.stderr)
        self.assertIn("PYTHON_BIN=/path/to/python3.11", completed.stderr)
        self.assertIn("STUDY_ANYTHING_VENV=/path/to/.venv", completed.stderr)
        self.assertIn("USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertNotIn(str(root), completed.stderr)

    def test_existing_skill_api_ready_prints_copyable_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            self.write_stub(
                bin_dir / "curl",
                """
                printf '{"status":"ok","version":"0.3.29"}\\n'
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_DATA_DIR": str(root / "data"),
                    "API_PORT": "18080",
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("Study Anything Skill API is already running.", completed.stdout)
        self.assertIn("Study Anything Skill API is ready at http://127.0.0.1:18080", completed.stdout)
        self.assertIn("Next steps:", completed.stdout)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:18080 health", completed.stdout)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:18080 demo", completed.stdout)
        self.assertIn("AGENT_GATEWAY_MODE=dry_run", completed.stdout)
        self.assertIn("agent-add-http --set-default", completed.stdout)
        self.assertIn("diagnose_adoption.py", completed.stdout)

    def test_existing_health_endpoint_for_wrong_service_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            self.write_stub(
                bin_dir / "curl",
                """
                printf '{"status":"ok","service":"other-app","token":"supersecret123","path":"/Users/james/private"}\\n'
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_DATA_DIR": str(root / "data"),
                    "API_PORT": "18080",
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("does not look like Study Anything", completed.stderr)
        self.assertIn("Health response excerpt", completed.stderr)
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("lsof -nP -iTCP:18080 -sTCP:LISTEN", completed.stderr)
        self.assertIn("./scripts/stop_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertIn('"token":"<redacted>"', completed.stderr)
        self.assertIn("<local-path>", completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)
        self.assertNotIn("/Users/james", completed.stderr)

    def test_venv_creation_failure_prints_concise_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            data_dir = root / "data"
            bin_dir.mkdir()
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "-" ]; then
                  cat >/dev/null
                  exit 0
                fi
                if [ "${1:-}" = "-c" ]; then
                  case "${2:-}" in
                    *"print(sys.version.split()[0])"*)
                      printf "3.11.9\\n"
                      exit 0
                      ;;
                  esac
                  exit 0
                fi
                if [ "${1:-}" = "-m" ] && [ "${2:-}" = "venv" ]; then
                  printf "The virtual environment was not created successfully because ensurepip is not available.\\n" >&2
                  printf "Diagnostic path /Users/james/private/venv with token=supersecret123 and https://user:secret@example.test/simple.\\n" >&2
                  printf "On Debian/Ubuntu systems, install the python3.11-venv package.\\n" >&2
                  exit 1
                fi
                exit 1
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_VENV": str(root / "venv"),
                    "STUDY_ANYTHING_DATA_DIR": str(data_dir),
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Study Anything virtual environment creation failed.", completed.stderr)
        self.assertIn("Relevant venv output", completed.stderr)
        self.assertIn("ensurepip is not available", completed.stderr)
        self.assertIn("sudo apt install python3.11-venv", completed.stderr)
        self.assertIn("PYTHON_BIN=/path/to/python3.11", completed.stderr)
        self.assertIn("STUDY_ANYTHING_VENV=/path/to/.venv", completed.stderr)
        self.assertIn("USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh", completed.stderr)
        self.assertIn("Full venv log:", completed.stderr)
        self.assertIn("<temp-path>", completed.stderr)
        self.assertIn("<local-path>", completed.stderr)
        self.assertIn("token=<redacted>", completed.stderr)
        self.assertIn("https://<redacted>@example.test/simple", completed.stderr)
        self.assertNotIn(str(root), completed.stdout + completed.stderr)
        self.assertNotIn("/Users/james", completed.stderr)
        self.assertNotIn("user:secret", completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)

    def test_unhealthy_existing_skill_process_has_recovery_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            bin_dir = root / "bin"
            venv_bin = root / "venv" / "bin"
            data_dir.mkdir()
            bin_dir.mkdir()
            venv_bin.mkdir(parents=True)
            (data_dir / "api.pid").write_text(str(os.getpid()), encoding="utf-8")
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(
                venv_bin / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "-" ]; then
                  cat >/dev/null
                  exit 0
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_VENV": str(root / "venv"),
                    "STUDY_ANYTHING_DATA_DIR": str(data_dir),
                    "API_PORT": "18080",
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("exists but is not healthy at http://127.0.0.1:18080", completed.stderr)
        self.assertIn("tail -n 80", completed.stderr)
        self.assertIn("./scripts/stop_skill_mode.sh && ./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertIn("<temp-path>", completed.stderr)
        self.assertNotIn(str(root), completed.stderr)

    def test_invalid_skill_pid_file_is_removed_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            bin_dir = root / "bin"
            venv_bin = root / "venv" / "bin"
            data_dir.mkdir()
            bin_dir.mkdir()
            venv_bin.mkdir(parents=True)
            (data_dir / "api.pid").write_text(
                "not-a-pid token=supersecret123 /Users/james/private/source.txt",
                encoding="utf-8",
            )
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(
                venv_bin / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "-" ] && [ "$#" -ge 3 ]; then
                  printf "port_in_use: %s:%s is already in use\\n" "$2" "$3" >&2
                  exit 2
                fi
                if [ "${1:-}" = "-" ]; then
                  cat >/dev/null
                  exit 0
                fi
                exit 99
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_VENV": str(root / "venv"),
                    "STUDY_ANYTHING_DATA_DIR": str(data_dir),
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

            pid_file_exists = (data_dir / "api.pid").exists()

        self.assertEqual(completed.returncode, 2)
        self.assertFalse(pid_file_exists)
        self.assertIn("Removed invalid stale Skill Mode PID file", completed.stderr)
        self.assertIn("Invalid PID value was: not-a-pid token=<redacted> <local-path>", completed.stderr)
        self.assertIn("Continuing with a fresh Skill Mode startup", completed.stderr)
        self.assertIn("port is already in use", completed.stderr)
        self.assertIn("<temp-path>", completed.stderr)
        self.assertNotIn(str(root), completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)
        self.assertNotIn("/Users/james", completed.stderr)

    def test_stop_skill_mode_removes_invalid_pid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "api.pid").write_text("", encoding="utf-8")

            env = os.environ.copy()
            env["STUDY_ANYTHING_DATA_DIR"] = str(data_dir)
            completed = subprocess.run(
                ["sh", str(STOP_SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

            pid_file_exists = (data_dir / "api.pid").exists()

        self.assertEqual(completed.returncode, 0)
        self.assertFalse(pid_file_exists)
        self.assertIn("Removed invalid Skill Mode PID file", completed.stdout)
        self.assertIn("Diagnostic classification: invalid_pid_file", completed.stdout)
        self.assertIn("Invalid PID value was empty.", completed.stdout)
        self.assertIn("<temp-path>", completed.stdout)
        self.assertNotIn(str(root), completed.stdout)

    def test_stop_skill_mode_redacts_invalid_pid_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "api.pid").write_text(
                "bad-pid Authorization: Bearer supersecret123 https://user:secret@example.test/simple /Users/james/private/source.txt",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["STUDY_ANYTHING_DATA_DIR"] = str(data_dir)
            completed = subprocess.run(
                ["sh", str(STOP_SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

            pid_file_exists = (data_dir / "api.pid").exists()

        self.assertEqual(completed.returncode, 0)
        self.assertFalse(pid_file_exists)
        self.assertIn("Removed invalid Skill Mode PID file", completed.stdout)
        self.assertIn("Diagnostic classification: invalid_pid_file", completed.stdout)
        self.assertIn("bad-pid Authorization: Bearer <redacted>", completed.stdout)
        self.assertIn("https://<redacted>@example.test/simple", completed.stdout)
        self.assertIn("<local-path>", completed.stdout)
        self.assertNotIn("supersecret123", completed.stdout)
        self.assertNotIn("user:secret", completed.stdout)
        self.assertNotIn("/Users/james", completed.stdout)

    def test_bind_preflight_permission_failure_stops_before_uvicorn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            venv_bin = root / "venv" / "bin"
            bin_dir.mkdir()
            venv_bin.mkdir(parents=True)
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(
                venv_bin / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "-" ] && [ "$#" -ge 3 ]; then
                  printf "permission_denied: cannot bind %s:%s\\n" "$2" "$3" >&2
                  exit 3
                fi
                if [ "${1:-}" = "-" ]; then
                  exit 0
                fi
                printf "unexpected uvicorn launch\\n" >&2
                exit 99
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_VENV": str(root / "venv"),
                    "STUDY_ANYTHING_DATA_DIR": str(root / "data"),
                    "API_PORT": "18080",
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 3)
        self.assertIn("cannot listen on 127.0.0.1:18080", completed.stderr)
        self.assertIn("normal terminal", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertNotIn("unexpected uvicorn launch", completed.stderr)

    def test_bind_preflight_port_in_use_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            venv_bin = root / "venv" / "bin"
            bin_dir.mkdir()
            venv_bin.mkdir(parents=True)
            self.write_stub(bin_dir / "curl", "exit 7")
            self.write_stub(
                venv_bin / "python3",
                """
                if [ "${1:-}" = "-c" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "-" ] && [ "$#" -ge 3 ]; then
                  printf "port_in_use: %s:%s is already in use\\n" "$2" "$3" >&2
                  exit 2
                fi
                if [ "${1:-}" = "-" ]; then
                  exit 0
                fi
                exit 99
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "STUDY_ANYTHING_VENV": str(root / "venv"),
                    "STUDY_ANYTHING_DATA_DIR": str(root / "data"),
                    "API_PORT": "8000",
                }
            )
            completed = subprocess.run(
                ["sh", str(SKILL_MODE_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("port is already in use: 127.0.0.1:8000", completed.stderr)
        self.assertIn("API_PORT=8012", completed.stderr)

    def test_run_skill_mode_demo_step_failure_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts_dir = root / "scripts"
            bin_dir = root / "bin"
            scripts_dir.mkdir()
            bin_dir.mkdir()
            (scripts_dir / "run_skill_mode_demo.sh").write_text(
                RUN_SKILL_MODE_DEMO_SCRIPT.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.write_stub(
                scripts_dir / "launch_skill_mode.sh",
                """
                printf "Study Anything Skill API is ready.\\n"
                """,
            )
            self.write_stub(scripts_dir / "stop_skill_mode.sh", "exit 0")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "scripts/verify_skill_cli_flow.py" ]; then
                  printf "fake verifier failure Authorization: Bearer supersecret123 at https://user:secret@example.test/simple path=/Users/james/private/source.txt\\n" >&2
                  exit 42
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "PYTHON_BIN": str(bin_dir / "python3"),
                }
            )
            completed = subprocess.run(
                ["sh", str(scripts_dir / "run_skill_mode_demo.sh")],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 42)
        self.assertIn("Running deterministic Skill Mode CLI flow", completed.stdout)
        self.assertIn(
            "Study Anything Skill Mode demo step failed: Running deterministic Skill Mode CLI flow",
            completed.stderr,
        )
        self.assertIn("Command:", completed.stderr)
        self.assertIn("scripts/verify_skill_cli_flow.py", completed.stderr)
        self.assertIn("fake verifier failure", completed.stderr)
        self.assertIn("Authorization: Bearer <redacted>", completed.stderr)
        self.assertIn("https://<redacted>@example.test/simple", completed.stderr)
        self.assertIn("<local-path>", completed.stderr)
        self.assertIn("API base: http://127.0.0.1:8012", completed.stderr)
        self.assertIn(
            "Failure classification: skill_mode_demo_step_failed",
            completed.stderr,
        )
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertIn("API_PORT=8013 ./scripts/run_skill_mode_demo.sh", completed.stderr)
        self.assertIn("<temp-path>", completed.stderr)
        self.assertNotIn(str(root), completed.stderr)
        self.assertNotIn("/Users/james", completed.stderr)
        self.assertNotIn("user:secret", completed.stderr)
        self.assertNotIn("supersecret123", completed.stderr)

    def test_run_skill_mode_demo_agent_gateway_failure_mentions_two_terminals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts_dir = root / "scripts"
            bin_dir = root / "bin"
            scripts_dir.mkdir()
            bin_dir.mkdir()
            (scripts_dir / "run_skill_mode_demo.sh").write_text(
                RUN_SKILL_MODE_DEMO_SCRIPT.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.write_stub(
                scripts_dir / "launch_skill_mode.sh",
                """
                printf "Study Anything Skill API is ready.\\n"
                """,
            )
            self.write_stub(scripts_dir / "stop_skill_mode.sh", "exit 0")
            self.write_stub(
                bin_dir / "python3",
                """
                if [ "${1:-}" = "scripts/verify_skill_cli_flow.py" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "scripts/verify_agent_eval_flow.py" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "scripts/run_external_agent_evals.py" ]; then
                  exit 0
                fi
                if [ "${1:-}" = "scripts/verify_openai_compatible_gateway.py" ]; then
                  printf "Agent provider test failed because the user-owned Agent exit is not ready.\\n" >&2
                  exit 43
                fi
                exit 0
                """,
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "PYTHON_BIN": str(bin_dir / "python3"),
                }
            )
            completed = subprocess.run(
                ["sh", str(scripts_dir / "run_skill_mode_demo.sh")],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 43)
        self.assertIn("user-owned Agent exit is not ready", completed.stderr)
        self.assertIn("long-running process", completed.stderr)
        self.assertIn("terminal 2", completed.stderr)
        self.assertIn("terminal 1", completed.stderr)
        self.assertIn("Failure classification: agent_gateway_not_ready", completed.stderr)
        self.assertIn("AGENT_GATEWAY_MODE=dry_run", completed.stderr)
        self.assertIn("agent-add-http --set-default", completed.stderr)

    def test_run_skill_mode_demo_launch_failure_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts_dir = root / "scripts"
            bin_dir = root / "bin"
            scripts_dir.mkdir()
            bin_dir.mkdir()
            (scripts_dir / "run_skill_mode_demo.sh").write_text(
                RUN_SKILL_MODE_DEMO_SCRIPT.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.write_stub(
                scripts_dir / "launch_skill_mode.sh",
                """
                printf "Local Skill Mode API cannot listen on 127.0.0.1:8012 from this runner.\\n" >&2
                exit 3
                """,
            )
            self.write_stub(scripts_dir / "stop_skill_mode.sh", "exit 0")
            self.write_stub(bin_dir / "python3", "exit 0")

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:/usr/bin:/bin",
                    "PYTHON_BIN": str(bin_dir / "python3"),
                }
            )
            completed = subprocess.run(
                ["sh", str(scripts_dir / "run_skill_mode_demo.sh")],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 3)
        self.assertIn("Starting Skill Mode API", completed.stdout)
        self.assertIn(
            "Study Anything Skill Mode demo step failed: Starting Skill Mode API",
            completed.stderr,
        )
        self.assertIn("Command: sh ./scripts/launch_skill_mode.sh", completed.stderr)
        self.assertIn("API base: http://127.0.0.1:8012", completed.stderr)
        self.assertIn("Failure classification: localhost_socket_blocked", completed.stderr)
        self.assertIn("diagnose_adoption.py", completed.stderr)
        self.assertIn("normal terminal or host shell", completed.stderr)


if __name__ == "__main__":
    unittest.main()
