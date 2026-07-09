#!/usr/bin/env python3
"""Build read-only Cognitive Loop Evolution Report Lite artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from html import escape
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MODULE_PATH = (
    ROOT / "apps" / "api" / "study_anything" / "core" / "cognitive_loop_contracts.py"
)

SCHEMA_VERSION = "cognitive-loop-evolution-report-lite-v1"

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


class EvolutionError(RuntimeError):
    """Readable Evolution Report Lite failure."""


@dataclass(frozen=True)
class EvidenceSummary:
    ref: str
    kind: str
    schema_version: str
    status: str
    sha256: str
    size_bytes: int
    signals: tuple[str, ...]
    content_included: bool = False
    missing: bool = False


def _load_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_cognitive_loop_contracts", CONTRACT_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise EvolutionError(f"Cannot load Cognitive Loop contracts: {CONTRACT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contracts = _load_contract_module()


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
        raise EvolutionError(f"Path must stay under project root: {value}") from exc
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
        raise EvolutionError(f"{label} contains private-looking text: literals={literal_hits} patterns={pattern_hits}")


def assert_no_policy_weakening(text: str, *, label: str) -> None:
    lowered = text.lower()
    hits = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if hits:
        raise EvolutionError(f"{label} tries to weaken protected policy: {hits}")


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_private_text(text, label=label)
    assert_no_policy_weakening(text, label=label)


def safe_status(value: Any) -> str:
    if isinstance(value, str) and value:
        return value[:80]
    return "unknown"


def summarize_json_evidence(root: Path, raw_path: str) -> EvidenceSummary:
    path = resolve_under_root(root, raw_path)
    relative = relative_path(root, path)
    if not path.is_file():
        return EvidenceSummary(
            ref=relative,
            kind="missing",
            schema_version="missing",
            status="missing",
            sha256="",
            size_bytes=0,
            signals=("missing evidence",),
            missing=True,
        )
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=relative)
    assert_no_policy_weakening(text, label=relative)
    if path.suffix != ".json":
        return EvidenceSummary(
            ref=relative,
            kind=path.suffix.lstrip(".") or "file",
            schema_version="not_applicable",
            status="present",
            sha256=sha256_bytes(data),
            size_bytes=len(data),
            signals=("non-json evidence",),
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EvolutionError(f"Evidence must be valid JSON: {relative}") from exc
    if not isinstance(payload, Mapping):
        raise EvolutionError(f"Evidence must be a JSON object: {relative}")
    signals = collect_signals(payload)
    return EvidenceSummary(
        ref=relative,
        kind="json",
        schema_version=safe_status(payload.get("schema_version")),
        status=safe_status(payload.get("status")),
        sha256=sha256_bytes(data),
        size_bytes=len(data),
        signals=tuple(signals),
    )


def collect_signals(payload: Mapping[str, Any]) -> list[str]:
    signals: list[str] = []
    status = payload.get("status")
    if isinstance(status, str) and status not in {"ok", "pass", "passed", "ready", "succeeded"}:
        signals.append(f"status:{status}")
    failure_modes = payload.get("failure_modes")
    if isinstance(failure_modes, Mapping):
        for key, value in failure_modes.items():
            if value:
                signals.append(f"failure_mode:{key}")
    success_modes = payload.get("success_modes")
    if isinstance(success_modes, Mapping):
        for key, value in success_modes.items():
            if key.endswith("_count") and isinstance(value, int) and value == 0:
                signals.append(f"missing_count:{key}")
    privacy = payload.get("privacy")
    if isinstance(privacy, Mapping):
        for key, value in privacy.items():
            if key.endswith("_included") and value is not False:
                signals.append(f"privacy_flag:{key}")
            if key.endswith("_stored") and value is not False:
                signals.append(f"storage_flag:{key}")
    if not signals:
        signals.append("healthy evidence")
    return signals[:12]


def classify_signal(signal: str) -> tuple[str, str, str]:
    lowered = signal.lower()
    if "privacy" in lowered or "secret" in lowered or "key" in lowered:
        return ("policy_or_privacy", "high", "Strengthen privacy and redaction checks before the next loop.")
    if "missing" in lowered or "not_found" in lowered:
        return ("missing_evidence", "medium", "Add the missing evidence producer or document the degraded path.")
    if "schema" in lowered or "invalid" in lowered:
        return ("schema_drift", "medium", "Regenerate schema evidence and add a regression check.")
    if "timeout" in lowered or "unavailable" in lowered or "unreachable" in lowered:
        return ("runtime_or_tooling", "medium", "Capture a bounded retry or fallback path with diagnostics.")
    if "failed" in lowered or "failure" in lowered or "blocked" in lowered:
        return ("verification_failure", "high", "Route the failure through a Human Mastery Gate before applying changes.")
    return ("healthy_or_low_signal", "low", "Keep the evidence path in the next release gate.")


def build_clusters(evidence: list[EvidenceSummary], failure_summaries: list[str]) -> list[dict[str, Any]]:
    categorized: dict[str, list[tuple[str, str]]] = {}
    severities: dict[str, str] = {}
    recommendations: dict[str, str] = {}
    for item in evidence:
        for signal in item.signals:
            category, severity, recommendation = classify_signal(signal)
            categorized.setdefault(category, []).append((item.ref, signal))
            severities[category] = max_risk(severities.get(category, "low"), severity)
            recommendations[category] = recommendation
    for summary in failure_summaries:
        category, severity, recommendation = classify_signal(summary)
        categorized.setdefault(category, []).append(("operator-summary", summary))
        severities[category] = max_risk(severities.get(category, "low"), severity)
        recommendations[category] = recommendation
    if not categorized:
        categorized["empty_evidence"] = [("operator-summary", "no evidence or failure summary supplied")]
        severities["empty_evidence"] = "medium"
        recommendations["empty_evidence"] = "Add at least one metadata-only evidence artifact before trusting improvement proposals."
    clusters = []
    for category, refs in sorted(categorized.items()):
        clusters.append(
            {
                "cluster_id": f"cluster-{category}",
                "category": category,
                "severity": severities[category],
                "signals": [{"evidence_ref": ref, "signal": signal} for ref, signal in refs[:8]],
                "recommendation": recommendations[category],
            }
        )
    return clusters


def max_risk(left: str, right: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return left if order[left] >= order[right] else right


def target_for_category(category: str) -> str:
    if category == "schema_drift":
        return "eval"
    if category == "missing_evidence":
        return "doc"
    if category == "runtime_or_tooling":
        return "task"
    if category == "policy_or_privacy":
        return "policy"
    if category == "verification_failure":
        return "eval"
    return "task"


def build_proposed_improvements(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    improvements: list[dict[str, Any]] = []
    for cluster in clusters:
        risk = str(cluster["severity"])
        target = target_for_category(str(cluster["category"]))
        improvements.append(
            {
                "target": target,
                "change": str(cluster["recommendation"]),
                "risk": risk,
                "auto_apply": False,
                "requires_human_mastery_gate": risk == "high",
                "rollback": "revert_generated_artifacts_or_drop_proposed_change",
            }
        )
    return improvements


def build_root_causes(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root_causes: list[dict[str, Any]] = []
    mapping = {
        "schema_drift": "missing_tests",
        "missing_evidence": "task_decomposition",
        "runtime_or_tooling": "tool_failure",
        "policy_or_privacy": "risk_policy",
        "verification_failure": "missing_tests",
        "healthy_or_low_signal": "bad_context",
        "empty_evidence": "bad_context",
    }
    for cluster in clusters:
        evidence = [
            str(item.get("evidence_ref"))
            for item in cluster.get("signals", [])
            if isinstance(item, Mapping) and item.get("evidence_ref")
        ]
        root_causes.append(
            {
                "category": mapping.get(str(cluster["category"]), "bad_context"),
                "hypothesis": f"{cluster['category']} is limiting the next Cognitive Loop iteration.",
                "evidence": sorted(set(evidence))[:6],
            }
        )
    return root_causes


def build_report(
    *,
    root: Path,
    evidence: list[EvidenceSummary],
    failure_summaries: list[str],
    generated_at: str,
    output_dir: Path,
) -> dict[str, Any]:
    clusters = build_clusters(evidence, failure_summaries)
    root_causes = build_root_causes(clusters)
    improvements = build_proposed_improvements(clusters)
    highest_risk = "low"
    for item in improvements:
        highest_risk = max_risk(highest_risk, str(item["risk"]))
    needs_gate = highest_risk == "high"
    degraded = any(item.missing for item in evidence) or not evidence
    report_id = f"evo-lite-{sha256_text(generated_at + json.dumps([item.ref for item in evidence]))[:12]}"
    verification_refs = [
        "python3 scripts/verify_cognitive_loop_evolution_report.py --check",
        "python3 scripts/cognitive_loop_evolution.py build --html --json",
    ]
    evolution_report = contracts.validate_evolution_report(
        {
            "report_id": report_id,
            "project_id": "study-anything",
            "status": "needs_review" if needs_gate or degraded else "approved",
            "proposed_changes": [item["change"] for item in improvements],
            "decision_card_ids": ["human-gate-required"] if needs_gate else ["decision-card-not-required"],
            "verification_refs": verification_refs,
            "risk_summary": (
                f"Highest proposed risk is {highest_risk}; auto-apply is disabled and protected policy cannot be weakened."
            ),
            "created_at": generated_at,
        }
    ).public_dict()
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "degraded" if degraded else "ready",
        "generated_at": generated_at,
        "title": "Cognitive Loop Evolution Report Lite",
        "evidence_sources": [item.__dict__ for item in evidence],
        "failure_clusters": clusters,
        "root_cause_hypotheses": root_causes,
        "proposed_improvements": improvements,
        "human_mastery_gate": {
            "required": needs_gate,
            "status": "pending" if needs_gate else "not_required",
            "reason": "High-risk evolution proposals require human explanation and approval." if needs_gate else "",
        },
        "regression_plan": [
            "Run python3 scripts/verify_cognitive_loop_evolution_report.py --check.",
            "Run python3 scripts/verify_platform_ecosystem_packs.py.",
            "Run python3 scripts/verify_ecosystem_submission_pack.py.",
            "Run ./scripts/release_check.sh before merge.",
        ],
        "next_loop_success_metric": {
            "metric_id": "phase8a-evolution-loop-success",
            "target": "next_loop_has_fewer_degraded_evidence_items_or_clearer_gate_decisions",
            "baseline_degraded": degraded,
            "cluster_count": len(clusters),
        },
        "evolution_report": evolution_report,
        "policy_guardrails": {
            "auto_apply_default": False,
            "forbidden_auto_changes": [
                "risk thresholds",
                "audit policy",
                "privacy policy",
                "rollback policy",
                "test requirements",
                "permissions policy",
            ],
            "policy_weakened": False,
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
        },
        "outputs": {
            "json_ref": relative_path(root, output_dir / "evolution-report-lite.json"),
            "html_ref": relative_path(root, output_dir / "evolution-report-lite.html"),
        },
        "commands": {
            "build": "python3 scripts/cognitive_loop_evolution.py build --html --json",
            "verify": "python3 scripts/verify_cognitive_loop_evolution_report.py --check",
        },
    }
    assert_public_payload(report, label="evolution report")
    return report


def render_html(report: Mapping[str, Any]) -> str:
    assert_public_payload(report, label="evolution html")

    def rows(items: Iterable[Mapping[str, Any]], *keys: str) -> str:
        rendered: list[str] = []
        for item in items:
            rendered.append("<tr>" + "".join(f"<td>{escape(str(item.get(key, '')))}</td>" for key in keys) + "</tr>")
        return "\n".join(rendered)

    sources = report.get("evidence_sources")
    if not isinstance(sources, list):
        sources = []
    clusters = report.get("failure_clusters")
    if not isinstance(clusters, list):
        clusters = []
    improvements = report.get("proposed_improvements")
    if not isinstance(improvements, list):
        improvements = []
    source_rows = rows([item for item in sources if isinstance(item, Mapping)], "ref", "schema_version", "status")
    cluster_rows = rows([item for item in clusters if isinstance(item, Mapping)], "cluster_id", "category", "severity")
    improvement_rows = rows(
        [item for item in improvements if isinstance(item, Mapping)],
        "target",
        "risk",
        "auto_apply",
        "requires_human_mastery_gate",
        "change",
    )
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(str(report.get('title', 'Evolution Report Lite')))}</title>
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
    <h1>Cognitive Loop Evolution Report Lite</h1>
    <p>Status: <code>{escape(str(report.get('status')))}</code>. This report is read-only and proposes governed next-loop improvements.</p>
    <h2>Evidence Sources</h2>
    <table><thead><tr><th>Ref</th><th>Schema</th><th>Status</th></tr></thead><tbody>{source_rows}</tbody></table>
    <h2>Failure Clusters</h2>
    <table><thead><tr><th>ID</th><th>Category</th><th>Severity</th></tr></thead><tbody>{cluster_rows}</tbody></table>
    <h2>Proposed Improvements</h2>
    <table><thead><tr><th>Target</th><th>Risk</th><th>Auto Apply</th><th>Gate</th><th>Change</th></tr></thead><tbody>{improvement_rows}</tbody></table>
  </main>
</body>
</html>
"""


