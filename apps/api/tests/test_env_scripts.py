from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]


def load_script(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup_env = load_script("setup_env", "scripts/setup_env.py")
check_env = load_script("check_env", "scripts/check_env.py")
smoke_core = load_script("smoke_core", "scripts/smoke_core.py")


class EnvScriptTests(unittest.TestCase):
    def test_core_smoke_runtime_failure_payload_is_actionable_and_redacted(self) -> None:
        payload = smoke_core.runtime_failure_payload(
            classification="python_version_unsupported",
            diagnostic=(
                "smoke_core failed at /Users/james/private/repo "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            ),
            details={"python_version": "3.9.6"},
        )
        serialized = json.dumps(payload, sort_keys=True)

        self.assertEqual(payload["schema_version"], "core-smoke-error-v1")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertIn(".venv/bin/python scripts/smoke_core.py", payload["next_steps"])
        self.assertIn("python3 scripts/setup_env.py", payload["next_steps"])
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secrets_recorded"])
        self.assertIn("<local-path>", serialized)
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertNotIn("/Users/james", serialized)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", serialized)

    def test_core_smoke_runs_with_repo_python(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/smoke_core.py"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("completed", completed.stdout)
        self.assertIn("level", completed.stdout)

    def run_setup_env(self, *args: str) -> tuple[int | None, str]:
        stderr = StringIO()
        argv = ["setup_env.py", *args]
        with patch.object(sys, "argv", argv):
            with patch("sys.stderr", stderr):
                try:
                    setup_env.main()
                except SystemExit as exc:
                    return exc.code, stderr.getvalue()
        return None, stderr.getvalue()

    def run_setup_env_with_stdout(self, *args: str) -> tuple[int | None, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        argv = ["setup_env.py", *args]
        with patch.object(sys, "argv", argv):
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                try:
                    setup_env.main()
                except SystemExit as exc:
                    return exc.code, stdout.getvalue(), stderr.getvalue()
        return None, stdout.getvalue(), stderr.getvalue()

    def run_check_env(self, *args: str) -> tuple[int | None, str]:
        stderr = StringIO()
        argv = ["check_env.py", *args]
        with patch.object(sys, "argv", argv):
            with patch("sys.stderr", stderr):
                try:
                    check_env.main()
                except SystemExit as exc:
                    return exc.code, stderr.getvalue()
        return None, stderr.getvalue()

    def run_check_env_with_stdout(self, *args: str) -> tuple[int | None, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        argv = ["check_env.py", *args]
        with patch.object(sys, "argv", argv):
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                try:
                    check_env.main()
                except SystemExit as exc:
                    return exc.code, stdout.getvalue(), stderr.getvalue()
        return None, stdout.getvalue(), stderr.getvalue()

    def test_skill_mode_launcher_redacts_bearer_tokens_in_logs(self) -> None:
        script = (REPO_ROOT / "scripts" / "launch_skill_mode.sh").read_text(encoding="utf-8")

        self.assertIn("[Aa]uthorization", script)
        self.assertIn("Bearer <redacted>", script)
        self.assertIn("sk-<redacted>", script)

    def test_skill_mode_launcher_bounds_dependency_install_for_new_users(self) -> None:
        script = (REPO_ROOT / "scripts" / "launch_skill_mode.sh").read_text(encoding="utf-8")

        self.assertIn("SKILL_PIP_INSTALL_TIMEOUT_SECONDS", script)
        self.assertIn("PIP_INSTALL_TIMEOUT_SECONDS", script)
        self.assertIn("PIP_DEFAULT_TIMEOUT", script)
        self.assertIn("PIP_RETRIES", script)
        self.assertIn("PIP_NO_INPUT", script)
        self.assertIn("--timeout", script)
        self.assertIn("--retries", script)
        self.assertIn("run_pip_install", script)
        self.assertIn("requirements/locked-skill.txt", script)
        self.assertIn("--require-hashes", script)
        self.assertIn("--no-deps", script)
        self.assertIn("dependency installation timed out after", script)
        self.assertIn("SKILL_PIP_INSTALL_TIMEOUT_SECONDS=1200", script)

    def test_skill_mode_demo_classifies_dependency_install_timeout(self) -> None:
        script = (REPO_ROOT / "scripts" / "run_skill_mode_demo.sh").read_text(encoding="utf-8")

        self.assertIn("dependency installation timed out", script)
        self.assertIn("SKILL_PIP_INSTALL_TIMEOUT_SECONDS=1200 ./scripts/run_skill_mode_demo.sh", script)
        self.assertIn("Failure classification: %s", script)

    def test_beginner_launcher_help_exits_before_runtime_checks(self) -> None:
        completed = subprocess.run(
            ["sh", "scripts/start_here.sh", "--help"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("Study Anything beginner launcher", completed.stdout)
        self.assertIn("START_HERE.command", completed.stdout)
        self.assertIn("./scripts/start_here.sh --keep-running", completed.stdout)
        self.assertIn("./scripts/start_here.sh --foreground", completed.stdout)
        self.assertIn("./scripts/start_here.sh --docker", completed.stdout)
        self.assertIn("./scripts/start_here.sh --check-only", completed.stdout)
        self.assertEqual(completed.stderr, "")

    def test_beginner_launcher_unknown_option_is_actionable(self) -> None:
        completed = subprocess.run(
            ["sh", "scripts/start_here.sh", "--bad-option"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )

        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 1)
        self.assertIn("Unknown start_here.sh option: --bad-option", output)
        self.assertIn("Recommended first command", output)
        self.assertNotIn(str(REPO_ROOT), output)

    def test_beginner_launcher_declares_safe_first_run_paths(self) -> None:
        script = (REPO_ROOT / "scripts" / "start_here.sh").read_text(encoding="utf-8")

        self.assertIn("run_demo", script)
        self.assertIn("sh ./scripts/run_skill_mode_demo.sh", script)
        self.assertIn("run_keep_running", script)
        self.assertIn("sh ./scripts/launch_skill_mode.sh", script)
        self.assertIn("run_foreground", script)
        self.assertIn("SKILL_API_FOREGROUND=true exec sh ./scripts/launch_skill_mode.sh", script)
        self.assertIn("run_docker", script)
        self.assertIn("sh ./scripts/launch_self_host.sh", script)
        self.assertIn("run_check_only", script)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", script)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", script)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", script)
        self.assertIn("START_HERE.command", script)
        self.assertIn("QUICKSTART.md", script)
        self.assertIn("docs/getting-started.md", script)
        self.assertIn("Do not paste raw source text", script)
        self.assertNotIn('printf "-', script)

    def test_macos_one_click_launcher_runs_beginner_demo(self) -> None:
        script_path = REPO_ROOT / "START_HERE.command"
        script = script_path.read_text(encoding="utf-8")

        self.assertTrue(os.access(script_path, os.X_OK))
        self.assertIn("./scripts/start_here.sh --demo", script)
        self.assertIn("Done. You have proved the local learning loop once.", script)
        self.assertIn("QUICKSTART.md", script)
        self.assertIn("diagnose_adoption.py", script)

    def test_skill_mode_launcher_help_exits_before_runtime_checks(self) -> None:
        completed = subprocess.run(
            ["sh", "scripts/launch_skill_mode.sh", "--help"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("Usage: ./scripts/launch_skill_mode.sh", completed.stdout)
        self.assertIn("--foreground", completed.stdout)
        self.assertIn("API_PORT=8012", completed.stdout)
        self.assertEqual(completed.stderr, "")

    def test_skill_mode_launcher_unknown_option_explains_port_configuration(self) -> None:
        completed = subprocess.run(
            ["sh", "scripts/launch_skill_mode.sh", "--port"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )

        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 1)
        self.assertIn("Unknown launch_skill_mode.sh option: --port", output)
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", output)
        self.assertIn("Usage: ./scripts/launch_skill_mode.sh", output)

    def test_skill_mode_demo_invalid_port_has_targeted_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["API_PORT"] = "bad"
            env["STUDY_ANYTHING_DATA_DIR"] = str(Path(tmp) / "demo-data")
            completed = subprocess.run(
                ["sh", "scripts/run_skill_mode_demo.sh"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=20,
            )

        output = completed.stdout + completed.stderr
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Detected invalid API_PORT configuration", output)
        self.assertIn("unset API_PORT", output)
        self.assertIn("API_PORT=8013 ./scripts/run_skill_mode_demo.sh", output)
        self.assertIn("diagnose_adoption.py", output)
        self.assertNotIn(str(REPO_ROOT), output)

    def test_skill_mode_launcher_reads_api_port_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text('export API_PORT="not-a-port" # local override\n', encoding="utf-8")
            env = os.environ.copy()
            env.pop("API_PORT", None)
            env["STUDY_ANYTHING_ENV_FILE"] = str(env_file)
            env["STUDY_ANYTHING_DATA_DIR"] = str(Path(tmp) / "skill-data")
            completed = subprocess.run(
                ["sh", "scripts/launch_skill_mode.sh"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=20,
            )

        output = completed.stdout + completed.stderr
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Invalid API_PORT=not-a-port for Skill Mode", output)
        self.assertIn("API_PORT must be a number from 1 to 65535", output)
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", output)
        self.assertIn("diagnose_adoption.py", output)
        self.assertNotIn(str(env_file), output)
        self.assertNotIn(str(Path(tmp)), output)

    def test_skill_mode_launcher_port_in_use_has_stop_and_lsof_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_venv = root / "venv"
            fake_bin = root / "bin"
            data_dir = root / "skill-data"
            fake_venv_bin = fake_venv / "bin"
            fake_venv_bin.mkdir(parents=True)
            fake_bin.mkdir()
            fake_python = fake_venv_bin / "python3"
            fake_python.write_text(
                "#!/usr/bin/env sh\n"
                "if [ \"$1\" = \"-c\" ]; then exit 0; fi\n"
                "if [ \"$1\" = \"-\" ] && [ -n \"$2\" ]; then\n"
                "  printf 'port_in_use: 127.0.0.1:18080 is already in use\\n' >&2\n"
                "  exit 2\n"
                "fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            fake_lsof = fake_bin / "lsof"
            fake_lsof.write_text(
                "#!/usr/bin/env sh\n"
                "printf 'COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\\n'\n"
                "printf 'Python 321 user 3u IPv4 0x0 0t0 TCP 127.0.0.1:18080 (LISTEN)\\n'\n",
                encoding="utf-8",
            )
            fake_lsof.chmod(0o755)
            env = os.environ.copy()
            env["STUDY_ANYTHING_VENV"] = str(fake_venv)
            env["STUDY_ANYTHING_DATA_DIR"] = str(data_dir)
            env["API_PORT"] = "18080"
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            completed = subprocess.run(
                ["sh", "scripts/launch_skill_mode.sh"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=20,
            )

        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertIn("Skill Mode API port is already in use: 127.0.0.1:18080", output)
        self.assertIn("Detected listener:", output)
        self.assertIn("./scripts/stop_skill_mode.sh", output)
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", output)
        self.assertIn("lsof -nP -iTCP:18080 -sTCP:LISTEN", output)
        self.assertIn("python3 scripts/diagnose_adoption.py", output)
        self.assertNotIn(str(root), output)

    def test_api_smoke_reads_api_port_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_file = root / ".env"
            env_file.write_text('export API_PORT="18080" # local override\n', encoding="utf-8")
            fake_bin = root / "bin"
            fake_bin.mkdir()
            curl_log = root / "curl.log"
            fake_curl = fake_bin / "curl"
            fake_curl.write_text(
                "#!/usr/bin/env sh\n"
                "printf '%s\\n' \"$*\" >> \"$CURL_LOG\"\n"
                "printf '{}'\n",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            env.pop("API_BASE", None)
            env.pop("STUDY_ANYTHING_API_BASE", None)
            env["STUDY_ANYTHING_ENV_FILE"] = str(env_file)
            env["CURL_LOG"] = str(curl_log)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            completed = subprocess.run(
                ["sh", "scripts/verify_api_smoke.sh"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue(curl_log.exists(), completed.stdout + completed.stderr)
            calls = curl_log.read_text(encoding="utf-8")
        self.assertIn("http://127.0.0.1:18080/v1/health", calls)
        self.assertIn("http://127.0.0.1:18080/v1/system/status", calls)
        self.assertIn("http://127.0.0.1:18080/v1/plugins", calls)

    def test_api_smoke_failure_has_actionable_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_curl = fake_bin / "curl"
            fake_curl.write_text(
                "#!/usr/bin/env sh\n"
                "printf 'curl: (7) Failed to connect to 127.0.0.1 port 18080\\n' >&2\n"
                "exit 7\n",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            env = os.environ.copy()
            env["API_BASE"] = "http://127.0.0.1:18080"
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            completed = subprocess.run(
                ["sh", "scripts/verify_api_smoke.sh"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=20,
            )

        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 7)
        self.assertIn("Study Anything API smoke failed: health endpoint is not reachable", output)
        self.assertIn("Endpoint: http://127.0.0.1:18080/v1/health", output)
        self.assertIn("Failure classification: api_unreachable", output)
        self.assertIn("./scripts/launch_skill_mode.sh", output)
        self.assertIn("API_BASE=http://127.0.0.1:<port> sh scripts/verify_api_smoke.sh", output)
        self.assertIn("python3 scripts/diagnose_adoption.py", output)
        self.assertIn("normal terminal or host shell", output)

    def test_stop_skill_mode_reports_env_file_port_listener_when_pid_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_file = root / ".env"
            data_dir = root / "skill-data"
            fake_bin = root / "bin"
            fake_bin.mkdir()
            data_dir.mkdir()
            env_file.write_text('export API_PORT="18080" # local override\n', encoding="utf-8")
            fake_lsof = fake_bin / "lsof"
            fake_lsof.write_text(
                "#!/usr/bin/env sh\n"
                "printf 'COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\\n'\n"
                "printf 'Python 123 user 3u IPv4 0x0 0t0 TCP 127.0.0.1:18080 (LISTEN)\\n'\n",
                encoding="utf-8",
            )
            fake_lsof.chmod(0o755)
            env = os.environ.copy()
            env.pop("API_PORT", None)
            env["STUDY_ANYTHING_ENV_FILE"] = str(env_file)
            env["STUDY_ANYTHING_DATA_DIR"] = str(data_dir)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            completed = subprocess.run(
                ["sh", "scripts/stop_skill_mode.sh"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=20,
            )

        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Study Anything Skill API is not running from its PID file.", output)
        self.assertIn("Expected API base from current env: http://127.0.0.1:18080", output)
        self.assertIn("Diagnostic classification: port_still_listening_without_pid", output)
        self.assertIn("warn  port 18080 is still listening", output)
        self.assertIn("started outside ./scripts/launch_skill_mode.sh", output)
        self.assertIn("python3 scripts/diagnose_adoption.py", output)
        self.assertNotIn(str(root), output)

    def test_setup_env_missing_template_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, stderr = self.run_setup_env(
                "--example",
                str(root / "missing.env.example"),
                "--output",
                str(root / ".env"),
            )

        self.assertEqual(code, 1)
        self.assertIn("setup_env failed", stderr)
        self.assertIn("Classification: template_missing", stderr)
        self.assertIn("Env template is missing", stderr)
        self.assertIn("Next steps:", stderr)
        self.assertIn("Machine-readable report:", stderr)
        self.assertIn("--json", stderr)
        self.assertIn("--example", stderr)
        self.assertIn("<env-file>", stderr)
        self.assertNotIn(str(root), stderr)

    def test_setup_env_missing_output_directory_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / ".env.example"
            template.write_text("APP_ENV=development\nPOSTGRES_PASSWORD=change-me\n", encoding="utf-8")
            code, stderr = self.run_setup_env(
                "--example",
                str(template),
                "--output",
                str(root / "missing" / ".env"),
            )

        self.assertEqual(code, 1)
        self.assertIn("Classification: output_directory_missing", stderr)
        self.assertIn("Output directory does not exist", stderr)
        self.assertIn("Next steps:", stderr)
        self.assertIn("Machine-readable report:", stderr)
        self.assertIn("--json", stderr)
        self.assertIn("--output", stderr)
        self.assertIn("check_env.py", stderr)
        self.assertIn("<env-dir>", stderr)
        self.assertNotIn(str(root), stderr)

    def test_setup_env_existing_output_is_successful_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / ".env"
            output.write_text("APP_ENV=development\nPOSTGRES_PASSWORD=existing\n", encoding="utf-8")
            code, stdout, stderr = self.run_setup_env_with_stdout(
                "--example",
                str(root / "missing.env.example"),
                "--output",
                str(output),
            )
            content = output.read_text(encoding="utf-8")

        self.assertIsNone(code)
        self.assertEqual(stderr, "")
        self.assertIn("already exists", stdout)
        self.assertIn("leaving it unchanged", stdout)
        self.assertIn("<env-file>", stdout)
        self.assertNotIn(str(output), stdout)
        self.assertEqual(content, "APP_ENV=development\nPOSTGRES_PASSWORD=existing\n")

    def test_setup_env_text_create_redacts_absolute_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / ".env.example"
            output = root / ".env"
            template.write_text("APP_ENV=development\nPOSTGRES_PASSWORD=change-me\n", encoding="utf-8")
            code, stdout, stderr = self.run_setup_env_with_stdout(
                "--example",
                str(template),
                "--output",
                str(output),
            )
            output_mode = output.stat().st_mode & 0o777

        self.assertIsNone(code)
        self.assertEqual(stderr, "")
        self.assertIn("Created <env-file> with generated local secrets.", stdout)
        self.assertNotIn(str(root), stdout)
        if os.name != "nt":
            self.assertEqual(output_mode, 0o600)

    def test_setup_env_json_create_is_redacted_and_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / ".env.example"
            output = root / ".env"
            template.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "POSTGRES_PASSWORD=change-me-study-postgres",
                        "DATABASE_URL=postgresql://study:change-me-study-postgres@app-postgres:5432/study_anything",
                        "NEXTAUTH_SECRET=change-me-nextauth-secret",
                        "LANGFUSE_ENCRYPTION_KEY=replace-with-generated-local-key",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_setup_env_with_stdout(
                "--example",
                str(template),
                "--output",
                str(output),
                "--json",
            )
            content = output.read_text(encoding="utf-8")

        self.assertIsNone(code)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["schema_version"], "setup-env-result-v1")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["action"], "created")
        self.assertEqual(payload["output"], "<env-file>")
        self.assertEqual(payload["example"], "<env-file>")
        self.assertFalse(payload["privacy"]["generated_secret_values_included"])
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertNotIn(str(output), stdout)
        self.assertNotIn("change-me-nextauth-secret", stdout)
        self.assertNotIn("change-me-nextauth-secret", content)
        self.assertIn("python3 scripts/check_env.py", " ".join(payload["next_steps"]))

    def test_setup_env_json_existing_output_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / ".env"
            output.write_text("APP_ENV=development\nPOSTGRES_PASSWORD=existing\n", encoding="utf-8")
            code, stdout, stderr = self.run_setup_env_with_stdout(
                "--example",
                str(root / "missing.env.example"),
                "--output",
                str(output),
                "--json",
            )
            content = output.read_text(encoding="utf-8")

        self.assertIsNone(code)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["action"], "unchanged")
        self.assertIn("--force", " ".join(payload["next_steps"]))
        self.assertEqual(content, "APP_ENV=development\nPOSTGRES_PASSWORD=existing\n")

    def test_setup_env_json_failure_is_classified_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_template = root / "missing.env.example"
            output = root / "missing-dir" / ".env"
            code, stdout, stderr = self.run_setup_env_with_stdout(
                "--example",
                str(missing_template),
                "--output",
                str(output),
                "--json",
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["action"], "failed")
        self.assertEqual(payload["error_code"], "template_missing")
        self.assertEqual(payload["output"], "<env-file>")
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertNotIn(str(missing_template), stdout)
        self.assertNotIn(str(output), stdout)
        self.assertIn("--example", " ".join(payload["next_steps"]))

    def test_check_env_missing_file_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stderr = self.run_check_env("--env", str(Path(tmp) / ".env"))

        self.assertEqual(code, 1)
        self.assertIn("fail  Missing <env-file>.", stderr)
        self.assertIn("setup_env.py", stderr)
        self.assertIn("Recovery:", stderr)
        self.assertIn("Run from the repository root", stderr)
        self.assertIn("<env-file>", stderr)
        self.assertNotIn(str(Path(tmp) / ".env"), stderr)

    def test_check_env_non_utf8_file_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_bytes(b"APP_ENV=development\nPOSTGRES_PASSWORD=\xff\n")
            code, stderr = self.run_check_env("--env", str(env_file))

        self.assertEqual(code, 1)
        self.assertIn("fail  <env-file> is not UTF-8 text.", stderr)
        self.assertIn("not UTF-8 text", stderr)
        self.assertIn("Save it as UTF-8", stderr)
        self.assertIn("Recovery:", stderr)
        self.assertIn("<env-file>", stderr)
        self.assertNotIn(str(env_file), stderr)
        self.assertNotIn("not-a-port", stderr)

    def test_check_env_strict_secret_failure_includes_recovery_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=production",
                        "POSTGRES_PASSWORD=change-me-study-postgres",
                        "LANGFUSE_POSTGRES_PASSWORD=change-me-langfuse-postgres",
                        "NEXTAUTH_SECRET=change-me-nextauth-secret",
                        "LANGFUSE_SALT=change-me-langfuse-salt",
                        "LANGFUSE_ENCRYPTION_KEY=" + "0" * 64,
                        "CLICKHOUSE_PASSWORD=change-me-clickhouse",
                        "MINIO_ROOT_PASSWORD=change-me-minio",
                        "REDIS_AUTH=change-me-redis",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout("--env", str(env_file), "--strict")

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("fail  POSTGRES_PASSWORD is still a default or placeholder value.", stderr)
        self.assertIn("python3 scripts/setup_env.py --force --output", stderr)
        self.assertIn("python3 scripts/check_env.py --env", stderr)
        self.assertIn("<env-file>", stderr)
        self.assertNotIn(str(env_file), stderr)

    def test_check_env_missing_database_url_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "SESSION_STORE=postgres",
                        "POSTGRES_PASSWORD=local-strong-postgres",
                        "LANGFUSE_POSTGRES_PASSWORD=local-strong-langfuse-postgres",
                        "NEXTAUTH_SECRET=local-strong-nextauth",
                        "LANGFUSE_SALT=local-strong-salt",
                        "LANGFUSE_ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                        "CLICKHOUSE_PASSWORD=local-strong-clickhouse",
                        "MINIO_ROOT_PASSWORD=local-strong-minio",
                        "REDIS_AUTH=local-strong-redis",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout("--env", str(env_file))

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("fail  SESSION_STORE=postgres requires DATABASE_URL.", stderr)
        self.assertIn("Set DATABASE_URL", stderr)
        self.assertIn("setup_env.py --force", stderr)
        self.assertIn("<env-file>", stderr)
        self.assertNotIn(str(env_file), stderr)

    def test_check_env_invalid_port_fails_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "POSTGRES_PASSWORD=local-strong-postgres",
                        "LANGFUSE_POSTGRES_PASSWORD=local-strong-langfuse-postgres",
                        "NEXTAUTH_SECRET=local-strong-nextauth",
                        "LANGFUSE_SALT=local-strong-salt",
                        "LANGFUSE_ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                        "CLICKHOUSE_PASSWORD=local-strong-clickhouse",
                        "MINIO_ROOT_PASSWORD=local-strong-minio",
                        "REDIS_AUTH=local-strong-redis",
                        "APP_POSTGRES_PORT=not-a-port",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout("--env", str(env_file))

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("fail  APP_POSTGRES_PORT must be a TCP port", stderr)
        self.assertIn("APP_POSTGRES_PORT=5433 ./scripts/launch_self_host.sh", stderr)
        self.assertIn("./scripts/doctor.sh", stderr)
        self.assertIn("<env-file>", stderr)
        self.assertNotIn(str(env_file), stderr)

    def test_check_env_accepts_exported_quoted_port_with_inline_comment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "POSTGRES_PASSWORD=local-strong-postgres",
                        "LANGFUSE_POSTGRES_PASSWORD=local-strong-langfuse-postgres",
                        "NEXTAUTH_SECRET=local-strong-nextauth",
                        "LANGFUSE_SALT=local-strong-salt",
                        "LANGFUSE_ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                        "CLICKHOUSE_PASSWORD=local-strong-clickhouse",
                        "MINIO_ROOT_PASSWORD=local-strong-minio",
                        "REDIS_AUTH=local-strong-redis",
                        'export API_PORT="18081" # local override',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout("--env", str(env_file), "--strict")

        self.assertIsNone(code)
        self.assertEqual(stderr, "")
        self.assertIn("ok    <env-file> is valid for APP_ENV=development.", stdout)

    def test_check_env_json_invalid_ports_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "POSTGRES_PASSWORD=local-strong-postgres",
                        "LANGFUSE_POSTGRES_PASSWORD=local-strong-langfuse-postgres",
                        "NEXTAUTH_SECRET=local-strong-nextauth",
                        "LANGFUSE_SALT=local-strong-salt",
                        "LANGFUSE_ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                        "CLICKHOUSE_PASSWORD=local-strong-clickhouse",
                        "MINIO_ROOT_PASSWORD=local-strong-minio",
                        "REDIS_AUTH=local-strong-redis",
                        "API_PORT=0",
                        "LANGFUSE_PORT=abc",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout(
                "--env",
                str(env_file),
                "--json",
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["schema_version"], "env-check-result-v1")
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["problem_count"], 2)
        self.assertEqual(
            [item["key"] for item in payload["problems"]],
            ["API_PORT", "LANGFUSE_PORT"],
        )
        self.assertEqual(
            {item["code"] for item in payload["problems"]},
            {"invalid_port_value"},
        )
        self.assertIn("API_PORT=8000 ./scripts/launch_skill_mode.sh", stdout)
        self.assertIn("LANGFUSE_PORT=3000 ./scripts/launch_self_host.sh", stdout)
        self.assertNotIn(str(env_file), stdout)

    def test_check_env_duplicate_active_host_ports_fail_before_compose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "STACK_PROFILE=full",
                        "POSTGRES_PASSWORD=local-strong-postgres",
                        "LANGFUSE_POSTGRES_PASSWORD=local-strong-langfuse-postgres",
                        "NEXTAUTH_SECRET=local-strong-nextauth",
                        "LANGFUSE_SALT=local-strong-salt",
                        "LANGFUSE_ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                        "CLICKHOUSE_PASSWORD=local-strong-clickhouse",
                        "MINIO_ROOT_PASSWORD=local-strong-minio",
                        "REDIS_AUTH=local-strong-redis",
                        "API_PORT=8000",
                        "LANGFUSE_PORT=8000",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout(
                "--env",
                str(env_file),
                "--json",
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["problem_count"], 1)
        problem = payload["problems"][0]
        self.assertEqual(problem["code"], "duplicate_host_port_value")
        self.assertIn("active stack profile", problem["message"])
        self.assertIn("API_PORT, LANGFUSE_PORT", problem["message"])
        self.assertIn("STACK_PROFILE=core ./scripts/launch_self_host.sh", stdout)
        self.assertNotIn(str(env_file), stdout)

    def test_check_env_internal_falkordb_port_does_not_conflict_with_redis_host_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "STACK_PROFILE=full",
                        "POSTGRES_PASSWORD=local-strong-postgres",
                        "LANGFUSE_POSTGRES_PASSWORD=local-strong-langfuse-postgres",
                        "NEXTAUTH_SECRET=local-strong-nextauth",
                        "LANGFUSE_SALT=local-strong-salt",
                        "LANGFUSE_ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                        "CLICKHOUSE_PASSWORD=local-strong-clickhouse",
                        "MINIO_ROOT_PASSWORD=local-strong-minio",
                        "REDIS_AUTH=local-strong-redis",
                        "REDIS_PORT=6379",
                        "FALKORDB_PORT=6379",
                        "FALKORDB_HOST_PORT=6378",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout("--env", str(env_file))

        self.assertIsNone(code)
        self.assertEqual(stderr, "")
        self.assertIn("valid for APP_ENV=development", stdout)

    def test_check_env_unsupported_stack_profile_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "STACK_PROFILE=everything",
                        "POSTGRES_PASSWORD=local-strong-postgres",
                        "LANGFUSE_POSTGRES_PASSWORD=local-strong-langfuse-postgres",
                        "NEXTAUTH_SECRET=local-strong-nextauth",
                        "LANGFUSE_SALT=local-strong-salt",
                        "LANGFUSE_ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                        "CLICKHOUSE_PASSWORD=local-strong-clickhouse",
                        "MINIO_ROOT_PASSWORD=local-strong-minio",
                        "REDIS_AUTH=local-strong-redis",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout("--env", str(env_file))

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("STACK_PROFILE must be one of core, smoke, or full", stderr)
        self.assertIn("STACK_PROFILE=core ./scripts/launch_self_host.sh", stderr)
        self.assertIn("./scripts/doctor.sh", stderr)
        self.assertNotIn(str(env_file), stderr)

    def test_check_env_json_failure_is_redacted_and_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            secret = "change-me-nextauth-secret"
            # Synthetic placeholder written only to prove that the checker redacts it.
            # codeql[py/clear-text-storage-sensitive-data]
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=production",
                        f"NEXTAUTH_SECRET={secret}",
                        "LANGFUSE_ENCRYPTION_KEY=not-hex",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout(
                "--env",
                str(env_file),
                "--strict",
                "--json",
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["schema_version"], "env-check-result-v1")
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["env_file"], "<env-file>")
        self.assertEqual(payload["problem_count"], 10)
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secret_values_included"])
        self.assertFalse(payload["privacy"]["raw_env_values_included"])
        self.assertNotIn(secret, stdout)
        self.assertNotIn(str(env_file), stdout)
        self.assertIn("weak_or_placeholder_secret", {item["code"] for item in payload["problems"]})
        self.assertIn("invalid_langfuse_encryption_key", {item["code"] for item in payload["problems"]})
        self.assertIn("production_api_auth_required", {item["code"] for item in payload["problems"]})
        self.assertIn("empty_agent_endpoint_allowlist", {item["code"] for item in payload["problems"]})

    def test_check_env_production_agent_allowlist_is_actionable_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=production",
                        "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=operator",
                        "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST=http://private-agent.example/invoke?token=secret",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout(
                "--env",
                str(env_file),
                "--json",
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        codes = {item["code"] for item in payload["problems"]}
        self.assertIn("production_agent_allowlist_required", codes)
        self.assertIn("invalid_agent_endpoint_allowlist_origin", codes)
        self.assertNotIn("private-agent.example", stdout)
        self.assertNotIn("token=secret", stdout)

    def test_check_env_accepts_production_agent_https_allowlist(self) -> None:
        issues = check_env.validate_agent_endpoint_allowlist(
            "https://agent.example,https://second-agent.example:8443/",
            Path(".env"),
        )

        self.assertEqual(issues, [])

    def test_check_env_accepts_production_oidc_with_static_jwks(self) -> None:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(
            private_key.public_key(),
            as_dict=True,
        )
        public_jwk.update({"kid": "test-signing-key", "alg": "RS256", "use": "sig"})
        jwks = json.dumps(
            {"keys": [public_jwk]},
            separators=(",", ":"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=production",
                        "API_BIND_HOST=0.0.0.0",
                        "STUDY_ANYTHING_API_AUTH_MODE=oidc_jwt",
                        "STUDY_ANYTHING_OIDC_ISSUER=https://identity.example",
                        "STUDY_ANYTHING_OIDC_AUDIENCE=study-anything-api",
                        "STUDY_ANYTHING_OIDC_TENANT_CLAIM=org_id",
                        f"STUDY_ANYTHING_OIDC_JWKS_JSON={jwks}",
                        "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=allowlist",
                        "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST=https://agent.example",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout(
                "--env",
                str(env_file),
                "--json",
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        codes = {item["code"] for item in payload["problems"]}
        self.assertNotIn("production_api_auth_required", codes)
        self.assertNotIn("network_bind_requires_token_auth", codes)
        self.assertNotIn("invalid_oidc_configuration", codes)

    def test_check_env_rejects_bad_oidc_without_leaking_jwks(self) -> None:
        private_needle = "private-signing-material-must-not-leak"
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "STUDY_ANYTHING_API_AUTH_MODE=oidc_jwt",
                        "STUDY_ANYTHING_OIDC_ISSUER=http://identity.example",
                        "STUDY_ANYTHING_OIDC_AUDIENCE=study-anything-api",
                        f"STUDY_ANYTHING_OIDC_JWKS_JSON={private_needle}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout(
                "--env",
                str(env_file),
                "--json",
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertIn(
            "invalid_oidc_configuration",
            {item["code"] for item in payload["problems"]},
        )
        self.assertNotIn(private_needle, stdout)
        self.assertNotIn(str(env_file), stdout)

    def test_check_env_rejects_separator_only_agent_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=allowlist",
                        "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST=, ,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self.run_check_env_with_stdout(
                "--env",
                str(env_file),
                "--json",
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertIn(
            "empty_agent_endpoint_allowlist",
            {item["code"] for item in payload["problems"]},
        )

    def test_check_env_json_missing_file_redacts_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            code, stdout, stderr = self.run_check_env_with_stdout(
                "--env",
                str(env_file),
                "--json",
            )

        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["error_code"] if "error_code" in payload else payload["status"], "fail")
        self.assertEqual(payload["env_file"], "<env-file>")
        self.assertEqual(payload["problems"][0]["code"], "env_file_unreadable")
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertNotIn(str(env_file), stdout)


if __name__ == "__main__":
    unittest.main()
