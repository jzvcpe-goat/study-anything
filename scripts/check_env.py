#!/usr/bin/env python3
"""Validate local environment settings before launch or release."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from typing import Any
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.core.hosted_identity import (  # noqa: E402
    HostedIdentityConfigurationError,
    load_hosted_identity_config,
)

DEFAULT_ENV = ROOT / ".env"
HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")
API_AUTH_MODES = {"local_only", "token", "oidc_jwt"}
AGENT_ENDPOINT_POLICY_MODES = {"operator", "allowlist"}
LOOPBACK_BIND_HOSTS = {"127.0.0.1", "::1", "localhost"}
MIN_API_TOKEN_LENGTH = 32

WEAK_VALUES = {
    "",
    "postgres",
    "study_dev_password",
    "miniosecret",
    "myredissecret",
    "clickhouse",
    "change-me-nextauth-secret",
    "change-me-langfuse-salt",
    "change-me-study-postgres",
    "change-me-langfuse-postgres",
    "change-me-clickhouse",
    "change-me-minio",
    "change-me-redis",
    "replace-with-generated-local-key",
    "replace-with-32-byte-base64-key-before-real-use",
    "0000000000000000000000000000000000000000000000000000000000000000",
}

SECRET_KEYS = (
    "POSTGRES_PASSWORD",
    "LANGFUSE_POSTGRES_PASSWORD",
    "NEXTAUTH_SECRET",
    "LANGFUSE_SALT",
    "LANGFUSE_ENCRYPTION_KEY",
    "CLICKHOUSE_PASSWORD",
    "MINIO_ROOT_PASSWORD",
    "REDIS_AUTH",
)
PORT_DEFAULTS = {
    "API_PORT": "8000",
    "APP_POSTGRES_PORT": "5433",
    "MOCK_AGENT_PORT": "8787",
    "LANGFUSE_PORT": "3000",
    "LANGFUSE_POSTGRES_PORT": "5432",
    "REDIS_PORT": "6379",
    "FALKORDB_HOST_PORT": "6378",
    "FALKORDB_PORT": "6379",
    "CLICKHOUSE_HTTP_PORT": "8123",
    "CLICKHOUSE_NATIVE_PORT": "9000",
    "MINIO_PORT": "9090",
    "MINIO_CONSOLE_PORT": "9091",
}
HOST_PORT_DEFAULTS = {
    key: value for key, value in PORT_DEFAULTS.items() if key != "FALKORDB_PORT"
}
PROFILE_HOST_PORT_KEYS = {
    "core": (
        "API_PORT",
        "APP_POSTGRES_PORT",
    ),
    "smoke": (
        "API_PORT",
        "APP_POSTGRES_PORT",
        "MOCK_AGENT_PORT",
        "FALKORDB_HOST_PORT",
    ),
    "full": tuple(HOST_PORT_DEFAULTS),
}


class CheckEnvError(RuntimeError):
    """Readable environment validation failure."""


def env_issue(code: str, key: str, message: str, next_steps: list[str]) -> dict[str, object]:
    return {
        "code": code,
        "key": key,
        "message": message,
        "next_steps": next_steps,
    }


def weak_secret_issue(key: str, env_path: Path) -> dict[str, object]:
    return env_issue(
        "weak_or_placeholder_secret",
        key,
        f"{key} is still a default or placeholder value.",
        [
            f"Regenerate local secrets: python3 scripts/setup_env.py --force --output {env_path}",
            f"Or edit {env_path} and replace {key} with a strong unique value.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path} --strict",
        ],
    )


def encryption_key_issue(env_path: Path) -> dict[str, object]:
    return env_issue(
        "invalid_langfuse_encryption_key",
        "LANGFUSE_ENCRYPTION_KEY",
        "LANGFUSE_ENCRYPTION_KEY must be a 64-character hex string.",
        [
            f"Regenerate local secrets: python3 scripts/setup_env.py --force --output {env_path}",
            "Or set LANGFUSE_ENCRYPTION_KEY to 32 random bytes encoded as 64 lowercase hex characters.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path} --strict",
        ],
    )


def database_url_issue(env_path: Path) -> dict[str, object]:
    return env_issue(
        "missing_database_url",
        "DATABASE_URL",
        "SESSION_STORE=postgres requires DATABASE_URL.",
        [
            "Set DATABASE_URL to the Postgres URL for the Study Anything app database.",
            f"For local self-host defaults, regenerate .env: python3 scripts/setup_env.py --force --output {env_path}",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def unsupported_api_auth_mode_issue(mode: str, env_path: Path) -> dict[str, object]:
    return env_issue(
        "unsupported_api_auth_mode",
        "STUDY_ANYTHING_API_AUTH_MODE",
        f"STUDY_ANYTHING_API_AUTH_MODE must be local_only, token, or oidc_jwt; got {mode!r}.",
        [
            f"Edit {env_path} and set STUDY_ANYTHING_API_AUTH_MODE=local_only for loopback-only use.",
            "For network or production use, set STUDY_ANYTHING_API_AUTH_MODE=token or oidc_jwt.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def production_api_auth_issue(env_path: Path) -> dict[str, object]:
    return env_issue(
        "production_api_auth_required",
        "STUDY_ANYTHING_API_AUTH_MODE",
        "APP_ENV=production requires STUDY_ANYTHING_API_AUTH_MODE=token or oidc_jwt.",
        [
            f"Edit {env_path} and set STUDY_ANYTHING_API_AUTH_MODE=token or oidc_jwt.",
            f"Generate a strong token with: python3 scripts/setup_env.py --force --output {env_path}",
            f"Recheck with: python3 scripts/check_env.py --env {env_path} --strict",
        ],
    )


def network_bind_without_auth_issue(bind_host: str, env_path: Path) -> dict[str, object]:
    return env_issue(
        "network_bind_requires_token_auth",
        "API_BIND_HOST",
        f"API_BIND_HOST={bind_host} is not loopback and requires token or oidc_jwt authentication.",
        [
            f"For local-only use, edit {env_path} and set API_BIND_HOST=127.0.0.1.",
            "For network use, set STUDY_ANYTHING_API_AUTH_MODE=token or oidc_jwt.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def invalid_oidc_configuration_issue(
    message: str,
    env_path: Path,
) -> dict[str, object]:
    return env_issue(
        "invalid_oidc_configuration",
        "STUDY_ANYTHING_OIDC_ISSUER",
        f"OIDC JWT authentication is not ready: {message}",
        [
            "Install the hosted dependency extra: python -m pip install -e '.[hosted]'.",
            f"Configure the OIDC issuer, audience, tenant claim, and exactly one static JWKS source in {env_path}.",
            "Keep automatic JWKS network fetching outside Study Anything v0.1; rotate the static JWKS through deployment configuration.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path} --strict",
        ],
    )


def missing_api_token_issue(env_path: Path) -> dict[str, object]:
    return env_issue(
        "missing_or_weak_api_token",
        "STUDY_ANYTHING_API_TOKEN",
        f"Token auth requires STUDY_ANYTHING_API_TOKEN with at least {MIN_API_TOKEN_LENGTH} characters.",
        [
            f"Generate a strong token with: python3 scripts/setup_env.py --force --output {env_path}",
            "Or set STUDY_ANYTHING_API_TOKEN to a strong random value in the private environment.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def wildcard_cors_issue(env_path: Path) -> dict[str, object]:
    return env_issue(
        "wildcard_cors_forbidden",
        "STUDY_ANYTHING_CORS_ORIGINS",
        "Wildcard CORS is forbidden for the local API.",
        [
            f"Leave STUDY_ANYTHING_CORS_ORIGINS empty in {env_path} for CLI and platform-Agent use.",
            "Or list exact trusted origins separated by commas.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def unsupported_agent_endpoint_policy_issue(mode: str, env_path: Path) -> dict[str, object]:
    return env_issue(
        "unsupported_agent_endpoint_policy",
        "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY",
        f"STUDY_ANYTHING_AGENT_ENDPOINT_POLICY must be operator or allowlist; got {mode!r}.",
        [
            f"For local single-operator use, edit {env_path} and set "
            "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=operator.",
            "For production use, set the policy to allowlist and provide exact trusted origins.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def production_agent_allowlist_required_issue(env_path: Path) -> dict[str, object]:
    return env_issue(
        "production_agent_allowlist_required",
        "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY",
        "APP_ENV=production requires STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=allowlist.",
        [
            f"Edit {env_path} and set STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=allowlist.",
            "Set STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST to exact trusted HTTPS origins.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path} --strict",
        ],
    )


def empty_agent_endpoint_allowlist_issue(env_path: Path) -> dict[str, object]:
    return env_issue(
        "empty_agent_endpoint_allowlist",
        "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST",
        "Agent endpoint allowlist mode requires at least one exact trusted origin.",
        [
            f"Edit {env_path} and set STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST=https://agent.example.",
            "Use comma-separated exact origins without paths, queries, fragments, or credentials.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path} --strict",
        ],
    )


def invalid_agent_endpoint_allowlist_origin_issue(
    index: int,
    reason: str,
    env_path: Path,
) -> dict[str, object]:
    return env_issue(
        "invalid_agent_endpoint_allowlist_origin",
        "STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST",
        f"Agent endpoint allowlist entry {index} is invalid: {reason}",
        [
            f"Edit entry {index} in {env_path}; use an exact HTTPS origin such as https://agent.example.",
            "Loopback development origins may use HTTP; non-loopback origins must use HTTPS.",
            f"Recheck with: python3 scripts/check_env.py --env {env_path} --strict",
        ],
    )


def unreadable_env_issue(error: str, env_path: Path) -> dict[str, object]:
    return env_issue(
        "env_file_unreadable",
        "env_file",
        error,
        [
            "Run from the repository root or pass --env path/to/.env.",
            f"Create a local env file: python3 scripts/setup_env.py --output {env_path}",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def invalid_port_issue(key: str, value: str, env_path: Path) -> dict[str, object]:
    default = PORT_DEFAULTS[key]
    launch_command = (
        f"{key}={default} ./scripts/launch_skill_mode.sh"
        if key == "API_PORT"
        else f"{key}={default} ./scripts/launch_self_host.sh"
    )
    return env_issue(
        "invalid_port_value",
        key,
        f"{key} must be a TCP port from 1 to 65535; got {value!r}.",
        [
            f"Edit {env_path} and set {key}={default}, or another free port from 1 to 65535.",
            f"One-shot retry with a safe default: {launch_command}",
            "Check current port owners and config: ./scripts/doctor.sh",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def unsupported_stack_profile_issue(profile: str, env_path: Path) -> dict[str, object]:
    return env_issue(
        "unsupported_stack_profile",
        "STACK_PROFILE",
        f"STACK_PROFILE must be one of core, smoke, or full; got {profile!r}.",
        [
            f"Edit {env_path} and set STACK_PROFILE=core, smoke, or full.",
            "One-shot minimal retry: STACK_PROFILE=core ./scripts/launch_self_host.sh",
            "Check Docker/self-host config: ./scripts/doctor.sh",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def duplicate_host_port_issue(
    *,
    keys: list[str],
    port: str,
    profile: str,
    env_path: Path,
) -> dict[str, object]:
    joined_keys = ", ".join(keys)
    return env_issue(
        "duplicate_host_port_value",
        "host_ports",
        f"STACK_PROFILE={profile} maps multiple host ports to {port}: {joined_keys}.",
        [
            f"Edit {env_path} so each active host port is unique: {joined_keys}.",
            "For the smallest first-run path: STACK_PROFILE=core ./scripts/launch_self_host.sh",
            "Check current port owners and config: ./scripts/doctor.sh",
            f"Recheck with: python3 scripts/check_env.py --env {env_path}",
        ],
    )


def is_valid_port(value: str) -> bool:
    if not value or not value.isdigit():
        return False
    port = int(value)
    return 1 <= port <= 65535


def active_host_port_keys(values: dict[str, str]) -> tuple[str, tuple[str, ...]]:
    profile = values.get("STACK_PROFILE", "core").strip() or "core"
    return profile, PROFILE_HOST_PORT_KEYS.get(profile, ())


def _is_loopback_agent_host(host: str) -> bool:
    normalized = host.lower().rstrip(".")
    if normalized in LOOPBACK_BIND_HOSTS:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_agent_endpoint_allowlist(value: str, env_path: Path) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    entries = [item.strip() for item in value.split(",") if item.strip()]
    for index, entry in enumerate(entries, 1):
        reason = ""
        try:
            parts = urllib.parse.urlsplit(entry)
            if parts.scheme not in {"http", "https"} or not parts.hostname:
                reason = "entry must be an HTTP(S) origin."
            elif parts.username or parts.password:
                reason = "credentials are forbidden."
            elif parts.path not in {"", "/"} or parts.query or parts.fragment:
                reason = "paths, queries, and fragments are forbidden."
            else:
                parts.port
                if parts.scheme == "http" and not _is_loopback_agent_host(parts.hostname):
                    reason = "non-loopback origins must use HTTPS."
        except ValueError:
            reason = "port is invalid."
        if reason:
            issues.append(invalid_agent_endpoint_allowlist_origin_issue(index, reason, env_path))
    return issues


def _redact_env_path(text: str, env_path: Path) -> str:
    env_text = str(env_path)
    if not env_path.is_absolute() or not env_text:
        return text
    return text.replace(env_text, "<env-file>")


def _redact_issue(issue: dict[str, object], env_path: Path) -> dict[str, object]:
    redacted = dict(issue)
    redacted["message"] = _redact_env_path(str(issue.get("message", "")), env_path)
    redacted["next_steps"] = [
        _redact_env_path(str(step), env_path)
        for step in issue.get("next_steps", [])
        if isinstance(step, str)
    ]
    return redacted


def json_report(
    *,
    env_path: Path,
    app_env: str,
    strict: bool,
    problems: list[dict[str, object]],
    warnings: list[dict[str, object]],
) -> dict[str, Any]:
    json_env_file = str(env_path) if not env_path.is_absolute() else "<env-file>"
    redacted_problems = [_redact_issue(problem, env_path) for problem in problems]
    redacted_warnings = [_redact_issue(warning, env_path) for warning in warnings]
    return {
        "schema_version": "env-check-result-v1",
        "status": "fail" if problems else "pass",
        "env_file": json_env_file,
        "app_env": app_env,
        "strict": strict,
        "problem_count": len(problems),
        "warning_count": len(warnings),
        "problems": redacted_problems,
        "warnings": redacted_warnings,
        "privacy": {
            "local_absolute_paths_included": False,
            "secret_values_included": False,
            "raw_env_values_included": False,
        },
    }


def print_json_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def print_text_report(
    *,
    env_path: Path,
    app_env: str,
    problems: list[dict[str, object]],
    warnings: list[dict[str, object]],
) -> None:
    redacted_problems = [_redact_issue(problem, env_path) for problem in problems]
    for warning in warnings:
        redacted_warning = _redact_issue(warning, env_path)
        print(f"warn  {redacted_warning['message']}")
        for step in redacted_warning["next_steps"]:
            print(f"      Recovery: {step}")
    if problems:
        for problem in redacted_problems:
            print(f"fail  {problem['message']}", file=sys.stderr)
            for step in problem["next_steps"]:
                print(f"      Recovery: {step}", file=sys.stderr)
        return
    print(f"ok    {_redact_env_path(str(env_path), env_path)} is valid for APP_ENV={app_env}.")


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise CheckEnvError(f"Missing {path}. Run `python3 scripts/setup_env.py` first.") from exc
    except UnicodeDecodeError as exc:
        raise CheckEnvError(f"{path} is not UTF-8 text. Save it as UTF-8 and retry: {exc}") from exc
    except OSError as exc:
        raise CheckEnvError(f"Cannot read {path}: {exc}") from exc
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = value.strip()
        if value.startswith('"'):
            end = value.find('"', 1)
            value = value[1:end] if end != -1 else value[1:]
        elif value.startswith("'"):
            end = value.find("'", 1)
            value = value[1:end] if end != -1 else value[1:]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        values[key] = value
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Study Anything .env safety.")
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on weak defaults even outside APP_ENV=production.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable redacted report for platform agents and support bundles.",
    )
    args = parser.parse_args()

    try:
        values = parse_env(args.env)
    except CheckEnvError as exc:
        unreadable_problem = unreadable_env_issue(str(exc), args.env)
        if args.json:
            print_json_report(
                {
                    "schema_version": "env-check-result-v1",
                    "status": "fail",
                    "env_file": str(args.env) if not args.env.is_absolute() else "<env-file>",
                    "app_env": "unknown",
                    "strict": args.strict,
                    "problem_count": 1,
                    "warning_count": 0,
                    "problems": [_redact_issue(unreadable_problem, args.env)],
                    "warnings": [],
                    "privacy": {
                        "local_absolute_paths_included": False,
                        "secret_values_included": False,
                        "raw_env_values_included": False,
                    },
                }
            )
        else:
            print_text_report(
                env_path=args.env,
                app_env="unknown",
                problems=[unreadable_problem],
                warnings=[],
            )
        raise SystemExit(1) from exc
    app_env = values.get("APP_ENV", "development").lower()
    strict = args.strict or app_env == "production"
    problems: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []

    for key in SECRET_KEYS:
        value = values.get(key, "")
        if value in WEAK_VALUES or value.startswith("change-me"):
            target = problems if strict else warnings
            target.append(weak_secret_issue(key, args.env))

    encryption_key = values.get("LANGFUSE_ENCRYPTION_KEY", "")
    if encryption_key and not HEX_64.match(encryption_key):
        problems.append(encryption_key_issue(args.env))

    if values.get("SESSION_STORE") == "postgres" and not values.get("DATABASE_URL"):
        problems.append(database_url_issue(args.env))

    api_auth_mode = values.get("STUDY_ANYTHING_API_AUTH_MODE", "local_only").strip().lower()
    api_bind_host = values.get("API_BIND_HOST", "127.0.0.1").strip().lower() or "127.0.0.1"
    api_token = values.get("STUDY_ANYTHING_API_TOKEN", "").strip()
    cors_origins = {
        origin.strip().rstrip("/")
        for origin in values.get("STUDY_ANYTHING_CORS_ORIGINS", "").split(",")
        if origin.strip()
    }
    if api_auth_mode not in API_AUTH_MODES:
        problems.append(unsupported_api_auth_mode_issue(api_auth_mode, args.env))
    elif app_env == "production" and api_auth_mode not in {"token", "oidc_jwt"}:
        problems.append(production_api_auth_issue(args.env))
    elif api_auth_mode == "local_only" and api_bind_host not in LOOPBACK_BIND_HOSTS:
        problems.append(network_bind_without_auth_issue(api_bind_host, args.env))
    elif api_auth_mode == "token" and len(api_token) < MIN_API_TOKEN_LENGTH:
        problems.append(missing_api_token_issue(args.env))
    elif api_auth_mode == "oidc_jwt":
        try:
            load_hosted_identity_config(values)
        except HostedIdentityConfigurationError as exc:
            problems.append(invalid_oidc_configuration_issue(str(exc), args.env))
    if "*" in cors_origins:
        problems.append(wildcard_cors_issue(args.env))

    default_agent_policy = "allowlist" if app_env == "production" else "operator"
    agent_endpoint_policy = values.get(
        "STUDY_ANYTHING_AGENT_ENDPOINT_POLICY",
        default_agent_policy,
    ).strip().lower()
    agent_endpoint_allowlist = values.get("STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST", "").strip()
    agent_endpoint_allowlist_entries = [
        item.strip() for item in agent_endpoint_allowlist.split(",") if item.strip()
    ]
    if agent_endpoint_policy not in AGENT_ENDPOINT_POLICY_MODES:
        problems.append(unsupported_agent_endpoint_policy_issue(agent_endpoint_policy, args.env))
    elif app_env == "production" and agent_endpoint_policy != "allowlist":
        problems.append(production_agent_allowlist_required_issue(args.env))
    elif agent_endpoint_policy == "allowlist" and not agent_endpoint_allowlist_entries:
        problems.append(empty_agent_endpoint_allowlist_issue(args.env))
    if agent_endpoint_allowlist_entries:
        problems.extend(validate_agent_endpoint_allowlist(agent_endpoint_allowlist, args.env))

    for key in PORT_DEFAULTS:
        value = values.get(key)
        if value is not None and not is_valid_port(value):
            problems.append(invalid_port_issue(key, value, args.env))

    stack_profile, host_port_keys = active_host_port_keys(values)
    if stack_profile not in PROFILE_HOST_PORT_KEYS:
        problems.append(unsupported_stack_profile_issue(stack_profile, args.env))
    else:
        host_ports_by_value: dict[str, list[str]] = {}
        for key in host_port_keys:
            value = values.get(key, HOST_PORT_DEFAULTS[key])
            if is_valid_port(value):
                host_ports_by_value.setdefault(value, []).append(key)
        for port, keys in host_ports_by_value.items():
            if len(keys) > 1:
                problems.append(
                    duplicate_host_port_issue(
                        keys=keys,
                        port=port,
                        profile=stack_profile,
                        env_path=args.env,
                    )
                )

    report = json_report(
        env_path=args.env,
        app_env=app_env,
        strict=strict,
        problems=problems,
        warnings=warnings,
    )
    if args.json:
        print_json_report(report)
    else:
        print_text_report(env_path=args.env, app_env=app_env, problems=problems, warnings=warnings)
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
