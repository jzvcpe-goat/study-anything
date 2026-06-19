#!/usr/bin/env python3
"""Build read-only Cognitive Loop Mastra evolution workflow replay artifacts."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "cognitive-loop-mastra-evolution-workflow-replay-v1"
RECEIPT_SCHEMA_VERSION = "cognitive-loop-mastra-evolution-receipt-link-v1"
WORKFLOW_ID = "cognitive-loop-evolution-workflow"
REQUIRED_ROLES = ("evolution_report", "apply_plan", "improvement_comparison", "patch_proposal")
VALID_RECEIPT_STATUSES = {"ready", "degraded", "blocked"}
SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bdiff --git\b"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
    re.compile(r"/Users/[^\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "learner answer:",
    "raw source text",
    "raw diff",
    "private source text",
    "agent endpoint:",
    "agent metadata:",
    "prompt:",
]
POLICY_WEAKENING_PHRASES = [
    "disable privacy",
    "skip privacy",
    "weaken privacy",
    "disable audit",
    "skip audit",
    "remove rollback",
    "skip rollback",
    "disable tests",
    "skip tests",
    "lower risk threshold",
    "weaken risk",
    "disable human gate",
    "bypass human gate",
    "loosen permissions",
]
PRIVACY_FALSE_KEYS = (
    "source_text_included",
    "raw_source_text_included",
    "raw_diff_included",
    "diff_bodies_included",
    "file_contents_included",
    "learner_answers_included",
    "agent_endpoint_included",
    "agent_endpoints_included",
    "agent_metadata_included",
    "prompt_text_included",
    "real_model_keys_stored",
    "model_called",
    "daemon_started",
    "mastra_workflow_started",
    "production_mastra_daemon_started",
    "apply_executed",
    "raw_unified_diff_generated",
    "policy_weakened",
    "source_files_modified",
)


class MastraEvolutionReplayError(RuntimeError):
    """Readable Mastra evolution workflow replay failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def resolve_under_root(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise MastraEvolutionReplayError(f"Path must stay under project root: {value}") from exc
    return path


def relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def assert_no_private_text(text: str, *, label: str) -> None:
    lowered = text.lower()
    literal_hits = [literal for literal in FORBIDDEN_LITERALS if literal.lower() in lowered]
    pattern_hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    if literal_hits or pattern_hits:
        raise MastraEvolutionReplayError(f"{label} contains private-looking text: literals={literal_hits} patterns={pattern_hits}")


def assert_no_policy_weakening(text: str, *, label: str) -> None:
    lowered = text.lower()
    hits = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if hits:
        raise MastraEvolutionReplayError(f"{label} tries to weaken protected policy: {hits}")


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_private_text(text, label=label)
    assert_no_policy_weakening(text, label=label)


def privacy_regressions(payload: Mapping[str, Any]) -> list[str]:
    regressions: list[str] = []
    for section_name in ("privacy", "guardrails", "runtime_boundaries"):
        section = payload.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for key in PRIVACY_FALSE_KEYS:
            if section.get(key) is True:
                regressions.append(f"{section_name}.{key}")
    links = payload.get("artifact_links")
    if isinstance(links, list):
        for index, link in enumerate(links):
            if isinstance(link, Mapping):
                for regression in link.get("privacy_regressions") or []:
                    regressions.append(f"artifact_links[{index}].{regression}")
    return sorted(set(regressions))


def load_receipt(root: Path, raw_path: str) -> tuple[dict[str, Any], str, str]:
    path = resolve_under_root(root, raw_path)
    if not path.is_file():
        raise MastraEvolutionReplayError(f"Missing receipt link artifact: {relative_path(root, path)}")
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=relative_path(root, path))
    assert_no_policy_weakening(text, label=relative_path(root, path))
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MastraEvolutionReplayError(f"Receipt link must be valid JSON: {relative_path(root, path)}") from exc
    if not isinstance(payload, dict):
        raise MastraEvolutionReplayError("Receipt link must be a JSON object.")
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise MastraEvolutionReplayError(f"Unsupported receipt link schema: {payload.get('schema_version')}")
    status = str(payload.get("status") or "").lower()
    if status not in VALID_RECEIPT_STATUSES:
        raise MastraEvolutionReplayError(f"Unsupported receipt link status: {status}")
    regressions = privacy_regressions(payload)
    if regressions:
        raise MastraEvolutionReplayError(f"Receipt link privacy regression detected: {', '.join(regressions)}")
    assert_public_payload(payload, label=relative_path(root, path))
    return payload, relative_path(root, path), sha256_bytes(data)


