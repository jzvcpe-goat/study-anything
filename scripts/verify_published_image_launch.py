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
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        timeout=timeout,
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
    run(
        compose(env_file, "down", "-v", "--remove-orphans", profiles=("smoke", "full")),
        check=False,
    )


def default_expected_versions(tag: str) -> set[str]:
    value = tag[1:] if tag.startswith("v") else tag
    return {value, value.replace("-alpha", "a0")}


def inspect_manifest_platforms(image: str, *, timeout_seconds: int = 20) -> dict[str, Any]:
    if shutil.which("docker") is None:
        return {
            "status": "unavailable",
            "reason": "docker_missing",
            "command": f"docker manifest inspect {image}",
        }
    try:
        completed = run(
            ["docker", "manifest", "inspect", image],
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "unavailable",
            "reason": "manifest_inspect_timeout",
            "command": f"docker manifest inspect {image}",
            "timeout_seconds": timeout_seconds,
        }
    if completed.returncode != 0:
        return {
            "status": "unavailable",
            "reason": "manifest_inspect_failed",
            "command": f"docker manifest inspect {image}",
            "stderr": completed.stderr[-1000:],
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "unavailable",
            "reason": "manifest_inspect_invalid_json",
            "command": f"docker manifest inspect {image}",
        }
    platforms = sorted(
        {
            f"{item.get('platform', {}).get('os')}/{item.get('platform', {}).get('architecture')}"
            for item in payload.get("manifests", [])
            if item.get("platform", {}).get("os") != "unknown"
        }
    )
    return {
        "status": "ok" if {"linux/amd64", "linux/arm64"}.issubset(platforms) else "incomplete",
        "command": f"docker manifest inspect {image}",
        "platforms": platforms,
        "required_platforms": ["linux/amd64", "linux/arm64"],
    }


def pull_timeout_report(
    *,
    tag: str,
    api_image: str,
    timeout_seconds: int,
    project_name: str,
    manifest_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "blocked_by_local_ghcr_pull",
        "tag": tag,
        "api_image": api_image,
        "project": project_name,
        "timeout_seconds": timeout_seconds,
        "diagnostic": (
            "The published API image exists, but this machine could not finish pulling it "
            "within the configured timeout. Treat this as a local Docker/GHCR/network limit "
            "unless docker manifest inspection or GitHub docker-images workflow also fails."
        ),
        "fallback_acceptance": {
            "acceptable_when": [
                "GitHub Actions docker-images workflow succeeded for the same tag or commit.",
                "docker manifest inspect shows linux/amd64 and linux/arm64 for the published API image.",
                "release_check.sh and external adoption proof passed before tagging.",
            ],
            "not_acceptable_when": [
                "manifest inspection fails",
                "required platforms are missing",
                "GitHub docker-images workflow failed",
            ],
        },
        "manifest_evidence": manifest_evidence or inspect_manifest_platforms(api_image),
        "next_steps": [
            f"docker manifest inspect {api_image}",
            f"python3 scripts/verify_published_image_launch.py --tag {tag} --skip-pull",
            "Retry from a faster network or verify from GitHub Actions.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        default="v0.3.5-alpha",
        help="Published Study Anything image tag.",
    )
    parser.add_argument(
        "--expected-version",
        help="Expected /v1/health and /v1/system/status version.",
    )
    parser.add_argument("--timeout", type=int, default=240, help="Seconds to wait for API health.")
    parser.add_argument(
        "--pull-timeout-seconds",
        type=int,
        default=0,
        help="Optional timeout for docker compose pull. 0 means no timeout.",
    )
    parser.add_argument(
        "--allow-pull-timeout-report",
        action="store_true",
        help="Return a JSON diagnostic instead of failing when docker pull is locally too slow.",
    )
    parser.add_argument("--skip-pull", action="store_true", help="Use locally cached images.")
    parser.add_argument(
        "--keep-on-failure",
        action="store_true",
        help="Leave disposable stack for debugging.",
    )
    parser.add_argument(
        "--keep-on-success",
        action="store_true",
        help="Leave disposable stack for inspection.",
    )
    parser.add_argument("--api-image", help="Exact API image to run.")
    args = parser.parse_args()

    tag = args.tag
    expected_versions = (
        {args.expected_version} if args.expected_version else default_expected_versions(tag)
    )
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
            try:
                run(
                    compose(env_file, "pull", "api"),
                    timeout=args.pull_timeout_seconds or None,
                )
            except subprocess.TimeoutExpired:
                if args.allow_pull_timeout_report and args.pull_timeout_seconds > 0:
                    manifest_evidence = inspect_manifest_platforms(api_image)
                    print(
                        json.dumps(
                            pull_timeout_report(
                                tag=tag,
                                api_image=api_image,
                                timeout_seconds=args.pull_timeout_seconds,
                                project_name=project_name,
                                manifest_evidence=manifest_evidence,
                            ),
                            ensure_ascii=False,
                        )
                    )
                    return
                raise
        run(compose(env_file, "up", "-d", "api"))
        wait_for_api(api_base, args.timeout)

        health = request_json(api_base, "/v1/health")
        system = request_json(api_base, "/v1/system/status")
        health_version = health.get("version")
        system_version = system.get("version")
        if health_version not in expected_versions or system_version not in expected_versions:
            raise RuntimeError(
                "Published image version mismatch: "
                f"expected one of {sorted(expected_versions)}, "
                f"health={health_version}, system={system_version}"
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
            print(
                f"Kept disposable published-image project for inspection: {project_name}",
                file=sys.stderr,
            )
            print(f"Disposable env: {env_file}", file=sys.stderr)
    except Exception:
        if args.keep_on_failure:
            cleanup = False
            print(
                f"Kept disposable published-image project for debugging: {project_name}",
                file=sys.stderr,
            )
            print(f"Disposable env: {env_file}", file=sys.stderr)
        raise
    finally:
        if cleanup:
            cleanup_stack(env_file)
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as exc:
        print(f"verify_published_image_launch failed: {exc}", file=sys.stderr)
        sys.exit(1)
