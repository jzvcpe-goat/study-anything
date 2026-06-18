#!/usr/bin/env python3
"""Verify Cognitive Loop Review Agent acceptance bundle assets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_FIXTURE_DIR = ROOT / "fixtures" / "review-agent"
BAD_BUNDLE_DIR = ROOT / "fixtures" / "review-agent-acceptance-bundles" / "raw-diff-leak"
CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_acceptance_bundle.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-acceptance-bundle.json"

SCHEMA_VERSION = "cognitive-loop-review-agent-acceptance-bundle-verification-v1"
BUNDLE_SCHEMA_VERSION = "cognitive-loop-review-agent-acceptance-bundle-v1"
REPORT_FIXTURES = ("approved.json", "needs-review.json", "needs-fix.json")
FIXED_GENERATED_AT = "2026-06-18T00:00:00+00:00"


class ReviewAgentAcceptanceBundleVerificationError(RuntimeError):
    """Readable Review Agent acceptance bundle verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_bundle_cli() -> Any:
    spec = importlib.util.spec_from_file_location("study_anything_review_agent_acceptance_bundle", CLI_PATH)
    if spec is None or spec.loader is None:
        raise ReviewAgentAcceptanceBundleVerificationError(f"Cannot load bundle CLI: {CLI_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentAcceptanceBundleVerificationError(message)


def build_bundle_for_fixture(module: Any, fixture_name: str, output_root: Path) -> dict[str, Any]:
    fixture_id = fixture_name.removesuffix(".json")
    output_dir = output_root / fixture_id
    args = argparse.Namespace(
        report=str(REPORT_FIXTURE_DIR / fixture_name),
        output_dir=str(output_dir),
        provider_id=f"fixture-{fixture_id}-review-agent",
        provider_label=f"Fixture {fixture_id} Review Agent",
        execution_surface="ci",
        pr_ref=f"PR-fixture-{fixture_id}",
        commit_sha=f"sha-fixture-{fixture_id}",
        base_ref="main",
        head_ref=f"codex/fixture-{fixture_id}",
        generated_at=FIXED_GENERATED_AT,
        validation_command="python3 scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json",
    )
    manifest = module.build_bundle(args)
    summary = module.validate_bundle_dir(output_dir)
    require(manifest["schema_version"] == BUNDLE_SCHEMA_VERSION, f"{fixture_name} bundle schema drifted.")
    for relative in ("manifest.json", "SUMMARY.md", "review-agent-ci-receipt.json", "review-agent-pr-comment-pack.json"):
        require((output_dir / relative).is_file(), f"{fixture_name} missing bundle artifact: {relative}")
    serialized = dump_json(manifest) + (output_dir / "SUMMARY.md").read_text(encoding="utf-8")
    for forbidden_text in ("diff --git", "@@ ", "subprocess.run(user_command"):
        require(forbidden_text not in serialized, f"{fixture_name} bundle leaked private text: {forbidden_text}")
    return {
        "summary": summary,
        "file_count": 4,
    }


def validate_bad_bundle(module: Any) -> str:
    try:
        module.validate_bundle_dir(BAD_BUNDLE_DIR)
    except Exception as exc:
        return str(exc)
    raise ReviewAgentAcceptanceBundleVerificationError("Bad acceptance bundle unexpectedly passed.")


def validate_docs() -> dict[str, str]:
    docs = {
        "docs/cognitive-loop-code-review.md": [
            "cognitive_loop_review_agent_acceptance_bundle.py build",
            "verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
        ],
        "docs/eval-frameworks.md": [
            "cognitive-loop-review-agent-acceptance-bundle-v1",
            "verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
        ],
        "evals/README.md": [
            "verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
        ],
        ".cognitive-loop/evals.yaml": [
            "cognitive-loop.review-agent-acceptance-bundle",
            "python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
        ],
        "scripts/release_check.sh": [
            "scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
        ],
        "platform/packs/kimi/README.md": [
            "cognitive_loop_review_agent_acceptance_bundle.py build",
            "verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
        ],
        "platform/packs/codex/README.md": [
            "cognitive_loop_review_agent_acceptance_bundle.py build",
            "verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
        ],
        "platform/packs/workbuddy/README.md": [
            "cognitive_loop_review_agent_acceptance_bundle.py build",
            "verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
        ],
    }
    checked: dict[str, str] = {}
    for relative, needles in docs.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        require(not missing, f"{relative} missing Review Agent acceptance bundle references: {missing}")
        checked[relative] = "pass"
    return checked


def build_report() -> dict[str, Any]:
    module = load_bundle_cli()
    with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-acceptance-") as tmp_name:
        output_root = Path(tmp_name)
        bundles = {fixture: build_bundle_for_fixture(module, fixture, output_root) for fixture in REPORT_FIXTURES}
    summaries = {fixture: value["summary"] for fixture, value in bundles.items()}
    decisions = {summary["decision"] for summary in summaries.values()}
    require(decisions == {"approved", "needs-review", "needs-fix"}, f"Bundle decision coverage drifted: {sorted(decisions)}")
    negative = {"raw-diff-leak": validate_bad_bundle(module)}
    docs = validate_docs()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "cli": "scripts/cognitive_loop_review_agent_acceptance_bundle.py",
        "bundle_count": len(summaries),
        "bundles": summaries,
        "negative_bundles": negative,
        "docs": docs,
        "quality_gates": {
            "decision_path_coverage": sorted(decisions),
            "bundle_files": ["manifest.json", "SUMMARY.md", "review-agent-ci-receipt.json", "review-agent-pr-comment-pack.json"],
            "metadata_only_bundle": "pass",
            "privacy_leak_rejection": "pass",
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
            "safe_to_attach_to_pr": True,
        },
        "acceptance": {
            "build_command": (
                "python3 scripts/cognitive_loop_review_agent_acceptance_bundle.py build "
                "--report REVIEW_AGENT_REPORT.json --output-dir /tmp/review-agent-acceptance"
            ),
            "validate_command": "python3 scripts/cognitive_loop_review_agent_acceptance_bundle.py validate --bundle-dir /tmp/review-agent-acceptance",
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check",
            "generated_report": "platform/generated/study-anything-cognitive-loop-review-agent-acceptance-bundle.json",
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
            raise SystemExit(f"Cognitive Loop Review Agent acceptance bundle report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent acceptance bundle report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentAcceptanceBundleVerificationError as exc:
        raise SystemExit(f"error: {exc}") from exc