def link_roles(receipt: Mapping[str, Any]) -> set[str]:
    links = receipt.get("artifact_links")
    roles: set[str] = set()
    if isinstance(links, list):
        for item in links:
            if isinstance(item, Mapping):
                role = str(item.get("role") or "")
                if role:
                    roles.add(role)
    return roles


def receipt_blocker_text(receipt: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("blockers", "degraded_reasons"):
        value = receipt.get(key)
        if isinstance(value, list):
            parts.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
    links = receipt.get("artifact_links")
    if isinstance(links, list):
        for item in links:
            if isinstance(item, Mapping):
                value = item.get("blockers")
                if isinstance(value, list):
                    parts.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return " ".join(parts).lower()


def validate_receipt_semantics(receipt: Mapping[str, Any]) -> dict[str, Any]:
    status = str(receipt.get("status") or "").lower()
    roles = link_roles(receipt)
    missing_roles = [role for role in REQUIRED_ROLES if role not in roles]
    declared_missing = receipt.get("missing_roles")
    if not isinstance(declared_missing, list):
        declared_missing = []
    blocker_text = receipt_blocker_text(receipt)
    high_risk_blocked = "high-risk artifact lacks human mastery gate" in blocker_text
    manual_patch_blocked = "manual-only" in blocker_text or "review-required" in blocker_text

    if status == "ready" and missing_roles:
        raise MastraEvolutionReplayError(f"Ready receipt link cannot miss required role(s): {', '.join(missing_roles)}")
    if status == "ready" and declared_missing:
        raise MastraEvolutionReplayError("Ready receipt link cannot declare missing roles.")
    if status in {"ready", "degraded"} and high_risk_blocked:
        raise MastraEvolutionReplayError("High-risk ungated receipt link must be blocked before replay.")
    if status in {"ready", "degraded"} and manual_patch_blocked:
        raise MastraEvolutionReplayError("Manual-only PatchProposal receipt link must be blocked before replay.")

    return {
        "receipt_status": status,
        "roles": sorted(roles),
        "missing_roles": missing_roles,
        "declared_missing_roles": [str(item) for item in declared_missing],
        "high_risk_blocked": high_risk_blocked,
        "manual_patch_blocked": manual_patch_blocked,
    }


def step(step_id: str, status: str, reason: str, *, gate_action: str = "none") -> dict[str, Any]:
    return {
        "step_id": step_id,
        "status": status,
        "reason": reason,
        "gate_action": gate_action,
        "metadata_only": True,
        "future_mastra_step": True,
        "runs_mastra_now": False,
        "calls_model": False,
        "executes_apply": False,
        "modifies_source": False,
    }


def build_steps(receipt: Mapping[str, Any], semantics: Mapping[str, Any]) -> list[dict[str, Any]]:
    status = str(semantics["receipt_status"])
    missing_roles = semantics.get("missing_roles") or semantics.get("declared_missing_roles") or []
    if status == "ready":
        return [
            step("validate-evolution-receipt-link", "ready", "Receipt link schema, roles, privacy flags, and guardrails passed."),
            step("verify-artifact-role-coverage", "ready", "All required Evolution, Apply Plan, Improvement Comparison, and Patch Proposal roles are present."),
            step("human-gate-evaluation", "ready", "No ungated high-risk blocker is present.", gate_action="not_required"),
            step("patch-review", "ready", "PatchProposal is accepted as a read-only specification; no diff body or apply path is generated."),
            step("apply-plan-review", "ready", "Apply Plan is available only as a reviewed metadata-only input."),
            step("observability-receipt", "ready", "Replay can be recorded as local metadata-only observability DTOs."),
        ]
    if status == "degraded":
        return [
            step("validate-evolution-receipt-link", "manual_review", "Receipt link is valid but not complete enough for replay-ready workflow."),
            step("verify-artifact-role-coverage", "manual_review", f"Missing or degraded role evidence requires review: {', '.join(map(str, missing_roles)) or 'degraded evidence'}.", gate_action="review_required"),
            step("human-gate-evaluation", "manual_review", "Operator must review degraded evidence before any future runtime promotion.", gate_action="review_required"),
            step("patch-review", "manual_review", "Patch review stays read-only until missing evidence is resolved.", gate_action="review_required"),
            step("apply-plan-review", "skipped", "Apply-plan execution is unavailable for degraded receipt links."),
            step("observability-receipt", "manual_review", "Replay records degraded status for audit and future repair."),
        ]
    return [
        step("validate-evolution-receipt-link", "blocked", "Receipt link is blocked and cannot become a replay-ready workflow.", gate_action="blocked"),
        step("verify-artifact-role-coverage", "blocked", "Blocked evidence prevents executable workflow planning.", gate_action="blocked"),
        step("human-gate-evaluation", "blocked", "Human Mastery Gate or manual-only blocker must be resolved before promotion.", gate_action="blocked"),
        step("patch-review", "blocked", "PatchProposal remains manual-only or blocked; no apply path is generated.", gate_action="blocked"),
        step("apply-plan-review", "blocked", "Apply execution is disabled for blocked receipt links.", gate_action="blocked"),
        step("observability-receipt", "blocked", "Replay records blocked status only.", gate_action="blocked"),
    ]


def replay_status_for(receipt_status: str) -> str:
    if receipt_status == "ready":
        return "replay_ready"
    if receipt_status == "degraded":
        return "manual_review"
    return "blocked"


def build_replay(
    *,
    receipt: dict[str, Any],
    receipt_ref: str,
    receipt_sha256: str,
    generated_at: str,
    output_dir: Path,
    root: Path,
) -> dict[str, Any]:
    semantics = validate_receipt_semantics(receipt)
    receipt_status = str(semantics["receipt_status"])
    replay_status = replay_status_for(receipt_status)
    steps = build_steps(receipt, semantics)
    replay_id = f"mastra-evolution-replay-{sha256_text(receipt_sha256 + generated_at)[:16]}"
    replay = {
        "schema_version": SCHEMA_VERSION,
        "status": replay_status,
        "replay_id": replay_id,
        "generated_at": generated_at,
        "title": "Cognitive Loop Mastra Evolution Workflow Replay Lite",
        "source_receipt": {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "status": receipt_status,
            "ref": receipt_ref,
            "sha256": receipt_sha256,
            "link_id": receipt.get("link_id"),
        },
        "workflow": {
            "workflow_id": WORKFLOW_ID,
            "mode": "metadata_only_replay",
            "future_runtime": "mastra",
            "production_mastra_daemon_started": False,
            "mastra_workflow_started": False,
            "workflow_executed": False,
        },
        "workflow_steps": steps,
        "gate_actions": [
            {
                "step_id": item["step_id"],
                "gate_action": item["gate_action"],
                "status": item["status"],
            }
            for item in steps
            if item["gate_action"] != "none"
        ],
        "replay_summary": {
            "receipt_status": receipt_status,
            "replay_status": replay_status,
            "ready_for_future_mastra_workflow": replay_status == "replay_ready",
            "manual_review_required": replay_status == "manual_review",
            "blocked": replay_status == "blocked",
            "linked_roles": semantics["roles"],
            "missing_roles": semantics["missing_roles"],
            "high_risk_blocked": semantics["high_risk_blocked"],
            "manual_patch_blocked": semantics["manual_patch_blocked"],
        },
        "operator_next_commands": [
            "python3 scripts/verify_cognitive_loop_mastra_evolution_replay.py --check",
            "python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json",
            "python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check",
            "python3 scripts/verify_cognitive_loop_langfuse_observability.py --check",
        ],
        "guardrails": {
            "read_only": True,
            "raw_unified_diff_generated": False,
            "apply_executed": False,
            "model_called": False,
            "daemon_started": False,
            "production_mastra_daemon_started": False,
            "mastra_workflow_started": False,
            "source_files_modified": False,
            "policy_weakened": False,
        },
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
        },
        "outputs": {
            "json_ref": relative_path(root, output_dir / "mastra-evolution-workflow-replay.json"),
            "html_ref": relative_path(root, output_dir / "mastra-evolution-workflow-replay.html"),
        },
        "commands": {
            "replay": "python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json",
            "verify": "python3 scripts/verify_cognitive_loop_mastra_evolution_replay.py --check",
        },
    }
    assert_public_payload(replay, label="mastra evolution workflow replay")
    return replay


