#!/usr/bin/env python3
"""Build governed low-risk Cognitive Loop apply-plan artifacts."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "cognitive-loop-apply-plan-lite-v1"
RECEIPT_SCHEMA_VERSION = "cognitive-loop-apply-receipt-lite-v1"

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
FORBIDDEN_TARGET_PREFIXES = (
    "README",
    "docs/",
    "scripts/",
    "apps/",
    "platform/",
    "skills/",
    ".github/",
    ".cognitive-loop/config",
    ".cognitive-loop/permissions",
    ".cognitive-loop/evals",
    ".cognitive-loop/risk",
)
ALLOWED_APPLY_PREFIX = ".cognitive-loop/artifacts/applied/"


class ApplyPlanError(RuntimeError):
    """Readable apply-plan failure."""


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
        raise ApplyPlanError(f"Path must stay under project root: {value}") from exc
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
        raise ApplyPlanError(f"{label} contains private-looking text: literals={literal_hits} patterns={pattern_hits}")


def assert_no_policy_weakening(text: str, *, label: str) -> None:
    lowered = text.lower()
    hits = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if hits:
        raise ApplyPlanError(f"{label} tries to weaken protected policy: {hits}")


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_private_text(text, label=label)
    assert_no_policy_weakening(text, label=label)


def load_proposal(root: Path, raw_path: str) -> tuple[dict[str, Any], str, str]:
    path = resolve_under_root(root, raw_path)
    if not path.is_file():
        raise ApplyPlanError(f"Missing proposal: {relative_path(root, path)}")
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=relative_path(root, path))
    assert_no_policy_weakening(text, label=relative_path(root, path))
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ApplyPlanError(f"Proposal must be valid JSON: {relative_path(root, path)}") from exc
    if not isinstance(payload, dict):
        raise ApplyPlanError("Proposal must be a JSON object.")
    assert_public_payload(payload, label="proposal")
    return payload, relative_path(root, path), sha256_bytes(data)


def normalize_target_path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return f"{ALLOWED_APPLY_PREFIX}apply-receipt.json"
    normalized = value.strip().replace("\\", "/").lstrip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if normalized in {".", ".."} or normalized.startswith("../") or "/../" in normalized:
        raise ApplyPlanError(f"Unsafe target path: {value}")
    return normalized


def is_forbidden_target(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in FORBIDDEN_TARGET_PREFIXES)


def action_from_improvement(index: int, improvement: Mapping[str, Any]) -> dict[str, Any]:
    change = str(improvement.get("change") or improvement.get("summary") or "").strip()
    if not change:
        change = "Record low-risk Cognitive Loop follow-up."
    assert_no_private_text(change, label=f"improvement[{index}].change")
    assert_no_policy_weakening(change, label=f"improvement[{index}].change")
    risk = str(improvement.get("risk") or "medium").lower()
    target = str(improvement.get("target") or "task")
    target_path = normalize_target_path(improvement.get("target_path"))
    requires_gate = bool(improvement.get("requires_human_mastery_gate"))
    explicitly_allowed = bool(improvement.get("explicitly_allowed") or improvement.get("allow_generated_artifact"))
    auto_apply = bool(improvement.get("auto_apply"))
    action_id = f"apply-{sha256_text(f'{index}:{target}:{target_path}:{change}')[:12]}"
    action = {
        "action_id": action_id,
        "target": target,
        "target_path": target_path,
        "change": change,
        "risk": risk,
        "auto_apply_requested": auto_apply,
        "explicitly_allowed": explicitly_allowed,
        "requires_human_mastery_gate": requires_gate,
        "source_files_modified": False,
        "execution_mode": "manual_only",
        "reason": "",
    }
    if risk != "low":
        action["reason"] = "Only low-risk improvements can enter the apply plan."
    elif requires_gate:
        action["reason"] = "Human Mastery Gate is required, so the action is manual-only."
    elif is_forbidden_target(target_path):
        action["reason"] = "Target path is not inside the generated artifact apply scope."
    elif not target_path.startswith(ALLOWED_APPLY_PREFIX):
        action["reason"] = "Apply Plan Lite can only write receipt markers under generated artifacts."
    else:
        action["execution_mode"] = "eligible_generated_artifact_receipt"
        action["reason"] = "Eligible for explicit generated-artifact receipt apply."
    return action


def extract_improvements(proposal: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = proposal.get("proposed_improvements")
    if raw is None and isinstance(proposal.get("evolution_report"), Mapping):
        raw = [
            {"target": "task", "change": item, "risk": "low", "target_path": f"{ALLOWED_APPLY_PREFIX}apply-receipt.json"}
            for item in proposal["evolution_report"].get("proposed_changes", [])
        ]
    if not isinstance(raw, list):
        raise ApplyPlanError("Proposal must include proposed_improvements or evolution_report.proposed_changes.")
    actions: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ApplyPlanError(f"Improvement {index} must be a JSON object.")
        actions.append(action_from_improvement(index, item))
    return actions


def build_receipt(*, plan_id: str, eligible_actions: list[dict[str, Any]], generated_at: str, applied: bool) -> dict[str, Any]:
    receipt_id = f"receipt-{sha256_text(plan_id + generated_at + json.dumps(eligible_actions, sort_keys=True))[:16]}"
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "plan_id": plan_id,
        "status": "applied" if applied else "dry_run",
        "applied": applied,
        "action_count": len(eligible_actions),
        "generated_at": generated_at,
        "write_scope": ALLOWED_APPLY_PREFIX.rstrip("/"),
        "source_files_modified": False,
        "actions": [
            {
                "action_id": item["action_id"],
                "target_path": item["target_path"],
                "receipt_only": True,
            }
            for item in eligible_actions
        ],
    }


def build_plan(
    *,
    proposal: Mapping[str, Any],
    proposal_ref: str,
    proposal_sha256: str,
    generated_at: str,
    output_dir: Path,
    root: Path,
    applied: bool,
) -> dict[str, Any]:
    actions = extract_improvements(proposal)
    eligible = [item for item in actions if item["execution_mode"] == "eligible_generated_artifact_receipt"]
    manual_only = [item for item in actions if item["execution_mode"] != "eligible_generated_artifact_receipt"]
    plan_id = f"apply-plan-{sha256_text(proposal_sha256 + generated_at)[:16]}"
    receipt = build_receipt(plan_id=plan_id, eligible_actions=eligible, generated_at=generated_at, applied=applied)
    status = "applied" if applied else "dry_run_ready"
    if not eligible:
        status = "manual_only"
    plan = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": generated_at,
        "plan_id": plan_id,
        "title": "Cognitive Loop Governed Apply Plan Lite",
        "proposal_ref": proposal_ref,
        "proposal_sha256": proposal_sha256,
        "eligible_actions": eligible,
        "manual_only_actions": manual_only,
        "receipt": receipt,
        "human_mastery_gate": {
            "required": False,
            "status": "not_required" if eligible else "manual_review_required",
            "reason": "" if eligible else "No low-risk generated-artifact receipt action is eligible.",
        },
        "guardrails": {
            "dry_run_default": True,
            "explicit_apply_required": True,
            "generated_artifact_scope_only": True,
            "allowed_write_prefix": ALLOWED_APPLY_PREFIX.rstrip("/"),
            "source_files_modified": False,
            "forbidden_write_targets": list(FORBIDDEN_TARGET_PREFIXES),
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
            "json_ref": relative_path(root, output_dir / "apply-plan-lite.json"),
            "html_ref": relative_path(root, output_dir / "apply-plan-lite.html"),
            "receipt_ref": relative_path(root, output_dir / "apply-receipt.json"),
            "marker_ref": relative_path(root, output_dir / "apply-receipt.marker"),
        },
        "commands": {
            "plan": "python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json",
            "apply": "python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --apply --allow-generated-artifacts --html --json",
            "verify": "python3 scripts/verify_cognitive_loop_apply_plan.py --check",
        },
    }
    assert_public_payload(plan, label="apply plan")
    return plan


def render_html(plan: Mapping[str, Any]) -> str:
    assert_public_payload(plan, label="apply plan html")

    def rows(items: Iterable[Mapping[str, Any]], *keys: str) -> str:
        rendered: list[str] = []
        for item in items:
            rendered.append("<tr>" + "".join(f"<td>{escape(str(item.get(key, '')))}</td>" for key in keys) + "</tr>")
        return "\n".join(rendered)

    eligible = plan.get("eligible_actions")
    if not isinstance(eligible, list):
        eligible = []
    manual = plan.get("manual_only_actions")
    if not isinstance(manual, list):
        manual = []
    eligible_rows = rows([item for item in eligible if isinstance(item, Mapping)], "action_id", "risk", "target_path", "change")
    manual_rows = rows([item for item in manual if isinstance(item, Mapping)], "action_id", "risk", "target_path", "reason")
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(str(plan.get('title', 'Apply Plan Lite')))}</title>
  <style>
    :root {{ color-scheme: light; --ink:#17201a; --muted:#5c6f65; --line:#d8e5dc; --paper:#fbfdf9; --accent:#2d6a4f; }}
    body {{ margin:0; font-family: ui-serif, Georgia, serif; color:var(--ink); background:linear-gradient(180deg,#fbfdf9,#edf6f0); }}
    main {{ max-width:1100px; margin:0 auto; padding:48px 20px 72px; }}
    h1 {{ font-size:clamp(2rem,5vw,4rem); line-height:1; margin:0 0 12px; }}
    h2 {{ margin-top:34px; }}
    p {{ color:var(--muted); max-width:760px; }}
    table {{ border-collapse:collapse; width:100%; background:rgba(255,255,255,.72); }}
    th,td {{ border:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }}
    th {{ background:#e5f1e9; }}
    code {{ color:var(--accent); }}
  </style>
</head>
<body>
  <main>
    <h1>Cognitive Loop Governed Apply Plan Lite</h1>
    <p>Status: <code>{escape(str(plan.get('status')))}</code>. This plan is dry-run by default and only writes generated-artifact receipts when explicitly allowed.</p>
    <h2>Eligible Generated-Artifact Receipt Actions</h2>
    <table><thead><tr><th>ID</th><th>Risk</th><th>Target Path</th><th>Change</th></tr></thead><tbody>{eligible_rows}</tbody></table>
    <h2>Manual-Only Actions</h2>
    <table><thead><tr><th>ID</th><th>Risk</th><th>Target Path</th><th>Reason</th></tr></thead><tbody>{manual_rows}</tbody></table>
  </main>
</body>
</html>
"""


