#!/usr/bin/env python3
"""Verify a disposable self-host stack from published GHCR images."""

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

from localhost_diagnostics import (
    format_localhost_listen_blocked,
    is_localhost_socket_blocked,
    verifier_name_from_file,
)


COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.yml"
IMAGE_COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.images.yml"
SETUP_ENV = ROOT / "scripts" / "setup_env.py"
VERIFY_FULL_API_FLOW = ROOT / "scripts" / "verify_full_api_flow.py"
VERIFIER_NAME = verifier_name_from_file(__file__)
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
FORBIDDEN_LITERALS = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY",
    "Private answer:",
    "Private source text:",
    "raw_source_text=",
    "learner_answer=",
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


def output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def sanitize_text(value: str | bytes | None) -> str:
    text = output_text(value)
    text = re.sub(r"/Users/[^\s\"']+", "<local-path>", text)
    text = re.sub(r"/private/var/folders/[^\s\"']+", "<temp-path>", text)
    text = re.sub(r"/var/folders/[^\s\"']+", "<temp-path>", text)
    text = re.sub(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", r"\1=<redacted>", text)
    text = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", text)
    return text.strip()[:1600]


def classify_failure(exc: BaseException) -> str:
    if isinstance(exc, FileNotFoundError):
        return "docker_missing"
    text = f"{exc}\n{getattr(exc, 'stderr', '')}\n{getattr(exc, 'output', '')}".lower()
    if "docker_missing" in text or "no such file or directory: 'docker'" in text or 'no such file or directory: "docker"' in text:
        return "docker_missing"
    if "docker: 'compose' is not a docker command" in text or "unknown shorthand flag" in text and "compose" in text:
        return "docker_compose_missing"
    if "permission denied" in text and ("docker" in text or "docker.sock" in text or "docker api" in text):
        return "docker_socket_permission_denied"
    if "cannot connect to the docker daemon" in text or "is the docker daemon running" in text:
        return "docker_daemon_unavailable"
    if "published image manifest is not ready" in text or "manifest inspect" in text:
        return "published_image_manifest_unavailable"
    if "api did not become healthy" in text:
        return "published_image_api_health_timeout"
    if "published image version mismatch" in text:
        return "published_image_version_mismatch"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "published_image_command_timeout"
    if isinstance(exc, subprocess.CalledProcessError):
        return "published_image_command_failed"
    return "published_image_launch_failed"


def failure_next_steps(classification: str, *, tag: str, api_image: str) -> list[str]:
    common = [
        "python3 scripts/diagnose_adoption.py",
        f"python3 scripts/verify_published_image_launch.py --tag {tag} --manifest-only",
        "./scripts/launch_skill_mode.sh",
    ]
    matrix = {
        "docker_missing": [
            "Install Docker Desktop or Docker Engine, then reopen your terminal.",
            "Run `docker --version` and `docker compose version`.",
        ],
        "docker_compose_missing": [
            "Install/enable Docker Compose v2.",
            "Run `docker compose version` before retrying.",
        ],
        "docker_socket_permission_denied": [
            "Start Docker Desktop and check the active Docker context.",
            "On Linux, add your user to the docker group or use a rootless Docker context.",
        ],
        "docker_daemon_unavailable": [
            "Start Docker Desktop or the Docker daemon.",
            "Run `docker info` until it succeeds.",
        ],
        "published_image_manifest_unavailable": [
            f"Run `docker manifest inspect {api_image}`.",
            "Retry from a network that can reach GHCR.",
        ],
        "published_image_api_health_timeout": [
            "Run `docker compose ps` for the disposable project if you used --keep-on-failure.",
            "Run compose logs for the api and app-postgres services.",
        ],
        "published_image_version_mismatch": [
            "Confirm the image tag matches the release tag.",
            f"Retry with `--api-image {api_image}` only if that exact image was published for this release.",
        ],
    }
    return matrix.get(classification, ["Retry with --keep-on-failure and inspect Docker logs."]) + common


def failure_report(
    *,
    exc: BaseException,
    tag: str,
    api_image: str,
    project_name: str | None = None,
) -> dict[str, Any]:
    classification = classify_failure(exc)
    stdout = getattr(exc, "stdout", None) or getattr(exc, "output", None)
    stderr = getattr(exc, "stderr", None)
    report = {
        "status": "blocked",
        "classification": classification,
        "tag": tag,
        "api_image": api_image,
        "project": project_name,
        "diagnostic": sanitize_text(str(exc)),
        "stdout": sanitize_text(stdout) if stdout else None,
        "stderr": sanitize_text(stderr) if stderr else None,
        "next_steps": failure_next_steps(classification, tag=tag, api_image=api_image),
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "local_absolute_paths_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def failure_context_from_argv(argv: list[str]) -> tuple[str, str]:
    tag = "v0.3.29-alpha"
    api_image: str | None = None
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--tag" and index + 1 < len(argv):
            tag = argv[index + 1]
            index += 2
            continue
        if item.startswith("--tag="):
            tag = item.split("=", 1)[1]
        if item == "--api-image" and index + 1 < len(argv):
            api_image = argv[index + 1]
            index += 2
            continue
        if item.startswith("--api-image="):
            api_image = item.split("=", 1)[1]
        index += 1
    return tag, api_image or f"ghcr.io/jzvcpe-goat/study-anything/api:{tag}"


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise RuntimeError(f"Published image launch report leaked private data: {leaks}")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except OSError as exc:
            if is_localhost_socket_blocked(exc):
                raise RuntimeError(
                    format_localhost_listen_blocked(verifier=VERIFIER_NAME)
                ) from exc
            raise
        return int(sock.getsockname()[1])


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        key, value = stripped.split("=", 1)
        raw_value = value.strip()
        if raw_value.startswith(("'", '"')):
            quote = raw_value[0]
            end = raw_value.find(quote, 1)
            parsed_value = raw_value[1:end] if end != -1 else raw_value[1:]
        else:
            parsed_value = re.split(r"\s+#", raw_value, maxsplit=1)[0].strip()
        values[key.strip()] = parsed_value
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
        "classification": "blocked_by_local_ghcr_pull",
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


def compose_up_timeout_report(
    *,
    tag: str,
    api_image: str,
    timeout_seconds: int,
    project_name: str,
    manifest_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "compose_up_timeout",
        "classification": "compose_up_timeout",
        "tag": tag,
        "api_image": api_image,
        "project": project_name,
        "timeout_seconds": timeout_seconds,
        "diagnostic": (
            "docker compose up did not finish within the configured timeout. This often means "
            "Compose was still pulling a missing image layer or Docker was slow to create the "
            "container. The verifier cleaned up the disposable project after reporting."
        ),
        "manifest_evidence": manifest_evidence or inspect_manifest_platforms(api_image),
        "next_steps": [
            f"docker manifest inspect {api_image}",
            f"python3 scripts/verify_published_image_launch.py --tag {tag} --manifest-only",
            f"python3 scripts/verify_published_image_launch.py --tag {tag} --skip-pull",
        ],
    }


def cached_image_missing_report(
    *,
    tag: str,
    api_image: str,
    project_name: str,
    stderr: str,
    manifest_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "cached_image_missing",
        "classification": "cached_image_missing",
        "tag": tag,
        "api_image": api_image,
        "project": project_name,
        "diagnostic": (
            "--skip-pull requested cached-only verification, but Docker could not start the "
            "published API image from the local cache."
        ),
        "compose_stderr_tail": stderr[-1200:],
        "manifest_evidence": manifest_evidence or inspect_manifest_platforms(api_image),
        "next_steps": [
            f"docker pull {api_image}",
            f"python3 scripts/verify_published_image_launch.py --tag {tag} --pull-timeout-seconds 180 --allow-pull-timeout-report",
            f"python3 scripts/verify_published_image_launch.py --tag {tag} --manifest-only",
        ],
    }


def manifest_only_report(
    *,
    tag: str,
    api_image: str,
    manifest_evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "manifest_available_runtime_unverified",
        "classification": "manifest_available_runtime_unverified",
        "tag": tag,
        "api_image": api_image,
        "diagnostic": (
            "The published image manifest is available with required platforms, but this mode "
            "does not start the container or run the API smoke."
        ),
        "release_gate": "acceptable_only_with_successful_docker_images_workflow_and_release_check",
        "manifest_evidence": manifest_evidence,
        "next_steps": [
            f"python3 scripts/verify_published_image_launch.py --tag {tag} --pull-timeout-seconds 180 --allow-pull-timeout-report",
            "Verify the matching GitHub Actions docker-images workflow succeeded.",
        ],
    }


def compose_up_args(*, skip_pull: bool) -> tuple[str, ...]:
    if skip_pull:
        return ("up", "--pull", "never", "-d", "api")
    return ("up", "-d", "api")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        default="v0.3.29-alpha",
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
        "--compose-up-timeout-seconds",
        type=int,
        default=300,
        help="Timeout for docker compose up. 0 means no timeout.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Only verify the published manifest platforms; do not pull, start, or smoke the container.",
    )
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
    if args.manifest_only:
        manifest_evidence = inspect_manifest_platforms(api_image)
        if manifest_evidence.get("status") != "ok":
            raise RuntimeError(f"Published image manifest is not ready: {manifest_evidence}")
        print(
            json.dumps(
                manifest_only_report(
                    tag=tag,
                    api_image=api_image,
                    manifest_evidence=manifest_evidence,
                ),
                ensure_ascii=False,
            )
        )
        return

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
        try:
            up = run(
                compose(env_file, *compose_up_args(skip_pull=args.skip_pull)),
                capture_output=True,
                check=False,
                timeout=args.compose_up_timeout_seconds or None,
            )
        except subprocess.TimeoutExpired:
            if args.allow_pull_timeout_report and args.compose_up_timeout_seconds > 0:
                print(
                    json.dumps(
                        compose_up_timeout_report(
                            tag=tag,
                            api_image=api_image,
                            timeout_seconds=args.compose_up_timeout_seconds,
                            project_name=project_name,
                            manifest_evidence=inspect_manifest_platforms(api_image),
                        ),
                        ensure_ascii=False,
                    )
                )
                return
            raise
        if up.returncode != 0:
            if args.allow_pull_timeout_report and args.skip_pull:
                print(
                    json.dumps(
                        cached_image_missing_report(
                            tag=tag,
                            api_image=api_image,
                            project_name=project_name,
                            stderr=up.stderr or "",
                            manifest_evidence=inspect_manifest_platforms(api_image),
                        ),
                        ensure_ascii=False,
                    )
                )
                return
            raise subprocess.CalledProcessError(
                up.returncode,
                up.args,
                output=up.stdout,
                stderr=up.stderr,
            )
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
        tag, api_image = failure_context_from_argv(sys.argv[1:])
        print(json.dumps(failure_report(exc=exc, tag=tag, api_image=api_image), ensure_ascii=False, sort_keys=True))
        print(f"verify_published_image_launch failed: {sanitize_text(str(exc))}", file=sys.stderr)
        sys.exit(1)
