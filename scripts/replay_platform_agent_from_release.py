#!/usr/bin/env python3
"""Replay Study Anything platform-agent tools from public release assets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "scripts" / "verify_release_asset_adoption.py"
SCHEMA_VERSION = "platform-agent-release-replay-v1"
DEFAULT_REPO = "jzvcpe-goat/study-anything"
DEFAULT_TAG = "v0.3.26-alpha"
PACK_ROOT = "study-anything-platform-adoption-pack"
REQUIRED_TOOLS = [
    "study_anything_health",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
]
PLATFORM_ENTRYPOINTS = {
    "kimi": [
        "platform/generated/study-anything-openai-tools.json",
        "platform/generated/study-anything-platform-openapi.json",
        "platform/packs/kimi/README.md",
    ],
    "codex": [
        "skills/study-anything/SKILL.md",
        "platform/packs/codex/README.md",
        "scripts/study_anything_cli.py",
    ],
    "workbuddy": [
        "platform/generated/study-anything-platform-openapi.json",
        "platform/generated/study-anything-tool-catalog.md",
        "platform/packs/workbuddy/README.md",
    ],
    "generic-openapi": [
        "platform/generated/study-anything-platform-openapi.json",
        "platform/generated/study-anything-tool-catalog.md",
    ],
}
CLASSIFICATIONS = {
    "platform_agent_replay_ready",
    "platform_agent_replay_metadata_ready",
    "tool_import_invalid",
    "api_unavailable",
    "runtime_launch_failed",
    "tool_call_failed",
    "schema_mismatch",
    "privacy_leak",
    "platform_entrypoint_missing",
    "release_asset_invalid",
}
RECOVERY_PLAN = {
    "tool_import_invalid": [
        "Regenerate platform tools and adoption pack.",
        "Run `python3 scripts/generate_platform_agent_assets.py --check` and `python3 scripts/generate_platform_adoption_pack.py --check`.",
    ],
    "api_unavailable": [
        "Start Study Anything with `./scripts/launch_skill_mode.sh` or provide `--api-base` for a running deployment.",
        "Confirm `GET /v1/health` returns status ok before replaying platform tools.",
    ],
    "runtime_launch_failed": [
        "Run `./scripts/doctor.sh` and retry Skill Mode from an ASCII-only checkout path.",
        "Use `--runtime external-api --api-base <url>` if another platform already launched Study Anything.",
    ],
    "tool_call_failed": [
        "Replay with the same release assets and attach the redacted transcript to a GitHub issue.",
        "Run `API_BASE=<url> python3 scripts/verify_platform_agent_tools.py` for the broader runtime verifier.",
    ],
    "schema_mismatch": [
        "Regenerate OpenAPI/OpenAI tool assets and rerun the platform replay simulator.",
        "Check that the API version matches the release asset tag.",
    ],
    "privacy_leak": [
        "Do not share the transcript. Remove raw source text, answers, API keys, or local paths before filing an issue.",
        "Fix the leaking endpoint or transcript sanitizer before release.",
    ],
    "platform_entrypoint_missing": [
        "Regenerate the platform adoption pack and confirm the selected platform pack is present.",
        "Run `python3 scripts/generate_platform_adoption_pack.py --check`.",
    ],
    "release_asset_invalid": [
        "Run `python3 scripts/bootstrap_from_release.py --tag <tag> --runtime metadata-only` for lower-level asset diagnostics.",
        "Recreate the GitHub Release assets from the matching main commit.",
    ],
}
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private platform replay source text",
    "Private platform replay learner answer",
    "sk-",
    "AGENT_ENDPOINT=http",
]


class ReplayError(RuntimeError):
    """Readable replay failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReplayError(f"Cannot read JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ReplayError(f"JSON object expected: {path.name}")
    return payload


def load_release_verifier() -> Any:
    spec = importlib.util.spec_from_file_location("study_anything_release_asset_verifier", VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise ReplayError("Could not load release asset verifier.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sanitize_error(message: str) -> str:
    first_line = (message or "Replay failed.").splitlines()[0]
    first_line = re.sub(r"/Users/[^\s\"']+", "<local-path>", first_line)
    first_line = re.sub(r"/private/var/folders/[^\s\"']+", "<temp-path>", first_line)
    first_line = re.sub(r"/var/folders/[^\s\"']+", "<temp-path>", first_line)
    return first_line[:800]


def classify_error(message: str) -> str:
    lowered = message.lower()
    if "platform entrypoint" in lowered or "entrypoint" in lowered:
        return "platform_entrypoint_missing"
    if "tool import" in lowered or "openapi" in lowered or "openai tool" in lowered:
        return "tool_import_invalid"
    if "api unavailable" in lowered or "cannot reach" in lowered or "connection refused" in lowered:
        return "api_unavailable"
    if "runtime launch" in lowered or "launch_skill_mode" in lowered:
        return "runtime_launch_failed"
    if "schema" in lowered or "expected" in lowered or "did not return" in lowered or "did not contain" in lowered:
        return "schema_mismatch"
    if "privacy" in lowered or "leaked" in lowered:
        return "privacy_leak"
    if "release" in lowered or "asset" in lowered or "zip" in lowered:
        return "release_asset_invalid"
    return "tool_call_failed"


def assert_redacted(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", serialized):
        leaks.append("secret-looking assignment")
    if leaks:
        raise ReplayError(f"Platform replay transcript leaked private data: {leaks}")


def make_verifier_namespace(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        repo=args.repo,
        tag=args.tag,
        asset_dir=args.asset_dir,
        release_json=args.release_json,
        fixture=args.fixture,
        runtime="metadata-only",
        skip_pull=args.skip_pull,
        expect_failure=args.expect_failure,
        keep=args.keep,
        include_asset_dir=False,
        python=args.python,
        timeout_seconds=args.timeout_seconds,
        network_timeout_seconds=args.network_timeout_seconds,
        pull_timeout_seconds=args.pull_timeout_seconds,
    )


def prepare_pack(args: argparse.Namespace) -> tuple[Path, dict[str, Any], dict[str, Any], Path]:
    verifier = load_release_verifier()
    verifier_args = make_verifier_namespace(args)
    fixture_classification = verifier.classification_from_fixture(verifier_args)
    if fixture_classification and args.expect_failure and fixture_classification != "release_asset_adoption_ready":
        raise ReplayError(f"Expected failure fixture: {fixture_classification}")
    work_root = Path(tempfile.mkdtemp(prefix="study-anything-platform-replay-"))
    asset_dir = Path(args.asset_dir).resolve() if args.asset_dir else work_root / "assets"
    try:
        release = verifier.load_release_metadata(verifier_args)
        assets = verifier.materialize_assets(verifier_args, release, asset_dir)
        pack_root = verifier.extract_adoption_pack(asset_dir, work_root)
        pack = verifier.validate_pack(pack_root, asset_dir)
    except Exception:
        if not args.keep and not args.asset_dir:
            shutil.rmtree(work_root, ignore_errors=True)
        raise
    return pack_root, pack, assets, work_root


def load_tool_contract(pack_root: Path, platform: str) -> dict[str, Any]:
    missing_entrypoints = [
        path for path in PLATFORM_ENTRYPOINTS[platform] if not (pack_root / path).is_file()
    ]
    if missing_entrypoints:
        raise ReplayError(f"Platform entrypoint missing for {platform}: {missing_entrypoints}")
    openai_tools_path = pack_root / "platform/generated/study-anything-openai-tools.json"
    openapi_path = pack_root / "platform/generated/study-anything-platform-openapi.json"
    try:
        openai_tools = json.loads(openai_tools_path.read_text(encoding="utf-8"))
        openapi = json.loads(openapi_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReplayError("Tool import assets are not readable JSON.") from exc
    if not isinstance(openai_tools, list):
        raise ReplayError("OpenAI tool manifest must be a list.")
    if openapi.get("openapi") != "3.1.0":
        raise ReplayError("OpenAPI manifest must be version 3.1.0.")
    if (openapi.get("components") or {}).get("securitySchemes"):
        raise ReplayError("OpenAPI manifest must not declare API-key security schemes.")

    openai_names = {
        str(item.get("function", {}).get("name"))
        for item in openai_tools
        if isinstance(item, dict) and isinstance(item.get("function"), dict)
    }
    operations: dict[str, dict[str, str]] = {}
    for path, methods in (openapi.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if isinstance(operation, dict) and operation.get("operationId"):
                operations[str(operation["operationId"])] = {
                    "method": method.upper(),
                    "path_template": str(path),
                }
    missing = [name for name in REQUIRED_TOOLS if name not in openai_names or name not in operations]
    if missing:
        raise ReplayError(f"Tool import missing required replay tools: {missing}")
    return {
        "openai_tool_count": len(openai_names),
        "openapi_operation_count": len(operations),
        "operations": operations,
        "required_tools": list(REQUIRED_TOOLS),
        "platform_entrypoints": PLATFORM_ENTRYPOINTS[platform],
    }


def url_for(api_base: str, path_template: str, path_params: dict[str, str] | None = None) -> str:
    path = path_template
    for key, value in (path_params or {}).items():
        path = path.replace("{" + key + "}", quote(value, safe=""))
    if "{" in path or "}" in path:
        raise ReplayError(f"Unresolved path parameter in {path_template}")
    return f"{api_base.rstrip('/')}{path}"


def call_operation(
    *,
    api_base: str,
    operation: dict[str, str],
    payload: dict[str, Any] | None = None,
    path_params: dict[str, str] | None = None,
    timeout_seconds: int,
) -> tuple[dict[str, Any], int, float]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url_for(api_base, operation["path_template"], path_params),
        data=body,
        headers={"Content-Type": "application/json"},
        method=operation["method"],
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict):
                raise ReplayError(f"Tool response must be a JSON object for {operation['path_template']}")
            return data, int(response.status), (time.monotonic() - started) * 1000
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise ReplayError(f"Tool call failed with HTTP {exc.code}: {operation['path_template']} {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ReplayError(f"API unavailable for {operation['path_template']}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReplayError(f"Tool response was not JSON for {operation['path_template']}") from exc


def response_summary(name: str, response: dict[str, Any]) -> dict[str, Any]:
    if name == "study_anything_health":
        return {"status": response.get("status"), "version": response.get("version")}
    if name == "study_anything_create_session":
        return {"status": response.get("status"), "session_id_present": bool(response.get("session_id"))}
    if name == "study_anything_add_reading":
        source = response.get("source") or {}
        return {"status": response.get("status"), "excerpt_hash_present": bool(source.get("excerpt_hash"))}
    if name == "study_anything_run":
        return {"stage": response.get("stage"), "quiz_item_count": len(response.get("quiz_items") or [])}
    if name == "study_anything_answer":
        return {"stage": response.get("stage")}
    if name == "study_anything_mastery":
        return {"level": response.get("level"), "bloom": response.get("bloom")}
    if name == "study_anything_agent_audit":
        return {
            "schema_version": response.get("schema_version"),
            "status": response.get("status"),
            "observed_task_count": len(response.get("observed_tasks") or []),
        }
    if name == "study_anything_agent_eval_artifact":
        return {
            "schema_version": response.get("schema_version"),
            "status": response.get("status"),
            "trajectory_count": len(response.get("trajectory") or []),
        }
    return {"schema_version": response.get("schema_version"), "status": response.get("status")}


def record_step(
    steps: list[dict[str, Any]],
    *,
    name: str,
    operation: dict[str, str],
    payload: dict[str, Any] | None,
    status_code: int,
    latency_ms: float,
    response: dict[str, Any],
) -> None:
    steps.append(
        {
            "tool_name": name,
            "operation_id": name,
            "method": operation["method"],
            "path_template": operation["path_template"],
            "payload_keys": sorted((payload or {}).keys()),
            "status": "ok",
            "status_code": status_code,
            "latency_ms": round(latency_ms, 2),
            "response_summary": response_summary(name, response),
        }
    )


def validate_learning_responses(
    *,
    health: dict[str, Any],
    session: dict[str, Any],
    reading: dict[str, Any],
    running: dict[str, Any],
    completed: dict[str, Any],
    mastery: dict[str, Any],
    audit: dict[str, Any],
    artifact: dict[str, Any],
) -> str:
    if health.get("status") != "ok":
        raise ReplayError(f"Expected health status ok, got {health.get('status')}")
    session_id = session.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ReplayError("Create session did not return a session_id.")
    if not (reading.get("source") or {}).get("excerpt_hash"):
        raise ReplayError("Add reading did not return a source excerpt hash.")
    quiz_items = running.get("quiz_items") or []
    if not quiz_items or not quiz_items[0].get("item_id"):
        raise ReplayError("Run did not return a quiz item id.")
    if completed.get("stage") != "completed":
        raise ReplayError(f"Answer did not complete the learning loop: {completed.get('stage')}")
    if not isinstance(mastery.get("level"), (int, float)) or not mastery.get("bloom"):
        raise ReplayError("Mastery response did not contain level and bloom.")
    if audit.get("schema_version") != "agent-audit-v1" or audit.get("status") != "verified":
        raise ReplayError("Agent audit did not return verified agent-audit-v1 evidence.")
    if artifact.get("schema_version") != "agent-eval-artifact-v1":
        raise ReplayError("Agent eval artifact schema mismatch.")
    if artifact.get("status") != "ready_for_external_eval":
        raise ReplayError("Agent eval artifact is not ready for external eval.")
    return session_id


def replay_tool_chain(
    *,
    api_base: str,
    operations: dict[str, dict[str, str]],
    timeout_seconds: int,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    private_source = "Private platform replay source text must not appear in transcript."
    private_answer = "Private platform replay learner answer must not appear in transcript."
    user_id = "platform-replay-user"

    def call(name: str, payload: dict[str, Any] | None = None, **path_params: str) -> dict[str, Any]:
        response, status_code, latency_ms = call_operation(
            api_base=api_base,
            operation=operations[name],
            payload=payload,
            path_params=path_params,
            timeout_seconds=timeout_seconds,
        )
        record_step(
            steps,
            name=name,
            operation=operations[name],
            payload=payload,
            status_code=status_code,
            latency_ms=latency_ms,
            response=response,
        )
        return response

    health = call("study_anything_health")
    session = call(
        "study_anything_create_session",
        {"user_id": user_id, "track": "ACADEMIC", "use_demo_agent": True},
    )
    session_id = str(session.get("session_id") or "")
    reading = call(
        "study_anything_add_reading",
        {
            "source_type": "local_text",
            "reference": "release-replay://platform-agent",
            "title": "Release Replay Source",
            "text": private_source,
        },
        session_id=session_id,
    )
    running = call("study_anything_run", {}, session_id=session_id)
    quiz_items = running.get("quiz_items") or []
    quiz_id = str((quiz_items[0] or {}).get("item_id") if quiz_items else "")
    completed = call("study_anything_answer", {"answers": {quiz_id: private_answer}}, session_id=session_id)
    mastery = call("study_anything_mastery", session_id=session_id)
    audit = call("study_anything_agent_audit", session_id=session_id)
    artifact = call("study_anything_agent_eval_artifact", session_id=session_id)
    validate_learning_responses(
        health=health,
        session=session,
        reading=reading,
        running=running,
        completed=completed,
        mastery=mastery,
        audit=audit,
        artifact=artifact,
    )
    transcript_fragment = {
        "tool_call_count": len(steps),
        "steps": steps,
        "learning_loop": {
            "session_id_present": True,
            "completed_stage": completed.get("stage"),
            "mastery_level": mastery.get("level"),
            "mastery_bloom": mastery.get("bloom"),
            "agent_audit_status": audit.get("status"),
            "eval_artifact_status": artifact.get("status"),
            "trajectory_count": len(artifact.get("trajectory") or []),
        },
    }
    assert_redacted(transcript_fragment)
    return transcript_fragment


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_api(api_base: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            request = Request(f"{api_base.rstrip('/')}/v1/health", method="GET")
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if isinstance(payload, dict) and payload.get("status") == "ok":
                    return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    raise ReplayError(f"API unavailable after runtime launch: {last_error}")


def run_command(command: list[str], *, cwd: Path, env: dict[str, str], timeout_seconds: int) -> None:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReplayError(f"Runtime launch command timed out: {' '.join(command)}") from exc
    if completed.returncode != 0:
        raise ReplayError(f"Runtime launch command failed: {' '.join(command)}")


def launch_skill_mode(args: argparse.Namespace) -> tuple[str, dict[str, str]]:
    port = free_port()
    env = os.environ.copy()
    env.update(
        {
            "API_PORT": str(port),
            "SKILL_API_HOST": "127.0.0.1",
            "STUDY_ANYTHING_API_BASE": f"http://127.0.0.1:{port}",
            "API_BASE": f"http://127.0.0.1:{port}",
            "STUDY_ANYTHING_RETRIEVAL_BACKEND": "memory",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
    if args.python:
        env["PYTHON_BIN"] = args.python
    if (ROOT / ".venv").exists():
        env["STUDY_ANYTHING_VENV"] = str(ROOT / ".venv")
    try:
        run_command(["./scripts/launch_skill_mode.sh"], cwd=ROOT, env=env, timeout_seconds=args.timeout_seconds)
        wait_for_api(env["API_BASE"], 60)
    except Exception as exc:
        raise ReplayError(f"Runtime launch failed for Skill Mode: {exc}") from exc
    return env["API_BASE"], env


def stop_skill_mode(env: dict[str, str]) -> None:
    subprocess.run(
        ["./scripts/stop_skill_mode.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def api_base_for_runtime(args: argparse.Namespace) -> tuple[str | None, dict[str, str] | None]:
    if args.runtime == "metadata-only":
        return None, None
    if args.runtime == "skill-mode":
        return launch_skill_mode(args)
    if args.runtime in {"external-api", "published-image"}:
        if not args.api_base:
            raise ReplayError(f"API unavailable: --api-base is required for {args.runtime} replay.")
        return args.api_base.rstrip("/"), None
    raise ReplayError(f"Unsupported runtime: {args.runtime}")


def build_failure_transcript(args: argparse.Namespace, classification: str, diagnostic: str, status: str = "blocked") -> dict[str, Any]:
    transcript = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "classification": classification,
        "tag": args.tag,
        "repo": args.repo,
        "platform": args.platform,
        "runtime": args.runtime,
        "diagnostic": sanitize_error(diagnostic),
        "recovery_plan": {classification: RECOVERY_PLAN.get(classification, RECOVERY_PLAN["tool_call_failed"])},
        "privacy": privacy_assertions(),
    }
    assert_redacted(transcript)
    return transcript


def privacy_assertions() -> dict[str, bool]:
    return {
        "raw_source_text_included": False,
        "learner_answers_included": False,
        "agent_prompts_included": False,
        "agent_endpoint_secrets_included": False,
        "real_model_keys_included": False,
        "support_bundle_private_payload_included": False,
        "local_absolute_paths_included": False,
        "automatic_upload": False,
    }


def run_replay(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    pack_root, pack, assets, work_root = prepare_pack(args)
    runtime_env: dict[str, str] | None = None
    try:
        tool_contract = load_tool_contract(pack_root, args.platform)
        api_base, runtime_env = api_base_for_runtime(args)
        replay = (
            {
                "tool_call_count": 0,
                "steps": [],
                "learning_loop": None,
            }
            if api_base is None
            else replay_tool_chain(
                api_base=api_base,
                operations=tool_contract["operations"],
                timeout_seconds=args.request_timeout_seconds,
            )
        )
        classification = (
            "platform_agent_replay_metadata_ready"
            if args.runtime == "metadata-only"
            else "platform_agent_replay_ready"
        )
        transcript = {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "classification": classification,
            "tag": args.tag,
            "repo": args.repo,
            "platform": args.platform,
            "runtime": {
                "requested": args.runtime,
                "api_base_provided": bool(args.api_base),
                "api_base_kind": "not_started" if api_base is None else "local_or_private",
            },
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "release_assets": {
                "asset_count": len(assets),
                "github_digest_verified_count": sum(1 for item in assets.values() if item.get("github_digest_verified")),
                "required_assets": sorted(assets),
            },
            "adoption_pack": {
                "schema_version": pack.get("schema_version"),
                "version": pack.get("version"),
                "file_count": pack.get("file_count"),
                "tool_count": pack.get("tool_count"),
                "no_frontend_required": pack.get("no_frontend_required"),
                "real_model_keys_stored_by_study_anything": pack.get("real_model_keys_stored_by_study_anything"),
            },
            "tool_import": {
                "status": "ready",
                "openai_tool_count": tool_contract["openai_tool_count"],
                "openapi_operation_count": tool_contract["openapi_operation_count"],
                "required_tools": tool_contract["required_tools"],
                "platform_entrypoints": tool_contract["platform_entrypoints"],
            },
            "replay": replay,
            "privacy": privacy_assertions(),
            "acceptance": {
                "release_asset_bootstrap": "release-asset-bootstrap-v1",
                "platform_replay_schema": SCHEMA_VERSION,
                "safe_for_external_platform_agent": True,
            },
        }
        assert_redacted(transcript)
        return transcript
    finally:
        if runtime_env is not None:
            stop_skill_mode(runtime_env)
        if not args.keep and not args.asset_dir:
            shutil.rmtree(work_root, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--asset-dir")
    parser.add_argument("--release-json")
    parser.add_argument("--fixture")
    parser.add_argument("--platform", choices=sorted(PLATFORM_ENTRYPOINTS), default="kimi")
    parser.add_argument(
        "--runtime",
        choices=["metadata-only", "skill-mode", "published-image", "external-api"],
        default="external-api",
    )
    parser.add_argument("--api-base")
    parser.add_argument("--skip-pull", action="store_true")
    parser.add_argument("--expect-failure", action="store_true")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--python")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--request-timeout-seconds", type=int, default=10)
    parser.add_argument("--network-timeout-seconds", type=int, default=60)
    parser.add_argument("--pull-timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    try:
        transcript = run_replay(args)
        print(dump_json(transcript))
    except Exception as exc:
        classification = classify_error(str(exc))
        status = "expected_failure" if args.expect_failure else "blocked"
        try:
            print(dump_json(build_failure_transcript(args, classification, str(exc), status=status)))
        except Exception:
            print(f"replay_platform_agent_from_release failed: {sanitize_error(str(exc))}", file=sys.stderr)
            sys.exit(1)
        if args.expect_failure:
            return
        sys.exit(1)


if __name__ == "__main__":
    main()
