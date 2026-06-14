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


class CleanCloneAdoptionError(RuntimeError):
    """Readable adoption-smoke failure."""


def output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


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
            f"Command timed out after {timeout_seconds}s: {' '.join(command)}\n"
            f"stdout:\n{output_text(exc.stdout)}\n"
            f"stderr:\n{output_text(exc.stderr)}"
        ) from exc
    if completed.returncode != 0:
        raise CleanCloneAdoptionError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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
        }
    )
    return env


def run_skill_mode_demo(clone: Path, env: dict[str, str], *, timeout_seconds: int) -> str:
    completed = run(
        ["sh", "scripts/run_skill_mode_demo.sh"],
        cwd=clone,
        env=env,
        timeout_seconds=timeout_seconds,
        capture_output=False,
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
    log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
    raise CleanCloneAdoptionError(
        f"Skill API did not become healthy at {api_base}: {last_error}\n"
        f"Log tail:\n{log_tail}"
    )


def run_promptfoo(
    clone: Path,
    env: dict[str, str],
    *,
    timeout_seconds: int,
    required: bool,
) -> dict[str, Any]:
    promptfoo_env = env.copy()
    promptfoo_port = free_port()
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
    parser.add_argument("--with-promptfoo", action="store_true")
    parser.add_argument("--promptfoo-required", action="store_true")
    parser.add_argument("--promptfoo-timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    work_root = Path(args.work_dir) if args.work_dir else Path(
        tempfile.mkdtemp(prefix="study-anything-adoption-")
    )
    clone = work_root / "study-anything"
    cleanup = not args.keep and args.work_dir is None
    api_port = free_port()
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
                timeout_seconds=args.promptfoo_timeout_seconds,
                required=args.promptfoo_required,
            )
            if args.promptfoo_required and promptfoo_result.get("status") != "ok":
                raise CleanCloneAdoptionError(f"Promptfoo did not pass: {promptfoo_result}")
        print(
            json.dumps(
                {
                    "status": "ok",
                    "repo": args.repo,
                    "ref": args.ref,
                    "clone_dir": str(clone) if args.keep else None,
                    "api_base": env["STUDY_ANYTHING_API_BASE"],
                    "skill_mode_demo": "passed",
                    "gateway_dry_run": "passed",
                    "teaching_layers": "passed",
                    "agent_audit_eval": "passed",
                    "promptfoo": promptfoo_result,
                    "demo_tail": demo_stdout[-2000:],
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
        print(f"verify_clean_clone_adoption failed: {exc}", file=sys.stderr)
        sys.exit(1)