def render_html(replay: Mapping[str, Any]) -> str:
    assert_public_payload(replay, label="mastra evolution replay html")

    def rows(items: Iterable[Mapping[str, Any]]) -> str:
        rendered: list[str] = []
        for item in items:
            rendered.append(
                "<tr>"
                + "".join(
                    f"<td>{escape(str(item.get(key, '')))}</td>"
                    for key in ("step_id", "status", "gate_action", "reason")
                )
                + "</tr>"
            )
        return "\n".join(rendered)

    steps = replay.get("workflow_steps")
    if not isinstance(steps, list):
        steps = []
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(str(replay.get('title', 'Mastra Evolution Workflow Replay Lite')))}</title>
  <style>
    :root {{ color-scheme: light; --ink:#18211b; --muted:#5f7066; --line:#d8e5dc; --paper:#fbfdf9; --accent:#2d6a4f; }}
    body {{ margin:0; font-family: ui-serif, Georgia, serif; color:var(--ink); background:linear-gradient(180deg,#fbfdf9,#edf6f0); }}
    main {{ max-width:1120px; margin:0 auto; padding:48px 20px 72px; }}
    h1 {{ font-size:clamp(2rem,5vw,4rem); line-height:1; margin:0 0 12px; }}
    h2 {{ margin-top:34px; }}
    p {{ color:var(--muted); max-width:780px; }}
    table {{ border-collapse:collapse; width:100%; background:rgba(255,255,255,.72); }}
    th,td {{ border:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ background:#e5f1e9; }}
    code {{ color:var(--accent); }}
  </style>
</head>
<body>
  <main>
    <h1>Cognitive Loop Mastra Evolution Workflow Replay Lite</h1>
    <p>Status: <code>{escape(str(replay.get('status')))}</code>. This artifact replays a metadata-only EvolutionReceiptLink into future Mastra workflow steps; it does not start Mastra, call models, apply changes, or modify source files.</p>
    <h2>Workflow Steps</h2>
    <table><thead><tr><th>Step</th><th>Status</th><th>Gate</th><th>Reason</th></tr></thead><tbody>{rows([item for item in steps if isinstance(item, Mapping)])}</tbody></table>
  </main>
</body>
</html>
"""


def cmd_replay(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output_dir = resolve_under_root(root, args.output_dir)
    receipt, receipt_ref, receipt_sha256 = load_receipt(root, args.receipt)
    replay = build_replay(
        receipt=receipt,
        receipt_ref=receipt_ref,
        receipt_sha256=receipt_sha256,
        generated_at=args.generated_at,
        output_dir=output_dir,
        root=root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.json:
        (output_dir / "mastra-evolution-workflow-replay.json").write_text(dump_json(replay), encoding="utf-8")
    if args.html:
        (output_dir / "mastra-evolution-workflow-replay.html").write_text(render_html(replay), encoding="utf-8")
    print(dump_json(replay), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root.")
    sub = parser.add_subparsers(dest="command", required=True)
    replay = sub.add_parser("replay", help="Build a read-only Mastra evolution workflow replay.")
    replay.add_argument("--receipt", required=True, help="Mastra Evolution Receipt Link JSON path.")
    replay.add_argument("--generated-at", default="2026-01-01T00:00:00Z")
    replay.add_argument("--output-dir", default=".cognitive-loop/artifacts/mastra")
    replay.add_argument("--html", action="store_true")
    replay.add_argument("--json", action="store_true")
    replay.set_defaults(func=cmd_replay)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except MastraEvolutionReplayError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
