#!/usr/bin/env python3
"""Build and validate safe Review Agent acceptance bundles."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_receipt.py"
COMMENT_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_pr_comment.py"

BUNDLE_SCHEMA_VERSION = "cognitive-loop-review-agent-acceptance-bundle-v1"
RECEIPT_FILE = "review-agent-ci-receipt.json"
COMMENT_PACK_FILE = "review-agent-pr-comment-pack.json"
MANIFEST_FILE = "manifest.json"
SUMMARY_FILE = "SUMMARY.md"


class ReviewAgentAcceptanceBundleError(RuntimeError):
    """Readable Review Agent acceptance bundle failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentAcceptanceBundleError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewAgentAcceptanceBundleError(f"JSON object expected: {path}")
    return value


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReviewAgentAcceptanceBundleError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentAcceptanceBundleError(message)


def require_mapping(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, Mapping):
        raise ReviewAgentAcceptanceBundleError(f"Expected object field: {key}")
    return value


def require_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReviewAgentAcceptanceBundleError(f"Expected non-empty string field: {key}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_summary(manifest: Mapping[str, Any]) -> str:
    decision = require_mapping(manifest, "decision_summary")
    source = require_mapping(manifest, "source")
    files = require_mapping(manifest, "files")
    lines = [
        "# Cognitive Loop Review Agent Acceptance Bundle",
        "",
        f"- Decision: `{decision['decision']}`",
        f"- Risk: `{decision['overall_risk']}`",
        f"- Findings: `{decision['finding_count']}` total, `{decision['critical_count']}` critical",
        f"- Human action: `{decision['human_action']}`",
        f"- Ref: `{source['pr_ref']}` at `{source['commit_sha']}`",
        f"- Receipt: `{files['receipt']['path']}`",
        f"- PR comment pack: `{files['comment_pack']['path']}`",
        "",
        "Use the comment pack JSON for copy-ready English and Chinese PR comments.",
        "Privacy: this bundle is metadata-only and excludes raw diffs, source bodies, report prose, secrets, model keys, and private reasoning traces.",
        "",
    ]
    return "\n".join(lines)


def build_manifest(
    *,
    receipt: Mapping[str, Any],
    comment_pack: Mapping[str, Any],
    receipt_sha256: str,
    comment_pack_sha256: str,
    generated_at: str,
) -> dict[str, Any]:
    receipt_cli = load_module(RECEIPT_CLI_PATH, "study_anything_review_agent_receipt")
    receipt_summary = receipt_cli.validate_receipt_payload(receipt)
    comment_cli = load_module(COMMENT_CLI_PATH, "study_anything_review_agent_pr_comment")
    comment_summary = comment_cli.validate_comment_pack_payload(comment_pack)
    source = require_mapping(receipt, "source")
    report = require_mapping(receipt, "validated_report")
    agent = require_mapping(receipt, "review_agent")
    decision = require_mapping(comment_pack, "decision_summary")
    commands = require_mapping(comment_pack, "commands")
    bundle_basis = "\n".join(
        [
            str(receipt.get("receipt_id")),
            str(comment_pack.get("comment_pack_id")),
            receipt_sha256,
            comment_pack_sha256,
        ]
    )
    require(receipt_summary["decision"] == comment_summary["decision"], "Receipt and comment pack decisions differ.")
    manifest = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "status": "pass",
        "bundle_id": f"review-agent-acceptance-{receipt_cli.sha256_text(bundle_basis)[:16]}",
        "generated_at": generated_at,
        "source": {
            "pr_ref": source.get("pr_ref"),
            "commit_sha": source.get("commit_sha"),
            "base_ref": source.get("base_ref"),
            "head_ref": source.get("head_ref"),
            "report_sha256": report.get("report_sha256"),
        },
        "review_agent": {
            "provider_id": agent.get("provider_id"),
            "provider_label": agent.get("provider_label", ""),
            "execution_surface": agent.get("execution_surface"),
            "user_owned_agent": True,
            "study_anything_executed_real_model": False,
        },
        "decision_summary": {
            "decision": decision.get("decision"),
            "overall_risk": decision.get("overall_risk"),
            "finding_count": decision.get("finding_count"),
            "critical_count": decision.get("critical_count"),
            "warn_count": decision.get("warn_count"),
            "info_count": decision.get("info_count"),
            "suppressed_count": decision.get("suppressed_count"),
            "should_block_merge": decision.get("should_block_merge"),
            "required_human_review": decision.get("required_human_review"),
            "labels_to_add": decision.get("labels_to_add", []),
            "human_action": decision.get("human_action"),
        },
        "files": {
            "receipt": {
                "path": RECEIPT_FILE,
                "schema_version": receipt.get("schema_version"),
                "sha256": receipt_sha256,
            },
            "comment_pack": {
                "path": COMMENT_PACK_FILE,
                "schema_version": comment_pack.get("schema_version"),
                "sha256": comment_pack_sha256,
            },
            "summary": {
                "path": SUMMARY_FILE,
                "format": "markdown",
            },
        },
        "commands": {
            "source_report_validation": commands.get("source_report_validation"),
            "receipt_validation": commands.get("receipt_validation"),
            "comment_pack_validation": commands.get("comment_pack_validation"),
            "bundle_validation": "python3 scripts/cognitive_loop_review_agent_acceptance_bundle.py validate --bundle-dir REVIEW_AGENT_ACCEPTANCE_BUNDLE_DIR",
            "release_gate": "python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
        },
        "privacy": {
            "raw_diff_included": False,
            "file_bodies_included": False,
            "finding_evidence_included": False,
            "report_summary_included": False,
            "raw_handoff_material_written": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "hidden_chain_of_thought_included": False,
            "metadata_only": True,
            "safe_to_attach_to_pr": True,
        },
    }
    validate_manifest_payload(manifest)
    return manifest


