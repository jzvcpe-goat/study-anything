#!/usr/bin/env python3
"""Compare metadata-only Cognitive Loop improvement evidence across loop runs."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "cognitive-loop-improvement-comparison-lite-v1"

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
SAFE_FALSE_PRIVACY_KEYS = {
    "source_text_included",
    "raw_diff_included",
    "learner_answers_included",
    "agent_endpoint_included",
    "agent_metadata_included",
    "prompt_text_included",
    "real_model_keys_stored",
    "model_called",
    "daemon_started",
    "policy_weakened",
    "source_files_modified",
    "secrets_returned",
    "agent_endpoints_returned",
    "raw_source_text_returned",
    "grading_feedback_returned",
    "generated_insights_returned",
    "raw_agent_metadata_returned",
}
PASS_STATUSES = {"ok", "pass", "passed", "ready", "succeeded", "dry_run_ready", "applied"}
FAIL_STATUSES = {"fail", "failed", "error", "blocked", "needs_fix", "needs-fix"}
DEGRADED_STATUSES = {"degraded", "needs_attention", "needs_review", "manual_only"}


class ImprovementComparisonError(RuntimeError):
    """Readable improvement comparison failure."""


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
        raise ImprovementComparisonError(f"Path must stay under project root: {value}") from exc
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
        raise ImprovementComparisonError(
            f"{label} contains private-looking text: literals={literal_hits} patterns={pattern_hits}"
        )


def assert_no_policy_weakening(text: str, *, label: str) -> None:
    lowered = text.lower()
    hits = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if hits:
        raise ImprovementComparisonError(f"{label} tries to weaken protected policy: {hits}")


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_private_text(text, label=label)
    assert_no_policy_weakening(text, label=label)


def load_artifact(root: Path, raw_path: str) -> tuple[dict[str, Any], str, str]:
    path = resolve_under_root(root, raw_path)
    if not path.is_file():
        raise ImprovementComparisonError(f"Missing comparison artifact: {relative_path(root, path)}")
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    assert_no_private_text(text, label=relative_path(root, path))
    assert_no_policy_weakening(text, label=relative_path(root, path))
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImprovementComparisonError(f"Comparison artifact must be valid JSON: {relative_path(root, path)}") from exc
    if not isinstance(payload, dict):
        raise ImprovementComparisonError("Comparison artifact must be a JSON object.")
    schema = payload.get("schema_version")
    if not isinstance(schema, str) or not schema:
        raise ImprovementComparisonError("Comparison artifact must include schema_version.")
    assert_public_payload(payload, label=relative_path(root, path))
    return payload, relative_path(root, path), sha256_bytes(data)


def count_list(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, list):
        return len(value)
    return 0


def numeric_from_path(payload: Mapping[str, Any], *path: str) -> int:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return 0
        current = current.get(key)
    if isinstance(current, bool):
        return int(current)
    if isinstance(current, int):
        return current
    if isinstance(current, float):
        return int(current)
    return 0


def privacy_flag_count(payload: Mapping[str, Any]) -> int:
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping):
        return 0
    count = 0
    for key, value in privacy.items():
        if key in SAFE_FALSE_PRIVACY_KEYS and value is not False:
            count += 1
        if key.endswith("_included") and value is not False:
            count += 1
        if key.endswith("_stored") and value is not False:
            count += 1
        if key.endswith("_returned") and value is not False:
            count += 1
    return count


def status_family(status: str) -> str:
    lowered = status.lower()
    if lowered in PASS_STATUSES:
        return "pass"
    if lowered in FAIL_STATUSES:
        return "fail"
    if lowered in DEGRADED_STATUSES:
        return "degraded"
    return "unknown"


def artifact_metrics(payload: Mapping[str, Any], ref: str, sha256: str) -> dict[str, Any]:
    status = str(payload.get("status") or "unknown")
    cluster_count = count_list(payload, "failure_clusters") + numeric_from_path(payload, "success_modes", "cluster_count")
    manual_only_count = count_list(payload, "manual_only_actions") + numeric_from_path(payload, "success_modes", "manual_only_count")
    eligible_action_count = count_list(payload, "eligible_actions") + numeric_from_path(
        payload, "success_modes", "eligible_action_count"
    )
    gate_count = int(bool(payload.get("human_mastery_gate", {}).get("required"))) if isinstance(payload.get("human_mastery_gate"), Mapping) else 0
    gate_count += int(bool(numeric_from_path(payload, "success_modes", "high_risk_gate_required")))
    degraded_count = int(status.lower() in DEGRADED_STATUSES)
    degraded_count += int(bool(numeric_from_path(payload, "degraded_modes", "empty_evidence_degraded")))
    degraded_count += int(bool(numeric_from_path(payload, "degraded_modes", "missing_evidence_degraded")))
    release_gate_pass_count = int(status_family(status) == "pass")
    release_gate_fail_count = int(status_family(status) == "fail")
    receipt_ready_count = int(status.lower() in {"dry_run_ready", "applied"})
    receipt_ready_count += int(bool(numeric_from_path(payload, "success_modes", "receipt_written")))
    privacy_count = privacy_flag_count(payload)
    bad_score = cluster_count + manual_only_count + gate_count + degraded_count + privacy_count + release_gate_fail_count
    good_score = eligible_action_count + release_gate_pass_count + receipt_ready_count
    return {
        "ref": ref,
        "schema_version": str(payload.get("schema_version")),
        "status": status,
        "status_family": status_family(status),
        "sha256": sha256,
        "cluster_count": cluster_count,
        "manual_only_count": manual_only_count,
        "eligible_action_count": eligible_action_count,
        "gate_count": gate_count,
        "degraded_evidence_count": degraded_count,
        "privacy_flag_count": privacy_count,
        "release_gate_pass_count": release_gate_pass_count,
        "release_gate_fail_count": release_gate_fail_count,
        "receipt_ready_count": receipt_ready_count,
        "bad_score": bad_score,
        "good_score": good_score,
    }


def delta_metrics(baseline: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, int]:
    keys = [
        "cluster_count",
        "manual_only_count",
        "eligible_action_count",
        "gate_count",
        "degraded_evidence_count",
        "privacy_flag_count",
        "release_gate_pass_count",
        "release_gate_fail_count",
        "receipt_ready_count",
        "bad_score",
        "good_score",
    ]
    return {key: int(current.get(key, 0)) - int(baseline.get(key, 0)) for key in keys}


def classify_delta(delta: Mapping[str, int]) -> tuple[str, str]:
    bad_improved = delta["bad_score"] < 0
    bad_regressed = delta["bad_score"] > 0
    good_improved = delta["good_score"] > 0
    good_regressed = delta["good_score"] < 0
    privacy_regressed = delta["privacy_flag_count"] > 0
    release_regressed = delta["release_gate_fail_count"] > 0
    if privacy_regressed or release_regressed:
        return ("regressed", "Privacy or release-gate evidence worsened; route through manual review.")
    if bad_regressed and good_improved:
        return ("ambiguous", "Mixed signal: apply-readiness improved while risk or degraded evidence also increased.")
    if bad_improved or (good_improved and not bad_regressed):
        return ("improved", "Current loop evidence is measurably better than the baseline.")
    if bad_regressed or good_regressed:
        return ("regressed", "Current loop evidence is worse than the baseline.")
    return ("unchanged", "Comparable metrics did not move.")


def build_comparison(
    *,
    artifacts: list[tuple[dict[str, Any], str, str]],
    generated_at: str,
    output_dir: Path,
    root: Path,
) -> dict[str, Any]:
    metrics = [artifact_metrics(payload, ref, digest) for payload, ref, digest in artifacts]
    if len(metrics) < 2:
        status = "insufficient"
        delta: dict[str, int] = {}
        recommendation = "Add at least two metadata-only loop artifacts before measuring improvement."
    else:
        delta = delta_metrics(metrics[0], metrics[-1])
        status, recommendation = classify_delta(delta)
    comparison_id = f"comparison-{sha256_text(generated_at + json.dumps(metrics, sort_keys=True))[:16]}"
    comparison = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "comparison_id": comparison_id,
        "generated_at": generated_at,
        "title": "Cognitive Loop Measured Improvement Comparator Lite",
        "artifact_count": len(metrics),
        "baseline_ref": metrics[0]["ref"] if metrics else "",
        "current_ref": metrics[-1]["ref"] if metrics else "",
        "artifact_metrics": metrics,
        "delta": delta,
        "recommendation": recommendation,
        "guardrails": {
            "read_only": True,
            "model_called": False,
            "daemon_started": False,
            "source_files_modified": False,
            "apply_executed": False,
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
            "json_ref": relative_path(root, output_dir / "improvement-comparison-lite.json"),
            "html_ref": relative_path(root, output_dir / "improvement-comparison-lite.html"),
        },
        "commands": {
            "compare": "python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json",
            "verify": "python3 scripts/verify_cognitive_loop_improvement_comparator.py --check",
        },
    }
    assert_public_payload(comparison, label="improvement comparison")
    return comparison


def render_html(comparison: Mapping[str, Any]) -> str:
    assert_public_payload(comparison, label="improvement comparison html")

    def rows(items: Iterable[Mapping[str, Any]]) -> str:
        rendered: list[str] = []
        keys = (
            "ref",
            "status",
            "cluster_count",
            "manual_only_count",
            "eligible_action_count",
            "gate_count",
            "degraded_evidence_count",
            "privacy_flag_count",
            "bad_score",
            "good_score",
        )
        for item in items:
            rendered.append("<tr>" + "".join(f"<td>{escape(str(item.get(key, '')))}</td>" for key in keys) + "</tr>")
        return "\n".join(rendered)

    metrics = comparison.get("artifact_metrics")
    if not isinstance(metrics, list):
        metrics = []
    metric_rows = rows([item for item in metrics if isinstance(item, Mapping)])
    delta = comparison.get("delta")
    if not isinstance(delta, Mapping):
        delta = {}
    delta_rows = "\n".join(
        f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>" for key, value in sorted(delta.items())
    )
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(str(comparison.get('title', 'Improvement Comparator Lite')))}</title>
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
    <h1>Cognitive Loop Measured Improvement Comparator Lite</h1>
    <p>Status: <code>{escape(str(comparison.get('status')))}</code>. {escape(str(comparison.get('recommendation')))}</p>
    <h2>Artifact Metrics</h2>
    <table><thead><tr><th>Ref</th><th>Status</th><th>Clusters</th><th>Manual</th><th>Eligible</th><th>Gates</th><th>Degraded</th><th>Privacy</th><th>Bad</th><th>Good</th></tr></thead><tbody>{metric_rows}</tbody></table>
    <h2>Delta</h2>
    <table><thead><tr><th>Metric</th><th>Current minus baseline</th></tr></thead><tbody>{delta_rows}</tbody></table>
  </main>
</body>
</html>
"""


def cmd_compare(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output_dir = resolve_under_root(root, args.output_dir)
    artifacts = [load_artifact(root, raw_path) for raw_path in args.artifact]
    comparison = build_comparison(
        artifacts=artifacts,
        generated_at=args.generated_at,
        output_dir=output_dir,
        root=root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.json:
        (output_dir / "improvement-comparison-lite.json").write_text(dump_json(comparison), encoding="utf-8")
    if args.html:
        (output_dir / "improvement-comparison-lite.html").write_text(render_html(comparison), encoding="utf-8")
    print(dump_json(comparison), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root.")
    sub = parser.add_subparsers(dest="command", required=True)
    compare = sub.add_parser("compare", help="Compare metadata-only loop evidence artifacts.")
    compare.add_argument("--artifact", action="append", default=[], help="Artifact JSON path under the project root.")
    compare.add_argument("--generated-at", default="2026-01-01T00:00:00Z")
    compare.add_argument("--output-dir", default=".cognitive-loop/artifacts/comparison")
    compare.add_argument("--html", action="store_true")
    compare.add_argument("--json", action="store_true")
    compare.set_defaults(func=cmd_compare)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except ImprovementComparisonError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
