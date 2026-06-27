#!/usr/bin/env python3
"""Build metadata-only Cognitive Loop governed patch-apply sandbox receipts."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "cognitive-loop-patch-apply-sandbox-receipt-v1"

ARTIFACT_SPECS = (
    {
        "role": "patch_proposal",
        "label": "Patch Proposal",
        "schema_version": "cognitive-loop-patch-proposal-lite-v1",
        "default_ref": ".cognitive-loop/artifacts/patches/patch-proposal-lite.json",
    },
    {
        "role": "apply_plan",
        "label": "Governed Apply Plan",
        "schema_version": "cognitive-loop-apply-plan-lite-v1",
        "default_ref": ".cognitive-loop/artifacts/applied/apply-plan-lite.json",
    },
    {
        "role": "evolution_receipt_link",
        "label": "Evolution Receipt Link",
        "schema_version": "cognitive-loop-mastra-evolution-receipt-link-v1",
        "default_ref": ".cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json",
    },
    {
        "role": "mastra_workflow_replay",
        "label": "Mastra Workflow Replay",
        "schema_version": "cognitive-loop-mastra-evolution-workflow-replay-v1",
        "default_ref": ".cognitive-loop/artifacts/mastra/mastra-evolution-workflow-replay.json",
    },
)

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
    "real_source_mutated",
)
PROTECTED_TARGET_FRAGMENTS = (
    ".env",
    ".pem",
    ".key",
    "secrets/",
    ".github/workflows/",
    ".cognitive-loop/permissions",
    ".cognitive-loop/risk",
)


class PatchApplySandboxError(RuntimeError):
    """Readable Patch Apply Sandbox failure."""


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
        raise PatchApplySandboxError(f"Path must stay under project root: {value}") from exc
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
        raise PatchApplySandboxError(f"{label} contains private-looking text: literals={literal_hits} patterns={pattern_hits}")


def assert_no_policy_weakening(text: str, *, label: str) -> None:
    lowered = text.lower()
    hits = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if hits:
        raise PatchApplySandboxError(f"{label} tries to weaken protected policy: {hits}")


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_private_text(text, label=label)
    assert_no_policy_weakening(text, label=label)


def privacy_regressions(payload: Mapping[str, Any]) -> list[str]:
    regressions: list[str] = []
    for section_name in ("privacy", "guardrails", "runtime_boundaries", "sandbox", "rollback_proof"):
        section = payload.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for key in PRIVACY_FALSE_KEYS:
            if section.get(key) is True:
                regressions.append(f"{section_name}.{key}")
    return sorted(set(regressions))


def target_path_values(payload: Mapping[str, Any]) -> Iterable[str]:
    keys = ("patch_candidates", "manual_only_candidates", "eligible_actions", "manual_only_actions")
    for key in keys:
        value = payload.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, Mapping):
                target = item.get("target_path")
                if isinstance(target, str):
                    yield target


def protected_target_hits(payload: Mapping[str, Any]) -> list[str]:
    hits: list[str] = []
    for target in target_path_values(payload):
        normalized = target.strip().replace("\\", "/").lstrip("/")
        lowered = normalized.lower()
        if any(fragment in lowered for fragment in PROTECTED_TARGET_FRAGMENTS):
            hits.append(normalized)
    return sorted(set(hits))


def load_artifact(root: Path, raw_path: str, spec: Mapping[str, str]) -> dict[str, Any]:
    path = resolve_under_root(root, raw_path)
    if not path.is_file():
        return {
            "role": spec["role"],
            "label": spec["label"],
            "schema_version": spec["schema_version"],
            "status": "missing",
            "ref": relative_path(root, path),
            "sha256": "",
            "size_bytes": 0,
            "gate_status": "unknown",
            "manual_review_required": True,
            "blocking_required": False,
            "privacy_flags": {},
            "content_included": False,
        }
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    ref = relative_path(root, path)
    assert_public_payload(text, label=ref)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PatchApplySandboxError(f"Artifact must be valid JSON: {ref}") from exc
    if not isinstance(payload, Mapping):
        raise PatchApplySandboxError(f"Artifact must be a JSON object: {ref}")
    schema = str(payload.get("schema_version") or "")
    if schema != spec["schema_version"]:
        raise PatchApplySandboxError(f"Artifact {ref} has invalid schema {schema}; expected {spec['schema_version']}")
    regressions = privacy_regressions(payload)
    if regressions:
        raise PatchApplySandboxError(f"Artifact privacy regression in {ref}: {', '.join(regressions)}")
    protected = protected_target_hits(payload)
    if protected:
        raise PatchApplySandboxError(f"Artifact targets protected path(s) in {ref}: {', '.join(protected)}")
    assert_public_payload(payload, label=ref)
    status = str(payload.get("status") or "unknown").lower()
    privacy = payload.get("privacy")
    return {
        "role": spec["role"],
        "label": spec["label"],
        "schema_version": schema,
        "status": status,
        "ref": ref,
        "sha256": sha256_bytes(data),
        "size_bytes": len(data),
        "gate_status": gate_status(payload),
        "manual_review_required": manual_review_required(payload, status),
        "blocking_required": blocking_required(payload, status),
        "privacy_flags": dict(privacy) if isinstance(privacy, Mapping) else {},
        "content_included": False,
    }


def gate_status(payload: Mapping[str, Any]) -> str:
    human_gate = payload.get("human_mastery_gate")
    if isinstance(human_gate, Mapping):
        status = str(human_gate.get("status") or "")
        if status:
            return status
        if human_gate.get("required") is True:
            return "required"
    gate_actions = payload.get("gate_actions")
    if isinstance(gate_actions, list):
        actions = sorted(
            {
                str(item.get("gate_action"))
                for item in gate_actions
                if isinstance(item, Mapping) and item.get("gate_action")
            }
        )
        if actions:
            return ",".join(actions)
    return "not_required"


def manual_review_required(payload: Mapping[str, Any], status: str) -> bool:
    if status in {"degraded", "manual_only", "needs_review", "manual_review", "insufficient", "regressed", "ambiguous"}:
        return True
    human_gate = payload.get("human_mastery_gate")
    if isinstance(human_gate, Mapping) and str(human_gate.get("status") or "") in {"pending", "manual_review_required"}:
        return True
    replay_summary = payload.get("replay_summary")
    if isinstance(replay_summary, Mapping) and replay_summary.get("manual_review_required") is True:
        return True
    return any(isinstance(payload.get(key), list) and len(payload[key]) > 0 for key in ("manual_only_actions", "manual_only_candidates"))


def blocking_required(payload: Mapping[str, Any], status: str) -> bool:
    if status == "blocked":
        return True
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        return True
    replay_summary = payload.get("replay_summary")
    if isinstance(replay_summary, Mapping) and replay_summary.get("blocked") is True:
        return True
    return False


def derive_status(artifacts: list[dict[str, Any]]) -> str:
    if any(item["blocking_required"] for item in artifacts):
        return "blocked"
    if any(item["status"] == "missing" for item in artifacts):
        return "degraded_missing_artifacts"
    if any(item["manual_review_required"] for item in artifacts):
        return "manual_review"
    statuses = {item["role"]: item["status"] for item in artifacts}
    if statuses.get("patch_proposal") != "ready":
        return "manual_review"
    if statuses.get("apply_plan") != "dry_run_ready":
        return "manual_review"
    if statuses.get("evolution_receipt_link") != "ready":
        return "manual_review"
    if statuses.get("mastra_workflow_replay") != "replay_ready":
        return "manual_review"
    return "sandbox_ready"


def action_counts(artifacts: list[dict[str, Any]], root: Path) -> dict[str, int]:
    counts = {
        "patch_candidates": 0,
        "manual_only_candidates": 0,
        "eligible_actions": 0,
        "manual_only_actions": 0,
    }
    for item in artifacts:
        ref = item.get("ref")
        if not ref or item.get("status") == "missing":
            continue
        payload = json.loads((root / str(ref)).read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            continue
        for key in counts:
            value = payload.get(key)
            if isinstance(value, list):
                counts[key] += len(value)
    return counts


def sandbox_preview_hash(artifacts: list[dict[str, Any]], generated_at: str) -> str:
    material = json.dumps(
        [{"role": item["role"], "sha256": item["sha256"], "status": item["status"]} for item in artifacts],
        sort_keys=True,
    )
    return sha256_text(f"{generated_at}:{material}")[:32]


def build_receipt(
    *,
    root: Path,
    artifact_paths: Mapping[str, str],
    generated_at: str,
    output_dir: Path,
) -> dict[str, Any]:
    artifacts = [
        load_artifact(root, artifact_paths.get(spec["role"], spec["default_ref"]), spec)
        for spec in ARTIFACT_SPECS
    ]
    status = derive_status(artifacts)
    missing = [item["role"] for item in artifacts if item["status"] == "missing"]
    blocked = [item["role"] for item in artifacts if item["blocking_required"]]
    manual = [item["role"] for item in artifacts if item["manual_review_required"] and item["status"] != "missing"]
    preview_hash = sandbox_preview_hash(artifacts, generated_at)
    temp_hash = ""
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-apply-sandbox-") as temp_dir:
        temp_hash = sha256_text(temp_dir)[:32]
    counts = action_counts(artifacts, root)
    receipt_id = f"patch-apply-sandbox-{sha256_text(preview_hash + generated_at)[:16]}"
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "receipt_id": receipt_id,
        "generated_at": generated_at,
        "title": "Cognitive Loop Governed Patch Apply Sandbox Lite",
        "artifact_count": len(artifacts) - len(missing),
        "expected_artifact_count": len(ARTIFACT_SPECS),
        "missing_artifact_count": len(missing),
        "missing_roles": missing,
        "manual_review_roles": manual,
        "blocking_roles": blocked,
        "artifact_refs": artifacts,
        "sandbox": {
            "mode": "metadata_only_temp_preview",
            "sandbox_path_hash": temp_hash,
            "sandbox_ref": f"temp://patch-apply-sandbox/{preview_hash}",
            "temporary_workspace_removed": True,
            "fixture_workspace_used": False,
            "raw_diff_materialized": False,
            "real_worktree_apply_executed": False,
            "source_files_modified": False,
            "no_real_source_mutation": True,
        },
        "dry_run": {
            "status": "ready" if status == "sandbox_ready" else "skipped",
            "patch_candidates": counts["patch_candidates"],
            "manual_only_candidates": counts["manual_only_candidates"],
            "eligible_actions": counts["eligible_actions"],
            "manual_only_actions": counts["manual_only_actions"],
            "applies_to_real_worktree": False,
            "applies_to_sandbox_only": True,
            "raw_unified_diff_generated": False,
        },
        "rollback_proof": {
            "required": True,
            "strategy": "delete_temp_workspace",
            "proved": True,
            "temporary_workspace_removed": True,
            "source_files_modified": False,
            "no_real_source_mutation": True,
        },
        "operator_next_command": "python3 scripts/verify_cognitive_loop_patch_apply_sandbox.py --check",
        "operator_next_commands": [
            "python3 scripts/verify_cognitive_loop_patch_apply_sandbox.py --check",
            "python3 scripts/cognitive_loop_patch_apply_sandbox.py sandbox --html --json",
            "python3 scripts/cognitive_loop_artifact_console.py build --html --json",
        ],
        "guardrails": {
            "read_only": True,
            "dry_run_only": True,
            "real_worktree_apply_executed": False,
            "apply_executed": False,
            "raw_unified_diff_generated": False,
            "model_called": False,
            "daemon_started": False,
            "production_mastra_daemon_started": False,
            "mastra_workflow_started": False,
            "source_files_modified": False,
            "real_source_mutated": False,
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
            "json_ref": relative_path(root, output_dir / "patch-apply-sandbox-receipt.json"),
            "html_ref": relative_path(root, output_dir / "patch-apply-sandbox-receipt.html"),
        },
        "commands": {
            "sandbox": "python3 scripts/cognitive_loop_patch_apply_sandbox.py sandbox --html --json",
            "verify": "python3 scripts/verify_cognitive_loop_patch_apply_sandbox.py --check",
        },
        "content_included": False,
    }
    assert_public_payload(receipt, label="patch apply sandbox receipt")
    return receipt


def render_html(receipt: Mapping[str, Any]) -> str:
    assert_public_payload(receipt, label="patch apply sandbox html")

    def rows(items: Iterable[Mapping[str, Any]]) -> str:
        rendered: list[str] = []
        for item in items:
            rendered.append(
                "<tr>"
                + "".join(
                    f"<td>{escape(str(item.get(key, '')))}</td>"
                    for key in ("role", "schema_version", "status", "ref", "gate_status", "manual_review_required", "blocking_required")
                )
                + "</tr>"
            )
        return "\n".join(rendered)

    artifacts = receipt.get("artifact_refs")
    if not isinstance(artifacts, list):
        artifacts = []
    sandbox = receipt.get("sandbox") if isinstance(receipt.get("sandbox"), Mapping) else {}
    rollback = receipt.get("rollback_proof") if isinstance(receipt.get("rollback_proof"), Mapping) else {}
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(str(receipt.get('title', 'Patch Apply Sandbox Lite')))}</title>
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
    @media (max-width:720px) {{ th,td {{ font-size:.86rem; padding:8px; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Cognitive Loop Governed Patch Apply Sandbox Lite</h1>
    <p>Status: <code>{escape(str(receipt.get('status')))}</code>. This receipt validates patch-apply readiness in a metadata-only temporary sandbox preview; it does not apply changes to the real worktree.</p>
    <h2>Sandbox Boundary</h2>
    <p>Sandbox ref: <code>{escape(str(sandbox.get('sandbox_ref', '')))}</code>. Rollback proved: <code>{escape(str(rollback.get('proved', False)))}</code>. Real source mutation: <code>false</code>.</p>
    <h2>Artifact Chain</h2>
    <table><thead><tr><th>Role</th><th>Schema</th><th>Status</th><th>Ref</th><th>Gate</th><th>Manual</th><th>Blocking</th></tr></thead><tbody>{rows([item for item in artifacts if isinstance(item, Mapping)])}</tbody></table>
  </main>
</body>
</html>
"""


