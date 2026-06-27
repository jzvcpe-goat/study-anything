#!/usr/bin/env python3
"""Verify Cognitive Loop Review Agent PR comment pack assets."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
REPORT_FIXTURE_DIR = ROOT / "fixtures" / "review-agent"
COMMENT_FIXTURE_DIR = ROOT / "fixtures" / "review-agent-pr-comments"
RECEIPT_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_receipt.py"
COMMENT_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_pr_comment.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-pr-comment-pack.json"

SCHEMA_VERSION = "cognitive-loop-review-agent-pr-comment-pack-verification-v1"
COMMENT_PACK_SCHEMA_VERSION = "cognitive-loop-review-agent-pr-comment-pack-v1"
REPORT_FIXTURES = ("approved.json", "needs-review.json", "needs-fix.json")
BAD_COMMENT_PACKS = ("raw-diff-leak.json",)
FIXED_GENERATED_AT = "2026-06-18T00:00:00+00:00"


class ReviewAgentPrCommentVerificationError(RuntimeError):
    """Readable Review Agent PR comment pack verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentPrCommentVerificationError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewAgentPrCommentVerificationError(f"JSON object expected: {path.relative_to(ROOT)}")
    return value


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReviewAgentPrCommentVerificationError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentPrCommentVerificationError(message)


