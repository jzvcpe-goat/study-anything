#!/usr/bin/env python3
"""Verify the Cognitive Loop advisory code review flow."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE_PATH = (
    ROOT / "apps" / "api" / "study_anything" / "core" / "cognitive_loop_contracts.py"
)
REVIEW_MODULE_PATH = ROOT / "apps" / "api" / "study_anything" / "core" / "cognitive_loop_review.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name}: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contracts = _load_module("study_anything_cognitive_loop_contracts", CONTRACT_MODULE_PATH)
review = _load_module("study_anything_cognitive_loop_review", REVIEW_MODULE_PATH)


REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review.json"
SCHEMA_VERSION = "cognitive-loop-code-review-verification-v1"
SECRET_PROBE = "OPENAI_API_KEY=sk-proj-thissecretmustnotappear000000"


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def assert_no_forbidden_text(text: str, *, label: str) -> None:
    forbidden = [
        SECRET_PROBE,
        "sk-proj-thissecretmustnotappear000000",
        "raw diff body",
        "file body should stay private",
        "http://private-agent.local",
        "model API key",
    ]
    leaked = [item for item in forbidden if item in text]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def prepare_fixture_repo(root: Path) -> None:
    contracts.write_default_contract_files(
        root,
        project_id="external-review-fixture",
        project_name="External Review Fixture",
    )
    (root / "README.md").write_text("# External Review Fixture\n", encoding="utf-8")
    run(["git", "init"], cwd=root)
    run(["git", "config", "user.email", "review@example.local"], cwd=root)
    run(["git", "config", "user.name", "Review Fixture"], cwd=root)
    run(["git", "add", "."], cwd=root)
    run(["git", "commit", "-m", "baseline"], cwd=root)
    run(["git", "branch", "-M", "main"], cwd=root)
    run(["git", "switch", "-c", "review-fixture"], cwd=root)

    api_dir = root / "apps" / "api" / "study_anything" / "core"
    api_dir.mkdir(parents=True, exist_ok=True)
    # This test-only repository contains a synthetic token to prove review output redaction.
    # codeql[py/clear-text-storage-sensitive-data]
    (api_dir / "auth_guard.py").write_text(
        f"# file body should stay private\nPROBE = {SECRET_PROBE!r}\n",
        encoding="utf-8",
    )
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "new_review_tool.py").write_text(
        "print('local review fixture')\n",
        encoding="utf-8",
    )
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "review.md").write_text(
        "This public doc update is safe to reference by path.\n",
        encoding="utf-8",
    )
    run(["git", "add", "."], cwd=root)
    run(["git", "commit", "-m", "review fixture changes"], cwd=root)


def build_cli_artifacts(root: Path) -> tuple[dict[str, Any], str]:
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "cognitive_loop_review.py"),
            "--root",
            str(root),
            "--base",
            "main",
            "--head",
            "HEAD",
            "--html",
            "--output",
            ".cognitive-loop/artifacts/review.html",
            "--json-output",
            ".cognitive-loop/events/review.json",
        ],
        cwd=ROOT,
    )
    json_path = root / ".cognitive-loop" / "events" / "review.json"
    html_path = root / ".cognitive-loop" / "artifacts" / "review.html"
    artifact_json = json.loads(json_path.read_text(encoding="utf-8"))
    artifact_html = html_path.read_text(encoding="utf-8")
    return artifact_json, artifact_html


def validate_review_output(artifact_json: dict[str, Any], artifact_html: str) -> dict[str, Any]:
    review.validate_review_artifact(artifact_json)
    serialized = json.dumps(artifact_json, ensure_ascii=False, sort_keys=True)
    assert_no_forbidden_text(serialized, label="JSON review artifact")
    assert_no_forbidden_text(artifact_html, label="HTML review artifact")

    review_run = artifact_json["review_run"]
    findings = review_run["findings"]
    gaps = review_run["test_gaps"]
    gate = review_run["security_gate"]
    decision = review_run["decision"]
    metrics = review_run["metrics"]
    if len(findings) > review.MAX_REVIEW_FINDINGS:
        raise RuntimeError("Review finding cap was not enforced.")
    required_finding_fields = {
        "file_path",
        "diff_ref",
        "risk_level",
        "confidence",
        "verification_command",
    }
    for finding in findings:
        missing = sorted(required_finding_fields - set(finding))
        if missing:
            raise RuntimeError(f"ReviewFinding missing fields: {missing}")
        if float(finding["confidence"]) < 0.7:
            raise RuntimeError("ReviewFinding confidence is below the high-confidence floor.")
    if gate["blocking"] is not False or gate["merge_blocked"] is not False:
        raise RuntimeError("Review security gate must be advisory-only.")
    if decision["merge_blocked"] is not False:
        raise RuntimeError("Review decision must not block merge in v0.1.")
    if metrics["raw_diff_included"] is not False or metrics["file_contents_included"] is not False:
        raise RuntimeError("Review metrics must prove raw diff and file contents are excluded.")
    if metrics["model_keys_stored"] is not False or metrics["agent_endpoints_stored"] is not False:
        raise RuntimeError("Review metrics must prove no key or Agent endpoint custody.")
    if artifact_json["risk_mapping"]["source"] != ".cognitive-loop/risk.yaml":
        raise RuntimeError("Review artifact must identify .cognitive-loop/risk.yaml as risk source.")
    if "Cognitive Loop Code Review" not in artifact_html or "Merge Blocked" not in artifact_html:
        raise RuntimeError("HTML review artifact is missing expected review sections.")
    return {
        "schema": artifact_json["schema_version"],
        "status": artifact_json["status"],
        "finding_count": len(findings),
        "test_gap_count": len(gaps),
        "highest_risk": metrics["highest_risk"],
        "blocking": gate["blocking"],
        "merge_blocked": decision["merge_blocked"],
        "max_findings": metrics["max_findings"],
        "html_contains_review": "Cognitive Loop Code Review" in artifact_html,
    }


def exercise_pr_summary_modes(root: Path) -> dict[str, Any]:
    summary_path = root / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "changed_files": [
                    {
                        "path": "scripts/from-pr-summary.py",
                        "status": "M",
                        "insertions": 4,
                        "deletions": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    changes = review.load_pr_summary_changes(summary_path, base_ref="main", head_ref="feature")
    artifact = review.build_review_artifact(
        root,
        changes=changes,
        source="pr_summary",
        base_ref="main",
        head_ref="feature",
        generated_at="2026-06-18T00:00:00Z",
    )
    review.validate_review_artifact(artifact)

    bad_path = root / "bad-summary.json"
    bad_path.write_text(
        json.dumps({"raw_diff": "raw diff body", "changed_files": []}),
        encoding="utf-8",
    )
    rejected_raw_summary = False
    try:
        review.load_pr_summary_changes(bad_path)
    except review.CognitiveLoopReviewError:
        rejected_raw_summary = True
    if not rejected_raw_summary:
        raise RuntimeError("PR summary raw_diff field was not rejected.")
    return {
        "pr_summary_supported": artifact["review_run"]["source"] == "pr_summary",
        "raw_pr_summary_rejected": rejected_raw_summary,
    }


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-review-") as tmp:
        fixture_root = Path(tmp)
        prepare_fixture_repo(fixture_root)
        artifact_json, artifact_html = build_cli_artifacts(fixture_root)
        output_summary = validate_review_output(artifact_json, artifact_html)
        pr_summary = exercise_pr_summary_modes(fixture_root)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "review_artifact": output_summary,
        "pr_summary": pr_summary,
        "privacy": {
            "raw_diff_included": False,
            "file_contents_included": False,
            "secret_probe_leaked": False,
            "model_keys_stored": False,
            "agent_endpoints_stored": False,
            "agent_reasoning_included": False,
        },
        "risk_mapping": {
            "source": ".cognitive-loop/risk.yaml",
            "evals_source": ".cognitive-loop/evals.yaml",
            "advisory_only": True,
            "hard_gate_enabled": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_review.py --check",
            "review_command": "python3 scripts/cognitive_loop_review.py --base main --head HEAD --html",
            "generated_report": "platform/generated/study-anything-cognitive-loop-review.json",
        },
    }


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


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
            raise SystemExit(f"Cognitive Loop review report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop review report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