def validate_manifest_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    receipt_cli = load_module(RECEIPT_CLI_PATH, "study_anything_review_agent_receipt")
    require(manifest.get("schema_version") == BUNDLE_SCHEMA_VERSION, "Acceptance bundle schema_version drifted.")
    require(manifest.get("status") == "pass", "Acceptance bundle status must be pass.")
    require_string(manifest, "bundle_id")
    require_string(manifest, "generated_at")
    source = require_mapping(manifest, "source")
    agent = require_mapping(manifest, "review_agent")
    decision = require_mapping(manifest, "decision_summary")
    files = require_mapping(manifest, "files")
    commands = require_mapping(manifest, "commands")
    privacy = require_mapping(manifest, "privacy")

    for key in ("pr_ref", "commit_sha", "report_sha256"):
        require_string(source, key)
    require_string(agent, "provider_id")
    require_string(agent, "execution_surface")
    require(agent.get("user_owned_agent") is True, "Acceptance bundle must state the Agent is user-owned.")
    require(agent.get("study_anything_executed_real_model") is False, "Study Anything must not execute real model calls.")
    review_decision = require_string(decision, "decision")
    risk = require_string(decision, "overall_risk")
    require(review_decision in {"approved", "needs-review", "needs-fix"}, f"Invalid bundle decision: {review_decision}")
    require(risk in {"low", "medium", "high"}, f"Invalid bundle risk: {risk}")
    for key in ("finding_count", "critical_count", "warn_count", "info_count", "suppressed_count"):
        value = decision.get(key)
        require(isinstance(value, int) and value >= 0, f"decision_summary.{key} must be a non-negative integer.")
    require(
        decision["finding_count"] == decision["critical_count"] + decision["warn_count"] + decision["info_count"],
        "finding_count must equal severity counts.",
    )
    require(decision.get("human_action") == receipt_cli.human_action_for(review_decision), "human_action drifted.")
    for key in ("receipt", "comment_pack", "summary"):
        entry = require_mapping(files, key)
        require_string(entry, "path")
    require(files["receipt"].get("schema_version") == "cognitive-loop-review-agent-ci-receipt-v1", "Receipt schema drifted.")
    require(
        files["comment_pack"].get("schema_version") == "cognitive-loop-review-agent-pr-comment-pack-v1",
        "Comment pack schema drifted.",
    )
    for key in ("source_report_validation", "receipt_validation", "comment_pack_validation", "bundle_validation", "release_gate"):
        require_string(commands, key)
    for key in (
        "raw_diff_included",
        "file_bodies_included",
        "finding_evidence_included",
        "report_summary_included",
        "raw_handoff_material_written",
        "agent_endpoint_secrets_included",
        "real_model_keys_included",
        "hidden_chain_of_thought_included",
    ):
        require(privacy.get(key) is False, f"privacy.{key} must be false.")
    require(privacy.get("metadata_only") is True, "Acceptance bundle must be metadata-only.")
    require(privacy.get("safe_to_attach_to_pr") is True, "Acceptance bundle must be safe to attach to PR.")
    receipt_cli.reject_private_text(manifest, label="Review Agent acceptance bundle manifest")
    return {
        "bundle_id": manifest["bundle_id"],
        "decision": review_decision,
        "overall_risk": risk,
        "finding_count": decision["finding_count"],
        "safe_to_attach_to_pr": privacy["safe_to_attach_to_pr"],
    }


