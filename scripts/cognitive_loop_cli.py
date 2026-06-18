#!/usr/bin/env python3
"""Local Cognitive Loop CLI for contracts and static artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE_PATH = (
    ROOT / "apps" / "api" / "study_anything" / "core" / "cognitive_loop_contracts.py"
)


class CognitiveLoopCliError(RuntimeError):
    """Readable CLI failure."""


def _load_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_cognitive_loop_contracts", CONTRACT_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise CognitiveLoopCliError(f"Cannot load Cognitive Loop module: {CONTRACT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contracts = _load_contract_module()


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def cmd_init(args: argparse.Namespace) -> int:
    reports = contracts.write_default_contract_files(
        _root(args),
        project_id=args.project_id,
        project_name=args.project_name,
        overwrite=args.force,
    )
    payload = {
        "schema_version": "cognitive-loop-cli-init-v1",
        "status": "ok",
        "root": str(_root(args)),
        "files": [report.public_dict() for report in reports],
        "next_commands": [
            "python3 scripts/cognitive_loop_cli.py verify",
            "python3 scripts/cognitive_loop_cli.py report --html",
        ],
    }
    if args.json:
        print(_dump(payload), end="")
    else:
        for item in payload["files"]:
            print(f"{item['status']}: {item['path']}")
        print("next: python3 scripts/cognitive_loop_cli.py verify")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    reports = contracts.validate_contract_files(_root(args))
    payload = {
        "schema_version": "cognitive-loop-cli-verify-v1",
        "status": "ok",
        "root": str(_root(args)),
        "files": [report.public_dict() for report in reports],
    }
    print(_dump(payload), end="")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    report = contracts.build_cli_artifact_report(
        _root(args),
        objective=args.objective,
        title=args.title,
        risk_level=args.risk_level,
    )
    wrote: list[str] = []
    if args.html:
        output = Path(args.output or (_root(args) / ".cognitive-loop" / "artifacts" / "cognitive-loop-report.html"))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contracts.render_cli_artifact_html(report), encoding="utf-8")
        wrote.append(str(output))
    if args.json_output:
        json_output = Path(args.json_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(_dump(report), encoding="utf-8")
        wrote.append(str(json_output))
    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(_dump(report), end="")
    return 0


def cmd_run_once(args: argparse.Namespace) -> int:
    root = _root(args)
    artifact_ref = args.output or ".cognitive-loop/artifacts/cognitive-loop-run-once.html"
    report = contracts.build_run_once_artifact(
        root,
        objective=args.objective,
        change_summary=args.change_summary,
        risk_level=args.risk_level,
        artifact_ref=artifact_ref,
    )
    wrote: list[str] = []
    if args.html:
        output = Path(artifact_ref)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contracts.render_cli_artifact_html(report), encoding="utf-8")
        wrote.append(str(output))

    json_output = Path(args.json_output or (root / ".cognitive-loop" / "events" / "cognitive-loop-run-once.json"))
    if not json_output.is_absolute():
        json_output = root / json_output
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(_dump(report), encoding="utf-8")
    wrote.append(str(json_output))

    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(_dump(report), end="")
    return 0


def _git_snapshot_paths(root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=str(root),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    paths: list[str] = []
    for line in completed.stdout.splitlines():
        if len(line) < 4:
            continue
        raw_path = line[3:].strip()
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1].strip()
        if raw_path:
            paths.append(raw_path)
    return paths


def cmd_snapshot(args: argparse.Namespace) -> int:
    root = _root(args)
    paths = list(args.path or [])
    if not paths:
        paths = _git_snapshot_paths(root)
    artifact_ref = args.output or ".cognitive-loop/artifacts/cognitive-loop-snapshot.html"
    report = contracts.build_project_snapshot_artifact(
        root,
        paths=paths,
        objective=args.objective,
        artifact_ref=artifact_ref,
    )
    wrote: list[str] = []
    if args.html:
        output = Path(artifact_ref)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contracts.render_cli_artifact_html(report), encoding="utf-8")
        wrote.append(str(output))

    json_output = Path(args.json_output or (root / ".cognitive-loop" / "events" / "cognitive-loop-snapshot.json"))
    if not json_output.is_absolute():
        json_output = root / json_output
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(_dump(report), encoding="utf-8")
    wrote.append(str(json_output))

    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(_dump(report), end="")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    root = _root(args)
    if args.approve == args.reject:
        raise CognitiveLoopCliError("Choose exactly one of --approve or --reject.")
    resolution = "approved" if args.approve else "rejected"
    artifact_ref = args.output or ".cognitive-loop/artifacts/cognitive-loop-human-gate.html"
    evidence_refs = list(args.evidence_ref or [])
    report = contracts.build_human_gate_artifact(
        root,
        decision_id=args.decision_id,
        resolution=resolution,
        rationale=args.rationale,
        operator_id=args.operator_id,
        objective=args.objective,
        artifact_ref=artifact_ref,
        evidence_refs=evidence_refs,
    )
    wrote: list[str] = []
    if args.html:
        output = Path(artifact_ref)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contracts.render_cli_artifact_html(report), encoding="utf-8")
        wrote.append(str(output))

    json_output = Path(args.json_output or (root / ".cognitive-loop" / "events" / "cognitive-loop-human-gate.json"))
    if not json_output.is_absolute():
        json_output = root / json_output
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(_dump(report), encoding="utf-8")
    wrote.append(str(json_output))

    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(_dump(report), end="")
    return 0


def _default_bundle_artifacts(root: Path) -> list[str]:
    candidates: list[str] = []
    for directory in (root / ".cognitive-loop" / "events", root / ".cognitive-loop" / "artifacts"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix in {".json", ".html", ".md"}:
                candidates.append(path.relative_to(root).as_posix())
    return candidates


def cmd_bundle(args: argparse.Namespace) -> int:
    root = _root(args)
    artifact_paths = list(args.artifact or [])
    if not artifact_paths:
        artifact_paths = _default_bundle_artifacts(root)
    artifact_ref = args.output or ".cognitive-loop/artifacts/cognitive-loop-evidence-bundle.html"
    report = contracts.build_evidence_bundle_artifact(
        root,
        artifact_paths=artifact_paths,
        objective=args.objective,
        artifact_ref=artifact_ref,
    )
    wrote: list[str] = []
    if args.html:
        output = Path(artifact_ref)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contracts.render_cli_artifact_html(report), encoding="utf-8")
        wrote.append(str(output))

    json_output = Path(args.json_output or (root / ".cognitive-loop" / "events" / "cognitive-loop-evidence-bundle.json"))
    if not json_output.is_absolute():
        json_output = root / json_output
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(_dump(report), encoding="utf-8")
    wrote.append(str(json_output))

    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(_dump(report), end="")
    return 0


def _default_event_index_events(root: Path) -> list[str]:
    directory = root / ".cognitive-loop" / "events"
    if not directory.is_dir():
        return []
    candidates: list[str] = []
    for path in sorted(directory.glob("*.json")):
        if path.name == "cognitive-loop-event-index.json":
            continue
        candidates.append(path.relative_to(root).as_posix())
    return candidates


def cmd_index(args: argparse.Namespace) -> int:
    root = _root(args)
    event_paths = list(args.event or [])
    if not event_paths:
        event_paths = _default_event_index_events(root)
    artifact_ref = args.output or ".cognitive-loop/artifacts/cognitive-loop-event-index.html"
    report = contracts.build_event_index_artifact(
        root,
        event_paths=event_paths,
        objective=args.objective,
        artifact_ref=artifact_ref,
    )
    wrote: list[str] = []
    if args.html:
        output = Path(artifact_ref)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contracts.render_cli_artifact_html(report), encoding="utf-8")
        wrote.append(str(output))

    json_output = Path(args.json_output or (root / ".cognitive-loop" / "events" / "cognitive-loop-event-index.json"))
    if not json_output.is_absolute():
        json_output = root / json_output
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(_dump(report), encoding="utf-8")
    wrote.append(str(json_output))

    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(_dump(report), end="")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = _root(args)
    artifact_ref = args.output or ".cognitive-loop/artifacts/cognitive-loop-artifact-doctor.html"
    report = contracts.build_artifact_doctor_artifact(
        root,
        objective=args.objective,
        artifact_ref=artifact_ref,
    )
    wrote: list[str] = []
    if args.html:
        output = Path(artifact_ref)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contracts.render_cli_artifact_html(report), encoding="utf-8")
        wrote.append(str(output))

    json_output = Path(args.json_output or (root / ".cognitive-loop" / "events" / "cognitive-loop-artifact-doctor.json"))
    if not json_output.is_absolute():
        json_output = root / json_output
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(_dump(report), encoding="utf-8")
    wrote.append(str(json_output))

    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(_dump(report), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository or project root.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create repo-local .cognitive-loop contracts.")
    init.add_argument("--project-id", default="study-anything")
    init.add_argument("--project-name", default="Study Anything")
    init.add_argument("--force", action="store_true", help="Overwrite existing contract files.")
    init.add_argument("--json", action="store_true")
    init.set_defaults(func=cmd_init)

    verify = sub.add_parser("verify", help="Validate repo-local .cognitive-loop contracts.")
    verify.set_defaults(func=cmd_verify)

    report = sub.add_parser("report", help="Render a redacted local Cognitive Loop artifact.")
    report.add_argument("--html", action="store_true", help="Write a static HTML report.")
    report.add_argument("--output", help="HTML output path. Defaults under .cognitive-loop/artifacts.")
    report.add_argument("--json-output", help="Optional JSON output path.")
    report.add_argument("--title", default="Cognitive Loop Local Readiness")
    report.add_argument(
        "--objective",
        default="Validate Cognitive Loop local contracts and create a shareable HTML artifact.",
    )
    report.add_argument("--risk-level", choices=sorted(contracts.ALLOWED_RISK_LEVELS), default="medium")
    report.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    report.set_defaults(func=cmd_report)

    run_once = sub.add_parser("run-once", help="Run one local Cognitive Loop evidence cycle.")
    run_once.add_argument("--html", action="store_true", help="Write a static HTML run artifact.")
    run_once.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-run-once.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    run_once.add_argument(
        "--json-output",
        help="JSON evidence output path. Defaults under .cognitive-loop/events.",
    )
    run_once.add_argument(
        "--objective",
        default="Run a bounded local Cognitive Loop evidence cycle.",
    )
    run_once.add_argument(
        "--change-summary",
        default="Validate local contracts and produce one governed run artifact.",
    )
    run_once.add_argument("--risk-level", choices=sorted(contracts.ALLOWED_RISK_LEVELS), default="medium")
    run_once.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    run_once.set_defaults(func=cmd_run_once)

    snapshot = sub.add_parser("snapshot", help="Capture redacted project snapshot events.")
    snapshot.add_argument("--html", action="store_true", help="Write a static HTML snapshot artifact.")
    snapshot.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-snapshot.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    snapshot.add_argument(
        "--json-output",
        help="JSON evidence output path. Defaults under .cognitive-loop/events.",
    )
    snapshot.add_argument(
        "--path",
        action="append",
        help="Repo-relative changed path. May be repeated. Defaults to git status paths.",
    )
    snapshot.add_argument(
        "--objective",
        default="Capture a redacted local project snapshot as Cognitive Loop evidence.",
    )
    snapshot.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    snapshot.set_defaults(func=cmd_snapshot)

    gate = sub.add_parser("gate", help="Record a local Human Mastery Gate resolution.")
    gate_resolution = gate.add_mutually_exclusive_group(required=True)
    gate_resolution.add_argument("--approve", action="store_true", help="Approve the gated decision.")
    gate_resolution.add_argument("--reject", action="store_true", help="Reject the gated decision.")
    gate.add_argument("--html", action="store_true", help="Write a static HTML gate artifact.")
    gate.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-human-gate.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    gate.add_argument(
        "--json-output",
        help="JSON evidence output path. Defaults under .cognitive-loop/events.",
    )
    gate.add_argument(
        "--decision-id",
        default="dec-cognitive-loop-human-gate",
        help="DecisionCard id being approved or rejected.",
    )
    gate.add_argument(
        "--rationale",
        default="Operator reviewed the decision, evidence, risk, and rollback plan.",
        help="Short public rationale. Do not include source text, answers, endpoints, or secrets.",
    )
    gate.add_argument("--operator-id", default="local-operator")
    gate.add_argument(
        "--objective",
        default="Record a local Human Mastery Gate resolution for a high-risk Cognitive Loop decision.",
    )
    gate.add_argument(
        "--evidence-ref",
        action="append",
        help="Public evidence reference. May be repeated.",
    )
    gate.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    gate.set_defaults(func=cmd_gate)

    bundle = sub.add_parser("bundle", help="Create a metadata-only local evidence bundle manifest.")
    bundle.add_argument("--html", action="store_true", help="Write a static HTML bundle artifact.")
    bundle.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-evidence-bundle.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    bundle.add_argument(
        "--json-output",
        help="JSON evidence output path. Defaults under .cognitive-loop/events.",
    )
    bundle.add_argument(
        "--artifact",
        action="append",
        help="Repo-relative artifact path to include. Defaults to local .cognitive-loop events/artifacts.",
    )
    bundle.add_argument(
        "--objective",
        default="Create a redacted local Cognitive Loop evidence bundle manifest.",
    )
    bundle.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    bundle.set_defaults(func=cmd_bundle)

    index = sub.add_parser("index", help="Create a metadata-only local event timeline index.")
    index.add_argument("--html", action="store_true", help="Write a static HTML event index artifact.")
    index.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-event-index.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    index.add_argument(
        "--json-output",
        help="JSON event-index output path. Defaults under .cognitive-loop/events.",
    )
    index.add_argument(
        "--event",
        action="append",
        help="Repo-relative event JSON path to include. Defaults to local .cognitive-loop/events JSON files.",
    )
    index.add_argument(
        "--objective",
        default="Create a redacted local Cognitive Loop event timeline index.",
    )
    index.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    index.set_defaults(func=cmd_index)

    doctor = sub.add_parser("doctor", help="Check local Cognitive Loop artifact consistency.")
    doctor.add_argument("--html", action="store_true", help="Write a static HTML doctor artifact.")
    doctor.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-artifact-doctor.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    doctor.add_argument(
        "--json-output",
        help="JSON doctor output path. Defaults under .cognitive-loop/events.",
    )
    doctor.add_argument(
        "--objective",
        default="Check local Cognitive Loop artifacts for metadata consistency before watcher automation.",
    )
    doctor.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except contracts.CognitiveLoopContractError as exc:
        raise SystemExit(f"cognitive-loop: {exc}") from exc
    except CognitiveLoopCliError as exc:
        raise SystemExit(f"cognitive-loop: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
