#!/usr/bin/env python3
"""Diagnose common Study Anything adoption blockers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import read_env_file_value as read_shared_env_file_value
from localhost_diagnostics import resolve_api_base


DEFAULT_CAPABILITIES = [
    "teach.overview",
    "teach.glossary",
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
]
DEFAULT_TAG = "v0.3.29-alpha"
DEFAULT_IMAGE = f"ghcr.io/jzvcpe-goat/study-anything/api:{DEFAULT_TAG}"
SUPPORTED_STACK_PROFILES = {"core", "smoke", "full"}
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE_BLOCKED_REPORT_DIR_TEXT = "data/release-blocked-reports"
DEFAULT_RELEASE_BLOCKED_REPORT_DIR = ROOT / DEFAULT_RELEASE_BLOCKED_REPORT_DIR_TEXT
CONTRACT_ONLY_RECOVERY_COMMANDS = [
    "python3 scripts/verify_openai_compatible_gateway.py --contract-only",
    "python3 scripts/verify_agent_gateway_hardening.py --contract-only",
    "python3 scripts/verify_external_agent_adapter_hardening.py --contract-only",
]
SECRET_QUERY_KEYS = {
    "api_key",
    "apikey",
    "access_key",
    "access_token",
    "auth",
    "authorization",
    "bearer",
    "client_secret",
    "credential",
    "key",
    "password",
    "secret",
    "token",
}


def docker_failure_kind(stderr: str) -> str:
    lowered = stderr.lower()
    if "permission denied" in lowered or "docker.sock" in lowered:
        return "docker_socket_permission_denied"
    return "docker_daemon_unreachable"


def is_local_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def error_text(exc: BaseException) -> str:
    reason = getattr(exc, "reason", "")
    return f"{exc} {reason}".strip()


def is_local_socket_blocked(exc: BaseException) -> bool:
    text = error_text(exc).lower()
    return (
        "operation not permitted" in text
        or "errno 1" in text
        or "permission denied" in text
        or "errno 13" in text
        or "permissionerror" in text
    )


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


def sanitize_diagnostic(text: str) -> str:
    sanitized = text or ""
    sanitized = re.sub(
        r"https?://[^\s\"'<>]+",
        lambda match: sanitize_url_for_diagnostic(match.group(0)),
        sanitized,
    )
    sanitized = re.sub(r"/Users/[^\s\"']+", "<local-path>", sanitized)
    sanitized = re.sub(r"/private/tmp/[^\s\"']+", "<temp-path>", sanitized)
    sanitized = re.sub(r"/tmp/[^\s\"']+", "<temp-path>", sanitized)
    sanitized = re.sub(r"/private/var/folders/[^\s\"']+", "<temp-path>", sanitized)
    sanitized = re.sub(r"/var/folders/[^\s\"']+", "<temp-path>", sanitized)
    sanitized = re.sub(
        r"(?i)\b(authorization\s*[:=]\s*(?:bearer\s+)?)[A-Za-z0-9._~+/=-]{8,}",
        r"\1<redacted>",
        sanitized,
    )
    sanitized = re.sub(
        r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}",
        r"\1=<redacted>",
        sanitized,
    )
    sanitized = re.sub(
        r'(?i)"(api_key|access_token|token|secret|password|credential)"\s*:\s*"[^"]*"',
        lambda match: f'"{match.group(1)}":"<redacted>"',
        sanitized,
    )
    sanitized = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", sanitized)
    return sanitized[:1000]


def sanitize_url_for_diagnostic(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    hostname = parsed.hostname or ""
    netloc = hostname
    if parsed.username or parsed.password:
        netloc = f"<redacted>@{hostname}"
    try:
        port = parsed.port
    except ValueError:
        host_port = parsed.netloc.rsplit("@", 1)[-1]
        netloc = f"<redacted>@{host_port}" if parsed.username or parsed.password else host_port
    else:
        if port is not None:
            netloc = f"{netloc}:{port}"
    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in SECRET_QUERY_KEYS or value.startswith("sk-"):
            query_pairs.append((key, "<redacted>"))
        else:
            query_pairs.append((key, value))
    query = urlencode(query_pairs).replace("%3Credacted%3E", "<redacted>")
    return urlunparse((parsed.scheme, netloc, parsed.path, "", query, ""))


def sanitize_diagnostic_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [sanitize_diagnostic(str(value)) for value in values if isinstance(value, str)]


def is_study_anything_health_payload(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and isinstance(payload.get("version"), str)
        and bool(payload.get("version"))
    )


def sanitized_health_excerpt(payload: Any) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        text = str(payload)
    return sanitize_diagnostic(text)[:500]


def diagnostic_path(path: Path) -> str:
    return "<env-file>" if path.is_absolute() else str(path)


def diagnostic_repo_path(path: Path) -> str:
    try:
        resolved = path.resolve()
        return str(resolved.relative_to(ROOT.resolve()))
    except (OSError, ValueError):
        if not path.is_absolute():
            return str(path)
        return sanitize_diagnostic(str(path))


def is_safe_release_report_root(report_root: Path) -> bool:
    try:
        resolved = report_root.resolve(strict=False)
        data_root = (ROOT / "data").resolve(strict=False)
        resolved.relative_to(data_root)
    except (OSError, ValueError):
        return False
    return resolved != data_root


def clear_release_blocked_reports(report_root: Path) -> dict[str, Any]:
    report_root_label = diagnostic_repo_path(report_root)
    if not is_safe_release_report_root(report_root):
        return {
            "status": "blocked",
            "schema_version": "release-blocked-report-cleanup-v1",
            "code": "unsafe_release_report_dir",
            "message": (
                "Refusing to clear release blocked reports outside the repository data/ "
                "directory."
            ),
            "report_root": report_root_label,
            "fix": (
                "Use the default data/release-blocked-reports directory, or remove custom "
                "external report directories manually after inspecting them."
            ),
            "privacy": {
                "absolute_paths_returned": False,
                "report_contents_returned": False,
            },
        }
    if not report_root.exists():
        return {
            "status": "ok",
            "schema_version": "release-blocked-report-cleanup-v1",
            "code": "release_blocked_reports_absent",
            "message": "No local release_check localhost-blocked reports were found.",
            "report_root": report_root_label,
            "cleared": False,
            "removed_directory_count": 0,
            "removed_file_count": 0,
            "privacy": {
                "absolute_paths_returned": False,
                "report_contents_returned": False,
            },
        }
    if report_root.is_symlink() or not report_root.is_dir():
        return {
            "status": "blocked",
            "schema_version": "release-blocked-report-cleanup-v1",
            "code": "release_report_dir_not_clearable",
            "message": "Release blocked report path is not a normal directory.",
            "report_root": report_root_label,
            "fix": "Inspect and remove the path manually if it is safe.",
            "privacy": {
                "absolute_paths_returned": False,
                "report_contents_returned": False,
            },
        }
    paths = list(report_root.rglob("*"))
    removed_directory_count = sum(1 for path in paths if path.is_dir()) + 1
    removed_file_count = sum(1 for path in paths if path.is_file())
    shutil.rmtree(report_root)
    return {
        "status": "ok",
        "schema_version": "release-blocked-report-cleanup-v1",
        "code": "release_blocked_reports_cleared",
        "message": (
            "Cleared local release_check localhost-blocked reports. This only removes "
            "stale local diagnostics; it does not replace a successful release_check.sh run."
        ),
        "report_root": report_root_label,
        "cleared": True,
        "removed_directory_count": removed_directory_count,
        "removed_file_count": removed_file_count,
        "next_command": "./scripts/release_check.sh",
        "privacy": {
            "absolute_paths_returned": False,
            "report_contents_returned": False,
        },
    }


def _read_release_block_report(report_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "file": diagnostic_repo_path(report_path),
            "status": "unreadable",
            "classification": "unreadable_blocked_report",
            "diagnostic": sanitize_diagnostic(str(exc)),
        }
    if not isinstance(payload, dict):
        return {
            "file": diagnostic_repo_path(report_path),
            "status": "unreadable",
            "classification": "invalid_blocked_report",
            "diagnostic": "Blocked report did not contain a JSON object.",
        }
    status = sanitize_diagnostic(str(payload.get("status") or "unknown"))
    classification = sanitize_diagnostic(str(payload.get("classification") or "unknown"))
    result = {
        "file": diagnostic_repo_path(report_path),
        "status": status,
        "classification": classification,
        "schema_version": sanitize_diagnostic(str(payload.get("schema_version") or "")),
    }
    if report_path.name.endswith(".contract-only.json"):
        contract = str(payload.get("contract") or report_path.name.removesuffix(".contract-only.json"))
        result.update(
            {
                "contract_only": True,
                "contract": sanitize_diagnostic(contract),
                "classification": (
                    classification if classification != "unknown" else f"contract_only_{status}"
                ),
                "runtime_gate_replaced": bool(payload.get("runtime_gate_replaced", False)),
            }
        )
        return result
    return {
        **result,
        "contract_only": False,
    }


def check_release_blocked_reports(report_root: Path) -> dict[str, Any]:
    if not report_root.exists():
        return {
            "status": "ok",
            "name": "release_blocked_reports",
            "code": "release_blocked_reports_absent",
            "message": "No local release_check localhost-blocked reports were found.",
        }
    if report_root.is_symlink() or not report_root.is_dir():
        return {
            "status": "warning",
            "name": "release_blocked_reports",
            "code": "release_report_path_not_directory",
            "message": (
                "The release blocked report path exists, but it is not a normal directory. "
                "Point --release-report-dir at data/release-blocked-reports or one numbered "
                "report directory inside it."
            ),
            "report_root": diagnostic_repo_path(report_root),
            "fix": (
                "Use python3 scripts/diagnose_adoption.py --release-report-dir "
                "data/release-blocked-reports, or inspect the path manually if you "
                "intended to pass a custom location."
            ),
            "next_commands": [
                "python3 scripts/diagnose_adoption.py --release-report-dir data/release-blocked-reports",
                "python3 scripts/diagnose_adoption.py",
            ],
        }
    direct_report_files = sorted(report_root.glob("*.json")) if report_root.is_dir() else []
    try:
        directories = (
            [report_root]
            if direct_report_files
            else [path for path in report_root.iterdir() if path.is_dir()]
        )
    except OSError as exc:
        return {
            "status": "warning",
            "name": "release_blocked_reports",
            "code": "release_report_dir_unreadable",
            "message": "Could not inspect local release_check blocked reports.",
            "report_root": diagnostic_repo_path(report_root),
            "diagnostic": sanitize_diagnostic(str(exc)),
            "fix": "Check directory permissions, or rerun ./scripts/release_check.sh.",
            "next_commands": [
                "./scripts/release_check.sh",
                "python3 scripts/diagnose_adoption.py",
            ],
        }
    if not directories:
        return {
            "status": "ok",
            "name": "release_blocked_reports",
            "code": "release_blocked_reports_absent",
            "message": "No local release_check localhost-blocked reports were found.",
            "report_root": diagnostic_repo_path(report_root),
        }
    directories.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    latest = directories[0]
    report_files = sorted(latest.glob("*.json"))
    reports = [_read_release_block_report(path) for path in report_files]
    classifications = sorted(
        {
            str(report.get("classification"))
            for report in reports
            if report.get("classification")
        }
    )
    contract_reports = [report for report in reports if report.get("contract_only")]
    report_root_label = diagnostic_repo_path(report_root)
    cleanup_command = "python3 scripts/diagnose_adoption.py --clear-release-blocked-reports"
    if report_root_label != DEFAULT_RELEASE_BLOCKED_REPORT_DIR_TEXT:
        cleanup_command = (
            "python3 scripts/diagnose_adoption.py "
            f"--release-report-dir {report_root_label} --clear-release-blocked-reports"
    )
    return {
        "status": "warning",
        "name": "release_blocked_reports",
        "code": "release_check_localhost_blocked_reports_present",
        "message": (
            "A previous release_check.sh run left machine-readable localhost-blocked "
            "reports. This usually means the current runner could not open localhost "
            "sockets; rerun the release gate from a normal terminal before treating "
            "the release as verified. A later successful release_check.sh run clears "
            "default stale blocked-report directories automatically."
        ),
        "report_root": report_root_label,
        "report_root_mode": "single_report_dir" if direct_report_files else "report_parent_dir",
        "latest_report_dir": diagnostic_repo_path(latest),
        "report_count": len(reports),
        "classifications": classifications,
        "contract_only_report_count": len(contract_reports),
        "contract_only_statuses": sorted(
            {
                f"{report.get('contract')}:{report.get('status')}"
                for report in contract_reports
                if report.get("contract")
            }
        ),
        "contract_only_reports_replace_runtime_gates": False,
        "reports": reports,
        "fix": (
            "Rerun ./scripts/release_check.sh from a normal terminal or host shell; "
            "a successful run clears default stale blocked reports. If the reports are "
            "already inspected and only the local warning is stale, clear them with "
            "--clear-release-blocked-reports."
        ),
        "next_commands": [
            "./scripts/release_check.sh",
            *CONTRACT_ONLY_RECOVERY_COMMANDS,
            (
                "STUDY_ANYTHING_RELEASE_BLOCKED_REPORT_DIR="
                f"{diagnostic_repo_path(latest)} ./scripts/release_check.sh"
            ),
            cleanup_command,
            "python3 scripts/diagnose_adoption.py",
        ],
    }


def check_env_file(env_file: Path, *, strict: bool = False) -> dict[str, Any]:
    if env_file.exists():
        command = [
            sys.executable,
            str(ROOT / "scripts" / "check_env.py"),
            "--env",
            str(env_file),
            "--json",
        ]
        if strict:
            command.append("--strict")
        try:
            completed = run(command, timeout=20)
        except subprocess.TimeoutExpired:
            return {
                "status": "warning",
                "name": "env_file",
                "code": "env_check_timeout",
                "message": "Environment file exists, but check_env.py timed out.",
                "fix": "Run python3 scripts/check_env.py manually, then rerun diagnostics.",
                "next_command": f"python3 scripts/check_env.py --env {diagnostic_path(env_file)} --strict",
            }
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {
                "status": "warning",
                "name": "env_file",
                "code": "env_check_unreadable",
                "message": "Environment file exists, but check_env.py did not emit a JSON report.",
                "stderr": sanitize_diagnostic(completed.stderr),
                "fix": "Run python3 scripts/check_env.py directly to inspect the env validation error.",
                "next_command": f"python3 scripts/check_env.py --env {diagnostic_path(env_file)} --strict",
            }
        problems = report.get("problems") if isinstance(report.get("problems"), list) else []
        warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
        if completed.returncode != 0 or report.get("status") == "fail":
            problem_codes = [
                str(item.get("code"))
                for item in problems
                if isinstance(item, dict) and item.get("code")
            ]
            return {
                "status": "warning",
                "name": "env_file",
                "code": "env_check_failed",
                "message": "Environment file exists, but check_env.py found blocking configuration issues.",
                "env_check_schema": report.get("schema_version"),
                "issue_codes": problem_codes,
                "problem_count": report.get("problem_count", len(problem_codes)),
                "warning_count": report.get("warning_count", len(warnings)),
                "problems": problems,
                "fix": "Fix .env before starting Skill Mode or Docker self-host.",
                "next_commands": [
                    f"python3 scripts/check_env.py --env {diagnostic_path(env_file)} --strict",
                    f"python3 scripts/setup_env.py --force --output {diagnostic_path(env_file)}",
                    "./scripts/doctor.sh",
                ],
            }
        warning_codes = [
            str(item.get("code"))
            for item in warnings
            if isinstance(item, dict) and item.get("code")
        ]
        return {
            "status": "ok",
            "name": "env_file",
            "code": "env_present",
            "message": f"Environment file exists and passed validation at {diagnostic_path(env_file)}.",
            "env_check_schema": report.get("schema_version"),
            "warning_count": report.get("warning_count", len(warning_codes)),
            "warning_codes": warning_codes,
        }
    return {
        "status": "warning",
        "name": "env_file",
        "code": "env_missing",
        "message": f"Environment file is missing at {diagnostic_path(env_file)}.",
        "fix": "Run python3 scripts/setup_env.py before Docker or Skill Mode startup.",
        "next_command": "python3 scripts/setup_env.py",
    }


def env_or_file_value(env_file: Path, key: str, default: str) -> str:
    override = os.environ.get(key)
    if override is not None and override.strip():
        return override.strip()
    value = read_shared_env_file_value(env_file, key)
    if value is not None and value.strip():
        return value.strip()
    return default


def is_valid_port(value: str) -> bool:
    try:
        port = int(value)
    except ValueError:
        return False
    return 1 <= port <= 65535


def check_launch_configuration(env_file: Path) -> dict[str, Any]:
    api_port = env_or_file_value(env_file, "API_PORT", "8000")
    stack_profile = env_or_file_value(env_file, "STACK_PROFILE", "core")
    issues: list[dict[str, str]] = []
    if not is_valid_port(api_port):
        issues.append(
            {
                "code": "invalid_api_port",
                "message": f"API_PORT={api_port} is not a valid TCP port.",
                "fix": "Unset API_PORT or set it to a number from 1 to 65535.",
            }
        )
    if stack_profile not in SUPPORTED_STACK_PROFILES:
        issues.append(
            {
                "code": "unsupported_stack_profile",
                "message": (
                    f"STACK_PROFILE={stack_profile} is not supported; use core, smoke, or full."
                ),
                "fix": "Unset STACK_PROFILE or set it to core, smoke, or full.",
            }
        )
    if issues:
        return {
            "status": "warning",
            "name": "launch_configuration",
            "code": "launch_configuration_invalid",
            "message": "Launch environment values need attention before startup.",
            "api_port": api_port,
            "stack_profile": stack_profile,
            "issue_codes": [issue["code"] for issue in issues],
            "issues": issues,
            "fix": "Fix API_PORT/STACK_PROFILE first, then rerun Skill Mode or Docker self-host.",
            "next_commands": [
                "unset API_PORT && ./scripts/launch_skill_mode.sh",
                "API_PORT=8012 ./scripts/launch_skill_mode.sh",
                "unset STACK_PROFILE && ./scripts/launch_self_host.sh",
                "./scripts/doctor.sh",
            ],
        }
    return {
        "status": "ok",
        "name": "launch_configuration",
        "code": "launch_configuration_ready",
        "message": "Launch environment values are valid.",
        "api_port": api_port,
        "stack_profile": stack_profile,
    }


def check_api(api_base: str) -> dict[str, Any]:
    parsed_api_base = urlparse(api_base)
    api_port = parsed_api_base.port or (443 if parsed_api_base.scheme == "https" else 80)
    try:
        health = request_json(f"{api_base.rstrip('/')}/v1/health")
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        if is_local_url(api_base) and is_local_socket_blocked(exc):
            return {
                "status": "warning",
                "name": "localhost_api",
                "code": "localhost_socket_permission_denied",
                "message": (
                    "Localhost API access is blocked from this runner at "
                    f"{sanitize_diagnostic(api_base)}: {sanitize_diagnostic(str(exc))}"
                ),
                "fix": (
                    "Run Study Anything from a normal terminal or host environment that permits "
                    "localhost sockets, then retry the API smoke."
                ),
                "next_command": "./scripts/launch_skill_mode.sh",
            }
        return {
            "status": "warning",
            "name": "localhost_api",
            "code": "api_unreachable",
            "message": (
                "Study Anything API is not reachable at "
                f"{sanitize_diagnostic(api_base)}: {sanitize_diagnostic(str(exc))}"
            ),
            "fix": (
                "Run ./scripts/launch_skill_mode.sh or ./scripts/launch_self_host.sh, "
                "then retry."
            ),
            "next_commands": [
                "./scripts/launch_skill_mode.sh",
                "./scripts/launch_self_host.sh",
            ],
        }
    if not is_study_anything_health_payload(health):
        return {
            "status": "warning",
            "name": "localhost_api",
            "code": "api_health_wrong_service",
            "message": (
                "A service responded at "
                f"{sanitize_diagnostic(api_base)}/v1/health, but it does not look like "
                "Study Anything."
            ),
            "health_excerpt": sanitized_health_excerpt(health),
            "fix": (
                "Use a free API_PORT or stop the service currently bound to this port, then "
                "start Study Anything Skill Mode again."
            ),
            "next_commands": [
                "API_PORT=8012 ./scripts/launch_skill_mode.sh",
                f"lsof -nP -iTCP:{api_port} -sTCP:LISTEN",
                "./scripts/stop_skill_mode.sh",
                "python3 scripts/diagnose_adoption.py",
            ],
            "privacy": {
                "health_excerpt_redacted": True,
                "raw_health_payload_returned": False,
            },
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
        code = docker_failure_kind(completed.stderr)
        if code == "docker_socket_permission_denied":
            return {
                "status": "warning",
                "name": "docker_daemon",
                "code": code,
                "message": "Docker socket is not accessible from this shell.",
                "stderr": sanitize_diagnostic(completed.stderr),
                "fix": (
                    "Start Docker Desktop, check the active Docker context, fix Docker socket "
                    "permissions, or use Skill Mode without Docker."
                ),
                "next_command": "./scripts/launch_skill_mode.sh",
            }
        return {
            "status": "warning",
            "name": "docker_daemon",
            "code": code,
            "message": "Docker daemon is not reachable.",
            "stderr": sanitize_diagnostic(completed.stderr),
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
            "stderr": sanitize_diagnostic(completed.stderr),
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


def normalize_agent_endpoint_for_diagnostics(endpoint: str) -> str:
    value = endpoint.strip()
    if "://" not in value and value.startswith(("127.", "localhost", "[::1]", "0.0.0.0")):
        value = f"http://{value}"
    return value


def endpoint_has_secret_material(endpoint: str) -> bool:
    parsed = urlparse(normalize_agent_endpoint_for_diagnostics(endpoint))
    if parsed.username or parsed.password:
        return True
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in SECRET_QUERY_KEYS:
            return True
        if value.startswith("sk-"):
            return True
    return False


def check_agent_endpoint_safety(endpoint: str) -> dict[str, Any] | None:
    if endpoint_has_secret_material(endpoint):
        return {
            "status": "warning",
            "name": "agent_endpoint",
            "code": "agent_endpoint_contains_secret",
            "message": (
                "Agent endpoint appears to contain inline credentials or secret-like query "
                "parameters. Study Anything will not probe or store this endpoint."
            ),
            "fix": (
                "Move model/API credentials into your private gateway or platform Agent "
                "environment, then pass only the plain /invoke endpoint."
            ),
            "next_command": "python3 scripts/study_anything_cli.py agent-add-http --set-default",
            "privacy": {
                "endpoint_value_returned": False,
                "endpoint_secrets_returned": False,
            },
        }
    return None


def health_url_for_agent(endpoint: str) -> str:
    endpoint = normalize_agent_endpoint_for_diagnostics(endpoint)
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return endpoint.rstrip("/") + "/health"
    path = parsed.path.rstrip("/")
    if path.endswith("/invoke"):
        path = path[: -len("/invoke")]
    base_path = path or ""
    return f"{parsed.scheme}://{parsed.netloc}{base_path}/health"


def check_agent_endpoint(endpoint: str) -> dict[str, Any]:
    unsafe = check_agent_endpoint_safety(endpoint)
    if unsafe is not None:
        return unsafe
    health_url = health_url_for_agent(endpoint)
    try:
        health = request_json(health_url)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        if is_local_url(health_url) and is_local_socket_blocked(exc):
            return {
                "status": "warning",
                "name": "agent_endpoint",
                "code": "agent_local_socket_permission_denied",
                "message": (
                    "Localhost Agent endpoint access is blocked from this runner at "
                    f"{sanitize_diagnostic(health_url)}: {sanitize_diagnostic(str(exc))}"
                ),
                "fix": (
                    "Run the gateway and verifier from a normal terminal or host environment "
                    "that permits localhost sockets."
                ),
                "next_command": "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
            }
        return {
            "status": "warning",
            "name": "agent_endpoint",
            "code": "agent_endpoint_unreachable",
            "message": (
                "Agent health is not reachable at "
                f"{sanitize_diagnostic(health_url)}: {sanitize_diagnostic(str(exc))}"
            ),
            "fix": "Start scripts/openai_compatible_agent_gateway.py or your private HTTP Agent.",
            "next_command": "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
        }
    status = health.get("status")
    if status not in {"ok", "healthy"}:
        next_steps = health.get("next_steps")
        return {
            "status": "warning",
            "name": "agent_endpoint",
            "code": str(health.get("diagnostic_code") or "agent_endpoint_unhealthy"),
            "message": sanitize_diagnostic(
                str(health.get("message") or f"Agent endpoint health returned status={status}.")
            ),
            "health_url": sanitize_diagnostic(health_url),
            "fix": (
                "Use dry-run for zero-configuration validation, or configure the user-owned "
                "Agent/model exit outside Study Anything."
            ),
            "next_command": "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
            "next_steps": sanitize_diagnostic_list(next_steps),
        }
    return {
        "status": "ok",
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
        if is_local_url(api_base) and is_local_socket_blocked(exc):
            return {
                "status": "warning",
                "name": "provider_capabilities",
                "code": "provider_status_blocked_by_localhost_socket",
                "message": (
                    "Cannot inspect provider defaults because this runner blocks "
                    f"localhost API access at {sanitize_diagnostic(api_base)}: "
                    f"{sanitize_diagnostic(str(exc))}"
                ),
                "fix": (
                    "Run Study Anything from a normal terminal or host environment that "
                    "permits localhost sockets, then retry provider diagnostics."
                ),
                "next_command": "./scripts/launch_skill_mode.sh",
            }
        return {
            "status": "warning",
            "name": "provider_capabilities",
            "code": "provider_status_unreachable",
            "message": (
                "Cannot inspect provider defaults because API is unavailable: "
                f"{sanitize_diagnostic(str(exc))}"
            ),
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
                "Run scripts/study_anything_cli.py agent-add-http --set-default for the "
                "local gateway, pass --endpoint only for a custom Agent, or set defaults "
                "with POST /v1/agents/defaults."
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
    failed_issue_codes = [
        str(issue_code)
        for check in checks
        if check.get("status") != "ok"
        for issue_code in check.get("issue_codes", [])
        if isinstance(issue_code, str)
    ]
    release_tag = image.rsplit(":", 1)[-1] if ":" in image else DEFAULT_TAG
    commands = {
        "normal_terminal": (
            "Run the following commands from a normal terminal or host shell that permits "
            "localhost sockets."
        ),
        "prepare_env": "python3 scripts/setup_env.py",
        "validate_env": "python3 scripts/check_env.py --strict",
        "regenerate_env": "python3 scripts/setup_env.py --force",
        "doctor": "./scripts/doctor.sh",
        "diagnose": "python3 scripts/diagnose_adoption.py",
        "clear_release_blocked_reports": (
            "python3 scripts/diagnose_adoption.py --clear-release-blocked-reports"
        ),
        "release_check": "./scripts/release_check.sh",
        "skill_mode": "./scripts/launch_skill_mode.sh",
        "skill_mode_demo": "./scripts/run_skill_mode_demo.sh",
        "docker_source": "./scripts/launch_self_host.sh",
        "docker_published_image": (
            f"USE_PUBLISHED_IMAGES=true STUDY_ANYTHING_IMAGE_TAG={release_tag} "
            "./scripts/launch_self_host.sh"
        ),
        "reset_api_port_skill_mode": "unset API_PORT && ./scripts/launch_skill_mode.sh",
        "alternate_api_port_skill_mode": "API_PORT=8012 ./scripts/launch_skill_mode.sh",
        "reset_stack_profile_self_host": "unset STACK_PROFILE && ./scripts/launch_self_host.sh",
        "core_profile_self_host": "STACK_PROFILE=core ./scripts/launch_self_host.sh",
        "api_smoke": f"API_BASE={api_base} python3 scripts/verify_full_api_flow.py",
        "platform_tools_smoke": (
            f"API_BASE={api_base} python3 scripts/verify_platform_agent_tools.py"
        ),
        "adoption_telemetry": (
            f"python3 scripts/verify_adoption_telemetry.py --api-base {api_base}"
        ),
        "agent_gateway_dry_run": (
            "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787"
        ),
        "openai_gateway_contract": (
            "python3 scripts/verify_openai_compatible_gateway.py --contract-only"
        ),
        "agent_gateway_contract": (
            "python3 scripts/verify_agent_gateway_hardening.py --contract-only"
        ),
        "external_agent_adapter_contract": (
            "python3 scripts/verify_external_agent_adapter_hardening.py --contract-only"
        ),
        "agent_register_local_gateway": (
            "python3 scripts/study_anything_cli.py agent-add-http --set-default"
        ),
        "published_image_smoke": (
            f"python3 scripts/verify_published_image_launch.py --tag {release_tag} "
            "--pull-timeout-seconds 180 --allow-pull-timeout-report"
        ),
        "ghcr_manifest": f"docker manifest inspect {image}",
    }
    local_socket_codes = {
        "localhost_socket_permission_denied",
        "agent_local_socket_permission_denied",
        "provider_status_blocked_by_localhost_socket",
        "release_check_localhost_blocked_reports_present",
    }
    agent_gateway_codes = {
        "agent_endpoint_unreachable",
        "agent_endpoint_unhealthy",
        "configuration_required",
    }
    if "invalid_api_port" in failed_issue_codes and "unsupported_stack_profile" in failed_issue_codes:
        recommended = ["reset_api_port_skill_mode", "reset_stack_profile_self_host", "doctor"]
    elif "invalid_api_port" in failed_issue_codes:
        recommended = ["reset_api_port_skill_mode", "alternate_api_port_skill_mode", "doctor"]
    elif "unsupported_stack_profile" in failed_issue_codes:
        recommended = ["reset_stack_profile_self_host", "core_profile_self_host", "doctor"]
    elif "agent_endpoint_contains_secret" in failed_codes:
        recommended = ["agent_gateway_dry_run", "agent_register_local_gateway", "doctor"]
    elif "env_check_failed" in failed_codes:
        recommended = ["validate_env", "regenerate_env", "doctor"]
    elif "release_check_localhost_blocked_reports_present" in failed_codes:
        recommended = ["normal_terminal", "release_check", "clear_release_blocked_reports", "diagnose"]
    elif any(code in failed_codes for code in agent_gateway_codes):
        recommended = ["agent_gateway_dry_run", "agent_register_local_gateway", "platform_tools_smoke"]
    elif any(code in failed_codes for code in local_socket_codes):
        recommended = [
            "normal_terminal",
            "openai_gateway_contract",
            "agent_gateway_contract",
            "external_agent_adapter_contract",
            "skill_mode_demo",
            "skill_mode",
            "api_smoke",
            "agent_gateway_dry_run",
            "agent_register_local_gateway",
            "platform_tools_smoke",
        ]
    elif (
        "docker_missing" in failed_codes
        or "docker_daemon_unreachable" in failed_codes
        or "docker_socket_permission_denied" in failed_codes
    ):
        recommended = ["prepare_env", "skill_mode_demo", "skill_mode", "api_smoke"]
    elif "env_missing" in failed_codes:
        recommended = ["prepare_env", "doctor"]
    elif "api_health_wrong_service" in failed_codes:
        recommended = ["alternate_api_port_skill_mode", "doctor", "diagnose"]
    elif "api_unreachable" in failed_codes:
        recommended = ["doctor", "docker_published_image", "api_smoke"]
    elif "provider_defaults_missing" in failed_codes:
        recommended = ["agent_gateway_dry_run", "agent_register_local_gateway", "platform_tools_smoke"]
    else:
        recommended = ["doctor", "api_smoke", "platform_tools_smoke", "adoption_telemetry"]
    return {
        "schema_version": "adoption-diagnostic-plan-v1",
        "summary": "Copyable next commands for local-first Study Anything adoption.",
        "failed_codes": failed_codes,
        "failed_issue_codes": failed_issue_codes,
        "recommended_order": recommended,
        "commands": commands,
        "environment": {
            "localhost_sockets_required": True,
            "normal_terminal_required": any(code in failed_codes for code in local_socket_codes),
        },
        "privacy": {
            "do_not_include": [
                "real model API keys",
                "agent endpoint secrets",
                "raw source text",
                "learner answers",
            ]
        },
    }


def build_recommended_path(plan: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    commands = plan.get("commands") if isinstance(plan.get("commands"), dict) else {}
    recommended_order = [
        str(item) for item in plan.get("recommended_order", []) if isinstance(item, str)
    ]
    all_codes = [str(check.get("code")) for check in checks if check.get("code")]
    failed_codes = [
        str(check.get("code"))
        for check in checks
        if check.get("status") != "ok" and check.get("code")
    ]
    local_socket_codes = {
        "localhost_socket_permission_denied",
        "agent_local_socket_permission_denied",
        "provider_status_blocked_by_localhost_socket",
        "release_check_localhost_blocked_reports_present",
    }
    env_present = "env_present" in all_codes and "env_missing" not in failed_codes
    specific_recovery_commands: list[str] = []
    if "env_check_failed" in failed_codes:
        for check in checks:
            if check.get("code") != "env_check_failed":
                continue
            for command in check.get("next_commands", []):
                if isinstance(command, str) and command not in specific_recovery_commands:
                    specific_recovery_commands.append(command)
    if any(
        code in failed_codes
        for code in {
            "release_check_localhost_blocked_reports_present",
            "release_report_path_not_directory",
            "release_report_dir_unreadable",
        }
    ):
        for check in checks:
            if check.get("code") not in {
                "release_check_localhost_blocked_reports_present",
                "release_report_path_not_directory",
                "release_report_dir_unreadable",
            }:
                continue
            for command in check.get("next_commands", []):
                if isinstance(command, str) and command not in specific_recovery_commands:
                    specific_recovery_commands.append(command)
    copyable_commands: list[str] = list(specific_recovery_commands)
    for key in recommended_order:
        if key == "normal_terminal":
            continue
        if key == "prepare_env" and env_present:
            continue
        if key in {"validate_env", "regenerate_env"} and specific_recovery_commands:
            continue
        if (
            key == "clear_release_blocked_reports"
            and any("--clear-release-blocked-reports" in command for command in specific_recovery_commands)
        ):
            continue
        command = commands.get(key)
        if isinstance(command, str) and command not in copyable_commands:
            copyable_commands.append(command)
    notes: list[str] = []
    environment = plan.get("environment") if isinstance(plan.get("environment"), dict) else {}
    if environment.get("normal_terminal_required"):
        normal_terminal = commands.get("normal_terminal")
        if isinstance(normal_terminal, str):
            notes.append(normal_terminal)
    if env_present and (
        "prepare_env" in recommended_order or "skill_mode_demo" in recommended_order
    ):
        notes.append(".env already exists; using existing local env in the primary path.")
    if "env_check_failed" in failed_codes:
        notes.append(".env exists but failed validation; fix it before starting any runtime.")
    if (
        "docker_missing" in failed_codes
        or "docker_socket_permission_denied" in failed_codes
        or "docker_daemon_unreachable" in failed_codes
    ):
        notes.append("Docker is optional for the first smoke; Skill Mode is the shortest local path.")
    if "env_missing" in failed_codes:
        notes.append("Create .env before Docker self-host so generated secrets are local and explicit.")
    if "api_health_wrong_service" in failed_codes:
        notes.append(
            "The configured API port is answering, but the response is not Study Anything; "
            "use a free API_PORT or stop the service on that port."
        )
    if "provider_defaults_missing" in failed_codes:
        notes.append(
            "The API is reachable, but Agent defaults are missing; register a provider with "
            "--set-default before judging learning quality."
        )
    if any(
        code in failed_codes
        for code in {
            "agent_endpoint_unreachable",
            "agent_endpoint_unhealthy",
            "configuration_required",
        }
    ):
        notes.append(
            "Start or fix the user-owned Agent gateway first; dry-run mode proves the local "
            "learning loop without model credentials."
        )
    if "agent_endpoint_contains_secret" in failed_codes:
        notes.append(
            "Remove credentials from Agent endpoint URLs; keep model/API keys inside the "
            "gateway or platform Agent environment."
        )
    if "launch_configuration_invalid" in failed_codes:
        notes.append("Fix launch configuration before judging API, Docker, or Agent readiness.")
    if (
        any(code in failed_codes for code in local_socket_codes)
        and "release_check_localhost_blocked_reports_present" not in failed_codes
    ):
        notes.append(
            "This runner appears to block localhost sockets. Run the contract-only checks "
            "here for sandbox evidence, then run the runtime smoke from a normal terminal."
        )
    if "release_check_localhost_blocked_reports_present" in failed_codes:
        notes.append(
            "A previous release gate produced localhost-blocked reports; rerun release_check.sh "
            "from a normal terminal before treating the release as verified."
        )
        for check in checks:
            if check.get("code") != "release_check_localhost_blocked_reports_present":
                continue
            contract_statuses = check.get("contract_only_statuses")
            if isinstance(contract_statuses, list) and contract_statuses:
                statuses = ", ".join(str(item) for item in contract_statuses if isinstance(item, str))
                if statuses:
                    notes.append(
                        "No-socket contract reports found in the blocked report directory: "
                        f"{statuses}. These are useful sandbox evidence, not release verification."
                    )
                break
        notes.append(
            "After inspecting the local reports, --clear-release-blocked-reports can remove "
            "stale diagnostics, but cleanup is not release verification."
        )
    if "release_report_path_not_directory" in failed_codes:
        notes.append(
            "--release-report-dir points at a file or non-directory path; rerun diagnostics "
            "with data/release-blocked-reports or a numbered report directory."
        )
    if "release_report_dir_unreadable" in failed_codes:
        notes.append(
            "The release blocked report directory could not be read; check permissions or "
            "rerun release_check.sh to create a fresh report."
        )
    if not copyable_commands:
        fallback = commands.get("doctor")
        if isinstance(fallback, str):
            copyable_commands.append(fallback)
    terminal_steps: list[dict[str, str]] = []
    seen_terminal_commands: set[str] = set()
    for command in specific_recovery_commands:
        description = "Run this recovery command before the remaining proof steps."
        if "--contract-only" in command:
            description = (
                "Prove the gateway/adapter contract without opening localhost sockets; "
                "this is useful sandbox evidence, not release verification."
            )
        elif "--clear-release-blocked-reports" in command:
            description = (
                "Clear inspected stale release-blocked diagnostics before rerunning "
                "release verification."
            )
        elif "--release-report-dir" in command:
            description = (
                "Rerun diagnostics with a valid release blocked report directory."
            )
        elif "check_env.py" in command or "setup_env.py" in command:
            description = "Fix local environment configuration before starting a runtime."
        terminal_steps.append(
            {
                "terminal": "terminal_1",
                "description": description,
                "command": command,
            }
        )
        seen_terminal_commands.add(command)
    if "release_check_localhost_blocked_reports_present" in failed_codes:
        release_check_command = commands.get("release_check")
        if isinstance(release_check_command, str) and release_check_command not in seen_terminal_commands:
            terminal_steps.append(
                {
                    "terminal": "terminal_1",
                    "description": (
                        "Rerun the strict release gate from a normal terminal that permits "
                        "localhost sockets."
                    ),
                    "command": release_check_command,
                }
            )
            seen_terminal_commands.add(release_check_command)
    needs_terminal_split = (
        (
            environment.get("normal_terminal_required")
            and "release_check_localhost_blocked_reports_present" not in failed_codes
        )
        or "agent_gateway_dry_run" in recommended_order
    )
    if needs_terminal_split:
        ordered_terminal_steps = []
        if any(
            key in recommended_order
            for key in {
                "openai_gateway_contract",
                "agent_gateway_contract",
                "external_agent_adapter_contract",
            }
        ):
            ordered_terminal_steps.extend(
                [
                    (
                        "terminal_1",
                        (
                            "Prove the OpenAI-compatible gateway contract without opening "
                            "localhost sockets; this is sandbox evidence, not runtime proof."
                        ),
                        commands.get("openai_gateway_contract"),
                    ),
                    (
                        "terminal_1",
                        (
                            "Prove gateway hardening without opening localhost sockets; "
                            "this does not replace the runtime smoke."
                        ),
                        commands.get("agent_gateway_contract"),
                    ),
                    (
                        "terminal_1",
                        (
                            "Prove external Agent adapter redaction/eval contracts without "
                            "opening localhost sockets."
                        ),
                        commands.get("external_agent_adapter_contract"),
                    ),
                ]
            )
        ordered_terminal_steps.extend([
            (
                "terminal_1",
                "Run the complete zero-configuration Skill Mode and dry-run Agent demo.",
                commands.get("skill_mode_demo"),
            ),
            (
                "terminal_1",
                "Start the local Study Anything API.",
                commands.get("skill_mode"),
            ),
            (
                "terminal_1",
                "Prove the local API can complete the fake-agent learning flow.",
                commands.get("api_smoke"),
            ),
            (
                "terminal_2",
                "Start the zero-key HTTP Agent gateway and leave this process running.",
                commands.get("agent_gateway_dry_run"),
            ),
            (
                "terminal_1",
                "Register the running gateway as the default Agent provider.",
                commands.get("agent_register_local_gateway"),
            ),
            (
                "terminal_1",
                "Prove platform Agent tools can call the configured provider.",
                commands.get("platform_tools_smoke"),
            ),
        ])
        for terminal, description, command in ordered_terminal_steps:
            if isinstance(command, str) and command not in seen_terminal_commands:
                terminal_steps.append(
                    {
                        "terminal": terminal,
                        "description": description,
                        "command": command,
                    }
                )
                seen_terminal_commands.add(command)
    if needs_terminal_split and terminal_steps:
        notes.append(
            "The Agent gateway command is a long-running process; keep it open in a second terminal."
        )
    return {
        "schema_version": "adoption-recommended-path-v1",
        "status": "ready" if not failed_codes else "needs_attention",
        "summary": (
            "Run the primary command first; the remaining commands are ordered recovery or proof steps."
        ),
        "blocking_codes": failed_codes,
        "primary_command": copyable_commands[0] if copyable_commands else "",
        "copyable_commands": copyable_commands,
        "terminal_steps": terminal_steps,
        "operator_notes": notes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base",
        help=(
            "Study Anything API base. Defaults to API_BASE, STUDY_ANYTHING_API_BASE, "
            "or API_PORT from --env-file/.env."
        ),
    )
    parser.add_argument("--agent-endpoint", default="http://127.0.0.1:8787/invoke")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--release-report-dir",
        default=DEFAULT_RELEASE_BLOCKED_REPORT_DIR_TEXT,
        help=(
            "Directory where release_check.sh writes localhost-blocked reports. "
            "Relative paths are resolved from the repository root."
        ),
    )
    parser.add_argument(
        "--clear-release-blocked-reports",
        action="store_true",
        help=(
            "Safely remove local release_check localhost-blocked report directories under "
            "repo data/. This does not replace a successful release_check.sh run."
        ),
    )
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
    )
    parser.add_argument("--user-id", default="local-user")
    parser.add_argument("--ghcr-timeout-seconds", type=int, default=20)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    env_file = Path(args.env_file)
    release_report_dir = Path(args.release_report_dir)
    if not release_report_dir.is_absolute():
        release_report_dir = ROOT / release_report_dir
    if args.clear_release_blocked_reports:
        payload = clear_release_blocked_reports(release_report_dir)
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if payload["status"] != "ok":
            raise SystemExit(1)
        return
    api_base = args.api_base or resolve_api_base(env_file=env_file)

    checks = [
        check_env_file(env_file, strict=args.strict),
        check_launch_configuration(env_file),
        check_release_blocked_reports(release_report_dir),
        check_api(api_base),
        check_docker(),
        check_ghcr_manifest(args.image, timeout=args.ghcr_timeout_seconds),
        check_agent_endpoint(args.agent_endpoint),
        check_provider_capabilities(
            api_base,
            user_id=args.user_id,
            required_capabilities=DEFAULT_CAPABILITIES,
        ),
    ]
    status = "ok" if all(check["status"] == "ok" for check in checks) else "needs_attention"
    recovery_plan = build_recovery_plan(
        api_base=api_base,
        image=args.image,
        checks=checks,
    )
    payload = {
        "status": status,
        "schema_version": "adoption-diagnostics-v1",
        "checks": checks,
        "recovery_plan": recovery_plan,
        "recommended_path": build_recommended_path(recovery_plan, checks),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and status != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
