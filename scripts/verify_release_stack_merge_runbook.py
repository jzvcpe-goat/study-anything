#!/usr/bin/env python3
"""Generate and verify the maintainer merge runbook for the stacked release PRs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from verify_release_stack_lineage import (
    DEFAULT_MANIFEST,
    ReleaseStackLineageError,
    load_manifest,
    redact,
    verify_lineage,
)
from verify_release_stack_readiness import current_group


SCHEMA_VERSION = "release-stack-merge-runbook-v1"


class MergeRunbookError(RuntimeError):
    """Readable merge runbook verification failure."""


def build_runbook(manifest: dict[str, Any], allow_missing_top_pr: bool, max_depth: int) -> dict[str, Any]:
    lineage_report = verify_lineage(manifest, allow_missing_top_pr=allow_missing_top_pr, max_depth=max_depth)
    group = current_group(manifest)
    group_status = str(group.get("status"))
    policy = manifest.get("release_policy", {})
    if not isinstance(policy, dict):
        raise MergeRunbookError("release_policy must be an object.")

    lineage = lineage_report.get("lineage", [])
    if not isinstance(lineage, list) or not lineage:
        raise MergeRunbookError("Lineage report must include a non-empty lineage.")

    steps: list[dict[str, Any]] = []
    blockers: list[str] = []
    draft_prs: list[int] = []
    pending_prs: list[int] = []

    ordered_lineage = list(lineage) if group_status == "completed" else list(reversed(lineage))
    target_branch = str(policy.get("target_branch"))
    cleanup_commands: list[str] = []

    for order, item in enumerate(ordered_lineage, start=1):
        if not isinstance(item, dict):
            raise MergeRunbookError("Lineage rows must be objects.")
        pr_number = item.get("pr")
        branch = item.get("branch")
        base = item.get("base")
        state = item.get("state")
        is_draft = item.get("is_draft")
        merge_ready = bool(item.get("merge_ready"))
        if not isinstance(pr_number, int) or not isinstance(branch, str) or not isinstance(base, str):
            raise MergeRunbookError("Lineage rows must include int pr and string branch/base.")
        if state == "pending_pr_creation":
            pending_prs.append(pr_number)
        elif state not in {"OPEN", "MERGED"}:
            blockers.append(f"PR #{pr_number} state must be OPEN or MERGED before runbook use.")
        if not merge_ready:
            blockers.append(f"PR #{pr_number} is not merge-ready in the lineage report.")
        if is_draft is True:
            draft_prs.append(pr_number)

        next_item = ordered_lineage[order] if order < len(ordered_lineage) else None
        next_pr = next_item.get("pr") if isinstance(next_item, dict) else None
        ready_command = f"gh pr ready {pr_number}" if is_draft is True else None
        if state == "MERGED":
            merge_command = None
            alternative_merge_command = None
            post_merge_commands = ["already merged; retain metadata-only receipt"]
        else:
            merge_command = f"gh pr merge {pr_number} --squash"
            alternative_merge_command = f"gh pr merge {pr_number} --merge"
            post_merge_commands = [
                "git fetch origin main",
                "git switch main",
                "git pull --ff-only",
            ]
            if isinstance(next_pr, int):
                post_merge_commands.extend(
                    [
                        f"gh pr edit {next_pr} --base {target_branch}",
                        f"gh pr checks {next_pr} --watch --interval 10",
                    ]
                )
            else:
                post_merge_commands.extend(str(command) for command in policy.get("before_tag", []))
        if state == "MERGED" and not isinstance(next_pr, int):
            post_merge_commands.extend(str(command) for command in policy.get("before_tag", []))
        if state != "MERGED":
            cleanup_commands.append(f"git push origin --delete {branch}")
        steps.append(
            {
                "order": order,
                "pr": pr_number,
                "branch": branch,
                "base": base,
                "state": state,
                "is_draft": is_draft,
                "required_checks": item.get("required_checks", {}),
                "ready_command": ready_command,
                "checks_command": f"gh pr checks {pr_number}",
                "retarget_after_previous_merge_command": (
                    f"gh pr edit {pr_number} --base {target_branch}"
                    if state != "MERGED" and base != target_branch
                    else None
                ),
                "recommended_merge_command": merge_command,
                "alternative_merge_command": alternative_merge_command,
                "post_merge_commands": post_merge_commands,
            }
        )

    lineage_status = str(lineage_report.get("status"))
    if lineage_status not in {"pass", "pending_top_pr"}:
        blockers.append(f"Lineage verifier status is {lineage_status}.")
    reaches_target = bool(lineage_report.get("lineage_reaches_target"))
    if not reaches_target:
        blockers.append("Lineage does not reach the target branch.")

    status = "pass"
    if pending_prs:
        status = "pending_top_pr"
    if blockers and not pending_prs:
        status = "blocked"

    ready_to_merge_now = status == "pass" and not draft_prs and group_status != "completed"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "version": manifest.get("version"),
        "current_group": group.get("group_id"),
        "current_group_status": group_status,
        "target_branch": target_branch,
        "merge_order": policy.get("merge_order"),
        "merge_mode": policy.get("merge_mode"),
        "stack_completed": group_status == "completed",
        "ready_to_merge_now": ready_to_merge_now,
        "manual_action_required": bool(draft_prs or pending_prs),
        "draft_pr_count": len(draft_prs),
        "draft_prs": draft_prs,
        "pending_prs": pending_prs,
        "lineage_length": lineage_report.get("lineage_length"),
        "lineage_reaches_target": reaches_target,
        "preflight_commands": [
            "python3 scripts/verify_release_stack_readiness.py",
            "python3 scripts/verify_release_stack_manifest_fixtures.py --check",
            "python3 scripts/verify_release_stack_live_status.py",
            "python3 scripts/verify_release_stack_lineage.py",
            "python3 scripts/verify_release_stack_merge_runbook.py --fail-if-draft",
            "./scripts/release_check.sh",
        ],
        "merge_steps": steps,
        "cleanup_commands_after_stack_merge": cleanup_commands,
        "before_tag_commands": policy.get("before_tag", []),
        "blocker_count": len(blockers),
        "blockers": [redact(item) for item in blockers[:10]],
        "privacy": {
            "github_tokens_stored": False,
            "live_check_payloads_stored": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--allow-missing-top-pr", action="store_true")
    parser.add_argument("--max-depth", type=int, default=80)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Return exit code 0 even when the runbook is not yet actionable.",
    )
    parser.add_argument(
        "--fail-if-draft",
        action="store_true",
        help="Fail when any PR is still draft. Use immediately before starting the real merge run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    report = build_runbook(manifest, allow_missing_top_pr=args.allow_missing_top_pr, max_depth=args.max_depth)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    blocked = report["status"] != "pass"
    draft_blocked = args.fail_if_draft and bool(report["draft_pr_count"])
    if (blocked or draft_blocked) and not args.report_only:
        raise MergeRunbookError("Release stack merge runbook is not actionable.")


if __name__ == "__main__":
    try:
        main()
    except (MergeRunbookError, ReleaseStackLineageError) as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_stack_merge_runbook failed: {redact(str(exc))}", file=sys.stderr)
        sys.exit(1)