def write_apply_receipt(root: Path, output_dir: Path, plan: Mapping[str, Any]) -> None:
    receipt = plan.get("receipt")
    if not isinstance(receipt, Mapping):
        raise ApplyPlanError("Apply receipt is missing.")
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = output_dir / "apply-receipt.json"
    marker_path = output_dir / "apply-receipt.marker"
    receipt_path.write_text(dump_json(receipt), encoding="utf-8")
    marker_path.write_text(f"{receipt['receipt_id']}\n", encoding="utf-8")
    for path in (receipt_path, marker_path):
        rel = relative_path(root, path)
        if not rel.startswith(ALLOWED_APPLY_PREFIX):
            raise ApplyPlanError(f"Receipt write escaped generated-artifact scope: {rel}")


def cmd_plan(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    proposal, proposal_ref, proposal_sha = load_proposal(root, args.proposal)
    output_dir = resolve_under_root(root, args.output_dir)
    output_rel = relative_path(root, output_dir)
    if not (output_rel + "/").startswith(ALLOWED_APPLY_PREFIX):
        raise ApplyPlanError(f"Output directory must be under {ALLOWED_APPLY_PREFIX}")
    if args.apply and not args.allow_generated_artifacts:
        raise ApplyPlanError("--apply requires --allow-generated-artifacts.")
    dry_plan = build_plan(
        proposal=proposal,
        proposal_ref=proposal_ref,
        proposal_sha256=proposal_sha,
        generated_at=args.generated_at,
        output_dir=output_dir,
        root=root,
        applied=False,
    )
    if args.apply:
        if not dry_plan["eligible_actions"]:
            raise ApplyPlanError("No low-risk generated-artifact receipt actions are eligible for apply.")
        if dry_plan["manual_only_actions"]:
            unsafe = [item for item in dry_plan["manual_only_actions"] if item.get("risk") != "low" or item.get("requires_human_mastery_gate")]
            if unsafe:
                raise ApplyPlanError("Cannot apply while medium/high-risk or gated actions are present.")
        plan = build_plan(
            proposal=proposal,
            proposal_ref=proposal_ref,
            proposal_sha256=proposal_sha,
            generated_at=args.generated_at,
            output_dir=output_dir,
            root=root,
            applied=True,
        )
    else:
        plan = dry_plan
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.json:
        (output_dir / "apply-plan-lite.json").write_text(dump_json(plan), encoding="utf-8")
    if args.html:
        (output_dir / "apply-plan-lite.html").write_text(render_html(plan), encoding="utf-8")
    if args.apply:
        write_apply_receipt(root, output_dir, plan)
    print(dump_json(plan), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root.")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Build a governed apply plan.")
    plan.add_argument("--proposal", required=True, help="Evolution Report Lite or metadata-only proposal JSON.")
    plan.add_argument("--generated-at", default="2026-01-01T00:00:00Z")
    plan.add_argument("--output-dir", default=".cognitive-loop/artifacts/applied")
    plan.add_argument("--html", action="store_true")
    plan.add_argument("--json", action="store_true")
    plan.add_argument("--apply", action="store_true")
    plan.add_argument("--allow-generated-artifacts", action="store_true")
    plan.set_defaults(func=cmd_plan)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except ApplyPlanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
