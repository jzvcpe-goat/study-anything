#!/usr/bin/env python3
"""Generate and verify locked Python supply-chain artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "uv.lock"
PYPROJECT = ROOT / "pyproject.toml"
RECEIPT_FILE = ROOT / "platform/generated/study-anything-python-supply-chain.json"
SBOM_FILE = ROOT / "platform/generated/study-anything-python-sbom.cdx.json"
MINIMUM_UV_VERSION = (0, 11, 18)
SCHEMA_VERSION = "python-supply-chain-receipt-v1"
DEFAULT_TIMEOUT_SECONDS = 600

REQUIREMENT_EXPORTS: tuple[tuple[Path, tuple[str, ...]], ...] = (
    (
        ROOT / "requirements/locked-skill.txt",
        ("--extra", "crypto", "--group", "build"),
    ),
    (
        ROOT / "requirements/locked-full.txt",
        ("--extra", "full", "--group", "build"),
    ),
    (
        ROOT / "requirements/locked-dev-full.txt",
        ("--extra", "full", "--extra", "dev", "--group", "build"),
    ),
)


class PythonSupplyChainError(RuntimeError):
    """Readable supply-chain generation failure."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PythonSupplyChainError(message)


def parse_uv_version(text: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"uv (\d+)\.(\d+)\.(\d+)(?:[-+].*)?", text.strip())
    require(match is not None, "Cannot parse uv version")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def resolve_uv() -> str:
    uv = os.environ.get("STUDY_ANYTHING_UV") or shutil.which("uv")
    require(bool(uv), "uv is required; install uv 0.11.18 or newer")
    try:
        completed = subprocess.run(
            [str(uv), "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PythonSupplyChainError("Cannot execute uv") from exc
    require(completed.returncode == 0, "uv --version failed")
    require(
        parse_uv_version(completed.stdout) >= MINIMUM_UV_VERSION,
        "uv 0.11.18 or newer is required",
    )
    return str(uv)


def run_uv(uv: str, args: Sequence[str], *, timeout_seconds: int) -> None:
    env = os.environ.copy()
    env.setdefault("UV_PYTHON_DOWNLOADS", "never")
    env.setdefault("UV_HTTP_TIMEOUT", "60")
    env.setdefault("UV_HTTP_RETRIES", "3")
    try:
        completed = subprocess.run(
            [uv, *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PythonSupplyChainError(
            f"uv {' '.join(args[:2])} timed out after {timeout_seconds}s"
        ) from exc
    except OSError as exc:
        raise PythonSupplyChainError("Cannot execute uv") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-1600:]
        raise PythonSupplyChainError(
            f"uv {' '.join(args[:2])} failed: {detail or 'no diagnostic output'}"
        )


def requirement_package_count(text: str) -> int:
    return sum(
        1
        for line in text.splitlines()
        if line and not line[0].isspace() and not line.startswith(("#", "-"))
    )


def validate_requirements_text(text: str, *, label: str) -> int:
    require("--hash=sha256:" in text, f"{label} does not contain hashes")
    require("file://" not in text, f"{label} contains a local file URL")
    require(" @ http" not in text, f"{label} contains a direct HTTP dependency")
    require("/Users/" not in text, f"{label} contains a local absolute path")
    blocks = re.split(r"\n(?=\S)", text.strip())
    package_blocks = [block for block in blocks if block and not block.startswith(("#", "-"))]
    require(package_blocks, f"{label} does not contain packages")
    for block in package_blocks:
        first_line = block.splitlines()[0]
        require("==" in first_line, f"{label} contains an unpinned requirement: {first_line}")
        require("--hash=sha256:" in block, f"{label} contains a package without a hash")
    return requirement_package_count(text)


def validate_sbom(payload: Mapping[str, Any]) -> int:
    require(payload.get("bomFormat") == "CycloneDX", "SBOM must use CycloneDX")
    require(payload.get("specVersion") == "1.5", "SBOM must use CycloneDX 1.5")
    components = payload.get("components")
    require(isinstance(components, list) and components, "SBOM components are missing")
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    require("/Users/" not in serialized, "SBOM contains a local absolute path")
    require(str(ROOT) not in serialized, "SBOM contains the repository path")
    return len(components)


def export_artifacts(
    uv: str,
    destination: Path,
    *,
    timeout_seconds: int,
) -> dict[Path, bytes]:
    outputs: dict[Path, bytes] = {}
    for target, selectors in REQUIREMENT_EXPORTS:
        temp_target = destination / target.name
        run_uv(
            uv,
            (
                "export",
                "--offline",
                "--locked",
                "--no-progress",
                "--format",
                "requirements.txt",
                "--no-dev",
                "--no-emit-project",
                *selectors,
                "--output-file",
                str(temp_target),
            ),
            timeout_seconds=timeout_seconds,
        )
        payload = temp_target.read_bytes()
        validate_requirements_text(payload.decode("utf-8"), label=relative(target))
        outputs[target] = payload

    temp_sbom = destination / SBOM_FILE.name
    run_uv(
        uv,
        (
            "export",
            "--offline",
            "--locked",
            "--no-progress",
            "--format",
            "cyclonedx1.5",
            "--no-dev",
            "--all-extras",
            "--group",
            "build",
            "--output-file",
            str(temp_sbom),
        ),
        timeout_seconds=timeout_seconds,
    )
    sbom_payload = json.loads(temp_sbom.read_text(encoding="utf-8"))
    require(isinstance(sbom_payload, Mapping), "SBOM root must be an object")
    validate_sbom(sbom_payload)
    outputs[SBOM_FILE] = (
        json.dumps(sbom_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return outputs


def build_receipt(outputs: Mapping[Path, bytes]) -> dict[str, Any]:
    lock_bytes = LOCK_FILE.read_bytes()
    lock_payload = tomllib.loads(lock_bytes.decode("utf-8"))
    packages = lock_payload.get("package")
    require(isinstance(packages, list) and packages, "uv.lock packages are missing")
    sbom_payload = json.loads(outputs[SBOM_FILE])
    requirement_records = []
    for path, _selectors in REQUIREMENT_EXPORTS:
        text = outputs[path].decode("utf-8")
        requirement_records.append(
            {
                "path": relative(path),
                "sha256": sha256_bytes(outputs[path]),
                "package_count": validate_requirements_text(text, label=relative(path)),
                "hashes_required": True,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "python_support": ">=3.11,<3.13",
        "lock": {
            "path": relative(LOCK_FILE),
            "sha256": sha256_bytes(lock_bytes),
            "package_count": len(packages),
            "universal_cross_platform": True,
        },
        "pyproject_sha256": sha256_bytes(PYPROJECT.read_bytes()),
        "requirements": requirement_records,
        "sbom": {
            "path": relative(SBOM_FILE),
            "sha256": sha256_bytes(outputs[SBOM_FILE]),
            "format": "CycloneDX",
            "spec_version": "1.5",
            "component_count": validate_sbom(sbom_payload),
        },
        "advisory_review": {
            "github_dependency_review_integrated": True,
            "online_advisory_query_performed": False,
            "known_default_branch_advisory_count_asserted": False,
        },
        "privacy": {
            "metadata_only": True,
            "local_absolute_paths_included": False,
            "environment_values_included": False,
            "raw_source_text_included": False,
            "secrets_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "This receipt proves lock freshness, hash-bound exported requirements, and a generated "
            "CycloneDX dependency inventory. It does not prove every package is vulnerability-free, "
            "that every package index is trustworthy, or that an online advisory query ran locally."
        ),
    }


def compare_or_write(path: Path, payload: bytes, *, refresh: bool) -> None:
    if refresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return
    require(path.exists(), f"Generated artifact is missing: {relative(path)}")
    require(path.read_bytes() == payload, f"Generated artifact is stale: {relative(path)}")


def generate(*, refresh: bool, timeout_seconds: int) -> dict[str, Any]:
    uv = resolve_uv()
    require(PYPROJECT.exists(), "pyproject.toml is missing")
    if refresh:
        run_uv(uv, ("lock", "--no-progress"), timeout_seconds=timeout_seconds)
    else:
        require(LOCK_FILE.exists(), "uv.lock is missing")
        run_uv(
            uv,
            ("lock", "--check", "--offline", "--no-progress"),
            timeout_seconds=min(timeout_seconds, 60),
        )
    with tempfile.TemporaryDirectory(prefix="study-anything-supply-chain-") as tmp:
        outputs = export_artifacts(uv, Path(tmp), timeout_seconds=timeout_seconds)
    receipt = build_receipt(outputs)
    receipt_bytes = (
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    for path, payload in outputs.items():
        compare_or_write(path, payload, refresh=refresh)
    compare_or_write(RECEIPT_FILE, receipt_bytes, refresh=refresh)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    args = parser.parse_args()
    require(args.timeout_seconds > 0, "--timeout-seconds must be positive")
    try:
        receipt = generate(refresh=args.refresh, timeout_seconds=args.timeout_seconds)
    except PythonSupplyChainError as exc:
        print(f"generate_python_supply_chain failed: {exc}", file=os.sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