def build_bundle(args: argparse.Namespace) -> dict[str, Any]:
    report_path = Path(args.report).resolve()
    report_text = report_path.read_text(encoding="utf-8")
    report_payload = json.loads(report_text)
    if not isinstance(report_payload, dict):
        raise ReviewAgentAcceptanceBundleError(f"JSON object expected: {report_path}")
    output_dir = Path(args.output_dir).resolve(strict=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    receipt_cli = load_module(RECEIPT_CLI_PATH, "study_anything_review_agent_receipt")
    receipt = receipt_cli.build_receipt_payload(
        report_payload,
        report_sha256=hashlib.sha256(report_text.encode("utf-8")).hexdigest(),
        source_report_name=report_path.name,
        provider_id=args.provider_id,
        provider_label=args.provider_label,
        execution_surface=args.execution_surface,
        pr_ref=args.pr_ref,
        commit_sha=args.commit_sha,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        generated_at=generated_at,
        validation_command=args.validation_command,
    )
    comment_cli = load_module(COMMENT_CLI_PATH, "study_anything_review_agent_pr_comment")
    comment_pack = comment_cli.build_comment_pack_payload(receipt, generated_at=generated_at)

    receipt_path = output_dir / RECEIPT_FILE
    comment_pack_path = output_dir / COMMENT_PACK_FILE
    receipt_path.write_text(dump_json(receipt), encoding="utf-8")
    comment_pack_path.write_text(dump_json(comment_pack), encoding="utf-8")
    manifest = build_manifest(
        receipt=receipt,
        comment_pack=comment_pack,
        receipt_sha256=sha256_file(receipt_path),
        comment_pack_sha256=sha256_file(comment_pack_path),
        generated_at=generated_at,
    )
    summary = render_summary(manifest)
    manifest_path = output_dir / MANIFEST_FILE
    summary_path = output_dir / SUMMARY_FILE
    manifest_path.write_text(dump_json(manifest), encoding="utf-8")
    summary_path.write_text(summary, encoding="utf-8")
    validate_bundle_dir(output_dir)
    return manifest


def validate_bundle_dir(bundle_dir: Path) -> dict[str, Any]:
    manifest_path = bundle_dir / MANIFEST_FILE
    manifest = read_json(manifest_path)
    summary = validate_manifest_payload(manifest)
    files = require_mapping(manifest, "files")
    receipt_path = bundle_dir / str(require_mapping(files, "receipt").get("path"))
    comment_pack_path = bundle_dir / str(require_mapping(files, "comment_pack").get("path"))
    summary_path = bundle_dir / str(require_mapping(files, "summary").get("path"))
    require(receipt_path.is_file(), f"Missing receipt file: {receipt_path}")
    require(comment_pack_path.is_file(), f"Missing comment pack file: {comment_pack_path}")
    require(summary_path.is_file(), f"Missing summary file: {summary_path}")

    receipt_cli = load_module(RECEIPT_CLI_PATH, "study_anything_review_agent_receipt")
    comment_cli = load_module(COMMENT_CLI_PATH, "study_anything_review_agent_pr_comment")
    receipt = read_json(receipt_path)
    comment_pack = read_json(comment_pack_path)
    receipt_cli.validate_receipt_payload(receipt)
    comment_cli.validate_comment_pack_payload(comment_pack)
    require(sha256_file(receipt_path) == files["receipt"].get("sha256"), "Receipt sha256 mismatch.")
    require(sha256_file(comment_pack_path) == files["comment_pack"].get("sha256"), "Comment pack sha256 mismatch.")
    summary_text = summary_path.read_text(encoding="utf-8")
    require("Decision:" in summary_text and "Privacy:" in summary_text, "SUMMARY.md missing required sections.")
    receipt_cli.reject_private_text(summary_text, label="Review Agent acceptance bundle summary")
    return summary


def build_command(args: argparse.Namespace) -> int:
    manifest = build_bundle(args)
    print(dump_json({"schema_version": BUNDLE_SCHEMA_VERSION, "status": "pass", "bundle_summary": validate_manifest_payload(manifest)}), end="")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    summary = validate_bundle_dir(Path(args.bundle_dir).resolve())
    print(dump_json({"schema_version": BUNDLE_SCHEMA_VERSION, "status": "pass", "bundle_summary": summary}), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build a safe Review Agent acceptance bundle from a report.")
    build.add_argument("--report", required=True, help="External Review Agent JSON report.")
    build.add_argument("--output-dir", required=True, help="Directory for safe bundle artifacts.")
    build.add_argument("--provider-id", default="external-review-agent", help="Operator-visible provider id.")
    build.add_argument("--provider-label", default="User-owned external Review Agent", help="Human-readable provider label.")
    build.add_argument("--execution-surface", default="ci", choices=["ci", "platform-agent", "local"], help="Where the external Agent ran.")
    build.add_argument("--pr-ref", default="local", help="PR, branch, or run reference.")
    build.add_argument("--commit-sha", default="unknown", help="Commit SHA or immutable run ref.")
    build.add_argument("--base-ref", default="main", help="Base ref.")
    build.add_argument("--head-ref", default="HEAD", help="Head ref.")
    build.add_argument("--generated-at", help="Deterministic timestamp for tests.")
    build.add_argument(
        "--validation-command",
        default="python3 scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json",
        help="Command used to validate the source report.",
    )
    build.set_defaults(func=build_command)

    validate = subparsers.add_parser("validate", help="Validate a safe Review Agent acceptance bundle directory.")
    validate.add_argument("--bundle-dir", required=True, help="Review Agent acceptance bundle directory.")
    validate.set_defaults(func=validate_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentAcceptanceBundleError as exc:
        raise SystemExit(f"error: {exc}") from exc
    except Exception as exc:
        if exc.__class__.__name__ in {"ReviewAgentReceiptError", "ReviewAgentReportError", "ReviewAgentPrCommentError"}:
            raise SystemExit(f"error: {exc}") from exc
        raise
