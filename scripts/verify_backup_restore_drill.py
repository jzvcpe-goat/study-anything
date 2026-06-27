#!/usr/bin/env python3
"""Run a disposable Docker backup/restore drill for self-host readiness."""

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
    format_api_unreachable,
    format_localhost_listen_blocked,
    is_localhost_socket_blocked,
    verifier_name_from_file,
)


COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.yml"
SETUP_ENV = ROOT / "scripts" / "setup_env.py"
SELF_HOST_DATA = ROOT / "scripts" / "self_host_data.py"
VERIFY_FULL_API_FLOW = ROOT / "scripts" / "verify_full_api_flow.py"
VERIFIER_NAME = verifier_name_from_file(__file__)
PRIVATE_PROJECT_PREFIX = "study_anything_drill_"
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


def sanitize_text(value: str | bytes | None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    text = re.sub(rf"{PRIVATE_PROJECT_PREFIX}\d+", "<compose-project>", text)
    text = re.sub(r"/Users/[^\s\"'?&]+", "<local-path>", text)
    text = re.sub(r"/private/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/tmp/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"(?i)(api[_-]?key|secret|token|password|passphrase)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", r"\1=<redacted>", text)
    text = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", text)
    text = re.sub(r"([?&](?:api[_-]?key|token|secret|password|passphrase)=)[^&\s\"']+", r"\1<redacted>", text, flags=re.IGNORECASE)
    return text.strip()[:1800]


def output_text(exc: BaseException) -> str:
    parts = [str(exc)]
    if isinstance(exc, subprocess.CalledProcessError):
        parts.append("command=" + " ".join(str(part) for part in exc.cmd))
        if exc.stdout:
            parts.append("stdout=" + str(exc.stdout))
        if exc.stderr:
            parts.append("stderr=" + str(exc.stderr))
    return "\n".join(parts)


def classify_failure(message: str) -> str:
    lowered = message.lower()
    if (
        "cannot allocate a local port" in lowered
        or "runner appears to block localhost listening sockets" in lowered
        or "operation not permitted" in lowered
        or "permission denied" in lowered
        or "localhost_socket_blocked" in lowered
    ):
        return "localhost_socket_blocked"
    if "no such file or directory" in lowered and "docker" in lowered:
        return "docker_missing"
    if "docker compose" in lowered or "compose" in lowered:
        if "up" in lowered:
            return "docker_compose_up_failed"
        if "down" in lowered:
            return "docker_compose_cleanup_failed"
        return "docker_compose_failed"
    if "docker daemon" in lowered or "cannot connect to the docker daemon" in lowered:
        return "docker_daemon_unavailable"
    if "api did not become healthy" in lowered:
        return "api_health_timeout"
    if "verify_full_api_flow" in lowered or "full_api_flow" in lowered:
        return "full_api_flow_failed"
    if "baseline smoke flow did not create" in lowered or "mutation smoke did not increase" in lowered:
        return "session_count_failed"
    if "self_host_data.py" in lowered and "backup" in lowered:
        return "backup_failed"
    if "self_host_data.py" in lowered and "restore" in lowered:
        return "restore_failed"
    if "restore did not roll back" in lowered:
        return "restore_failed"
    if "restore api should remain disabled" in lowered:
        return "recovery_status_failed"
    if "json" in lowered and "decode" in lowered:
        return "json_parse_failed"
    if "source checkout path contains non-ascii" in lowered or "ascii source copy" in lowered:
        return "ascii_reexec_failed"
    return "backup_restore_drill_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "python3 scripts/verify_backup_restore_drill.py --no-build",
        "python3 scripts/diagnose_adoption.py",
        "./scripts/doctor.sh",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run this Docker drill from a normal terminal or host shell that permits localhost listening sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "docker_missing": [
            "Install Docker Desktop or Docker Engine, then reopen the terminal so `docker` is on PATH.",
            "Use Skill Mode for a no-Docker smoke while Docker is unavailable.",
        ],
        "docker_daemon_unavailable": [
            "Start Docker Desktop or the Docker daemon.",
            "Run `docker info` and `docker compose version` before rerunning the drill.",
        ],
        "docker_compose_up_failed": [
            "Run `./scripts/doctor.sh` to check Docker, ports, Compose, and env files.",
            "Retry with `--no-build` if the image already exists and local builds are the blocker.",
        ],
        "docker_compose_failed": [
            "Inspect the Docker Compose stderr and rerun `docker compose config`.",
            "Run `./scripts/doctor.sh` for port and Docker diagnostics.",
        ],
        "docker_compose_cleanup_failed": [
            "Cleanup failed after the drill; run `docker compose down -v --remove-orphans` for the printed project manually.",
            "Do not publish the drill transcript until disposable resources are cleaned up.",
        ],
        "api_health_timeout": [
            "Inspect API container logs and the generated disposable `.env` if you kept the drill on failure.",
            "Increase `--timeout` on slow machines.",
        ],
        "full_api_flow_failed": [
            "Run `API_BASE=<drill-api> python3 scripts/verify_full_api_flow.py` to isolate API flow failures.",
            "Check the structured JSON emitted by `verify_full_api_flow.py`.",
        ],
        "session_count_failed": [
            "Inspect Postgres state in the disposable stack; backup/restore evidence needs session count changes.",
            "Rerun after confirming the full API smoke creates sessions.",
        ],
        "backup_failed": [
            "Run `python3 scripts/self_host_data.py backup --help` and inspect backup manifest diagnostics.",
            "Do not proceed to restore until backup manifest verification passes.",
        ],
        "restore_failed": [
            "Inspect restore output and Postgres container logs.",
            "Keep the drill with `--keep-on-failure` for local debugging.",
        ],
        "recovery_status_failed": [
            "Recovery status must keep destructive API restore disabled.",
            "Run `python3 scripts/verify_security_recovery_hardening.py` before this drill.",
        ],
        "json_parse_failed": [
            "A nested verifier returned non-JSON output; inspect its stderr and rerun it directly.",
            "Confirm the nested verifier and API come from the same checkout.",
        ],
        "ascii_reexec_failed": [
            "Use an ASCII-only checkout path for Docker source builds, or use published images/Skill Mode.",
            "If the script kept an ASCII temp copy, inspect it locally and remove it after debugging.",
        ],
    }
    return matrix.get(classification, ["Rerun the backup/restore drill after fixing the reported invariant."]) + common


def failure_report(exc: BaseException) -> dict[str, Any]:
    diagnostic = sanitize_text(output_text(exc))
    classification = classify_failure(diagnostic)
    report = {
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": failure_next_steps(classification),
        "source": {
            "verifier": VERIFIER_NAME,
            "compose_file": sanitize_text(str(COMPOSE_FILE.relative_to(ROOT))),
        },
        "privacy": {
            "env_file_paths_included": False,
            "backup_paths_included": False,
            "local_absolute_paths_included": False,
            "generated_secrets_included": False,
            "learner_answers_included": False,
            "raw_source_text_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def format_cli_failure(report: dict[str, Any]) -> str:
    lines = [
        "verify_backup_restore_drill failed:",
        f"classification: {report.get('classification')}",
        f"Diagnostic: {report.get('diagnostic')}",
        "Next steps:",
    ]
    lines.extend(f"- {step}" for step in report.get("next_steps", []))
    return "\n".join(lines)


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks: list[str] = []
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"/tmp/[^\s\"']+", serialized):
        leaks.append("tmp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if re.search(rf"{PRIVATE_PROJECT_PREFIX}\d+", serialized):
        leaks.append("compose project name")
    if leaks:
        raise RuntimeError(f"Backup/restore drill failure report leaked private data: {leaks}")


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
        f"for Docker BuildKit: {sanitize_text(str(target))}",
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
        print(f"Kept ASCII source copy for debugging: {sanitize_text(str(target))}", file=sys.stderr)
    raise SystemExit(result.returncode)


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
    run([sys.executable, str(SETUP_ENV), "--force", "--output", str(env_file)], capture_output=True)
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


def wait_for_api(api_base: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            request_json(api_base, "/v1/health")
            return
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            if isinstance(exc, (URLError, TimeoutError, OSError)):
                last_error = format_api_unreachable(api_base, exc, verifier=VERIFIER_NAME)
            else:
                last_error = str(exc)
            time.sleep(2)
    raise RuntimeError(f"API did not become healthy within {timeout_seconds}s: {last_error}")


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
    backup_dir = work_dir / "backup"
    cleanup = True

    try:
        up_command = ["up", "-d"]
        if not args.no_build:
            up_command.append("--build")
        up_command.append("api")
        run(compose(env_file, *up_command))
        wait_for_api(api_base, args.timeout)

        baseline_flow = verify_flow(api_base)
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
                    "baseline_session_count": baseline_count,
                    "mutated_session_count": mutated_count,
                    "restored_session_count": restored_count,
                    "baseline_session_id": baseline_flow["session_id"],
                    "mutated_session_id": mutated_flow["session_id"],
                    "backup_manifest": str(backup_dir / "manifest.json"),
                    "restore_api_enabled": recovery["restore_api_enabled"],
                    "registry_verified_plugins": baseline_flow.get("registry_verified_plugins"),
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
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_cli_failure(report), file=sys.stderr)
        sys.exit(1)
