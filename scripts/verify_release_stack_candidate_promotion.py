#!/usr/bin/env python3
"""Verify that release stack intake candidates were safely promoted into the manifest."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from verify_release_stack_intake_candidate import (
    SOURCE_SCHEMA_VERSION,
    normalize_checks,
    normalize_merge_commit,
    reject_private_text,
    reject_raw_payloads,
)
from verify_release_stack_readiness import (
    MANIFEST,
    REQUIRED_CHECKS,
    ROOT,
    VERSION,
    ReleaseStackReadinessError,
    current_group,
    load_json,
    verify_manifest,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-release-stack-candidate-promotion.json"
PR_217_SOURCE = ROOT / "fixtures" / "release-stack" / "pr-217-intake-candidate.json"
PR_218_SOURCE = ROOT / "fixtures" / "release-stack" / "pr-218-intake-candidate.json"
REPORT_SCHEMA_VERSION = "release-stack-candidate-promotion-v1"
PROMOTED_GROUP_ID = "release-stack-promotion-v0.3.107-v0.3.108"
PREVIOUS_CURRENT_GROUP_ID = "release-stack-promotion-v0.3.105-v0.3.106"
GENERATED_AT = "2026-01-01T00:00:00Z"
SAFE_OPERATOR_COMMANDS = {
    "python3 scripts/verify_release_stack_readiness.py",
    "python3 scripts/verify_release_stack_manifest_fixtures.py --check",
    "python3 scripts/verify_release_stack_intake_candidate.py --check",
    "python3 scripts/verify_release_stack_candidate_promotion.py --check",
    "python3 scripts/verify_release_stack_live_status.py",
    "python3 scripts/verify_release_stack_lineage.py",
    "python3 scripts/verify_release_stack_merge_runbook.py --report-only",
    "./scripts/release_check.sh",
}
POST_MERGE_EVIDENCE_REFS = [
    "platform/generated/study-anything-release-stack-intake-candidate.json",
    "platform/generated/study-anything-release-stack-manifest-fixtures.json",
    "platform/generated/study-anything-platform-bundle.json",
    "platform/generated/study-anything-platform-adoption-pack.json",
    "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json",
]
PR_217_EVIDENCE_REFS = [
    "platform/generated/study-anything-release-stack-intake-candidate.json",
    "platform/generated/study-anything-release-stack-manifest-fixtures.json",
    "platform/generated/study-anything-release-stack-candidate-promotion.json",
    "platform/generated/study-anything-platform-bundle.json",
    "platform/generated/study-anything-platform-adoption-pack.json",
    "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json",
]
PR_218_EVIDENCE_REFS = [
    "platform/generated/study-anything-release-stack-intake-candidate.json",
    "platform/generated/study-anything-release-stack-candidate-promotion.json",
    "platform/generated/study-anything-platform-bundle.json",
    "platform/generated/study-anything-platform-adoption-pack.json",
    "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json",
]
PRIVACY_ASSERTIONS = {
    "metadata_only": True,
    "github_tokens_included": False,
    "job_logs_included": False,
    "check_annotations_included": False,
    "live_check_payloads_included": False,
    "source_mutation_performed": False,
    "raw_source_text_included": False,
    "learner_answers_included": False,
    "agent_endpoint_secrets_included": False,
    "real_model_keys_included": False,
}
PRIVATE_NEEDLES = (
    "gho_",
    "ghp_",
    "github_pat_",
    "sk-proj-",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "raw log:",
    "job log:",
    "artifact:",
    "annotation:",
    "raw source text:",
    "learner answer:",
    "agent endpoint:",
)


class ReleaseStackPromotionError(RuntimeError):
    """Readable release stack promotion failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def redact(text: str) -> str:
    redacted = text
    for needle in PRIVATE_NEEDLES:
        redacted = re.sub(re.escape(needle), "<redacted>", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._-]+", r"\1<redacted>", redacted)
    redacted = re.sub(r"github_pat_[A-Za-z0-9_]+", "<redacted>", redacted)
    redacted = re.sub(r"gh[op]_[A-Za-z0-9_]+", "<redacted>", redacted)
    redacted = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "<redacted>", redacted)
    return redacted


