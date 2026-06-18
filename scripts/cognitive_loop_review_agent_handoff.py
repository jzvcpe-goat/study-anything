#!/usr/bin/env python3
"""Prepare and validate external Cognitive Loop Review Agent handoffs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "platform" / "prompts" / "cognitive-loop-review-agent.json"
REPORT_SCHEMA_PATH = ROOT / "platform" / "schemas" / "cognitive-loop-review-agent-report.schema.json"
REPORT_VERIFIER_PATH = ROOT / "scripts" / "verify_cognitive_loop_review_agent_report.py"

REQUEST_SCHEMA_VERSION = "cognitive-loop-review-agent-handoff-request-v1"
VALIDATION_SCHEMA_VERSION = "cognitive-loop-review-agent-handoff-validation-v1"


class ReviewAgentHandoffError(RuntimeError):
    """Readable handoff CLI failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentHandoffError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReviewAgentHandoffError(f"JSON object expected: {path}")
    return payload


def load_report_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_review_agent_report_verifier",
        REPORT_VERIFIER_PATH,
    )
    if spec is None or spec.loader is None:
        raise ReviewAgentHandoffError(f"Cannot load report verifier: {REPORT_VERIFIER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_git(root: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "unknown git error"
        raise ReviewAgentHandoffError(f"git {' '.join(args)} failed: {stderr}")
    return completed.stdout


def ref_args(base: str | None, head: str | None) -> list[str]:
    if base and head:
        return [base, head]
    if base:
        return [base, "HEAD"]
    if head:
        return ["HEAD", head]
    return ["HEAD"]


def collect_git_diff(root: Path, *, base: str | None, head: str | None) -> dict[str, Any]:
    refs = ref_args(base, head)
    diff = run_git(root, ["diff", "--no-ext-diff", "--unified=80", *refs, "--"])
    shortstat = run_git(root, ["diff", "--shortstat", *refs, "--"]).strip()
    changed_files = [
        line.strip()
        for line in run_git(root, ["diff", "--name-only", *refs, "--"]).splitlines()
        if line.strip()
    ]
    return {
        "diff_source": "git",
        "base_ref": base or "HEAD",
        "head_ref": head or ("HEAD" if base else "worktree"),
        "git_diff": diff,
        "git_diff_stats": shortstat,
        "changed_files": changed_files,
    }


def files_from_diff(diff_text: str) -> list[str]:
    files: list[str] = []
    for line in diff_text.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if len(parts) >= 4:
            candidate = parts[3]
            if candidate.startswith("b/"):
                candidate = candidate[2:]
            if candidate not in files:
                files.append(candidate)
    return files


def stats_from_diff(diff_text: str) -> dict[str, int]:
    additions = 0
    deletions = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return {"additions": additions, "deletions": deletions}


def collect_diff_file(path: Path) -> dict[str, Any]:
    diff = path.read_text(encoding="utf-8")
    stats = stats_from_diff(diff)
    return {
        "diff_source": "diff_file",
        "base_ref": "operator-provided",
        "head_ref": "operator-provided",
        "git_diff": diff,
        "git_diff_stats": f"{len(files_from_diff(diff))} files changed, {stats['additions']} insertions(+), {stats['deletions']} deletions(-)",
        "changed_files": files_from_diff(diff),
    }


def build_request(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    prompt = read_json(PROMPT_PATH)
    report_schema = read_json(REPORT_SCHEMA_PATH)
    diff_payload = (
        collect_diff_file(Path(args.diff_file).resolve())
        if args.diff_file
        else collect_git_diff(root, base=args.base, head=args.head)
    )
    diff_text = diff_payload["git_diff"]
    request_id = hashlib.sha256(
        f"{args.pr_id}\n{args.title}\n{args.description}\n{diff_text}".encode("utf-8")
    ).hexdigest()[:16]
    return {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "handoff_type": "ephemeral_external_review_agent_request",
        "review_agent_prompt_contract": prompt,
        "final_report_schema": report_schema,
        "operator_instructions": [
            "Send this handoff request to a user-owned external Review Agent such as Kimi, Codex, WorkBuddy, or a private CI Agent.",
            "The external Agent may inspect only the included git_diff unless the operator explicitly supplies more context.",
            "The external Agent must return JSON only and conform to platform/schemas/cognitive-loop-review-agent-report.schema.json.",
            "Validate the returned JSON with: python3 scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json",
            "Do not commit this handoff request, raw git diff, model credentials, private Agent endpoints, or hidden reasoning traces.",
        ],
        "review_input": {
            "pr_id": args.pr_id,
            "pr_title": args.title,
            "pr_description": args.description,
            "diff_sha256": hashlib.sha256(diff_text.encode("utf-8")).hexdigest(),
            **diff_payload,
        },
        "required_output": {
            "report_version": "1.0",
            "schema_path": "platform/schemas/cognitive-loop-review-agent-report.schema.json",
            "max_findings": 8,
            "final_findings_confidence": ["medium", "high"],
            "low_confidence_destination": "suppressed_low_confidence",
        },
        "privacy_boundary": {
            "raw_diff_in_request": True,
            "request_is_ephemeral_operator_material": True,
            "study_anything_may_persist_request": False,
            "study_anything_may_persist_raw_diff": False,
            "study_anything_may_persist_file_bodies": False,
            "study_anything_may_persist_model_keys": False,
            "study_anything_may_persist_private_agent_endpoints": False,
            "safe_to_commit": False,
        },
    }


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def guard_handoff_output_dir(output_dir: Path, review_root: Path, *, allow_repo_output: bool) -> Path:
    resolved = output_dir.resolve(strict=False)
    review_root = review_root.resolve(strict=False)
    if is_inside(resolved, review_root) and not allow_repo_output:
        raise ReviewAgentHandoffError(
            "Refusing to write raw-diff handoff material inside the reviewed repository. "
            "Use a temp directory outside the repo, or pass --allow-repo-output for an explicit local-only test."
        )
    forbidden = [
        review_root / ".git",
        review_root / ".cognitive-loop",
        review_root / "platform" / "generated",
        review_root / "docs",
        review_root / "fixtures",
    ]
    for parent in forbidden:
        if is_inside(resolved, parent.resolve(strict=False)):
            raise ReviewAgentHandoffError(f"Refusing unsafe handoff output directory: {resolved}")
    return resolved


def write_handoff_dir(output_dir: Path, request: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "request": output_dir / "review-agent-handoff-request.json",
        "prompt": output_dir / "review-agent-prompt-contract.json",
        "schema": output_dir / "review-agent-report-schema.json",
        "readme": output_dir / "README.md",
    }
    files["request"].write_text(dump_json(request), encoding="utf-8")
    files["prompt"].write_text(dump_json(request["review_agent_prompt_contract"]), encoding="utf-8")
    files["schema"].write_text(dump_json(request["final_report_schema"]), encoding="utf-8")
    files["readme"].write_text(
        "\n".join(
            [
                "# Cognitive Loop Review Agent Handoff",
                "",
                "This directory contains ephemeral operator material for a user-owned external Review Agent.",
                "Do not commit it. The request file contains a raw git diff.",
                "",
                "1. Send `review-agent-handoff-request.json` to the external Agent.",
                "2. Save the Agent JSON-only response outside the repo.",
                "3. Validate it with:",
                "",
                "```bash",
                "python3 scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {key: str(value) for key, value in files.items()}


def prepare(args: argparse.Namespace) -> int:
    request = build_request(args)
    if args.output_dir:
        review_root = Path(args.root).resolve()
        output_dir = guard_handoff_output_dir(
            Path(args.output_dir),
            review_root,
            allow_repo_output=args.allow_repo_output,
        )
        written = write_handoff_dir(output_dir, request)
        print(dump_json({"status": "wrote", "schema_version": REQUEST_SCHEMA_VERSION, "files": written}), end="")
    else:
        print(dump_json(request), end="")
    return 0


def build_validation_summary(report_path: Path) -> dict[str, Any]:
    verifier = load_report_verifier()
    payload = read_json(report_path)
    summary = verifier.validate_report(payload, fixture_name=report_path.name)
    verifier.reject_private_text(payload, label=f"{report_path.name} validated report")
    result = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "status": "pass",
        "source_report_name": report_path.name,
        "report_summary": summary,
        "ci_instructions": {
            "decision": payload.get("decision"),
            "should_block_merge": payload.get("ci_instructions", {}).get("should_block_merge"),
            "required_human_review": payload.get("ci_instructions", {}).get("required_human_review"),
        },
        "privacy": {
            "validated_report_contains_raw_diff": False,
            "validated_report_contains_file_bodies": False,
            "validated_report_contains_model_keys": False,
            "validated_report_contains_private_agent_endpoints": False,
            "validation_summary_safe_to_store": True,
        },
        "next_steps": [
            "Attach this validation summary to PR evidence or CI logs.",
            "Do not attach the raw handoff request or git diff.",
            "If decision is needs-fix, require a code fix before merge.",
            "If decision is needs-review, require human maintainer review before merge.",
        ],
    }
    verifier.reject_private_text(result, label="Review Agent handoff validation summary")
    return result


def validate(args: argparse.Namespace) -> int:
    report_path = Path(args.report).resolve()
    summary = build_validation_summary(report_path)
    serialized = dump_json(summary)
    if args.summary_output:
        output = Path(args.summary_output).resolve(strict=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Build an ephemeral external Agent handoff request.")
    prepare_parser.add_argument("--root", default=".", help="Repository root to diff.")
    prepare_parser.add_argument("--base", help="Base git ref. Defaults to HEAD when no diff file is provided.")
    prepare_parser.add_argument("--head", help="Head git ref. Defaults to worktree when no diff file is provided.")
    prepare_parser.add_argument("--diff-file", help="Operator-provided git diff file.")
    prepare_parser.add_argument("--pr-id", default="local", help="PR, branch, or local run id.")
    prepare_parser.add_argument("--title", default="Local Cognitive Loop Review", help="PR title or change title.")
    prepare_parser.add_argument("--description", default="", help="PR description or operator notes.")
    prepare_parser.add_argument("--output-dir", help="Optional temp directory for handoff files.")
    prepare_parser.add_argument(
        "--allow-repo-output",
        action="store_true",
        help="Explicitly allow output under the reviewed repo for local-only tests.",
    )
    prepare_parser.set_defaults(func=prepare)

    validate_parser = subparsers.add_parser("validate", help="Validate a returned external Agent JSON report.")
    validate_parser.add_argument("--report", required=True, help="External Review Agent JSON report.")
    validate_parser.add_argument("--summary-output", help="Optional path for a redacted validation summary.")
    validate_parser.set_defaults(func=validate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentHandoffError as exc:
        raise SystemExit(f"error: {exc}") from exc
    except Exception as exc:
        if exc.__class__.__name__ == "ReviewAgentReportError":
            raise SystemExit(f"error: {exc}") from exc
        raise
