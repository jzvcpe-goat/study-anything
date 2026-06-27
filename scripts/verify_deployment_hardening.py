#!/usr/bin/env python3
"""Verify deployment hardening evidence for external operator adoption."""

from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import redact_diagnostic  # noqa: E402

SCHEMA_VERSION = "deployment-hardening-verification-v1"
RELEASE_VERSION = "v0.3.29-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-deployment-hardening.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"

PLATFORM_IDS = ("codex", "kimi", "workbuddy")
REQUIRED_PACK_COMMAND = "verify_deployment_hardening.py --check"
REQUIRED_SOURCE_COMMAND = "verify_commercial_readiness.py"
REQUIRED_EVIDENCE = "deployment_hardening.schema_version == deployment-hardening-verification-v1"
REQUIRED_FILES = [
    "README.md",
    "QUICKSTART.md",
    "docs/adoption.md",
    "docs/self-hosting.md",
    "docs/github-launch.md",
    "docs/platform-agent-integrations.md",
    "docs/use-with-kimi.md",
    "scripts/launch_self_host.sh",
    "scripts/study_anything_cli.py",
    "scripts/release_check.sh",
    "START_HERE.command",
    "scripts/doctor.sh",
    "scripts/diagnose_adoption.py",
    "scripts/stop_self_host.sh",
    "scripts/verify_api_smoke.sh",
    "scripts/verify_published_image_launch.py",
    "scripts/verify_clean_clone_adoption.py",
    "scripts/setup_env.py",
    "scripts/check_env.py",
    "infra/compose/docker-compose.yml",
    "infra/compose/docker-compose.images.yml",
    "platform/ecosystem-submission.json",
    "platform/generated/study-anything-platform-adoption-pack.json",
    "platform/generated/study-anything-platform-bundle.json",
]
PACK_MANIFEST_REPLACEMENTS = {
    "platform/generated/study-anything-platform-adoption-pack.json": "manifest.json",
}
SOURCE_ONLY_REQUIRED_FILES = {
    "platform/generated/study-anything-platform-bundle.json",
}
RAW_SOURCE_TEXT_SENTINEL = "raw source text " + "returned"
LEARNER_EMAIL_SENTINEL = "learner" + "@example.com"
PRIVATE_ANSWER_SENTINEL = "Private " + "answer:"
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    LEARNER_EMAIL_SENTINEL,
    PRIVATE_ANSWER_SENTINEL,
    RAW_SOURCE_TEXT_SENTINEL,
    "Private platform browser/video context",
]


class DeploymentHardeningError(RuntimeError):
    """Readable deployment-hardening verification failure."""


