#!/usr/bin/env python3
"""Validate local environment settings before launch or release."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = ROOT / ".env"
HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")

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


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Study Anything .env safety.")
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on weak defaults even outside APP_ENV=production.",
    )
    args = parser.parse_args()

    if not args.env.exists():
        raise SystemExit(f"Missing {args.env}. Run `python3 scripts/setup_env.py` first.")

    values = parse_env(args.env)
    app_env = values.get("APP_ENV", "development").lower()
    strict = args.strict or app_env == "production"
    problems: list[str] = []
    warnings: list[str] = []

    for key in SECRET_KEYS:
        value = values.get(key, "")
        if value in WEAK_VALUES or value.startswith("change-me"):
            target = problems if strict else warnings
            target.append(f"{key} is still a default or placeholder value.")

    encryption_key = values.get("LANGFUSE_ENCRYPTION_KEY", "")
    if encryption_key and not HEX_64.match(encryption_key):
        problems.append("LANGFUSE_ENCRYPTION_KEY must be a 64-character hex string.")

    if values.get("SESSION_STORE") == "postgres" and not values.get("DATABASE_URL"):
        problems.append("SESSION_STORE=postgres requires DATABASE_URL.")

    for warning in warnings:
        print(f"warn  {warning}")
    if problems:
        for problem in problems:
            print(f"fail  {problem}", file=sys.stderr)
        raise SystemExit(1)
    print(f"ok    {args.env} is valid for APP_ENV={app_env}.")


if __name__ == "__main__":
    main()
