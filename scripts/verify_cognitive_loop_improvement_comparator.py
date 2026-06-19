#!/usr/bin/env python3
"""Verify Cognitive Loop Measured Improvement Comparator Lite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "cognitive_loop_improvement_comparator.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-improvement-comparison.json"
SCHEMA_VERSION = "cognitive-loop-improvement-comparison-verification-v1"


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
        "agent metadata:",
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


def base_artifact(status: str = "ready") -> dict[str, Any]:
    return {
        "schema_version": "fixture-loop-evidence-v1",
        "status": status,
        "failure_clusters": [],
        "manual_only_actions": [],
        "eligible_actions": [],
        "human_mastery_gate": {"required": False},
        "privacy": {
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
            "source_files_modified": False,
        },
    }


def write_artifact(
    root: Path,
    name: str,
    *,
    status: str = "ready",
    clusters: int = 0,
    manual: int = 0,
    eligible: int = 0,
    gate: bool = False,
    privacy_leak: bool = False,
) -> Path:
    payload = base_artifact(status)
    payload["failure_clusters"] = [{"cluster_id": f"cluster-{index}"} for index in range(clusters)]
    payload["manual_only_actions"] = [{"action_id": f"manual-{index}"} for index in range(manual)]
    payload["eligible_actions"] = [{"action_id": f"eligible-{index}"} for index in range(eligible)]
    payload["human_mastery_gate"] = {"required": gate}
    if privacy_leak:
        payload["privacy"]["source_text_included"] = True
    path = root / ".cognitive-loop" / "artifacts" / "comparison-fixtures" / f"{name}.json"
    write_json(path, payload)
    return path


def run_compare(root: Path, artifacts: list[Path]) -> tuple[dict[str, Any], str]:
    command = [
        sys.executable,
        str(CLI),
        "--root",
        str(root),
        "compare",
        "--html",
        "--json",
        "--generated-at",
        "2026-01-01T00:00:00Z",
    ]
    for artifact in artifacts:
        command.extend(["--artifact", str(artifact.relative_to(root))])
    report = run_json(command)
    html = (root / report["outputs"]["html_ref"]).read_text(encoding="utf-8")
    assert_no_forbidden_text(json.dumps(report, ensure_ascii=False), label="comparison report")
    assert_no_forbidden_text(html, label="comparison html")
    if "Cognitive Loop Measured Improvement Comparator Lite" not in html:
        raise RuntimeError("Comparison HTML missed product title.")
    if "Artifact Metrics" not in html or "Delta" not in html:
        raise RuntimeError("Comparison HTML missed required sections.")
    if report["guardrails"]["read_only"] is not True:
        raise RuntimeError("Comparator must be read-only.")
    if report["guardrails"]["source_files_modified"] is not False:
        raise RuntimeError("Comparator must not modify source files.")
    if report["guardrails"]["apply_executed"] is not False:
        raise RuntimeError("Comparator must not execute apply.")
    return report, html


def verify_success_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-comparison-success-") as tmp:
        root = Path(tmp)
        noisy = write_artifact(root, "noisy", status="degraded", clusters=3, manual=2, eligible=0, gate=True)
        better = write_artifact(root, "better", status="ready", clusters=1, manual=0, eligible=2, gate=False)
        same_a = write_artifact(root, "same-a", status="ready", clusters=1, manual=1, eligible=1)
        same_b = write_artifact(root, "same-b", status="ready", clusters=1, manual=1, eligible=1)
        healthy = write_artifact(root, "healthy", status="ready", clusters=0, manual=0, eligible=2)
        worse = write_artifact(root, "worse", status="failed", clusters=4, manual=3, eligible=0, gate=True)
        mixed = write_artifact(root, "mixed", status="ready", clusters=5, manual=0, eligible=5)
        improved, _ = run_compare(root, [noisy, better])
        unchanged, _ = run_compare(root, [same_a, same_b])
        regressed, _ = run_compare(root, [healthy, worse])
        ambiguous, _ = run_compare(root, [healthy, mixed])
        insufficient, _ = run_compare(root, [healthy])
    if improved["status"] != "improved":
        raise RuntimeError("Expected improved comparison.")
    if unchanged["status"] != "unchanged":
        raise RuntimeError("Expected unchanged comparison.")
    if regressed["status"] != "regressed":
        raise RuntimeError("Expected regressed comparison.")
    if ambiguous["status"] != "ambiguous":
        raise RuntimeError("Expected ambiguous comparison.")
    if insufficient["status"] != "insufficient":
        raise RuntimeError("Expected insufficient comparison.")
    if improved["delta"]["cluster_count"] >= 0 or improved["delta"]["manual_only_count"] >= 0:
        raise RuntimeError("Improved comparison must show reduced bad evidence.")
    if improved["delta"]["eligible_action_count"] <= 0:
        raise RuntimeError("Improved comparison must show increased eligible action evidence.")
    return {
        "improved_status": improved["status"],
        "unchanged_status": unchanged["status"],
        "regressed_status": regressed["status"],
        "ambiguous_status": ambiguous["status"],
        "insufficient_status": insufficient["status"],
        "html_json_created": True,
        "read_only": True,
    }


def verify_privacy_and_failure_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-comparison-failures-") as tmp:
        root = Path(tmp)
        healthy = write_artifact(root, "healthy", status="ready", clusters=0, manual=0, eligible=1)
        privacy = write_artifact(root, "privacy", status="ready", clusters=0, manual=0, eligible=1, privacy_leak=True)
        privacy_report, _ = run_compare(root, [healthy, privacy])
        secret = root / ".cognitive-loop" / "artifacts" / "comparison-fixtures" / "secret.json"
        write_json(secret, {"schema_version": "fixture-loop-evidence-v1", "status": "failed", "value": "OPENAI_API_KEY=sk-proj-abcdefghijklmnop"})
        raw_diff = root / ".cognitive-loop" / "artifacts" / "comparison-fixtures" / "raw-diff.json"
        write_json(raw_diff, {"schema_version": "fixture-loop-evidence-v1", "status": "failed", "value": "diff --git a/app.py b/app.py"})
        weak_policy = root / ".cognitive-loop" / "artifacts" / "comparison-fixtures" / "weak-policy.json"
        write_json(weak_policy, {"schema_version": "fixture-loop-evidence-v1", "status": "failed", "value": "disable tests to speed up release"})
        malformed = root / ".cognitive-loop" / "artifacts" / "comparison-fixtures" / "malformed.json"
        malformed.write_text("{not-json\n", encoding="utf-8")
        invalid_schema = root / ".cognitive-loop" / "artifacts" / "comparison-fixtures" / "invalid-schema.json"
        write_json(invalid_schema, {"status": "ready"})
        secret_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "compare", "--artifact", str(secret.relative_to(root)), "--json"],
            required=False,
        )
        diff_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "compare", "--artifact", str(raw_diff.relative_to(root)), "--json"],
            required=False,
        )
        weak_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "compare", "--artifact", str(weak_policy.relative_to(root)), "--json"],
            required=False,
        )
        malformed_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "compare", "--artifact", str(malformed.relative_to(root)), "--json"],
            required=False,
        )
        invalid_schema_result = run_json(
            [sys.executable, str(CLI), "--root", str(root), "compare", "--artifact", str(invalid_schema.relative_to(root)), "--json"],
            required=False,
        )
    if privacy_report["status"] != "regressed":
        raise RuntimeError("Privacy flag regression should be regressed.")
    if privacy_report["delta"]["privacy_flag_count"] <= 0:
        raise RuntimeError("Privacy flag regression must be counted.")
    if secret_result["returncode"] == 0:
        raise RuntimeError("Secret-like artifact should fail.")
    if diff_result["returncode"] == 0:
        raise RuntimeError("Raw diff artifact should fail.")
    if weak_result["returncode"] == 0:
        raise RuntimeError("Policy-weakening artifact should fail.")
    if malformed_result["returncode"] == 0:
        raise RuntimeError("Malformed JSON artifact should fail.")
    if invalid_schema_result["returncode"] == 0:
        raise RuntimeError("Invalid schema artifact should fail.")
    return {
        "privacy_flag_regression_detected": True,
        "secret_artifact_rejected": True,
        "raw_diff_artifact_rejected": True,
        "policy_weakening_rejected": True,
        "malformed_json_rejected": True,
        "invalid_schema_rejected": True,
    }


def build_report() -> dict[str, Any]:
    success = verify_success_modes()
    failures = verify_privacy_and_failure_modes()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": "v0.3.31-alpha",
        "cli": "scripts/cognitive_loop_improvement_comparator.py",
        "artifact_schema": "cognitive-loop-improvement-comparison-lite-v1",
        "success_modes": success,
        "failure_modes": failures,
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_improvement_comparator.py --check",
            "example_command": "python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json",
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
            "apply_executed": False,
            "policy_weakened": False,
            "source_files_modified": False,
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
                "Cognitive Loop Improvement Comparator Lite report is stale. "
                "Run `python3 scripts/verify_cognitive_loop_improvement_comparator.py --write`."
            )
        print("ok    Cognitive Loop Improvement Comparator Lite report is up to date")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
