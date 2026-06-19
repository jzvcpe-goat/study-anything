#!/usr/bin/env python3
"""Verify the offline GitHub release stack archive manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "platform" / "release-stack.json"
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"
SCHEMA_VERSION = "study-anything-release-stack-v1"
REPORT_SCHEMA_VERSION = "release-stack-readiness-v1"
VERSION = "v0.3.31-alpha"
REQUIRED_CHECKS = {"api-tests", "compose-smoke"}
REQUIRED_BEFORE_TAG = {
    "python3 scripts/verify_release_stack_readiness.py",
    "python3 scripts/verify_release_stack_manifest_fixtures.py --check",
    "./scripts/release_check.sh",
    "python3 scripts/verify_launch_acceptance_ledger.py --check",
    "python3 scripts/verify_github_launch_operator_guide.py --check",
    "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
}
SAFE_OPERATOR_COMMANDS = {
    "python3 scripts/verify_release_stack_readiness.py",
    "python3 scripts/verify_release_stack_manifest_fixtures.py --check",
    "python3 scripts/verify_release_stack_live_status.py",
    "python3 scripts/verify_release_stack_lineage.py",
    "python3 scripts/verify_release_stack_merge_runbook.py --report-only",
    "python3 scripts/verify_cognitive_loop_pr_ci_receipt.py --check",
    "python3 scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check",
    "./scripts/release_check.sh",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PRIVATE_NEEDLES = (
    "gho_",
    "ghp_",
    "github_pat_",
    "sk-proj-",
    "secret_access_key",
    "bearer ",
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "Private source text:",
    "Private answer:",
)
FALSE_PRIVACY_FLAGS = (
    "github_tokens_included",
    "job_logs_included",
    "check_annotations_included",
    "live_check_payloads_included",
    "source_mutation_performed",
    "raw_source_text_included",
    "learner_answers_included",
    "agent_endpoint_secrets_included",
    "real_model_keys_included",
)


class ReleaseStackReadinessError(RuntimeError):
    """Readable release stack readiness verification failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReleaseStackReadinessError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseStackReadinessError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseStackReadinessError(f"{path.relative_to(ROOT)} must contain a JSON object.")
    return payload


def reject_private_text(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle.lower() in serialized]
    if leaked:
        raise ReleaseStackReadinessError(f"Release stack manifest contains private or secret-like text: {leaked}")


def validate_privacy(payload: dict[str, Any], label: str) -> dict[str, Any]:
    privacy = payload.get("privacy_assertions")
    if not isinstance(privacy, dict):
        raise ReleaseStackReadinessError(f"{label}.privacy_assertions must be an object.")
    if privacy.get("metadata_only") is not True:
        raise ReleaseStackReadinessError(f"{label}.privacy_assertions.metadata_only must be true.")
    for key in FALSE_PRIVACY_FLAGS:
        if privacy.get(key) is not False:
            raise ReleaseStackReadinessError(f"{label}.privacy_assertions.{key} must be false.")
    return privacy


def required_checks_from(payload: dict[str, Any], label: str) -> set[str]:
    checks = set(str(item) for item in payload.get("required_checks", []))
    if checks != REQUIRED_CHECKS:
        raise ReleaseStackReadinessError(f"{label}.required_checks drifted: {sorted(checks)}")
    return checks


