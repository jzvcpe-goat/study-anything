#!/usr/bin/env python3
"""Build read-only Cognitive Loop patch proposal artifacts."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "cognitive-loop-patch-proposal-lite-v1"

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
PATCH_CATEGORIES = ("prompt", "policy", "eval", "task", "doc", "retrieval")
FORBIDDEN_TARGET_FRAGMENTS = (
    ".env",
    ".pem",
    ".key",
    "secrets/",
    ".github/workflows/",
    ".cognitive-loop/permissions",
    ".cognitive-loop/risk",
)
DEFAULT_VERIFICATION = {
    "prompt": ["python3 scripts/verify_cognitive_loop_evolution_report.py --check"],
    "policy": ["python3 scripts/verify_cognitive_loop_contracts.py --check"],
    "eval": ["python3 scripts/verify_ecosystem_submission_pack.py"],
    "task": ["python3 scripts/verify_cognitive_loop_improvement_comparator.py --check"],
    "doc": ["python3 scripts/verify_platform_ecosystem_packs.py"],
    "retrieval": ["python3 scripts/verify_retrieval_quality.py --check"],
}


class PatchProposalError(RuntimeError):
    """Readable Patch Proposal Lite failure."""


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
        raise PatchProposalError(f"Path must stay under project root: {value}") from exc
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
        raise PatchProposalError(f"{label} contains private-looking text: literals={literal_hits} patterns={pattern_hits}")


def assert_no_policy_weakening(text: str, *, label: str) -> None:
    lowered = text.lower()
    hits = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if hits:
        raise PatchProposalError(f"{label} tries to weaken protected policy: {hits}")


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_private_text(text, label=label)
    assert_no_policy_weakening(text, label=label)


def normalize_target_path(value: Any, category: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return f".cognitive-loop/artifacts/patches/{category}-proposal.json"
    normalized = value.strip().replace("\\", "/").lstrip("/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    if normalized in {".", ".."} or normalized.startswith("../") or "/../" in normalized:
        raise PatchProposalError(f"Unsafe target path: {value}")
    return normalized


def is_forbidden_target(path: str) -> bool:
    lowered = path.lower()
    return any(fragment in lowered for fragment in FORBIDDEN_TARGET_FRAGMENTS)


def normalize_category(value: Any) -> str:
    raw = str(value or "task").lower().strip()
    aliases = {
        "docs": "doc",
        "documentation": "doc",
        "test": "eval",
        "tests": "eval",
        "evaluation": "eval",
        "retrieval_rule": "retrieval",
        "learning": "task",
    }
    raw = aliases.get(raw, raw)
    if raw not in PATCH_CATEGORIES:
        return "task"
    return raw


def load_artifact(root: Path, raw_path: str) -> tuple[dict[str, Any], str, str]:
    path = resolve_under_root(root, raw_path)
    if not path.is_file():
        raise PatchProposalError(f"Missing artifact: {relative_path(root, path)}")
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=relative_path(root, path))
    assert_no_policy_weakening(text, label=relative_path(root, path))
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PatchProposalError(f"Artifact must be valid JSON: {relative_path(root, path)}") from exc
    if not isinstance(payload, dict):
        raise PatchProposalError("Artifact must be a JSON object.")
    schema = payload.get("schema_version")
    if not isinstance(schema, str) or not schema:
        raise PatchProposalError("Artifact must include schema_version.")
    assert_public_payload(payload, label=relative_path(root, path))
    return payload, relative_path(root, path), sha256_bytes(data)


def degraded_reason(payload: Mapping[str, Any]) -> str:
    status = str(payload.get("status") or "").lower()
    schema = str(payload.get("schema_version") or "")
    if schema == "cognitive-loop-improvement-comparison-lite-v1" and status in {"insufficient", "regressed", "ambiguous"}:
        return f"Comparison status {status} requires manual review before patch proposal."
    if status in {"degraded", "failed", "error", "blocked"}:
        return f"Artifact status {status} is not eligible for patch proposal."
    return ""


def improvement_items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("proposed_improvements"), list):
        return [dict(item) for item in payload["proposed_improvements"] if isinstance(item, Mapping)]
    if isinstance(payload.get("eligible_actions"), list) or isinstance(payload.get("manual_only_actions"), list):
        items: list[dict[str, Any]] = []
        for action in payload.get("eligible_actions") or []:
            if isinstance(action, Mapping):
                items.append(
                    {
                        "target": action.get("target"),
                        "target_path": action.get("target_path"),
                        "change": action.get("change"),
                        "risk": action.get("risk", "low"),
                        "requires_human_mastery_gate": action.get("requires_human_mastery_gate", False),
                    }
                )
        for action in payload.get("manual_only_actions") or []:
            if isinstance(action, Mapping):
                items.append(
                    {
                        "target": action.get("target"),
                        "target_path": action.get("target_path"),
                        "change": action.get("change") or action.get("reason"),
                        "risk": action.get("risk", "medium"),
                        "requires_human_mastery_gate": action.get("requires_human_mastery_gate", True),
                        "manual_only_source": True,
                    }
                )
        return items
    if isinstance(payload.get("evolution_report"), Mapping):
        changes = payload["evolution_report"].get("proposed_changes") or []
        return [
            {"target": "task", "change": item, "risk": "low"}
            for item in changes
            if isinstance(item, str) and item.strip()
        ]
    return []


def candidate_from_improvement(index: int, item: Mapping[str, Any], source_ref: str, source_sha: str, source_reason: str) -> dict[str, Any]:
    category = normalize_category(item.get("target") or item.get("category"))
    intent = str(item.get("change") or item.get("summary") or "Record a bounded patch proposal.").strip()
    assert_no_private_text(intent, label=f"improvement[{index}].change")
    assert_no_policy_weakening(intent, label=f"improvement[{index}].change")
    risk = str(item.get("risk") or "medium").lower()
    target_path = normalize_target_path(item.get("target_path"), category)
    requires_gate = bool(item.get("requires_human_mastery_gate"))
    manual_only_source = bool(item.get("manual_only_source"))
    reason = source_reason
    eligible = True
    if risk != "low":
        eligible = False
        reason = "Only low-risk improvements can become patch candidates."
    if requires_gate:
        eligible = False
        reason = "Human Mastery Gate is required before this can become a patch candidate."
    if manual_only_source:
        eligible = False
        reason = "Source artifact marked this action manual-only."
    if is_forbidden_target(target_path):
        eligible = False
        reason = "Target path is protected from automatic patch proposal."
    if source_reason:
        eligible = False
    patch_id = f"patch-{sha256_text(f'{source_sha}:{index}:{category}:{target_path}:{intent}')[:12]}"
    return {
        "patch_id": patch_id,
        "source_ref": source_ref,
        "category": category,
        "target_path": target_path,
        "intent": intent,
        "risk": risk,
        "requires_human_mastery_gate": requires_gate,
        "manual_only": not eligible,
        "manual_reason": reason,
        "verification_commands": DEFAULT_VERIFICATION[category],
        "diff_body_included": False,
        "source_files_modified": False,
    }


def build_patch_proposal(
    *,
    artifacts: list[tuple[dict[str, Any], str, str]],
    generated_at: str,
    output_dir: Path,
    root: Path,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    manual_only: list[dict[str, Any]] = []
    degraded_sources: list[dict[str, str]] = []
    for payload, ref, digest in artifacts:
        reason = degraded_reason(payload)
        if reason:
            degraded_sources.append({"ref": ref, "reason": reason})
        for index, item in enumerate(improvement_items(payload)):
            candidate = candidate_from_improvement(index, item, ref, digest, reason)
            if candidate["manual_only"]:
                manual_only.append(candidate)
            else:
                candidates.append(candidate)
    if degraded_sources:
        status = "degraded"
    elif candidates and manual_only:
        status = "needs_review"
    elif candidates:
        status = "ready"
    else:
        status = "manual_only"
    proposal_id = f"patch-proposal-{sha256_text(generated_at + json.dumps(candidates + manual_only, sort_keys=True))[:16]}"
    proposal = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "proposal_id": proposal_id,
        "generated_at": generated_at,
        "title": "Cognitive Loop Patch Proposal Lite",
        "artifact_count": len(artifacts),
        "patch_candidates": candidates,
        "manual_only_candidates": manual_only,
        "degraded_sources": degraded_sources,
        "coverage": {
            category: sum(1 for item in candidates if item["category"] == category)
            for category in PATCH_CATEGORIES
        },
        "guardrails": {
            "read_only": True,
            "raw_unified_diff_generated": False,
            "apply_executed": False,
            "model_called": False,
            "daemon_started": False,
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
            "json_ref": relative_path(root, output_dir / "patch-proposal-lite.json"),
            "html_ref": relative_path(root, output_dir / "patch-proposal-lite.html"),
        },
        "commands": {
            "build": "python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json",
            "verify": "python3 scripts/verify_cognitive_loop_patch_proposal.py --check",
        },
    }
    assert_public_payload(proposal, label="patch proposal")
    return proposal


def render_html(proposal: Mapping[str, Any]) -> str:
    assert_public_payload(proposal, label="patch proposal html")

    def rows(items: Iterable[Mapping[str, Any]]) -> str:
        rendered: list[str] = []
        for item in items:
            rendered.append(
                "<tr>"
                + "".join(
                    f"<td>{escape(str(item.get(key, '')))}</td>"
                    for key in ("patch_id", "category", "risk", "target_path", "intent", "manual_reason")
                )
                + "</tr>"
            )
        return "\n".join(rendered)

    patch_candidates = proposal.get("patch_candidates")
    if not isinstance(patch_candidates, list):
        patch_candidates = []
    manual = proposal.get("manual_only_candidates")
    if not isinstance(manual, list):
        manual = []
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(str(proposal.get('title', 'Patch Proposal Lite')))}</title>
  <style>
    :root {{ color-scheme: light; --ink:#17201a; --muted:#5c6f65; --line:#d8e5dc; --paper:#fbfdf9; --accent:#2d6a4f; }}
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
    <h1>Cognitive Loop Patch Proposal Lite</h1>
    <p>Status: <code>{escape(str(proposal.get('status')))}</code>. This artifact is read-only and contains patch specifications, not source changes.</p>
    <h2>Patch Candidates</h2>
    <table><thead><tr><th>ID</th><th>Category</th><th>Risk</th><th>Target</th><th>Intent</th><th>Manual Reason</th></tr></thead><tbody>{rows([item for item in patch_candidates if isinstance(item, Mapping)])}</tbody></table>
    <h2>Manual-Only Candidates</h2>
    <table><thead><tr><th>ID</th><th>Category</th><th>Risk</th><th>Target</th><th>Intent</th><th>Manual Reason</th></tr></thead><tbody>{rows([item for item in manual if isinstance(item, Mapping)])}</tbody></table>
  </main>
</body>
</html>
"""


def cmd_build(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output_dir = resolve_under_root(root, args.output_dir)
    artifacts = [load_artifact(root, raw_path) for raw_path in args.artifact]
    proposal = build_patch_proposal(
        artifacts=artifacts,
        generated_at=args.generated_at,
        output_dir=output_dir,
        root=root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.json:
        (output_dir / "patch-proposal-lite.json").write_text(dump_json(proposal), encoding="utf-8")
    if args.html:
        (output_dir / "patch-proposal-lite.html").write_text(render_html(proposal), encoding="utf-8")
    print(dump_json(proposal), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Build a read-only patch proposal.")
    build.add_argument("--artifact", action="append", default=[], help="Metadata-only artifact JSON path.")
    build.add_argument("--generated-at", default="2026-01-01T00:00:00Z")
    build.add_argument("--output-dir", default=".cognitive-loop/artifacts/patches")
    build.add_argument("--html", action="store_true")
    build.add_argument("--json", action="store_true")
    build.set_defaults(func=cmd_build)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except PatchProposalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
