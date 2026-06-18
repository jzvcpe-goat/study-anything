#!/usr/bin/env python3
"""Build and validate safe PR comment packs from Review Agent CI receipts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_receipt.py"

COMMENT_PACK_SCHEMA_VERSION = "cognitive-loop-review-agent-pr-comment-pack-v1"
COMMENT_PACK_VALIDATE_COMMAND = (
    "python3 scripts/cognitive_loop_review_agent_pr_comment.py validate --comment-pack COMMENT_PACK.json"
)


class ReviewAgentPrCommentError(RuntimeError):
    """Readable Review Agent PR comment pack failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentPrCommentError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewAgentPrCommentError(f"JSON object expected: {path}")
    return value


def load_receipt_cli() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_review_agent_receipt",
        RECEIPT_CLI_PATH,
    )
    if spec is None or spec.loader is None:
        raise ReviewAgentPrCommentError(f"Cannot load receipt CLI: {RECEIPT_CLI_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentPrCommentError(message)


def require_mapping(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, Mapping):
        raise ReviewAgentPrCommentError(f"Expected object field: {key}")
    return value


def require_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReviewAgentPrCommentError(f"Expected non-empty string field: {key}")
    return value


def require_bool(mapping: Mapping[str, Any], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ReviewAgentPrCommentError(f"Expected boolean field: {key}")
    return value


def conclusion_for(decision: str) -> str:
    if decision == "needs-fix":
        return "failure"
    if decision == "needs-review":
        return "neutral"
    return "success"


def title_for(decision: str) -> str:
    if decision == "needs-fix":
        return "Cognitive Loop Review Agent: fixes required"
    if decision == "needs-review":
        return "Cognitive Loop Review Agent: maintainer review required"
    return "Cognitive Loop Review Agent: approved"


def zh_title_for(decision: str) -> str:
    if decision == "needs-fix":
        return "Cognitive Loop Review Agent：需要修复"
    if decision == "needs-review":
        return "Cognitive Loop Review Agent：需要维护者复核"
    return "Cognitive Loop Review Agent：已通过"


def render_labels(labels: list[str]) -> str:
    if not labels:
        return "none"
    return ", ".join(f"`{label}`" for label in labels)


def render_labels_zh(labels: list[str]) -> str:
    if not labels:
        return "无"
    return "、".join(f"`{label}`" for label in labels)


def render_markdown_en(pack: Mapping[str, Any]) -> str:
    summary = require_mapping(pack, "decision_summary")
    source = require_mapping(pack, "source_receipt")
    agent = require_mapping(pack, "review_agent")
    commands = require_mapping(pack, "commands")
    labels = summary.get("labels_to_add", [])
    if not isinstance(labels, list):
        labels = []
    lines = [
        f"## {title_for(str(summary['decision']))}",
        "",
        f"- Decision: `{summary['decision']}`",
        f"- Risk: `{summary['overall_risk']}`",
        (
            "- Finding counts: "
            f"{summary['critical_count']} critical, {summary['warn_count']} warn, "
            f"{summary['info_count']} info; {summary['suppressed_count']} suppressed"
        ),
        f"- Provider: `{agent['provider_id']}` on `{agent['execution_surface']}`",
        f"- Ref: `{source['pr_ref']}` at `{source['commit_sha']}`",
        f"- Report hash: `{source['report_sha256']}`",
        f"- Human action: `{summary['human_action']}`",
        f"- Suggested labels: {render_labels([str(label) for label in labels])}",
        "",
        "Validation:",
        f"- `{commands['source_report_validation']}`",
        f"- `{commands['receipt_validation']}`",
        f"- `{commands['comment_pack_validation']}`",
        "",
        (
            "Privacy: this comment is metadata-only. It does not include raw diffs, source bodies, "
            "finding evidence, report prose, endpoint secrets, model keys, or private reasoning traces."
        ),
    ]
    return "\n".join(lines)


def render_markdown_zh(pack: Mapping[str, Any]) -> str:
    summary = require_mapping(pack, "decision_summary")
    source = require_mapping(pack, "source_receipt")
    agent = require_mapping(pack, "review_agent")
    commands = require_mapping(pack, "commands")
    labels = summary.get("labels_to_add", [])
    if not isinstance(labels, list):
        labels = []
    lines = [
        f"## {zh_title_for(str(summary['decision']))}",
        "",
        f"- 决策：`{summary['decision']}`",
        f"- 风险：`{summary['overall_risk']}`",
        (
            "- 发现计数："
            f"{summary['critical_count']} 个 critical，{summary['warn_count']} 个 warn，"
            f"{summary['info_count']} 个 info；{summary['suppressed_count']} 个已抑制"
        ),
        f"- Agent：`{agent['provider_id']}` / `{agent['execution_surface']}`",
        f"- 引用：`{source['pr_ref']}` at `{source['commit_sha']}`",
        f"- 报告哈希：`{source['report_sha256']}`",
        f"- 人工动作：`{summary['human_action']}`",
        f"- 建议标签：{render_labels_zh([str(label) for label in labels])}",
        "",
        "验证命令：",
        f"- `{commands['source_report_validation']}`",
        f"- `{commands['receipt_validation']}`",
        f"- `{commands['comment_pack_validation']}`",
        "",
        "隐私：这条评论只包含元数据，不包含原始 diff、源码正文、证据片段、报告正文、端点密钥、模型密钥或私有推理痕迹。",
    ]
    return "\n".join(lines)


def build_comment_pack_payload(receipt: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    receipt_cli = load_receipt_cli()
    receipt_summary = receipt_cli.validate_receipt_payload(receipt)
    receipt_cli.reject_private_text(receipt, label="Review Agent CI receipt source")
    review_agent = require_mapping(receipt, "review_agent")
    source = require_mapping(receipt, "source")
    validated_report = require_mapping(receipt, "validated_report")
    ci = require_mapping(receipt, "ci")
    labels = ci.get("labels_to_add", [])
    if not isinstance(labels, list):
        labels = []

    pack_basis = "\n".join(
        [
            str(receipt.get("receipt_id")),
            str(validated_report.get("report_sha256")),
            str(source.get("pr_ref")),
            str(source.get("commit_sha")),
            str(receipt_summary["decision"]),
        ]
    )
    pack = {
        "schema_version": COMMENT_PACK_SCHEMA_VERSION,
        "status": "pass",
        "comment_pack_id": f"review-agent-pr-comment-{receipt_cli.sha256_text(pack_basis)[:16]}",
        "generated_at": generated_at,
        "source_receipt": {
            "receipt_id": receipt.get("receipt_id"),
            "receipt_schema_version": receipt.get("schema_version"),
            "report_sha256": validated_report.get("report_sha256"),
            "pr_ref": source.get("pr_ref"),
            "commit_sha": source.get("commit_sha"),
            "base_ref": source.get("base_ref"),
            "head_ref": source.get("head_ref"),
        },
        "review_agent": {
            "provider_id": review_agent.get("provider_id"),
            "provider_label": review_agent.get("provider_label", ""),
            "execution_surface": review_agent.get("execution_surface"),
            "user_owned_agent": True,
            "study_anything_executed_real_model": False,
        },
        "decision_summary": {
            "decision": receipt_summary["decision"],
            "overall_risk": receipt_summary["overall_risk"],
            "finding_count": receipt_summary["finding_count"],
            "critical_count": receipt_summary["critical_count"],
            "warn_count": validated_report.get("warn_count"),
            "info_count": validated_report.get("info_count"),
            "suppressed_count": validated_report.get("suppressed_count"),
            "should_block_merge": ci.get("should_block_merge"),
            "required_human_review": ci.get("required_human_review"),
            "labels_to_add": [str(label) for label in labels],
            "human_action": ci.get("human_action"),
        },
        "commands": {
            "source_report_validation": ci.get("validation_command"),
            "receipt_validation": ci.get("receipt_validation_command"),
            "comment_pack_validation": COMMENT_PACK_VALIDATE_COMMAND,
            "release_gate": "python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check",
        },
        "checks_summary": {
            "name": "Cognitive Loop Review Agent",
            "status": "completed",
            "conclusion": conclusion_for(str(receipt_summary["decision"])),
            "title": title_for(str(receipt_summary["decision"])),
            "summary": (
                f"decision={receipt_summary['decision']} risk={receipt_summary['overall_risk']} "
                f"findings={receipt_summary['finding_count']} report_sha256={validated_report.get('report_sha256')}"
            ),
        },
        "comments": {},
        "privacy": {
            "raw_diff_included": False,
            "file_bodies_included": False,
            "finding_evidence_included": False,
            "report_summary_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "hidden_chain_of_thought_included": False,
            "metadata_only": True,
            "safe_to_attach_to_pr": True,
        },
    }
    pack["comments"] = {
        "markdown_en": render_markdown_en(pack),
        "markdown_zh": render_markdown_zh(pack),
    }
    validate_comment_pack_payload(pack)
    return pack


def validate_comment_pack_payload(pack: Mapping[str, Any]) -> dict[str, Any]:
    receipt_cli = load_receipt_cli()
    require(pack.get("schema_version") == COMMENT_PACK_SCHEMA_VERSION, "Comment pack schema_version drifted.")
    require(pack.get("status") == "pass", "Comment pack status must be pass.")
    require_string(pack, "comment_pack_id")
    require_string(pack, "generated_at")
    source = require_mapping(pack, "source_receipt")
    agent = require_mapping(pack, "review_agent")
    summary = require_mapping(pack, "decision_summary")
    commands = require_mapping(pack, "commands")
    checks = require_mapping(pack, "checks_summary")
    comments = require_mapping(pack, "comments")
    privacy = require_mapping(pack, "privacy")

    require_string(source, "receipt_id")
    require(source.get("receipt_schema_version") == "cognitive-loop-review-agent-ci-receipt-v1", "Source receipt schema drifted.")
    require_string(source, "report_sha256")
    require_string(source, "pr_ref")
    require_string(source, "commit_sha")
    require_string(agent, "provider_id")
    require_string(agent, "execution_surface")
    require(agent.get("user_owned_agent") is True, "Comment pack must state the Agent is user-owned.")
    require(agent.get("study_anything_executed_real_model") is False, "Study Anything must not execute real model calls.")

    decision = require_string(summary, "decision")
    risk = require_string(summary, "overall_risk")
    require(decision in {"approved", "needs-review", "needs-fix"}, f"Invalid comment pack decision: {decision}")
    require(risk in {"low", "medium", "high"}, f"Invalid comment pack risk: {risk}")
    for key in ("finding_count", "critical_count", "warn_count", "info_count", "suppressed_count"):
        value = summary.get(key)
        require(isinstance(value, int) and value >= 0, f"decision_summary.{key} must be a non-negative integer.")
    require(
        summary["finding_count"] == summary["critical_count"] + summary["warn_count"] + summary["info_count"],
        "finding_count must equal severity counts.",
    )
    require_bool(summary, "should_block_merge")
    require_bool(summary, "required_human_review")
    labels = summary.get("labels_to_add")
    require(isinstance(labels, list) and all(isinstance(label, str) for label in labels), "labels_to_add must be a string list.")
    expected_action = receipt_cli.human_action_for(decision)
    require(summary.get("human_action") == expected_action, f"human_action must be {expected_action}.")
    if decision == "needs-fix":
        require(summary.get("should_block_merge") is True, "needs-fix comment packs must block merge.")
        require(summary.get("critical_count", 0) > 0, "needs-fix comment packs need critical findings.")
    if decision == "needs-review":
        require(summary.get("required_human_review") is True, "needs-review comment packs must require human review.")

    require(checks.get("status") == "completed", "checks_summary.status must be completed.")
    require(checks.get("conclusion") == conclusion_for(decision), "checks_summary.conclusion drifted.")
    require_string(checks, "title")
    require_string(checks, "summary")
    for key in ("source_report_validation", "receipt_validation", "comment_pack_validation", "release_gate"):
        require_string(commands, key)
    markdown_en = require_string(comments, "markdown_en")
    markdown_zh = require_string(comments, "markdown_zh")
    require("Decision:" in markdown_en and "Privacy:" in markdown_en, "English PR comment missing required sections.")
    require("决策：" in markdown_zh and "隐私：" in markdown_zh, "Chinese PR comment missing required sections.")
    require(source["report_sha256"] in markdown_en, "English PR comment must include report hash.")
    require(source["report_sha256"] in markdown_zh, "Chinese PR comment must include report hash.")

    for key in (
        "raw_diff_included",
        "file_bodies_included",
        "finding_evidence_included",
        "report_summary_included",
        "agent_endpoint_secrets_included",
        "real_model_keys_included",
        "hidden_chain_of_thought_included",
    ):
        require(privacy.get(key) is False, f"privacy.{key} must be false.")
    require(privacy.get("metadata_only") is True, "Comment pack must be metadata-only.")
    require(privacy.get("safe_to_attach_to_pr") is True, "Comment pack must be safe to attach to PR.")
    receipt_cli.reject_private_text(pack, label="Review Agent PR comment pack")
    return {
        "comment_pack_id": pack["comment_pack_id"],
        "decision": decision,
        "overall_risk": risk,
        "finding_count": summary["finding_count"],
        "conclusion": checks["conclusion"],
        "safe_to_attach_to_pr": privacy["safe_to_attach_to_pr"],
    }


def build_comment_pack(args: argparse.Namespace) -> dict[str, Any]:
    receipt = read_json(Path(args.receipt).resolve())
    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return build_comment_pack_payload(receipt, generated_at=generated_at)


def build_command(args: argparse.Namespace) -> int:
    pack = build_comment_pack(args)
    serialized = dump_json(pack)
    if args.output:
        output = Path(args.output).resolve(strict=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    pack = read_json(Path(args.comment_pack).resolve())
    summary = validate_comment_pack_payload(pack)
    print(dump_json({"schema_version": COMMENT_PACK_SCHEMA_VERSION, "status": "pass", "comment_pack_summary": summary}), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build a safe bilingual PR comment pack from a CI receipt.")
    build.add_argument("--receipt", required=True, help="Review Agent CI receipt JSON.")
    build.add_argument("--generated-at", help="Deterministic timestamp for tests.")
    build.add_argument("--output", help="Optional comment pack output path.")
    build.set_defaults(func=build_command)

    validate = subparsers.add_parser("validate", help="Validate a safe bilingual PR comment pack.")
    validate.add_argument("--comment-pack", required=True, help="Review Agent PR comment pack JSON.")
    validate.set_defaults(func=validate_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentPrCommentError as exc:
        raise SystemExit(f"error: {exc}") from exc
    except Exception as exc:
        if exc.__class__.__name__ in {"ReviewAgentReceiptError", "ReviewAgentReportError"}:
            raise SystemExit(f"error: {exc}") from exc
        raise
