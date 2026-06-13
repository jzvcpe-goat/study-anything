#!/usr/bin/env python3
"""Back up and restore a self-hosted Study Anything deployment."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterable


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "infra" / "compose" / "docker-compose.yml"
DEFAULT_ENV = ROOT / ".env"
DEFAULT_BACKUP_ROOT = ROOT / "backups"
MANIFEST_NAME = "manifest.json"
SCHEMA_VERSION = 1

CORE_VOLUME_KEYS = ("study_anything_data",)
OPTIONAL_VOLUME_KEYS = (
    "falkordb_data",
    "langfuse_postgres_data",
    "langfuse_clickhouse_data",
    "langfuse_clickhouse_logs",
    "langfuse_minio_data",
    "langfuse_redis_data",
)

ARCHIVE_VOLUME_SCRIPT = """
import pathlib
import sys
import tarfile

root = pathlib.Path("/volume")
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        archive.add(child, arcname=child.name, recursive=True)
"""

RESTORE_VOLUME_SCRIPT = """
import pathlib
import shutil
import sys
import tarfile

root = pathlib.Path("/volume")
root.mkdir(parents=True, exist_ok=True)
for child in root.iterdir():
    if child.is_dir() and not child.is_symlink():
        shutil.rmtree(child)
    else:
        child.unlink()

resolved_root = root.resolve()
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz") as archive:
    for member in archive:
        target = (root / member.name).resolve()
        if target != resolved_root and resolved_root not in target.parents:
            raise RuntimeError(f"Unsafe archive member: {member.name}")
        if member.issym() or member.islnk():
            raise RuntimeError(f"Archive links are not allowed: {member.name}")
        archive.extract(member, path=root)
