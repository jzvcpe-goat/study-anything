#!/usr/bin/env python3
"""Verify support bundle replay evidence, fixtures, and pack inclusion."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from localhost_diagnostics import redact_diagnostic


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "platform-support-bundle-replay-evidence-v1"
REPLAY_SCHEMA_VERSION = "platform-support-bundle-replay-v1"
BUNDLE_SCHEMA_VERSION = "platform-support-bundle-v1"
RELEASE_VERSION = "v0.3.29-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-platform-support-bundle-replay.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
REPLAY_SCRIPT = "scripts/replay_support_bundle.py"
GENERATOR_SCRIPT = "scripts/generate_platform_support_bundle_replay.py"

REQUIRED_FIELDS = {
    "release_version",
    "platform_id",
    "runtime",
    "failure_class",
    "workflow_stage",
    "command_ran",
    "diagnostic_code",
    "redacted_log_excerpt",
    "next_commands_tried",
    "recommended_next_steps",
    "replay_command",
    "redaction_flags",
}

FIXTURE_EXPECTATIONS = {
    "local-ghcr-pull-timeout": "local_ghcr_pull_timeout",
    "cleanroom-runtime-launch-failed": "runtime_launch_failed",
    "privacy-contract-violation": "privacy_contract_violation",
}

FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
    "full_support_bundle_payload",
]


class SupportBundleReplayVerificationError(RuntimeError):
    """Readable support bundle replay verification failure."""


def format_cli_failure(exc: BaseException) -> str:
    diagnostic = redact_diagnostic(str(exc))
    return "\n".join(
        [
            f"verify_platform_support_bundle_replay failed: {diagnostic}",
            "",
            "Next steps:",
            "1. Regenerate the support-bundle replay assets: python3 scripts/generate_platform_support_bundle_replay.py",
            "2. Re-run a known replay fixture: python3 scripts/replay_support_bundle.py --bundle fixtures/platform-support-bundles/local-ghcr-pull-timeout.json",
            "3. Verify the current adoption pack: python3 scripts/verify_platform_support_bundle_replay.py --pack platform/generated/study-anything-platform-adoption-pack.zip",
            "4. If this came from a user report, ask for a redacted bundle from: python3 scripts/diagnose_adoption.py",
        ]
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SupportBundleReplayVerificationError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SupportBundleReplayVerificationError(f"JSON object expected: {path}")
    return value


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise SupportBundleReplayVerificationError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise SupportBundleReplayVerificationError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise SupportBundleReplayVerificationError(
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
        raise SupportBundleReplayVerificationError(
            f"Unsafe path escapes pack root: {relative_path}"
        ) from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise SupportBundleReplayVerificationError(
            f"Required support bundle replay asset is missing: {relative_path}"
        )
    return target


def assert_no_leaks(payload: Any, *, allow_privacy_fixture: bool = False) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks and not allow_privacy_fixture:
        raise SupportBundleReplayVerificationError(
            f"Support bundle replay asset leaked private data: {leaks}"
        )


def run_replay(root: Path, bundle_path: str, expected: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            sys.executable,
            str(require_file(root, REPLAY_SCRIPT)),
            "--bundle",
            str(require_file(root, bundle_path)),
            "--expect-classification",
            expected,
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if expected == "privacy_contract_violation":
        if completed.returncode != 2:
            raise SupportBundleReplayVerificationError(
                f"Privacy replay should exit 2, got {completed.returncode}: {completed.stderr}"
            )
    elif completed.returncode != 0:
        raise SupportBundleReplayVerificationError(
            f"Support bundle replay failed for {bundle_path}: {completed.stderr}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SupportBundleReplayVerificationError(
            f"Support bundle replay did not emit JSON for {bundle_path}: {completed.stdout}"
        ) from exc
    if payload.get("schema_version") != REPLAY_SCHEMA_VERSION:
        raise SupportBundleReplayVerificationError("Replay schema drifted.")
    if payload.get("classification") != expected:
        raise SupportBundleReplayVerificationError(
            f"Replay classification drifted for {bundle_path}: {payload.get('classification')}"
        )
    if "## Study Anything support bundle replay" not in str(payload.get("issue_body") or ""):
        raise SupportBundleReplayVerificationError(f"Replay issue body missing for {bundle_path}.")
    if expected != "privacy_contract_violation":
        assert_no_leaks(payload)
    return payload


def validate_fixture(root: Path, fixture_id: str, expected: str) -> dict[str, Any]:
    relative_path = f"fixtures/platform-support-bundles/{fixture_id}.json"
    payload = read_json(require_file(root, relative_path))
    if payload.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise SupportBundleReplayVerificationError(f"{relative_path} schema drifted.")
    if payload.get("release_version") != RELEASE_VERSION:
        raise SupportBundleReplayVerificationError(f"{relative_path} version drifted.")
    missing = REQUIRED_FIELDS - set(payload)
    if missing:
        raise SupportBundleReplayVerificationError(f"{relative_path} missing fields: {sorted(missing)}")
    if not isinstance(payload.get("next_commands_tried"), list) or not payload["next_commands_tried"]:
        raise SupportBundleReplayVerificationError(f"{relative_path} must include next_commands_tried.")
    if not isinstance(payload.get("recommended_next_steps"), list) or not payload["recommended_next_steps"]:
        raise SupportBundleReplayVerificationError(f"{relative_path} must include recommended_next_steps.")
    flags = payload.get("redaction_flags") or {}
    if expected == "privacy_contract_violation":
        if not any(value is True for value in flags.values()):
            raise SupportBundleReplayVerificationError("Privacy fixture must include a true leak flag.")
    else:
        if any(value is not False for value in flags.values()):
            raise SupportBundleReplayVerificationError(f"{relative_path} has unsafe redaction flags.")
        assert_no_leaks(payload)
    replay = run_replay(root, relative_path, expected)
    return {
        "fixture_id": fixture_id,
        "path": relative_path,
        "expected_classification": expected,
        "replay_status": replay.get("status"),
    }


def validate_report(root: Path) -> dict[str, Any]:
    report = read_json(
        require_file(root, "platform/generated/study-anything-platform-support-bundle-replay.json")
    )
    if report.get("schema_version") != SCHEMA_VERSION:
        raise SupportBundleReplayVerificationError("Support bundle replay evidence schema drifted.")
    if report.get("version") != RELEASE_VERSION:
        raise SupportBundleReplayVerificationError("Support bundle replay evidence version drifted.")
    if report.get("status") != "pass":
        raise SupportBundleReplayVerificationError("Support bundle replay evidence must pass.")
    schemas = report.get("schemas") or {}
    if schemas.get("support_bundle") != BUNDLE_SCHEMA_VERSION:
        raise SupportBundleReplayVerificationError("Support bundle schema reference drifted.")
    if schemas.get("maintainer_replay") != REPLAY_SCHEMA_VERSION:
        raise SupportBundleReplayVerificationError("Maintainer replay schema reference drifted.")
    if set(report.get("required_bundle_fields") or []) != REQUIRED_FIELDS:
        raise SupportBundleReplayVerificationError("Required bundle fields drifted.")
    refs = report.get("fixture_refs")
    if not isinstance(refs, list) or len(refs) != len(FIXTURE_EXPECTATIONS):
        raise SupportBundleReplayVerificationError("Support bundle fixture count drifted.")
    if {str(item.get("fixture_id")) for item in refs if isinstance(item, dict)} != set(FIXTURE_EXPECTATIONS):
        raise SupportBundleReplayVerificationError("Support bundle fixture ids drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key, value in privacy.items():
        if key == "fixtures_are_mock_only":
            if value is not True:
                raise SupportBundleReplayVerificationError("Fixtures must be mock-only.")
        elif value is not False:
            raise SupportBundleReplayVerificationError(f"Privacy assertion must be false: {key}")
    assert_no_leaks(report)
    fixture_results = [
        validate_fixture(root, fixture_id, expected)
        for fixture_id, expected in FIXTURE_EXPECTATIONS.items()
    ]
    require_file(root, GENERATOR_SCRIPT)
    require_file(root, REPLAY_SCRIPT)
    return {
        "schema_version": report.get("schema_version"),
        "version": report.get("version"),
        "fixture_count": len(fixture_results),
        "blocked_privacy_fixture": any(
            item["expected_classification"] == "privacy_contract_violation"
            and item["replay_status"] == "blocked"
            for item in fixture_results
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--pack", default=None)
    parser.add_argument("--pack-root", default=None)
    args = parser.parse_args()

    if args.check:
        generated = subprocess.run(
            [sys.executable, str(ROOT / GENERATOR_SCRIPT), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if generated.returncode != 0:
            raise SupportBundleReplayVerificationError(generated.stderr or generated.stdout)

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = resolve_pack_root(args, Path(tmp_dir))
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": "pass",
            "support_bundle_replay": validate_report(root),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(format_cli_failure(exc), file=sys.stderr)
        sys.exit(1)
