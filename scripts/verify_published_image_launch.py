#!/usr/bin/env python3
"""Verify a disposable self-host stack from published GHCR images."""

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
IMAGE_COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.images.yml"
SETUP_ENV = ROOT / "scripts" / "setup_env.py"
VERIFY_FULL_API_FLOW = ROOT / "scripts" / "verify_full_api_flow.py"
PORT_KEYS = (
    "API_PORT",
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


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def compose(env_file: Path, *args: str, profiles: tuple[str, ...] = ()) -> list[str]:
    project_name = parse_env(env_file).get("COMPOSE_PROJECT_NAME")
    command = ["docker", "compose"]
    if project_name:
        command.extend(["--project-name", project_name])
    command.extend(
        [
            "--env-file",
            str(env_file),
            "-f",
            str(COMPOSE_FILE),
            "-f",
            str(IMAGE_COMPOSE_FILE),
        ]
    )
    for profile in profiles:
        command.extend(["--profile", profile])
    command.extend(args)
    return command


def create_disposable_env(
    work_dir: Path,
    *,
    project_name: str,
    tag: str,
    api_image: str,
) -> Path:
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
        "STUDY_ANYTHING_IMAGE_TAG": tag,
        "STUDY_ANYTHING_API_IMAGE": api_image,
    }
    additions.update({key: str(free_port()) for key in PORT_KEYS})
    with env_file.open("a", encoding="utf-8") as target:
        target.write("\n# verify_published_image_launch.py disposable overrides\n")
        for key, value in additions.items():
            target.write(f"{key}={value}\n")
    return env_file


def request_json(base: str, path: str) -> Any:
    req = Request(f"{base.rstrip('/')}{path}", method="GET")
    with urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


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


def verify_flow(api_base: str) -> dict[str, Any]:
    env = {**os.environ, "API_BASE": api_base}
    result = run([sys.executable, str(VERIFY_FULL_API_FLOW)], env=env, capture_output=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def cleanup_stack(env_file: Path) -> None:
    run(compose(env_file, "down", "-v", "--remove-orphans", profiles=("smoke", "full")), check=False)


def default_expected_version(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="v0.2.7-alpha", help="Published Study Anything image tag.")
    parser.add_argument("--expected-version", help="Expected /v1/health and /v1/system/status version.")
    parser.add_argument("--timeout", type=int, default=240, help="Seconds to wait for API health.")
    parser.add_argument("--skip-pull", action="store_true", help="Use locally cached images.")
    parser.add_argument("--keep-on-failure", action="store_true", help="Leave disposable stack for debugging.")
    parser.add_argument("--keep-on-success", action="store_true", help="Leave disposable stack for inspection.")
    parser.add_argument("--api-image", help="Exact API image to run.")
    args = parser.parse_args()

    tag = args.tag
    expected_version = args.expected_version or default_expected_version(tag)
    api_image = args.api_image or f"ghcr.io/jzvcpe-goat/study-anything/api:{tag}"
    project_name = f"study_anything_published_{int(time.time())}"
    work_dir = Path(tempfile.mkdtemp(prefix="study-anything-published-"))
    env_file = create_disposable_env(
        work_dir,
        project_name=project_name,
        tag=tag,
        api_image=api_image,
    )
    values = parse_env(env_file)
    api_base = f"http://127.0.0.1:{values['API_PORT']}"
    cleanup = not args.keep_on_success

    try:
        if not args.skip_pull:
            run(compose(env_file, "pull", "api"))
        run(compose(env_file, "up", "-d", "api"))
        wait_for_api(api_base, args.timeout)

        health = request_json(api_base, "/v1/health")
        system = request_json(api_base, "/v1/system/status")
        if health.get("version") != expected_version or system.get("version") != expected_version:
            raise RuntimeError(
                "Published image version mismatch: "
                f"expected {expected_version}, health={health.get('version')}, "
                f"system={system.get('version')}"
            )

        api_flow = verify_flow(api_base)

        print(
            json.dumps(
                {
                    "status": "ok",
                    "project": project_name,
                    "tag": tag,
                    "api_image": api_image,
                    "api_base": api_base,
                    "system_version": system["version"],
                    "api_session_id": api_flow["session_id"],
                    "registry_verified_plugins": api_flow.get("registry_verified_plugins"),
                    "env_file": str(env_file) if args.keep_on_success else None,
                },
                ensure_ascii=False,
            )
        )
        if args.keep_on_success:
            print(f"Kept disposable published-image project for inspection: {project_name}", file=sys.stderr)
            print(f"Disposable env: {env_file}", file=sys.stderr)
    except Exception:
        if args.keep_on_failure:
            cleanup = False
            print(f"Kept disposable published-image project for debugging: {project_name}", file=sys.stderr)
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
        print(f"verify_published_image_launch failed: {exc}", file=sys.stderr)
        sys.exit(1)
