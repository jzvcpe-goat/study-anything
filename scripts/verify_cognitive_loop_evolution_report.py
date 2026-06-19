#!/usr/bin/env python3
"""Verify Cognitive Loop Evolution Report Lite."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_evolution.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-evolution-report.json"
SCHEMA_VERSION = "cognitive-loop-evolution-report-verification-v1"


def run_json(command: list[str], *, cwd: Path = ROOT, required: bool = True) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if required and completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    if completed.returncode != 0:
        return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not emit JSON: {' '.join(command)}\n{completed.stdout}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_no_forbidden_text(text: str, *, label: str) -> None:
    forbidden = [
        "sk-proj-",
        "bearer ",
        "raw source text",
        "raw diff",
        "learner answer:",
        "diff --git",
        "api_key",
        "agent endpoint:",
        "http://127.0.0.1:8787",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
        "disable tests",
        "lower risk threshold",
        "bypass human gate",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden if needle.lower() in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> dict[str, Path]:
    evidence_dir = root / ".cognitive-loop" / "events"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    healthy = evidence_dir / "healthy.json"
    failed = evidence_dir / "failed.json"
    write_json(
        healthy,
        {
            "schema_version": "fixture-evidence-v1",
            "status": "pass",
            "privacy": {
                "source_text_included": False,
                "raw_diff_included": False,
                "learner_answers_included": False,
                "agent_endpoint_included": False,
                "real_model_keys_stored": False,
            },
            "success_modes": {"study_card_count": 4, "quiz_item_count": 3},
        },
    )
    write_json(
        failed,
        {
            "schema_version": "fixture-evidence-v1",
            "status": "failed",
            "failure_modes": {
                "secret_target_rejected": True,
                "schema_validation_failed": True,
            },
            "privacy": {
                "source_text_included": False,
                "raw_diff_included": False,
                "learner_answers_included": False,
                "agent_endpoint_included": False,
                "real_model_keys_stored": False,
            },
        },
    )
    return {"healthy": healthy, "failed": failed}


def run_evolution(root: Path, args: list[str]) -> tuple[dict[str, Any], str]:
    report = run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "build",
            "--html",
            "--json",
            "--generated-at",
            "2026-01-01T00:00:00Z",
            *args,
        ]
    )
    html = (root / report["outputs"]["html_ref"]).read_text(encoding="utf-8")
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="evolution report")
    assert_no_forbidden_text(html, label="evolution html")
    if "Cognitive Loop Evolution Report Lite" not in html:
        raise RuntimeError("Evolution HTML missed product title.")
    if "Failure Clusters" not in html or "Proposed Improvements" not in html:
        raise RuntimeError("Evolution HTML missed required sections.")
    if report["privacy"]["read_only"] is not True:
        raise RuntimeError("Evolution report must stay read-only.")
    if report["privacy"]["model_called"] is not False or report["privacy"]["daemon_started"] is not False:
        raise RuntimeError("Evolution report must not call a model or start a daemon.")
    if report["policy_guardrails"]["auto_apply_default"] is not False:
        raise RuntimeError("Evolution report must default auto-apply off.")
    if report["policy_guardrails"]["policy_weakened"] is not False:
        raise RuntimeError("Evolution report must not weaken protected policy.")
    return report, html


def verify_success_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-") as tmp:
        root = Path(tmp)
        fixtures = write_fixture(root)
        before_hash = sha256_file(fixtures["failed"])
        report, _html = run_evolution(
            root,
            [
                "--evidence",
                ".cognitive-loop/events/healthy.json",
                "--evidence",
                ".cognitive-loop/events/failed.json",
                "--failure-summary",
                "Security verification failed in the release gate.",
            ],
        )
        after_hash = sha256_file(fixtures["failed"])
        if before_hash != after_hash:
            raise RuntimeError("Evolution report modified evidence input.")
        if report["schema_version"] != "cognitive-loop-evolution-report-lite-v1":
            raise RuntimeError("Evolution report schema drifted.")
        if report["status"] != "ready":
            raise RuntimeError("Evolution report success fixture should be ready.")
        if report["human_mastery_gate"]["required"] is not True:
            raise RuntimeError("High-risk evolution proposals must require a Human Mastery Gate.")
        if not report["failure_clusters"]:
            raise RuntimeError("Evolution report missed failure clusters.")
        if not report["root_cause_hypotheses"]:
            raise RuntimeError("Evolution report missed root-cause hypotheses.")
        if not report["proposed_improvements"]:
            raise RuntimeError("Evolution report missed proposed improvements.")
        if not report["regression_plan"]:
            raise RuntimeError("Evolution report missed regression plan.")
        if report["evolution_report"]["status"] != "needs_review":
            raise RuntimeError("High-risk report should be needs_review.")
        artifact_files = sorted((root / ".cognitive-loop" / "artifacts" / "evolution").glob("*"))
    return {
        "artifact_file_count": len(artifact_files),
        "cluster_count": len(report["failure_clusters"]),
        "root_cause_count": len(report["root_cause_hypotheses"]),
        "proposed_improvement_count": len(report["proposed_improvements"]),
        "high_risk_gate_required": report["human_mastery_gate"]["required"],
        "input_hash_unchanged": True,
        "html_json_created": True,
    }


def verify_degraded_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-degraded-") as tmp:
        root = Path(tmp)
        empty, _empty_html = run_evolution(root, [])
        missing, _missing_html = run_evolution(root, ["--evidence", ".cognitive-loop/events/missing.json"])
    if empty["status"] != "degraded":
        raise RuntimeError("Empty evidence should degrade.")
    if missing["status"] != "degraded":
        raise RuntimeError("Missing evidence should degrade.")
    if missing["evidence_sources"][0]["missing"] is not True:
        raise RuntimeError("Missing evidence should be explicit in evidence summary.")
    return {
        "empty_evidence_degraded": True,
        "missing_evidence_degraded": True,
        "missing_evidence_recorded": True,
    }


def verify_failure_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-failures-") as tmp:
        root = Path(tmp)
        (root / ".cognitive-loop" / "events").mkdir(parents=True, exist_ok=True)
        secret = root / ".cognitive-loop" / "events" / "secret.json"
        secret.write_text('{"schema_version":"x","status":"failed","value":"OPENAI_API_KEY=sk-proj-abcdefghijklmnop"}\n', encoding="utf-8")
        raw_body = run_json(
            [
                sys.executable,
                str(CLI),
                "--root",
                str(root),
                "build",
                "--failure-summary",
                "diff --git a/app.py b/app.py",
                "--json",
            ],
            required=False,
        )
        secret_body = run_json(
            [
                sys.executable,
                str(CLI),
                "--root",
                str(root),
                "build",
                "--evidence",
                ".cognitive-loop/events/secret.json",
                "--json",
            ],
            required=False,
        )
        weak_policy = run_json(
            [
                sys.executable,
                str(CLI),
                "--root",
                str(root),
                "build",
                "--failure-summary",
                "disable tests to speed up release",
                "--json",
            ],
            required=False,
        )
    if raw_body["returncode"] == 0:
        raise RuntimeError("Raw diff-like summary should fail.")
    if secret_body["returncode"] == 0:
        raise RuntimeError("Secret-looking evidence should fail.")
    if weak_policy["returncode"] == 0:
        raise RuntimeError("Policy-weakening summary should fail.")
    return {
        "raw_diff_body_rejected": True,
        "secret_evidence_rejected": True,
        "policy_weakening_rejected": True,
    }


def build_report() -> dict[str, Any]:
    success = verify_success_modes()
    degraded = verify_degraded_modes()
    failures = verify_failure_modes()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": "v0.3.31-alpha",
        "cli": "scripts/cognitive_loop_evolution.py",
        "artifact_schema": "cognitive-loop-evolution-report-lite-v1",
        "success_modes": success,
        "degraded_modes": degraded,
        "failure_modes": failures,
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_evolution_report.py --check",
            "example_command": "python3 scripts/cognitive_loop_evolution.py build --html --json",
            "release_gate": "scripts/release_check.sh",
        },
        "privacy": {
            "read_only": True,
            "source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "agent_endpoint_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "model_called": False,
            "daemon_started": False,
            "policy_weakened": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert_no_forbidden_text(text, label="verification report")
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        return 0
    if args.check:
        if not REPORT.exists():
            raise RuntimeError(f"Missing generated report: {REPORT.relative_to(ROOT)}")
        current = REPORT.read_text(encoding="utf-8")
        if current != text:
            raise RuntimeError(
                "Cognitive Loop Evolution Report Lite report is stale. "
                "Run `python3 scripts/verify_cognitive_loop_evolution_report.py --write`."
            )
        print("ok    Cognitive Loop Evolution Report Lite report is up to date")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
