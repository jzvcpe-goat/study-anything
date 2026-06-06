#!/usr/bin/env python3
"""Run a disposable Docker backup/restore drill for self-host readiness."""

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
COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.yml"
SETUP_ENV = ROOT / "scripts" / "setup_env.py"
SELF_HOST_DATA = ROOT / "scripts" / "self_host_data.py"
VERIFY_FULL_API_FLOW = ROOT / "scripts" / "verify_full_api_flow.py"
VERIFY_FULL_STACK_WEB = ROOT / "scripts" / "verify_full_stack_web.py"
PORT_KEYS = (
    "API_PORT",
    "WEB_PORT",
    "APP_POSTGRES_PORT",
    "MOCK_AGENT_PORT",
    "FALKORDB_HOST_PORT",
    "LANGFUSE_PORT",
    "CLICKHOUSE_HTTP_PORT",
    "CLICKHOUSE_NATIVE_PORT",
    "MINIO_PORT",
    "MINIO_CONSOLE_PORT",
    "REDIS_PORT",
    "LANGFUSE_POSTGRES_PORT",
)
ASCII_REEXEC_ENV = "STUDY_ANYTHING_DRILL_ASCII_REEXEC"
SOURCE_COPY_ENV = "STUDY_ANYTHING_DRILL_SOURCE_COPY"
SOURCE_COPY_EXCLUDES = (
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "data",
    "backups",
    ".env",
    ".DS_Store",
)


def run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
    )


def is_ascii_path(path: Path) -> bool:
    try:
        str(path).encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def maybe_reexec_from_ascii_copy(keep_on_failure: bool) -> None:
    if is_ascii_path(ROOT) or os.getenv(ASCII_REEXEC_ENV) == "1":
        return

    parent = Path(tempfile.mkdtemp(prefix="study-anything-drill-src-", dir="/tmp"))
    target = parent / "study-anything"
    print(
        "Source checkout path contains non-ASCII characters; copying to an ASCII temp path "
        f"for Docker BuildKit: {target}",
        file=sys.stderr,
    )
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(*SOURCE_COPY_EXCLUDES),
    )
    env = {**os.environ, ASCII_REEXEC_ENV: "1", SOURCE_COPY_ENV: str(parent)}
    result = subprocess.run(
        [sys.executable, str(target / "scripts" / "verify_backup_restore_drill.py"), *sys.argv[1:]],
        env=env,
    )
    if result.returncode == 0 or not keep_on_failure:
        shutil.rmtree(parent, ignore_errors=True)
    else:
        print(f"Kept ASCII source copy for debugging: {target}", file=sys.stderr)
    raise SystemExit(result.returncode)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def compose(env_file: Path, *args: str, profiles: tuple[str, ...] = ()) -> list[str]:
    project_name = parse_env(env_file).get("COMPOSE_PROJECT_NAME")
    command = ["docker", "compose"]
    if project_name:
        command.extend(["--project-name", project_name])
    command.extend(["--env-file", str(env_file), "-f", str(COMPOSE_FILE)])
    for profile in profiles:
        command.extend(["--profile", profile])
    command.extend(args)
    return command


