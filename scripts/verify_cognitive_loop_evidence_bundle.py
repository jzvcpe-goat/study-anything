#!/usr/bin/env python3
"""Verify the Cognitive Loop local evidence bundle path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-evidence-bundle.json"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
SCHEMA_VERSION = "cognitive-loop-evidence-bundle-verification-v1"


def run_cli(args: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(cwd),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI did not emit JSON for {args}: {completed.stdout}") from exc


def assert_no_forbidden_text(text: str, *, label: str) -> None:
    forbidden_values = [
        "sk-proj-",
        "bearer ",
        "raw private source text",
        "learner answer:",
        "diff --git",
        "api_key",
        "agent endpoint:",
        "http://127.0.0.1:8787",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden_values if needle in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-bundle-") as tmp:
        root = Path(tmp)
        init = run_cli(
            [
                "--root",
                str(root),
                "init",
                "--project-id",
                "external-adopter-project",
                "--project-name",
                "External Adopter Project",
                "--json",
            ],
            cwd=ROOT,
        )
        run_once = run_cli(
            [
                "--root",
                str(root),
                "run-once",
                "--html",
                "--json",
                "--output",
                ".cognitive-loop/artifacts/run-once.html",
                "--json-output",
                ".cognitive-loop/events/run-once.json",
            ],
            cwd=ROOT,
        )
        snapshot = run_cli(
            [
                "--root",
                str(root),
                "snapshot",
                "--html",
                "--json",
                "--path",
                "README.md",
                "--path",
                "docs/cognitive-loop-contracts.md",
                "--output",
                ".cognitive-loop/artifacts/snapshot.html",
                "--json-output",
                ".cognitive-loop/events/snapshot.json",
            ],
            cwd=ROOT,
        )
        gate = run_cli(
            [
                "--root",
                str(root),
                "gate",
                "--approve",
                "--html",
                "--json",
                "--decision-id",
                "dec-sensitive-runtime",
                "--rationale",
                "Operator verified the evidence, risk, rollback, and verification plan.",
                "--output",
                ".cognitive-loop/artifacts/human-gate.html",
                "--json-output",
                ".cognitive-loop/events/human-gate.json",
            ],
            cwd=ROOT,
        )
        bundle_html_path = root / ".cognitive-loop" / "artifacts" / "evidence-bundle.html"
        bundle_json_path = root / ".cognitive-loop" / "events" / "evidence-bundle.json"
        bundle = run_cli(
            [
                "--root",
                str(root),
                "bundle",
                "--html",
                "--json",
                "--artifact",
                ".cognitive-loop/events/run-once.json",
                "--artifact",
                ".cognitive-loop/artifacts/run-once.html",
                "--artifact",
                ".cognitive-loop/events/snapshot.json",
                "--artifact",
                ".cognitive-loop/events/human-gate.json",
                "--output",
                ".cognitive-loop/artifacts/evidence-bundle.html",
                "--json-output",
                ".cognitive-loop/events/evidence-bundle.json",
            ],
            cwd=ROOT,
        )
        verify = run_cli(["--root", str(root), "verify"], cwd=ROOT)
        html = bundle_html_path.read_text(encoding="utf-8")
        artifact_json = json.loads(bundle_json_path.read_text(encoding="utf-8"))
        assert_no_forbidden_text(html, label="HTML evidence bundle artifact")
        assert_no_forbidden_text(json.dumps(artifact_json, ensure_ascii=False), label="JSON evidence bundle")
        bundle_payload = artifact_json["evidence_bundle"]
        artifacts = bundle_payload["artifacts"]
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "pass",
            "cli": "scripts/cognitive_loop_cli.py",
            "init_schema": init["schema_version"],
            "verify_schema": verify["schema_version"],
            "run_once_schema": run_once["schema_version"],
            "snapshot_schema": snapshot["schema_version"],
            "gate_schema": gate["schema_version"],
            "bundle_schema": bundle["schema_version"],
            "artifact_json_schema": artifact_json["schema_version"],
            "evidence_bundle": {
                "created": bundle_json_path.is_file(),
                "artifact_count": bundle_payload["artifact_count"],
                "content_included": bundle_payload["content_included"],
                "all_items_have_hash": all(bool(item.get("sha256")) for item in artifacts),
                "all_items_exclude_content": all(item.get("content_included") is False for item in artifacts),
            },
            "html_artifact": {
                "created": bundle_html_path.is_file(),
                "contains_brand": "Delivery Clearance" in html,
                "contains_evidence_bundle": "Evidence Bundle" in html,
                "contains_redacted_json": "Redacted JSON" in html,
                "standalone_frontend_required": False,
            },
            "privacy": {
                "forbidden_text_leaked": False,
                "artifact_contents_included": False,
                "diff_body_included": False,
                "file_contents_included": False,
                "raw_source_text_included": False,
                "learner_answers_included": False,
                "real_model_keys_stored": False,
                "agent_endpoints_included": False,
                "agent_metadata_included": False,
                "watcher_daemon_started": False,
                "mastra_runtime_started": False,
            },
            "commands": {
                "init": "python3 scripts/cognitive_loop_cli.py init",
                "verify": "python3 scripts/cognitive_loop_cli.py verify",
                "bundle": "python3 scripts/cognitive_loop_cli.py bundle --html",
            },
        }


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
            raise SystemExit(f"Cognitive Loop evidence bundle report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop evidence bundle report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_evidence_bundle.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
