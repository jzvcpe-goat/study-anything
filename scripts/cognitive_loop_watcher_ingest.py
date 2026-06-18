#!/usr/bin/env python3
"""Manual watcher-event ingest for Cognitive Loop metadata artifacts."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE_PATH = (
    ROOT / "apps" / "api" / "study_anything" / "core" / "cognitive_loop_contracts.py"
)


class WatcherIngestError(RuntimeError):
    """Readable watcher ingest failure."""


def _load_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_cognitive_loop_contracts", CONTRACT_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise WatcherIngestError(f"Cannot load Cognitive Loop module: {CONTRACT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contracts = _load_contract_module()


FORBIDDEN_TEXT = (
    "sk-proj-",
    "bearer ",
    "raw private source text",
    "learner answer:",
    "diff --git",
    "api_key",
    "agent endpoint:",
    "http://127.0.0.1:8787",
)


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _assert_no_forbidden_text(value: Any, *, label: str) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    leaked = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if leaked:
        raise WatcherIngestError(f"{label} contains private-looking text: {leaked}")


def _safe_target(target: str) -> str:
    normalized = target.strip().replace("\\", "/")
    if not normalized:
        raise WatcherIngestError("watcher ingest target is required.")
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        raise WatcherIngestError(f"watcher ingest target must be repo-relative or symbolic: {target}")
    contracts._assert_public_value("watcher_target", normalized)  # type: ignore[attr-defined]
    return normalized


def _safe_refs(values: list[str], *, target: str, max_refs: int) -> list[str]:
    refs = list(values)
    if not refs:
        refs = [f"path:{target}"]
    safe: list[str] = []
    for raw_ref in refs:
        value = raw_ref.strip().replace("\\", "/")
        if not value:
            continue
        if value.startswith("/") or value.startswith("../") or "/../" in value:
            raise WatcherIngestError(f"watcher ingest ref must be repo-relative or symbolic: {raw_ref}")
        contracts._assert_public_value("watcher_ref", value)  # type: ignore[attr-defined]
        safe.append(value)
    deduped = list(dict.fromkeys(safe))
    if len(deduped) > max_refs:
        raise WatcherIngestError(f"watcher ingest refs exceed maxRefs={max_refs}.")
    return deduped


def _match_any(patterns: list[str], target: str) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatchcase(target, pattern) for pattern in patterns)


def _load_config(root: Path) -> dict[str, Any]:
    return contracts.validate_watcher_config_file(root)


def _select_watcher(config: Mapping[str, Any], watcher_id: str) -> dict[str, Any]:
    watchers = config.get("watchers")
    if not isinstance(watchers, list):
        raise WatcherIngestError("watcher config has no watchers list.")
    for watcher in watchers:
        if isinstance(watcher, Mapping) and watcher.get("id") == watcher_id:
            return dict(watcher)
    raise WatcherIngestError(f"watcher id is not configured: {watcher_id}")


def _ensure_target_allowed(watcher: Mapping[str, Any], target: str) -> None:
    include = watcher.get("include") if isinstance(watcher.get("include"), list) else []
    exclude = watcher.get("exclude") if isinstance(watcher.get("exclude"), list) else []
    if not _match_any([str(item) for item in include], target):
        raise WatcherIngestError(f"target is not included by watcher {watcher.get('id')}: {target}")
    if _match_any([str(item) for item in exclude], target):
        raise WatcherIngestError(f"target is excluded by watcher {watcher.get('id')}: {target}")


def _event_id(*, project_id: str, watcher_id: str, event_type: str, target: str, refs: list[str]) -> str:
    seed = "|".join([project_id, watcher_id, event_type, target, *refs])
    return "evt-watcher-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def build_watcher_ingest_artifact(
    root: Path,
    *,
    watcher_id: str,
    target: str,
    summary: str,
    refs: list[str],
    artifact_ref: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or contracts._utc_now()  # type: ignore[attr-defined]
    contracts._assert_public_value("watcher_summary", summary)  # type: ignore[attr-defined]
    contracts._assert_public_value("artifact_ref", artifact_ref)  # type: ignore[attr-defined]
    project = contracts._project_metadata(root)  # type: ignore[attr-defined]
    contract_reports = [report.public_dict() for report in contracts.validate_contract_files(root)]
    config = _load_config(root)
    watcher = _select_watcher(config, watcher_id)
    safe_target = _safe_target(target)
    _ensure_target_allowed(watcher, safe_target)
    max_refs = int((config.get("defaults") or {}).get("maxRefs", 12))
    safe_refs = _safe_refs(refs, target=safe_target, max_refs=max_refs)
    event_type = str(watcher["eventType"])
    source_kind = str(watcher["kind"])
    event = contracts.validate_project_event(
        {
            "event_id": _event_id(
                project_id=project["id"],
                watcher_id=watcher_id,
                event_type=event_type,
                target=safe_target,
                refs=safe_refs,
            ),
            "project_id": project["id"],
            "actor": "system",
            "event_type": event_type,
            "summary": summary,
            "timestamp": generated_at,
            "target": safe_target,
            "refs": [f"watcher:{watcher_id}", *safe_refs],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = contracts.validate_decision_card(
        {
            "decision_id": f"dec-{event['event_id']}",
            "project_id": project["id"],
            "title": "Ingest watcher ProjectEvent",
            "status": "approved",
            "summary": "Normalize one watcher observation into a metadata-only ProjectEvent artifact.",
            "event_ids": [event["event_id"]],
            "evidence_refs": [
                f"event:{event['event_id']}",
                "config:.cognitive-loop/watchers.yaml",
                f"artifact:{artifact_ref}",
            ],
            "risk": {
                "level": "low",
                "score": 0.18,
                "reasons": [
                    "metadata-only watcher ingest",
                    "manual command instead of daemon",
                    "file contents and diff bodies excluded",
                ],
            },
            "human_mastery_gate": {
                "required": False,
                "status": "not_required",
                "questions": [
                    "Can the operator explain which watcher produced the event?",
                    "Can the operator inspect refs without exposing source contents?",
                ],
            },
            "verification": {
                "status": "passed",
                "commands": [
                    "python3 scripts/cognitive_loop_watcher_ingest.py ingest --html",
                    "python3 scripts/verify_cognitive_loop_watcher_ingest.py --check",
                ],
            },
            "rollback": {"strategy": "delete_watcher_ingest_artifact", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop = contracts.validate_loop_run(
        {
            "run_id": f"loop-{event['event_id']}",
            "project_id": project["id"],
            "objective": "Record one watcher event as local Cognitive Loop evidence.",
            "status": "succeeded",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    report = {
        "schema_version": contracts.WATCHER_INGEST_SCHEMA_VERSION,
        "status": "ready",
        "generated_at": generated_at,
        "title": "Cognitive Loop Watcher Ingest",
        "objective": "Normalize a local watcher observation into a metadata-only ProjectEvent.",
        "project": project,
        "contract_files": contract_reports,
        "watcher_ingest": {
            "config_ref": ".cognitive-loop/watchers.yaml",
            "watcher_id": watcher_id,
            "source_kind": source_kind,
            "event_type": event_type,
            "target": safe_target,
            "refs": safe_refs,
            "ref_count": len(safe_refs),
            "content_mode": "metadata_only",
            "content_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "daemon_started": False,
            "selected_by_config": True,
        },
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "event_contents_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
        },
        "current_limits": [
            "This is a manual watcher ingest command, not a background watcher daemon.",
            "It records project-event metadata only and does not read or store source contents.",
            "Realtime HTML console, automatic debounce batching, and durable runtime handoff remain planned.",
        ],
        "commands": {
            "init_config": "python3 scripts/cognitive_loop_watcher_ingest.py init-config",
            "ingest": "python3 scripts/cognitive_loop_watcher_ingest.py ingest --html",
            "check": "python3 scripts/verify_cognitive_loop_watcher_ingest.py --check",
            "event_store": "python3 scripts/cognitive_loop_event_store.py rebuild",
        },
    }
    contracts._assert_public_value("watcher_ingest_artifact", report)  # type: ignore[attr-defined]
    _assert_no_forbidden_text(report, label="watcher ingest artifact")
    return report


def cmd_init_config(args: argparse.Namespace) -> int:
    report = contracts.write_default_watcher_config(_root(args), overwrite=args.force)
    payload = {
        "schema_version": contracts.WATCHER_CONFIG_SCHEMA_VERSION,
        "status": "ok",
        "root": str(_root(args)),
        "file": report.public_dict(),
        "daemon_started": False,
        "next_commands": [
            "python3 scripts/cognitive_loop_watcher_ingest.py ingest --html",
            "python3 scripts/verify_cognitive_loop_watcher_ingest.py --check",
        ],
    }
    print(_dump(payload), end="")
    return 0


def cmd_validate_config(args: argparse.Namespace) -> int:
    config = _load_config(_root(args))
    payload = {
        "schema_version": contracts.WATCHER_CONFIG_SCHEMA_VERSION,
        "status": "pass",
        "root": str(_root(args)),
        "watcher_count": len(config["watchers"]),
        "mode": config["mode"],
        "daemon": config["daemon"],
        "content_mode": config["defaults"]["contentMode"],
    }
    print(_dump(payload), end="")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    root = _root(args)
    artifact_ref = args.output or ".cognitive-loop/artifacts/cognitive-loop-watcher-ingest.html"
    report = build_watcher_ingest_artifact(
        root,
        watcher_id=args.watcher_id,
        target=args.target,
        summary=args.summary,
        refs=list(args.ref or []),
        artifact_ref=artifact_ref,
        generated_at=args.generated_at,
    )
    wrote: list[str] = []
    if args.html:
        output = Path(artifact_ref)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(contracts.render_cli_artifact_html(report), encoding="utf-8")
        wrote.append(str(output))

    json_output = Path(args.json_output or (root / ".cognitive-loop" / "events" / "cognitive-loop-watcher-ingest.json"))
    if not json_output.is_absolute():
        json_output = root / json_output
    json_output.parent.mkdir(parents=True, exist_ok=True)
    serialized = _dump(report)
    json_output.write_text(serialized, encoding="utf-8")
    wrote.append(str(json_output))

    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(serialized, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository or project root.")
    sub = parser.add_subparsers(dest="command", required=True)

    init_config = sub.add_parser("init-config", help="Create optional watcher ingest config.")
    init_config.add_argument("--force", action="store_true", help="Overwrite .cognitive-loop/watchers.yaml.")
    init_config.set_defaults(func=cmd_init_config)

    validate_config = sub.add_parser("validate-config", help="Validate optional watcher ingest config.")
    validate_config.set_defaults(func=cmd_validate_config)

    ingest = sub.add_parser("ingest", help="Write one metadata-only watcher ProjectEvent artifact.")
    ingest.add_argument("--html", action="store_true", help="Write a static HTML artifact.")
    ingest.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-watcher-ingest.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    ingest.add_argument(
        "--json-output",
        help="JSON evidence output path. Defaults under .cognitive-loop/events.",
    )
    ingest.add_argument("--watcher-id", default="file-change", help="Configured watcher id.")
    ingest.add_argument("--target", required=True, help="Repo-relative or symbolic watcher target.")
    ingest.add_argument(
        "--summary",
        default="Captured a local watcher observation without source contents.",
        help="Short public event summary. Do not include file contents, diffs, endpoints, or secrets.",
    )
    ingest.add_argument(
        "--ref",
        action="append",
        help="Public metadata ref such as path:README.md, git:HEAD, test:api. May be repeated.",
    )
    ingest.add_argument("--generated-at", help="Optional ISO timestamp for deterministic verification.")
    ingest.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    ingest.set_defaults(func=cmd_ingest)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except contracts.CognitiveLoopContractError as exc:
        raise SystemExit(f"cognitive-loop-watcher-ingest: {exc}") from exc
    except WatcherIngestError as exc:
        raise SystemExit(f"cognitive-loop-watcher-ingest: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