"""


def run(
    command: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | int | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        check=check,
        stdin=stdin,
        stdout=subprocess.PIPE if capture_output else stdout,
        stderr=subprocess.PIPE if capture_output else None,
    )


def compose_project_name(env_file: Path) -> str | None:
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "COMPOSE_PROJECT_NAME":
            project_name = value.strip().strip("'\"")
            return project_name or None
    return None


def compose_command(env_file: Path, *args: str, profiles: Iterable[str] = ()) -> list[str]:
    command = ["docker", "compose"]
    project_name = compose_project_name(env_file)
    if project_name:
        command.extend(["--project-name", project_name])
    command.extend(["--env-file", str(env_file), "-f", str(COMPOSE_FILE)])
    for profile in profiles:
        command.extend(["--profile", profile])
    command.extend(args)
    return command


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def compose_config(env_file: Path, *, include_optional: bool) -> dict[str, Any]:
    profiles = ("full",) if include_optional else ()
    result = run(
        compose_command(env_file, "config", "--format", "json", profiles=profiles),
        capture_output=True,
    )
    return json.loads(result.stdout.decode("utf-8"))


def compose_volume_name(config: dict[str, Any], key: str) -> str:
    try:
        return str(config["volumes"][key]["name"])
    except KeyError as exc:
        raise RuntimeError(f"Compose volume {key!r} is not configured.") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def docker_ready() -> None:
    try:
        run(["docker", "info"], capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Docker daemon is not running. Start Docker Desktop, then retry.") from exc


def docker_volume_exists(name: str) -> bool:
    return run(["docker", "volume", "inspect", name], check=False, capture_output=True).returncode == 0


def ensure_docker_volume(name: str) -> None:
    if not docker_volume_exists(name):
        run(["docker", "volume", "create", name], capture_output=True)


def helper_image(env_file: Path) -> str:
    result = run(compose_command(env_file, "images", "-q", "api"), capture_output=True)
    image = result.stdout.decode("utf-8").strip()
    if not image:
        print("Building the API helper image for volume archive operations...")
        run(compose_command(env_file, "build", "api"))
        result = run(compose_command(env_file, "images", "-q", "api"), capture_output=True)
        image = result.stdout.decode("utf-8").strip()
    if not image:
        raise RuntimeError("Unable to find or build the API helper image.")
    return image.splitlines()[0]


def wait_for_postgres(env_file: Path, values: dict[str, str]) -> None:
    user = values.get("POSTGRES_USER", "study")
    database = values.get("POSTGRES_DB", "study_anything")
    running = run(
        compose_command(env_file, "ps", "--status", "running", "-q", "app-postgres"),
        capture_output=True,
    )
    if not running.stdout.decode("utf-8").strip():
        run(compose_command(env_file, "up", "-d", "app-postgres"))
    for _attempt in range(30):
        result = run(
            compose_command(
                env_file,
                "exec",
                "-T",
                "app-postgres",
                "pg_isready",
                "-U",
                user,
                "-d",
                database,
            ),
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError("Postgres did not become ready within 60 seconds.")


def dump_postgres(env_file: Path, values: dict[str, str], output: Path) -> None:
    user = values.get("POSTGRES_USER", "study")
    database = values.get("POSTGRES_DB", "study_anything")
    command = compose_command(
        env_file,
        "exec",
        "-T",
        "app-postgres",
        "pg_dump",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "-U",
        user,
        "-d",
        database,
    )
    with gzip.open(output, "wb") as target:
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        assert process.stdout is not None
        shutil.copyfileobj(process.stdout, target)
        if process.wait() != 0:
            raise RuntimeError("Postgres backup failed.")


def restore_postgres(env_file: Path, values: dict[str, str], backup: Path) -> None:
    user = values.get("POSTGRES_USER", "study")
    database = values.get("POSTGRES_DB", "study_anything")
    command = compose_command(
        env_file,
        "exec",
        "-T",
        "app-postgres",
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        user,
        "-d",
        database,
    )
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    with gzip.open(backup, "rb") as source:
        shutil.copyfileobj(source, process.stdin)
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("Postgres restore failed.")


def archive_volume(image: str, volume_name: str, output: Path) -> None:
    command = [
        "docker",
        "run",
        "--rm",
        "--volume",
        f"{volume_name}:/volume:ro",
        "--entrypoint",
        "python",
        image,
        "-c",
        ARCHIVE_VOLUME_SCRIPT,
    ]
    with output.open("wb") as target:
        run(command, stdout=target)


def restore_volume(image: str, volume_name: str, backup: Path) -> None:
    ensure_docker_volume(volume_name)
    command = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--volume",
        f"{volume_name}:/volume",
        "--entrypoint",
        "python",
        image,
        "-c",
        RESTORE_VOLUME_SCRIPT,
    ]
    with backup.open("rb") as source:
        run(command, stdin=source)


def write_manifest(backup_dir: Path, manifest: dict[str, Any]) -> None:
    target = backup_dir / MANIFEST_NAME
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target.chmod(0o600)


def verify_manifest(backup_dir: Path) -> dict[str, Any]:
    manifest_path = backup_dir / MANIFEST_NAME
    if not manifest_path.exists():
        raise RuntimeError(f"Missing {MANIFEST_NAME}.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("Unsupported backup manifest schema.")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise RuntimeError("Backup manifest files must be a list.")
    seen_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise RuntimeError("Backup manifest file records must be objects.")
        relative_path = item.get("path")
        checksum = item.get("sha256")
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise RuntimeError("Backup manifest file record is missing a safe path.")
        if relative_path in seen_paths:
            raise RuntimeError(f"Duplicate backup file in manifest: {relative_path}.")
        seen_paths.add(relative_path)
        if not _is_sha256(checksum):
            raise RuntimeError(f"Invalid sha256 for backup file: {relative_path}.")
        path = safe_backup_member_path(backup_dir, relative_path)
        if not path.is_file():
            raise RuntimeError(f"Missing backup file: {relative_path}.")
        if sha256(path) != checksum:
            raise RuntimeError(f"Checksum mismatch for backup file: {relative_path}.")
    return manifest


def file_record(backup_dir: Path, path: Path, *, role: str) -> dict[str, str]:
    try:
        relative_path = path.resolve().relative_to(backup_dir.resolve())
    except ValueError as exc:
        raise RuntimeError("Backup file records must stay inside the backup directory.") from exc
    return {
        "path": relative_path.as_posix(),
        "role": role,
        "sha256": sha256(path),
    }


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def safe_backup_member_path(backup_dir: Path, relative_path: str) -> Path:
    if "\\" in relative_path:
        raise RuntimeError(f"Unsafe backup file path: {relative_path}.")
    candidate = Path(relative_path)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise RuntimeError(f"Unsafe backup file path: {relative_path}.")
    root = backup_dir.resolve()
    target = (root / candidate).resolve()
    if target == root or root not in target.parents:
        raise RuntimeError(f"Unsafe backup file path: {relative_path}.")
    return target


def default_backup_dir() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_BACKUP_ROOT / f"study-anything-backup-{timestamp}"


def create_backup(env_file: Path, output: Path, *, include_optional: bool) -> None:
    if not env_file.is_file():
        raise RuntimeError(f"Missing {env_file}. Run `python3 scripts/setup_env.py` first.")
    docker_ready()
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    volumes_dir = output / "volumes"
    volumes_dir.mkdir(mode=0o700)

    values = parse_env(env_file)
    config = compose_config(env_file, include_optional=include_optional)
    image = helper_image(env_file)
    wait_for_postgres(env_file, values)

    env_snapshot = output / "env.snapshot"
    shutil.copy2(env_file, env_snapshot)
    env_snapshot.chmod(0o600)

    database_backup = output / "app-postgres.sql.gz"
    dump_postgres(env_file, values, database_backup)
    database_backup.chmod(0o600)

    records = [
        file_record(output, env_snapshot, role="environment"),
        file_record(output, database_backup, role="canonical-postgres"),
    ]
    archived_volumes: list[str] = []
    skipped_optional: list[str] = []
    volume_keys = CORE_VOLUME_KEYS + (OPTIONAL_VOLUME_KEYS if include_optional else ())
    for key in volume_keys:
        volume_name = compose_volume_name(config, key)
        if not docker_volume_exists(volume_name):
            if key in OPTIONAL_VOLUME_KEYS:
                skipped_optional.append(key)
                continue
            raise RuntimeError(f"Required Docker volume {volume_name!r} does not exist.")
        archive = volumes_dir / f"{key}.tar.gz"
        archive_volume(image, volume_name, archive)
        archive.chmod(0o600)
        records.append(file_record(output, archive, role=f"docker-volume:{key}"))
        archived_volumes.append(key)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "includes_optional_volumes": include_optional,
        "archived_volumes": archived_volumes,
        "skipped_optional_volumes": skipped_optional,
        "files": records,
    }
    write_manifest(output, manifest)
    print(f"Backup created at {output}")
    print("The backup contains an env.snapshot with local secrets. Store it securely.")


def restore_env_snapshot(backup_dir: Path, env_file: Path, *, restore_env: bool) -> None:
    snapshot = backup_dir / "env.snapshot"
    if not snapshot.is_file():
        raise RuntimeError(f"Missing {snapshot}.")
    if env_file.exists() and not restore_env:
        return
    env_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot, env_file)
    env_file.chmod(0o600)
    print(f"Restored environment snapshot to {env_file}")


def restore_backup(env_file: Path, backup_dir: Path, *, restore_env: bool, confirmed: bool) -> None:
    if not confirmed:
        raise RuntimeError("Restore is destructive. Re-run with --yes after checking the backup path.")
    manifest = verify_manifest(backup_dir)
    restore_env_snapshot(backup_dir, env_file, restore_env=restore_env)
    docker_ready()

    values = parse_env(env_file)
    config = compose_config(env_file, include_optional=True)
    image = helper_image(env_file)
    run(compose_command(env_file, "--profile", "full", "--profile", "smoke", "down"))

    for key in manifest.get("archived_volumes", []):
        archive = backup_dir / "volumes" / f"{key}.tar.gz"
        restore_volume(image, compose_volume_name(config, key), archive)

    wait_for_postgres(env_file, values)
    restore_postgres(env_file, values, backup_dir / "app-postgres.sql.gz")
    print("Restore completed. Start the app with ./scripts/launch_self_host.sh")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV, help="Compose environment file.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create a local self-host backup.")
    backup_parser.add_argument("--output", type=Path, default=None)
    backup_parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Archive optional Langfuse and FalkorDB volumes when they exist.",
    )

    restore_parser = subparsers.add_parser("restore", help="Restore a local self-host backup.")
    restore_parser.add_argument("backup_dir", type=Path)
    restore_parser.add_argument(
        "--restore-env",
        action="store_true",
        help="Replace an existing .env with the backed-up environment snapshot.",
    )
    restore_parser.add_argument("--yes", action="store_true", help="Confirm destructive restore.")

    args = parser.parse_args()
    try:
        if args.command == "backup":
            create_backup(
                args.env.resolve(),
                (args.output or default_backup_dir()).resolve(),
                include_optional=args.include_optional,
            )
        else:
            restore_backup(
                args.env.resolve(),
                args.backup_dir.resolve(),
                restore_env=args.restore_env,
                confirmed=args.yes,
            )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"error: {exc}") from exc


if __name__ == "__main__":
    main()
