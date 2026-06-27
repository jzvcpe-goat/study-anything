#!/usr/bin/env python3
"""Create a local .env file with generated self-host secrets."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = ROOT / ".env.example"
DEFAULT_OUTPUT = ROOT / ".env"


class SetupEnvError(RuntimeError):
    """Readable setup failure for first-run users."""


def redact_path(path: Path) -> str:
    return "<env-file>" if path.is_absolute() else str(path)


def redact_text(text: str, *paths: Path) -> str:
    redacted = text
    replacements: list[tuple[str, str]] = []
    for path in paths:
        if not path.is_absolute():
            continue
        path_text = str(path)
        if path_text:
            replacements.append((path_text, redact_path(path)))
        parent = path.parent
        parent_text = str(parent)
        if parent.is_absolute() and parent_text not in {"", "/"}:
            replacements.append((parent_text, "<env-dir>"))
    for path_text, replacement in sorted(set(replacements), key=lambda item: len(item[0]), reverse=True):
        redacted = redacted.replace(path_text, replacement)
    return redacted


def classify_setup_error(message: str) -> str:
    lowered = message.lower()
    if "template is missing" in lowered:
        return "template_missing"
    if "template is not utf-8" in lowered:
        return "template_not_utf8"
    if "output directory does not exist" in lowered:
        return "output_directory_missing"
    if "cannot write env file" in lowered:
        return "output_write_failed"
    if "cannot read env template" in lowered:
        return "template_unreadable"
    return "setup_env_failed"


def next_steps_for_error(code: str, example: Path, output: Path) -> list[str]:
    if code == "template_missing":
        return [
            "Run this command from the repository root.",
            "Or pass --example path/to/.env.example.",
            f"Then retry: python3 scripts/setup_env.py --example {example} --output {output}",
        ]
    if code == "output_directory_missing":
        return [
            f"Create the output parent directory: mkdir -p {output.parent}",
            f"Or choose an existing directory with --output {output}",
            f"Then validate it with: python3 scripts/check_env.py --env {output}",
        ]
    if code == "template_not_utf8":
        return [
            "Restore .env.example from the repository or save the template as UTF-8 text.",
            f"Then retry: python3 scripts/setup_env.py --example {example} --output {output}",
        ]
    return [
        "Check that the template is readable and the output path is writable.",
        f"Retry with: python3 scripts/setup_env.py --example {example} --output {output}",
        "For diagnostics after creation, run: python3 scripts/check_env.py --strict",
    ]


def setup_report(
    *,
    status: str,
    action: str,
    example: Path,
    output: Path,
    message: str,
    next_steps: list[str],
    error_code: str | None = None,
) -> dict[str, Any]:
    redacted_steps = [redact_text(step, example, output) for step in next_steps]
    report: dict[str, Any] = {
        "schema_version": "setup-env-result-v1",
        "status": status,
        "action": action,
        "output": redact_path(output),
        "example": redact_path(example),
        "message": redact_text(message, example, output),
        "next_steps": redacted_steps,
        "privacy": {
            "generated_secret_values_included": False,
            "raw_template_values_included": False,
            "local_absolute_paths_included": False,
        },
    }
    if error_code:
        report["error_code"] = error_code
    return report


def format_text_failure(code: str, message: str, example: Path, output: Path) -> str:
    lines = [
        "setup_env failed.",
        f"Classification: {code}",
        f"Diagnostic: {message}",
        "Next steps:",
    ]
    lines.extend(f"  {index}. {step}" for index, step in enumerate(next_steps_for_error(code, example, output), 1))
    lines.append(
        "Machine-readable report: "
        f"python3 scripts/setup_env.py --json --example {example} --output {output}"
    )
    return redact_text("\n".join(lines), example, output)


def print_json_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def random_secret(bytes_count: int = 24) -> str:
    return secrets.token_urlsafe(bytes_count)


def random_hex(bytes_count: int = 32) -> str:
    return secrets.token_hex(bytes_count)


def build_generated_values() -> dict[str, str]:
    postgres_password = random_secret()
    langfuse_postgres_password = random_secret()
    values = {
        "POSTGRES_PASSWORD": postgres_password,
        "DATABASE_URL": (
            "postgresql://study:"
            f"{quote(postgres_password, safe='')}@app-postgres:5432/study_anything"
        ),
        "LANGFUSE_POSTGRES_PASSWORD": langfuse_postgres_password,
        "LANGFUSE_DATABASE_URL": (
            "postgresql://postgres:"
            f"{quote(langfuse_postgres_password, safe='')}@langfuse-postgres:5432/postgres"
        ),
        "NEXTAUTH_SECRET": random_secret(32),
        "LANGFUSE_SALT": random_secret(24),
        "LANGFUSE_ENCRYPTION_KEY": random_hex(32),
        "CLICKHOUSE_PASSWORD": random_secret(),
        "MINIO_ROOT_PASSWORD": random_secret(),
        "REDIS_AUTH": random_secret(),
        "ENCRYPTION_KEY_DEV_ONLY": random_secret(32),
    }
    return values


def render_env(template: str, generated: dict[str, str]) -> str:
    lines: list[str] = []
    for line in template.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            lines.append(line)
            continue
        key, _value = line.split("=", 1)
        if key in generated:
            lines.append(f"{key}={generated[key]}")
        else:
            lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


def read_template(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SetupEnvError(
            f"Env template is missing: {path}. Run this command from the repository root, "
            "or pass --example path/to/.env.example."
        ) from exc
    except UnicodeDecodeError as exc:
        raise SetupEnvError(
            f"Env template is not UTF-8 text: {path}. Restore .env.example or pass a UTF-8 template. {exc}"
        ) from exc
    except OSError as exc:
        raise SetupEnvError(f"Cannot read env template {path}: {exc}") from exc


def write_output(path: Path, content: str) -> None:
    parent = path.parent
    if parent and not parent.exists():
        raise SetupEnvError(
            f"Output directory does not exist: {parent}. Create it first or choose another --output path."
        )
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise SetupEnvError(
            f"Cannot write env file {path}: {exc}. Check path permissions or choose another --output path."
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Study Anything .env file.")
    parser.add_argument("--example", type=Path, default=DEFAULT_EXAMPLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable redacted setup report without generated secret values.",
    )
    args = parser.parse_args()

    try:
        if args.output.exists() and not args.force:
            message = f"{args.output} already exists; leaving it unchanged. Use --force to replace it."
            if args.json:
                print_json_report(
                    setup_report(
                        status="ok",
                        action="unchanged",
                        example=args.example,
                        output=args.output,
                        message=message,
                        next_steps=[
                            f"Validate the existing file: python3 scripts/check_env.py --env {args.output}",
                            f"Regenerate only if intentional: python3 scripts/setup_env.py --force --output {args.output}",
                        ],
                    )
                )
            else:
                print(redact_text(message, args.example, args.output))
            return
        template = read_template(args.example)
        write_output(args.output, render_env(template, build_generated_values()))
    except SetupEnvError as exc:
        code = classify_setup_error(str(exc))
        if args.json:
            print_json_report(
                setup_report(
                    status="fail",
                    action="failed",
                    example=args.example,
                    output=args.output,
                    message="setup_env failed: " + str(exc),
                    next_steps=next_steps_for_error(code, args.example, args.output),
                    error_code=code,
                )
            )
        else:
            print(format_text_failure(code, str(exc), args.example, args.output), file=sys.stderr)
        raise SystemExit(1) from exc
    message = f"Created {args.output} with generated local secrets."
    if args.json:
        print_json_report(
            setup_report(
                status="ok",
                action="created",
                example=args.example,
                output=args.output,
                message=message,
                next_steps=[
                    f"Validate the generated file: python3 scripts/check_env.py --env {args.output} --strict",
                    "Start local Skill Mode: ./scripts/launch_skill_mode.sh",
                    "Or start the Docker stack: ./scripts/launch_self_host.sh",
                ],
            )
        )
    else:
        print(redact_text(message, args.example, args.output))


if __name__ == "__main__":
    main()