def report_sha(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def build_receipt_for_fixture(receipt_cli: Any, fixture_name: str) -> dict[str, Any]:
    report_path = REPORT_FIXTURE_DIR / fixture_name
    report = read_json(report_path)
    fixture_id = fixture_name.removesuffix(".json")
    return receipt_cli.build_receipt_payload(
        report,
        report_sha256=report_sha(report_path),
        source_report_name=fixture_name,
        provider_id=f"fixture-{fixture_id}-review-agent",
        provider_label=f"Fixture {fixture_id} Review Agent",
        execution_surface="ci",
        pr_ref=f"PR-fixture-{fixture_id}",
        commit_sha=f"sha-fixture-{fixture_id}",
        base_ref="main",
        head_ref=f"codex/fixture-{fixture_id}",
        generated_at=FIXED_GENERATED_AT,
    )


def build_comment_pack_for_fixture(receipt_cli: Any, comment_cli: Any, fixture_name: str) -> dict[str, Any]:
    receipt = build_receipt_for_fixture(receipt_cli, fixture_name)
    pack = comment_cli.build_comment_pack_payload(receipt, generated_at=FIXED_GENERATED_AT)
    summary = comment_cli.validate_comment_pack_payload(pack)
    require(pack["schema_version"] == COMMENT_PACK_SCHEMA_VERSION, f"{fixture_name} comment pack schema drifted.")
    serialized = dump_json(pack)
    for forbidden_text in ("diff --git", "@@ ", "subprocess.run(user_command"):
        require(forbidden_text not in serialized, f"{fixture_name} comment pack leaked private text: {forbidden_text}")
    comments = pack.get("comments", {})
    require(isinstance(comments, Mapping), f"{fixture_name} comments must be an object.")
    require("Decision:" in str(comments.get("markdown_en", "")), f"{fixture_name} English comment missing decision.")
    require("决策：" in str(comments.get("markdown_zh", "")), f"{fixture_name} Chinese comment missing decision.")
    return {
        "summary": summary,
        "comment_hashes": {
            "markdown_en_sha256": receipt_cli.sha256_text(str(comments.get("markdown_en", ""))),
            "markdown_zh_sha256": receipt_cli.sha256_text(str(comments.get("markdown_zh", ""))),
        },
        "labels_to_add": pack.get("decision_summary", {}).get("labels_to_add", []),
        "human_action": pack.get("decision_summary", {}).get("human_action"),
    }


def validate_bad_comment_pack(comment_cli: Any, fixture_name: str) -> str:
    path = COMMENT_FIXTURE_DIR / fixture_name
    payload = read_json(path)
    try:
        comment_cli.validate_comment_pack_payload(payload)
    except Exception as exc:
        return str(exc)
    raise ReviewAgentPrCommentVerificationError(f"Bad comment pack unexpectedly passed: {path.relative_to(ROOT)}")


def validate_docs() -> dict[str, str]:
    docs = {
        "docs/cognitive-loop-code-review.md": [
            "cognitive_loop_review_agent_pr_comment.py build",
            "verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
        ],
        "docs/eval-frameworks.md": [
            "cognitive-loop-review-agent-pr-comment-pack-v1",
            "verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
        ],
        "evals/README.md": [
            "verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
        ],
        ".cognitive-loop/evals.yaml": [
            "cognitive-loop.review-agent-pr-comment-pack",
            "python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
        ],
        "scripts/release_check.sh": [
            "scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
        ],
        "platform/packs/kimi/README.md": [
            "cognitive_loop_review_agent_pr_comment.py build",
            "verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
        ],
        "platform/packs/codex/README.md": [
            "cognitive_loop_review_agent_pr_comment.py build",
            "verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
        ],
        "platform/packs/workbuddy/README.md": [
            "cognitive_loop_review_agent_pr_comment.py build",
            "verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
        ],
    }
    checked: dict[str, str] = {}
    for relative, needles in docs.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        require(not missing, f"{relative} missing Review Agent PR comment pack references: {missing}")
        checked[relative] = "pass"
    return checked


def build_report() -> dict[str, Any]:
    receipt_cli = load_module(RECEIPT_CLI_PATH, "study_anything_review_agent_receipt")
    comment_cli = load_module(COMMENT_CLI_PATH, "study_anything_review_agent_pr_comment")
    built = {fixture: build_comment_pack_for_fixture(receipt_cli, comment_cli, fixture) for fixture in REPORT_FIXTURES}
    summaries = {fixture: value["summary"] for fixture, value in built.items()}
    decisions = {summary["decision"] for summary in summaries.values()}
    conclusions = {summary["conclusion"] for summary in summaries.values()}
    require(decisions == {"approved", "needs-review", "needs-fix"}, f"Comment pack decision coverage drifted: {sorted(decisions)}")
    require(conclusions == {"success", "neutral", "failure"}, f"Comment pack conclusion coverage drifted: {sorted(conclusions)}")
    negative = {fixture: validate_bad_comment_pack(comment_cli, fixture) for fixture in BAD_COMMENT_PACKS}
    docs = validate_docs()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "comment_pack_schema_version": COMMENT_PACK_SCHEMA_VERSION,
        "cli": "scripts/cognitive_loop_review_agent_pr_comment.py",
        "comment_pack_count": len(summaries),
        "comment_packs": {
            fixture: {
                "summary": value["summary"],
                "comment_hashes": value["comment_hashes"],
                "labels_to_add": value["labels_to_add"],
                "human_action": value["human_action"],
            }
            for fixture, value in built.items()
        },
        "negative_comment_packs": negative,
        "docs": docs,
        "quality_gates": {
            "decision_path_coverage": sorted(decisions),
            "checks_conclusion_coverage": sorted(conclusions),
            "bilingual_markdown_comments": "pass",
            "metadata_only_comments": "pass",
            "privacy_leak_rejection": "pass",
        },
        "privacy": {
            "raw_diff_included": False,
            "file_bodies_included": False,
            "finding_evidence_included": False,
            "report_summary_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "hidden_chain_of_thought_included": False,
            "safe_to_attach_to_pr": True,
        },
        "acceptance": {
            "build_command": (
                "python3 scripts/cognitive_loop_review_agent_pr_comment.py build "
                "--receipt REVIEW_AGENT_CI_RECEIPT.json"
            ),
            "validate_command": "python3 scripts/cognitive_loop_review_agent_pr_comment.py validate --comment-pack COMMENT_PACK.json",
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
            "generated_report": "platform/generated/study-anything-cognitive-loop-review-agent-pr-comment-pack.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop Review Agent PR comment pack report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent PR comment pack report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentPrCommentVerificationError as exc:
        raise SystemExit(f"error: {exc}") from exc