def format_cli_failure(exc: BaseException) -> str:
    diagnostic = redact_diagnostic(str(exc))
    return "\n".join(
        [
            f"verify_deployment_hardening failed: {diagnostic}",
            "",
            "Next steps:",
            "  1. Rebuild the deployment report: python3 scripts/verify_deployment_hardening.py --write",
            "  2. Check the generated report: python3 scripts/verify_deployment_hardening.py --check",
            "  3. Validate the distributed pack: python3 scripts/verify_deployment_hardening.py --pack platform/generated/study-anything-platform-adoption-pack.zip",
            "  4. If pack contents changed, refresh: python3 scripts/generate_platform_adoption_pack.py && python3 scripts/generate_platform_bundle_manifest.py",
            "  5. For local environment diagnostics, run: python3 scripts/diagnose_adoption.py",
            "  6. See docs/self-hosting.md, docs/adoption.md, docs/github-launch.md, and docs/skill-mode.md.",
        ]
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DeploymentHardeningError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DeploymentHardeningError(f"JSON object expected: {path}")
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise DeploymentHardeningError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise DeploymentHardeningError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise DeploymentHardeningError(
                    f"Adoption pack archive should have one root, got {sorted(roots)}"
                )
            archive.extractall(tmp_root)
        return tmp_root / next(iter(roots))
    return ROOT


def safe_relative(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise DeploymentHardeningError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise DeploymentHardeningError(f"Required deployment asset is missing: {relative_path}")
    return target


def assert_contains(root: Path, relative_path: str, *needles: str) -> str:
    target = require_file(root, relative_path)
    text = target.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise DeploymentHardeningError(f"{relative_path} is missing required text: {missing}")
    return text


def assert_no_sensitive_text(report_text: str) -> None:
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(report_text):
            raise DeploymentHardeningError("Deployment report contains secret-like text.")
    for literal in FORBIDDEN_LITERALS:
        if literal in report_text:
            raise DeploymentHardeningError(f"Deployment report contains forbidden literal: {literal}")


def verify_required_files(root: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    pack_root = safe_relative(root, "manifest.json").is_file()
    for relative_path in REQUIRED_FILES:
        if pack_root and relative_path in PACK_MANIFEST_REPLACEMENTS:
            pack_path = PACK_MANIFEST_REPLACEMENTS[relative_path]
            require_file(root, pack_path)
            files.append(
                {
                    "path": pack_path,
                    "status": "present",
                    "source_equivalent": relative_path,
                }
            )
            continue
        if pack_root and relative_path in SOURCE_ONLY_REQUIRED_FILES:
            files.append({"path": relative_path, "status": "source_only_not_in_pack"})
            continue
        require_file(root, relative_path)
        files.append({"path": relative_path, "status": "present"})
    return files


def verify_launch_script(root: Path) -> dict[str, Any]:
    text = assert_contains(
        root,
        "scripts/launch_self_host.sh",
        RELEASE_VERSION,
        "USE_PUBLISHED_IMAGES",
        "PULL_PUBLISHED_IMAGES",
        "STUDY_ANYTHING_API_IMAGE",
        "docker-compose.images.yml",
        "path_has_non_ascii",
        "ALLOW_NON_ASCII_DOCKER_BUILD",
        "docker info",
        "print_compose_up_failure_hint",
        "print_api_health_timeout_hint",
        "validate_self_host_unique_active_ports",
        "Duplicate host port",
        "active_self_host_port_records",
        "SELF_HOST_API_HEALTH_ATTEMPTS",
        "self_host_api_port",
        "export[[:space:]]+",
        "logs --tail=200 api app-postgres",
        "API_PORT=8012 ./scripts/launch_self_host.sh",
        "STACK_PROFILE=core ./scripts/launch_self_host.sh",
        "API did not become healthy",
    )
    if "up -d --build" not in text:
        raise DeploymentHardeningError("launch_self_host.sh must keep source-build path explicit.")
    return {
        "script": "scripts/launch_self_host.sh",
        "published_image_default_tag": RELEASE_VERSION,
        "supports_published_images": True,
        "supports_cached_image_skip": True,
        "guards_non_ascii_source_builds": True,
        "source_build_requires_explicit_bypass_for_non_ascii": True,
        "validates_duplicate_active_host_ports": True,
        "honors_env_file_api_port_after_launch": True,
        "supports_export_style_env_lines": True,
    }


def verify_skill_mode_launcher(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/launch_skill_mode.sh",
        "env_or_file_value",
        "STUDY_ANYTHING_ENV_FILE",
        'api_port="$(env_or_file_value API_PORT 8000)"',
        "Invalid API_PORT=%s for Skill Mode.",
        "API_PORT=8012 ./scripts/launch_skill_mode.sh",
        "is_study_anything_health_payload",
        "print_wrong_health_service_hint",
        "does not look like Study Anything",
        "print_port_in_use_hint",
        "print_early_exit_hint",
        "print_contract_only_recovery_hint",
        "No startup log was written before the process exited.",
        "./scripts/launch_skill_mode.sh --foreground",
        "verify_openai_compatible_gateway.py --contract-only",
        "verify_agent_gateway_hardening.py --contract-only",
        "verify_external_agent_adapter_hardening.py --contract-only",
        "sandbox evidence only",
        "./scripts/stop_skill_mode.sh",
        "lsof -nP -iTCP:%s -sTCP:LISTEN",
        "python3 scripts/diagnose_adoption.py",
    )
    return {
        "script": "scripts/launch_skill_mode.sh",
        "api_port_sources": ["API_PORT", ".env API_PORT", "default 8000"],
        "environment_override_wins": True,
        "validates_api_port_before_start": True,
        "rejects_non_study_health_responders": True,
        "socket_blocked_contract_only_recovery": True,
        "redacted_diagnostics": True,
    }


def verify_beginner_launcher(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/start_here.sh",
        "Study Anything beginner launcher",
        "START_HERE.command",
        "QUICKSTART.md",
        "run_demo",
        "sh ./scripts/run_skill_mode_demo.sh",
        "run_keep_running",
        "sh ./scripts/launch_skill_mode.sh",
        "run_foreground",
        "SKILL_API_FOREGROUND=true exec sh ./scripts/launch_skill_mode.sh",
        "run_docker",
        "sh ./scripts/launch_self_host.sh",
        "run_check_only",
        "verify_openai_compatible_gateway.py --contract-only",
        "verify_agent_gateway_hardening.py --contract-only",
        "verify_external_agent_adapter_hardening.py --contract-only",
        "These checks do not replace a real localhost runtime smoke",
        "docs/getting-started.md",
        "Do not paste raw source text",
    )
    return {
        "script": "scripts/start_here.sh",
        "one_click_macos_launcher": "START_HERE.command",
        "default_mode": "zero_key_disposable_demo",
        "supports_persistent_skill_mode": True,
        "supports_foreground_skill_mode": True,
        "supports_docker_self_host": True,
        "supports_no_socket_contract_checks": True,
        "privacy_warning": True,
    }


def verify_stop_self_host_script(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/stop_self_host.sh",
        'env_file="${ENV_FILE:-${STUDY_ANYTHING_ENV_FILE:-.env}}"',
        '--env-file "$env_file"',
        "docker compose version",
        "docker info",
        "Docker socket is not accessible",
        "./scripts/stop_skill_mode.sh",
        "python3 scripts/diagnose_adoption.py",
    )
    return {
        "script": "scripts/stop_self_host.sh",
        "honors_custom_env_file": True,
        "checks_docker_before_compose_down": True,
        "redacted_diagnostics": True,
    }


def verify_recovery_env_parsers(root: Path) -> dict[str, Any]:
    scripts = [
        "scripts/self_host_data.py",
        "scripts/verify_backup_restore_drill.py",
        "scripts/verify_published_image_launch.py",
    ]
    for path in scripts:
        assert_contains(
            root,
            path,
            "stripped.startswith(\"export \")",
            're.split(r"\\s+#"',
            "COMPOSE_PROJECT_NAME",
        )
    assert_contains(
        root,
        "scripts/self_host_data.py",
        "format_error",
        "sanitize_text",
        "self_host_data failed [",
        "Next steps:",
        "docker_daemon_unavailable",
        "restore_confirmation_required",
        "local absolute paths",
        "<local-path>",
    )
    return {
        "scripts": scripts,
        "supports_export_style_env_lines": True,
        "strips_unquoted_inline_comments": True,
        "preserves_quoted_values": True,
        "redacts_backup_restore_cli_errors": True,
        "copyable_backup_restore_next_steps": True,
    }


def verify_verifier_api_base_resolution(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/localhost_diagnostics.py",
        "normalise_api_base",
        "resolve_api_base",
        "STUDY_ANYTHING_ENV_FILE",
        "api_base_from_env_file",
        "API_PORT",
        "127.",
        "/v1/health",
        "SECRET_QUERY_KEYS",
        "api-key",
        "x-api-key",
        "accesstoken",
        "clientsecret",
        "cookie",
        "redact_url",
    )
    scripts = [
        "scripts/verify_full_api_flow.py",
        "scripts/verify_agent_eval_flow.py",
        "scripts/verify_mock_http_agent_flow.py",
        "scripts/verify_platform_lesson_flow.py",
        "scripts/verify_importer_lesson_flow.py",
        "scripts/verify_importer_runtime_retrieval_flow.py",
        "scripts/verify_platform_agent_tools.py",
        "scripts/verify_platform_ecosystem_eval_flow.py",
        "scripts/verify_falkordb_flow.py",
        "scripts/run_external_agent_evals.py",
        "scripts/verify_openai_compatible_gateway.py",
        "scripts/verify_skill_cli_flow.py",
        "scripts/diagnose_adoption.py",
    ]
    for path in scripts:
        assert_contains(root, path, "resolve_api_base")
    assert_contains(
        root,
        "scripts/verify_openai_compatible_gateway.py",
        "DEFAULT_GATEWAY_PORT = 8787",
        "resolve_gateway_port",
        "reuse_running_gateway",
        "ephemeral free port",
    )
    return {
        "helper": "scripts/localhost_diagnostics.py",
        "api_base_sources": ["API_BASE", "STUDY_ANYTHING_API_BASE", ".env API_PORT", "default 8000"],
        "gateway_port_sources": [
            "--port",
            "--reuse-running-gateway default 8787",
            "ephemeral verifier-owned port",
        ],
        "script_count": len(scripts),
        "scripts": scripts,
    }


def verify_doctor(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/doctor.sh",
        RELEASE_VERSION,
        "docker compose version",
        "docker daemon is running",
        "docker socket is not accessible",
        "check_python_runtime",
        "Python 3.11 or newer",
        "PYTHON_BIN=/path/to/python3.11",
        "STUDY_ANYTHING_ENV_FILE",
        "check_port",
        "is_study_anything_health_payload",
        "is_agent_gateway_health_payload_ready",
        "normalize_agent_gateway_url",
        "http://0.0.0.0:",
        "http://127.0.0.1:${value#http://0.0.0.0:}",
        "agent_endpoint_has_secret_material",
        "agent_gateway_health_url",
        "does not look like Study Anything",
        "not healthy yet",
        "AGENT_HTTP_GATEWAY_URL must not contain inline credentials",
        "lower_value=",
        "api-key",
        "x-api-key",
        "accesstoken",
        "authorization",
        "clientsecret",
        "AGENT_GATEWAY_MODE=dry_run",
        "AGENT_HTTP_GATEWAY_URL",
        "USE_PUBLISHED_IMAGES=true",
        "PULL_PUBLISHED_IMAGES=false",
        "latest_release_blocked_report_dir",
        "release_report_python",
        "release_contract_report_summary",
        "Release gate reminder",
        "release_check.sh left localhost-blocked reports",
        "Contract-only no-socket reports",
        "replaces runtime gate",
        "These reports prove sandbox-safe contracts only",
        "--clear-release-blocked-reports",
        "Recovery commands",
    )
    return {
        "script": "scripts/doctor.sh",
        "checks": [
            "docker",
            "docker_compose",
            "docker_daemon",
            "python_runtime",
            "env_file",
            "non_ascii_source_path",
            "ports",
            "api_health",
            "api_health_wrong_service",
            "agent_gateway_hint",
            "agent_gateway_unhealthy",
            "agent_gateway_bind_address_probe_normalization",
            "agent_endpoint_contains_secret",
            "agent_endpoint_secret_query_case_insensitive",
            "plugin_install_dir",
            "release_blocked_report_hint",
            "release_blocked_contract_summary",
        ],
    }


def verify_diagnostics(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/diagnose_adoption.py",
        RELEASE_VERSION,
        "adoption-diagnostic-plan-v1",
        "check_ghcr_manifest",
        "check_agent_endpoint",
        "check_release_blocked_reports",
        "clear_release_blocked_reports",
        "api_health_wrong_service",
        "is_study_anything_health_payload",
        "release_check_localhost_blocked_reports_present",
        "--clear-release-blocked-reports",
        "data/release-blocked-reports",
        "--release-report-dir",
        "published_image_smoke",
        "ghcr_manifest",
        "do_not_include",
    )
    return {
        "script": "scripts/diagnose_adoption.py",
        "schema": "adoption-diagnostic-plan-v1",
        "covers": [
            "env_file",
            "localhost_api",
            "api_health_wrong_service",
            "release_blocked_reports",
            "release_blocked_report_cleanup",
            "docker_daemon",
            "ghcr_manifest",
            "agent_endpoint",
            "provider_capabilities",
        ],
    }


def verify_env_check(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/check_env.py",
        "PORT_DEFAULTS",
        "PROFILE_HOST_PORT_KEYS",
        "invalid_port_value",
        "duplicate_host_port_value",
        "unsupported_stack_profile",
        "One-shot retry with a safe default",
        "For the smallest first-run path: STACK_PROFILE=core ./scripts/launch_self_host.sh",
        "Check current port owners and config: ./scripts/doctor.sh",
        "key.startswith(\"export \")",
        "secret_values_included",
        "raw_env_values_included",
    )
    return {
        "script": "scripts/check_env.py",
        "schema": "env-check-result-v1",
        "blocks": [
            "weak_or_placeholder_secret",
            "invalid_langfuse_encryption_key",
            "missing_database_url",
            "invalid_port_value",
            "duplicate_host_port_value",
            "unsupported_stack_profile",
        ],
        "privacy": {
            "secret_values_included": False,
            "raw_env_values_included": False,
            "local_absolute_paths_included": False,
        },
        "supports_export_style_env_lines": True,
    }


def verify_cli_first_run_guidance(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/study_anything_cli.py",
        "session_next_steps",
        "answer --session",
        "teach --session",
        "resolve --session",
        "--decision approve",
        "agent-set-default",
        "Start a zero-key demo",
        "memory.retrieve",
        "defaults_configured",
        "Test it: python3 scripts/study_anything_cli.py agent-test",
        "select_agent_provider_for_test",
        "provider_id_optional",
        "AUTO_AGENT_MODE_REQUIRED_CAPABILITIES",
        "resolve_start_agent_mode",
        "warn_auto_agent_fallback",
        "auto Agent mode fell back to the zero-key demo",
        "missing defaults:",
        "agent-set-default {provider_ids[0]}",
        "This is now the default when no --capability is passed.",
        "add_agent_mode_argument",
        "choices=[\"auto\", \"demo\", \"configured\"]",
        "No Agent provider is configured yet.",
        "Multiple Agent providers exist and no default provider is configured.",
        "is_agent_configuration_hitl",
        "Resume after fixing Agent setup",
        "did not respond before the CLI timeout",
        "except (TimeoutError, OSError) as exc",
        "agent-eval-report --session",
        "obsidian-export --session",
        "SECRET_QUERY_KEYS",
        "access_token",
        "authorization",
        "bearer",
        "clientsecret",
        "cookie",
        "normalise_session_output_or_id_arg",
        "Print a compact session summary. When SESSION_ID is provided",
        "Missing session id. Pass SESSION_ID after the command, --session SESSION_ID, or --session-id SESSION_ID.",
        "read_text_input_file",
        "Cannot read {option}",
        "Save it as UTF-8 or paste with {inline_option}",
        "Cannot read JSON file",
        "write_output_file",
        "Cannot write {description}",
        "avoid using a file as a parent directory",
        "write_json_output_file",
        "decode_api_json_response",
        "_format_api_decode_failure",
        "response was not valid JSON",
        "--api-base points to the wrong service",
        "require_json_object",
        "require_json_list",
        "require_string_field",
        "missing required field:",
        "the API and CLI versions are mismatched",
        "require_unanswered_quiz",
        "missing required unanswered quiz item with item_id",
        "Session response",
        "Demo session response",
        "Lesson run response",
        "Obsidian export response",
        "Second-brain handoff response",
        "parse_json_object_option",
        "Cannot parse {option} as a JSON object",
        "Wrap inline JSON in single quotes",
        "For larger payloads, use {file_option} path/to/input.json",
    )
    return {
        "script": "scripts/study_anything_cli.py",
        "copyable_next_steps": True,
        "supports_named_session_aliases": ["--session", "--session-id"],
        "covers": [
            "quiz_answer",
            "teaching_layer",
            "hitl_resolution",
            "agent_default_setup",
            "agent_mode_auto_routing",
            "partial_agent_defaults_warning",
            "session_output_or_id_alias",
            "api_unreachable_recovery",
            "file_input_output_recovery",
            "non_json_api_response_recovery",
            "api_response_shape_recovery",
            "combo_session_shape_recovery",
            "export_response_shape_recovery",
            "inline_json_option_recovery",
            "mastery_check",
            "agent_eval_report",
            "obsidian_export",
        ],
    }


def verify_agent_endpoint_normalization(root: Path) -> dict[str, Any]:
    core_path = root / "apps/api/study_anything/core/agent_registry.py"
    core_available = core_path.exists()
    if core_available:
        assert_contains(
            root,
            "apps/api/study_anything/core/agent_registry.py",
            "normalise_http_agent_endpoint",
            "127.0.0.1:8787",
            "/health",
            "/invoke",
            "_remove_secret_query_params",
        )
    for path in [
        "scripts/study_anything_cli.py",
        "scripts/verify_mock_http_agent_flow.py",
        "scripts/verify_agent_eval_flow.py",
    ]:
        assert_contains(root, path, "normalise_http_agent_endpoint")
    assert_contains(
        root,
        "scripts/verify_mock_http_agent_flow.py",
        "STUDY_ANYTHING_TEST_AGENT_ENDPOINT",
    )
    assert_contains(
        root,
        "scripts/verify_external_adoption.py",
        "AGENT_ENDPOINT=http://127.0.0.1:8787/invoke",
        "AGENT_ENDPOINT=http://mock-http-agent:8787/invoke",
        "format_cli_failure",
        "redact_diagnostic",
        "--allow-localhost-block-report",
    )
    assert_contains(
        root,
        "scripts/verify_external_agent_adapter_hardening.py",
        "format_cli_failure",
        "redact_diagnostic",
        "--allow-localhost-block-report",
        "python3 scripts/diagnose_adoption.py",
    )
    release_checklist = assert_contains(
        root,
        "docs/release-checklist.md",
        "AGENT_ENDPOINT=<mock-agent-endpoint>/invoke",
        "AGENT_ENDPOINT=<compose-mock-agent-endpoint>/invoke",
    )
    if "STUDY_ANYTHING_TEST_AGENT_ENDPOINT" in release_checklist:
        raise DeploymentHardeningError(
            "docs/release-checklist.md must use AGENT_ENDPOINT, not the legacy "
            "STUDY_ANYTHING_TEST_AGENT_ENDPOINT alias."
        )
    return {
        "core": "apps/api/study_anything/core/agent_registry.py" if core_available else None,
        "normalizes": [
            "gateway_root",
            "localhost_without_scheme",
            "health_endpoint",
            *(
                ["legacy_saved_provider_root"]
                if core_available
                else ["pack_script_entrypoints"]
            ),
        ],
        "preserves": ["custom_invoke_paths", "non_secret_query_parameters"],
        "rejects": ["inline_credentials", "secret_query_parameters"],
        "redacts": ["external_adoption_cli_failures", "external_agent_adapter_cli_failures"],
        "script_entrypoints": [
            "scripts/study_anything_cli.py",
            "scripts/verify_mock_http_agent_flow.py",
            "scripts/verify_agent_eval_flow.py",
            "scripts/verify_external_adoption.py",
            "scripts/verify_external_agent_adapter_hardening.py",
        ],
        "compatibility_aliases": ["STUDY_ANYTHING_TEST_AGENT_ENDPOINT"],
    }


def verify_release_check_blocked_reports(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/release_check.sh",
        "collect_localhost_block_reports",
        "write_blocked_report",
        "write_contract_only_report",
        "write_blocked_report_readme",
        "cleanup_successful_blocked_reports",
        "cleared stale localhost-blocked reports",
        "--clear-release-blocked-reports",
        "After inspecting this local report directory",
        "display_python_bin",
        'printf "Using Python runtime: %s\\n" "$(display_python_bin)"',
        "display_path",
        "STUDY_ANYTHING_RELEASE_BLOCKED_REPORT_DIR",
        "data/release-blocked-reports",
        "external-adoption.localhost-blocked",
        "agent-gateway-hardening.localhost-blocked",
        "external-agent-adapter-hardening.localhost-blocked",
        "openai-compatible-gateway.contract-only",
        "agent-gateway-hardening.contract-only",
        "external-agent-adapter-hardening.contract-only",
        "release-contract-only-report-v1",
        "This release gate remains strict and will exit non-zero here.",
        "*.contract-only.json",
        "ignored data/",
        "--allow-localhost-block-report",
    )
    return {
        "script": "scripts/release_check.sh",
        "strict_failure_preserved": True,
        "default_report_dir": "data/release-blocked-reports",
        "writes_local_readme": True,
        "clears_default_reports_on_success": True,
        "automatic_localhost_blocked_reports": [
            "external-adoption.localhost-blocked.json",
            "agent-gateway-hardening.localhost-blocked.json",
            "external-agent-adapter-hardening.localhost-blocked.json",
            "openai-compatible-gateway.contract-only.json",
            "agent-gateway-hardening.contract-only.json",
            "external-agent-adapter-hardening.contract-only.json",
            "README.txt",
        ],
        "contract_only_reports_replace_runtime_gates": False,
    }


def verify_published_image_smoke(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/verify_published_image_launch.py",
        RELEASE_VERSION,
        "blocked_by_local_ghcr_pull",
        "fallback_acceptance",
        "linux/amd64",
        "linux/arm64",
        "--allow-pull-timeout-report",
        "--skip-pull",
        "verify_full_api_flow.py",
    )
    return {
        "script": "scripts/verify_published_image_launch.py",
        "schema_when_pull_blocks": "blocked_by_local_ghcr_pull",
        "required_platforms": ["linux/amd64", "linux/arm64"],
        "fallback_is_acceptance_when_ci_manifest_and_release_check_pass": True,
    }


def verify_clean_clone(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/verify_clean_clone_adoption.py",
        "run_skill_mode_demo",
        "gateway_dry_run",
        "teaching_layers",
        "agent_audit_eval",
        "promptfoo",
        "dependency_failure_excerpt",
        "sanitize_json_value",
        "SECRET_JSON_KEYS",
        "REDACTION_SELF_CHECK_MARKERS",
        "redact_diagnostic",
        "<temp-path>",
    )
    return {
        "script": "scripts/verify_clean_clone_adoption.py",
        "default_runtime": "skill-mode",
        "checks": [
            "clean_clone",
            "env_generation",
            "skill_mode_demo",
            "gateway_dry_run",
            "teaching_layers",
            "agent_audit_eval",
        ],
    }


def verify_skill_mode_demo_script(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/run_skill_mode_demo.sh",
        "print_step_specific_hint",
        "Agent provider test failed",
        "user-owned Agent exit is not ready",
        "long-running process",
        "terminal 2",
        "terminal 1",
        "AGENT_GATEWAY_MODE=dry_run",
        "print_contract_only_recovery_hint",
        "verify_openai_compatible_gateway.py --contract-only",
        "verify_agent_gateway_hardening.py --contract-only",
        "verify_external_agent_adapter_hardening.py --contract-only",
        "agent-add-http --set-default",
    )
    return {
        "script": "scripts/run_skill_mode_demo.sh",
        "agent_gateway_failure_mentions_two_terminals": True,
        "socket_blocked_contract_only_recovery": True,
    }


def verify_compose(root: Path) -> dict[str, Any]:
    base = assert_contains(root, "infra/compose/docker-compose.yml", "api:", "app-postgres:")
    images = assert_contains(
        root,
        "infra/compose/docker-compose.images.yml",
        "STUDY_ANYTHING_API_IMAGE",
        "ghcr.io/jzvcpe-goat/study-anything/api",
    )
    if "build:" not in base:
        raise DeploymentHardeningError("Base compose file should retain source build config.")
    if "image:" not in images:
        raise DeploymentHardeningError("Published-image compose override must declare image.")
    return {
        "source_compose": "infra/compose/docker-compose.yml",
        "published_image_override": "infra/compose/docker-compose.images.yml",
        "source_build_and_published_image_paths_are_separate": True,
    }


def verify_docs(root: Path) -> dict[str, Any]:
    docs = {
        "README.md": [
            RELEASE_VERSION,
            "USE_PUBLISHED_IMAGES=true",
            "verify_published_image_launch.py",
            "non-ASCII",
        ],
        "docs/self-hosting.md": [
            RELEASE_VERSION,
            "Skill Mode",
            "USE_PUBLISHED_IMAGES=true",
            "PULL_PUBLISHED_IMAGES=false",
            "non-ASCII",
        ],
        "docs/adoption.md": [
            RELEASE_VERSION,
            "clean-clone",
            "published-image",
            "allow-pull-timeout-report",
        ],
        "docs/github-launch.md": [
            RELEASE_VERSION,
            "docker manifest inspect",
            "verify_published_image_launch.py",
            "allow-pull-timeout-report",
        ],
        "docs/use-with-kimi.md": [
            "study_anything_deployment_guide",
            "Skill Mode",
            "published",
        ],
        "docs/getting-started.md": [
            "START_HERE.command",
            "./scripts/start_here.sh",
            "--keep-running",
            "--check-only",
            "SESSION_ID",
            "AGENT_GATEWAY_MODE=dry_run",
            "diagnose_adoption.py",
            "不要把以下内容贴到公开 issue",
        ],
        "QUICKSTART.md": [
            "START_HERE.command",
            "./scripts/start_here.sh",
            "Done. You have proved the local learning loop once.",
            "diagnose_adoption.py",
        ],
        "docs/skill-mode.md": [
            "零配置体验",
            "AGENT_GATEWAY_MODE=dry_run",
            "--agent-mode auto",
            "--agent-mode configured",
            "agent-add-http",
            "teach --session",
            "--session SESSION_ID",
        ],
        "skills/study-anything/SKILL.md": [
            "--agent-mode auto",
            "configured Agent automatically",
            "missing default capabilities",
            "--session SESSION_ID",
            "--agent-mode demo",
            "--agent-mode configured",
            "agent-test` after configuration",
        ],
        "docs/platform-agent-integrations.md": [
            "deployment guide",
            "published GHCR images",
            "diagnostics",
        ],
    }
    for path, needles in docs.items():
        text = assert_contains(root, path, *needles)
        if path == "skills/study-anything/SKILL.md" and (
            "Start real sessions with `--agent-mode configured`" in text
        ):
            raise DeploymentHardeningError(
                "skills/study-anything/SKILL.md must describe auto Agent routing, not require "
                "--agent-mode configured for every real session."
            )
    return {"checked_docs": sorted(docs), "operator_docs_are_copyable": True}


def verify_platform_packs(root: Path) -> dict[str, Any]:
    platforms: dict[str, Any] = {}
    for platform_id in PLATFORM_IDS:
        path = f"platform/packs/{platform_id}/pack.json"
        pack = read_json(require_file(root, path))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        source_commands = "\n".join(
            str(command) for command in pack.get("source_verification_commands", [])
        )
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        if REQUIRED_PACK_COMMAND not in commands:
            raise DeploymentHardeningError(f"{path} is missing deployment hardening command.")
        if REQUIRED_SOURCE_COMMAND not in source_commands:
            raise DeploymentHardeningError(f"{path} is missing source-only commercial readiness command.")
        if REQUIRED_EVIDENCE not in evidence:
            raise DeploymentHardeningError(f"{path} is missing deployment hardening evidence.")
        platforms[platform_id] = {
            "command_declared": True,
            "source_command_declared": True,
            "acceptance_evidence_declared": True,
        }
    return platforms


def verify_generated_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("version") != RELEASE_VERSION:
        raise DeploymentHardeningError("Generated adoption pack version drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    required = {
        "scripts/verify_deployment_hardening.py",
        "scripts/release_check.sh",
        "scripts/verify_api_smoke.sh",
        "platform/generated/study-anything-deployment-hardening.json",
        "docs/release-notes/v0.3.29-alpha.md",
    }
    missing = required - paths
    if missing:
        raise DeploymentHardeningError(f"Generated adoption pack missing deployment files: {sorted(missing)}")
    acceptance = manifest.get("acceptance") or {}
    must_verify = set(str(item) for item in acceptance.get("must_verify", []))
    if SCHEMA_VERSION not in must_verify:
        raise DeploymentHardeningError("Adoption pack must_verify missing deployment hardening schema.")
    local_dependency_report = verify_pack_local_python_dependencies(root, paths)
    command_report = verify_pack_local_verification_command_scripts(root, paths)
    return {
        "schema": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "deployment_assets_included": len(required),
        "python_scripts_checked": local_dependency_report["python_scripts_checked"],
        "pack_command_scripts_checked": command_report["pack_command_scripts_checked"],
        "pack_command_path_refs_checked": command_report["pack_command_path_refs_checked"],
        "local_python_dependencies_complete": True,
        "pack_verification_commands_reference_included_scripts": True,
        "pack_verification_commands_reference_included_paths": True,
    }


COMMAND_SCRIPT_PATTERN = re.compile(
    r"(?:(?:python3|python|\.venv/bin/python)\s+)?"
    r"((?:\./)?(?:scripts|platform/bootstrap)/[A-Za-z0-9_./-]+\.(?:py|sh))"
)
PACK_PATH_PREFIXES = (
    "docs/",
    "evals/",
    "fixtures/",
    "infra/",
    "platform/",
    "plugins/",
    "scripts/",
    "skills/",
)


def command_script_paths(command: str) -> set[str]:
    return {match.group(1).lstrip("./") for match in COMMAND_SCRIPT_PATTERN.finditer(command)}


def command_pack_path_refs(command: str) -> set[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    refs: set[str] = set()
    for token in tokens:
        normalized = token.strip().strip(",;").lstrip("./")
        if normalized.startswith(PACK_PATH_PREFIXES):
            refs.add(normalized)
    refs.update(command_script_paths(command))
    return refs


def pack_path_declared(paths: set[str], relative_path: str) -> bool:
    if relative_path in paths:
        return True
    prefix = relative_path.rstrip("/") + "/"
    return any(path.startswith(prefix) for path in paths)


def verify_pack_local_verification_command_scripts(root: Path, paths: set[str]) -> dict[str, Any]:
    missing: list[str] = []
    script_refs_checked = 0
    path_refs_checked = 0
    for platform_id in PLATFORM_IDS:
        pack = read_json(require_file(root, f"platform/packs/{platform_id}/pack.json"))
        commands = pack.get("local_verification_commands", [])
        if not isinstance(commands, list) or not commands:
            raise DeploymentHardeningError(f"{platform_id} pack must declare local_verification_commands.")
        for command in commands:
            command_text = str(command)
            for script_path in sorted(command_script_paths(command_text)):
                script_refs_checked += 1
            for relative_path in sorted(command_pack_path_refs(command_text)):
                path_refs_checked += 1
                if not pack_path_declared(paths, relative_path):
                    missing.append(f"{platform_id}: {relative_path} from {command_text}")
        for command in pack.get("source_verification_commands", []):
            if any(pack_path_declared(paths, script_path) for script_path in command_script_paths(str(command))):
                raise DeploymentHardeningError(
                    f"{platform_id} source_verification_commands should not duplicate pack-contained "
                    f"scripts: {command}"
                )
    if missing:
        raise DeploymentHardeningError(
            "Pack-local verification commands reference paths missing from the adoption pack: "
            + "; ".join(missing)
        )
    return {
        "pack_command_scripts_checked": script_refs_checked,
        "pack_command_path_refs_checked": path_refs_checked,
    }


def verify_pack_local_python_dependencies(root: Path, paths: set[str]) -> dict[str, Any]:
    script_modules = {path.stem for path in safe_relative(root, "scripts").glob("*.py")}
    source_script_modules = {path.stem for path in (ROOT / "scripts").glob("*.py")}
    known_local_modules = script_modules | source_script_modules
    missing: list[str] = []
    checked = 0
    for path_str in sorted(path for path in paths if path.startswith("scripts/") and path.endswith(".py")):
        path = safe_relative(root, path_str)
        if not path.is_file():
            continue
        checked += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            raise DeploymentHardeningError(f"Cannot parse packed Python script {path_str}: {exc}") from exc
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".", 1)[0])
        for module in sorted(imports & known_local_modules):
            dependency = f"scripts/{module}.py"
            if dependency != path_str and dependency not in paths:
                missing.append(f"{path_str} imports {dependency}")
    if missing:
        raise DeploymentHardeningError(
            "Generated adoption pack is missing local Python dependencies: "
            + "; ".join(missing)
        )
    return {"python_scripts_checked": checked}


def verify_submission(root: Path) -> dict[str, Any]:
    submission = read_json(require_file(root, "platform/ecosystem-submission.json"))
    if submission.get("version") != RELEASE_VERSION:
        raise DeploymentHardeningError("Ecosystem submission version drifted.")
    shared_assets = set(str(asset) for asset in submission.get("shared_assets", []))
    required_assets = {
        "scripts/verify_deployment_hardening.py",
        "platform/generated/study-anything-deployment-hardening.json",
        "docs/self-hosting.md",
    }
    missing_assets = required_assets - shared_assets
    if missing_assets:
        raise DeploymentHardeningError(f"Ecosystem submission missing assets: {sorted(missing_assets)}")
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(command) for command in acceptance.get("minimum_commands", []))
    if REQUIRED_PACK_COMMAND not in command_text:
        raise DeploymentHardeningError("Ecosystem submission missing deployment hardening command.")
    must_prove = set(str(item) for item in acceptance.get("must_prove", []))
    if not any(SCHEMA_VERSION in item for item in must_prove):
        raise DeploymentHardeningError("Ecosystem submission must_prove missing deployment hardening.")
    return {
        "schema": submission.get("schema_version"),
        "version": submission.get("version"),
        "shared_assets_included": len(required_assets),
    }


def build_report(root: Path) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "checked_assets": verify_required_files(root),
        "deployment_modes": [
            {
                "id": "skill_mode",
                "recommended_for": "external platform agents and first-run users",
                "command": "./scripts/launch_skill_mode.sh",
                "source_build_required": False,
            },
            {
                "id": "published_image",
                "recommended_for": "Docker users who want to avoid local builds",
                "command": "USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh",
                "source_build_required": False,
            },
            {
                "id": "source_build",
                "recommended_for": "contributors changing the API image",
                "command": "./scripts/launch_self_host.sh",
                "source_build_required": True,
            },
        ],
        "launch_script": verify_launch_script(root),
        "stop_script": verify_stop_self_host_script(root),
        "recovery_env_parsers": verify_recovery_env_parsers(root),
        "skill_mode_launcher": verify_skill_mode_launcher(root),
        "verifier_api_base_resolution": verify_verifier_api_base_resolution(root),
        "env_check": verify_env_check(root),
        "doctor": verify_doctor(root),
        "diagnostics": verify_diagnostics(root),
        "cli_first_run_guidance": verify_cli_first_run_guidance(root),
        "beginner_launcher": verify_beginner_launcher(root),
        "agent_endpoint_normalization": verify_agent_endpoint_normalization(root),
        "release_check": verify_release_check_blocked_reports(root),
        "published_image_smoke": verify_published_image_smoke(root),
        "clean_clone_adoption": verify_clean_clone(root),
        "skill_mode_demo_script": verify_skill_mode_demo_script(root),
        "compose": verify_compose(root),
        "operator_docs": verify_docs(root),
        "platform_packs": verify_platform_packs(root),
        "adoption_pack": verify_generated_pack(root),
        "ecosystem_submission": verify_submission(root),
        "operator_commands": {
            "prepare_env": "python3 scripts/setup_env.py",
            "doctor": "./scripts/doctor.sh",
            "start_here": "./scripts/start_here.sh",
            "skill_mode": "./scripts/launch_skill_mode.sh",
            "skill_mode_demo": "./scripts/run_skill_mode_demo.sh",
            "published_image": f"USE_PUBLISHED_IMAGES=true STUDY_ANYTHING_IMAGE_TAG={RELEASE_VERSION} ./scripts/launch_self_host.sh",
            "published_image_cached": "USE_PUBLISHED_IMAGES=true PULL_PUBLISHED_IMAGES=false ./scripts/launch_self_host.sh",
            "source_build": "./scripts/launch_self_host.sh",
            "diagnose": "python3 scripts/diagnose_adoption.py",
            "manifest": f"docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:{RELEASE_VERSION}",
            "published_image_smoke": f"python3 scripts/verify_published_image_launch.py --tag {RELEASE_VERSION} --pull-timeout-seconds 180 --allow-pull-timeout-report",
            "clean_clone": "python3 scripts/verify_clean_clone_adoption.py --repo .",
        },
        "failure_classes": [
            "docker_missing_or_daemon_unreachable",
            "docker_socket_permission_denied",
            "docker_compose_missing",
            "docker_compose_up_failed",
            "invalid_env_port_value",
            "port_conflict",
            "non_ascii_source_build_path",
            "ghcr_manifest_unavailable",
            "published_image_pull_timeout",
            "api_health_timeout",
            "localhost_socket_permission_denied",
            "agent_endpoint_contains_secret",
            "agent_endpoint_unreachable",
            "agent_endpoint_unhealthy",
            "configuration_required",
            "agent_local_socket_permission_denied",
            "provider_status_blocked_by_localhost_socket",
            "provider_defaults_missing",
        ],
        "privacy_assertions": {
            "real_model_keys_stored_by_study_anything": False,
            "agent_endpoint_secrets_in_report": False,
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "browser_video_private_context_in_report": False,
            "report_is_redacted": True,
        },
    }
    assert_no_sensitive_text(dump_json(report))
    return report


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def check_report(path: Path, payload: dict[str, Any]) -> None:
    expected = dump_json(payload)
    if not path.exists():
        raise DeploymentHardeningError(f"Deployment hardening report is missing: {path}")
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        raise DeploymentHardeningError(
            f"Deployment hardening report is stale. Run {Path(__file__).name} --write."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--write", action="store_true", help="Write the generated report.")
    parser.add_argument("--check", action="store_true", help="Require the generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-deploy-hardening-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        report = build_report(root)

    output = Path(args.output)
    if args.write:
        write_report(output, report)
    if args.check:
        check_report(output, report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(format_cli_failure(exc), file=sys.stderr)
        sys.exit(1)
