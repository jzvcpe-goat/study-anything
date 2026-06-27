#!/usr/bin/env python3
"""Build read-only Cognitive Loop Mastra evolution receipt-link artifacts."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "cognitive-loop-mastra-evolution-receipt-link-v1"
WORKFLOW_ID = "cognitive-loop-evolution-workflow"
REQUIRED_ROLES = ("evolution_report", "apply_plan", "improvement_comparison", "patch_proposal")
ALLOWED_SCHEMAS = {
    "cognitive-loop-evolution-report-lite-v1": "evolution_report",
    "cognitive-loop-apply-plan-lite-v1": "apply_plan",
    "cognitive-loop-improvement-comparison-lite-v1": "improvement_comparison",
    "cognitive-loop-patch-proposal-lite-v1": "patch_proposal",
}
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
    "apply_executed",
    "raw_unified_diff_generated",
    "policy_weakened",
    "source_files_modified",
)


class MastraEvolutionReceiptError(RuntimeError):
    """Readable Mastra evolution receipt-link failure."""


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
        raise MastraEvolutionReceiptError(f"Path must stay under project root: {value}") from exc
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
        raise MastraEvolutionReceiptError(f"{label} contains private-looking text: literals={literal_hits} patterns={pattern_hits}")


def assert_no_policy_weakening(text: str, *, label: str) -> None:
    lowered = text.lower()
    hits = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if hits:
        raise MastraEvolutionReceiptError(f"{label} tries to weaken protected policy: {hits}")


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_private_text(text, label=label)
    assert_no_policy_weakening(text, label=label)


def load_artifact(root: Path, raw_path: str) -> tuple[dict[str, Any], str, str, str]:
    path = resolve_under_root(root, raw_path)
    if not path.is_file():
        raise MastraEvolutionReceiptError(f"Missing artifact: {relative_path(root, path)}")
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=relative_path(root, path))
    assert_no_policy_weakening(text, label=relative_path(root, path))
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MastraEvolutionReceiptError(f"Artifact must be valid JSON: {relative_path(root, path)}") from exc
    if not isinstance(payload, dict):
        raise MastraEvolutionReceiptError("Artifact must be a JSON object.")
    schema = payload.get("schema_version")
    if schema not in ALLOWED_SCHEMAS:
        raise MastraEvolutionReceiptError(f"Unsupported artifact schema for Mastra receipt link: {schema}")
    assert_public_payload(payload, label=relative_path(root, path))
    return payload, relative_path(root, path), sha256_bytes(data), str(schema)


def privacy_regressions(payload: Mapping[str, Any]) -> list[str]:
    regressions: list[str] = []
    for section_name in ("privacy", "guardrails"):
        section = payload.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for key in PRIVACY_FALSE_KEYS:
            if section.get(key) is True:
                regressions.append(f"{section_name}.{key}")
    return sorted(set(regressions))


def has_high_risk_without_gate(payload: Mapping[str, Any]) -> bool:
    collections: list[Any] = []
    for key in ("proposed_improvements", "eligible_actions", "manual_only_actions", "patch_candidates", "manual_only_candidates"):
        value = payload.get(key)
        if isinstance(value, list):
            collections.extend(value)
    evolution_report = payload.get("evolution_report")
    if isinstance(evolution_report, Mapping):
        value = evolution_report.get("proposed_improvements")
        if isinstance(value, list):
            collections.extend(value)
    for item in collections:
        if not isinstance(item, Mapping):
            continue
        risk = str(item.get("risk") or "").lower()
        gate = bool(item.get("requires_human_mastery_gate"))
        if risk in {"high", "blocked"} and not gate:
            return True
    return False


def patch_requires_manual(payload: Mapping[str, Any]) -> bool:
    if ALLOWED_SCHEMAS.get(str(payload.get("schema_version"))) != "patch_proposal":
        return False
    if str(payload.get("status") or "").lower() in {"manual_only", "needs_review", "blocked"}:
        return True
    manual = payload.get("manual_only_candidates")
    return isinstance(manual, list) and len(manual) > 0


def artifact_link(payload: Mapping[str, Any], ref: str, digest: str, schema: str) -> dict[str, Any]:
    role = ALLOWED_SCHEMAS[schema]
    status = str(payload.get("status") or "unknown")
    blockers: list[str] = []
    regressions = privacy_regressions(payload)
    if regressions:
        blockers.append(f"privacy regression: {', '.join(regressions)}")
    if has_high_risk_without_gate(payload):
        blockers.append("high-risk artifact lacks Human Mastery Gate")
    if patch_requires_manual(payload):
        blockers.append("PatchProposal contains manual-only or review-required candidates")
    if status.lower() in {"failed", "error", "blocked"}:
        blockers.append(f"artifact status is {status}")
    return {
        "role": role,
        "schema_version": schema,
        "status": status,
        "ref": ref,
        "sha256": digest,
        "accepted_for_mastra_receipt": not blockers,
        "blockers": blockers,
        "privacy_regressions": regressions,
    }


def build_workflow_steps(links: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    step_names = {
        "evolution_report": "ingest-evolution-report",
        "apply_plan": "ingest-governed-apply-plan",
        "improvement_comparison": "ingest-improvement-comparison",
        "patch_proposal": "ingest-patch-proposal",
    }
    steps: list[dict[str, Any]] = []
    by_role = {str(link["role"]): link for link in links}
    for role in REQUIRED_ROLES:
        link = by_role.get(role)
        steps.append(
            {
                "step_id": step_names[role],
                "role": role,
                "artifact_ref": link.get("ref") if link else None,
                "artifact_sha256": link.get("sha256") if link else None,
                "status": "ready" if link and link.get("accepted_for_mastra_receipt") else "blocked" if link else "missing",
                "runs_mastra": False,
                "metadata_only": True,
            }
        )
    return steps


def build_receipt_link(
    *,
    artifacts: list[tuple[dict[str, Any], str, str, str]],
    generated_at: str,
    output_dir: Path,
    root: Path,
) -> dict[str, Any]:
    links = [artifact_link(payload, ref, digest, schema) for payload, ref, digest, schema in artifacts]
    present_roles = sorted({str(link["role"]) for link in links})
    missing_roles = [role for role in REQUIRED_ROLES if role not in present_roles]
    blockers = [
        {"ref": link["ref"], "role": link["role"], "blockers": link["blockers"]}
        for link in links
        if link.get("blockers")
    ]
    degraded_reasons: list[str] = []
    if missing_roles:
        degraded_reasons.append(f"Missing required role(s): {', '.join(missing_roles)}")
    for link in links:
        if str(link.get("role")) == "improvement_comparison" and str(link.get("status")).lower() in {"insufficient", "regressed", "ambiguous"}:
            degraded_reasons.append(f"Improvement comparison status {link.get('status')} requires review before runtime linkage.")
    if blockers:
        status = "blocked"
    elif degraded_reasons:
        status = "degraded"
    else:
        status = "ready"
    link_id = f"mastra-evolution-link-{sha256_text(generated_at + json.dumps(links, sort_keys=True))[:16]}"
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "link_id": link_id,
        "generated_at": generated_at,
        "title": "Cognitive Loop Mastra Evolution Receipt Link Lite",
        "artifact_count": len(links),
        "artifact_links": links,
        "workflow_steps": build_workflow_steps(links),
        "missing_roles": missing_roles,
        "degraded_reasons": degraded_reasons,
        "blockers": blockers,
        "mastra_workflow": {
            "workflow_id": WORKFLOW_ID,
            "future_runtime": "mastra",
            "receipt_mode": "metadata_only_link",
            "daemon_started": False,
            "workflow_executed": False,
        },
        "receipt": {
            "schema_version": SCHEMA_VERSION,
            "ready_for_mastra": status == "ready",
            "linked_roles": present_roles,
            "human_mastery_gate_required": any("Human Mastery Gate" in " ".join(item.get("blockers", [])) for item in links),
            "manual_only_required": any(str(item.get("role")) == "patch_proposal" and item.get("blockers") for item in links),
        },
        "guardrails": {
            "read_only": True,
            "raw_unified_diff_generated": False,
            "apply_executed": False,
            "model_called": False,
            "daemon_started": False,
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
            "json_ref": relative_path(root, output_dir / "mastra-evolution-receipt-link.json"),
            "html_ref": relative_path(root, output_dir / "mastra-evolution-receipt-link.html"),
        },
        "commands": {
            "build": "python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json",
            "verify": "python3 scripts/verify_cognitive_loop_mastra_evolution_receipt.py --check",
        },
    }
    assert_public_payload(receipt, label="mastra evolution receipt link")
    return receipt


def render_html(receipt: Mapping[str, Any]) -> str:
    assert_public_payload(receipt, label="mastra evolution receipt html")

    def rows(items: Iterable[Mapping[str, Any]]) -> str:
        rendered: list[str] = []
        for item in items:
            rendered.append(
                "<tr>"
                + "".join(
                    f"<td>{escape(str(item.get(key, '')))}</td>"
                    for key in ("role", "schema_version", "status", "ref", "accepted_for_mastra_receipt")
                )
                + "</tr>"
            )
        return "\n".join(rendered)

    links = receipt.get("artifact_links")
    if not isinstance(links, list):
        links = []
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(str(receipt.get('title', 'Mastra Evolution Receipt Link Lite')))}</title>
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
    <h1>Cognitive Loop Mastra Evolution Receipt Link Lite</h1>
    <p>Status: <code>{escape(str(receipt.get('status')))}</code>. This artifact links metadata-only loop evidence to a future Mastra workflow receipt; it does not start Mastra or apply changes.</p>
    <h2>Artifact Links</h2>
    <table><thead><tr><th>Role</th><th>Schema</th><th>Status</th><th>Reference</th><th>Accepted</th></tr></thead><tbody>{rows([item for item in links if isinstance(item, Mapping)])}</tbody></table>
  </main>
</body>
</html>
"""


def cmd_build(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output_dir = resolve_under_root(root, args.output_dir)
    artifacts = [load_artifact(root, raw_path) for raw_path in args.artifact]
    receipt = build_receipt_link(
        artifacts=artifacts,
        generated_at=args.generated_at,
        output_dir=output_dir,
        root=root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.json:
        (output_dir / "mastra-evolution-receipt-link.json").write_text(dump_json(receipt), encoding="utf-8")
    if args.html:
        (output_dir / "mastra-evolution-receipt-link.html").write_text(render_html(receipt), encoding="utf-8")
    print(dump_json(receipt), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Build a read-only Mastra evolution receipt link.")
    build.add_argument("--artifact", action="append", default=[], help="Metadata-only artifact JSON path.")
    build.add_argument("--generated-at", default="2026-01-01T00:00:00Z")
    build.add_argument("--output-dir", default=".cognitive-loop/artifacts/mastra")
    build.add_argument("--html", action="store_true")
    build.add_argument("--json", action="store_true")
    build.set_defaults(func=cmd_build)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except MastraEvolutionReceiptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
