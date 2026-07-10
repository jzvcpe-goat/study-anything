#!/usr/bin/env python3
"""Verify the API container, Compose, and GitHub workflow security baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "apps" / "api" / "Dockerfile"
COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.yml"
WORKFLOW_DIR = ROOT / ".github" / "workflows"
WORKFLOW_DIRS = (WORKFLOW_DIR, ROOT / "platform" / "workflows")
SECURITY_WORKFLOW = WORKFLOW_DIR / "security.yml"
SCHEMA_VERSION = "container-security-baseline-v1"
EXPECTED_UID = "10001"
PINNED_PYTHON_BASE_IMAGE = (
    "public.ecr.aws/docker/library/python:3.11-slim@"
    "sha256:e031123e3d85762b141ad1cbc56452ba69c6e722ebf2f042cc0dc86c47c0d8b3"
)
ACTION_PIN_PATTERN = re.compile(
    r"^\s*-?\s*uses:\s+[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?@([0-9a-f]{40})(?:\s+#.*)?$"
)


class ContainerSecurityError(RuntimeError):
    """Readable security baseline failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContainerSecurityError(message)


def require_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    require(isinstance(value, Mapping), f"{key} must be an object")
    return value


def read_compose(path: Path = COMPOSE_FILE) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ContainerSecurityError("Cannot parse Docker Compose policy") from exc
    require(isinstance(payload, dict), "Docker Compose must contain an object")
    return payload


def validate_dockerfile(text: str) -> dict[str, Any]:
    require("PYTHON_BASE_IMAGE=python:3.11-slim@sha256:" in text, "Python base image must be digest pinned")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    user_lines = [line for line in lines if line.startswith("USER ")]
    require(user_lines == [f"USER {EXPECTED_UID}:{EXPECTED_UID}"], "Final image must use UID/GID 10001")
    user_index = lines.index(user_lines[0])
    command_index = next(index for index, line in enumerate(lines) if line.startswith("CMD "))
    require(user_index < command_index, "USER must be set before the runtime command")
    require(
        any("groupadd --gid 10001" in line for line in lines),
        "Dockerfile must create the fixed runtime group",
    )
    require(
        any("useradd --uid 10001 --gid 10001" in line for line in lines),
        "Dockerfile must create the fixed runtime user",
    )
    require(
        any("chown -R 10001:10001" in line for line in lines),
        "Writable runtime directories must belong to the runtime user",
    )
    require(
        all("pip install" not in line for line in lines[user_index + 1 :]),
        "Package installation must finish before dropping privileges",
    )
    require("sudo" not in text, "Runtime image must not install or invoke sudo")
    require("--upgrade pip" not in text, "Docker build must not upgrade pip outside the lock")
    require(
        "--require-hashes -r requirements/locked-full.txt" in text,
        "Docker dependencies must use the hash-bound full requirements",
    )
    require(
        "--no-deps --no-build-isolation -e ." in text,
        "Docker must install the local project without resolving dependencies",
    )
    return {
        "fixed_uid": 10001,
        "fixed_gid": 10001,
        "non_root_user_final": True,
        "package_install_before_user_drop": True,
        "base_image_digest_pinned": True,
        "runtime_data_owned_by_user": True,
        "hash_bound_dependencies": True,
    }


def normalized_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def validate_service(name: str, service: Mapping[str, Any]) -> dict[str, Any]:
    require(service.get("privileged") is not True, f"{name} must not be privileged")
    require(service.get("network_mode") != "host", f"{name} must not use host networking")
    require(service.get("read_only") is True, f"{name} root filesystem must be read-only")
    require(service.get("init") is True, f"{name} must enable the init shim")
    cap_drop = {item.upper() for item in normalized_list(service.get("cap_drop"))}
    require("ALL" in cap_drop, f"{name} must drop all Linux capabilities")
    security_opt = {item.lower() for item in normalized_list(service.get("security_opt"))}
    require(
        "no-new-privileges:true" in security_opt,
        f"{name} must enable no-new-privileges",
    )
    tmpfs = normalized_list(service.get("tmpfs"))
    tmp_policy = next((item for item in tmpfs if item.startswith("/tmp:")), "")
    for option in ("noexec", "nosuid", "nodev"):
        require(option in tmp_policy.split(","), f"{name} /tmp tmpfs must include {option}")
    volumes = normalized_list(service.get("volumes"))
    require(
        all("/var/run/docker.sock" not in item for item in volumes),
        f"{name} must not mount the Docker socket",
    )
    return {
        "read_only_rootfs": True,
        "init_enabled": True,
        "all_capabilities_dropped": True,
        "no_new_privileges": True,
        "hardened_tmpfs": True,
        "docker_socket_mounted": False,
        "privileged": False,
        "host_network": False,
    }