def create_disposable_env(work_dir: Path, project_name: str) -> Path:
    env_file = work_dir / ".env"
    run([sys.executable, str(SETUP_ENV), "--force", "--output", str(env_file)])
    additions = {
        "COMPOSE_PROJECT_NAME": project_name,
        "STACK_PROFILE": "core",
        "FALKORDB_ENABLED": "false",
        "TELEMETRY_ENABLED": "false",
        "LANGGRAPH_CHECKPOINTER": "postgres",
        "SESSION_STORE": "postgres",
        "WORKFLOW_ENGINE": "langgraph",
    }
    additions.update({key: str(free_port()) for key in PORT_KEYS})
    with env_file.open("a", encoding="utf-8") as target:
        target.write("\n# verify_backup_restore_drill.py disposable overrides\n")
        for key, value in additions.items():
            target.write(f"{key}={value}\n")
    return env_file


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def wait_for_api(api_base: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            request_json(api_base, "/v1/health")
            return
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = str(exc)
            time.sleep(2)
    raise RuntimeError(f"API did not become healthy within {timeout_seconds}s: {last_error}")


def wait_for_web(web_base: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            request_text(web_base, "/")
            return
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = str(exc)
            time.sleep(2)
    raise RuntimeError(f"Web UI did not become reachable within {timeout_seconds}s: {last_error}")


def request_text(base: str, path: str) -> str:
    req = Request(f"{base.rstrip('/')}{path}", method="GET")
    with urlopen(req, timeout=10) as response:
        return response.read().decode("utf-8")


def request_json(api_base: str, path: str) -> Any:
    req = Request(f"{api_base.rstrip('/')}{path}", method="GET")
    with urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def session_count(env_file: Path) -> int:
    result = run(
        compose(
            env_file,
            "exec",
            "-T",
            "app-postgres",
            "psql",
            "-U",
            "study",
            "-d",
            "study_anything",
            "-Atc",
            "SELECT count(*) FROM study_anything_sessions",
        ),
        capture_output=True,
    )
    return int(result.stdout.strip() or "0")


def verify_flow(api_base: str) -> dict[str, Any]:
    env = {**os.environ, "API_BASE": api_base}
    result = run(
        [sys.executable, str(VERIFY_FULL_API_FLOW)],
        env=env,
        capture_output=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def verify_web_flow(web_base: str) -> dict[str, Any]:
    env = {**os.environ, "WEB_BASE": web_base}
    result = run(
        [sys.executable, str(VERIFY_FULL_STACK_WEB)],
        env=env,
        capture_output=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def cleanup_stack(env_file: Path) -> None:
    run(compose(env_file, "down", "-v", "--remove-orphans", profiles=("smoke", "full")), check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=180, help="Seconds to wait for API health.")
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Start the disposable stack without `docker compose up --build`.",
    )
    parser.add_argument(
        "--keep-on-failure",
        action="store_true",
        help="Leave disposable containers, volumes, and backup files for debugging.",
    )
    args = parser.parse_args()
    maybe_reexec_from_ascii_copy(args.keep_on_failure)

    project_name = f"study_anything_drill_{int(time.time())}"
    work_dir = Path(tempfile.mkdtemp(prefix="study-anything-restore-drill-"))
    env_file = create_disposable_env(work_dir, project_name)
    values = parse_env(env_file)
    api_base = f"http://127.0.0.1:{values['API_PORT']}"
    web_base = f"http://127.0.0.1:{values['WEB_PORT']}"
    backup_dir = work_dir / "backup"
    cleanup = True

    try:
        up_command = ["up", "-d"]
        if not args.no_build:
            up_command.append("--build")
        up_command.extend(["api", "web"])
        run(compose(env_file, *up_command))
        wait_for_api(api_base, args.timeout)
        wait_for_web(web_base, args.timeout)

        baseline_flow = verify_flow(api_base)
        baseline_web_flow = verify_web_flow(web_base)
        baseline_count = session_count(env_file)
        if baseline_count < 1:
            raise RuntimeError("Baseline smoke flow did not create a session.")

        run(
            [
                sys.executable,
                str(SELF_HOST_DATA),
                "--env",
                str(env_file),
                "backup",
                "--output",
                str(backup_dir),
            ]
        )

        mutated_flow = verify_flow(api_base)
        mutated_count = session_count(env_file)
        if mutated_count <= baseline_count:
            raise RuntimeError(
                f"Mutation smoke did not increase session count: {baseline_count} -> {mutated_count}"
            )

        run(
            [
                sys.executable,
                str(SELF_HOST_DATA),
                "--env",
                str(env_file),
                "restore",
                str(backup_dir),
                "--yes",
            ]
        )
        run(compose(env_file, *up_command))
        wait_for_api(api_base, args.timeout)
        restored_count = session_count(env_file)
        if restored_count != baseline_count:
            raise RuntimeError(
                f"Restore did not roll back session count: {baseline_count} != {restored_count}"
            )
        recovery = request_json(api_base, "/v1/recovery/status")
        if recovery.get("restore_api_enabled"):
            raise RuntimeError(f"Restore API should remain disabled: {recovery}")

        print(
            json.dumps(
                {
                    "status": "ok",
                    "project": project_name,
                    "api_base": api_base,
                    "web_base": web_base,
                    "baseline_session_count": baseline_count,
                    "mutated_session_count": mutated_count,
                    "restored_session_count": restored_count,
                    "baseline_session_id": baseline_flow["session_id"],
                    "baseline_web_session_id": baseline_web_flow["session_id"],
                    "mutated_session_id": mutated_flow["session_id"],
                    "backup_manifest": str(backup_dir / "manifest.json"),
                    "restore_api_enabled": recovery["restore_api_enabled"],
                    "registry_verified_plugins": baseline_flow.get("registry_verified_plugins"),
                    "web_sync_package_schema": baseline_web_flow.get("sync_package_schema"),
                    "web_sync_plaintext_returned": baseline_web_flow.get("sync_plaintext_returned"),
                },
                ensure_ascii=False,
            )
        )
    except Exception:
        if args.keep_on_failure:
            cleanup = False
            print(f"Kept disposable drill project for debugging: {project_name}", file=sys.stderr)
            print(f"Disposable env: {env_file}", file=sys.stderr)
        raise
    finally:
        if cleanup:
            cleanup_stack(env_file)
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"verify_backup_restore_drill failed: {exc}", file=sys.stderr)
        sys.exit(1)