def cmd_build(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    for summary in args.failure_summary or []:
        assert_no_private_text(summary, label="failure summary")
        assert_no_policy_weakening(summary, label="failure summary")
    output_dir = resolve_under_root(root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = [summarize_json_evidence(root, path) for path in args.evidence or []]
    report = build_report(
        root=root,
        evidence=evidence,
        failure_summaries=list(args.failure_summary or []),
        generated_at=args.generated_at,
        output_dir=output_dir,
    )
    if args.json:
        json_path = output_dir / "evolution-report-lite.json"
        json_path.write_text(dump_json(report), encoding="utf-8")
    if args.html:
        html_path = output_dir / "evolution-report-lite.html"
        html_path.write_text(render_html(report), encoding="utf-8")
    print(dump_json(report), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Build an Evolution Report Lite artifact.")
    build.add_argument("--evidence", action="append", default=[], help="Metadata-only JSON evidence path.")
    build.add_argument("--failure-summary", action="append", default=[], help="Bounded failure summary.")
    build.add_argument("--generated-at", default="2026-01-01T00:00:00Z")
    build.add_argument("--output-dir", default=".cognitive-loop/artifacts/evolution")
    build.add_argument("--html", action="store_true")
    build.add_argument("--json", action="store_true")
    build.set_defaults(func=cmd_build)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except EvolutionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