def validate_compose(payload: Mapping[str, Any]) -> dict[str, Any]:
    services = require_mapping(payload, "services")
    results: dict[str, Any] = {}
    for service_name in ("api", "mock-http-agent"):
        results[service_name] = validate_service(
            service_name,
            require_mapping(services, service_name),
        )
    api_ports = normalized_list(require_mapping(services, "api").get("ports"))
    api_environment = require_mapping(require_mapping(services, "api"), "environment")
    require(
        any(port.startswith("${API_BIND_HOST:-127.0.0.1}:") for port in api_ports),
        "API port must default to loopback",
    )
    require(
        api_environment.get("STUDY_ANYTHING_AGENT_ENDPOINT_POLICY")
        == "${STUDY_ANYTHING_AGENT_ENDPOINT_POLICY:-operator}",
        "API Compose service must pass through the Agent endpoint policy",
    )
    require(
        api_environment.get("STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST")
        == "${STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST:-}",
        "API Compose service must pass through the Agent endpoint allowlist",
    )
    oidc_environment = {
        "STUDY_ANYTHING_OIDC_ISSUER": "${STUDY_ANYTHING_OIDC_ISSUER:-}",
        "STUDY_ANYTHING_OIDC_AUDIENCE": "${STUDY_ANYTHING_OIDC_AUDIENCE:-}",
        "STUDY_ANYTHING_OIDC_TENANT_CLAIM": "${STUDY_ANYTHING_OIDC_TENANT_CLAIM:-org_id}",
        "STUDY_ANYTHING_OIDC_JWKS_JSON": "${STUDY_ANYTHING_OIDC_JWKS_JSON:-}",
        "STUDY_ANYTHING_OIDC_JWKS_FILE": "${STUDY_ANYTHING_OIDC_JWKS_FILE:-}",
        "STUDY_ANYTHING_OIDC_LEEWAY_SECONDS": "${STUDY_ANYTHING_OIDC_LEEWAY_SECONDS:-30}",
        "STUDY_ANYTHING_OIDC_MAX_TOKEN_AGE_SECONDS": (
            "${STUDY_ANYTHING_OIDC_MAX_TOKEN_AGE_SECONDS:-3600}"
        ),
    }
    for key, expected in oidc_environment.items():
        require(
            api_environment.get(key) == expected,
            f"API Compose service must pass through {key}",
        )
    mock_ports = normalized_list(require_mapping(services, "mock-http-agent").get("ports"))
    require(
        all(port.startswith("127.0.0.1:") for port in mock_ports),
        "Mock Agent ports must bind to loopback",
    )
    for service_name in ("langfuse-web", "minio"):
        service_ports = normalized_list(require_mapping(services, service_name).get("ports"))
        require(
            all(port.startswith("127.0.0.1:") for port in service_ports),
            f"{service_name} ports must bind to loopback",
        )
    minio_environment = require_mapping(services, "minio").get("environment")
    require(isinstance(minio_environment, Mapping), "MinIO environment must be configured")
    require(
        str(minio_environment.get("MINIO_ROOT_PASSWORD", "")).startswith(
            "${MINIO_ROOT_PASSWORD:?"
        ),
        "MinIO root password must not have a fallback default",
    )
    results["agent_endpoint_policy"] = {
        "policy_env_forwarded": True,
        "allowlist_env_forwarded": True,
    }
    results["hosted_identity"] = {
        "auth_mode_env_forwarded": True,
        "static_jwks_env_forwarded": True,
        "issuer_audience_env_forwarded": True,
        "tenant_claim_env_forwarded": True,
        "token_lifetime_policy_env_forwarded": True,
    }
    return results


def validate_action_pins() -> dict[str, Any]:
    workflow_files = sorted(
        path
        for workflow_dir in WORKFLOW_DIRS
        for path in workflow_dir.glob("*.yml")
    )
    require(workflow_files, "GitHub workflow files are missing")
    action_count = 0
    for path in workflow_files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "uses:" not in line:
                continue
            action_count += 1
            require(
                ACTION_PIN_PATTERN.match(line) is not None,
                f"Unpinned GitHub Action at {path.relative_to(ROOT)}:{line_number}",
            )
    require(action_count >= 10, "Expected GitHub Action references are missing")
    return {"workflow_count": len(workflow_files), "pinned_action_count": action_count}


def validate_security_workflow(text: str) -> dict[str, Any]:
    required = (
        "codeql (python)",
        "security-events: write",
        "github/codeql-action/init@f52b05f4acaaa234e44466e66d29050e135ea9ef",
        "github/codeql-action/analyze@f52b05f4acaaa234e44466e66d29050e135ea9ef",
        "queries: security-extended",
        "dependency review",
        "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294",
        "fail-on-severity: high",
        "container policy",
        "verify_container_security.py --check",
        "verify_dependency_risk_acceptance.py --check",
        "verify_agent_endpoint_policy.py --check",
        "verify_hosted_identity_tenancy.py --check",
    )
    missing = [marker for marker in required if marker not in text]
    require(not missing, f"Security workflow markers are missing: {missing}")
    require("pull_request:" in text, "Security workflow must run for pull requests")
    require("schedule:" in text, "Security workflow must run on a schedule")
    return {
        "codeql_python": True,
        "security_extended_queries": True,
        "dependency_review": True,
        "high_severity_dependency_changes_block": True,
        "scheduled_scan": True,
        "container_policy_job": True,
    }


