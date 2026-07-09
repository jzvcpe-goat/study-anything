#!/usr/bin/env python3
"""Verify negative fixtures for the release-stack archive manifest."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from typing import Any, Callable

from verify_release_stack_readiness import MANIFEST, ROOT, ReleaseStackReadinessError, load_json, verify_manifest


REPORT = ROOT / "platform" / "generated" / "study-anything-release-stack-manifest-fixtures.json"
SCHEMA_VERSION = "release-stack-manifest-fixtures-v1"


class ReleaseStackManifestFixtureError(RuntimeError):
    """Readable release stack manifest fixture failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def selected_current_group(manifest: dict[str, Any]) -> dict[str, Any]:
    current_id = manifest.get("current_group")
    groups = manifest.get("stack_groups")
    if not isinstance(groups, list):
        raise ReleaseStackManifestFixtureError("canonical manifest must include stack_groups.")
    for group in groups:
        if isinstance(group, dict) and group.get("group_id") == current_id:
            return group
    raise ReleaseStackManifestFixtureError("canonical manifest current_group was not found.")


def sync_top_level_stack(manifest: dict[str, Any]) -> None:
    manifest["stack"] = copy.deepcopy(selected_current_group(manifest)["stack"])


def mutate_missing_current_group(manifest: dict[str, Any]) -> None:
    manifest.pop("current_group", None)


def mutate_wrong_merge_commit_shape(manifest: dict[str, Any]) -> None:
    group = selected_current_group(manifest)
    group["stack"][0]["merge_commit"] = "abc123"
    sync_top_level_stack(manifest)


def mutate_missing_required_check(manifest: dict[str, Any]) -> None:
    group = selected_current_group(manifest)
    group["stack"][0]["required_checks"].pop("compose-smoke", None)
    sync_top_level_stack(manifest)


def mutate_unsafe_command(manifest: dict[str, Any]) -> None:
    group = selected_current_group(manifest)
    group["operator_commands"].append("gh api repos/jzvcpe-goat/study-anything/actions/jobs/1/logs")


def mutate_privacy_flag_regression(manifest: dict[str, Any]) -> None:
    selected_current_group(manifest)["privacy_assertions"]["github_tokens_included"] = True


def mutate_stale_current_status(manifest: dict[str, Any]) -> None:
    selected_current_group(manifest)["status"] = "archived"


def mutate_stale_archived_status(manifest: dict[str, Any]) -> None:
    for group in manifest.get("stack_groups", []):
        if isinstance(group, dict) and group.get("role") == "archived":
            group["status"] = "completed"
            return
    raise ReleaseStackManifestFixtureError("canonical manifest does not include an archived group.")


CASES: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
    ("missing_current_group", mutate_missing_current_group),
    ("wrong_merge_commit_shape", mutate_wrong_merge_commit_shape),
    ("missing_required_check", mutate_missing_required_check),
    ("unsafe_command", mutate_unsafe_command),
    ("privacy_flag_regression", mutate_privacy_flag_regression),
    ("stale_current_status", mutate_stale_current_status),
    ("stale_archived_status", mutate_stale_archived_status),
)


def run_case(case_id: str, mutator: Callable[[dict[str, Any]], None], canonical: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(canonical)
    mutator(payload)
    try:
        verify_manifest(payload)
    except ReleaseStackReadinessError as exc:
        return {
            "case_id": case_id,
            "status": "rejected",
            "error": str(exc),
        }
    raise ReleaseStackManifestFixtureError(f"Negative fixture {case_id} unexpectedly passed.")


def build_report() -> dict[str, Any]:
    canonical = load_json(MANIFEST)
    canonical_report = verify_manifest(canonical)
    cases = [run_case(case_id, mutator, canonical) for case_id, mutator in CASES]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "source_manifest": "platform/release-stack.json",
        "canonical_schema_version": canonical_report["schema_version"],
        "canonical_status": canonical_report["status"],
        "current_group": canonical_report["current_group"],
        "case_count": len(cases),
        "case_ids": [case["case_id"] for case in cases],
        "cases": cases,
        "privacy": {
            "github_tokens_stored": False,
            "job_logs_stored": False,
            "live_check_payloads_stored": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    text = dump_json(report)
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(text, encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
        return
    if args.check:
        if not REPORT.exists():
            raise ReleaseStackManifestFixtureError(f"Fixture report missing: {REPORT.relative_to(ROOT)}")
        if REPORT.read_text(encoding="utf-8") != text:
            raise ReleaseStackManifestFixtureError(
                "Release stack manifest fixture report is stale. Run "
                "`python3 scripts/verify_release_stack_manifest_fixtures.py --write`."
            )
        print("ok    release stack manifest fixture report is up to date")
        return
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_stack_manifest_fixtures failed: {exc}", file=sys.stderr)
        sys.exit(1)
