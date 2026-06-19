#!/usr/bin/env python3
"""Export a metadata-only professional Cognitive Loop evolution evidence pack."""

from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys
import zipfile
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "cognitive-loop-evolution-pack-manifest-v1"
ARCHIVE_ROOT = "cognitive-loop-professional-evolution-pack"

ARTIFACT_SPECS = (
    {
        "role": "artifact_console",
        "label": "Artifact Console",
        "schema_version": "cognitive-loop-artifact-console-v1",
        "default_ref": ".cognitive-loop/artifacts/console/manifest.json",
    },
    {
        "role": "evolution_report",
        "label": "Evolution Report",
        "schema_version": "cognitive-loop-evolution-report-lite-v1",
        "default_ref": ".cognitive-loop/artifacts/evolution/evolution-report-lite.json",
    },
    {
        "role": "apply_plan",
        "label": "Governed Apply Plan",
        "schema_version": "cognitive-loop-apply-plan-lite-v1",
        "default_ref": ".cognitive-loop/artifacts/applied/apply-plan-lite.json",
    },
    {
        "role": "improvement_comparison",
        "label": "Improvement Comparison",
        "schema_version": "cognitive-loop-improvement-comparison-lite-v1",
        "default_ref": ".cognitive-loop/artifacts/comparison/improvement-comparison-lite.json",
    },
    {
        "role": "patch_proposal",
        "label": "Patch Proposal",
        "schema_version": "cognitive-loop-patch-proposal-lite-v1",
        "default_ref": ".cognitive-loop/artifacts/patches/patch-proposal-lite.json",
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
    {
        "role": "patch_apply_sandbox",
        "label": "Patch Apply Sandbox",
        "schema_version": "cognitive-loop-patch-apply-sandbox-receipt-v1",
        "default_ref": ".cognitive-loop/artifacts/applied/patch-apply-sandbox-receipt.json",
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


class EvolutionPackExportError(RuntimeError):
    """Readable evolution-pack export failure."""


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
        raise EvolutionPackExportError(f"Path must stay under project root: {value}") from exc
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
        raise EvolutionPackExportError(f"{label} contains private-looking text: literals={literal_hits} patterns={pattern_hits}")


def assert_no_policy_weakening(text: str, *, label: str) -> None:
    lowered = text.lower()
    hits = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if hits:
        raise EvolutionPackExportError(f"{label} tries to weaken protected policy: {hits}")


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
    links = payload.get("artifact_links")
    if isinstance(links, list):
        for index, link in enumerate(links):
            if not isinstance(link, Mapping):
                continue
            for regression in link.get("privacy_regressions") or []:
                regressions.append(f"artifact_links[{index}].{regression}")
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
    receipt = payload.get("receipt")
    if isinstance(receipt, Mapping) and receipt.get("manual_only_required") is True:
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


def html_ref_from_payload(payload: Mapping[str, Any]) -> str:
    outputs = payload.get("outputs")
    if isinstance(outputs, Mapping):
        value = outputs.get("html_ref")
        if isinstance(value, str) and value:
            return value
    refs = payload.get("artifact_refs")
    if isinstance(refs, Mapping):
        for key in ("html", "html_ref"):
            value = refs.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def archive_path_for(relative: str) -> str:
    normalized = relative.replace("\\", "/").lstrip("/")
    return f"{ARCHIVE_ROOT}/artifacts/{normalized}"


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
            "html_ref": "",
            "gate_status": "unknown",
            "manual_review_required": True,
            "blocking_required": False,
            "privacy_flags": {},
            "pack_included": False,
            "content_included": False,
        }
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    ref = relative_path(root, path)
    assert_public_payload(text, label=ref)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EvolutionPackExportError(f"Artifact must be valid JSON: {ref}") from exc
    if not isinstance(payload, Mapping):
        raise EvolutionPackExportError(f"Artifact must be a JSON object: {ref}")
    schema = str(payload.get("schema_version") or "")
    if schema != spec["schema_version"]:
        raise EvolutionPackExportError(f"Artifact {ref} has invalid schema {schema}; expected {spec['schema_version']}")
    regressions = privacy_regressions(payload)
    if regressions:
        raise EvolutionPackExportError(f"Artifact privacy regression in {ref}: {', '.join(regressions)}")
    protected = protected_target_hits(payload)
    if protected:
        raise EvolutionPackExportError(f"Artifact targets protected path(s) in {ref}: {', '.join(protected)}")
    assert_public_payload(payload, label=ref)
    status = str(payload.get("status") or "unknown").lower()
    privacy = payload.get("privacy")
    html_ref = html_ref_from_payload(payload)
    return {
        "role": spec["role"],
        "label": spec["label"],
        "schema_version": schema,
        "status": status,
        "ref": ref,
        "sha256": sha256_bytes(data),
        "size_bytes": len(data),
        "html_ref": html_ref,
        "gate_status": gate_status(payload),
        "manual_review_required": manual_review_required(payload, status),
        "blocking_required": blocking_required(payload, status),
        "privacy_flags": dict(privacy) if isinstance(privacy, Mapping) else {},
        "pack_included": True,
        "content_included": False,
    }


def existing_pack_files(root: Path, artifacts: list[dict[str, Any]], index_html: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = [
        {
            "role": "evolution_pack_index",
            "source_ref": "generated:index.html",
            "archive_path": f"{ARCHIVE_ROOT}/index.html",
            "kind": "html",
            "size_bytes": len(index_html.encode("utf-8")),
            "sha256": sha256_text(index_html),
            "content_included": False,
        }
    ]
    seen: set[str] = set()
    for artifact in artifacts:
        if artifact.get("status") == "missing":
            continue
        for key, kind in (("ref", "json"), ("html_ref", "html")):
            ref = str(artifact.get(key) or "")
            if not ref or ref in seen:
                continue
            path = resolve_under_root(root, ref)
            if not path.is_file():
                continue
            data = path.read_bytes()
            text = data.decode("utf-8", errors="replace")
            assert_public_payload(text, label=ref)
            records.append(
                {
                    "role": artifact["role"],
                    "source_ref": ref,
                    "archive_path": archive_path_for(ref),
                    "kind": kind,
                    "size_bytes": len(data),
                    "sha256": sha256_bytes(data),
                    "content_included": False,
                }
            )
            seen.add(ref)
    return records


def derive_status(artifacts: list[dict[str, Any]]) -> str:
    if any(item["blocking_required"] for item in artifacts):
        return "blocked"
    if any(item["status"] == "missing" for item in artifacts):
        return "degraded_missing_artifacts"
    if any(item["manual_review_required"] for item in artifacts):
        return "manual_review"
    return "pack_ready"


def build_manifest(
    *,
    root: Path,
    artifact_paths: Mapping[str, str],
    generated_at: str,
    output_dir: Path,
    index_html: str,
) -> dict[str, Any]:
    artifacts = [
        load_artifact(root, artifact_paths.get(spec["role"], spec["default_ref"]), spec)
        for spec in ARTIFACT_SPECS
    ]
    status = derive_status(artifacts)
    missing = [item["role"] for item in artifacts if item["status"] == "missing"]
    blocked = [item["role"] for item in artifacts if item["blocking_required"]]
    manual = [item["role"] for item in artifacts if item["manual_review_required"] and item["status"] != "missing"]
    pack_files = existing_pack_files(root, artifacts, index_html)
    pack_id = f"evolution-pack-{sha256_text(generated_at + json.dumps(pack_files, sort_keys=True))[:16]}"
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "pack_id": pack_id,
        "generated_at": generated_at,
        "title": "Cognitive Loop Professional Evolution Pack Export Lite",
        "archive_root": ARCHIVE_ROOT,
        "artifact_count": len(artifacts) - len(missing),
        "expected_artifact_count": len(ARTIFACT_SPECS),
        "missing_artifact_count": len(missing),
        "missing_roles": missing,
        "manual_review_roles": manual,
        "blocking_roles": blocked,
        "artifact_refs": artifacts,
        "pack_files": pack_files,
        "archive_layout": [
            f"{ARCHIVE_ROOT}/manifest.json",
            f"{ARCHIVE_ROOT}/index.html",
            *[record["archive_path"] for record in pack_files if record["archive_path"] != f"{ARCHIVE_ROOT}/index.html"],
        ],
        "operator_next_command": "python3 scripts/verify_cognitive_loop_evolution_pack_export.py --check",
        "operator_next_commands": [
            "python3 scripts/verify_cognitive_loop_evolution_pack_export.py --check",
            "python3 scripts/cognitive_loop_evolution_pack_export.py export --html --json --zip",
            "python3 scripts/cognitive_loop_artifact_console.py build --html --json",
        ],
        "guardrails": {
            "read_only": True,
            "metadata_only": True,
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
            "no_real_source_mutation": True,
        },
        "privacy": {
            "metadata_only": True,
            "source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "agent_endpoint_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "model_called": False,
            "daemon_started": False,
            "no_model_calls": True,
            "no_raw_payloads": True,
        },
        "outputs": {
            "json_ref": relative_path(root, output_dir / "evolution-pack-manifest.json"),
            "html_ref": relative_path(root, output_dir / "index.html"),
            "zip_ref": relative_path(root, output_dir / "cognitive-loop-professional-evolution-pack.zip"),
        },
        "commands": {
            "export": "python3 scripts/cognitive_loop_evolution_pack_export.py export --html --json --zip",
            "verify": "python3 scripts/verify_cognitive_loop_evolution_pack_export.py --check",
            "console": "python3 scripts/cognitive_loop_artifact_console.py build --html --json",
        },
        "content_included": False,
        "no_real_source_mutation": True,
        "no_model_calls": True,
        "no_raw_payloads": True,
    }
    assert_public_payload(manifest, label="evolution pack manifest")
    return manifest


def render_html_shell(status: str, generated_at: str) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Cognitive Loop Professional Evolution Pack</title>
</head>
<body>
  <main>
    <h1>Cognitive Loop Professional Evolution Pack</h1>
    <p>Status: <code>{escape(status)}</code>. Generated at <code>{escape(generated_at)}</code>.</p>
  </main>
</body>
</html>
"""


def render_html(manifest: Mapping[str, Any]) -> str:
    assert_public_payload(manifest, label="evolution pack html")

    def rows(items: Iterable[Mapping[str, Any]], keys: Iterable[str]) -> str:
        rendered: list[str] = []
        for item in items:
            rendered.append("<tr>" + "".join(f"<td>{escape(str(item.get(key, '')))}</td>" for key in keys) + "</tr>")
        return "\n".join(rendered)

    artifacts = manifest.get("artifact_refs")
    if not isinstance(artifacts, list):
        artifacts = []
    pack_files = manifest.get("pack_files")
    if not isinstance(pack_files, list):
        pack_files = []
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(str(manifest.get('title', 'Evolution Pack Export Lite')))}</title>
  <style>
    :root {{ color-scheme: light; --ink:#162019; --muted:#5b6b60; --line:#d8e4db; --paper:#fbfcf7; --accent:#235d44; }}
    body {{ margin:0; font-family: Charter, 'Iowan Old Style', Georgia, serif; color:var(--ink); background:linear-gradient(135deg,#fbfcf7,#edf5ed); }}
    main {{ max-width:1180px; margin:0 auto; padding:48px 20px 76px; }}
    h1 {{ font-size:clamp(2.4rem,7vw,5.5rem); line-height:.95; margin:0 0 16px; letter-spacing:0; }}
    h2 {{ margin-top:34px; }}
    p {{ color:var(--muted); max-width:820px; }}
    table {{ border-collapse:collapse; width:100%; background:rgba(255,255,255,.68); margin-top:12px; }}
    th,td {{ border:1px solid var(--line); padding:9px; text-align:left; vertical-align:top; overflow-wrap:anywhere; }}
    th {{ background:#e4f0e7; }}
    code {{ color:var(--accent); }}
    @media (max-width:760px) {{ table {{ display:block; overflow-x:auto; white-space:nowrap; }} th,td {{ font-size:.85rem; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Cognitive Loop Professional Evolution Pack</h1>
    <p>Status: <code>{escape(str(manifest.get('status')))}</code>. This local-first export packages metadata-only evolution evidence for maintainers and platform Agents. It includes no source bodies, no patch bodies, no learner answers, no Agent endpoints, and no model keys.</p>
    <h2>Pack Summary</h2>
    <table><tbody>{rows([
        {'key': 'pack_id', 'value': manifest.get('pack_id')},
        {'key': 'artifact_count', 'value': manifest.get('artifact_count')},
        {'key': 'missing_artifact_count', 'value': manifest.get('missing_artifact_count')},
        {'key': 'no_real_source_mutation', 'value': manifest.get('no_real_source_mutation')},
        {'key': 'no_model_calls', 'value': manifest.get('no_model_calls')},
    ], ('key', 'value'))}</tbody></table>
    <h2>Artifact Chain</h2>
    <table><thead><tr><th>Role</th><th>Schema</th><th>Status</th><th>Ref</th><th>SHA-256</th><th>Manual</th><th>Blocked</th></tr></thead><tbody>{rows([item for item in artifacts if isinstance(item, Mapping)], ('role', 'schema_version', 'status', 'ref', 'sha256', 'manual_review_required', 'blocking_required'))}</tbody></table>
    <h2>Pack Files</h2>
    <table><thead><tr><th>Role</th><th>Archive Path</th><th>Kind</th><th>Bytes</th><th>SHA-256</th></tr></thead><tbody>{rows([item for item in pack_files if isinstance(item, Mapping)], ('role', 'archive_path', 'kind', 'size_bytes', 'sha256'))}</tbody></table>
  </main>
</body>
</html>
"""


def write_zip_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name)
    info.date_time = (2026, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def write_archive(root: Path, manifest: Mapping[str, Any], html: str, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = dump_json(manifest).encode("utf-8")
    html_bytes = html.encode("utf-8")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        write_zip_entry(archive, f"{ARCHIVE_ROOT}/manifest.json", manifest_bytes)
        write_zip_entry(archive, f"{ARCHIVE_ROOT}/index.html", html_bytes)
        for record in manifest.get("pack_files", []):
            if not isinstance(record, Mapping):
                continue
            source_ref = str(record.get("source_ref") or "")
            archive_ref = str(record.get("archive_path") or "")
            if not source_ref or source_ref == "generated:index.html":
                continue
            path = resolve_under_root(root, source_ref)
            data = path.read_bytes()
            assert_public_payload(data.decode("utf-8", errors="replace"), label=source_ref)
            if sha256_bytes(data) != record.get("sha256"):
                raise EvolutionPackExportError(f"Pack file hash drifted before archive write: {source_ref}")
            write_zip_entry(archive, archive_ref, data)


def cmd_export(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    output_dir = resolve_under_root(root, args.output_dir)
    artifact_paths = {
        "artifact_console": args.artifact_console,
        "evolution_report": args.evolution_report,
        "apply_plan": args.apply_plan,
        "improvement_comparison": args.improvement_comparison,
        "patch_proposal": args.patch_proposal,
        "evolution_receipt_link": args.receipt,
        "mastra_workflow_replay": args.replay,
        "patch_apply_sandbox": args.sandbox,
    }
    shell = render_html_shell("building", args.generated_at)
    manifest = build_manifest(
        root=root,
        artifact_paths=artifact_paths,
        generated_at=args.generated_at,
        output_dir=output_dir,
        index_html=shell,
    )
    html = render_html(manifest)
    manifest["pack_files"][0]["size_bytes"] = len(html.encode("utf-8"))
    manifest["pack_files"][0]["sha256"] = sha256_text(html)
    assert_public_payload(manifest, label="evolution pack manifest")

    output_dir.mkdir(parents=True, exist_ok=True)
    if args.json:
        (output_dir / "evolution-pack-manifest.json").write_text(dump_json(manifest), encoding="utf-8")
    if args.html:
        (output_dir / "index.html").write_text(html, encoding="utf-8")
    if args.zip:
        write_archive(root, manifest, html, output_dir / "cognitive-loop-professional-evolution-pack.zip")
    print(dump_json(manifest), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Project root.")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="Export a professional evolution evidence pack.")
    export.add_argument("--artifact-console", default=".cognitive-loop/artifacts/console/manifest.json")
    export.add_argument("--evolution-report", default=".cognitive-loop/artifacts/evolution/evolution-report-lite.json")
    export.add_argument("--apply-plan", default=".cognitive-loop/artifacts/applied/apply-plan-lite.json")
    export.add_argument("--improvement-comparison", default=".cognitive-loop/artifacts/comparison/improvement-comparison-lite.json")
    export.add_argument("--patch-proposal", default=".cognitive-loop/artifacts/patches/patch-proposal-lite.json")
    export.add_argument("--receipt", default=".cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json")
    export.add_argument("--replay", default=".cognitive-loop/artifacts/mastra/mastra-evolution-workflow-replay.json")
    export.add_argument("--sandbox", default=".cognitive-loop/artifacts/applied/patch-apply-sandbox-receipt.json")
    export.add_argument("--generated-at", default="2026-01-01T00:00:00Z")
    export.add_argument("--output-dir", default=".cognitive-loop/artifacts/evolution-pack")
    export.add_argument("--html", action="store_true")
    export.add_argument("--json", action="store_true")
    export.add_argument("--zip", action="store_true")
    export.set_defaults(func=cmd_export)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except EvolutionPackExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