def stack_groups(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    groups = manifest.get("stack_groups")
    if not isinstance(groups, list) or not groups:
        raise ReleaseStackReadinessError("release-stack manifest must include non-empty stack_groups.")
    for group in groups:
        if not isinstance(group, dict):
            raise ReleaseStackReadinessError("release-stack stack_groups rows must be objects.")
    return groups


def current_group(manifest: dict[str, Any]) -> dict[str, Any]:
    current_id = manifest.get("current_group")
    if not isinstance(current_id, str) or not current_id:
        raise ReleaseStackReadinessError("release-stack manifest must declare current_group.")
    matches = [group for group in stack_groups(manifest) if group.get("group_id") == current_id]
    if len(matches) != 1:
        raise ReleaseStackReadinessError(f"current_group {current_id!r} must match exactly one stack group.")
    group = matches[0]
    if group.get("role") != "current":
        raise ReleaseStackReadinessError("current_group role must be current.")
    if group.get("status") not in {"completed", "open"}:
        raise ReleaseStackReadinessError("current_group status must be completed or open.")
    return group


def validate_operator_commands(group: dict[str, Any]) -> None:
    commands = group.get("operator_commands", [])
    if not isinstance(commands, list) or not commands:
        raise ReleaseStackReadinessError("current_group.operator_commands must be a non-empty list.")
    unsafe = [command for command in commands if str(command) not in SAFE_OPERATOR_COMMANDS]
    if unsafe:
        raise ReleaseStackReadinessError(f"current_group.operator_commands contains unsafe commands: {unsafe}")


def validate_evidence_refs(row: dict[str, Any], label: str) -> None:
    refs = row.get("evidence_refs", [])
    if not isinstance(refs, list) or not refs:
        raise ReleaseStackReadinessError(f"{label}.evidence_refs must be a non-empty list.")
    for ref in refs:
        if not isinstance(ref, str) or not ref:
            raise ReleaseStackReadinessError(f"{label}.evidence_refs must contain strings.")
        if ref.startswith("/") or ".." in Path(ref).parts:
            raise ReleaseStackReadinessError(f"{label}.evidence_refs contains unsafe path {ref}.")
        if not (ROOT / ref).exists():
            raise ReleaseStackReadinessError(f"{label}.evidence_refs missing file {ref}.")


def validate_stack_rows(group: dict[str, Any], target_branch: str) -> list[dict[str, Any]]:
    stack = group.get("stack")
    if not isinstance(stack, list) or not stack:
        raise ReleaseStackReadinessError(f"{group.get('group_id')}.stack must be a non-empty list.")
    orders = [row.get("order") for row in stack if isinstance(row, dict)]
    expected_orders = list(range(1, len(stack) + 1))
    if orders != expected_orders:
        raise ReleaseStackReadinessError(f"{group.get('group_id')}.stack order must be contiguous: {orders}")

    observed: list[dict[str, Any]] = []
    for index, row in enumerate(stack, start=1):
        if not isinstance(row, dict):
            raise ReleaseStackReadinessError(f"{group.get('group_id')}.stack rows must be objects.")
        label = f"{group.get('group_id')}.stack[{index}]"
        pr_number = row.get("pr")
        branch = row.get("branch")
        base = row.get("base")
        if not isinstance(pr_number, int) or not isinstance(branch, str) or not isinstance(base, str):
            raise ReleaseStackReadinessError(f"{label} must include int pr and string branch/base.")
        if row.get("status_expected_before_merge") != "checks_pass":
            raise ReleaseStackReadinessError(f"{label}.status_expected_before_merge must be checks_pass.")

        if group.get("status") == "completed":
            if base != target_branch:
                raise ReleaseStackReadinessError(f"{label}.base must equal target branch {target_branch}.")
            if row.get("final_state") != "MERGED":
                raise ReleaseStackReadinessError(f"{label}.final_state must be MERGED for completed groups.")
            merge_commit = row.get("merge_commit")
            if not isinstance(merge_commit, str) or not SHA_RE.match(merge_commit):
                raise ReleaseStackReadinessError(f"{label}.merge_commit must be a 40-character lowercase SHA.")
            row_checks = row.get("required_checks")
            if not isinstance(row_checks, dict):
                raise ReleaseStackReadinessError(f"{label}.required_checks must be an object.")
            for check_name in sorted(REQUIRED_CHECKS):
                if row_checks.get(check_name) != "pass":
                    raise ReleaseStackReadinessError(f"{label}.required_checks.{check_name} must be pass.")
            validate_evidence_refs(row, label)

        observed.append(
            {
                "order": row["order"],
                "pr": pr_number,
                "branch": branch,
                "base": base,
                "final_state": row.get("final_state"),
                "merge_commit": row.get("merge_commit"),
            }
        )
    return observed


def verify_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ReleaseStackReadinessError("Release stack schema_version drifted.")
    if manifest.get("version") != VERSION:
        raise ReleaseStackReadinessError("Release stack version drifted.")

    policy = manifest.get("release_policy")
    if not isinstance(policy, dict):
        raise ReleaseStackReadinessError("release_policy must be an object.")
    target_branch = policy.get("target_branch")
    if target_branch != "main":
        raise ReleaseStackReadinessError("Release stack target_branch must be main.")
    if policy.get("merge_order") != "oldest_to_newest":
        raise ReleaseStackReadinessError("Release stack must merge oldest to newest.")
    before_tag = set(str(item) for item in policy.get("before_tag", []))
    missing_tag_gates = REQUIRED_BEFORE_TAG - before_tag
    if missing_tag_gates:
        raise ReleaseStackReadinessError(f"Release stack missing before_tag gates: {sorted(missing_tag_gates)}")

    required_checks_from(manifest, "manifest")
    top_level_privacy = validate_privacy(manifest, "manifest")

    groups = stack_groups(manifest)
    archived_count = 0
    for group in groups:
        group_id = group.get("group_id")
        if not isinstance(group_id, str) or not group_id:
            raise ReleaseStackReadinessError("stack_groups[].group_id must be a non-empty string.")
        if group.get("role") == "archived":
            archived_count += 1
            if group.get("status") != "archived":
                raise ReleaseStackReadinessError(f"{group_id}.status must be archived.")
        required_checks_from(group, group_id)
        validate_privacy(group, group_id)

    current = current_group(manifest)
    validate_operator_commands(current)
    post_merge_refs = current.get("post_merge_evidence_refs", [])
    if not isinstance(post_merge_refs, list) or not post_merge_refs:
        raise ReleaseStackReadinessError("current_group.post_merge_evidence_refs must be a non-empty list.")
    validate_evidence_refs({"evidence_refs": post_merge_refs}, "current_group")
    observed = validate_stack_rows(current, str(target_branch))

    top_level_stack = manifest.get("stack")
    if top_level_stack != current.get("stack"):
        raise ReleaseStackReadinessError("Top-level stack must mirror the current stack group.")

    reject_private_text(manifest)
    release_check_text = RELEASE_CHECK.read_text(encoding="utf-8")
    for command in (
        "verify_release_stack_readiness.py",
        "verify_release_stack_manifest_fixtures.py --check",
    ):
        if command not in release_check_text:
            raise ReleaseStackReadinessError(f"release_check.sh must run {command}.")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "target_branch": policy["target_branch"],
        "merge_order": policy["merge_order"],
        "current_group": current["group_id"],
        "current_group_status": current["status"],
        "archived_group_count": archived_count,
        "stack_prs": [item["pr"] for item in observed],
        "top_branch": observed[-1]["branch"],
        "required_checks": sorted(REQUIRED_CHECKS),
        "before_tag_gate_count": len(before_tag),
        "release_check_includes_verifier": True,
        "privacy_assertions": top_level_privacy,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_json(args.manifest)
    report = verify_manifest(manifest)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_stack_readiness failed: {exc}", file=sys.stderr)
        sys.exit(1)
