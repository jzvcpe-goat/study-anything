#!/usr/bin/env python3
"""Verify Study Anything from a disposable clean clone.

This is the adoption smoke for external users: clone the repo into a temporary
directory, create local env files, run Skill Mode, verify the OpenAI-compatible
gateway dry-run path, and optionally run the Promptfoo external eval wrapper.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import is_localhost_socket_blocked, redact_diagnostic, verifier_name_from_file


class CleanCloneAdoptionError(RuntimeError):
    """Readable adoption-smoke failure."""


VERIFIER_NAME = verifier_name_from_file(__file__)
FORBIDDEN_LITERALS = (
    "AGENT_LLM_API_KEY=",
    "MOONSHOT_API_KEY=",
    "OPENAI_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


def output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def sanitize_text(value: str | bytes | None) -> str:
    return redact_diagnostic(output_text(value)).strip()[:1600]


SECRET_JSON_KEYS = {"api_key", "apikey", "key", "secret", "token", "password", "credential"}
REDACTION_SELF_CHECK_MARKERS = ("/private/" + "tmp/study-anything-example", "<temp-path>")


def sanitize_json_value(value: Any, *, key_hint: str | None = None) -> Any:
    if isinstance(value, str):
        normalized_key = (key_hint or "").lower().replace("-", "_")
        if normalized_key in SECRET_JSON_KEYS or any(
            marker in normalized_key
            for marker in ("api_key", "access_token", "secret", "token", "password")
        ):
            return "<redacted>"
        return sanitize_text(value)
    if isinstance(value, bytes):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_json_value(item, key_hint=key_hint) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize_json_value(item, key_hint=str(key)) for key, item in value.items()}
    return value


def command_failure_message(
    command: list[str],
    *,
    returncode: int | None,
    stdout: str | bytes | None,
    stderr: str | bytes | None,
    timeout_seconds: int | None = None,
) -> str:
    status = f"timed out after {timeout_seconds}s" if timeout_seconds is not None else f"exited with {returncode}"
    return (
        f"Clean-clone adoption command {status}: {' '.join(command)}\n"
        f"stdout:\n{sanitize_text(stdout) or '(empty)'}\n"
        f"stderr:\n{sanitize_text(stderr) or '(empty)'}\n"
        "Recovery:\n"
        "- Run `python3 scripts/diagnose_adoption.py` in the source checkout for a redacted local report.\n"
        "- Run `./scripts/launch_skill_mode.sh` directly to isolate local API startup issues.\n"
        "- If localhost sockets are blocked, rerun from a normal terminal or host shell.\n"
        "- If dependency installation failed, configure PIP_INDEX_URL or retry from a networked shell.\n"
        "- If pip downloads are slow, retry with SKILL_PIP_INSTALL_TIMEOUT_SECONDS=1200."
    )


def format_cli_failure(exc: BaseException) -> str:
    return format_failure_for_human(failure_report(exc))


def classify_failure(message: str) -> str:
    lowered = message.lower()
    if (
        "blocks localhost" in lowered
        or "localhost listening sockets" in lowered
        or "could not bind to localhost" in lowered
        or "cannot reserve a localhost port" in lowered
        or "operation not permitted" in lowered
        or "permission denied" in lowered
        or "localhost_socket_blocked" in lowered
    ):
        return "localhost_socket_blocked"
    if "--api-port must be between" in lowered or "--promptfoo-api-port must be between" in lowered:
        return "invalid_cli_input"
    if (
        "python dependency installation failed" in lowered
        or "dependency installation timed out" in lowered
        or "skill_pip_install_timeout_seconds" in lowered
        or "could not reach pypi" in lowered
        or "pip subprocess to install build dependencies" in lowered
        or "could not find a version that satisfies" in lowered
        or "no matching distribution found" in lowered
        or "pip_index_url" in lowered
    ):
        return "dependency_install_failed"
    if "timed out after" in lowered:
        return "clean_clone_timeout"
    if "bounded skill mode demo verification step failed" in lowered:
        return "skill_mode_demo_step_failed"
    if "skill mode did not create .venv/bin/python" in lowered:
        return "skill_mode_venv_missing"
    if "python 3.11 or newer is required" in lowered:
        return "python_version_missing"
    if "promptfoo did not pass" in lowered:
        return "promptfoo_eval_failed"
    if "gateway" in lowered and ("dry-run" in lowered or "dry_run" in lowered):
        return "gateway_dry_run_failed"
    if "clean-clone adoption command" in lowered:
        return "clean_clone_command_failed"
    return "clean_clone_adoption_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "python3 scripts/diagnose_adoption.py",
        "./scripts/run_skill_mode_demo.sh",
        "If localhost sockets are blocked, rerun from a normal terminal or host shell.",
        "If dependency installation failed, configure PIP_INDEX_URL or retry from a networked shell.",
        "python3 scripts/verify_clean_clone_adoption.py --copy-worktree",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run the adoption smoke from a normal terminal or host shell that permits localhost listening sockets.",
            "If this came from Codex or another sandboxed Agent, keep the blocked report and rerun outside the sandbox.",
        ],
        "clean_clone_timeout": [
            "Rerun once with `--timeout-seconds 1200` to separate a slow install from a real hang.",
            "Inspect the emitted command and local logs before filing a support ticket.",
        ],
        "dependency_install_failed": [
            "Configure `PIP_INDEX_URL` or an internal package mirror, then rerun the smoke.",
            "If the network is restricted, run `./scripts/launch_skill_mode.sh` first to prebuild the local .venv.",
            "If downloads are slow but reachable, retry with `SKILL_PIP_INSTALL_TIMEOUT_SECONDS=1200`.",
            "For flaky package indexes, try `PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=1`.",
        ],
        "skill_mode_demo_step_failed": [
            "Run `./scripts/run_skill_mode_demo.sh` directly and use the reported step name as the first failing boundary.",
            "Do not debug real model credentials yet; the clean-clone smoke should pass with the dry-run gateway.",
        ],
        "skill_mode_venv_missing": [
            "Run `python3 scripts/setup_env.py --force` and then `./scripts/launch_skill_mode.sh` in the clean clone.",
            "Verify the selected Python points to 3.11 or newer.",
        ],
        "python_version_missing": [
            "Install Python 3.11 or newer, or set `STUDY_ANYTHING_PYTHON=/path/to/python3.11`.",
            "Avoid system Python versions older than 3.11 for the Skill Mode smoke.",
        ],
        "promptfoo_eval_failed": [
            "Rerun without `--with-promptfoo` to confirm the core adoption smoke first.",
            "Install and verify Promptfoo only after the local Skill Mode dry-run path passes.",
        ],
        "gateway_dry_run_failed": [
            "Start the gateway explicitly with `AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --host 127.0.0.1 --port 8787`.",
            "Confirm `/health` reports `mode: dry_run` before registering the endpoint.",
        ],
        "clean_clone_command_failed": [
            "Read the command, stdout, and stderr fields in the diagnostic before retrying.",
            "If the failing command is `git clone`, confirm the repo/ref is reachable from this machine.",
        ],
        "invalid_cli_input": [
            "Fix the reported command-line argument, then rerun the same clean-clone smoke.",
            "Use `python3 scripts/verify_clean_clone_adoption.py --help` to inspect supported flags.",
        ],
    }
    return matrix.get(
        classification,
        ["Rerun the clean-clone smoke with `--copy-worktree` to isolate clone/ref issues."],
    ) + common


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:tmp|var/folders)/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"/var/" + r"folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if re.search(r"(?i)(api[_-]?key|access[_-]?token|authorization|secret|token|password)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", serialized):
        leaks.append("secret-looking key/value")
    if leaks:
        raise CleanCloneAdoptionError(f"Clean-clone failure report leaked private data: {leaks}")


def failure_report(exc: BaseException) -> dict[str, Any]:
    diagnostic = sanitize_text(str(exc))
    classification = classify_failure(diagnostic)
    report = {
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": failure_next_steps(classification),
        "source": {
            "verifier": VERIFIER_NAME,
            "repo_root": sanitize_text(str(ROOT)),
        },
        "privacy": {
            "local_absolute_paths_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "real_model_keys_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def format_failure_for_human(report: dict[str, Any]) -> str:
    steps = [
        f"- {sanitize_text(str(step))}"
        for step in report.get("next_steps", [])
        if isinstance(step, str) and step.strip()
    ]
    return "\n".join(
        [
            f"{VERIFIER_NAME} failed:",
            f"classification: {sanitize_text(str(report.get('classification') or 'clean_clone_adoption_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Run python3 scripts/diagnose_adoption.py, then rerun the clean-clone smoke."]),
        ]
    )


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout_seconds: int,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=capture_output,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CleanCloneAdoptionError(
            command_failure_message(
                command,
                returncode=None,
                stdout=exc.stdout,
                stderr=exc.stderr,
                timeout_seconds=timeout_seconds,
            )
        ) from exc
    if completed.returncode != 0:
        if is_local_bind_permission_denied(f"{completed.stdout}\n{completed.stderr}"):
            raise CleanCloneAdoptionError(
                local_bind_permission_message(command, completed.stdout, completed.stderr)
            )
        if is_dependency_download_failure(f"{completed.stdout}\n{completed.stderr}"):
            raise CleanCloneAdoptionError(
                dependency_download_message(command, completed.stdout, completed.stderr)
            )
        if is_skill_demo_step_failure(f"{completed.stdout}\n{completed.stderr}"):
            raise CleanCloneAdoptionError(
                skill_demo_step_failure_message(command, completed.stdout, completed.stderr)
            )
        raise CleanCloneAdoptionError(
            command_failure_message(
                command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        )
    return completed


def is_local_bind_permission_denied(text: str) -> bool:
    lowered = text.lower()
    return (
        (
            ("operation not permitted" in lowered or "permission denied" in lowered)
            and "bind" in lowered
            and ("127.0.0.1" in lowered or "localhost" in lowered)
        )
        or (
            "cannot listen" in lowered
            and "localhost listening sockets" in lowered
        )
    )


def is_dependency_download_failure(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "pip subprocess to install build dependencies",
        "dependency installation timed out",
        "skill_pip_install_timeout_seconds",
        "readtimeout",
        "timeouterror",
        "connection timed out",
        "could not find a version that satisfies",
        "no matching distribution found",
        "failed to establish a new connection",
        "nodename nor servname provided",
        "temporary failure in name resolution",
        "/simple/setuptools/",
        "/simple/pip/",
    ]
    return any(marker in lowered for marker in markers)


def is_skill_demo_step_failure(text: str) -> bool:
    return "study anything skill mode demo step failed:" in text.lower()


def skill_demo_step_failure_message(command: list[str], stdout: str, stderr: str) -> str:
    return (
        "A bounded Skill Mode demo verification step failed after the local API started. "
        "This is not a silent deployment failure; use the step name below to narrow the issue, "
        "then run the redacted diagnostics before filing a support ticket. "
        f"Command: {' '.join(command)}\n"
        f"stdout:\n{sanitize_text(stdout)}\n"
        f"stderr:\n{sanitize_text(stderr)}"
    )


def dependency_failure_excerpt(stdout: str, stderr: str) -> str:
    markers = [
        "installing study anything api dependencies",
        "installing build dependencies",
        "pip subprocess to install build dependencies",
        "dependency installation timed out",
        "skill_pip_install_timeout_seconds",
        "readtimeout",
        "timeouterror",
        "connection timed out",
        "timed out after",
        "failed to establish a new connection",
        "nodename nor servname provided",
        "temporary failure in name resolution",
        "could not find a version that satisfies",
        "no matching distribution found",
        "/simple/setuptools/",
        "/simple/pip/",
    ]
    lines: list[str] = []
    saw_retry_connection = False
    for raw_line in f"{stdout}\n{stderr}".splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if not line:
            continue
        if "retrying" in lowered and "failed to establish a new connection" in lowered:
            saw_retry_connection = True
            continue
        if not any(marker in lowered for marker in markers):
            continue
        if len(line) > 300:
            line = f"{line[:297]}..."
        if line not in lines:
            lines.append(line)
    if saw_retry_connection:
        connection_summary = "pip could not establish a connection to the configured package index."
        if connection_summary not in lines:
            lines.insert(0, connection_summary)
    if not lines:
        fallback = f"{stdout}\n{stderr}".strip()
        return sanitize_text(fallback[-1000:]) if fallback else "(no captured output)"
    return sanitize_text("\n".join(lines[:10]))


def dependency_download_message(command: list[str], stdout: str, stderr: str) -> str:
    return (
        "Python dependency installation failed while preparing the disposable clean-clone "
        "environment. This usually means the current runner cannot reach PyPI or the "
        "configured package index, or a package download exceeded the bounded install "
        "timeout; it is not a Study Anything learning-flow failure. "
        "Retry from a networked terminal, configure PIP_INDEX_URL / an internal mirror, "
        "increase SKILL_PIP_INSTALL_TIMEOUT_SECONDS if downloads are slow, "
        "or prebuild the .venv with ./scripts/launch_skill_mode.sh before running the "
        "adoption smoke again. "
        f"Command: {' '.join(command)}\n"
        f"Relevant output:\n{dependency_failure_excerpt(stdout, stderr)}"
    )


def local_bind_permission_message(command: list[str], stdout: str, stderr: str) -> str:
    return (
        "Local Skill Mode API could not bind to localhost from this runner. "
        "This usually means the current agent sandbox blocks listening sockets. "
        "Run this smoke from a normal terminal or host shell that permits localhost binds, "
        "then retry the same command. "
        f"Command: {' '.join(command)}\n"
        f"stdout:\n{sanitize_text(stdout)}\n"
        f"stderr:\n{sanitize_text(stderr)}"
    )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def reserve_free_port(purpose: str) -> int:
    try:
        return free_port()
    except OSError as exc:
        recovery = (
            "This usually means the current runner or agent sandbox blocks local sockets. "
            "Run this smoke from a normal terminal, or pass --api-port PORT for the main "
            "Skill Mode API when port probing is blocked but binding a known port is allowed."
        )
        if not is_localhost_socket_blocked(exc):
            recovery = (
                "Choose another port or retry from a shell with access to localhost sockets. "
                "You can pass --api-port PORT for the main Skill Mode API to avoid automatic "
                "port probing."
            )
        raise CleanCloneAdoptionError(
            f"Cannot reserve a localhost port for {purpose}: {exc}. {recovery}"
        ) from exc


def select_localhost_port(
    explicit_port: int | None,
    *,
    flag_name: str,
    purpose: str,
) -> int:
    if explicit_port is not None:
        if explicit_port <= 0 or explicit_port > 65535:
            raise CleanCloneAdoptionError(f"{flag_name} must be between 1 and 65535.")
        return explicit_port
    return reserve_free_port(purpose)


def select_api_port(explicit_port: int | None) -> int:
    return select_localhost_port(
        explicit_port,
        flag_name="--api-port",
        purpose="Skill Mode API",
    )


def select_promptfoo_api_port(explicit_port: int | None) -> int:
    return select_localhost_port(
        explicit_port,
        flag_name="--promptfoo-api-port",
        purpose="Promptfoo eval API",
    )


def is_python_311_or_newer(candidate: str) -> bool:
    try:
        completed = subprocess.run(
            [
                candidate,
                "-c",
                "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def find_python_311() -> str:
    candidates = [
        os.environ.get("STUDY_ANYTHING_PYTHON"),
        sys.executable,
        str(ROOT / ".venv" / "bin" / "python"),
        str(ROOT / ".venv" / "bin" / "python3"),
        shutil.which("python3.12"),
        shutil.which("python3.11"),
        shutil.which("python3"),
    ]
    for candidate in candidates:
        if candidate and is_python_311_or_newer(candidate):
            return candidate
    raise CleanCloneAdoptionError(
        "Python 3.11 or newer is required. Create .venv or install python3.11/python3.12."
    )


def copy_worktree(source: Path, target: Path) -> None:
    ignored = shutil.ignore_patterns(
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "data",
        "*.pyc",
    )
    shutil.copytree(source, target, ignore=ignored)


def clone_repo(source: str, target: Path, *, ref: str | None, copy: bool) -> None:
    if copy:
        copy_worktree(Path(source).resolve(), target)
        return
    run(["git", "clone", "--no-local", source, str(target)], cwd=ROOT, timeout_seconds=180)
    if ref:
        run(["git", "checkout", ref], cwd=target, timeout_seconds=60)
        return
    source_path = Path(source)
    if source_path.exists():
        completed = run(
            ["git", "rev-parse", "HEAD"],
            cwd=source_path.resolve(),
            timeout_seconds=30,
            capture_output=True,
        )
        source_head = completed.stdout.strip()
        if source_head:
            run(["git", "checkout", source_head], cwd=target, timeout_seconds=60)


def python_in_clone(clone: Path) -> Path:
    for candidate in [clone / ".venv" / "bin" / "python3", clone / ".venv" / "bin" / "python"]:
        if candidate.exists():
            return candidate
    raise CleanCloneAdoptionError("Skill Mode did not create .venv/bin/python in the clean clone.")


def make_env(clone: Path, work_dir: Path, *, api_port: int) -> dict[str, str]:
    python_bin = find_python_311()
    env = os.environ.copy()
    env.update(
        {
            "PYTHON_BIN": python_bin,
            "STUDY_ANYTHING_VENV": str(clone / ".venv"),
            "STUDY_ANYTHING_DATA_DIR": str(work_dir / "skill-mode-data"),
            "API_PORT": str(api_port),
            "SKILL_API_HOST": "127.0.0.1",
            "STUDY_ANYTHING_API_BASE": f"http://127.0.0.1:{api_port}",
            "API_BASE": f"http://127.0.0.1:{api_port}",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_DEFAULT_TIMEOUT": os.environ.get("PIP_DEFAULT_TIMEOUT", "60"),
            "PIP_RETRIES": os.environ.get("PIP_RETRIES", "2"),
            "PIP_NO_INPUT": "1",
            "SKILL_PIP_INSTALL_TIMEOUT_SECONDS": os.environ.get(
                "SKILL_PIP_INSTALL_TIMEOUT_SECONDS",
                "600",
            ),
        }
    )
    return env


def run_skill_mode_demo(clone: Path, env: dict[str, str], *, timeout_seconds: int) -> str:
    completed = run(
        ["sh", "scripts/run_skill_mode_demo.sh"],
        cwd=clone,
        env=env,
        timeout_seconds=timeout_seconds,
        capture_output=True,
    )
    return completed.stdout or ""


def wait_for_api(api_base: str, *, timeout_seconds: int, log_path: Path) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            request = Request(f"{api_base.rstrip('/')}/v1/health", method="GET")
            with urlopen(request, timeout=2) as response:
                if response.status == 200:
                    return
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    log_tail = sanitize_text(log_path.read_text(encoding="utf-8", errors="replace")[-4000:])
    if is_local_bind_permission_denied(f"{last_error}\n{log_tail}"):
        raise CleanCloneAdoptionError(
            "Local Skill Mode API could not bind to localhost from this runner. "
            "This usually means the current agent sandbox blocks listening sockets. "
            "Run this smoke from a normal terminal or host shell that permits localhost binds, "
            "then retry the same command.\n"
            f"Log tail:\n{log_tail}"
        )
    raise CleanCloneAdoptionError(
        f"Skill API did not become healthy at {api_base}: {last_error}\n"
        f"Log tail:\n{log_tail}"
    )


def run_promptfoo(
    clone: Path,
    env: dict[str, str],
    *,
    api_port: int | None,
    timeout_seconds: int,
    required: bool,
) -> dict[str, Any]:
    promptfoo_env = env.copy()
    promptfoo_port = select_promptfoo_api_port(api_port)
    promptfoo_env.update(
        {
            "API_PORT": str(promptfoo_port),
            "STUDY_ANYTHING_API_BASE": f"http://127.0.0.1:{promptfoo_port}",
            "API_BASE": f"http://127.0.0.1:{promptfoo_port}",
            "STUDY_ANYTHING_DATA_DIR": env["STUDY_ANYTHING_DATA_DIR"] + "-promptfoo",
        }
    )
    data_dir = Path(promptfoo_env["STUDY_ANYTHING_DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "api.log"
    python_bin = python_in_clone(clone)
    api_env = promptfoo_env.copy()
    api_env.update(
        {
            "SESSION_STORE": "json",
            "WORKFLOW_ENGINE": "langgraph",
            "LANGGRAPH_CHECKPOINTER": "memory",
            "FALKORDB_ENABLED": "false",
        }
    )
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            str(python_bin),
            "-m",
            "uvicorn",
            "study_anything.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(promptfoo_port),
        ],
        cwd=clone,
        env=api_env,
        stdout=log_handle,
        stderr=log_handle,
    )
    try:
        wait_for_api(promptfoo_env["API_BASE"], timeout_seconds=60, log_path=log_path)
        command = [
            str(python_bin),
            "scripts/run_external_agent_evals.py",
            "--tool",
            "promptfoo",
            "--create-session",
            "--api-base",
            promptfoo_env["API_BASE"],
            "--timeout-seconds",
            str(timeout_seconds),
        ]
        if required:
            command.append("--required")
        completed = run(
            command,
            cwd=clone,
            env=promptfoo_env,
            timeout_seconds=timeout_seconds + 30,
        )
        return json.loads(completed.stdout.strip().splitlines()[-1])
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        log_handle.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(ROOT), help="Repository path or URL to clone.")
    parser.add_argument("--ref", help="Optional branch, tag, or commit to check out after clone.")
    parser.add_argument("--work-dir", help="Directory for the disposable clone and state.")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the disposable clone after success.",
    )
    parser.add_argument(
        "--copy-worktree",
        action="store_true",
        help="Developer convenience: copy the current worktree instead of git clone.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument(
        "--api-port",
        type=int,
        help=(
            "Use a fixed localhost API port instead of probing for a free one. "
            "Useful in runners that block ephemeral port probing."
        ),
    )
    parser.add_argument("--with-promptfoo", action="store_true")
    parser.add_argument("--promptfoo-required", action="store_true")
    parser.add_argument("--promptfoo-timeout-seconds", type=int, default=180)
    parser.add_argument(
        "--promptfoo-api-port",
        type=int,
        help=(
            "Use a fixed localhost API port for the optional Promptfoo eval API. "
            "Useful when sandboxed runners block automatic port probing."
        ),
    )
    args = parser.parse_args()

    work_root = Path(args.work_dir) if args.work_dir else Path(
        tempfile.mkdtemp(prefix="study-anything-adoption-")
    )
    clone = work_root / "study-anything"
    cleanup = not args.keep and args.work_dir is None
    promptfoo_api_port = (
        select_promptfoo_api_port(args.promptfoo_api_port)
        if args.promptfoo_api_port is not None
        else None
    )
    api_port = select_api_port(args.api_port)
    env = make_env(clone, work_root, api_port=api_port)
    promptfoo_result: dict[str, Any] | None = None

    try:
        clone_repo(args.repo, clone, ref=args.ref, copy=args.copy_worktree)
        run([sys.executable, "scripts/setup_env.py", "--force"], cwd=clone, timeout_seconds=60)
        demo_stdout = run_skill_mode_demo(clone, env, timeout_seconds=args.timeout_seconds)
        if args.with_promptfoo:
            promptfoo_result = run_promptfoo(
                clone,
                env,
                api_port=promptfoo_api_port,
                timeout_seconds=args.promptfoo_timeout_seconds,
                required=args.promptfoo_required,
            )
            if args.promptfoo_required and promptfoo_result.get("status") != "ok":
                raise CleanCloneAdoptionError(f"Promptfoo did not pass: {promptfoo_result}")
        print(
            json.dumps(
                {
                    "status": "ok",
                    "repo": sanitize_text(args.repo),
                    "ref": args.ref,
                    "clone_dir": sanitize_text(str(clone)) if args.keep else None,
                    "clone_dir_retained": bool(args.keep),
                    "api_base": env["STUDY_ANYTHING_API_BASE"],
                    "skill_mode_demo": "passed",
                    "gateway_dry_run": "passed",
                    "teaching_layers": "passed",
                    "agent_audit_eval": "passed",
                    "promptfoo": sanitize_json_value(promptfoo_result),
                    "demo_tail": sanitize_text(demo_stdout[-2000:]),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    finally:
        if cleanup:
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_failure_for_human(report), file=sys.stderr)
        sys.exit(1)
