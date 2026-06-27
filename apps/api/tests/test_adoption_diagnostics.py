from __future__ import annotations

import importlib.util
import json
from io import StringIO
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from urllib.error import URLError
from unittest.mock import patch

from _path import ROOT as API_ROOT  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "diagnose_adoption",
    REPO_ROOT / "scripts" / "diagnose_adoption.py",
)
assert SPEC is not None and SPEC.loader is not None
diagnose = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnose)


class AdoptionDiagnosticsTests(unittest.TestCase):
    def test_default_image_tracks_release_tag(self) -> None:
        self.assertEqual(
            diagnose.DEFAULT_IMAGE,
            "ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
        )

    def test_env_file_check_reports_copyable_setup_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = diagnose.check_env_file(Path(tmp) / ".env")

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "env_missing")
        self.assertEqual(result["next_command"], "python3 scripts/setup_env.py")

    def test_env_file_check_validates_existing_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=development",
                        "POSTGRES_PASSWORD=local-strong-postgres",
                        "LANGFUSE_POSTGRES_PASSWORD=local-strong-langfuse-postgres",
                        "NEXTAUTH_SECRET=local-strong-nextauth",
                        "LANGFUSE_SALT=local-strong-salt",
                        "LANGFUSE_ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                        "CLICKHOUSE_PASSWORD=local-strong-clickhouse",
                        "MINIO_ROOT_PASSWORD=local-strong-minio",
                        "REDIS_AUTH=local-strong-redis",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = diagnose.check_env_file(env_file)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["code"], "env_present")
        self.assertEqual(result["env_check_schema"], "env-check-result-v1")
        self.assertEqual(result["warning_count"], 0)

    def test_env_file_check_reports_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "APP_ENV=production",
                        "NEXTAUTH_SECRET=change-me-nextauth-secret",
                        "LANGFUSE_ENCRYPTION_KEY=not-hex",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            result = diagnose.check_env_file(env_file)

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "env_check_failed")
        self.assertEqual(result["env_check_schema"], "env-check-result-v1")
        self.assertIn("weak_or_placeholder_secret", result["issue_codes"])
        self.assertIn("invalid_langfuse_encryption_key", result["issue_codes"])
        self.assertEqual(
            result["next_commands"][0],
            "python3 scripts/check_env.py --env <env-file> --strict",
        )
        self.assertEqual(
            result["next_commands"][1],
            "python3 scripts/setup_env.py --force --output <env-file>",
        )
        self.assertNotIn(str(env_file), json.dumps(result))

    def test_launch_configuration_reports_invalid_api_port_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "API_PORT=not-a-port\nSTACK_PROFILE=core\n",
                encoding="utf-8",
            )
            with patch.dict(diagnose.os.environ, {}, clear=True):
                result = diagnose.check_launch_configuration(env_file)

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "launch_configuration_invalid")
        self.assertIn("invalid_api_port", result["issue_codes"])
        self.assertEqual(result["api_port"], "not-a-port")
        self.assertIn("unset API_PORT", " ".join(result["next_commands"]))

    def test_launch_configuration_reports_unsupported_stack_profile_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("API_PORT=8000\nSTACK_PROFILE=core\n", encoding="utf-8")
            with patch.dict(diagnose.os.environ, {"STACK_PROFILE": "everything"}, clear=True):
                result = diagnose.check_launch_configuration(env_file)

        self.assertEqual(result["status"], "warning")
        self.assertIn("unsupported_stack_profile", result["issue_codes"])
        self.assertEqual(result["stack_profile"], "everything")
        self.assertIn("unset STACK_PROFILE", " ".join(result["next_commands"]))

    def test_launch_configuration_parses_exported_quoted_api_port_with_comment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                'export API_PORT="18080" # local override\nSTACK_PROFILE=core\n',
                encoding="utf-8",
            )
            with patch.dict(diagnose.os.environ, {}, clear=True):
                result = diagnose.check_launch_configuration(env_file)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["code"], "launch_configuration_ready")
        self.assertEqual(result["api_port"], "18080")

    def test_launch_configuration_ready_uses_defaults_when_env_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(diagnose.os.environ, {}, clear=True):
                result = diagnose.check_launch_configuration(Path(tmp) / ".env")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["code"], "launch_configuration_ready")
        self.assertEqual(result["api_port"], "8000")
        self.assertEqual(result["stack_profile"], "core")

    def test_main_uses_env_file_api_port_when_api_base_is_not_explicit(self) -> None:
        calls: dict[str, str] = {}

        def ok_check(name: str) -> dict[str, str]:
            return {"status": "ok", "name": name, "code": f"{name}_ok"}

        def fake_check_api(api_base: str) -> dict[str, str]:
            calls["api_base"] = api_base
            return ok_check("localhost_api")

        def fake_check_provider_capabilities(api_base: str, **_kwargs: object) -> dict[str, str]:
            calls["provider_api_base"] = api_base
            return ok_check("provider_capabilities")

        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text('export API_PORT="18080" # local override\n', encoding="utf-8")
            with (
                patch.object(
                    diagnose.sys,
                    "argv",
                    ["diagnose_adoption.py", "--env-file", str(env_file)],
                ),
                patch.dict(diagnose.os.environ, {}, clear=True),
                patch.object(diagnose, "check_env_file", return_value=ok_check("env_file")),
                patch.object(
                    diagnose,
                    "check_launch_configuration",
                    return_value=ok_check("launch_configuration"),
                ),
                patch.object(
                    diagnose,
                    "check_release_blocked_reports",
                    return_value=ok_check("release_blocked_reports"),
                ),
                patch.object(diagnose, "check_api", side_effect=fake_check_api),
                patch.object(diagnose, "check_docker", return_value=ok_check("docker_daemon")),
                patch.object(diagnose, "check_ghcr_manifest", return_value=ok_check("ghcr_manifest")),
                patch.object(diagnose, "check_agent_endpoint", return_value=ok_check("agent_endpoint")),
                patch.object(
                    diagnose,
                    "check_provider_capabilities",
                    side_effect=fake_check_provider_capabilities,
                ),
                patch("sys.stdout", new_callable=StringIO),
            ):
                diagnose.main()

        self.assertEqual(calls["api_base"], "http://127.0.0.1:18080")
        self.assertEqual(calls["provider_api_base"], "http://127.0.0.1:18080")

    def test_release_blocked_reports_absent_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = diagnose.check_release_blocked_reports(
                Path(tmp) / "data" / "release-blocked-reports"
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["code"], "release_blocked_reports_absent")

    def test_release_blocked_reports_present_are_actionable_and_redacted(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_root = root / "data" / "release-blocked-reports"
            older = report_root / "1"
            latest = report_root / "2"
            older.mkdir(parents=True)
            latest.mkdir()
            (older / "external-adoption.localhost-blocked.json").write_text(
                json.dumps(
                    {
                        "schema_version": "adoption-proof-v1",
                        "status": "blocked",
                        "classification": "old_report",
                    }
                ),
                encoding="utf-8",
            )
            (latest / "external-adoption.localhost-blocked.json").write_text(
                json.dumps(
                    {
                        "schema_version": "adoption-proof-v1",
                        "status": "blocked",
                        "classification": (
                            f"localhost_socket_blocked token={secret} "
                            "/Users/example/private"
                        ),
                    }
                ),
                encoding="utf-8",
            )
            (latest / "openai-compatible-gateway.contract-only.json").write_text(
                json.dumps(
                    {
                        "schema_version": "gateway-verification-v1",
                        "status": "ok",
                    }
                ),
                encoding="utf-8",
            )
            (latest / "README.txt").write_text("human guide", encoding="utf-8")

            with patch.object(diagnose, "ROOT", root):
                result = diagnose.check_release_blocked_reports(report_root)

        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "release_check_localhost_blocked_reports_present")
        self.assertEqual(result["latest_report_dir"], "data/release-blocked-reports/2")
        self.assertEqual(result["report_count"], 2)
        self.assertEqual(result["contract_only_report_count"], 1)
        self.assertIn("contract_only_ok", result["classifications"])
        self.assertIn(
            "openai-compatible-gateway:ok",
            result["contract_only_statuses"],
        )
        self.assertFalse(result["contract_only_reports_replace_runtime_gates"])
        self.assertTrue(
            any("localhost_socket_blocked" in item for item in result["classifications"])
        )
        self.assertIn("./scripts/release_check.sh", result["next_commands"][0])
        self.assertIn(
            "verify_openai_compatible_gateway.py --contract-only",
            " ".join(result["next_commands"]),
        )
        self.assertIn("--clear-release-blocked-reports", " ".join(result["next_commands"]))
        self.assertIn("successful run clears", result["fix"])
        self.assertIn("clears", result["message"])
        self.assertNotIn(secret, serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertIn("<local-path>", serialized)

    def test_release_blocked_reports_accepts_single_report_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "data" / "release-blocked-reports" / "123"
            report_dir.mkdir(parents=True)
            (report_dir / "external-adoption.localhost-blocked.json").write_text(
                json.dumps(
                    {
                        "schema_version": "adoption-proof-v1",
                        "status": "blocked",
                        "classification": "localhost_socket_blocked",
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(diagnose, "ROOT", root):
                result = diagnose.check_release_blocked_reports(report_dir)

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "release_check_localhost_blocked_reports_present")
        self.assertEqual(result["report_root"], "data/release-blocked-reports/123")
        self.assertEqual(result["report_root_mode"], "single_report_dir")
        self.assertEqual(result["latest_report_dir"], "data/release-blocked-reports/123")
        self.assertEqual(result["report_count"], 1)
        self.assertIn(
            "--release-report-dir data/release-blocked-reports/123 --clear-release-blocked-reports",
            " ".join(result["next_commands"]),
        )

    def test_release_blocked_reports_file_path_is_actionable_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_file = root / "data" / "release-blocked-reports" / "README.txt"
            report_file.parent.mkdir(parents=True)
            report_file.write_text("not a report directory", encoding="utf-8")

            with patch.object(diagnose, "ROOT", root):
                result = diagnose.check_release_blocked_reports(report_file)

        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "release_report_path_not_directory")
        self.assertEqual(result["report_root"], "data/release-blocked-reports/README.txt")
        self.assertIn("data/release-blocked-reports", result["fix"])
        self.assertIn("diagnose_adoption.py", " ".join(result["next_commands"]))
        self.assertNotIn(str(root), serialized)

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=[result],
        )
        recommended = diagnose.build_recommended_path(plan, [result])
        commands_text = "\n".join(recommended["copyable_commands"])
        self.assertIn(
            "python3 scripts/diagnose_adoption.py --release-report-dir data/release-blocked-reports",
            commands_text,
        )
        self.assertEqual(
            recommended["terminal_steps"][0]["command"],
            "python3 scripts/diagnose_adoption.py --release-report-dir data/release-blocked-reports",
        )
        self.assertTrue(
            any("--release-report-dir points at a file" in note for note in recommended["operator_notes"])
        )

    def test_clear_release_blocked_reports_removes_default_dir_and_is_redacted(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_root = root / "data" / "release-blocked-reports"
            latest = report_root / "123"
            latest.mkdir(parents=True)
            (latest / "external-adoption.localhost-blocked.json").write_text(
                json.dumps(
                    {
                        "schema_version": "adoption-proof-v1",
                        "status": "blocked",
                        "classification": f"localhost_socket_blocked token={secret}",
                    }
                ),
                encoding="utf-8",
            )
            (latest / "README.txt").write_text(
                f"Inspect /Users/example/private and token={secret}",
                encoding="utf-8",
            )

            with patch.object(diagnose, "ROOT", root):
                result = diagnose.clear_release_blocked_reports(report_root)

        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["code"], "release_blocked_reports_cleared")
        self.assertTrue(result["cleared"])
        self.assertEqual(result["report_root"], "data/release-blocked-reports")
        self.assertEqual(result["removed_directory_count"], 2)
        self.assertEqual(result["removed_file_count"], 2)
        self.assertFalse(report_root.exists())
        self.assertEqual(result["next_command"], "./scripts/release_check.sh")
        self.assertNotIn(secret, serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertTrue(result["privacy"]["absolute_paths_returned"] is False)
        self.assertTrue(result["privacy"]["report_contents_returned"] is False)

    def test_clear_release_blocked_reports_absent_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_root = root / "data" / "release-blocked-reports"
            with patch.object(diagnose, "ROOT", root):
                result = diagnose.clear_release_blocked_reports(report_root)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["code"], "release_blocked_reports_absent")
        self.assertFalse(result["cleared"])

    def test_clear_release_blocked_reports_refuses_path_outside_repo_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            outside = Path(tmp) / "outside" / "release-blocked-reports"
            outside.mkdir(parents=True)
            (outside / "report.json").write_text(
                json.dumps({"classification": "localhost_socket_blocked"}),
                encoding="utf-8",
            )

            with patch.object(diagnose, "ROOT", root):
                result = diagnose.clear_release_blocked_reports(outside)
                outside_still_exists = outside.exists()

        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["code"], "unsafe_release_report_dir")
        self.assertTrue(outside_still_exists)
        self.assertNotIn(str(outside), serialized)
        self.assertTrue(result["privacy"]["absolute_paths_returned"] is False)

    def test_main_clear_release_blocked_reports_exits_before_runtime_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_root = root / "data" / "release-blocked-reports"
            (report_root / "123").mkdir(parents=True)
            with (
                patch.object(diagnose, "ROOT", root),
                patch.object(
                    diagnose.sys,
                    "argv",
                    ["diagnose_adoption.py", "--clear-release-blocked-reports"],
                ),
                patch.object(diagnose, "check_api") as check_api,
                patch("sys.stdout", new_callable=StringIO) as stdout,
            ):
                diagnose.main()

        check_api.assert_not_called()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["code"], "release_blocked_reports_cleared")

    def test_health_url_for_agent_invoke_endpoint(self) -> None:
        self.assertEqual(
            diagnose.health_url_for_agent("http://127.0.0.1:8787/invoke"),
            "http://127.0.0.1:8787/health",
        )

    def test_health_url_preserves_gateway_base_path(self) -> None:
        self.assertEqual(
            diagnose.health_url_for_agent("https://agent.example.test/study/invoke"),
            "https://agent.example.test/study/health",
        )

    def test_health_url_accepts_localhost_endpoint_without_scheme(self) -> None:
        self.assertEqual(
            diagnose.health_url_for_agent("127.0.0.1:8787/invoke"),
            "http://127.0.0.1:8787/health",
        )

    def test_agent_endpoint_with_inline_credentials_is_not_probed_or_leaked(self) -> None:
        with patch.object(diagnose, "request_json") as request_json:
            result = diagnose.check_agent_endpoint(
                "http://user:secret-password@127.0.0.1:8787/invoke"
            )

        serialized = json.dumps(result, sort_keys=True)
        request_json.assert_not_called()
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "agent_endpoint_contains_secret")
        self.assertFalse(result["privacy"]["endpoint_value_returned"])
        self.assertNotIn("secret-password", serialized)
        self.assertNotIn("user:secret", serialized)

    def test_agent_endpoint_with_secret_query_is_not_probed_or_leaked(self) -> None:
        with patch.object(diagnose, "request_json") as request_json:
            result = diagnose.check_agent_endpoint(
                "http://127.0.0.1:8787/invoke?api_key=sk-secret123456789"
            )

        serialized = json.dumps(result, sort_keys=True)
        request_json.assert_not_called()
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "agent_endpoint_contains_secret")
        self.assertFalse(result["privacy"]["endpoint_secrets_returned"])
        self.assertNotIn("sk-secret123456789", serialized)
        self.assertNotIn("api_key=", serialized)

    def test_sanitize_diagnostic_redacts_urls_bearer_and_temp_paths(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        diagnostic = diagnose.sanitize_diagnostic(
            "failed with Authorization: Bearer "
            f"{secret} at http://user:secret@example.test/v1?api_key={secret}&region=us "
            "while writing /private/tmp/study-anything/trace.log"
        )

        self.assertIn("Authorization: Bearer <redacted>", diagnostic)
        self.assertIn("http://<redacted>@example.test/v1?api_key=<redacted>&region=us", diagnostic)
        self.assertIn("<temp-path>", diagnostic)
        self.assertNotIn(secret, diagnostic)
        self.assertNotIn("user:secret", diagnostic)
        self.assertNotIn("/private/tmp", diagnostic)

    def test_sanitize_diagnostic_handles_log_punctuation_after_port(self) -> None:
        diagnostic = diagnose.sanitize_diagnostic(
            "Cannot reach http://user:secret@127.0.0.1:9. "
            "Authorization: Bearer sk-proj-abcdefghijklmnop123456"
        )

        self.assertIn("http://<redacted>@127.0.0.1", diagnostic)
        self.assertIn("Authorization: Bearer <redacted>", diagnostic)
        self.assertNotIn("user:secret", diagnostic)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", diagnostic)

    def test_agent_endpoint_configuration_error_returns_dry_run_recovery(self) -> None:
        with patch.object(
            diagnose,
            "request_json",
            return_value={
                "status": "error",
                "diagnostic_code": "configuration_required",
                "message": "AGENT_LLM_API_KEY is required.",
                "next_steps": ["Run with --dry-run for a zero-configuration demo."],
            },
        ):
            result = diagnose.check_agent_endpoint("http://127.0.0.1:8787/invoke")

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "configuration_required")
        self.assertIn("--dry-run", result["next_command"])
        self.assertEqual(result["next_steps"], ["Run with --dry-run for a zero-configuration demo."])

    def test_agent_endpoint_unhealthy_redacts_health_payload(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        with patch.object(
            diagnose,
            "request_json",
            return_value={
                "status": "error",
                "diagnostic_code": "configuration_required",
                "message": (
                    "upstream failed with Authorization: Bearer "
                    f"{secret} at http://user:secret@example.test/v1?token={secret} "
                    "while reading /private/tmp/study-anything/gateway.log"
                ),
                "next_steps": [
                    f"export AGENT_LLM_API_KEY={secret}",
                    "inspect /private/tmp/study-anything/gateway.log",
                ],
            },
        ):
            result = diagnose.check_agent_endpoint("http://127.0.0.1:8787/invoke")

        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "configuration_required")
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertIn("AGENT_LLM_API_KEY=<redacted>", serialized)
        self.assertIn("<temp-path>", serialized)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("user:secret", serialized)
        self.assertNotIn("/private/tmp", serialized)

    def test_docker_socket_permission_denied_has_specific_recovery(self) -> None:
        with patch.object(diagnose.shutil, "which", return_value="/usr/local/bin/docker"):
            with patch.object(
                diagnose,
                "run",
                return_value=CompletedProcess(
                    ["docker", "info"],
                    1,
                    stdout="",
                    stderr=(
                        "permission denied while trying to connect to the docker API "
                        "at unix:///Users/example/.docker/run/docker.sock"
                    ),
                ),
            ):
                result = diagnose.check_docker()

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "docker_socket_permission_denied")
        self.assertIn("Skill Mode", result["fix"])
        self.assertEqual(result["next_command"], "./scripts/launch_skill_mode.sh")
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("/Users/example", serialized)
        self.assertIn("<local-path>", serialized)

    def test_ghcr_manifest_failure_redacts_local_paths_bearer_urls_and_tokens(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        with patch.object(diagnose.shutil, "which", return_value="/usr/local/bin/docker"):
            with patch.object(
                diagnose,
                "run",
                return_value=CompletedProcess(
                    ["docker", "manifest", "inspect", diagnose.DEFAULT_IMAGE],
                    1,
                    stdout="",
                    stderr=(
                        "failed using config /Users/example/.docker/config.json "
                        f"Authorization: Bearer {secret} "
                        f"https://user:secret@example.test/v2?token={secret} "
                        "api_key=sk-secret123456789"
                    ),
                ),
            ):
                result = diagnose.check_ghcr_manifest(diagnose.DEFAULT_IMAGE, timeout=1)

        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "ghcr_manifest_unavailable")
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("sk-secret123456789", serialized)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("user:secret", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertIn("api_key=<redacted>", serialized)

    def test_localhost_api_socket_blocked_has_specific_recovery(self) -> None:
        with patch.object(
            diagnose,
            "request_json",
            side_effect=URLError(OSError(1, "Operation not permitted")),
        ):
            result = diagnose.check_api("http://127.0.0.1:8000")

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "localhost_socket_permission_denied")
        self.assertIn("normal terminal", result["fix"])
        self.assertEqual(result["next_command"], "./scripts/launch_skill_mode.sh")

    def test_localhost_api_permission_denied_has_specific_recovery(self) -> None:
        with patch.object(
            diagnose,
            "request_json",
            side_effect=URLError(OSError(13, "Permission denied")),
        ):
            result = diagnose.check_api("http://127.0.0.1:8000")

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "localhost_socket_permission_denied")
        self.assertIn("normal terminal", result["fix"])

    def test_localhost_api_wrong_service_is_actionable_and_redacted(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        with patch.object(
            diagnose,
            "request_json",
            return_value={
                "status": "ok",
                "service": "other-app",
                "token": secret,
                "path": "/Users/james/private/source.txt",
            },
        ):
            result = diagnose.check_api("http://127.0.0.1:18080")

        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "api_health_wrong_service")
        self.assertIn("does not look like Study Anything", result["message"])
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", result["next_commands"])
        self.assertIn("lsof -nP -iTCP:18080 -sTCP:LISTEN", result["next_commands"])
        self.assertTrue(result["privacy"]["health_excerpt_redacted"])
        self.assertFalse(result["privacy"]["raw_health_payload_returned"])
        self.assertNotIn(secret, serialized)
        self.assertNotIn("/Users/james", serialized)
        self.assertIn('"token":"<redacted>"', result["health_excerpt"])
        self.assertIn("<local-path>", serialized)

    def test_agent_local_socket_blocked_has_specific_recovery(self) -> None:
        with patch.object(
            diagnose,
            "request_json",
            side_effect=URLError(OSError(1, "Operation not permitted")),
        ):
            result = diagnose.check_agent_endpoint("http://127.0.0.1:8787/invoke")

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "agent_local_socket_permission_denied")
        self.assertIn("normal terminal", result["fix"])
        self.assertIn("--dry-run", result["next_command"])

    def test_provider_status_local_socket_blocked_has_specific_recovery(self) -> None:
        with patch.object(
            diagnose,
            "request_json",
            side_effect=URLError(OSError(1, "Operation not permitted")),
        ):
            result = diagnose.check_provider_capabilities(
                "http://127.0.0.1:8000",
                user_id="local-user",
                required_capabilities=["quiz.generate"],
            )

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "provider_status_blocked_by_localhost_socket")
        self.assertIn("normal terminal", result["fix"])
        self.assertEqual(result["next_command"], "./scripts/launch_skill_mode.sh")

    def test_provider_capability_check_reports_missing_defaults(self) -> None:
        status = {
            "defaults": {"quiz.generate": "provider-1"},
            "providers": [
                {
                    "provider_id": "provider-1",
                    "capabilities": ["quiz.generate"],
                }
            ],
        }

        result = diagnose.provider_capability_report(
            status,
            required_capabilities=["quiz.generate", "answer.grade"],
        )

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["missing_defaults"], ["answer.grade"])

    def test_recovery_plan_prefers_skill_mode_without_docker(self) -> None:
        checks = [
            {"status": "warning", "code": "docker_missing"},
            {"status": "warning", "code": "api_unreachable"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )

        self.assertEqual(plan["schema_version"], "adoption-diagnostic-plan-v1")
        self.assertEqual(
            plan["recommended_order"],
            ["prepare_env", "skill_mode_demo", "skill_mode", "api_smoke"],
        )
        self.assertIn("./scripts/launch_skill_mode.sh", plan["commands"]["skill_mode"])
        self.assertIn("./scripts/run_skill_mode_demo.sh", plan["commands"]["skill_mode_demo"])
        self.assertIn("v0.3.29-alpha", plan["commands"]["docker_published_image"])
        self.assertIn("verify_adoption_telemetry.py", plan["commands"]["adoption_telemetry"])

        recommended = diagnose.build_recommended_path(plan, checks)
        self.assertEqual(recommended["schema_version"], "adoption-recommended-path-v1")
        self.assertEqual(recommended["status"], "needs_attention")
        self.assertEqual(recommended["primary_command"], "python3 scripts/setup_env.py")
        self.assertIn("./scripts/run_skill_mode_demo.sh", recommended["copyable_commands"])
        self.assertIn("./scripts/launch_skill_mode.sh", recommended["copyable_commands"])
        self.assertIn("verify_full_api_flow.py", " ".join(recommended["copyable_commands"]))
        self.assertTrue(any("Skill Mode" in note for note in recommended["operator_notes"]))

    def test_recovery_plan_prefers_alternate_port_when_api_health_is_wrong_service(self) -> None:
        checks = [{"status": "warning", "code": "api_health_wrong_service"}]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:18080",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(
            plan["recommended_order"],
            ["alternate_api_port_skill_mode", "doctor", "diagnose"],
        )
        self.assertEqual(
            recommended["primary_command"],
            "API_PORT=8012 ./scripts/launch_skill_mode.sh",
        )
        self.assertIn("./scripts/doctor.sh", recommended["copyable_commands"])
        self.assertTrue(any("not Study Anything" in note for note in recommended["operator_notes"]))

    def test_recovery_plan_prefers_normal_terminal_when_local_socket_is_blocked(self) -> None:
        checks = [
            {"status": "warning", "code": "localhost_socket_permission_denied"},
            {"status": "warning", "code": "provider_status_blocked_by_localhost_socket"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )

        self.assertEqual(
            plan["recommended_order"],
            [
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
            ],
        )
        self.assertTrue(plan["environment"]["normal_terminal_required"])
        self.assertIn("normal terminal", plan["commands"]["normal_terminal"])

        recommended = diagnose.build_recommended_path(plan, checks)
        self.assertEqual(
            recommended["primary_command"],
            "python3 scripts/verify_openai_compatible_gateway.py --contract-only",
        )
        self.assertNotIn("normal_terminal", recommended["copyable_commands"])
        self.assertIn(
            "verify_external_agent_adapter_hardening.py --contract-only",
            " ".join(recommended["copyable_commands"]),
        )
        self.assertIn("./scripts/run_skill_mode_demo.sh", recommended["copyable_commands"])
        self.assertIn("openai_compatible_agent_gateway.py", " ".join(recommended["copyable_commands"]))
        self.assertTrue(
            any(
                "sandbox evidence" in step["description"]
                for step in recommended["terminal_steps"]
                if "--contract-only" in step["command"]
            )
        )
        self.assertIn("terminal_2", {step["terminal"] for step in recommended["terminal_steps"]})
        self.assertTrue(
            any("long-running process" in note for note in recommended["operator_notes"])
        )
        self.assertTrue(any("contract-only checks" in note for note in recommended["operator_notes"]))
        self.assertTrue(any("normal terminal" in note for note in recommended["operator_notes"]))

    def test_recommended_path_skips_setup_when_env_already_exists(self) -> None:
        checks = [
            {"status": "ok", "code": "env_present"},
            {"status": "warning", "code": "localhost_socket_permission_denied"},
            {"status": "warning", "code": "provider_status_blocked_by_localhost_socket"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(
            recommended["primary_command"],
            "python3 scripts/verify_openai_compatible_gateway.py --contract-only",
        )
        self.assertNotIn("python3 scripts/setup_env.py", recommended["copyable_commands"])
        self.assertIn("verify_platform_agent_tools.py", " ".join(recommended["copyable_commands"]))
        self.assertEqual(
            recommended["terminal_steps"][0]["command"],
            "python3 scripts/verify_openai_compatible_gateway.py --contract-only",
        )
        self.assertTrue(
            any(
                step["terminal"] == "terminal_2" and "gateway" in step["description"].lower()
                for step in recommended["terminal_steps"]
            )
        )
        self.assertTrue(any(".env already exists" in note for note in recommended["operator_notes"]))

    def test_recovery_plan_prefers_release_check_when_blocked_reports_exist(self) -> None:
        checks = [
            {
                "status": "warning",
                "code": "release_check_localhost_blocked_reports_present",
                "contract_only_statuses": [
                    "agent-gateway-hardening:pass",
                    "external-agent-adapter-hardening:pass",
                    "openai-compatible-gateway:ok",
                ],
                "next_commands": [
                    "./scripts/release_check.sh",
                    "python3 scripts/verify_openai_compatible_gateway.py --contract-only",
                    "python3 scripts/verify_agent_gateway_hardening.py --contract-only",
                    "python3 scripts/verify_external_agent_adapter_hardening.py --contract-only",
                    "STUDY_ANYTHING_RELEASE_BLOCKED_REPORT_DIR=data/release-blocked-reports/123 ./scripts/release_check.sh",
                    "python3 scripts/diagnose_adoption.py --clear-release-blocked-reports",
                    "python3 scripts/diagnose_adoption.py",
                ],
            }
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(
            plan["recommended_order"],
            ["normal_terminal", "release_check", "clear_release_blocked_reports", "diagnose"],
        )
        self.assertTrue(plan["environment"]["normal_terminal_required"])
        self.assertEqual(recommended["primary_command"], "./scripts/release_check.sh")
        self.assertEqual(recommended["terminal_steps"][0]["command"], "./scripts/release_check.sh")
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", " ".join(recommended["copyable_commands"]))
        self.assertTrue(
            any(
                "not release verification" in step["description"]
                for step in recommended["terminal_steps"]
                if "--contract-only" in step["command"]
            )
        )
        self.assertIn("--clear-release-blocked-reports", " ".join(recommended["copyable_commands"]))
        self.assertNotIn("openai_compatible_agent_gateway.py", " ".join(recommended["copyable_commands"]))
        self.assertTrue(any("release gate" in note for note in recommended["operator_notes"]))
        self.assertTrue(any("No-socket contract reports found" in note for note in recommended["operator_notes"]))
        self.assertTrue(any("cleanup is not release verification" in note for note in recommended["operator_notes"]))

    def test_recommended_path_uses_specific_release_report_cleanup_command(self) -> None:
        checks = [
            {
                "status": "warning",
                "code": "release_check_localhost_blocked_reports_present",
                "next_commands": [
                    "./scripts/release_check.sh",
                    (
                        "python3 scripts/diagnose_adoption.py --release-report-dir "
                        "data/release-blocked-reports/123 --clear-release-blocked-reports"
                    ),
                ],
            }
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        commands_text = "\n".join(recommended["copyable_commands"])
        self.assertIn(
            "--release-report-dir data/release-blocked-reports/123 --clear-release-blocked-reports",
            commands_text,
        )
        self.assertIn(
            "data/release-blocked-reports/123 --clear-release-blocked-reports",
            "\n".join(step["command"] for step in recommended["terminal_steps"]),
        )
        self.assertEqual(
            len({step["command"] for step in recommended["terminal_steps"]}),
            len(recommended["terminal_steps"]),
        )
        self.assertNotIn(
            "python3 scripts/diagnose_adoption.py --clear-release-blocked-reports\n",
            commands_text + "\n",
        )

    def test_recovery_plan_prefers_launch_configuration_fix(self) -> None:
        checks = [
            {
                "status": "warning",
                "code": "launch_configuration_invalid",
                "issue_codes": ["invalid_api_port"],
            }
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(plan["failed_issue_codes"], ["invalid_api_port"])
        self.assertEqual(
            plan["recommended_order"],
            ["reset_api_port_skill_mode", "alternate_api_port_skill_mode", "doctor"],
        )
        self.assertEqual(
            recommended["primary_command"],
            "unset API_PORT && ./scripts/launch_skill_mode.sh",
        )
        self.assertIn("API_PORT=8012 ./scripts/launch_skill_mode.sh", recommended["copyable_commands"])
        self.assertTrue(
            any("Fix launch configuration" in note for note in recommended["operator_notes"])
        )

    def test_recovery_plan_prefers_launch_configuration_before_localhost_blocker(self) -> None:
        checks = [
            {
                "status": "warning",
                "code": "launch_configuration_invalid",
                "issue_codes": ["invalid_api_port", "unsupported_stack_profile"],
            },
            {"status": "warning", "code": "localhost_socket_permission_denied"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(
            plan["recommended_order"],
            ["reset_api_port_skill_mode", "reset_stack_profile_self_host", "doctor"],
        )
        self.assertEqual(
            recommended["primary_command"],
            "unset API_PORT && ./scripts/launch_skill_mode.sh",
        )
        self.assertIn(
            "unset STACK_PROFILE && ./scripts/launch_self_host.sh",
            recommended["copyable_commands"],
        )

    def test_recovery_plan_prefers_env_validation_before_runtime(self) -> None:
        checks = [
            {
                "status": "warning",
                "code": "env_check_failed",
                "issue_codes": ["invalid_langfuse_encryption_key"],
                "next_commands": [
                    "python3 scripts/check_env.py --env <env-file> --strict",
                    "python3 scripts/setup_env.py --force --output <env-file>",
                ],
            },
            {"status": "warning", "code": "api_unreachable"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(plan["recommended_order"], ["validate_env", "regenerate_env", "doctor"])
        self.assertEqual(
            recommended["primary_command"],
            "python3 scripts/check_env.py --env <env-file> --strict",
        )
        self.assertIn(
            "python3 scripts/setup_env.py --force --output <env-file>",
            recommended["copyable_commands"],
        )
        self.assertTrue(any("failed validation" in note for note in recommended["operator_notes"]))

    def test_recovery_plan_prefers_env_validation_before_localhost_blocker(self) -> None:
        checks = [
            {
                "status": "warning",
                "code": "env_check_failed",
                "issue_codes": ["weak_or_placeholder_secret"],
                "next_commands": [
                    "python3 scripts/check_env.py --env <env-file> --strict",
                    "python3 scripts/setup_env.py --force --output <env-file>",
                ],
            },
            {"status": "warning", "code": "localhost_socket_permission_denied"},
            {"status": "warning", "code": "agent_local_socket_permission_denied"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(plan["recommended_order"], ["validate_env", "regenerate_env", "doctor"])
        self.assertEqual(
            recommended["primary_command"],
            "python3 scripts/check_env.py --env <env-file> --strict",
        )
        self.assertNotIn("./scripts/run_skill_mode_demo.sh", recommended["copyable_commands"])
        self.assertTrue(plan["environment"]["normal_terminal_required"])
        self.assertTrue(any("normal terminal" in note for note in recommended["operator_notes"]))

    def test_recovery_plan_prefers_agent_endpoint_secret_fix(self) -> None:
        checks = [
            {"status": "ok", "code": "env_present"},
            {
                "status": "warning",
                "code": "agent_endpoint_contains_secret",
                "name": "agent_endpoint",
            },
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(
            plan["recommended_order"],
            ["agent_gateway_dry_run", "agent_register_local_gateway", "doctor"],
        )
        self.assertEqual(
            recommended["primary_command"],
            "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
        )
        self.assertIn(
            "python3 scripts/study_anything_cli.py agent-add-http --set-default",
            recommended["copyable_commands"],
        )
        self.assertTrue(any("Remove credentials" in note for note in recommended["operator_notes"]))

    def test_recovery_plan_prefers_agent_endpoint_unreachable_fix(self) -> None:
        checks = [
            {"status": "ok", "code": "env_present"},
            {"status": "warning", "code": "agent_endpoint_unreachable"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(
            plan["recommended_order"],
            ["agent_gateway_dry_run", "agent_register_local_gateway", "platform_tools_smoke"],
        )
        self.assertEqual(
            recommended["primary_command"],
            "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
        )
        self.assertIn(
            "python3 scripts/study_anything_cli.py agent-add-http --set-default",
            recommended["copyable_commands"],
        )
        self.assertIn("terminal_2", {step["terminal"] for step in recommended["terminal_steps"]})
        self.assertTrue(any("dry-run mode" in note for note in recommended["operator_notes"]))

    def test_recovery_plan_prefers_configuration_required_gateway_fix(self) -> None:
        checks = [
            {"status": "ok", "code": "env_present"},
            {"status": "warning", "code": "configuration_required"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(
            plan["recommended_order"],
            ["agent_gateway_dry_run", "agent_register_local_gateway", "platform_tools_smoke"],
        )
        self.assertEqual(
            recommended["primary_command"],
            "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
        )
        self.assertTrue(any("user-owned Agent gateway" in note for note in recommended["operator_notes"]))

    def test_recovery_plan_prefers_provider_defaults_registration(self) -> None:
        checks = [
            {"status": "ok", "code": "env_present"},
            {"status": "ok", "code": "api_reachable"},
            {"status": "warning", "code": "provider_defaults_missing"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(
            plan["recommended_order"],
            ["agent_gateway_dry_run", "agent_register_local_gateway", "platform_tools_smoke"],
        )
        self.assertEqual(
            recommended["primary_command"],
            "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port 8787",
        )
        self.assertIn("--set-default", " ".join(recommended["copyable_commands"]))
        self.assertTrue(
            any("Agent defaults are missing" in note for note in recommended["operator_notes"])
        )

    def test_recommended_path_for_green_diagnostics_runs_proof_commands(self) -> None:
        checks = [
            {"status": "ok", "code": "env_present"},
            {"status": "ok", "code": "api_reachable"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )
        recommended = diagnose.build_recommended_path(plan, checks)

        self.assertEqual(recommended["status"], "ready")
        self.assertEqual(recommended["blocking_codes"], [])
        self.assertEqual(recommended["primary_command"], "./scripts/doctor.sh")
        self.assertIn("verify_platform_agent_tools.py", " ".join(recommended["copyable_commands"]))
        self.assertIn("verify_adoption_telemetry.py", " ".join(recommended["copyable_commands"]))


if __name__ == "__main__":
    unittest.main()
