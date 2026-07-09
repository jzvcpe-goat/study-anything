#!/usr/bin/env python3
"""Run an isolated source-build or published-image restart soak."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.yml"
IMAGE_COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.images.yml"
SETUP_ENV = ROOT / "scripts" / "setup_env.py"
VERIFY_FULL_API_FLOW = ROOT / "scripts" / "verify_full_api_flow.py"
DEFAULT_OUTPUT = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "reliability"
    / "self-host-reliability-matrix.json"
)
SCHEMA_VERSION = "self-host-reliability-matrix-receipt-v1"
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

SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from self_host_soak import run_soak  # noqa: E402


class ReliabilityMatrixError(RuntimeError):
    """Classified failure without carrying raw command output into receipts."""

    def __init__(self, phase: str, category: str) -> None:
        super().__init__(f"{phase}:{category}")
        self.phase = phase
        self.category = category


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def compose(env_file: Path, mode: str, *args: str) -> list[str]:
    values = parse_env(env_file)
    command = [
        "docker",
        "compose",
        "--project-name",
        values["COMPOSE_PROJECT_NAME"],
        "--env-file",
        str(env_file),
        "-f",
        str(COMPOSE_FILE),
    ]
    if mode == "published-image":
        command.extend(["-f", str(IMAGE_COMPOSE_FILE)])
    command.extend(args)
    return command


def compose_up_args(mode: str) -> list[str]:
    if mode == "source-build":
        return ["up", "--build", "-d", "api"]
    return ["up", "-d", "api"]


def run_command(
    command: list[str],
    *,
    phase: str,
    timeout_seconds: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReliabilityMatrixError(phase, "timeout") from exc
    if completed.returncode != 0:
        raise ReliabilityMatrixError(phase, "command_failed")
    return completed


def source_revision() -> tuple[str, bool]:
    revision = run_command(
        ["git", "rev-parse", "HEAD"],
        phase="source_revision",
        timeout_seconds=30,
    ).stdout.strip()
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise ReliabilityMatrixError("source_revision", "invalid_commit_sha")
    dirty = bool(
        run_command(
            ["git", "status", "--porcelain"],
            phase="source_revision",
            timeout_seconds=30,
        ).stdout.strip()
    )
    return revision, dirty


def inspect_image_digest(image_reference: str) -> str:
    result = run_command(
        ["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image_reference],
        phase="image_identity",
        timeout_seconds=60,
    )
    try:
        repo_digests = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise ReliabilityMatrixError("image_identity", "invalid_json") from exc
    if not isinstance(repo_digests, list):
        raise ReliabilityMatrixError("image_identity", "digest_missing")
    for value in repo_digests:
        if not isinstance(value, str) or "@" not in value:
            continue
        digest = value.rsplit("@", 1)[-1]
        if digest.startswith("sha256:") and len(digest) == 71:
            return digest
    raise ReliabilityMatrixError("image_identity", "digest_missing")


def create_env(
    work_dir: Path,
    *,
    project_name: str,
    mode: str,
    tag: str,
    api_image: str,
) -> Path:
    env_file = work_dir / ".env"
    run_command(
        [sys.executable, str(SETUP_ENV), "--force", "--output", str(env_file)],
        phase="environment_setup",
        timeout_seconds=60,
    )
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
        "PYTHON_BASE_IMAGE": "public.ecr.aws/docker/library/python:3.11-slim",
    }
    additions.update({key: str(free_port()) for key in PORT_KEYS})
    with env_file.open("a", encoding="utf-8") as target:
        target.write(f"\n# disposable {mode} reliability overrides\n")
        for key, value in additions.items():
            target.write(f"{key}={value}\n")
    env_file.chmod(0o600)
    return env_file


def request_json(api_base: str, path: str) -> Any:
    request = Request(f"{api_base.rstrip('/')}{path}", method="GET")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_api(api_base: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            payload = request_json(api_base, "/v1/health")
            if payload.get("status") == "ok":
                return
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            pass
        time.sleep(2)
    raise ReliabilityMatrixError("startup", "api_health_timeout")


def verify_flow(api_base: str, timeout_seconds: int) -> dict[str, Any]:
    result = run_command(
        [sys.executable, str(VERIFY_FULL_API_FLOW)],
        phase="api_flow",
        timeout_seconds=timeout_seconds,
        env={**os.environ, "API_BASE": api_base},
    )
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ReliabilityMatrixError("api_flow", "invalid_json") from exc


def verify_persisted_session(api_base: str, flow_result: Mapping[str, Any]) -> None:
    session_id = flow_result.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ReliabilityMatrixError("session_recovery", "missing_session_id")
    try:
        mastery = request_json(api_base, f"/v1/sessions/{session_id}/mastery")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise ReliabilityMatrixError("session_recovery", "request_failed") from exc
    if not isinstance(mastery, Mapping) or not mastery.get("level"):
        raise ReliabilityMatrixError("session_recovery", "invalid_mastery_response")


def build_receipt(
    *,
    mode: str,
    status: str,
    started_at: str,
    finished_at: str,
    samples_requested: int,
    interval_seconds: float,
    fault_after_seconds: float,
    fault_duration_seconds: float,
    soak: dict[str, object] | None,
    api_flow_completed: bool,
    source_build_completed: bool,
    image_pull_completed: bool,
    restart_attempted: bool,
    restart_completed: bool,
    session_recovery_completed: bool,
    source_revision_sha: str | None = None,
    source_worktree_dirty: bool | None = None,
    published_image_digest: str | None = None,
    failure_phase: str | None = None,
    failure_category: str | None = None,
    tag: str | None = None,
) -> dict[str, object]:
    sampling = soak.get("sampling") if soak else None
    recovery_observed = bool(
        isinstance(sampling, Mapping) and sampling.get("recovered_after_failure")
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "mode": mode,
        "started_at": started_at,
        "finished_at": finished_at,
        "schedule": {
            "samples_requested": samples_requested,
            "interval_seconds": interval_seconds,
            "fault_after_seconds": fault_after_seconds,
            "fault_duration_seconds": fault_duration_seconds,
            "real_elapsed_time_required": True,
            "accelerated_clock_used": False,
        },
        "runtime": {
            "api_flow_completed": api_flow_completed,
            "source_build_completed": source_build_completed,
            "published_image_pull_completed": image_pull_completed,
            "controlled_restart_attempted": restart_attempted,
            "controlled_restart_completed": restart_completed,
            "recovery_after_failure_observed": recovery_observed,
            "pre_restart_session_recovery_completed": session_recovery_completed,
            "published_tag": tag if mode == "published-image" else None,
            "published_image_digest": published_image_digest,
            "source_revision_sha": source_revision_sha,
            "source_worktree_dirty": source_worktree_dirty,
            "image_reference_included": False,
            "compose_project_included": False,
        },
        "soak": soak,
        "failure": {
            "phase": failure_phase,
            "category": failure_category,
            "raw_error_included": False,
            "command_output_included": False,
        },
        "privacy": {
            "metadata_only": True,
            "api_url_included": False,
            "env_file_path_included": False,
            "compose_project_name_included": False,
            "docker_logs_included": False,
            "command_stdout_included": False,
            "command_stderr_included": False,
            "local_absolute_paths_included": False,
            "secrets_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
            "disposable_test_volumes_only": True,
        },
        "claim_boundary": (
            "This receipt proves only one real elapsed-time isolated Compose window for the selected "
            "runtime mode, including one controlled API interruption and observed HTTP recovery. "
            "It is not a production SLO, disaster-recovery certification, or customer availability guarantee."
        ),
    }


def write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    path.chmod(0o600)


def run_matrix(args: argparse.Namespace) -> dict[str, object]:
    started_at = utc_now()
    project_name = f"study_anything_reliability_{args.mode.replace('-', '_')}_{int(time.time())}"
    work_dir = Path(tempfile.mkdtemp(prefix="study-anything-reliability-"))
    env_file: Path | None = None
    soak: dict[str, object] | None = None
    api_flow_completed = False
    source_build_completed = False
    image_pull_completed = False
    restart_attempted = False
    restart_completed = False
    session_recovery_completed = False
    source_revision_sha: str | None = None
    source_worktree_dirty: bool | None = None
    published_image_digest: str | None = None
    failure: ReliabilityMatrixError | None = None
    tag = args.tag if args.mode == "published-image" else None

    try:
        api_image = args.api_image or f"ghcr.io/jzvcpe-goat/study-anything/api:{args.tag}"
        if args.mode == "source-build":
            source_revision_sha, source_worktree_dirty = source_revision()
        env_file = create_env(
            work_dir,
            project_name=project_name,
            mode=args.mode,
            tag=args.tag,
            api_image=api_image,
        )
        values = parse_env(env_file)
        api_base = f"http://127.0.0.1:{values['API_PORT']}"

        if args.mode == "published-image":
            run_command(
                compose(env_file, args.mode, "pull", "api"),
                phase="image_pull",
                timeout_seconds=args.pull_timeout_seconds,
            )
            image_pull_completed = True
            published_image_digest = inspect_image_digest(api_image)
        run_command(
            compose(env_file, args.mode, *compose_up_args(args.mode)),
            phase="compose_start",
            timeout_seconds=args.startup_timeout_seconds,
        )
        source_build_completed = args.mode == "source-build"
        wait_for_api(api_base, args.startup_timeout_seconds)
        flow_result = verify_flow(api_base, args.flow_timeout_seconds)
        api_flow_completed = True

        fault_result: dict[str, object] = {"error": None}

        def inject_restart() -> None:
            nonlocal restart_completed
            try:
                time.sleep(args.fault_after_seconds)
                run_command(
                    compose(env_file, args.mode, "stop", "api"),
                    phase="controlled_stop",
                    timeout_seconds=args.startup_timeout_seconds,
                )
                time.sleep(args.fault_duration_seconds)
                run_command(
                    compose(env_file, args.mode, "start", "api"),
                    phase="controlled_start",
                    timeout_seconds=args.startup_timeout_seconds,
                )
                restart_completed = True
            except ReliabilityMatrixError as exc:
                fault_result["error"] = exc
            except Exception:
                fault_result["error"] = ReliabilityMatrixError(
                    "controlled_restart", "unexpected_error"
                )

        fault_thread = threading.Thread(target=inject_restart, daemon=True)
        restart_attempted = True
        fault_thread.start()
        soak = run_soak(
            api_base=api_base,
            token=None,
            sample_count=args.samples,
            interval_seconds=args.interval_seconds,
            request_timeout_seconds=args.request_timeout_seconds,
            min_success_ratio=args.min_success_ratio,
            max_consecutive_failures=args.max_consecutive_failures,
            require_recovery=True,
        )
        fault_thread.join(
            timeout=args.fault_after_seconds
            + args.fault_duration_seconds
            + args.startup_timeout_seconds
        )
        if fault_thread.is_alive():
            raise ReliabilityMatrixError("controlled_restart", "thread_timeout")
        if isinstance(fault_result["error"], ReliabilityMatrixError):
            raise fault_result["error"]
        wait_for_api(api_base, args.startup_timeout_seconds)
        verify_persisted_session(api_base, flow_result)
        session_recovery_completed = True
        if soak["status"] != "pass":
            raise ReliabilityMatrixError("soak", "reliability_gate_blocked")
    except ReliabilityMatrixError as exc:
        failure = exc
    except Exception:
        failure = ReliabilityMatrixError("runtime", "unexpected_error")
    finally:
        if env_file is not None and not (failure and args.keep_on_failure):
            try:
                run_command(
                    compose(
                        env_file,
                        args.mode,
                        "down",
                        "-v",
                        "--remove-orphans",
                    ),
                    phase="cleanup",
                    timeout_seconds=args.startup_timeout_seconds,
                )
            except ReliabilityMatrixError as exc:
                failure = failure or exc
        if not (failure and args.keep_on_failure):
            shutil.rmtree(work_dir, ignore_errors=True)

    status = "pass" if failure is None else "blocked"
    return build_receipt(
        mode=args.mode,
        status=status,
        started_at=started_at,
        finished_at=utc_now(),
        samples_requested=args.samples,
        interval_seconds=args.interval_seconds,
        fault_after_seconds=args.fault_after_seconds,
        fault_duration_seconds=args.fault_duration_seconds,
        soak=soak,
        api_flow_completed=api_flow_completed,
        source_build_completed=source_build_completed,
        image_pull_completed=image_pull_completed,
        restart_attempted=restart_attempted,
        restart_completed=restart_completed,
        session_recovery_completed=session_recovery_completed,
        source_revision_sha=source_revision_sha,
        source_worktree_dirty=source_worktree_dirty,
        published_image_digest=published_image_digest,
        failure_phase=failure.phase if failure else None,
        failure_category=failure.category if failure else None,
        tag=tag,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("source-build", "published-image"), required=True)
    parser.add_argument("--samples", type=int, default=721)
    parser.add_argument("--interval-seconds", type=float, default=10.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--fault-after-seconds", type=float, default=600.0)
    parser.add_argument("--fault-duration-seconds", type=float, default=45.0)
    parser.add_argument("--min-success-ratio", type=float, default=0.99)
    parser.add_argument("--max-consecutive-failures", type=int, default=8)
    parser.add_argument("--startup-timeout-seconds", type=int, default=300)
    parser.add_argument("--flow-timeout-seconds", type=int, default=180)
    parser.add_argument("--pull-timeout-seconds", type=int, default=600)
    parser.add_argument("--tag", default="main")
    parser.add_argument("--api-image")
    parser.add_argument("--keep-on-failure", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    total_window = (args.samples - 1) * args.interval_seconds
    if args.samples < 3:
        parser.error("--samples must be at least 3")
    if args.interval_seconds <= 0 or args.request_timeout_seconds <= 0:
        parser.error("interval and request timeout must be positive")
    if args.fault_after_seconds < 0 or args.fault_duration_seconds <= 0:
        parser.error("fault timing must be non-negative with positive duration")
    if args.fault_after_seconds + args.fault_duration_seconds >= total_window:
        parser.error("the controlled fault must finish before the final scheduled probe")
    if not 0 < args.min_success_ratio <= 1:
        parser.error("--min-success-ratio must be greater than 0 and at most 1")
    if args.max_consecutive_failures < 1:
        parser.error("--max-consecutive-failures must be at least 1")
    return args


def main() -> None:
    args = parse_args()
    receipt = run_matrix(args)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    write_receipt(output, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if receipt["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
