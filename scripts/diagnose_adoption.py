#!/usr/bin/env python3
"""Diagnose common Study Anything adoption blockers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_CAPABILITIES = [
    "teach.overview",
    "teach.glossary",
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
]
DEFAULT_TAG = "v0.3.11-alpha"
DEFAULT_IMAGE = f"ghcr.io/jzvcpe-goat/study-anything/api:{DEFAULT_TAG}"


def request_json(url: str, *, timeout: int = 5) -> Any:
    request = Request(url, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def check_env_file(env_file: Path) -> dict[str, Any]:
    if env_file.exists():
        return {
            "status": "ok",
            "name": "env_file",
            "code": "env_present",
            "message": f"Environment file exists at {env_file}.",
        }
    return {
        "status": "warning",
        "name": "env_file",
        "code": "env_missing",
        "message": f"Environment file is missing at {env_file}.",
        "fix": "Run python3 scripts/setup_env.py before Docker or Skill Mode startup.",
        "next_command": "python3 scripts/setup_env.py",
    }


def check_api(api_base: str) -> dict[str, Any]:
    try:
        health = request_json(f"{api_base.rstrip('/')}/v1/health")
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "status": "warning",
            "name": "localhost_api",
            "code": "api_unreachable",
            "message": f"Study Anything API is not reachable at {api_base}: {exc}",
            "fix": (
                "Run ./scripts/launch_skill_mode.sh or ./scripts/launch_self_host.sh, "
                "then retry."
            ),
            "next_commands": [
                "./scripts/launch_skill_mode.sh",
                "./scripts/launch_self_host.sh",
            ],
        }
    return {
        "status": "ok",
        "name": "localhost_api",
        "code": "api_reachable",
        "message": f"Study Anything API responds at {api_base}.",
        "version": health.get("version"),
    }


def check_docker() -> dict[str, Any]:
    if shutil.which("docker") is None:
        return {
            "status": "warning",
            "name": "docker_daemon",
            "code": "docker_missing",
            "message": "docker is not installed or not on PATH.",
            "fix": "Install Docker Desktop or use Skill Mode without Docker.",
            "next_command": "./scripts/launch_skill_mode.sh",
        }
    try:
        completed = run(["docker", "info"], timeout=15)
    except subprocess.TimeoutExpired:
        return {
            "status": "warning",
            "name": "docker_daemon",
            "code": "docker_info_timeout",
            "message": "docker info timed out.",
            "fix": "Start or restart Docker Desktop.",
        }
    if completed.returncode != 0:
        return {
            "status": "warning",
            "name": "docker_daemon",
            "code": "docker_daemon_unreachable",
            "message": "Docker daemon is not reachable.",
            "stderr": completed.stderr[-1000:],
            "fix": "Start Docker Desktop before Docker self-host or published-image smoke.",
        }
    return {
        "status": "ok",
        "name": "docker_daemon",
        "code": "docker_daemon_reachable",
        "message": "Docker daemon is reachable.",
    }


def check_ghcr_manifest(image: str, *, timeout: int) -> dict[str, Any]:
    if shutil.which("docker") is None:
        return {
            "status": "warning",
            "name": "ghcr_manifest",
            "code": "docker_missing",
            "message": "Cannot inspect GHCR image because docker is missing.",
            "fix": "Install Docker Desktop, or rely on GitHub docker-images workflow evidence.",
        }
    try:
        completed = run(["docker", "manifest", "inspect", image], timeout=timeout)
    except subprocess.TimeoutExpired:
        return {
            "status": "warning",
            "name": "ghcr_manifest",
            "code": "ghcr_manifest_timeout",
            "message": f"docker manifest inspect timed out after {timeout}s for {image}.",
            "fix": "Check GitHub Actions docker-images status, then retry on a faster network.",
            "next_command": f"docker manifest inspect {image}",
        }
    if completed.returncode != 0:
        return {
            "status": "warning",
            "name": "ghcr_manifest",
            "code": "ghcr_manifest_unavailable",
            "message": f"Could not inspect {image}.",
            "stderr": completed.stderr[-1000:],
            "fix": "Confirm the release tag exists and GHCR package visibility is public.",
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {
            "status": "warning",
            "name": "ghcr_manifest",
            "code": "ghcr_manifest_invalid_json",
            "message": "docker manifest inspect returned non-JSON output.",
            "fix": "Upgrade Docker CLI or inspect the image from GitHub Actions.",
        }
    platforms = sorted(
        {
            f"{item.get('platform', {}).get('os')}/{item.get('platform', {}).get('architecture')}"
            for item in payload.get("manifests", [])
            if item.get("platform", {}).get("os") != "unknown"
        }
    )
    return {
        "status": "ok" if {"linux/amd64", "linux/arm64"}.issubset(platforms) else "warning",
        "name": "ghcr_manifest",
        "code": "ghcr_manifest_multi_arch",
        "message": f"GHCR manifest inspected for {image}.",
        "platforms": platforms,
        "fix": "Expected linux/amd64 and linux/arm64 manifests for public release images.",
    }


def health_url_for_agent(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return endpoint.rstrip("/") + "/health"
    path = parsed.path.rstrip("/")
    if path.endswith("/invoke"):
        path = path[: -len("/invoke")]
    base_path = path or ""
    return f"{parsed.scheme}://{parsed.netloc}{base_path}/health"


def check_agent_endpoint(endpoint: str) -> dict[str, Any]:
    health_url = health_url_for_agent(endpoint)
    try:
        health = request_json(health_url)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "status": "warning",
            "name": "agent_endpoint",
            "code": "agent_endpoint_unreachable",
            "message": f"Agent health is not reachable at {health_url}: {exc}",
            "fix": "Start scripts/openai_compatible_agent_gateway.py or your private HTTP Agent.",
            "next_command": "python3 scripts/openai_compatible_agent_gateway.py",
        }
    status = health.get("status")
    return {
        "status": "ok" if status in {"ok", "healthy"} else "warning",
        "name": "agent_endpoint",
        "code": "agent_endpoint_health_checked",
        "message": f"Agent endpoint health returned status={status}.",
        "health_url": health_url,
    }


def check_provider_capabilities(
    api_base: str,
    *,
    user_id: str,
    required_capabilities: list[str],
) -> dict[str, Any]:
    try:
        status = request_json(f"{api_base.rstrip('/')}/v1/agents/status?user_id={user_id}")
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "status": "warning",
            "name": "provider_capabilities",
            "code": "provider_status_unreachable",
            "message": f"Cannot inspect provider defaults because API is unavailable: {exc}",
            "fix": "Start the API and register an HTTP Agent provider with --set-default.",
        }
    return provider_capability_report(status, required_capabilities=required_capabilities)


def provider_capability_report(
    status: dict[str, Any],
    *,
    required_capabilities: list[str],
) -> dict[str, Any]:
    defaults = status.get("defaults") or {}
    missing_defaults = [
        capability for capability in required_capabilities if not defaults.get(capability)
    ]
    providers = status.get("providers") or []
    provider_caps = {
        provider.get("provider_id"): set(provider.get("capabilities") or [])
        for provider in providers
        if isinstance(provider, dict)
    }
    defaults_without_capability = [
        capability
        for capability, provider_id in defaults.items()
        if provider_id
        and capability in required_capabilities
        and capability not in provider_caps.get(provider_id, set())
    ]
    if missing_defaults or defaults_without_capability:
        return {
            "status": "warning",
            "name": "provider_capabilities",
            "code": "provider_defaults_missing",
            "message": "Required Agent capability defaults are incomplete.",
            "missing_defaults": missing_defaults,
            "defaults_without_capability": defaults_without_capability,
            "fix": (
                "Run scripts/study_anything_cli.py agent-add-http --endpoint ... --set-default, "
                "or set defaults with POST /v1/agents/defaults."
            ),
        }
    return {
        "status": "ok",
        "name": "provider_capabilities",
        "code": "provider_defaults_ready",
        "message": "Required Agent capability defaults are configured.",
        "capabilities": required_capabilities,
    }


def build_recovery_plan(
    *,
    api_base: str,
    image: str,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    failed_codes = [
        str(check.get("code"))
        for check in checks
        if check.get("status") != "ok" and check.get("code")
    ]
    release_tag = image.rsplit(":", 1)[-1] if ":" in image else DEFAULT_TAG
    commands = {
        "prepare_env": "python3 scripts/setup_env.py",
        "doctor": "./scripts/doctor.sh",
        "skill_mode": "./scripts/launch_skill_mode.sh",
        "docker_source": "./scripts/launch_self_host.sh",
        "docker_published_image": (
            f"USE_PUBLISHED_IMAGES=true STUDY_ANYTHING_IMAGE_TAG={release_tag} "
            "./scripts/launch_self_host.sh"
        ),
        "api_smoke": f"API_BASE={api_base} python3 scripts/verify_full_api_flow.py",
        "platform_tools_smoke": (
            f"API_BASE={api_base} python3 scripts/verify_platform_agent_tools.py"
        ),
        "adoption_telemetry": (
            f"python3 scripts/verify_adoption_telemetry.py --api-base {api_base}"
        ),
        "published_image_smoke": (
            f"python3 scripts/verify_published_image_launch.py --tag {release_tag} "
            "--pull-timeout-seconds 180 --allow-pull-timeout-report"
        ),
        "ghcr_manifest": f"docker manifest inspect {image}",
    }
    if "docker_missing" in failed_codes or "docker_daemon_unreachable" in failed_codes:
        recommended = ["prepare_env", "skill_mode", "api_smoke"]
    elif "env_missing" in failed_codes:
        recommended = ["prepare_env", "doctor"]
    elif "api_unreachable" in failed_codes:
        recommended = ["doctor", "docker_published_image", "api_smoke"]
    elif "provider_defaults_missing" in failed_codes:
        recommended = ["platform_tools_smoke"]
    else:
        recommended = ["doctor", "api_smoke", "platform_tools_smoke", "adoption_telemetry"]
    return {
        "schema_version": "adoption-diagnostic-plan-v1",
        "summary": "Copyable next commands for local-first Study Anything adoption.",
        "failed_codes": failed_codes,
        "recommended_order": recommended,
        "commands": commands,
        "privacy": {
            "do_not_include": [
                "real model API keys",
                "agent endpoint secrets",
                "raw source text",
                "learner answers",
            ]
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--agent-endpoint", default="http://127.0.0.1:8787/invoke")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
    )
    parser.add_argument("--user-id", default="local-user")
    parser.add_argument("--ghcr-timeout-seconds", type=int, default=20)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    checks = [
        check_env_file(Path(args.env_file)),
        check_api(args.api_base),
        check_docker(),
        check_ghcr_manifest(args.image, timeout=args.ghcr_timeout_seconds),
        check_agent_endpoint(args.agent_endpoint),
        check_provider_capabilities(
            args.api_base,
            user_id=args.user_id,
            required_capabilities=DEFAULT_CAPABILITIES,
        ),
    ]
    status = "ok" if all(check["status"] == "ok" for check in checks) else "needs_attention"
    payload = {
        "status": status,
        "schema_version": "adoption-diagnostics-v1",
        "checks": checks,
        "recovery_plan": build_recovery_plan(
            api_base=args.api_base,
            image=args.image,
            checks=checks,
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and status != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
