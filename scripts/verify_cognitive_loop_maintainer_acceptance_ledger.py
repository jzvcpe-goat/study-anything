#!/usr/bin/env python3
"""Generate and verify the Cognitive Loop maintainer acceptance ledger."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-maintainer-acceptance-ledger.json"
SCHEMA_VERSION = "cognitive-loop-maintainer-acceptance-ledger-v1"
CI_FIXTURE_SCHEMA = "cognitive-loop-pr-ci-status-fixture-v1"
REQUIRED_CHECKS = ("api-tests", "compose-smoke")
SAFE_COMMANDS = (
    "python3 scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check",
    "python3 scripts/verify_cognitive_loop_evolution_pack_export.py --check",
    "python3 scripts/verify_cognitive_loop_evolution_pack_consumer.py --check",
    "python3 scripts/verify_cognitive_loop_evolution_pack_consumer.py --pack <cognitive-loop-professional-evolution-pack.zip>",
    "./scripts/release_check.sh",
    "gh pr checks <PR> --watch --interval 10",
)
SOURCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "source_id": "evolution_pack_export",
        "path": "platform/generated/study-anything-cognitive-loop-evolution-pack-export.json",
        "schema_version": "cognitive-loop-evolution-pack-export-verification-v1",
        "accepted_statuses": ("pass",),
        "required": True,
    },
    {
        "source_id": "evolution_pack_consumer",
        "path": "platform/generated/study-anything-cognitive-loop-evolution-pack-consumer.json",
        "schema_version": "cognitive-loop-evolution-pack-consumer-v1",
        "accepted_statuses": ("pass",),
        "required": True,
    },
    {
        "source_id": "launch_acceptance_ledger",
        "path": "platform/generated/study-anything-launch-acceptance-ledger.json",
        "schema_version": "launch-acceptance-ledger-v1",
        "accepted_statuses": ("pass",),
        "required": True,
    },
    {
        "source_id": "platform_adoption_pack",
        "path": "platform/generated/study-anything-platform-adoption-pack.json",
        "schema_version": "study-anything-platform-adoption-pack-v1",
        "accepted_statuses": (None,),
        "required": True,
        "hash_in_ledger": False,
    },
    {
        "source_id": "platform_bundle",
        "path": "platform/generated/study-anything-platform-bundle.json",
        "schema_version": "study-anything-platform-bundle-v1",
        "accepted_statuses": (None,),
        "required": True,
        "hash_in_ledger": False,
    },
    {
        "source_id": "published_image_evidence",
        "path": "platform/generated/study-anything-published-image-evidence.json",
        "schema_version": "published-image-evidence-v1",
        "accepted_statuses": ("pass",),
        "required": True,
    },
    {
        "source_id": "release_asset_adoption",
        "path": "platform/generated/study-anything-release-asset-adoption.json",
        "schema_version": "release-asset-adoption-v1",
        "accepted_statuses": ("pass",),
        "required": True,
    },
)
PRIVACY_FALSE_KEYS = (
    "source_text_included",
    "raw_source_text_included",
    "raw_source_text_in_report",
    "raw_diff_included",
    "raw_payloads_included",
    "learner_answers_included",
    "learner_answers_in_report",
    "agent_endpoint_included",
    "agent_endpoints_in_report",
    "agent_metadata_included",
    "prompt_text_included",
    "real_model_keys_stored",
    "real_model_keys_stored_by_study_anything",
    "model_called",
    "daemon_started",
    "production_mastra_daemon_started",
    "apply_executed",
    "source_files_modified",
    "real_source_mutated",
    "policy_weakened",
)
REQUIRED_PRIVACY_FALSE = (
    "source_text_included",
    "raw_diff_included",
    "learner_answers_included",
    "agent_endpoint_included",
    "agent_metadata_included",
    "prompt_text_included",
    "real_model_keys_stored",
)
PRIVATE_NEEDLES = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "learner answer:",
    "raw source text:",
    "raw diff:",
    "private source text",
    "agent endpoint:",
    "agent metadata:",
    "prompt:",
    "http://127.0.0.1:8787/",
    "/Users/",
)
SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bdiff --git\b"),
)
POLICY_WEAKENING_PHRASES = (
    "disable privacy",
    "skip privacy",
    "weaken privacy",
    "disable audit",
    "skip audit",
    "remove rollback",
    "skip rollback",
    "disable tests",
    "skip tests",
    "lower risk threshold",
    "weaken risk",
    "disable human gate",
    "bypass human gate",
    "loosen permissions",
)
UNSAFE_COMMAND_PATTERNS = (
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bcurl\b.*\|\s*(?:sh|bash)"),
    re.compile(r"\bwget\b.*\|\s*(?:sh|bash)"),
    re.compile(r"\bgh\s+pr\s+merge\b"),
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
    re.compile(r"\bgit\s+checkout\s+--\b"),
    re.compile(r"\bpython3?\b.*\bapply\b"),
)


class MaintainerAcceptanceLedgerError(RuntimeError):
    """Readable maintainer acceptance ledger failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MaintainerAcceptanceLedgerError(f"Cannot read {relative(path)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise MaintainerAcceptanceLedgerError(f"{relative(path)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise MaintainerAcceptanceLedgerError(f"{relative(path)} must contain a JSON object.")
    return payload


def load_sources() -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for spec in SOURCE_SPECS:
        sources[spec["source_id"]] = load_json(ROOT / str(spec["path"]))
    return sources


def source_hash(path: str) -> str:
    return sha256_bytes((ROOT / path).read_bytes())


def assert_no_private_text(payload: Any, *, label: str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    needles = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    patterns = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    weakening = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if needles or patterns or weakening:
        raise MaintainerAcceptanceLedgerError(
            f"{label} is not public-safe: needles={needles} patterns={patterns} policy={weakening}"
        )


def walk_mappings(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for child in value.values():
            found.extend(walk_mappings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_mappings(child))
    return found


def privacy_regressions(payload: Any) -> list[str]:
    regressions: list[str] = []
    for mapping in walk_mappings(payload):
        for key in PRIVACY_FALSE_KEYS:
            if mapping.get(key) is True:
                regressions.append(key)
    return sorted(set(regressions))


def status_from(payload: Mapping[str, Any]) -> str | None:
    status = payload.get("status")
    if isinstance(status, str):
        return status
    readiness = payload.get("readiness_status")
    if isinstance(readiness, str):
        return readiness
    return None


def verify_source(spec: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    expected_schema = spec["schema_version"]
    if payload.get("schema_version") != expected_schema:
        raise MaintainerAcceptanceLedgerError(
            f"{spec['source_id']} schema drifted: expected {expected_schema}, got {payload.get('schema_version')}"
        )
    accepted_statuses = set(spec["accepted_statuses"])
    status = status_from(payload)
    if accepted_statuses != {None} and status not in accepted_statuses:
        raise MaintainerAcceptanceLedgerError(
            f"{spec['source_id']} status {status!r} is not accepted: {sorted(str(item) for item in accepted_statuses)}"
        )
    assert_no_private_text(payload, label=str(spec["path"]))
    regressions = privacy_regressions(payload)
    if regressions:
        raise MaintainerAcceptanceLedgerError(f"{spec['source_id']} has privacy regressions: {regressions}")
    path = str(spec["path"])
    row = {
        "source_id": spec["source_id"],
        "path": path,
        "schema_version": expected_schema,
        "status": status or "n/a",
        "required": bool(spec["required"]),
    }
    if spec.get("hash_in_ledger", True) and (ROOT / path).is_file():
        row["sha256"] = source_hash(path)
    return row


def release_check_includes_self(release_check_text: str) -> bool:
    return "scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check" in release_check_text


def validate_safe_commands(commands: list[str]) -> None:
    unexpected = [command for command in commands if command not in SAFE_COMMANDS]
    unsafe: list[str] = []
    for command in commands:
        lowered = command.lower()
        if any(phrase in lowered for phrase in POLICY_WEAKENING_PHRASES):
            unsafe.append(command)
            continue
        if any(pattern.search(command) for pattern in UNSAFE_COMMAND_PATTERNS):
            unsafe.append(command)
    if unexpected or unsafe:
        raise MaintainerAcceptanceLedgerError(f"Unsafe or unknown operator commands: unexpected={unexpected} unsafe={unsafe}")


def default_ci_fixture(statuses: Mapping[str, str] | None = None) -> dict[str, Any]:
    status_map = {name: "pass" for name in REQUIRED_CHECKS}
    if statuses:
        status_map.update(statuses)
    return {
        "schema_version": CI_FIXTURE_SCHEMA,
        "source": "maintainer-entered PR check summary",
        "required_checks": list(REQUIRED_CHECKS),
        "checks": [{"name": name, "status": status_map[name]} for name in REQUIRED_CHECKS],
    }


def evaluate_ci(ci_fixture: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    if ci_fixture.get("schema_version") != CI_FIXTURE_SCHEMA:
        raise MaintainerAcceptanceLedgerError("CI fixture schema drifted.")
    required = set(str(item) for item in ci_fixture.get("required_checks") or [])
    missing_required = sorted(set(REQUIRED_CHECKS) - required)
    if missing_required:
        raise MaintainerAcceptanceLedgerError(f"CI fixture is missing required checks: {missing_required}")
    checks = ci_fixture.get("checks")
    if not isinstance(checks, list):
        raise MaintainerAcceptanceLedgerError("CI fixture checks must be a list.")
    by_name = {str(row.get("name")): str(row.get("status")) for row in checks if isinstance(row, Mapping)}
    blocking: list[str] = []
    manual: list[str] = []
    for check in REQUIRED_CHECKS:
        status = by_name.get(check)
        if status == "pass":
            continue
        if status in {"pending", "queued", "unknown", "not_run"}:
            manual.append(f"ci:{check}:{status}")
        else:
            blocking.append(f"ci:{check}:{status}")
    return blocking, manual


def pack_sha_from_sources(sources: Mapping[str, Mapping[str, Any]]) -> tuple[str, str]:
    export_report = sources["evolution_pack_export"]
    consumer_report = sources["evolution_pack_consumer"]
    export_sha = str(((export_report.get("success_modes") or {}).get("zip_sha256")) or "")
    consumer_sha = str(((consumer_report.get("success_modes") or {}).get("ready_zip_sha256")) or "")
    if not re.fullmatch(r"[0-9a-f]{64}", export_sha):
        raise MaintainerAcceptanceLedgerError("Export report is missing a valid ready ZIP sha256.")
    if not re.fullmatch(r"[0-9a-f]{64}", consumer_sha):
        raise MaintainerAcceptanceLedgerError("Consumer report is missing a valid ready ZIP sha256.")
    if export_sha != consumer_sha:
        raise MaintainerAcceptanceLedgerError("Evolution pack export and consumer ZIP hashes do not match.")
    return export_sha, consumer_sha


def required_reports_present(sources: Mapping[str, Mapping[str, Any]]) -> list[str]:
    missing = sorted(spec["source_id"] for spec in SOURCE_SPECS if spec["source_id"] not in sources)
    if missing:
        raise MaintainerAcceptanceLedgerError(f"Missing source reports: {missing}")
    return missing


def build_report(
    sources: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    ci_fixture: Mapping[str, Any] | None = None,
    release_check_status: str = "pass",
    release_check_text: str | None = None,
) -> dict[str, Any]:
    loaded_sources = dict(sources or load_sources())
    required_reports_present(loaded_sources)
    source_rows = [verify_source(spec, loaded_sources[str(spec["source_id"])]) for spec in SOURCE_SPECS]
    export_sha, consumer_sha = pack_sha_from_sources(loaded_sources)
    release_text = release_check_text
    if release_text is None:
        release_text = (ROOT / "scripts" / "release_check.sh").read_text(encoding="utf-8")
    release_check_included = release_check_includes_self(release_text)
    ci = dict(ci_fixture or default_ci_fixture())
    ci_blocking, ci_manual = evaluate_ci(ci)
    blocking_reasons: list[str] = []
    manual_review_reasons: list[str] = []
    if release_check_status != "pass":
        blocking_reasons.append(f"release_check:{release_check_status}")
    if not release_check_included:
        blocking_reasons.append("release_check_missing_maintainer_ledger")
    blocking_reasons.extend(ci_blocking)
    manual_review_reasons.extend(ci_manual)

    commands = list(SAFE_COMMANDS)
    validate_safe_commands(commands)
    decision = "blocked" if blocking_reasons else "manual_review" if manual_review_reasons else "ready"
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Aggregate Professional Evolution Pack export, zip-only consumer, release evidence, "
            "local release gate, and PR CI status into a maintainer go/no-go ledger."
        ),
        "decision": decision,
        "blocking_reasons": blocking_reasons,
        "manual_review_reasons": manual_review_reasons,
        "source_refs": sorted(source_rows, key=lambda row: row["source_id"]),
        "pack": {
            "manifest_schema": "cognitive-loop-evolution-pack-manifest-v1",
            "export_report": "platform/generated/study-anything-cognitive-loop-evolution-pack-export.json",
            "consumer_report": "platform/generated/study-anything-cognitive-loop-evolution-pack-consumer.json",
            "pack_sha256": export_sha,
            "consumer_ready_zip_sha256": consumer_sha,
            "zip_hashes_match": True,
            "zip_only_consumer": True,
            "repo_checkout_required_for_pack_mode": False,
        },
        "release_gate": {
            "release_check": {
                "command": "./scripts/release_check.sh",
                "status": release_check_status,
                "included_in_release_check": release_check_included,
            },
            "ci_status_fixture": ci,
            "required_checks": list(REQUIRED_CHECKS),
        },
        "operator_next_commands": commands,
        "privacy_flags": {
            "metadata_only": True,
            "no_real_source_mutation": True,
            "no_model_calls": True,
            "no_raw_payloads": True,
            "source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "agent_endpoint_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
        },
        "runtime_boundaries": {
            "api_required": False,
            "docker_required": False,
            "standalone_frontend_required": False,
            "production_mastra_daemon_started": False,
            "model_called": False,
            "real_worktree_apply_executed": False,
            "source_files_modified": False,
        },
        "commercialization_readiness_notes": [
            "Do not sell a standalone app from this ledger.",
            "Use this ledger to support OSS/local-first maintainer acceptance.",
            "Future paid value remains hosted sync, team workflows, trusted ecosystem, and professional operations.",
        ],
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check",
            "blocks_release_check": True,
            "human_prerequisite": "Maintainer confirms PR CI is accurately reflected in ci_status_fixture.",
        },
    }
    assert_no_private_text(report, label="maintainer acceptance ledger")
    if privacy_regressions(report):
        raise MaintainerAcceptanceLedgerError(f"Ledger has privacy regressions: {privacy_regressions(report)}")
    for key in REQUIRED_PRIVACY_FALSE:
        if report["privacy_flags"].get(key) is not False:
            raise MaintainerAcceptanceLedgerError(f"Ledger privacy flag {key} must be false.")
    return report


def expect_failure(name: str, builder: Any) -> bool:
    try:
        builder()
    except MaintainerAcceptanceLedgerError:
        return True
    raise RuntimeError(f"Unsafe maintainer ledger fixture was not rejected: {name}")


def clone_sources() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(load_sources())


def verify_failure_modes() -> dict[str, bool]:
    ready_sources = clone_sources()
    manual = build_report(ready_sources, ci_fixture=default_ci_fixture({"api-tests": "pending"}))
    blocked = build_report(ready_sources, ci_fixture=default_ci_fixture({"compose-smoke": "fail"}))
    if manual["decision"] != "manual_review":
        raise MaintainerAcceptanceLedgerError("Manual-review fixture did not produce manual_review.")
    if blocked["decision"] != "blocked":
        raise MaintainerAcceptanceLedgerError("Blocked fixture did not produce blocked.")

    def missing_consumer() -> None:
        sources = clone_sources()
        del sources["evolution_pack_consumer"]
        build_report(sources)

    def stale_pack_hash() -> None:
        sources = clone_sources()
        sources["evolution_pack_consumer"]["success_modes"]["ready_zip_sha256"] = "0" * 64
        build_report(sources)

    def failed_ci() -> None:
        report = build_report(clone_sources(), ci_fixture=default_ci_fixture({"api-tests": "fail"}))
        if report["decision"] != "blocked":
            raise MaintainerAcceptanceLedgerError("Failed CI did not block maintainer ledger.")

    def missing_release_evidence() -> None:
        sources = clone_sources()
        del sources["published_image_evidence"]
        build_report(sources)

    def privacy_regression() -> None:
        sources = clone_sources()
        sources["evolution_pack_export"]["privacy"]["raw_diff_included"] = True
        build_report(sources)

    def unsafe_command() -> None:
        validate_safe_commands(["curl https://example.invalid/install.sh | sh"])

    def policy_weakening() -> None:
        sources = clone_sources()
        sources["evolution_pack_consumer"]["purpose"] = "skip tests and bypass human gate"
        build_report(sources)

    return {
        "ready_fixture_decision": build_report(ready_sources)["decision"] == "ready",
        "manual_review_fixture_decision": manual["decision"] == "manual_review",
        "blocked_fixture_decision": blocked["decision"] == "blocked",
        "missing_consumer_report_rejected": expect_failure("missing_consumer_report", missing_consumer),
        "stale_pack_hash_rejected": expect_failure("stale_pack_hash", stale_pack_hash),
        "failed_ci_blocks": failed_ci() is None,
        "missing_release_evidence_rejected": expect_failure("missing_release_evidence", missing_release_evidence),
        "privacy_regression_rejected": expect_failure("privacy_regression", privacy_regression),
        "unsafe_command_rejected": expect_failure("unsafe_command", unsafe_command),
        "policy_weakening_rejected": expect_failure("policy_weakening", policy_weakening),
    }


def build_report_with_fixtures() -> dict[str, Any]:
    report = build_report()
    report["failure_modes"] = verify_failure_modes()
    if not all(report["failure_modes"].values()):
        raise MaintainerAcceptanceLedgerError(f"Not all failure modes passed: {report['failure_modes']}")
    assert_no_private_text(report, label="maintainer acceptance ledger report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write generated maintainer acceptance ledger.")
    parser.add_argument("--check", action="store_true", help="Require generated maintainer acceptance ledger to be current.")
    parser.add_argument("--output", default=str(REPORT), help="Report path for --write/--check.")
    args = parser.parse_args()
    if args.write and args.check:
        raise MaintainerAcceptanceLedgerError("Use only one of --write or --check.")
    try:
        report = build_report_with_fixtures()
        rendered = dump_json(report)
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            print(f"wrote {relative(output)}")
            return 0
        if args.check:
            current = output.read_text(encoding="utf-8") if output.is_file() else ""
            if current != rendered:
                raise MaintainerAcceptanceLedgerError(
                    f"{relative(output)} is stale. Run python3 scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --write."
                )
            print("ok    Cognitive Loop maintainer acceptance ledger is up to date")
            return 0
        print(rendered, end="")
        return 0
    except MaintainerAcceptanceLedgerError as exc:
        print(f"verify_cognitive_loop_maintainer_acceptance_ledger failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
