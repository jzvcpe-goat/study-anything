from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]


SPEC = importlib.util.spec_from_file_location(
    "study_anything_cli",
    REPO_ROOT / "scripts" / "study_anything_cli.py",
)
assert SPEC is not None and SPEC.loader is not None
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


class FakeUrlopenResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "FakeUrlopenResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class StudyAnythingCliTests(unittest.TestCase):
    def test_cli_error_payload_is_json_serializable_and_redacted(self) -> None:
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        payload = cli.cli_error_payload(
            cli.StudyAnythingError(
                f"Cannot reach Study Anything at http://127.0.0.1:8000 from "
                f"/Users/james/private/source.txt with Authorization: Bearer {secret}"
            )
        )
        serialized = json.dumps(payload, sort_keys=True)

        self.assertEqual(payload["schema_version"], "study-anything-cli-error-v1")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["classification"], "api_unreachable")
        self.assertIn("./scripts/launch_skill_mode.sh", payload["next_steps"])
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secrets_recorded"])
        self.assertIn("<local-path>", serialized)
        self.assertIn("Authorization=<redacted>", serialized)
        self.assertNotIn("/Users/james", serialized)
        self.assertNotIn(secret, serialized)

    def test_emit_cli_error_json_mode_writes_machine_readable_stdout(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            cli.emit_cli_error(
                cli.StudyAnythingError(
                    "Agent endpoint must not contain inline credentials "
                    f"http://user:{secret}@127.0.0.1:8787/invoke"
                ),
                wants_json=True,
            )

        payload = json.loads(stdout.getvalue())
        serialized = json.dumps(payload, sort_keys=True)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(payload["classification"], "agent_endpoint_contains_secret")
        self.assertIn("agent-add-http", " ".join(payload["next_steps"]))
        self.assertNotIn(secret, serialized)
        self.assertNotIn("user:", serialized)

    def test_emit_cli_error_plain_mode_preserves_human_stderr(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            cli.emit_cli_error(cli.StudyAnythingError("Missing command."), wants_json=False)

        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("study-anything: Missing command.", stderr.getvalue())

    def test_unknown_command_has_suggestion_and_first_run_commands(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.build_parser().parse_args(["stat"])

        message = str(context.exception)
        self.assertIn("Unknown command: stat", message)
        self.assertIn("Did you mean", message)
        self.assertIn("health", message)
        self.assertIn("start --text 'Paste source text here.'", message)
        self.assertIn("agent-add-http --set-default", message)

    def test_missing_command_has_first_run_commands(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.build_parser().parse_args([])

        message = str(context.exception)
        self.assertIn("Missing command", message)
        self.assertIn("study_anything_cli.py demo", message)
        self.assertIn("--help", message)

    def test_missing_required_argument_is_actionable(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.build_parser().parse_args(["lesson", "--text", "source"])

        message = str(context.exception)
        self.assertIn("Missing required argument", message)
        self.assertIn("--help", message)
        self.assertIn("start --text 'Paste source text here.'", message)

    def test_unrecognized_argument_mentions_positional_values(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.build_parser().parse_args(["health", "--session", "session-123"])

        message = str(context.exception)
        self.assertIn("Unrecognized CLI argument", message)
        self.assertIn("positional", message)

    def test_missing_session_option_value_is_actionable(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.build_parser().parse_args(["teach", "--session"])

        message = str(context.exception)
        self.assertIn("Missing value for --session", message)
        self.assertIn("teach --session session-123", message)
        self.assertIn("study_anything_cli.py sessions", message)
        self.assertNotIn("expected one argument", message)

    def test_missing_provider_option_value_is_actionable(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.build_parser().parse_args(["agent-test", "--provider-id"])

        message = str(context.exception)
        self.assertIn("Missing value for --provider-id", message)
        self.assertIn("agent-test --provider-id provider-123", message)
        self.assertIn("study_anything_cli.py agents", message)
        self.assertNotIn("expected one argument", message)

    def test_missing_api_base_option_value_is_actionable(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.build_parser().parse_args(cli.normalise_global_options(["health", "--api-base"]))

        message = str(context.exception)
        self.assertIn("Missing value for --api-base", message)
        self.assertIn("http://127.0.0.1:8000", message)
        self.assertIn("launch_skill_mode.sh", message)

    def test_global_json_flag_is_accepted_after_subcommand(self) -> None:
        args = cli.build_parser().parse_args(
            cli.normalise_global_options(["mastery", "--session", "session-123", "--json"])
        )

        cli.normalise_session_id_arg(args)

        self.assertTrue(args.json)
        self.assertEqual(args.session_id, "session-123")

    def test_global_api_base_is_accepted_after_subcommand(self) -> None:
        args = cli.build_parser().parse_args(
            cli.normalise_global_options(["health", "--api-base", "http://127.0.0.1:9"])
        )

        self.assertEqual(args.api_base, "http://127.0.0.1:9")

    def test_api_base_accepts_localhost_without_scheme(self) -> None:
        self.assertEqual(cli.normalise_api_base("127.0.0.1:8000"), "http://127.0.0.1:8000")
        self.assertEqual(cli.normalise_api_base("localhost:8000"), "http://localhost:8000")

    def test_api_base_strips_common_health_paths(self) -> None:
        self.assertEqual(
            cli.normalise_api_base("http://127.0.0.1:8000/health"),
            "http://127.0.0.1:8000",
        )
        self.assertEqual(
            cli.normalise_api_base("http://127.0.0.1:8000/v1/health"),
            "http://127.0.0.1:8000",
        )

    def test_api_base_preserves_service_root_path(self) -> None:
        self.assertEqual(
            cli.normalise_api_base("https://example.test/study-anything/"),
            "https://example.test/study-anything",
        )

    def test_api_base_rejects_nonlocal_without_scheme(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_api_base("example.test:8000")

        message = str(context.exception)
        self.assertIn("must include http:// or https://", message)
        self.assertIn("--api-base 127.0.0.1:8000", message)

    def test_api_base_rejects_placeholder_port(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_api_base("http://127.0.0.1:port")

        message = str(context.exception)
        self.assertIn("API base has an invalid port", message)
        self.assertIn("http://127.0.0.1:8000", message)
        self.assertNotIn("127.0.0.1:port", message)

    def test_api_base_rejects_port_zero(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_api_base("http://127.0.0.1:0")

        message = str(context.exception)
        self.assertIn("port 0 is not usable", message)
        self.assertIn("http://127.0.0.1:8000", message)

    def test_api_base_rejects_query_or_fragment(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_api_base("http://127.0.0.1:8000?token=secret#debug")

        message = str(context.exception)
        self.assertIn("must not include query parameters", message)
        self.assertIn("server root", message)

    def test_api_base_uses_env_file_api_port_when_no_explicit_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text('export API_PORT="18080" # local override\n', encoding="utf-8")

            with patch.dict(
                cli.os.environ,
                {"STUDY_ANYTHING_ENV_FILE": str(env_file)},
                clear=True,
            ):
                self.assertEqual(cli.api_base(), "http://127.0.0.1:18080")

    def test_api_base_explicit_env_var_wins_over_env_file_api_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("API_PORT=18080\n", encoding="utf-8")

            with patch.dict(
                cli.os.environ,
                {
                    "STUDY_ANYTHING_ENV_FILE": str(env_file),
                    "STUDY_ANYTHING_API_BASE": "http://127.0.0.1:19090",
                },
                clear=True,
            ):
                self.assertEqual(cli.api_base(), "http://127.0.0.1:19090")

    def test_api_base_missing_env_file_keeps_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_env = Path(tmpdir) / ".env"

            with patch.dict(
                cli.os.environ,
                {"STUDY_ANYTHING_ENV_FILE": str(missing_env)},
                clear=True,
            ):
                self.assertEqual(cli.api_base(), "http://127.0.0.1:8000")

    def test_api_token_uses_explicit_env_then_private_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("STUDY_ANYTHING_API_TOKEN=file-token-value\n", encoding="utf-8")
            with patch.dict(
                cli.os.environ,
                {"STUDY_ANYTHING_ENV_FILE": str(env_file)},
                clear=True,
            ):
                self.assertEqual(cli.api_token(), "file-token-value")
            with patch.dict(
                cli.os.environ,
                {
                    "STUDY_ANYTHING_ENV_FILE": str(env_file),
                    "STUDY_ANYTHING_API_TOKEN": "explicit-token-value",
                },
                clear=True,
            ):
                self.assertEqual(cli.api_token(), "explicit-token-value")

    def test_api_base_invalid_env_file_api_port_is_actionable_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("API_PORT=not-a-port\n", encoding="utf-8")

            with (
                patch.dict(
                    cli.os.environ,
                    {"STUDY_ANYTHING_ENV_FILE": str(env_file)},
                    clear=True,
                ),
                self.assertRaises(cli.StudyAnythingError) as context,
            ):
                cli.api_base()

        message = str(context.exception)
        self.assertIn("Invalid API_PORT in <env-file>", message)
        self.assertIn("check_env.py --env .env", message)
        self.assertIn("--api-base http://127.0.0.1:8000", message)
        self.assertNotIn(str(env_file), message)
        self.assertNotIn(str(Path(tmpdir)), message)

    def test_session_alias_is_accepted_for_teach(self) -> None:
        args = cli.build_parser().parse_args(
            ["teach", "--session", "session-123", "--layer", "overview"]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")

    def test_session_alias_is_accepted_for_resolve(self) -> None:
        args = cli.build_parser().parse_args(
            ["resolve", "task-123", "--session", "session-123", "--decision", "approve"]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(args.decision, "approve")

    def test_session_id_alias_is_accepted_for_teach(self) -> None:
        args = cli.build_parser().parse_args(
            ["teach", "--session-id", "session-123", "--layer", "overview"]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")

    def test_teach_accepts_unquoted_multiword_text_options(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"schema_version": "teaching-layers-v1"}

        args = cli.build_parser().parse_args(
            [
                "teach",
                "session-123",
                "--level",
                "very",
                "beginner",
                "--language",
                "zh",
                "CN",
                "--example-mode",
                "worked",
                "examples",
            ]
        )

        with patch.object(cli, "post", side_effect=fake_post), patch.object(cli, "emit"):
            cli.cmd_teach(args)

        self.assertEqual(posted[0][0], "/v1/sessions/session-123/teaching-layers")
        self.assertEqual(posted[0][1]["level"], "very beginner")
        self.assertEqual(posted[0][1]["language"], "zh CN")
        self.assertEqual(posted[0][1]["example_mode"], "worked examples")

    def test_session_and_session_id_same_value_is_allowed(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "show",
                "--session",
                "session-123",
                "--session-id",
                "session-123",
            ]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")

    def test_session_alias_conflict_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["show", "session-a", "--session", "session-b"]
        )

        with self.assertRaisesRegex(cli.StudyAnythingError, "positional SESSION_ID"):
            cli.normalise_session_id_arg(args)

    def test_session_named_alias_conflict_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["answer", "--session", "session-a", "--session-id", "session-b", "--text", "answer"]
        )

        with self.assertRaisesRegex(cli.StudyAnythingError, "--session and --session-id"):
            cli.normalise_session_id_arg(args)

    def test_missing_session_id_error_names_both_supported_styles(self) -> None:
        args = cli.build_parser().parse_args(["mastery"])

        with self.assertRaisesRegex(cli.StudyAnythingError, "--session-id SESSION_ID"):
            cli.normalise_session_id_arg(args)

    def test_literal_session_placeholder_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["show", "SESSION_ID"])

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_session_id_arg(args)

        message = str(context.exception)
        self.assertIn("placeholder", message)
        self.assertIn("start --text 'Paste source text here.'", message)
        self.assertIn("sessions", message)

    def test_import_creation_commands_accept_session_as_existing_session_id(self) -> None:
        cases = [
            ["context-import", "package.json", "--session", "session-123"],
            [
                "importer-run",
                "example-note-importer",
                "--confirm-permission",
                "write:context",
                "--session",
                "session-123",
            ],
            [
                "retrieval-import",
                "--source-session-id",
                "source-session",
                "--query",
                "focus",
                "--session",
                "session-123",
            ],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                args = cli.build_parser().parse_args(argv)
                cli.normalise_session_output_or_id_arg(args)

                self.assertEqual(args.session_id, "session-123")
                self.assertIs(args.session, True)

    def test_import_creation_commands_keep_bare_session_as_summary_flag(self) -> None:
        args = cli.build_parser().parse_args(["context-import", "package.json", "--session"])

        cli.normalise_session_output_or_id_arg(args)

        self.assertIs(args.session, True)
        self.assertFalse(getattr(args, "session_id", None))

    def test_import_creation_literal_session_placeholder_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["context-import", "package.json", "--session", "SESSION_ID"]
        )

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_session_output_or_id_arg(args)

        message = str(context.exception)
        self.assertIn("placeholder", message)
        self.assertIn("sessions", message)

    def test_session_output_id_conflict_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["context-import", "package.json", "--session-id", "session-a", "--session", "session-b"]
        )

        with self.assertRaisesRegex(cli.StudyAnythingError, "--session and --session-id"):
            cli.normalise_session_output_or_id_arg(args)

    def test_start_accepts_source_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            text_path = Path(tmpdir) / "source.txt"
            text_path.write_text("File based learning source.", encoding="utf-8")
            args = cli.build_parser().parse_args(
                ["start", "--title", "File Source", "--text-file", str(text_path)]
            )

            self.assertEqual(cli.resolve_text_input(args), "File based learning source.")

    def test_text_file_literal_path_placeholder_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["start", "--text-file", "PATH"])

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.resolve_text_input(args)

        message = str(context.exception)
        self.assertIn("placeholder", message)
        self.assertIn("--text-file ./notes/source.txt", message)
        self.assertIn("--text 'Paste the source text here.'", message)
        self.assertIn("--text-file -", message)

    def test_answer_text_file_placeholder_with_angle_brackets_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["answer", "--session", "session-123", "--text-file", "<PATH>"]
        )
        cli.normalise_session_id_arg(args)

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.resolve_answer_text_input(args)

        message = str(context.exception)
        self.assertIn("placeholder", message)
        self.assertIn("--text 'Paste the source text here.'", message)

    def test_start_accepts_positional_source_text(self) -> None:
        args = cli.build_parser().parse_args(["start", "Rust ownership keeps memory safe."])

        self.assertEqual(cli.resolve_source_text_input(args), "Rust ownership keeps memory safe.")

    def test_start_accepts_unquoted_multiword_source_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["start", "Rust", "ownership", "keeps", "memory", "safe."]
        )

        self.assertEqual(cli.resolve_source_text_input(args), "Rust ownership keeps memory safe.")

    def test_start_text_option_accepts_unquoted_multiword_source_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["start", "--text", "Rust", "ownership", "keeps", "memory", "safe."]
        )

        self.assertEqual(cli.resolve_source_text_input(args), "Rust ownership keeps memory safe.")

    def test_start_reference_option_accepts_unquoted_multiword_reference(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            if path == "/v1/sessions":
                return {"session_id": "session-123"}
            if path.endswith("/run"):
                return {"session_id": "session-123", "stage": "quiz"}
            return {"ok": True}

        args = cli.build_parser().parse_args(
            [
                "start",
                "--text",
                "Rust ownership source.",
                "--reference",
                "rust",
                "book",
                "--agent-mode",
                "demo",
            ]
        )

        with patch.object(cli, "post", side_effect=fake_post):
            cli.create_session(args)

        self.assertEqual(posted[1][1]["reference"], "rust book")

    def test_start_title_accepts_unquoted_multiword_with_explicit_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["start", "--title", "Rust", "ownership", "--text", "source"]
        )

        source_text = cli.resolve_source_text_input(args)

        self.assertEqual(source_text, "source")
        self.assertEqual(cli.resolve_title_input(args, source_text), "Rust ownership")

    def test_start_title_spill_recovers_source_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["start", "--title", "Rust", "ownership", "keeps", "memory", "safe."]
        )

        source_text = cli.resolve_source_text_input(args)

        self.assertEqual(source_text, "ownership keeps memory safe.")
        self.assertEqual(cli.resolve_title_input(args, source_text), "Rust")

    def test_start_without_title_derives_title_from_source_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["start", "--text", "Rust ownership keeps memory safe.", "--agent-mode", "demo"]
        )

        self.assertEqual(
            cli.resolve_title_input(args, cli.resolve_text_input(args)),
            "Rust ownership keeps memory safe.",
        )

    def test_start_blank_title_derives_title_from_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            text_path = Path(tmpdir) / "source.txt"
            text_path.write_text("\nFile based learning source.\nSecond line.", encoding="utf-8")
            args = cli.build_parser().parse_args(
                ["start", "--title", "   ", "--text-file", str(text_path), "--agent-mode", "demo"]
            )

            self.assertEqual(
                cli.resolve_title_input(args, cli.resolve_text_input(args)),
                "File based learning source.",
            )

    def test_start_derived_title_is_redacted_and_bounded(self) -> None:
        local_home = "/Users/" + "james"
        secret = "sk-" + "proj-abcdef1234567890"
        args = cli.build_parser().parse_args(
            ["start", "--text", f"{local_home}/private/source.txt {secret}", "--agent-mode", "demo"]
        )

        title = cli.resolve_title_input(args, cli.resolve_text_input(args))

        self.assertIn("<local-path>", title)
        self.assertIn("sk-<redacted>", title)
        self.assertNotIn(local_home, title)
        self.assertLessEqual(len(title), cli.MAX_DERIVED_TITLE_CHARS)

    def test_create_session_without_title_posts_derived_title(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            if path == "/v1/sessions":
                return {"session_id": "session-123"}
            if path.endswith("/run"):
                return {"session_id": "session-123", "stage": "quiz"}
            return {"ok": True}

        args = cli.build_parser().parse_args(
            ["start", "--text", "Derived session title.", "--agent-mode", "demo"]
        )

        with patch.object(cli, "post", side_effect=fake_post):
            cli.create_session(args)

        reading_payload = posted[1][1]
        self.assertEqual(reading_payload["title"], "Derived session title.")

    def test_lesson_without_title_is_accepted_and_derives_title(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "lesson",
                "--text",
                "Layered teaching source.",
                "--answer",
                "A grounded answer.",
                "--agent-mode",
                "demo",
            ]
        )

        self.assertEqual(
            cli.resolve_title_input(args, cli.resolve_text_input(args)),
            "Layered teaching source.",
        )

    def test_lesson_accepts_positional_source_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["lesson", "Layered teaching source.", "--answer", "A grounded answer."]
        )

        self.assertEqual(cli.resolve_source_text_input(args), "Layered teaching source.")

    def test_lesson_accepts_unquoted_multiword_source_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["lesson", "Layered", "teaching", "source.", "--answer", "A grounded answer."]
        )

        self.assertEqual(cli.resolve_source_text_input(args), "Layered teaching source.")

    def test_lesson_text_option_accepts_unquoted_multiword_source_text(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "lesson",
                "--text",
                "Layered",
                "teaching",
                "source.",
                "--answer",
                "A grounded answer.",
            ]
        )

        self.assertEqual(cli.resolve_source_text_input(args), "Layered teaching source.")

    def test_lesson_accepts_unquoted_multiword_answer(self) -> None:
        args = cli.build_parser().parse_args(
            ["lesson", "Layered", "source.", "--answer", "A", "grounded", "answer."]
        )

        self.assertEqual(cli.resolve_source_text_input(args), "Layered source.")
        self.assertEqual(cli._positional_text(args.answer), "A grounded answer.")

    def test_lesson_title_accepts_unquoted_multiword_after_source(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "lesson",
                "Layered",
                "source.",
                "--title",
                "Layered",
                "lesson",
                "--answer",
                "ok",
            ]
        )

        source_text = cli.resolve_source_text_input(args)

        self.assertEqual(source_text, "Layered source.")
        self.assertEqual(cli.resolve_title_input(args, source_text), "Layered lesson")

    def test_missing_text_file_error_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "missing-source.txt"
            args = cli.build_parser().parse_args(
                ["start", "--title", "Missing File", "--text-file", str(missing_path)]
            )

            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.resolve_text_input(args)

        message = str(context.exception)
        self.assertIn("Cannot read --text-file", message)
        self.assertIn("<text-file>", message)
        self.assertIn("Check that the path exists", message)
        self.assertIn("--text-file -", message)
        self.assertNotIn(str(missing_path), message)

    def test_non_utf8_enrichment_file_error_names_matching_inline_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            enrichment_path = Path(tmpdir) / "bad-enrichment.bin"
            enrichment_path.write_bytes(b"\xff\xfe\x00")
            args = cli.build_parser().parse_args(
                [
                    "lesson",
                    "--title",
                    "Bad Enrichment",
                    "--text",
                    "Core source.",
                    "--answer",
                    "Grounded answer.",
                    "--enrichment-text-file",
                    str(enrichment_path),
                ]
            )

            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.resolve_text_input(
                    args,
                    text_attr="enrichment_text",
                    file_attr="enrichment_text_file",
                    text_option="--enrichment-text",
                    file_option="--enrichment-text-file",
                )

        message = str(context.exception)
        self.assertIn("--enrichment-text-file", message)
        self.assertIn("<text-file>", message)
        self.assertIn("not UTF-8", message)
        self.assertIn("paste with --enrichment-text", message)
        self.assertNotIn(str(enrichment_path), message)
        self.assertNotIn("paste with --text:", message)

    def test_text_and_text_file_conflict_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["start", "--title", "Conflict", "--text", "inline", "--text-file", "source.txt"]
        )

        with self.assertRaisesRegex(cli.StudyAnythingError, "Use either --text or --text-file"):
            cli.resolve_text_input(args)

    def test_positional_source_text_conflicts_with_text_option(self) -> None:
        args = cli.build_parser().parse_args(
            ["start", "Positional source.", "--text", "Inline source."]
        )

        with self.assertRaisesRegex(cli.StudyAnythingError, "choose only one source input"):
            cli.resolve_source_text_input(args)

    def test_positional_source_text_conflicts_with_text_file(self) -> None:
        args = cli.build_parser().parse_args(
            ["start", "Positional source.", "--text-file", "source.txt"]
        )

        with self.assertRaisesRegex(cli.StudyAnythingError, "choose only one source input"):
            cli.resolve_source_text_input(args)

    def test_missing_text_error_mentions_file_and_stdin(self) -> None:
        args = cli.build_parser().parse_args(["start", "--title", "Missing Text"])

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.resolve_text_input(args)

        message = str(context.exception)
        self.assertIn("--text-file ./notes/source.txt", message)
        self.assertIn("--text-file -", message)
        self.assertNotIn("--text-file PATH", message)

    def test_missing_json_file_error_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "missing-package.json"

            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.load_json_file(str(missing_path))

        message = str(context.exception)
        self.assertIn("Cannot read JSON file", message)
        self.assertIn("<json-file>", message)
        self.assertIn("Check that the path exists", message)
        self.assertIn("read permission", message)
        self.assertNotIn(str(missing_path), message)

    def test_non_utf8_json_file_error_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = Path(tmpdir) / "bad-package.json"
            bad_path.write_bytes(b"\xff\xfe\x00")

            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.load_json_file(str(bad_path))

        message = str(context.exception)
        self.assertIn("<json-file>", message)
        self.assertIn("not UTF-8 text", message)
        self.assertIn("Save it as UTF-8", message)
        self.assertNotIn(str(bad_path), message)

    def test_output_file_creates_missing_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "missing-parent" / "export.md"

            cli.write_output_file(output_path, "export")

            self.assertEqual(output_path.read_text(encoding="utf-8"), "export")

    def test_output_file_parent_file_error_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_parent = Path(tmpdir) / "parent-file"
            output_parent.write_text("already a file", encoding="utf-8")
            output_path = output_parent / "export.md"

            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.write_output_file(output_path, "export")

        message = str(context.exception)
        self.assertIn("Cannot write output file", message)
        self.assertIn("<output-file>", message)
        self.assertIn("avoid using a file as a parent directory", message)
        self.assertIn("omit --output", message)
        self.assertNotIn(str(output_path), message)
        self.assertNotIn(str(output_parent), message)

    def test_metadata_json_parse_error_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "enrich",
                "--session",
                "session-123",
                "--reference",
                "https://example.test",
                "--title",
                "Bad metadata",
                "--text",
                "excerpt",
                "--metadata-json",
                "{bad",
            ]
        )
        cli.normalise_session_id_arg(args)

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.cmd_enrich(args)

        message = str(context.exception)
        self.assertIn("Cannot parse --metadata-json as a JSON object", message)
        self.assertIn("Wrap inline JSON in single quotes", message)
        self.assertIn("--metadata-json '{\"source\":\"browser\"}'", message)

    def test_metadata_json_non_object_error_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "enrich",
                "--session",
                "session-123",
                "--reference",
                "https://example.test",
                "--title",
                "Bad metadata",
                "--text",
                "excerpt",
                "--metadata-json",
                "[1]",
            ]
        )
        cli.normalise_session_id_arg(args)

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.cmd_enrich(args)

        message = str(context.exception)
        self.assertIn("--metadata-json must decode to a JSON object", message)
        self.assertIn("got list", message)

    def test_enrich_without_reference_or_title_posts_safe_defaults(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"status": "ok"}

        args = cli.build_parser().parse_args(
            [
                "enrich",
                "--session",
                "session-123",
                "--text",
                "Video clip shows retrieval before rereading.",
            ]
        )
        cli.normalise_session_id_arg(args)

        with patch.object(cli, "post", side_effect=fake_post), patch.object(cli, "emit"):
            cli.cmd_enrich(args)

        item = posted[0][1]["items"][0]
        self.assertEqual(item["reference"], cli.DEFAULT_ENRICHMENT_REFERENCE)
        self.assertEqual(item["title"], "Video clip shows retrieval before rereading.")
        self.assertEqual(item["text"], "Video clip shows retrieval before rereading.")

    def test_enrich_accepts_positional_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["enrich", "session-123", "Video", "clip", "shows", "retrieval."]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_enrichment_text_input(args), "Video clip shows retrieval.")

    def test_enrich_accepts_named_session_with_positional_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["enrich", "--session", "session-123", "Video", "clip", "shows", "retrieval."]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_enrichment_text_input(args), "Video clip shows retrieval.")

    def test_enrich_text_option_accepts_unquoted_multiword_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["enrich", "session-123", "--text", "Video", "clip", "shows", "retrieval."]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_enrichment_text_input(args), "Video clip shows retrieval.")

    def test_enrich_reference_locator_options_accept_unquoted_multiword_values(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"status": "ok"}

        args = cli.build_parser().parse_args(
            [
                "enrich",
                "session-123",
                "--text",
                "Video",
                "clip",
                "--reference",
                "browser",
                "clip",
                "--locator",
                "00:01",
                "-",
                "00:10",
                "--bundle-reference",
                "local",
                "bundle",
            ]
        )
        cli.normalise_session_id_arg(args)

        with patch.object(cli, "post", side_effect=fake_post), patch.object(cli, "emit"):
            cli.cmd_enrich(args)

        payload = posted[0][1]
        item = payload["items"][0]
        self.assertEqual(payload["reference"], "local bundle")
        self.assertEqual(item["reference"], "browser clip")
        self.assertEqual(item["locator"], "00:01 - 00:10")

    def test_enrich_title_accepts_unquoted_multiword_after_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["enrich", "session-123", "excerpt", "--title", "Video", "clip"]
        )

        cli.normalise_session_id_arg(args)
        enrichment_text = cli.resolve_enrichment_text_input(args)

        self.assertEqual(enrichment_text, "excerpt")
        self.assertEqual(
            cli.resolve_title_input(args, enrichment_text, default_title=cli.DEFAULT_ENRICHMENT_TITLE),
            "Video clip",
        )

    def test_enrich_positional_text_conflicts_with_text_option(self) -> None:
        args = cli.build_parser().parse_args(
            ["enrich", "session-123", "Video", "clip", "--text", "Other excerpt."]
        )

        cli.normalise_session_id_arg(args)

        with self.assertRaisesRegex(cli.StudyAnythingError, "choose only one enrichment input"):
            cli.resolve_enrichment_text_input(args)

    def test_enrich_positional_text_conflicts_with_text_file(self) -> None:
        args = cli.build_parser().parse_args(
            ["enrich", "session-123", "Video", "clip", "--text-file", "excerpt.txt"]
        )

        cli.normalise_session_id_arg(args)

        with self.assertRaisesRegex(cli.StudyAnythingError, "choose only one enrichment input"):
            cli.resolve_enrichment_text_input(args)

    def test_retrieval_search_accepts_positional_query(self) -> None:
        args = cli.build_parser().parse_args(["retrieval-search", "session-123", "focus", "topic"])

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_query_input(args), "focus topic")

    def test_retrieval_search_query_option_accepts_unquoted_multiword_query(self) -> None:
        args = cli.build_parser().parse_args(
            ["retrieval-search", "session-123", "--query", "focus", "topic"]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_query_input(args), "focus topic")

    def test_retrieval_eval_accepts_named_session_with_positional_query(self) -> None:
        args = cli.build_parser().parse_args(
            ["retrieval-eval", "--session", "session-123", "focus", "topic"]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_query_input(args), "focus topic")

    def test_retrieval_eval_query_option_accepts_unquoted_multiword_query(self) -> None:
        args = cli.build_parser().parse_args(
            ["retrieval-eval", "--session", "session-123", "--query", "focus", "topic"]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_query_input(args), "focus topic")

    def test_retrieval_query_positional_conflicts_with_query_option(self) -> None:
        args = cli.build_parser().parse_args(
            ["retrieval-search", "session-123", "focus", "--query", "other"]
        )

        cli.normalise_session_id_arg(args)

        with self.assertRaisesRegex(cli.StudyAnythingError, "choose only one query input"):
            cli.resolve_query_input(args)

    def test_retrieval_query_missing_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["retrieval-search", "session-123"])

        cli.normalise_session_id_arg(args)

        with self.assertRaisesRegex(cli.StudyAnythingError, "Missing query"):
            cli.resolve_query_input(args)

    def test_retrieval_import_query_option_accepts_unquoted_multiword_query(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"session_id": "session-123"}

        args = cli.build_parser().parse_args(
            [
                "retrieval-import",
                "--source-session-id",
                "source-session",
                "--query",
                "focus",
                "topic",
                "--session-id",
                "session-123",
            ]
        )
        cli.normalise_session_output_or_id_arg(args)

        with patch.object(cli, "post", side_effect=fake_post), patch.object(cli, "emit"):
            cli.cmd_retrieval_import(args)

        self.assertEqual(posted[0][0], "/v1/sessions/session-123/retrieval/context-package")
        self.assertEqual(posted[0][1]["query"], "focus topic")

    def test_enrich_blank_reference_and_title_fall_back_without_leaking_path(self) -> None:
        posted: list[tuple[str, dict]] = []
        local_home = "/Users/" + "james"
        secret = "sk-" + "proj-abcdefghijklmnop123456"

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"status": "ok"}

        args = cli.build_parser().parse_args(
            [
                "enrich",
                "--session",
                "session-123",
                "--reference",
                "   ",
                "--title",
                "   ",
                "--text",
                f"{local_home}/private/video-note.txt {secret}",
            ]
        )
        cli.normalise_session_id_arg(args)

        with patch.object(cli, "post", side_effect=fake_post), patch.object(cli, "emit"):
            cli.cmd_enrich(args)

        item = posted[0][1]["items"][0]
        self.assertEqual(item["reference"], cli.DEFAULT_ENRICHMENT_REFERENCE)
        self.assertIn("<local-path>", item["title"])
        self.assertIn("sk-<redacted>", item["title"])
        self.assertNotIn(local_home, item["title"])

    def test_input_json_parse_error_suggests_input_file(self) -> None:
        args = cli.build_parser().parse_args(["importer-run", "web", "--input-json", "{bad"])

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli._importer_inputs(args)

        message = str(context.exception)
        self.assertIn("Cannot parse --input-json as a JSON object", message)
        self.assertIn("Wrap inline JSON in single quotes", message)
        self.assertIn("--input-json '{\"url\":\"https://example.test\"}'", message)
        self.assertIn("--input-file path/to/input.json", message)

    def test_input_json_non_object_suggests_input_file(self) -> None:
        args = cli.build_parser().parse_args(["importer-run", "web", "--input-json", "[1]"])

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli._importer_inputs(args)

        message = str(context.exception)
        self.assertIn("--input-json must decode to a JSON object", message)
        self.assertIn("got list", message)
        self.assertIn("--input-file path/to/input.json", message)

    def test_start_agent_mode_defaults_to_auto(self) -> None:
        args = cli.build_parser().parse_args(["start", "--title", "Auto", "--text", "source"])

        self.assertEqual(args.agent_mode, "auto")

    def test_auto_agent_mode_falls_back_to_demo_without_required_defaults(self) -> None:
        args = cli.build_parser().parse_args(["start", "--title", "Auto", "--text", "source"])

        with patch.object(
            cli,
            "request",
            return_value={
                "schema_version": "agent-v1",
                "providers": [],
                "defaults": {"quiz.generate": None, "answer.grade": None},
            },
        ):
            self.assertEqual(cli.resolve_start_agent_mode(args), "demo")
        self.assertEqual(
            args.auto_agent_missing_defaults,
            ["quiz.generate", "answer.grade", "insight.synthesize", "source.verify"],
        )
        self.assertFalse(args.auto_agent_has_user_configuration)

    def test_auto_agent_mode_uses_configured_when_learning_defaults_exist(self) -> None:
        args = cli.build_parser().parse_args(["start", "--title", "Auto", "--text", "source"])
        defaults = {
            capability: "provider-123"
            for capability in cli.AUTO_AGENT_MODE_REQUIRED_CAPABILITIES
        }

        with patch.object(
            cli,
            "request",
            return_value={"schema_version": "agent-v1", "providers": [], "defaults": defaults},
        ):
            self.assertEqual(cli.resolve_start_agent_mode(args), "configured")
        self.assertEqual(args.auto_agent_missing_defaults, [])

    def test_create_session_auto_uses_configured_agent_defaults(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            if path == "/v1/sessions":
                return {"session_id": "session-123"}
            if path.endswith("/run"):
                return {"session_id": "session-123", "stage": "quiz"}
            return {"ok": True}

        args = cli.build_parser().parse_args(
            ["start", "--title", "Auto", "--text", "source", "--user-id", "alice"]
        )
        defaults = {
            capability: "provider-123"
            for capability in cli.AUTO_AGENT_MODE_REQUIRED_CAPABILITIES
        }

        with (
            patch.object(
                cli,
                "request",
                return_value={"schema_version": "agent-v1", "providers": [], "defaults": defaults},
            ),
            patch.object(cli, "post", side_effect=fake_post),
        ):
            cli.create_session(args)

        self.assertEqual(posted[0][0], "/v1/sessions")
        self.assertIs(posted[0][1]["use_demo_agent"], False)

    def test_create_session_auto_falls_back_to_demo_without_defaults(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            if path == "/v1/sessions":
                return {"session_id": "session-123"}
            if path.endswith("/run"):
                return {"session_id": "session-123", "stage": "quiz"}
            return {"ok": True}

        args = cli.build_parser().parse_args(["start", "--title", "Auto", "--text", "source"])

        with (
            patch.object(
                cli,
                "request",
                return_value={"schema_version": "agent-v1", "providers": [], "defaults": {}},
            ),
            patch.object(cli, "post", side_effect=fake_post),
        ):
            cli.create_session(args)

        self.assertEqual(posted[0][0], "/v1/sessions")
        self.assertIs(posted[0][1]["use_demo_agent"], True)

    def test_create_session_auto_warns_when_user_agent_defaults_are_partial(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            if path == "/v1/sessions":
                return {"session_id": "session-123"}
            if path.endswith("/run"):
                return {"session_id": "session-123", "stage": "quiz"}
            return {"ok": True}

        args = cli.build_parser().parse_args(["start", "--title", "Auto", "--text", "source"])
        status = {
            "schema_version": "agent-v1",
            "providers": [
                {
                    "provider_id": "provider-123",
                    "kind": "http_agent",
                    "enabled": True,
                    "capabilities": ["quiz.generate"],
                }
            ],
            "defaults": {"quiz.generate": "provider-123"},
        }
        stderr = StringIO()

        with (
            patch.object(cli, "request", return_value=status),
            patch.object(cli, "post", side_effect=fake_post),
            patch("sys.stderr", stderr),
        ):
            cli.create_session(args)

        message = stderr.getvalue()
        self.assertIn("auto Agent mode fell back to the zero-key demo", message)
        self.assertIn("missing defaults: answer.grade, insight.synthesize, source.verify", message)
        self.assertIn("agent-set-default provider-123", message)
        self.assertNotIn("agent-set-default PROVIDER_ID", message)
        self.assertNotIn("agent-set-default PROVIDER_ID --all", message)
        self.assertIs(posted[0][1]["use_demo_agent"], True)

    def test_create_session_auto_does_not_warn_for_fresh_zero_config_demo(self) -> None:
        def fake_post(path: str, payload: dict | None = None) -> dict:
            if path == "/v1/sessions":
                return {"session_id": "session-123"}
            if path.endswith("/run"):
                return {"session_id": "session-123", "stage": "quiz"}
            return {"ok": True}

        args = cli.build_parser().parse_args(["start", "--title", "Auto", "--text", "source"])
        status = {
            "schema_version": "agent-v1",
            "providers": [
                {"provider_id": "fake-deterministic", "kind": "fake_agent", "enabled": True}
            ],
            "defaults": {},
        }
        stderr = StringIO()

        with (
            patch.object(cli, "request", return_value=status),
            patch.object(cli, "post", side_effect=fake_post),
            patch("sys.stderr", stderr),
        ):
            cli.create_session(args)

        self.assertEqual(stderr.getvalue(), "")

    def test_create_session_auto_fallback_warning_is_suppressed_for_json_output(self) -> None:
        def fake_post(path: str, payload: dict | None = None) -> dict:
            if path == "/v1/sessions":
                return {"session_id": "session-123"}
            if path.endswith("/run"):
                return {"session_id": "session-123", "stage": "quiz"}
            return {"ok": True}

        args = cli.build_parser().parse_args(
            cli.normalise_global_options(["start", "--title", "Auto", "--text", "source", "--json"])
        )
        status = {
            "schema_version": "agent-v1",
            "providers": [{"provider_id": "provider-123", "kind": "http_agent", "enabled": True}],
            "defaults": {"quiz.generate": "provider-123"},
        }
        stderr = StringIO()

        with (
            patch.object(cli, "request", return_value=status),
            patch.object(cli, "post", side_effect=fake_post),
            patch("sys.stderr", stderr),
        ):
            cli.create_session(args)

        self.assertEqual(stderr.getvalue(), "")

    def test_answer_accepts_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            text_path = Path(tmpdir) / "answer.txt"
            text_path.write_text("Grounded answer from a file.", encoding="utf-8")
            args = cli.build_parser().parse_args(
                ["answer", "--session", "session-123", "--text-file", str(text_path)]
            )

            cli.normalise_session_id_arg(args)

            self.assertEqual(args.session_id, "session-123")
            self.assertEqual(cli.resolve_text_input(args), "Grounded answer from a file.")

    def test_answer_accepts_positional_text(self) -> None:
        args = cli.build_parser().parse_args(["answer", "session-123", "Grounded answer."])

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_answer_text_input(args), "Grounded answer.")

    def test_answer_accepts_unquoted_multiword_positional_text(self) -> None:
        args = cli.build_parser().parse_args(["answer", "session-123", "Grounded", "answer."])

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_answer_text_input(args), "Grounded answer.")

    def test_answer_accepts_named_session_with_positional_text(self) -> None:
        args = cli.build_parser().parse_args(["answer", "--session", "session-123", "Grounded answer."])

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_answer_text_input(args), "Grounded answer.")

    def test_answer_accepts_named_session_with_unquoted_multiword_text(self) -> None:
        args = cli.build_parser().parse_args(
            ["answer", "--session", "session-123", "Grounded", "answer."]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_answer_text_input(args), "Grounded answer.")

    def test_answer_text_option_accepts_unquoted_multiword_answer(self) -> None:
        args = cli.build_parser().parse_args(
            ["answer", "session-123", "--text", "A", "grounded", "answer."]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(cli.resolve_answer_text_input(args), "A grounded answer.")

    def test_answer_item_id_option_accepts_unquoted_multiword_id(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"session_id": "session-123", "stage": "completed"}

        args = cli.build_parser().parse_args(
            [
                "answer",
                "session-123",
                "--item-id",
                "quiz",
                "one",
                "--text",
                "A",
                "grounded",
                "answer.",
            ]
        )
        cli.normalise_session_id_arg(args)

        with (
            patch.object(cli, "request", return_value={"session_id": "session-123"}),
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
        ):
            cli.cmd_answer(args)

        self.assertEqual(posted[0][0], "/v1/sessions/session-123/answers")
        self.assertEqual(posted[0][1]["answers"], {"quiz one": "A grounded answer."})

    def test_answer_positional_text_conflicts_with_text_option(self) -> None:
        args = cli.build_parser().parse_args(
            ["answer", "session-123", "Grounded answer.", "--text", "Other answer."]
        )

        cli.normalise_session_id_arg(args)

        with self.assertRaisesRegex(cli.StudyAnythingError, "choose only one answer input"):
            cli.resolve_answer_text_input(args)

    def test_answer_positional_text_conflicts_with_text_file(self) -> None:
        args = cli.build_parser().parse_args(
            ["answer", "session-123", "Grounded answer.", "--text-file", "answer.txt"]
        )

        cli.normalise_session_id_arg(args)

        with self.assertRaisesRegex(cli.StudyAnythingError, "choose only one answer input"):
            cli.resolve_answer_text_input(args)

    def test_lesson_accepts_enrichment_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.txt"
            enrichment_path = Path(tmpdir) / "enrichment.txt"
            source_path.write_text("Core lesson source.", encoding="utf-8")
            enrichment_path.write_text("Extra context from browser or notes.", encoding="utf-8")
            args = cli.build_parser().parse_args(
                [
                    "lesson",
                    "--title",
                    "File Lesson",
                    "--text-file",
                    str(source_path),
                    "--answer",
                    "A grounded answer.",
                    "--enrichment-text-file",
                    str(enrichment_path),
                ]
            )

            self.assertEqual(cli.resolve_text_input(args), "Core lesson source.")
            self.assertEqual(
                cli.resolve_text_input(
                    args,
                    text_attr="enrichment_text",
                    file_attr="enrichment_text_file",
                    text_option="--enrichment-text",
                    file_option="--enrichment-text-file",
                ),
                "Extra context from browser or notes.",
            )

    def test_agent_endpoint_root_is_normalised_to_invoke(self) -> None:
        self.assertEqual(
            cli.normalise_http_agent_endpoint("http://127.0.0.1:8787"),
            "http://127.0.0.1:8787/invoke",
        )

    def test_agent_endpoint_health_is_normalised_to_invoke(self) -> None:
        self.assertEqual(
            cli.normalise_http_agent_endpoint("http://127.0.0.1:8787/health"),
            "http://127.0.0.1:8787/invoke",
        )

    def test_agent_endpoint_accepts_localhost_without_scheme(self) -> None:
        self.assertEqual(
            cli.normalise_http_agent_endpoint("127.0.0.1:8787"),
            "http://127.0.0.1:8787/invoke",
        )

    def test_agent_endpoint_rejects_placeholder_port(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_http_agent_endpoint("http://127.0.0.1:port/invoke")

        message = str(context.exception)
        self.assertIn("Agent endpoint has an invalid port", message)
        self.assertIn("http://127.0.0.1:8787/invoke", message)
        self.assertNotIn("127.0.0.1:port", message)

    def test_agent_endpoint_preserves_custom_invoke_path(self) -> None:
        self.assertEqual(
            cli.normalise_http_agent_endpoint("https://agent.example.test/custom/invoke"),
            "https://agent.example.test/custom/invoke",
        )

    def test_agent_endpoint_rejects_inline_credentials(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_http_agent_endpoint("http://user:secret@127.0.0.1:8787/invoke")

        message = str(context.exception)
        self.assertIn("inline credentials", message)
        self.assertIn("Keep model/API secrets inside your own gateway", message)
        self.assertIn("http://127.0.0.1:8787/invoke", message)
        self.assertIn("study_anything_cli.py agent-test", message)
        self.assertNotIn("user:secret", message)

    def test_agent_endpoint_rejects_secret_query(self) -> None:
        secret = "sk-" + "proj-example123456789012345"
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_http_agent_endpoint(
                f"http://127.0.0.1:8787/invoke?api_key={secret}"
            )

        message = str(context.exception)
        self.assertIn("query parameters", message)
        self.assertIn("Keep model/API secrets inside your own gateway", message)
        self.assertIn("openai_compatible_agent_gateway.py --dry-run --port 8787", message)
        self.assertNotIn(secret, message)

    def test_agent_endpoint_rejects_non_secret_query_without_echoing_value(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_http_agent_endpoint(
                "http://127.0.0.1:8787/invoke?debug=true&mode=browser"
            )

        message = str(context.exception)
        self.assertIn("must not include query parameters", message)
        self.assertIn("without browser/debug parameters", message)
        self.assertIn("agent-add-http --endpoint http://127.0.0.1:8787/invoke --set-default", message)
        self.assertNotIn("debug=true", message)
        self.assertNotIn("mode=browser", message)

    def test_agent_endpoint_rejects_authorization_query(self) -> None:
        secret = "Bearer" + "Secret123456"
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_http_agent_endpoint(
                f"http://127.0.0.1:8787/invoke?Authorization={secret}"
            )

        message = str(context.exception)
        self.assertIn("query parameters", message)
        self.assertIn("Keep model/API secrets inside your own gateway", message)
        self.assertNotIn(secret, message)

    def test_agent_endpoint_rejects_fragment_without_leaking_values(self) -> None:
        secret = "sk-" + "proj-example123456789012345"
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_http_agent_endpoint(
                f"http://127.0.0.1:8787/invoke#token={secret}"
            )

        message = str(context.exception)
        self.assertIn("URL fragments", message)
        self.assertIn("HTTP clients do not send #... fragments", message)
        self.assertIn("http://127.0.0.1:8787/invoke", message)
        self.assertIn("Keep model/API secrets inside your own gateway", message)
        self.assertNotIn("token=", message)
        self.assertNotIn(secret, message)

    def test_agent_endpoint_rejects_non_secret_fragment(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_http_agent_endpoint("http://127.0.0.1:8787/invoke#debug")

        message = str(context.exception)
        self.assertIn("URL fragments", message)
        self.assertIn("cannot configure the Agent", message)
        self.assertNotIn("debug", message)

    def test_agent_endpoint_empty_error_has_zero_key_path(self) -> None:
        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_http_agent_endpoint("")

        message = str(context.exception)
        self.assertIn("Agent endpoint is empty", message)
        self.assertIn("openai_compatible_agent_gateway.py --dry-run --port 8787", message)
        self.assertIn("agent-add-http --set-default", message)

    def test_default_http_agent_capabilities_cover_memory_retrieval(self) -> None:
        self.assertIn("memory.retrieve", cli.DEFAULT_HTTP_AGENT_CAPABILITIES)

    def test_agent_add_http_label_defaults_from_endpoint(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"provider_id": "provider-123"}

        args = cli.build_parser().parse_args(
            ["agent-add-http", "--endpoint", "http://127.0.0.1:8787"]
        )

        with (
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_add_http(args)

        self.assertEqual(posted[0][0], "/v1/agents/providers")
        self.assertEqual(posted[0][1]["endpoint"], "http://127.0.0.1:8787/invoke")
        self.assertEqual(posted[0][1]["label"], "Local gateway (127.0.0.1:8787)")

    def test_agent_add_http_accepts_positional_endpoint(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"provider_id": "provider-123"}

        args = cli.build_parser().parse_args(["agent-add-http", "127.0.0.1:8787"])

        with (
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_add_http(args)

        self.assertEqual(posted[0][1]["endpoint"], "http://127.0.0.1:8787/invoke")
        self.assertEqual(posted[0][1]["label"], "Local gateway (127.0.0.1:8787)")

    def test_agent_add_http_positional_endpoint_conflicts_with_endpoint_option(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "agent-add-http",
                "http://127.0.0.1:8787",
                "--endpoint",
                "https://agent.example.test/invoke",
            ]
        )

        with self.assertRaisesRegex(cli.StudyAnythingError, "positional AGENT_ENDPOINT"):
            cli.cmd_agent_add_http(args)

    def test_agent_add_http_accepts_unquoted_multiword_label(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"provider_id": "provider-123"}

        args = cli.build_parser().parse_args(
            [
                "agent-add-http",
                "http://127.0.0.1:8787",
                "--label",
                "Local",
                "learning",
                "gateway",
            ]
        )

        with (
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_add_http(args)

        self.assertEqual(posted[0][1]["label"], "Local learning gateway")

    def test_agent_add_http_without_endpoint_uses_local_gateway_default(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"provider_id": "provider-123"}

        args = cli.build_parser().parse_args(["agent-add-http"])

        with (
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_add_http(args)

        self.assertEqual(posted[0][0], "/v1/agents/providers")
        self.assertEqual(posted[0][1]["endpoint"], cli.DEFAULT_LOCAL_AGENT_ENDPOINT)
        self.assertEqual(posted[0][1]["label"], "Local gateway (127.0.0.1:8787)")

    def test_agent_add_http_empty_endpoint_still_errors(self) -> None:
        args = cli.build_parser().parse_args(["agent-add-http", "--endpoint", ""])

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.cmd_agent_add_http(args)

        self.assertIn("Agent endpoint is empty", str(context.exception))

    def test_agent_add_http_set_default_covers_memory_retrieval(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            if path == "/v1/agents/providers":
                return {"provider_id": "provider-123"}
            return {"schema_version": "agent-v1", "providers": [], "defaults": {}}

        args = cli.build_parser().parse_args(
            ["agent-add-http", "--endpoint", "http://127.0.0.1:8787", "--set-default"]
        )

        with (
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_add_http(args)

        default_payloads = [payload for path, payload in posted if path == "/v1/agents/defaults"]
        self.assertTrue(
            any(payload["capability"] == "memory.retrieve" for payload in default_payloads)
        )

    def test_agent_add_http_splits_dedupes_capabilities_and_validates_timeout(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"provider_id": "provider-123"}

        args = cli.build_parser().parse_args(
            [
                "agent-add-http",
                "--endpoint",
                "http://127.0.0.1:8787",
                "--capability",
                "quiz.generate, answer.grade",
                "--capability",
                "quiz.generate",
                "--timeout",
                "20",
            ]
        )

        with (
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_add_http(args)

        self.assertEqual(posted[0][1]["capabilities"], ["quiz.generate", "answer.grade"])
        self.assertEqual(posted[0][1]["timeout_seconds"], 20)

    def test_agent_add_http_accepts_unquoted_capability_values(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"provider_id": "provider-123"}

        args = cli.build_parser().parse_args(
            [
                "agent-add-http",
                "--endpoint",
                "http://127.0.0.1:8787",
                "--capability",
                "quiz.generate",
                "answer.grade",
                "--capability",
                "quiz.generate",
            ]
        )

        with (
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_add_http(args)

        self.assertEqual(posted[0][1]["capabilities"], ["quiz.generate", "answer.grade"])

    def test_agent_add_http_accepts_comma_space_capability_values_without_quotes(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"provider_id": "provider-123"}

        args = cli.build_parser().parse_args(
            [
                "agent-add-http",
                "--endpoint",
                "http://127.0.0.1:8787",
                "--capability",
                "quiz.generate,",
                "answer.grade",
            ]
        )

        with (
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_add_http(args)

        self.assertEqual(posted[0][1]["capabilities"], ["quiz.generate", "answer.grade"])

    def test_agent_add_http_rejects_empty_capability(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "agent-add-http",
                "--endpoint",
                "http://127.0.0.1:8787",
                "--capability",
                "quiz.generate, ,answer.grade",
            ]
        )

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.cmd_agent_add_http(args)

        message = str(context.exception)
        self.assertIn("Agent capability is empty", message)
        self.assertIn("omit --capability", message)

    def test_agent_add_http_rejects_non_positive_timeout(self) -> None:
        args = cli.build_parser().parse_args(
            [
                "agent-add-http",
                "--endpoint",
                "http://127.0.0.1:8787",
                "--timeout",
                "0",
            ]
        )

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.cmd_agent_add_http(args)

        self.assertIn("positive number of seconds", str(context.exception))

    def test_agent_add_http_preserves_explicit_label(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"provider_id": "provider-123"}

        args = cli.build_parser().parse_args(
            [
                "agent-add-http",
                "--label",
                "Kimi gateway",
                "--endpoint",
                "https://agent.example.test/custom/invoke",
            ]
        )

        with (
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_add_http(args)

        self.assertEqual(posted[0][1]["label"], "Kimi gateway")
        self.assertEqual(posted[0][1]["endpoint"], "https://agent.example.test/custom/invoke")

    def test_agent_add_http_success_prints_copyable_next_steps(self) -> None:
        def fake_post(path: str, payload: dict | None = None) -> dict:
            if path == "/v1/agents/providers":
                return {
                    "provider_id": "provider-123",
                    "kind": "http_agent",
                    "label": "Local gateway",
                    "endpoint": "http://127.0.0.1:8787/invoke",
                }
            return {"schema_version": "agent-v1", "providers": [], "defaults": {}}

        args = cli.build_parser().parse_args(
            ["agent-add-http", "--endpoint", "http://127.0.0.1:8787"]
        )
        stdout = StringIO()

        with patch.object(cli, "post", side_effect=fake_post), patch("sys.stdout", stdout):
            cli.cmd_agent_add_http(args)

        output = stdout.getvalue()
        self.assertIn("provider: provider-123", output)
        self.assertIn("openai_compatible_agent_gateway.py --dry-run --port 8787", output)
        self.assertIn("agent-test --provider-id provider-123", output)
        self.assertIn("agent-set-default provider-123", output)
        self.assertNotIn("agent-set-default provider-123 --all", output)

    def test_agent_add_http_success_redacts_endpoint_diagnostics(self) -> None:
        secret = "sk-" + "proj-abcdefghijklmnop123456"

        def fake_post(path: str, payload: dict | None = None) -> dict:
            if path == "/v1/agents/providers":
                return {
                    "provider_id": "provider-123",
                    "kind": "http_agent",
                    "label": f"Platform agent {secret}",
                    "endpoint": f"https://agent.example.test/invoke/{secret}?mode=demo",
                }
            return {"schema_version": "agent-v1", "providers": [], "defaults": {}}

        args = cli.build_parser().parse_args(
            ["agent-add-http", "--endpoint", "https://agent.example.test/invoke"]
        )
        stdout = StringIO()

        with patch.object(cli, "post", side_effect=fake_post), patch("sys.stdout", stdout):
            cli.cmd_agent_add_http(args)

        output = stdout.getvalue()
        self.assertIn("endpoint:", output)
        self.assertIn("label: Platform agent sk-<redacted>", output)
        self.assertIn("sk-<redacted>", output)
        self.assertNotIn("openai_compatible_agent_gateway.py --dry-run --port 8787", output)
        self.assertNotIn(secret, output)

    def test_agent_add_http_with_defaults_prints_configured_lesson_next_step(self) -> None:
        def fake_post(path: str, payload: dict | None = None) -> dict:
            if path == "/v1/agents/providers":
                return {
                    "provider_id": "provider-123",
                    "kind": "http_agent",
                    "label": "Local gateway",
                    "endpoint": "http://127.0.0.1:8787/invoke",
                }
            return {"schema_version": "agent-v1", "providers": [], "defaults": {}}

        args = cli.build_parser().parse_args(
            ["agent-add-http", "--endpoint", "http://127.0.0.1:8787", "--set-default"]
        )
        stdout = StringIO()

        with patch.object(cli, "post", side_effect=fake_post), patch("sys.stdout", stdout):
            cli.cmd_agent_add_http(args)

        output = stdout.getvalue()
        self.assertIn("defaults_configured: yes", output)
        self.assertIn("Test it: python3 scripts/study_anything_cli.py agent-test", output)
        self.assertNotIn("agent-test --provider-id provider-123", output)
        self.assertIn("--agent-mode configured", output)

    def test_agent_test_accepts_provider_id_alias(self) -> None:
        args = cli.build_parser().parse_args(["agent-test", "--provider-id", "provider-123"])

        cli.normalise_provider_id_arg(args)

        self.assertEqual(args.provider_id, "provider-123")

    def test_literal_provider_placeholder_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["agent-test", "PROVIDER_ID"])

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_provider_id_arg(args)

        message = str(context.exception)
        self.assertIn("placeholder", message)
        self.assertIn("agent-test", message)
        self.assertIn("agent-set-default", message)

    def test_agent_test_without_provider_id_is_allowed_for_default_lookup(self) -> None:
        args = cli.build_parser().parse_args(["agent-test"])

        cli.normalise_provider_id_arg(args)

        self.assertIsNone(args.provider_id)
        self.assertTrue(args.provider_id_optional)

    def test_agent_set_default_without_provider_id_is_allowed_for_default_lookup(self) -> None:
        args = cli.build_parser().parse_args(["agent-set-default", "--all"])

        cli.normalise_provider_id_arg(args)

        self.assertIsNone(args.provider_id)
        self.assertTrue(args.provider_id_optional)

    def test_agent_set_default_accepts_provider_id_alias(self) -> None:
        args = cli.build_parser().parse_args(
            ["agent-set-default", "--provider-id", "provider-123", "--all"]
        )

        cli.normalise_provider_id_arg(args)

        self.assertEqual(args.provider_id, "provider-123")
        self.assertTrue(args.all)

    def test_agent_test_provider_id_conflict_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["agent-test", "provider-a", "--provider-id", "provider-b"]
        )

        with self.assertRaisesRegex(cli.StudyAnythingError, "Use either positional PROVIDER_ID"):
            cli.normalise_provider_id_arg(args)

    def test_agent_test_gateway_failure_has_next_steps(self) -> None:
        message = cli._format_agent_test_failure(
            502,
            '{"status":"error","message":"Upstream LLM is unavailable.","diagnostic_code":"upstream_unavailable"}',
        )

        self.assertIn("user-owned Agent exit is not ready", message)
        self.assertIn("curl http://127.0.0.1:8787/health", message)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", message)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", message)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", message)
        self.assertIn("agent-add-http --set-default", message)
        self.assertIn("AGENT_LLM_API_KEY", message)

    def test_agent_test_gateway_failure_redacts_secret_diagnostics(self) -> None:
        local_home = "/Users/" + "james"
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        message = cli._format_agent_test_failure(
            502,
            json.dumps(
                {
                    "status": "error",
                    "message": (
                        "upstream failed with Authorization: Bearer "
                        f"{secret} at http://user:pass@example.test/v1?api_key={secret} "
                        f"while reading {local_home}/private/source.txt"
                    ),
                    "diagnostic_code": "upstream_unavailable",
                }
            ),
        )

        self.assertIn("Original response: HTTP 502", message)
        self.assertIn("<redacted>", message)
        self.assertIn("<local-path>", message)
        self.assertNotIn(secret, message)
        self.assertNotIn("user:pass", message)
        self.assertNotIn(local_home, message)

    def test_agent_test_gateway_failure_includes_agent_returned_next_steps(self) -> None:
        secret = "sk-" + "proj-next-step-token123456"
        message = cli._format_agent_test_failure(
            503,
            json.dumps(
                {
                    "status": "error",
                    "message": "configuration required",
                    "diagnostic_code": "configuration_required",
                    "next_steps": [
                        f"Set AGENT_LLM_API_KEY={secret}",
                        "Restart gateway",
                    ],
                }
            ),
        )

        self.assertIn("Agent-provided next steps:", message)
        self.assertIn("Set AGENT_LLM_API_KEY=sk-<redacted>", message)
        self.assertIn("Restart gateway", message)
        self.assertNotIn(secret, message)

    def test_agent_test_success_prints_human_next_steps(self) -> None:
        args = cli.build_parser().parse_args(["agent-test", "--provider-id", "provider-123"])
        cli.normalise_provider_id_arg(args)
        stdout = StringIO()

        with (
            patch.object(
                cli,
                "post",
                return_value={
                    "provider_id": "provider-123",
                    "status": "healthy",
                    "message": "HTTP agent accepted the Study Anything contract.",
                    "capabilities": ["quiz.generate", "answer.grade"],
                    "diagnostic_code": "ok",
                    "latency_ms": 7,
                    "privacy": {
                        "secrets_returned": False,
                        "endpoint_secrets_returned": False,
                        "raw_task_payload_returned": False,
                    },
                },
            ),
            patch("sys.stdout", stdout),
        ):
            cli.cmd_agent_test(args)

        output = stdout.getvalue()
        self.assertIn("provider: provider-123", output)
        self.assertIn("status: healthy", output)
        self.assertIn("diagnostic_code: ok", output)
        self.assertIn("latency_ms: 7", output)
        self.assertIn("capabilities: 2", output)
        self.assertIn("privacy: secrets_returned=no", output)
        self.assertIn("start --text 'Paste source text here.'", output)
        self.assertIn("agent-set-default provider-123", output)
        self.assertNotIn("agent-set-default provider-123 --all", output)

    def test_agent_test_unhealthy_prints_gateway_recovery(self) -> None:
        args = cli.build_parser().parse_args(["agent-test", "--provider-id", "provider-123"])
        cli.normalise_provider_id_arg(args)
        stdout = StringIO()

        with (
            patch.object(
                cli,
                "post",
                return_value={
                    "provider_id": "provider-123",
                    "status": "unhealthy",
                    "message": "HTTP agent unavailable.",
                    "capabilities": ["source.verify"],
                    "diagnostic_code": "provider_unavailable",
                    "latency_ms": 12,
                    "privacy": {
                        "secrets_returned": False,
                        "endpoint_secrets_returned": False,
                        "raw_task_payload_returned": False,
                    },
                },
            ),
            patch("sys.stdout", stdout),
        ):
            cli.cmd_agent_test(args)

        output = stdout.getvalue()
        self.assertIn("status: unhealthy", output)
        self.assertIn("curl http://127.0.0.1:8787/health", output)
        self.assertIn("openai_compatible_agent_gateway.py --dry-run --port 8787", output)
        self.assertIn("diagnose_adoption.py", output)

    def test_agent_test_result_redacts_message_diagnostics(self) -> None:
        local_home = "/Users/" + "james"
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        args = cli.build_parser().parse_args(["agent-test", "--provider-id", "provider-123"])
        cli.normalise_provider_id_arg(args)
        stdout = StringIO()

        with (
            patch.object(
                cli,
                "post",
                return_value={
                    "provider_id": "provider-123",
                    "status": "unhealthy",
                    "message": (
                        f"upstream token={secret} at "
                        f"http://user:pass@example.test/invoke?api_key={secret} "
                        f"wrote {local_home}/private/agent.log"
                    ),
                    "capabilities": [],
                    "diagnostic_code": "provider_unavailable",
                },
            ),
            patch("sys.stdout", stdout),
        ):
            cli.cmd_agent_test(args)

        output = stdout.getvalue()
        self.assertIn("message:", output)
        self.assertIn("<redacted>", output)
        self.assertIn("<local-path>", output)
        self.assertNotIn(secret, output)
        self.assertNotIn("user:pass", output)
        self.assertNotIn(local_home, output)

    def test_agent_test_json_output_stays_machine_readable(self) -> None:
        args = cli.build_parser().parse_args(
            cli.normalise_global_options(["agent-test", "--provider-id", "provider-123", "--json"])
        )
        cli.normalise_provider_id_arg(args)
        stdout = StringIO()

        with (
            patch.object(
                cli,
                "post",
                return_value={
                    "provider_id": "provider-123",
                    "status": "healthy",
                    "message": "ok",
                    "capabilities": [],
                    "diagnostic_code": "ok",
                    "privacy": {"secrets_returned": False},
                },
            ),
            patch("sys.stdout", stdout),
        ):
            cli.cmd_agent_test(args)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["provider_id"], "provider-123")
        self.assertEqual(payload["status"], "healthy")

    def test_agent_test_without_id_uses_configured_default(self) -> None:
        calls: list[tuple[str, dict | None]] = []

        def fake_request(path: str, payload: dict | None = None) -> dict:
            calls.append((path, payload))
            if path.startswith("/v1/agents/status"):
                return {
                    "schema_version": "agent-v1",
                    "providers": [{"provider_id": "provider-123", "enabled": True}],
                    "defaults": {"quiz.generate": "provider-123"},
                }
            if path == "/v1/agents/test":
                return {"provider_id": payload["provider_id"], "status": "healthy"}
            raise AssertionError(path)

        args = cli.build_parser().parse_args(["agent-test"])
        cli.normalise_provider_id_arg(args)

        with patch.object(cli, "request", side_effect=fake_request), patch("sys.stdout", StringIO()):
            cli.cmd_agent_test(args)

        self.assertEqual(calls[-1], ("/v1/agents/test", {"provider_id": "provider-123"}))

    def test_agent_test_without_id_uses_single_provider(self) -> None:
        calls: list[tuple[str, dict | None]] = []

        def fake_request(path: str, payload: dict | None = None) -> dict:
            calls.append((path, payload))
            if path.startswith("/v1/agents/status"):
                return {
                    "schema_version": "agent-v1",
                    "providers": [{"provider_id": "provider-123", "enabled": True}],
                    "defaults": {"quiz.generate": None},
                }
            if path == "/v1/agents/test":
                return {"provider_id": payload["provider_id"], "status": "healthy"}
            raise AssertionError(path)

        args = cli.build_parser().parse_args(["agent-test"])
        cli.normalise_provider_id_arg(args)

        with patch.object(cli, "request", side_effect=fake_request), patch("sys.stdout", StringIO()):
            cli.cmd_agent_test(args)

        self.assertEqual(calls[-1], ("/v1/agents/test", {"provider_id": "provider-123"}))

    def test_agent_test_without_id_no_provider_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["agent-test"])
        cli.normalise_provider_id_arg(args)

        with patch.object(
            cli,
            "request",
            return_value={"schema_version": "agent-v1", "providers": [], "defaults": {}},
        ):
            with self.assertRaisesRegex(cli.StudyAnythingError, "No Agent provider"):
                cli.cmd_agent_test(args)

    def test_agent_test_without_id_multiple_providers_needs_default(self) -> None:
        args = cli.build_parser().parse_args(["agent-test"])
        cli.normalise_provider_id_arg(args)
        status = {
            "schema_version": "agent-v1",
            "providers": [
                {"provider_id": "provider-a", "enabled": True},
                {"provider_id": "provider-b", "enabled": True},
            ],
            "defaults": {"quiz.generate": None},
        }

        with patch.object(cli, "request", return_value=status):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_agent_test(args)

        message = str(context.exception)
        self.assertIn("Multiple Agent providers", message)
        self.assertIn("agent-test --provider-id provider-a", message)
        self.assertIn("agent-set-default provider-a", message)
        self.assertNotIn("PROVIDER_ID", message)

    def test_agent_status_without_providers_prints_copyable_setup(self) -> None:
        status = {"schema_version": "agent-v1", "providers": [], "defaults": {}}
        stdout = StringIO()
        args = cli.build_parser().parse_args(["agents"])

        with patch.object(cli, "request", return_value=status), patch("sys.stdout", stdout):
            cli.cmd_agents(args)

        output = stdout.getvalue()
        self.assertIn("providers: none", output)
        self.assertIn("openai_compatible_agent_gateway.py --dry-run --port 8787", output)
        self.assertIn("agent-add-http --set-default", output)

    def test_agent_status_missing_defaults_suggests_set_default(self) -> None:
        status = {
            "schema_version": "agent-v1",
            "providers": [
                {
                    "provider_id": "provider-123",
                    "kind": "http_agent",
                    "label": "Local gateway",
                    "capabilities": ["quiz.generate"],
                    "enabled": True,
                }
            ],
            "defaults": {"quiz.generate": None},
        }
        stdout = StringIO()
        args = cli.build_parser().parse_args(["agents"])

        with patch.object(cli, "request", return_value=status), patch("sys.stdout", stdout):
            cli.cmd_agents(args)

        output = stdout.getvalue()
        self.assertIn("providers:", output)
        self.assertIn("defaults: 0/1 configured", output)
        self.assertIn("agent-set-default provider-123", output)
        self.assertNotIn("agent-set-default provider-123 --all", output)

    def test_agent_status_redacts_label_diagnostics(self) -> None:
        local_home = "/Users/" + "james"
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        status = {
            "schema_version": "agent-v1",
            "providers": [
                {
                    "provider_id": "provider-123",
                    "kind": "http_agent",
                    "label": f"Gateway {secret} {local_home}/private/agent.log",
                    "capabilities": ["quiz.generate"],
                    "enabled": True,
                }
            ],
            "defaults": {"quiz.generate": "provider-123"},
        }
        stdout = StringIO()
        args = cli.build_parser().parse_args(["agents"])

        with patch.object(cli, "request", return_value=status), patch("sys.stdout", stdout):
            cli.cmd_agents(args)

        output = stdout.getvalue()
        self.assertIn("label=Gateway sk-<redacted> <local-path>", output)
        self.assertNotIn(secret, output)
        self.assertNotIn(local_home, output)

    def test_agent_set_default_posts_all_common_capabilities(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {
                "schema_version": "agent-v1",
                "providers": [{"provider_id": "provider-123", "capabilities": []}],
                "defaults": {"quiz.generate": "provider-123"},
            }

        args = cli.build_parser().parse_args(["agent-set-default", "provider-123", "--all"])
        cli.normalise_provider_id_arg(args)

        with patch.object(cli, "post", side_effect=fake_post), patch("sys.stdout", StringIO()):
            cli.cmd_agent_set_default(args)

        self.assertEqual(len(posted), len(cli.DEFAULT_HTTP_AGENT_CAPABILITIES))
        self.assertTrue(all(path == "/v1/agents/defaults" for path, _ in posted))
        self.assertEqual(posted[0][1]["provider_id"], "provider-123")
        self.assertEqual(posted[0][1]["user_id"], "local-user")

    def test_agent_set_default_without_id_uses_configured_default(self) -> None:
        requests: list[str] = []
        posted: list[tuple[str, dict]] = []

        def fake_request(path: str) -> dict:
            requests.append(path)
            return {
                "schema_version": "agent-v1",
                "providers": [{"provider_id": "provider-123", "enabled": True}],
                "defaults": {"quiz.generate": "provider-123"},
            }

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {
                "schema_version": "agent-v1",
                "providers": [{"provider_id": "provider-123", "capabilities": []}],
                "defaults": {"quiz.generate": "provider-123"},
            }

        args = cli.build_parser().parse_args(["agent-set-default", "--all"])
        cli.normalise_provider_id_arg(args)

        with (
            patch.object(cli, "request", side_effect=fake_request),
            patch.object(cli, "post", side_effect=fake_post),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_set_default(args)

        self.assertEqual(requests, ["/v1/agents/status?user_id=local-user"])
        self.assertEqual(len(posted), len(cli.DEFAULT_HTTP_AGENT_CAPABILITIES))
        self.assertTrue(all(payload["provider_id"] == "provider-123" for _path, payload in posted))

    def test_agent_set_default_without_flags_uses_single_provider_and_common_capabilities(self) -> None:
        requests: list[str] = []
        posted: list[tuple[str, dict]] = []

        def fake_request(path: str) -> dict:
            requests.append(path)
            return {
                "schema_version": "agent-v1",
                "providers": [{"provider_id": "provider-123", "enabled": True}],
                "defaults": {},
            }

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {
                "schema_version": "agent-v1",
                "providers": [{"provider_id": "provider-123", "capabilities": []}],
                "defaults": {"quiz.generate": "provider-123"},
            }

        args = cli.build_parser().parse_args(["agent-set-default"])
        cli.normalise_provider_id_arg(args)

        with (
            patch.object(cli, "request", side_effect=fake_request),
            patch.object(cli, "post", side_effect=fake_post),
            patch("sys.stdout", StringIO()),
        ):
            cli.cmd_agent_set_default(args)

        self.assertEqual(requests, ["/v1/agents/status?user_id=local-user"])
        self.assertEqual(len(posted), len(cli.DEFAULT_HTTP_AGENT_CAPABILITIES))
        self.assertTrue(all(payload["provider_id"] == "provider-123" for _path, payload in posted))

    def test_agent_set_default_splits_dedupes_capabilities(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {
                "schema_version": "agent-v1",
                "providers": [{"provider_id": "provider-123", "capabilities": []}],
                "defaults": {"quiz.generate": "provider-123"},
            }

        args = cli.build_parser().parse_args(
            [
                "agent-set-default",
                "provider-123",
                "--capability",
                "quiz.generate,answer.grade",
                "--capability",
                "quiz.generate",
            ]
        )
        cli.normalise_provider_id_arg(args)

        with patch.object(cli, "post", side_effect=fake_post), patch("sys.stdout", StringIO()):
            cli.cmd_agent_set_default(args)

        self.assertEqual(
            [payload["capability"] for _path, payload in posted],
            ["quiz.generate", "answer.grade"],
        )

    def test_agent_set_default_defaults_to_all_common_capabilities(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {
                "schema_version": "agent-v1",
                "providers": [{"provider_id": "provider-123", "capabilities": []}],
                "defaults": {"quiz.generate": "provider-123"},
            }

        args = cli.build_parser().parse_args(["agent-set-default", "provider-123"])
        cli.normalise_provider_id_arg(args)

        with patch.object(cli, "post", side_effect=fake_post), patch("sys.stdout", StringIO()):
            cli.cmd_agent_set_default(args)

        self.assertEqual(len(posted), len(cli.DEFAULT_HTTP_AGENT_CAPABILITIES))
        self.assertTrue(all(path == "/v1/agents/defaults" for path, _payload in posted))
        self.assertTrue(all(payload["provider_id"] == "provider-123" for _path, payload in posted))

    def test_session_next_steps_prompt_answer_and_teaching_layer(self) -> None:
        summary = {
            "session_id": "session-123",
            "stage": "quiz",
            "question": {"item_id": "q1", "prompt": "What matters?"},
            "open_hitl": [],
            "discarded": False,
        }

        steps = cli.session_next_steps(summary)

        self.assertIn("answer session-123 'your answer'", steps[0])
        self.assertIn("teach --session session-123 --layer overview", steps[1])

    def test_session_next_steps_for_completed_session_include_evidence_exports(self) -> None:
        summary = {
            "session_id": "session-123",
            "stage": "completed",
            "question": None,
            "open_hitl": [],
            "discarded": False,
        }

        steps = cli.session_next_steps(summary)

        self.assertIn("mastery --session session-123", steps[0])
        self.assertIn("agent-eval-report --session session-123", steps[1])
        self.assertIn("obsidian-export --session session-123", steps[2])

    def test_second_brain_archive_file_conflict_error_is_actionable(self) -> None:
        handoff = {
            "local_archive": {
                "manifest": {"session_id": "session-123"},
                "files": [{"path": "note.md", "content": "note"}],
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "archive"
            archive_path.write_text("already a file", encoding="utf-8")
            args = cli.build_parser().parse_args(
                [
                    "second-brain-handoff",
                    "--session",
                    "session-123",
                    "--archive-dir",
                    str(archive_path),
                ]
            )
            cli.normalise_session_id_arg(args)

            with (
                patch.object(cli, "request", return_value=handoff),
                self.assertRaises(cli.StudyAnythingError) as context,
            ):
                cli.cmd_second_brain_handoff(args)

        message = str(context.exception)
        self.assertIn("Cannot create archive directory", message)
        self.assertIn("<archive-dir>", message)
        self.assertNotIn(str(archive_path), message)
        self.assertNotIn(str(Path(tmpdir)), message)

    def test_session_next_steps_for_hitl_include_resolution_command(self) -> None:
        summary = {
            "session_id": "session-123",
            "stage": "hitl",
            "question": None,
            "open_hitl": [{"task_id": "task-123"}],
            "discarded": False,
        }

        steps = cli.session_next_steps(summary)

        self.assertIn("study_anything_cli.py hitl", steps[0])
        self.assertIn("resolve --session session-123 --decision approve", steps[1])

    def test_session_next_steps_for_agent_configuration_hitl_fix_agent_first(self) -> None:
        summary = {
            "session_id": "session-123",
            "stage": "hitl",
            "question": None,
            "open_hitl": [
                {
                    "task_id": "task-123",
                    "kind": "agent.configuration_required",
                    "message": "No default agent configured for capability 'quiz.generate'.",
                }
            ],
            "discarded": False,
        }

        steps = cli.session_next_steps(summary)

        self.assertIn("agents", steps[0])
        self.assertIn("agent-add-http --set-default", steps[1])
        self.assertIn("agent-test", steps[2])
        self.assertIn("resume --session session-123", steps[3])
        self.assertFalse(any("resolve task-123" in step for step in steps))

    def test_resolve_posts_structured_decision_payload(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"session_id": "session-123"}

        args = cli.build_parser().parse_args(
            [
                "resolve",
                "task-123",
                "--session",
                "session-123",
                "--decision",
                "approve",
                "--note",
                "Looks good.",
            ]
        )
        cli.normalise_session_id_arg(args)

        with patch.object(cli, "post", side_effect=fake_post), patch.object(cli, "emit"):
            cli.cmd_resolve(args)

        self.assertEqual(posted[0][0], "/v1/hitl/task-123/resolve")
        self.assertEqual(
            posted[0][1],
            {
                "session_id": "session-123",
                "payload": {"note": "Looks good.", "decision": "approve"},
            },
        )

    def test_resolve_accepts_positional_session_without_task_id(self) -> None:
        requested: list[str] = []
        posted: list[tuple[str, dict]] = []

        def fake_request(path: str) -> dict:
            requested.append(path)
            return {
                "session_id": "session-123",
                "hitl_interrupts": [
                    {"task_id": "task-123", "status": "open", "kind": "agent.default_missing"}
                ],
            }

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"session_id": "session-123", "stage": "quiz"}

        args = cli.build_parser().parse_args(["resolve", "session-123", "--decision", "approve"])
        cli.normalise_session_id_arg(args)

        with (
            patch.object(cli, "request", side_effect=fake_request),
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
        ):
            cli.cmd_resolve(args)

        self.assertIsNone(args.task_id)
        self.assertEqual(args.session_id, "session-123")
        self.assertEqual(requested, ["/v1/sessions/session-123"])
        self.assertEqual(posted[0][0], "/v1/hitl/task-123/resolve")
        self.assertEqual(posted[0][1]["session_id"], "session-123")
        self.assertEqual(posted[0][1]["payload"]["decision"], "approve")

    def test_resolve_keeps_explicit_task_with_session_alias(self) -> None:
        args = cli.build_parser().parse_args(
            ["resolve", "task-123", "--session", "session-123", "--decision", "approve"]
        )

        cli.normalise_session_id_arg(args)

        self.assertEqual(args.task_id, "task-123")
        self.assertEqual(args.session_id, "session-123")

    def test_resolve_literal_task_placeholder_is_actionable_with_session_alias(self) -> None:
        args = cli.build_parser().parse_args(
            ["resolve", "TASK_ID", "--session", "session-123", "--decision", "approve"]
        )

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_session_id_arg(args)

        message = str(context.exception)
        self.assertIn("placeholder", message)
        self.assertIn("hitl", message)
        self.assertIn("resolve --session session-123 --decision approve", message)
        self.assertIn("resolve task-123 --session session-123", message)

    def test_resolve_literal_task_placeholder_is_actionable_without_session_alias(self) -> None:
        args = cli.build_parser().parse_args(["resolve", "TASK_ID", "--decision", "approve"])

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_session_id_arg(args)

        message = str(context.exception)
        self.assertIn("Human-review task id is still a placeholder", message)
        self.assertIn("resolve task-123 --session session-123", message)

    def test_resolve_rejects_ambiguous_two_positionals(self) -> None:
        args = cli.build_parser().parse_args(
            ["resolve", "session-123", "task-123", "--decision", "approve"]
        )

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_session_id_arg(args)

        message = str(context.exception)
        self.assertIn("ambiguous", message)
        self.assertIn("resolve session-123 --decision approve", message)
        self.assertIn("resolve task-123 --session session-123 --decision approve", message)

    def test_resolve_accepts_unquoted_multiword_note_without_task_drift(self) -> None:
        posted: list[tuple[str, dict]] = []

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"session_id": "session-123"}

        args = cli.build_parser().parse_args(
            [
                "resolve",
                "task-123",
                "--session",
                "session-123",
                "--decision",
                "approve",
                "--note",
                "Looks",
                "good.",
            ]
        )
        cli.normalise_session_id_arg(args)

        with patch.object(cli, "post", side_effect=fake_post), patch.object(cli, "emit"):
            cli.cmd_resolve(args)

        self.assertEqual(args.task_id, "task-123")
        self.assertEqual(posted[0][0], "/v1/hitl/task-123/resolve")
        self.assertEqual(posted[0][1]["payload"]["note"], "Looks good.")

    def test_resolve_without_task_id_selects_single_open_session_task(self) -> None:
        requested: list[str] = []
        posted: list[tuple[str, dict]] = []

        def fake_request(path: str) -> dict:
            requested.append(path)
            return {
                "session_id": "session-123",
                "hitl_interrupts": [
                    {"task_id": "task-old", "status": "resolved"},
                    {"task_id": "task-123", "status": "open"},
                ],
            }

        def fake_post(path: str, payload: dict | None = None) -> dict:
            posted.append((path, payload or {}))
            return {"session_id": "session-123"}

        args = cli.build_parser().parse_args(
            ["resolve", "--session", "session-123", "--decision", "approve"]
        )
        cli.normalise_session_id_arg(args)

        with (
            patch.object(cli, "request", side_effect=fake_request),
            patch.object(cli, "post", side_effect=fake_post),
            patch.object(cli, "emit"),
        ):
            cli.cmd_resolve(args)

        self.assertEqual(requested, ["/v1/sessions/session-123"])
        self.assertEqual(posted[0][0], "/v1/hitl/task-123/resolve")
        self.assertEqual(posted[0][1]["payload"]["decision"], "approve")

    def test_resolve_without_task_id_errors_when_no_open_session_task(self) -> None:
        args = cli.build_parser().parse_args(["resolve", "--session", "session-123"])
        cli.normalise_session_id_arg(args)

        with patch.object(cli, "request", return_value={"session_id": "session-123", "hitl_interrupts": []}):
            with self.assertRaisesRegex(cli.StudyAnythingError, "No open human-review task"):
                cli.cmd_resolve(args)

    def test_resolve_without_task_id_errors_when_multiple_session_tasks(self) -> None:
        args = cli.build_parser().parse_args(["resolve", "--session", "session-123"])
        cli.normalise_session_id_arg(args)

        with patch.object(
            cli,
            "request",
            return_value={
                "session_id": "session-123",
                "open_hitl": [
                    {"task_id": "task-a", "status": "open"},
                    {"task_id": "task-b", "status": "open"},
                ],
            },
        ):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_resolve(args)

        message = str(context.exception)
        self.assertIn("Multiple open human-review tasks", message)
        self.assertIn("resolve task-a --session session-123 --decision approve", message)
        self.assertNotIn("resolve TASK_ID", message)

    def test_print_session_includes_copyable_next_steps(self) -> None:
        session = {
            "session_id": "session-123",
            "stage": "quiz",
            "source": {"title": "Source"},
            "mastery": {"level": 0.0, "bloom": "remember"},
            "quiz_items": [{"item_id": "q1", "prompt": "What matters?"}],
            "answers": [],
            "grading_results": [],
            "insights": [],
            "hitl_interrupts": [],
        }
        stdout = StringIO()

        with patch("sys.stdout", stdout):
            cli.print_session(session)

        output = stdout.getvalue()
        self.assertIn("next:", output)
        self.assertIn("answer session-123 'your answer'", output)
        self.assertIn("teach --session session-123 --layer overview", output)

    def test_first_unanswered_quiz_ignores_malformed_items_without_traceback(self) -> None:
        session = {
            "answers": [{"text": "missing item id"}, "bad-answer"],
            "quiz_items": ["bad-quiz", {"prompt": "missing item id"}, {"item_id": "q1"}],
        }

        quiz = cli.first_unanswered_quiz(session)

        self.assertEqual(quiz, {"item_id": "q1"})

    def test_print_session_handles_quiz_without_prompt_without_traceback(self) -> None:
        session = {
            "session_id": "session-123",
            "stage": "quiz",
            "quiz_items": [{"item_id": "q1"}],
            "answers": [],
        }
        stdout = StringIO()

        with patch("sys.stdout", stdout):
            cli.print_session(session)

        output = stdout.getvalue()
        self.assertIn("question_id: q1", output)
        self.assertIn("question: -", output)

    def test_answer_missing_quiz_item_id_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["answer", "--session", "session-123", "--text", "answer"]
        )
        cli.normalise_session_id_arg(args)

        with patch.object(
            cli,
            "request",
            return_value={"session_id": "session-123", "quiz_items": [{"prompt": "no id"}]},
        ):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_answer(args)

        message = str(context.exception)
        self.assertIn("Session quiz response", message)
        self.assertIn("missing required unanswered quiz item with item_id", message)
        self.assertIn("show --session session-123", message)
        self.assertIn("resume --session session-123", message)
        self.assertNotIn("--session SESSION_ID", message)

    def test_demo_missing_session_id_after_run_is_actionable(self) -> None:
        def fake_post(path: str, _payload: dict | None = None) -> dict:
            if path == "/v1/sessions":
                return {"session_id": "session-123"}
            if path.endswith("/reading"):
                return {"ok": True}
            if path.endswith("/run"):
                return {"quiz_items": [{"item_id": "q1"}], "answers": []}
            raise AssertionError(path)

        args = cli.build_parser().parse_args(["demo"])

        with patch.object(cli, "post", side_effect=fake_post):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_demo(args)

        message = str(context.exception)
        self.assertIn("Demo session response", message)
        self.assertIn("missing required field: session_id", message)

    def test_lesson_missing_quiz_item_id_is_actionable(self) -> None:
        def fake_post(path: str, _payload: dict | None = None) -> dict:
            if path == "/v1/sessions":
                return {"session_id": "session-123"}
            if path.endswith("/reading"):
                return {"ok": True}
            if path.endswith("/teaching-layers"):
                return {"schema_version": "teaching-layers-v1"}
            if path.endswith("/run"):
                return {"session_id": "session-123", "quiz_items": [{"prompt": "no id"}]}
            raise AssertionError(path)

        args = cli.build_parser().parse_args(
            [
                "lesson",
                "--title",
                "Bad quiz",
                "--text",
                "source",
                "--answer",
                "answer",
                "--agent-mode",
                "demo",
            ]
        )

        with patch.object(cli, "post", side_effect=fake_post):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_lesson(args)

        message = str(context.exception)
        self.assertIn("Lesson run response", message)
        self.assertIn("missing required unanswered quiz item with item_id", message)
        self.assertIn("resume --session session-123", message)
        self.assertNotIn("--session SESSION_ID", message)

    def test_obsidian_export_wrong_shape_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["obsidian-export", "--session", "session-123"])
        cli.normalise_session_id_arg(args)

        with patch.object(cli, "request", return_value=[]):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_obsidian_export(args)

        message = str(context.exception)
        self.assertIn("Obsidian export response", message)
        self.assertIn("expected: JSON object", message)

    def test_obsidian_export_output_success_redacts_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "notes" / "session.md"
            output_path.parent.mkdir()
            args = cli.build_parser().parse_args(
                [
                    "obsidian-export",
                    "--session",
                    "session-123",
                    "--output",
                    str(output_path),
                ]
            )
            cli.normalise_session_id_arg(args)
            stdout = StringIO()

            with (
                patch.object(cli, "request", return_value={"markdown": "# Session\n"}),
                patch("sys.stdout", stdout),
            ):
                cli.cmd_obsidian_export(args)

            output = stdout.getvalue()
            self.assertEqual(output_path.read_text(encoding="utf-8"), "# Session\n")
            self.assertIn("wrote: <output-file>", output)
            self.assertNotIn(str(output_path), output)
            self.assertNotIn(str(Path(tmpdir)), output)

    def test_learning_package_output_success_redacts_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "learning-package.json"
            args = cli.build_parser().parse_args(
                [
                    "package-export",
                    "--session",
                    "session-123",
                    "--output",
                    str(output_path),
                ]
            )
            cli.normalise_session_id_arg(args)
            stdout = StringIO()

            with (
                patch.object(cli, "request", return_value={"session_id": "session-123"}),
                patch("sys.stdout", stdout),
            ):
                cli.cmd_learning_package(args)

            output = stdout.getvalue()
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["session_id"], "session-123")
            self.assertIn("wrote: <output-file>", output)
            self.assertNotIn(str(output_path), output)
            self.assertNotIn(str(Path(tmpdir)), output)

    def test_second_brain_archive_success_redacts_absolute_path(self) -> None:
        handoff = {
            "local_archive": {
                "manifest": {"session_id": "session-123"},
                "files": [{"path": "note.md", "content": "note"}],
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / "archive"
            args = cli.build_parser().parse_args(
                [
                    "second-brain-handoff",
                    "--session",
                    "session-123",
                    "--archive-dir",
                    str(archive_path),
                ]
            )
            cli.normalise_session_id_arg(args)
            stdout = StringIO()

            with (
                patch.object(cli, "request", return_value=handoff),
                patch("sys.stdout", stdout),
            ):
                cli.cmd_second_brain_handoff(args)

            output = stdout.getvalue()
            self.assertEqual((archive_path / "note.md").read_text(encoding="utf-8"), "note")
            self.assertIn("wrote: <archive-dir>", output)
            self.assertNotIn(str(archive_path), output)
            self.assertNotIn(str(Path(tmpdir)), output)

    def test_second_brain_archive_wrong_shape_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["second-brain-handoff", "--session", "session-123", "--archive-manifest"]
        )
        cli.normalise_session_id_arg(args)

        with patch.object(cli, "request", return_value={"local_archive": []}):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_second_brain_handoff(args)

        message = str(context.exception)
        self.assertIn("Second-brain handoff response", message)
        self.assertIn("missing object field: local_archive", message)

    def test_empty_sessions_print_copyable_start_commands(self) -> None:
        stdout = StringIO()
        args = cli.build_parser().parse_args(["sessions"])

        with patch.object(cli, "request", return_value=[]), patch("sys.stdout", stdout):
            cli.cmd_sessions(args)

        output = stdout.getvalue()
        self.assertIn("none", output)
        self.assertIn("study_anything_cli.py demo", output)
        self.assertIn("start --text 'Paste source text here.'", output)

    def test_sessions_list_item_wrong_shape_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["sessions"])

        with patch.object(cli, "request", return_value=["bad-session"]):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_sessions(args)

        message = str(context.exception)
        self.assertIn("Sessions list item", message)
        self.assertIn("expected: JSON object", message)

    def test_session_not_found_http_error_has_recovery_commands(self) -> None:
        message = cli._format_api_http_failure(
            404,
            "/v1/sessions/missing-session",
            '{"detail":"Session not found"}',
        )

        self.assertIn("session id was not found", message)
        self.assertIn("study_anything_cli.py sessions", message)
        self.assertIn("start --text 'Paste source text here.'", message)

    def test_agent_provider_not_found_http_error_has_recovery_commands(self) -> None:
        message = cli._format_api_http_failure(
            404,
            "/v1/agents/missing-provider/invoke",
            '{"detail":"Agent provider missing-provider is missing or disabled."}',
        )

        self.assertIn("Agent provider id was not found", message)
        self.assertIn("agent-add-http", message)
        self.assertIn("agent-add-http --label 'Local gateway' --set-default", message)
        self.assertIn("study_anything_cli.py agent-test", message)

    def test_conflict_http_error_points_to_show_events_resume(self) -> None:
        message = cli._format_api_http_failure(
            409,
            "/v1/sessions/session-123/topology/rebuild",
            '{"detail":"data is not ready for topology rebuild"}',
        )

        self.assertIn("conflicts with the current session", message)
        self.assertIn("show --session session-123", message)
        self.assertIn("events --session session-123", message)
        self.assertIn("resume --session session-123", message)
        self.assertNotIn("--session SESSION_ID", message)

    def test_conflict_http_error_uses_example_session_when_path_has_no_session(self) -> None:
        message = cli._format_api_http_failure(
            409,
            "/v1/graph/status",
            '{"detail":"runtime conflict"}',
        )

        self.assertIn("show --session session-123", message)
        self.assertNotIn("--session SESSION_ID", message)

    def test_schema_http_error_points_to_agent_contract(self) -> None:
        message = cli._format_api_http_failure(
            422,
            "/v1/agents/provider-123/invoke",
            '{"detail":"Agent result score must be a number from 0 to 1."}',
        )

        self.assertIn("rejected the request shape", message)
        self.assertIn("study_anything_cli.py agent-test", message)
        self.assertIn("docs/agent-contract.md", message)

    def test_api_http_failure_redacts_secret_diagnostics(self) -> None:
        temp_root = "/private/" + "tmp"
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        message = cli._format_api_http_failure(
            503,
            "/v1/agents/test",
            json.dumps(
                {
                    "message": (
                        f"agent returned token={secret} "
                        f"from http://user:pass@example.test/invoke?token={secret} "
                        f"and wrote {temp_root}/study-anything/trace.log"
                    )
                }
            ),
        )

        self.assertIn("API returned HTTP 503", message)
        self.assertIn("<redacted>", message)
        self.assertIn("<local-path>", message)
        self.assertNotIn(secret, message)
        self.assertNotIn("user:pass", message)
        self.assertNotIn(temp_root, message)

    def test_api_http_failure_redacts_authorization_query_diagnostics(self) -> None:
        secret = "Bearer" + "Secret123456"
        message = cli._format_api_http_failure(
            503,
            "/v1/agents/test",
            json.dumps(
                {
                    "message": (
                        "gateway failed at "
                        f"http://agent.example.test/invoke?authorization={secret}"
                    )
                }
            ),
        )

        self.assertIn("API returned HTTP 503", message)
        self.assertIn("authorization=<redacted>", message)
        self.assertNotIn(secret, message)

    def test_fastapi_validation_list_is_summarised(self) -> None:
        message = cli._format_api_http_failure(
            422,
            "/v1/sessions",
            '{"detail":[{"loc":["body","title"],"msg":"field required","type":"value_error.missing"}]}',
        )

        self.assertIn("body.title: field required", message)
        self.assertIn("--help", message)

    def test_api_unreachable_failure_has_recovery_commands(self) -> None:
        message = cli._format_api_unreachable_failure("connection refused")

        self.assertIn("./scripts/run_skill_mode_demo.sh", message)
        self.assertIn("./scripts/launch_skill_mode.sh", message)
        self.assertIn("study_anything_cli.py health", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("--api-base", message)

    def test_api_unreachable_failure_detects_localhost_socket_block(self) -> None:
        message = cli._format_api_unreachable_failure("[Errno 1] Operation not permitted")

        self.assertIn("block localhost sockets", message)
        self.assertIn("normal terminal", message)
        self.assertIn("./scripts/run_skill_mode_demo.sh", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("--api-base", message)

    def test_api_unreachable_failure_detects_permission_denied_socket_block(self) -> None:
        message = cli._format_api_unreachable_failure("[Errno 13] Permission denied")

        self.assertIn("block localhost sockets", message)
        self.assertIn("normal terminal", message)
        self.assertIn("./scripts/run_skill_mode_demo.sh", message)
        self.assertIn("--api-base", message)

    def test_api_unreachable_failure_detects_timeout(self) -> None:
        message = cli._format_api_unreachable_failure(TimeoutError("timed out"))

        self.assertIn("did not respond before the CLI timeout", message)
        self.assertIn("./scripts/run_skill_mode_demo.sh", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("--api-base", message)
        self.assertIn("./scripts/doctor.sh", message)

    def test_api_base_rejects_credentials_without_leaking_values(self) -> None:
        secret = "sk-" + "proj-abcdefghijklmnop123456"

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_api_base(f"http://user:{secret}@example.test:8000/base")

        message = str(context.exception)
        self.assertIn("must not contain inline credentials", message)
        self.assertNotIn("user:", message)
        self.assertNotIn(secret, message)

    def test_api_base_rejects_query_without_leaking_values(self) -> None:
        secret = "sk-" + "proj-abcdefghijklmnop123456"

        with self.assertRaises(cli.StudyAnythingError) as context:
            cli.normalise_api_base(f"http://example.test:8000/base?api_key={secret}#token=secret")

        message = str(context.exception)
        self.assertIn("must not include query parameters", message)
        self.assertNotIn(secret, message)
        self.assertNotIn("token=secret", message)

    def test_request_wraps_direct_oserror_without_traceback(self) -> None:
        with patch.object(cli, "urlopen", side_effect=OSError("network is unreachable")):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.request("/v1/health")

        message = str(context.exception)
        self.assertIn("Cannot reach Study Anything", message)
        self.assertIn("network is unreachable", message)
        self.assertIn("./scripts/launch_skill_mode.sh", message)

    def test_request_sends_api_token_without_putting_it_in_url(self) -> None:
        captured = []

        def fake_urlopen(request, timeout=15):
            captured.append((request, timeout))
            return FakeUrlopenResponse(b'{"status":"ok"}')

        token = "private-local-token-" + "x" * 32
        with (
            patch.dict(
                cli.os.environ,
                {
                    "STUDY_ANYTHING_API_BASE": "http://127.0.0.1:8000",
                    "STUDY_ANYTHING_API_TOKEN": token,
                },
                clear=True,
            ),
            patch.object(cli, "urlopen", side_effect=fake_urlopen),
        ):
            payload = cli.request("/v1/system/integrations")

        request = captured[0][0]
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {token}")
        self.assertNotIn(token, request.full_url)

    def test_api_401_diagnostic_points_to_private_token_configuration(self) -> None:
        message = cli._format_api_http_failure(
            401,
            "/v1/system/integrations",
            '{"detail":"A valid local API bearer token is required."}',
        )

        self.assertIn("requires its local bearer token", message)
        self.assertIn("STUDY_ANYTHING_API_TOKEN", message)
        self.assertIn("must not put it in --api-base", message)

    def test_request_socket_blocked_includes_contract_only_recovery(self) -> None:
        with patch.object(cli, "urlopen", side_effect=OSError("[Errno 1] Operation not permitted")):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.request("/v1/health")

        message = str(context.exception)
        self.assertIn("block localhost sockets", message)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", message)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", message)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", message)

    def test_request_wraps_direct_timeout_without_traceback(self) -> None:
        with patch.object(cli, "urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.request("/v1/health")

        message = str(context.exception)
        self.assertIn("did not respond before the CLI timeout", message)
        self.assertIn("Check API health", message)

    def test_request_wraps_non_json_success_response_without_traceback(self) -> None:
        with patch.object(cli, "urlopen", return_value=FakeUrlopenResponse(b"<html>wrong app</html>")):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.request("/v1/health")

        message = str(context.exception)
        self.assertIn("could not be decoded", message)
        self.assertIn("not valid JSON", message)
        self.assertIn("--api-base points to the wrong service", message)
        self.assertIn("response preview", message)
        self.assertIn("diagnose_adoption.py", message)

    def test_decode_failure_preview_redacts_secret_diagnostics(self) -> None:
        var_root = "/var/" + "folders"
        secret = "sk-" + "proj-abcdefghijklmnop123456"
        message = cli._format_api_decode_failure(
            "/v1/health",
            "response was not valid JSON",
                (
                    f"<html>token={secret} "
                    f"http://user:pass@example.test/error?api_key={secret} "
                    f"{var_root}/n0/private/log.txt</html>"
                ),
        )

        self.assertIn("response preview", message)
        self.assertIn("<redacted>", message)
        self.assertIn("<local-path>", message)
        self.assertNotIn(secret, message)
        self.assertNotIn("user:pass", message)
        self.assertNotIn(var_root, message)

    def test_request_wraps_empty_success_response_without_traceback(self) -> None:
        with patch.object(cli, "urlopen", return_value=FakeUrlopenResponse(b"")):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.request("/v1/health")

        message = str(context.exception)
        self.assertIn("response was empty", message)
        self.assertIn("python3 scripts/study_anything_cli.py health", message)

    def test_request_wraps_non_utf8_success_response_without_traceback(self) -> None:
        with patch.object(cli, "urlopen", return_value=FakeUrlopenResponse(b"\xff\xfe\x00")):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.request("/v1/health")

        message = str(context.exception)
        self.assertIn("not UTF-8", message)
        self.assertIn("diagnose_adoption.py", message)

    def test_agent_status_wrong_shape_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["agents"])

        with patch.object(cli, "request", return_value=[]):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_agents(args)

        message = str(context.exception)
        self.assertIn("Agent status response", message)
        self.assertIn("expected: JSON object", message)
        self.assertIn("CLI and API came from the same checkout", message)

    def test_sessions_wrong_shape_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["sessions"])

        with patch.object(cli, "request", return_value={"sessions": []}):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_sessions(args)

        message = str(context.exception)
        self.assertIn("Sessions list response", message)
        self.assertIn("expected: JSON array", message)
        self.assertIn("diagnose_adoption.py", message)

    def test_create_session_missing_session_id_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(["start", "--title", "Shape", "--text", "source"])

        with (
            patch.object(cli, "request", return_value={"providers": [], "defaults": {}}),
            patch.object(cli, "post", return_value={}),
            self.assertRaises(cli.StudyAnythingError) as context,
        ):
            cli.create_session(args)

        message = str(context.exception)
        self.assertIn("Session creation response", message)
        self.assertIn("missing required field: session_id", message)
        self.assertIn("API and CLI versions are mismatched", message)

    def test_agent_provider_creation_missing_provider_id_is_actionable(self) -> None:
        args = cli.build_parser().parse_args(
            ["agent-add-http", "--endpoint", "http://127.0.0.1:8787/invoke", "--set-default"]
        )

        with patch.object(cli, "post", return_value={}):
            with self.assertRaises(cli.StudyAnythingError) as context:
                cli.cmd_agent_add_http(args)

        message = str(context.exception)
        self.assertIn("Agent provider creation response", message)
        self.assertIn("missing required field: provider_id", message)
        self.assertIn("study_anything_cli.py health", message)


if __name__ == "__main__":
    unittest.main()