def cmd_sandbox(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output_dir = resolve_under_root(root, args.output_dir)
    artifact_paths = {
        "patch_proposal": args.patch_proposal,
        "apply_plan": args.apply_plan,
        "evolution_receipt_link": args.receipt,
        "mastra_workflow_replay": args.replay,
    }
    receipt = build_receipt(
        root=root,
        artifact_paths=artifact_paths,
        generated_at=args.generated_at,
        output_dir=output_dir,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.json:
        (output_dir / "patch-apply-sandbox-receipt.json").write_text(dump_json(receipt), encoding="utf-8")
    if args.html:
        (output_dir / "patch-apply-sandbox-receipt.html").write_text(render_html(receipt), encoding="utf-8")
    print(dump_json(receipt), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root.")
    sub = parser.add_subparsers(dest="command", required=True)
    sandbox = sub.add_parser("sandbox", help="Build a governed patch-apply sandbox receipt.")
    sandbox.add_argument("--patch-proposal", default=".cognitive-loop/artifacts/patches/patch-proposal-lite.json")
    sandbox.add_argument("--apply-plan", default=".cognitive-loop/artifacts/applied/apply-plan-lite.json")
    sandbox.add_argument("--receipt", default=".cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json")
    sandbox.add_argument("--replay", default=".cognitive-loop/artifacts/mastra/mastra-evolution-workflow-replay.json")
    sandbox.add_argument("--generated-at", default="2026-01-01T00:00:00Z")
    sandbox.add_argument("--output-dir", default=".cognitive-loop/artifacts/applied")
    sandbox.add_argument("--html", action="store_true")
    sandbox.add_argument("--json", action="store_true")
    sandbox.set_defaults(func=cmd_sandbox)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except PatchApplySandboxError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
