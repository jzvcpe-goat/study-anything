from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = ROOT.parents[1]
SCRIPT = REPO / "scripts" / "verify_deployment_hardening.py"
PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
SPEC = importlib.util.spec_from_file_location("verify_deployment_hardening", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
deployment_hardening = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deployment_hardening)


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


class DeploymentHardeningTests(unittest.TestCase):
    def test_source_tree_report_covers_three_runtime_modes_and_fallback(self) -> None:
        completed = run_script()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "deployment-hardening-verification-v1")
        self.assertEqual(report["version"], "v0.3.29-alpha")
        self.assertEqual(report["status"], "pass")
        modes = {item["id"] for item in report["deployment_modes"]}
        self.assertEqual(modes, {"skill_mode", "published_image", "source_build"})
        self.assertTrue(
            report["published_image_smoke"][
                "fallback_is_acceptance_when_ci_manifest_and_release_check_pass"
            ]
        )
        self.assertEqual(
            set(report["published_image_smoke"]["required_platforms"]),
            {"linux/amd64", "linux/arm64"},
        )
        self.assertIn("docker_socket_permission_denied", report["failure_classes"])
        self.assertIn("localhost_socket_permission_denied", report["failure_classes"])
        self.assertIn("invalid_env_port_value", report["failure_classes"])
        self.assertIn("agent_local_socket_permission_denied", report["failure_classes"])
        self.assertIn("agent_endpoint_unhealthy", report["failure_classes"])
        self.assertIn("configuration_required", report["failure_classes"])
        self.assertIn("provider_status_blocked_by_localhost_socket", report["failure_classes"])
        self.assertIn("invalid_port_value", report["env_check"]["blocks"])
        self.assertIn("duplicate_host_port_value", report["env_check"]["blocks"])
        self.assertIn("unsupported_stack_profile", report["env_check"]["blocks"])
        self.assertTrue(report["launch_script"]["validates_duplicate_active_host_ports"])
        self.assertEqual(
            report["skill_mode_launcher"]["api_port_sources"],
            ["API_PORT", ".env API_PORT", "default 8000"],
        )
        self.assertTrue(report["skill_mode_launcher"]["environment_override_wins"])
        self.assertTrue(report["skill_mode_launcher"]["validates_api_port_before_start"])
        self.assertTrue(report["skill_mode_launcher"]["rejects_non_study_health_responders"])
        self.assertEqual(
            report["verifier_api_base_resolution"]["api_base_sources"],
            ["API_BASE", "STUDY_ANYTHING_API_BASE", ".env API_PORT", "default 8000"],
        )
        self.assertEqual(
            report["verifier_api_base_resolution"]["gateway_port_sources"],
            ["--port", "--reuse-running-gateway default 8787", "ephemeral verifier-owned port"],
        )
        self.assertGreaterEqual(report["verifier_api_base_resolution"]["script_count"], 10)
        self.assertFalse(report["env_check"]["privacy"]["secret_values_included"])
        self.assertEqual(report["operator_commands"]["skill_mode_demo"], "./scripts/run_skill_mode_demo.sh")
        self.assertTrue(report["launch_script"]["honors_env_file_api_port_after_launch"])
        self.assertTrue(report["launch_script"]["supports_export_style_env_lines"])
        self.assertTrue(report["stop_script"]["honors_custom_env_file"])
        self.assertTrue(report["stop_script"]["checks_docker_before_compose_down"])
        self.assertTrue(report["recovery_env_parsers"]["supports_export_style_env_lines"])
        self.assertTrue(report["recovery_env_parsers"]["redacts_backup_restore_cli_errors"])
        self.assertTrue(report["recovery_env_parsers"]["copyable_backup_restore_next_steps"])
        self.assertIn(
            "scripts/self_host_data.py",
            report["recovery_env_parsers"]["scripts"],
        )
        self.assertTrue(report["env_check"]["supports_export_style_env_lines"])
        self.assertEqual(report["operator_commands"]["start_here"], "./scripts/start_here.sh")
        self.assertEqual(report["beginner_launcher"]["default_mode"], "zero_key_disposable_demo")
        self.assertTrue(report["beginner_launcher"]["supports_foreground_skill_mode"])
        self.assertTrue(report["beginner_launcher"]["supports_no_socket_contract_checks"])
        self.assertTrue(
            report["skill_mode_demo_script"]["agent_gateway_failure_mentions_two_terminals"]
        )
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])
        self.assertTrue(report["cli_first_run_guidance"]["copyable_next_steps"])
        self.assertIn("--session", report["cli_first_run_guidance"]["supports_named_session_aliases"])
        self.assertIn("hitl_resolution", report["cli_first_run_guidance"]["covers"])
        self.assertIn("agent_default_setup", report["cli_first_run_guidance"]["covers"])
        self.assertIn("agent_mode_auto_routing", report["cli_first_run_guidance"]["covers"])
        self.assertIn("partial_agent_defaults_warning", report["cli_first_run_guidance"]["covers"])
        self.assertIn("session_output_or_id_alias", report["cli_first_run_guidance"]["covers"])
        self.assertIn("file_input_output_recovery", report["cli_first_run_guidance"]["covers"])
        self.assertIn("non_json_api_response_recovery", report["cli_first_run_guidance"]["covers"])
        self.assertIn("api_response_shape_recovery", report["cli_first_run_guidance"]["covers"])
        self.assertIn("combo_session_shape_recovery", report["cli_first_run_guidance"]["covers"])
        self.assertIn("export_response_shape_recovery", report["cli_first_run_guidance"]["covers"])
        self.assertIn("inline_json_option_recovery", report["cli_first_run_guidance"]["covers"])
        self.assertIn(
            "gateway_root",
            report["agent_endpoint_normalization"]["normalizes"],
        )
        self.assertIn(
            "legacy_saved_provider_root",
            report["agent_endpoint_normalization"]["normalizes"],
        )
        self.assertTrue(report["release_check"]["strict_failure_preserved"])
        self.assertTrue(report["release_check"]["clears_default_reports_on_success"])
        self.assertIn("release_blocked_reports", report["diagnostics"]["covers"])
        self.assertIn("release_blocked_report_cleanup", report["diagnostics"]["covers"])
        self.assertIn("api_health_wrong_service", report["diagnostics"]["covers"])
        self.assertIn("release_blocked_report_hint", report["doctor"]["checks"])
        self.assertIn("api_health_wrong_service", report["doctor"]["checks"])
        self.assertIn("agent_gateway_unhealthy", report["doctor"]["checks"])
        self.assertIn("agent_endpoint_contains_secret", report["doctor"]["checks"])
        self.assertIn("python_runtime", report["doctor"]["checks"])
        self.assertIn("release_blocked_contract_summary", report["doctor"]["checks"])
        self.assertIn(
            "external-adoption.localhost-blocked.json",
            report["release_check"]["automatic_localhost_blocked_reports"],
        )
        self.assertIn(
            "openai-compatible-gateway.contract-only.json",
            report["release_check"]["automatic_localhost_blocked_reports"],
        )
        self.assertFalse(report["release_check"]["contract_only_reports_replace_runtime_gates"])
        self.assertIn(
            "external_agent_adapter_cli_failures",
            report["agent_endpoint_normalization"]["redacts"],
        )
        self.assertIn(
            "scripts/verify_external_agent_adapter_hardening.py",
            report["agent_endpoint_normalization"]["script_entrypoints"],
        )
        self.assertIn("docs/skill-mode.md", report["operator_docs"]["checked_docs"])
        self.assertIn("docs/getting-started.md", report["operator_docs"]["checked_docs"])
        self.assertIn("skills/study-anything/SKILL.md", report["operator_docs"]["checked_docs"])

    def test_skill_mode_zero_config_gateway_path_uses_configured_agent(self) -> None:
        skill_mode = (REPO / "docs" / "skill-mode.md").read_text(encoding="utf-8")

        self.assertIn("零配置体验", skill_mode)
        self.assertIn("AGENT_GATEWAY_MODE=dry_run", skill_mode)
        self.assertIn("agent-add-http", skill_mode)
        self.assertIn("--agent-mode configured", skill_mode)
        self.assertIn("teach --session", skill_mode)
        self.assertIn("--session SESSION_ID", skill_mode)

    def test_repo_skill_uses_auto_agent_routing(self) -> None:
        skill = (REPO / "skills" / "study-anything" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("--agent-mode auto", skill)
        self.assertIn("configured Agent automatically", skill)
        self.assertIn("missing default capabilities", skill)
        self.assertIn("--session SESSION_ID", skill)
        self.assertIn("--agent-mode demo", skill)
        self.assertIn("--agent-mode configured", skill)
        self.assertNotIn("Start real sessions with `--agent-mode configured`", skill)

    def test_pack_report_validates_copy_ready_deployment_assets(self) -> None:
        completed = run_script("--pack", str(PACK))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "deployment-hardening-verification-v1")
        self.assertEqual(report["adoption_pack"]["version"], "v0.3.29-alpha")
        self.assertTrue(report["adoption_pack"]["local_python_dependencies_complete"])
        self.assertTrue(
            report["adoption_pack"]["pack_verification_commands_reference_included_scripts"]
        )
        self.assertTrue(report["adoption_pack"]["pack_verification_commands_reference_included_paths"])
        self.assertGreater(report["adoption_pack"]["python_scripts_checked"], 10)
        self.assertGreater(report["adoption_pack"]["pack_command_scripts_checked"], 100)
        self.assertGreater(report["adoption_pack"]["pack_command_path_refs_checked"], 140)
        checked_assets = report["checked_assets"]
        checked_paths = [item["path"] for item in checked_assets]
        self.assertEqual(checked_paths.count("manifest.json"), 1)
        manifest_asset = next(item for item in checked_assets if item["path"] == "manifest.json")
        self.assertEqual(
            manifest_asset["source_equivalent"],
            "platform/generated/study-anything-platform-adoption-pack.json",
        )
        bundle_asset = next(
            item
            for item in checked_assets
            if item["path"] == "platform/generated/study-anything-platform-bundle.json"
        )
        self.assertEqual(bundle_asset["status"], "source_only_not_in_pack")

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "scripts").mkdir()
            completed = run_script("--pack-root", str(root))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Required deployment asset is missing", completed.stderr)
        self.assertIn("Next steps:", completed.stderr)

    def test_cli_failure_formatter_is_actionable_and_redacted(self) -> None:
        message = deployment_hardening.format_cli_failure(
            RuntimeError(
                "deployment report failed at /private/tmp/study-anything/deploy.json "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            )
        )

        self.assertIn("verify_deployment_hardening failed", message)
        self.assertIn("Next steps:", message)
        self.assertIn("verify_deployment_hardening.py --write", message)
        self.assertIn("verify_deployment_hardening.py --check", message)
        self.assertIn("generate_platform_adoption_pack.py", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("docs/self-hosting.md", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/tmp", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)

    def test_skill_mode_dependency_install_failure_is_actionable(self) -> None:
        launch_text = (REPO / "scripts" / "launch_skill_mode.sh").read_text(encoding="utf-8")

        self.assertIn("print_skill_mode_ready_next_steps", launch_text)
        self.assertIn("study_anything_cli.py --api-base %s health", launch_text)
        self.assertIn("study_anything_cli.py --api-base %s demo", launch_text)
        self.assertIn("AGENT_GATEWAY_MODE=dry_run", launch_text)
        self.assertIn("agent-add-http --set-default", launch_text)
        self.assertIn("diagnose_adoption.py", launch_text)
        self.assertIn("Study Anything dependency installation failed.", launch_text)
        self.assertIn("import setuptools", launch_text)
        self.assertIn("retrying without build isolation", launch_text)
        self.assertIn("standard build isolation", launch_text)
        self.assertIn("--no-build-isolation", launch_text)
        self.assertIn("setuptools wheel", launch_text)
        self.assertIn("USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh", launch_text)
        self.assertIn("PIP_CACHE_DIR", launch_text)

    def test_skill_mode_python_failure_is_actionable(self) -> None:
        launch_text = (REPO / "scripts" / "launch_skill_mode.sh").read_text(encoding="utf-8")

        self.assertIn("print_python_missing_hint", launch_text)
        self.assertIn("print_python_version_hint", launch_text)
        self.assertIn("PYTHON_BIN=/path/to/python3.11", launch_text)
        self.assertIn("STUDY_ANYTHING_VENV=/path/to/.venv", launch_text)
        self.assertIn("USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh", launch_text)
        self.assertIn("diagnose_adoption.py", launch_text)

    def test_skill_mode_venv_creation_failure_is_actionable(self) -> None:
        launch_text = (REPO / "scripts" / "launch_skill_mode.sh").read_text(encoding="utf-8")

        self.assertIn("print_venv_creation_failure_hint", launch_text)
        self.assertIn("venv-create.log", launch_text)
        self.assertIn("python3.11-venv", launch_text)
        self.assertIn("PYTHON_BIN=/path/to/python3.11", launch_text)
        self.assertIn("STUDY_ANYTHING_VENV=/path/to/.venv", launch_text)
        self.assertIn("USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh", launch_text)
        self.assertIn("diagnose_adoption.py", launch_text)

    def test_skill_mode_bind_preflight_is_actionable(self) -> None:
        launch_text = (REPO / "scripts" / "launch_skill_mode.sh").read_text(encoding="utf-8")

        self.assertIn("check_bind_preflight", launch_text)
        self.assertIn("print_port_in_use_hint", launch_text)
        self.assertIn("print_contract_only_recovery_hint", launch_text)
        self.assertIn("cannot listen on", launch_text)
        self.assertIn("agent sandbox blocks localhost listening sockets", launch_text)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", launch_text)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", launch_text)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", launch_text)
        self.assertIn("sandbox evidence only", launch_text)
        self.assertIn("./scripts/stop_skill_mode.sh", launch_text)
        self.assertIn("lsof -nP -iTCP:%s -sTCP:LISTEN", launch_text)
        self.assertIn("API_PORT=8012", launch_text)
        self.assertIn("diagnose_adoption.py", launch_text)

    def test_skill_mode_unhealthy_existing_process_is_actionable(self) -> None:
        launch_text = (REPO / "scripts" / "launch_skill_mode.sh").read_text(encoding="utf-8")

        self.assertIn("print_unhealthy_existing_process_hint", launch_text)
        self.assertIn("print_invalid_pid_file_hint", launch_text)
        self.assertIn("./scripts/stop_skill_mode.sh && ./scripts/launch_skill_mode.sh", launch_text)
        self.assertIn("tail -n 80", launch_text)
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", launch_text)
        self.assertIn("diagnose_adoption.py", launch_text)

    def test_stop_skill_mode_invalid_pid_is_actionable(self) -> None:
        stop_text = (REPO / "scripts" / "stop_skill_mode.sh").read_text(encoding="utf-8")

        self.assertIn("is_positive_pid", stop_text)
        self.assertIn("Removed invalid Skill Mode PID file", stop_text)
        self.assertIn("Invalid PID value was empty.", stop_text)

    def test_gateway_verifiers_have_dependency_recovery(self) -> None:
        verifier_paths = [
            REPO / "scripts" / "verify_agent_gateway_hardening.py",
            REPO / "scripts" / "verify_external_agent_adapter_hardening.py",
        ]
        for path in verifier_paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("./scripts/launch_skill_mode.sh", text)
            self.assertIn(".venv/bin/python", text)

    def test_external_agent_smoke_scripts_normalise_copy_pasted_endpoints(self) -> None:
        smoke_paths = [
            REPO / "scripts" / "verify_mock_http_agent_flow.py",
            REPO / "scripts" / "verify_agent_eval_flow.py",
        ]
        for path in smoke_paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("normalise_http_agent_endpoint", text)
            self.assertIn("http://127.0.0.1:8787/invoke", text)

        mock_flow_text = (REPO / "scripts" / "verify_mock_http_agent_flow.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("STUDY_ANYTHING_TEST_AGENT_ENDPOINT", mock_flow_text)

        adoption_text = (REPO / "scripts" / "verify_external_adoption.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("AGENT_ENDPOINT=http://127.0.0.1:8787/invoke", adoption_text)
        self.assertIn("AGENT_ENDPOINT=http://mock-http-agent:8787/invoke", adoption_text)
        self.assertIn("format_cli_failure", adoption_text)
        self.assertIn("redact_diagnostic", adoption_text)
        self.assertIn("--allow-localhost-block-report", adoption_text)

        adapter_text = (REPO / "scripts" / "verify_external_agent_adapter_hardening.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("format_cli_failure", adapter_text)
        self.assertIn("redact_diagnostic", adapter_text)
        self.assertIn("--allow-localhost-block-report", adapter_text)
        self.assertIn("python3 scripts/diagnose_adoption.py", adapter_text)

        release_checklist = (REPO / "docs" / "release-checklist.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("AGENT_ENDPOINT=<mock-agent-endpoint>/invoke", release_checklist)
        self.assertIn("AGENT_ENDPOINT=<compose-mock-agent-endpoint>/invoke", release_checklist)
        self.assertNotIn("STUDY_ANYTHING_TEST_AGENT_ENDPOINT", release_checklist)

    def test_agent_registry_normalises_direct_api_endpoint_registration(self) -> None:
        registry_text = (REPO / "apps/api/study_anything/core/agent_registry.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("normalise_http_agent_endpoint", registry_text)
        self.assertIn("gateway root", registry_text)
        self.assertIn("endpoint = f\"http://{endpoint}\"", registry_text)
        self.assertIn("path.rstrip(\"/\") == \"/health\"", registry_text)
        self.assertIn("path = \"/invoke\"", registry_text)
        self.assertIn("_remove_secret_query_params", registry_text)

    def test_release_check_localhost_sensitive_gates_are_actionable(self) -> None:
        release_text = (REPO / "scripts" / "release_check.sh").read_text(encoding="utf-8")

        self.assertIn("run_localhost_sensitive_gate", release_text)
        self.assertIn("print_localhost_gate_hint", release_text)
        self.assertIn("collect_localhost_block_reports", release_text)
        self.assertIn("write_blocked_report", release_text)
        self.assertIn("write_contract_only_report", release_text)
        self.assertIn("release-contract-only-report-v1", release_text)
        self.assertIn("redact_diagnostic", release_text)
        self.assertIn("https://[^/@[:space:]]*:[^/@[:space:]]*@", release_text)
        self.assertIn("[Aa]uthorization", release_text)
        self.assertIn("Bearer <redacted>", release_text)
        self.assertIn("run_redacted", release_text)
        self.assertIn("redact_file \"$gate_log\"", release_text)
        self.assertIn("run_redacted \"$python_bin\" scripts/check_env.py", release_text)
        self.assertIn("STUDY_ANYTHING_RELEASE_BLOCKED_REPORT_DIR", release_text)
        self.assertIn("data/release-blocked-reports", release_text)
        self.assertIn("write_blocked_report_readme", release_text)
        self.assertIn("cleanup_successful_blocked_reports", release_text)
        self.assertIn("cleared stale localhost-blocked reports", release_text)
        self.assertIn("--clear-release-blocked-reports", release_text)
        self.assertIn("After inspecting this local report directory", release_text)
        self.assertIn("display_python_bin", release_text)
        self.assertIn('printf "Using Python runtime: %s\\n" "$(display_python_bin)"', release_text)
        self.assertIn('$(display_python_bin) scripts/diagnose_adoption.py', release_text)
        self.assertIn("display_path", release_text)
        self.assertIn("ignored data/", release_text)
        self.assertIn("external-adoption.localhost-blocked", release_text)
        self.assertIn("agent-gateway-hardening.localhost-blocked", release_text)
        self.assertIn("external-agent-adapter-hardening.localhost-blocked", release_text)
        self.assertIn("openai-compatible-gateway.contract-only", release_text)
        self.assertIn("agent-gateway-hardening.contract-only", release_text)
        self.assertIn("external-agent-adapter-hardening.contract-only", release_text)
        self.assertIn("*.contract-only.json", release_text)
        self.assertIn("runtime_gate_replaced", release_text)
        self.assertIn("release_check.sh attempted to collect", release_text)
        self.assertIn("else\n    status=$?\n  fi", release_text)
        self.assertIn("--allow-localhost-block-report", release_text)
        self.assertIn("verify_external_adoption.py --pack", release_text)
        self.assertIn("verify_agent_gateway_hardening.py --allow-localhost-block-report", release_text)
        self.assertIn(
            "verify_external_agent_adapter_hardening.py --allow-localhost-block-report",
            release_text,
        )
        self.assertIn(
            "run_localhost_sensitive_gate openai_compatible_gateway",
            release_text,
        )
        self.assertIn("verify_openai_compatible_gateway.py --gateway-only || exit $?", release_text)
        self.assertIn("run_localhost_sensitive_gate agent_gateway_hardening", release_text)
        self.assertIn("verify_agent_gateway_hardening.py || exit $?", release_text)
        self.assertIn(
            "run_localhost_sensitive_gate external_agent_adapter_hardening",
            release_text,
        )
        self.assertIn("verify_external_agent_adapter_hardening.py || exit $?", release_text)
        self.assertIn("release gate remains strict", release_text.lower())

    def test_docker_socket_permission_failures_are_actionable(self) -> None:
        doctor_text = (REPO / "scripts" / "doctor.sh").read_text(encoding="utf-8")
        launch_text = (REPO / "scripts" / "launch_self_host.sh").read_text(encoding="utf-8")

        for text in [doctor_text, launch_text]:
            self.assertIn("docker socket is not accessible", text.lower())
            self.assertIn("launch_skill_mode.sh", text)
            self.assertIn("active Docker context", text)

        self.assertIn("check_python_runtime", doctor_text)
        self.assertIn("Python 3.11 or newer", doctor_text)
        self.assertIn("PYTHON_BIN=/path/to/python3.11", doctor_text)
        self.assertIn("Fastest local smoke", doctor_text)
        self.assertIn("Zero-key Agent gateway", doctor_text)
        self.assertIn("latest_release_blocked_report_dir", doctor_text)
        self.assertIn("release_report_python", doctor_text)
        self.assertIn("release_contract_report_summary", doctor_text)
        self.assertIn('ls -td "$report_root"/*/', doctor_text)
        self.assertIn("Release gate reminder", doctor_text)
        self.assertIn("release_check.sh left localhost-blocked reports", doctor_text)
        self.assertIn("Contract-only no-socket reports", doctor_text)
        self.assertIn("replaces runtime gate", doctor_text)
        self.assertIn("These reports prove sandbox-safe contracts only", doctor_text)
        self.assertIn("--clear-release-blocked-reports", doctor_text)
        self.assertIn("does not look like Study Anything", doctor_text)
        self.assertIn("not healthy yet", doctor_text)
        self.assertIn("AGENT_HTTP_GATEWAY_URL must not contain inline credentials", doctor_text)
        self.assertIn("Doctor found no blocking issues.", doctor_text)
        self.assertIn("Recommended next step", doctor_text)
        self.assertIn("Next steps:", launch_text)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:%s health", launch_text)
        self.assertIn("study_anything_cli.py --api-base http://127.0.0.1:%s demo", launch_text)
        self.assertIn("AGENT_GATEWAY_MODE=dry_run", launch_text)
        self.assertIn("agent-add-http --set-default", launch_text)
        self.assertIn("self_host_api_port", launch_text)
        self.assertIn("Docker command was not found in PATH.", launch_text)
        self.assertIn("Docker Compose v2 plugin is not available", launch_text)
        self.assertIn("print_docker_pull_failure_hint", launch_text)
        self.assertIn("print_compose_up_failure_hint", launch_text)
        self.assertIn("print_api_health_timeout_hint", launch_text)
        self.assertIn("validate_self_host_unique_active_ports", launch_text)
        self.assertIn("Duplicate host port", launch_text)
        self.assertIn("docker manifest inspect", launch_text)
        self.assertIn("PULL_PUBLISHED_IMAGES=false", launch_text)
        self.assertIn("logs --tail=200 api app-postgres", launch_text)
        self.assertIn("API_PORT=8012 ./scripts/launch_self_host.sh", launch_text)
        self.assertIn("docker compose version", launch_text)
        self.assertIn("diagnose_adoption.py", launch_text)

        demo_text = (REPO / "scripts" / "run_skill_mode_demo.sh").read_text(encoding="utf-8")
        self.assertIn("print_contract_only_recovery_hint", demo_text)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", demo_text)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", demo_text)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", demo_text)
        self.assertIn("These checks do not replace the runtime demo", demo_text)

    def test_cli_first_run_guidance_is_copyable(self) -> None:
        cli_text = (REPO / "scripts" / "study_anything_cli.py").read_text(encoding="utf-8")

        self.assertIn("session_next_steps", cli_text)
        self.assertIn("answer --session", cli_text)
        self.assertIn("teach --session", cli_text)
        self.assertIn("resolve --session", cli_text)
        self.assertIn("--decision approve", cli_text)
        self.assertIn("agent-set-default", cli_text)
        self.assertIn("Start a zero-key demo", cli_text)
        self.assertIn("memory.retrieve", cli_text)
        self.assertIn("defaults_configured", cli_text)
        self.assertIn("Test it: python3 scripts/study_anything_cli.py agent-test", cli_text)
        self.assertIn("CONTRACT_ONLY_RECOVERY_STEPS", cli_text)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", cli_text)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", cli_text)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", cli_text)
        self.assertIn("select_agent_provider_for_test", cli_text)
        self.assertIn("provider_id_optional", cli_text)
        self.assertIn("No Agent provider is configured yet.", cli_text)
        self.assertIn("Multiple Agent providers exist and no default provider is configured.", cli_text)
        self.assertIn("is_agent_configuration_hitl", cli_text)
        self.assertIn("Resume after fixing Agent setup", cli_text)
        self.assertIn("agent-eval-report --session", cli_text)
        self.assertIn("obsidian-export --session", cli_text)
        self.assertIn("--session-id SESSION_ID", cli_text)


if __name__ == "__main__":
    unittest.main()
