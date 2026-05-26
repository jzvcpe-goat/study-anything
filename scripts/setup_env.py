#!/usr/bin/env python3
"""Create a local .env file with generated self-host secrets."""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = ROOT / ".env.example"
DEFAULT_OUTPUT = ROOT / ".env"


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Study Anything .env file.")
    parser.add_argument("--example", type=Path, default=DEFAULT_EXAMPLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        raise SystemExit(f"{args.output} already exists. Use --force to replace it.")
    template = args.example.read_text(encoding="utf-8")
    args.output.write_text(render_env(template, build_generated_values()), encoding="utf-8")
    print(f"Created {args.output} with generated local secrets.")


if __name__ == "__main__":
    main()