def reject_private_payload(payload: Any, label: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    lowered = serialized.lower()
    hits = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    if hits:
        raise ReleaseStackPromotionError(f"{label} contains private or unsafe text: {hits}")


def relative_ref_exists(ref: str) -> bool:
    path = Path(ref)
    return not path.is_absolute() and ".." not in path.parts and (ROOT / path).exists()


def validate_refs(refs: list[str], label: str) -> None:
    if not refs:
        raise ReleaseStackPromotionError(f"{label} must include evidence refs.")
    missing = [ref for ref in refs if not relative_ref_exists(ref)]
    if missing:
        raise ReleaseStackPromotionError(f"{label} has missing or unsafe evidence refs: {missing}")


def validate_commands(commands: Any) -> list[str]:
    if not isinstance(commands, list) or not commands:
        raise ReleaseStackPromotionError("promotion operator_commands must be a non-empty list.")
    normalized = [str(command) for command in commands]
    unsafe = [command for command in normalized if command not in SAFE_OPERATOR_COMMANDS]
    if unsafe:
        raise ReleaseStackPromotionError(f"promotion operator_commands contains unsafe commands: {unsafe}")
    return normalized


def load_source_row(
    source: Mapping[str, Any],
    *,
    expected_pr: int,
    order: int,
    evidence_refs: list[str],
    require_promotion_commands: bool,
) -> dict[str, Any]:
    if source.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise ReleaseStackPromotionError(f"PR #{expected_pr} source schema_version drifted.")
    reject_private_text(source, f"PR #{expected_pr} promotion source")
    reject_raw_payloads(source)
    reject_private_payload(source, f"PR #{expected_pr} promotion source")
    if source.get("pr_number") != expected_pr:
        raise ReleaseStackPromotionError(f"PR #{expected_pr} promotion source must describe PR #{expected_pr}.")
    if source.get("base_branch") != "main" or source.get("state") != "MERGED":
        raise ReleaseStackPromotionError(f"PR #{expected_pr} promotion source must be merged into main.")
    if require_promotion_commands:
        commands = validate_commands(source.get("operator_commands"))
        for command in (
            "python3 scripts/verify_release_stack_intake_candidate.py --check",
            "python3 scripts/verify_release_stack_candidate_promotion.py --check",
        ):
            if command not in commands:
                raise ReleaseStackPromotionError(f"PR #{expected_pr} promotion source missing operator command: {command}")
    checks = normalize_checks(source)
    row = {
        "order": order,
        "pr": expected_pr,
        "branch": str(source.get("head_branch")),
        "base": "main",
        "status_expected_before_merge": "checks_pass",
        "final_state": "MERGED",
        "merge_commit": normalize_merge_commit(source),
        "required_checks": checks,
        "evidence_refs": list(evidence_refs),
    }
    validate_refs(row["evidence_refs"], f"PR #{expected_pr} evidence_refs")
    return row


def expected_group(pr_217_source: Mapping[str, Any], pr_218_source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "group_id": PROMOTED_GROUP_ID,
        "role": "current",
        "status": "completed",
        "target_branch": "main",
        "summary": "Completed release stack maintenance chain for release-stack promotion and self-intake continuity.",
        "required_checks": sorted(REQUIRED_CHECKS),
        "operator_commands": [
            "python3 scripts/verify_release_stack_readiness.py",
            "python3 scripts/verify_release_stack_manifest_fixtures.py --check",
            "python3 scripts/verify_release_stack_intake_candidate.py --check",
            "python3 scripts/verify_release_stack_candidate_promotion.py --check",
            "python3 scripts/verify_release_stack_live_status.py",
            "python3 scripts/verify_release_stack_lineage.py",
            "python3 scripts/verify_release_stack_merge_runbook.py --report-only",
            "./scripts/release_check.sh",
        ],
        "post_merge_evidence_refs": list(POST_MERGE_EVIDENCE_REFS),
        "stack": [
            load_source_row(
                pr_217_source,
                expected_pr=217,
                order=1,
                evidence_refs=PR_217_EVIDENCE_REFS,
                require_promotion_commands=False,
            ),
            load_source_row(
                pr_218_source,
                expected_pr=218,
                order=2,
                evidence_refs=PR_218_EVIDENCE_REFS,
                require_promotion_commands=True,
            ),
        ],
        "privacy_assertions": dict(PRIVACY_ASSERTIONS),
    }


def find_group(manifest: Mapping[str, Any], group_id: str) -> dict[str, Any]:
    groups = manifest.get("stack_groups")
    if not isinstance(groups, list):
        raise ReleaseStackPromotionError("manifest stack_groups must be a list.")
    matches = [group for group in groups if isinstance(group, dict) and group.get("group_id") == group_id]
    if len(matches) != 1:
        raise ReleaseStackPromotionError(f"manifest group {group_id!r} must exist exactly once.")
    return matches[0]


def all_manifest_prs(manifest: Mapping[str, Any]) -> list[int]:
    prs: list[int] = []
    for group in manifest.get("stack_groups", []):
        if not isinstance(group, Mapping):
            continue
        for row in group.get("stack", []):
            if isinstance(row, Mapping) and isinstance(row.get("pr"), int):
                prs.append(row["pr"])
    return prs


def assert_no_duplicate_prs(manifest: Mapping[str, Any]) -> None:
    prs = all_manifest_prs(manifest)
    duplicates = sorted({pr for pr in prs if prs.count(pr) > 1})
    if duplicates:
        raise ReleaseStackPromotionError(f"manifest contains duplicate promoted PRs: {duplicates}")


def verify_promoted_manifest(
    manifest: dict[str, Any],
    pr_217_source: Mapping[str, Any],
    pr_218_source: Mapping[str, Any],
) -> dict[str, Any]:
    reject_private_payload(manifest, "release stack manifest")
    try:
        readiness = verify_manifest(manifest)
    except ReleaseStackReadinessError as exc:
        raise ReleaseStackPromotionError(str(exc)) from exc
    if manifest.get("current_group") != PROMOTED_GROUP_ID:
        raise ReleaseStackPromotionError(f"manifest current_group must be {PROMOTED_GROUP_ID}.")
    previous = find_group(manifest, PREVIOUS_CURRENT_GROUP_ID)
    if previous.get("role") != "archived" or previous.get("status") != "archived":
        raise ReleaseStackPromotionError("previous current group must be archived after promotion.")
    previous_prs = [row.get("pr") for row in previous.get("stack", []) if isinstance(row, Mapping)]
    if previous_prs != [215, 216]:
        raise ReleaseStackPromotionError("previous current group must retain PR #215-#216 audit rows.")

    expected = expected_group(pr_217_source, pr_218_source)
    actual = find_group(manifest, PROMOTED_GROUP_ID)
    if actual != expected:
        raise ReleaseStackPromotionError("promoted current group does not match the expected #217/#218 candidate group.")
    if manifest.get("stack") != expected["stack"]:
        raise ReleaseStackPromotionError("top-level stack must mirror promoted current group stack.")
    validate_commands(actual.get("operator_commands"))
    validate_refs(actual.get("post_merge_evidence_refs", []), "promoted post_merge_evidence_refs")
    assert_no_duplicate_prs(manifest)
    return readiness


def run_negative_case(
    case_id: str,
    mutator: Any,
    manifest: dict[str, Any],
    pr_217_source: Mapping[str, Any],
    pr_218_source: Mapping[str, Any],
) -> dict[str, str]:
    payload = copy.deepcopy(manifest)
    mutator(payload)
    try:
        verify_promoted_manifest(payload, pr_217_source, pr_218_source)
    except ReleaseStackPromotionError as exc:
        return {"case_id": case_id, "status": "rejected", "error": redact(str(exc))}
    raise ReleaseStackPromotionError(f"Negative promotion fixture was not rejected: {case_id}")


def sync_top_level_stack(manifest: dict[str, Any]) -> None:
    group = find_group(manifest, PROMOTED_GROUP_ID)
    manifest["stack"] = copy.deepcopy(group["stack"])


def negative_fixtures(
    manifest: dict[str, Any],
    pr_217_source: Mapping[str, Any],
    pr_218_source: Mapping[str, Any],
) -> list[dict[str, str]]:
    def duplicate_pr(payload: dict[str, Any]) -> None:
        group = find_group(payload, PROMOTED_GROUP_ID)
        duplicate = copy.deepcopy(group["stack"][0])
        duplicate["order"] = len(group["stack"]) + 1
        group["stack"].append(duplicate)
        sync_top_level_stack(payload)

    def missing_merge_commit(payload: dict[str, Any]) -> None:
        group = find_group(payload, PROMOTED_GROUP_ID)
        group["stack"][1]["merge_commit"] = "not-a-sha"
        sync_top_level_stack(payload)

    def failed_required_check(payload: dict[str, Any]) -> None:
        group = find_group(payload, PROMOTED_GROUP_ID)
        group["stack"][1]["required_checks"]["api-tests"] = "failed"
        sync_top_level_stack(payload)

    def missing_required_check(payload: dict[str, Any]) -> None:
        group = find_group(payload, PROMOTED_GROUP_ID)
        group["stack"][1]["required_checks"].pop("compose-smoke", None)
        sync_top_level_stack(payload)

    def unsafe_command(payload: dict[str, Any]) -> None:
        find_group(payload, PROMOTED_GROUP_ID)["operator_commands"].append(
            "gh api repos/jzvcpe-goat/study-anything/actions/jobs/1/logs"
        )

    def secret_payload(payload: dict[str, Any]) -> None:
        find_group(payload, PROMOTED_GROUP_ID)["summary"] = "github_pat_unsafe raw log: do not store"

    def manifest_regression(payload: dict[str, Any]) -> None:
        payload["current_group"] = PREVIOUS_CURRENT_GROUP_ID

    cases = [
        ("already_represented_pr", duplicate_pr),
        ("missing_merge_commit", missing_merge_commit),
        ("failed_required_check", failed_required_check),
        ("missing_required_check", missing_required_check),
        ("unsafe_command", unsafe_command),
        ("secret_log_artifact_payload", secret_payload),
        ("manifest_regression", manifest_regression),
    ]
    return [run_negative_case(case_id, mutator, manifest, pr_217_source, pr_218_source) for case_id, mutator in cases]


def build_report(manifest: dict[str, Any], pr_217_source: Mapping[str, Any], pr_218_source: Mapping[str, Any]) -> dict[str, Any]:
    readiness = verify_promoted_manifest(manifest, pr_217_source, pr_218_source)
    current = current_group(manifest)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "generated_at": GENERATED_AT,
        "source_reports": [
            "fixtures/release-stack/pr-217-intake-candidate.json",
            "fixtures/release-stack/pr-218-intake-candidate.json",
            "platform/release-stack.json",
        ],
        "promotion": {
            "previous_current_group": PREVIOUS_CURRENT_GROUP_ID,
            "previous_current_group_archived": True,
            "current_group": PROMOTED_GROUP_ID,
            "promoted_prs": [row["pr"] for row in current["stack"]],
            "top_level_stack_mirrors_current": True,
        },
        "readiness": {
            "schema_version": readiness["schema_version"],
            "status": readiness["status"],
            "current_group": readiness["current_group"],
            "archived_group_count": readiness["archived_group_count"],
            "stack_prs": readiness["stack_prs"],
        },
        "negative_fixtures": negative_fixtures(manifest, pr_217_source, pr_218_source),
        "privacy": {
            "metadata_only": True,
            "github_tokens_stored": False,
            "job_logs_stored": False,
            "check_annotations_stored": False,
            "artifacts_stored": False,
            "live_check_payloads_stored": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "source_mutation_performed": False,
        },
    }
    reject_private_payload(report, "release stack promotion report")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--pr-217-source", type=Path, default=PR_217_SOURCE)
    parser.add_argument("--pr-218-source", type=Path, default=PR_218_SOURCE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_json(args.manifest)
    pr_217_source = load_json(args.pr_217_source)
    pr_218_source = load_json(args.pr_218_source)
    report = build_report(manifest, pr_217_source, pr_218_source)
    text = dump_json(report)
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
        return
    if args.check:
        if not REPORT.exists():
            raise ReleaseStackPromotionError(f"promotion report missing: {REPORT.relative_to(ROOT)}")
        if REPORT.read_text(encoding="utf-8") != text:
            raise ReleaseStackPromotionError(
                "Release stack candidate promotion report is stale. Run: "
                "python3 scripts/verify_release_stack_candidate_promotion.py --write"
            )
        print("ok    release stack candidate promotion report is up to date")
        return
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_stack_candidate_promotion failed: {redact(str(exc))}", file=sys.stderr)
        sys.exit(1)