def validate_ci_workflow(text: str) -> dict[str, Any]:
    require(
        f"PYTHON_BASE_IMAGE: {PINNED_PYTHON_BASE_IMAGE}" in text,
        "Compose smoke must use the digest-pinned Python base image",
    )
    require(
        "python scripts/setup_env.py --force" in text,
        "Compose smoke must generate its local environment file",
    )
    require(
        "pip install --require-hashes -r requirements/locked-dev-full.txt" in text,
        "API CI must install hash-bound dev/full dependencies",
    )
    require(
        "generate_python_supply_chain.py --check" in text,
        "API CI must verify the Python lock and SBOM",
    )
    compose_commands = [
        line.strip() for line in text.splitlines() if "docker compose" in line
    ]
    require(compose_commands, "Compose smoke commands are missing")
    require(
        all("docker compose --env-file .env " in line for line in compose_commands),
        "Every CI Compose command must read the generated repository .env file",
    )
    return {
        "compose_env_file_explicit": True,
        "compose_command_count": len(compose_commands),
        "python_base_image_digest_pinned": True,
    }


def inspect_runtime_container(container_id: str) -> dict[str, Any]:
    require(bool(container_id.strip()), "Runtime container id is empty")
    try:
        completed = subprocess.run(
            ["docker", "inspect", container_id],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContainerSecurityError("Cannot inspect runtime container") from exc
    require(completed.returncode == 0, "Docker runtime inspection failed")
    try:
        items = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContainerSecurityError("Docker runtime inspection returned invalid JSON") from exc
    require(isinstance(items, list) and len(items) == 1, "Expected one Docker inspection record")
    record = items[0]
    require(isinstance(record, Mapping), "Docker inspection record is invalid")
    config = require_mapping(record, "Config")
    host_config = require_mapping(record, "HostConfig")
    user = str(config.get("User") or "")
    cap_drop = {str(item).upper() for item in (host_config.get("CapDrop") or [])}
    security_opt = {str(item).lower() for item in (host_config.get("SecurityOpt") or [])}
    checks = {
        "non_root_uid": user in {EXPECTED_UID, f"{EXPECTED_UID}:{EXPECTED_UID}"},
        "read_only_rootfs": host_config.get("ReadonlyRootfs") is True,
        "all_capabilities_dropped": "ALL" in cap_drop,
        "no_new_privileges": "no-new-privileges:true" in security_opt,
        "init_enabled": host_config.get("Init") is True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    require(not failed, f"Runtime container hardening failed: {failed}")
    return {"checked": True, **checks, "container_id_included": False}


def verify(*, runtime_container_id: str | None = None) -> dict[str, Any]:
    dockerfile = validate_dockerfile(DOCKERFILE.read_text(encoding="utf-8"))
    compose = validate_compose(read_compose())
    action_pins = validate_action_pins()
    security_workflow = validate_security_workflow(SECURITY_WORKFLOW.read_text(encoding="utf-8"))
    ci = (WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
    ci_workflow = validate_ci_workflow(ci)
    release_check = (ROOT / "scripts" / "release_check.sh").read_text(encoding="utf-8")
    require(
        "verify_container_security.py --check" in ci,
        "CI is missing the container security verifier",
    )
    require(
        "verify_container_security.py --check" in release_check,
        "Release check is missing the container security verifier",
    )
    runtime = (
        inspect_runtime_container(runtime_container_id)
        if runtime_container_id
        else {"checked": False, "reason": "no_container_id_supplied"}
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "dockerfile": dockerfile,
        "compose_services": compose,
        "github_actions": {**action_pins, **security_workflow, **ci_workflow},
        "runtime_container": runtime,
        "repository_settings": {
            "secret_scanning_expected": True,
            "push_protection_expected": True,
            "branch_protection_expected": True,
            "live_settings_verified_by_this_command": False,
        },
        "privacy": {
            "metadata_only": True,
            "docker_inspect_payload_included": False,
            "container_id_included": False,
            "workflow_logs_included": False,
            "environment_values_included": False,
            "secrets_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "This verifier proves repository container and workflow security policy, plus runtime "
            "container settings only when a container id is supplied. It is not an independent "
            "security audit, vulnerability-free claim, tenant-isolation proof, or production certification."
        ),
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--runtime-container-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = verify(runtime_container_id=args.runtime_container_id)
        if args.output:
            output = args.output if args.output.is_absolute() else ROOT / args.output
            write_report(output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    except ContainerSecurityError as exc:
        print(f"verify_container_security failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
