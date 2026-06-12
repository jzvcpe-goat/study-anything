"""Second-brain handoff exports for Obsidian, NotebookLM-style, and archives."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .learning_enrichment import build_learning_enrichment_artifact
from .learning_package import build_learning_package_export
from .workflow import LearningState


SECOND_BRAIN_HANDOFF_SCHEMA_VERSION = "second-brain-handoff-v1"
SECOND_BRAIN_ARCHIVE_MANIFEST_SCHEMA_VERSION = "second-brain-archive-manifest-v1"
SECOND_BRAIN_OBSIDIAN_NOTE_SCHEMA_VERSION = "second-brain-obsidian-note-v1"


def build_second_brain_handoff(state: LearningState) -> dict[str, object]:
    """Build a redacted second-brain handoff for user-owned knowledge tools.

    This export is stricter than the direct Obsidian/learning-package exports.
    It is meant for platform Agents and local archive workflows, so it keeps
    stable references, generated learning artifacts, and review metadata while
    excluding raw source text, raw enrichment text, learner answers, grading
    feedback, raw agent metadata, endpoints, and secrets.
    """

    if state.source is None:
        raise ValueError("Session needs a source before exporting second-brain handoff.")

    obsidian_note = _obsidian_note(state)
    learning_package = _redacted_learning_package(state)
    enrichment_artifact = _safe_enrichment_artifact(state)
    notebooklm_bridge = _notebooklm_bridge(state)
    archive_files = _archive_files(
        state,
        obsidian_note=obsidian_note,
        learning_package=learning_package,
        enrichment_artifact=enrichment_artifact,
    )
    archive_manifest = _archive_manifest(
        state,
        files=archive_files,
        notebooklm_bridge=notebooklm_bridge,
        obsidian_note=obsidian_note,
    )

    return {
        "schema_version": SECOND_BRAIN_HANDOFF_SCHEMA_VERSION,
        "session_id": state.session_id,
        "format": "json+markdown+html",
        "filename": _handoff_filename(state),
        "intended_consumers": [
            "platform_agent",
            "kimi_work",
            "codex",
            "workbuddy",
            "obsidian_vault",
            "notebooklm_manual_bridge",
            "local_archive",
        ],
        "handoff_contract": {
            "official_notebooklm_api_required": False,
            "notebooklm_mode": "manual_export_import",
            "obsidian_mode": "write_markdown_note_then_review_queue",
            "local_archive_mode": "write_manifest_and_files",
            "platform_agent_owns_original_sources": True,
            "study_anything_owns_learning_state": True,
        },
        "obsidian": obsidian_note,
        "notebooklm_bridge": notebooklm_bridge,
        "learning_package": learning_package,
        "enrichment_artifact": enrichment_artifact,
        "local_archive": {
            "manifest": archive_manifest,
            "files": archive_files,
        },
        "privacy": _privacy_flags(),
    }


def _redacted_learning_package(state: LearningState) -> dict[str, object]:
    package = build_learning_package_export(state)
    package["schema_version"] = "learning-package-v1-redacted-for-second-brain"
    package["filename"] = _json_filename(state, "learning-package-redacted")
    package["quiz_review"] = [
        {
            "item_id": item.get("item_id"),
            "prompt": item.get("prompt"),
            "source_ref": item.get("source_ref"),
            "excerpt_hash": item.get("excerpt_hash"),
            "rubric": item.get("rubric"),
            "answer_included": False,
            "grading_feedback_included": False,
        }
        for item in _as_list_of_dicts(package.get("quiz_review"))
    ]
    package["teaching_layers"] = [
        {
            "layer": layer.get("layer"),
            "task_type": layer.get("task_type"),
            "content": layer.get("content"),
            "citations": layer.get("citations") or [],
            "confidence": layer.get("confidence"),
            "agent_metadata_included": False,
        }
        for layer in _as_list_of_dicts(package.get("teaching_layers"))
    ]
    package["notebooklm_bridge"] = _notebooklm_bridge(state)
    package["privacy"] = {
        **_privacy_flags(),
        "generated_teaching_content_included": bool(state.teaching_layers),
        "insights_included": bool(state.insights),
        "quiz_prompts_included": bool(state.quiz_items),
    }
    return package


def _safe_enrichment_artifact(state: LearningState) -> dict[str, object] | None:
    if not state.enrichment_items:
        return None
    artifact = build_learning_enrichment_artifact(state)
    return {
        **artifact,
        "privacy": {
            **_privacy_flags(),
            "generated_teaching_content_included": True,
        },
    }


def _obsidian_note(state: LearningState) -> dict[str, object]:
    source = state.source
    assert source is not None
    title = source.title or "Study Anything Session"
    backlinks = _obsidian_backlinks(state)
    graph = _note_graph(state, backlinks)
    review_queue = _review_queue(state)
    markdown = "\n".join(_obsidian_markdown_lines(state, backlinks, review_queue))
    filename = _markdown_filename(state, prefix="study-anything-second-brain")
    return {
        "schema_version": SECOND_BRAIN_OBSIDIAN_NOTE_SCHEMA_VERSION,
        "filename": filename,
        "title": title,
        "frontmatter": {
            "study_anything_schema": SECOND_BRAIN_OBSIDIAN_NOTE_SCHEMA_VERSION,
            "study_anything_session": state.session_id,
            "track": state.track,
            "stage": state.stage,
            "mastery_level": state.mastery.level,
            "mastery_bloom": state.mastery.bloom,
            "source_title": title,
            "source_type": source.source_type,
            "source_reference": source.reference,
            "source_excerpt_hash": source.excerpt_hash,
            "tags": ["study-anything", f"study-anything/{_tag_part(state.track)}"],
            "related_notes": backlinks,
            "review_queue": review_queue,
        },
        "backlinks": backlinks,
        "note_graph": graph,
        "review_queue": review_queue,
        "markdown": markdown,
        "privacy": _privacy_flags(),
    }


def _obsidian_markdown_lines(
    state: LearningState,
    backlinks: list[str],
    review_queue: dict[str, object],
) -> list[str]:
    source = state.source
    assert source is not None
    title = source.title or "Study Anything Session"
    lines = [
        "---",
        f"study_anything_schema: {_yaml_string(SECOND_BRAIN_OBSIDIAN_NOTE_SCHEMA_VERSION)}",
        f"study_anything_session: {_yaml_string(state.session_id)}",
        f"track: {_yaml_string(state.track)}",
        f"stage: {_yaml_string(state.stage)}",
        f"mastery_level: {state.mastery.level}",
        f"mastery_bloom: {_yaml_string(state.mastery.bloom)}",
        f"source_title: {_yaml_string(title)}",
        f"source_type: {_yaml_string(source.source_type)}",
        f"source_reference: {_yaml_string(source.reference)}",
        f"source_excerpt_hash: {_yaml_string(source.excerpt_hash)}",
        "tags:",
        "  - study-anything",
        f"  - study-anything/{_tag_part(state.track)}",
        "related_notes:",
        *[f"  - {_yaml_string(backlink)}" for backlink in backlinks],
        "review_queue:",
        f"  mode: {_yaml_string(review_queue['mode'])}",
        f"  prompt_count: {review_queue['prompt_count']}",
        f"  mastery_level: {review_queue['mastery_level']}",
        f"  mastery_bloom: {_yaml_string(review_queue['mastery_bloom'])}",
        "---",
        "",
        f"# {title}",
        "",
        "> Study Anything second-brain handoff. Raw source text, learner answers, grading feedback, Agent endpoints, and secrets are not included.",
        "",
        "## Source Map",
        "",
        f"- Primary: `{source.source_type}` {source.reference} (`{source.excerpt_hash}`)",
    ]
    if state.enrichment_items:
        for item in state.enrichment_items:
            locator = f" locator={item.locator}" if item.locator else ""
            lines.append(
                f"- Enrichment: `{item.source_type}` {item.title}: {item.reference} "
                f"(`{item.excerpt_hash}`{locator})"
            )
    else:
        lines.append("- Enrichment: _none attached_")

    lines.extend(["", "## Learning Map", ""])
    if state.teaching_layers:
        for layer in state.teaching_layers:
            if not isinstance(layer, dict):
                continue
            layer_name = str(layer.get("layer") or "layer")
            lines.extend([f"### {layer_name.title()}", "", _markdown_value(layer.get("content")), ""])
    else:
        lines.extend(["_No teaching layers generated yet._", ""])

    lines.extend(
        [
            "## Mastery Snapshot",
            "",
            f"- Level: {state.mastery.level:.1f}",
            f"- Bloom: {state.mastery.bloom}",
            "",
            "## Review Queue",
            "",
            "- Re-answer the prompts without opening the source.",
            "- Reopen only references whose excerpt hash or locator you cannot explain.",
        ]
    )
    if state.quiz_items:
        for index, item in enumerate(state.quiz_items, start=1):
            lines.extend(
                [
                    "",
                    f"### Prompt {index}",
                    "",
                    f"- Prompt: {item.prompt}",
                    f"- Source: {item.source_ref}",
                    f"- Excerpt hash: `{item.excerpt_hash}`",
                    "- Answer: _not included in second-brain handoff_",
                ]
            )
    else:
        lines.extend(["", "_No quiz prompts generated yet._"])

    lines.extend(["", "## Insights", ""])
    if state.insights:
        lines.extend([f"- {insight}" for insight in state.insights])
    else:
        lines.append("_No synthesis yet._")
    lines.extend(["", "## Backlinks", ""])
    if backlinks:
        lines.extend([f"- {backlink}" for backlink in backlinks])
    else:
        lines.append("_No Obsidian backlinks provided._")
    return lines


def _notebooklm_bridge(state: LearningState) -> dict[str, object]:
    source = state.source
    assert source is not None
    return {
        "status": "ready_for_manual_import",
        "official_notebooklm_api_required": False,
        "bridge_mode": "manual_export_import",
        "role": (
            "Use this handoff as learning-state context. Upload or paste original user-owned "
            "sources into NotebookLM through the platform Agent when the user wants NotebookLM analysis."
        ),
        "manual_steps": [
            "Export or open the local archive manifest.",
            "Upload original user-approved sources through the platform Agent or NotebookLM UI.",
            "Paste the redacted learning package or Obsidian note as study-state context.",
            "Ask NotebookLM to compare its source-grounded answer with Study Anything mastery and review cues.",
        ],
        "suggested_sources": _source_references(state),
        "privacy": _privacy_flags(),
    }


def _archive_files(
    state: LearningState,
    *,
    obsidian_note: dict[str, object],
    learning_package: dict[str, object],
    enrichment_artifact: dict[str, object] | None,
) -> list[dict[str, object]]:
    files = [
        _archive_file(
            path=f"obsidian/{obsidian_note['filename']}",
            role="obsidian_note",
            media_type="text/markdown",
            content=str(obsidian_note["markdown"]),
        ),
        _archive_file(
            path=f"learning-package/{learning_package['filename']}",
            role="learning_package",
            media_type="application/json",
            content=_dump_json(learning_package),
        ),
    ]
    if enrichment_artifact is not None:
        markdown_name = _markdown_filename(state, prefix="study-anything-enrichment")
        html_name = str(enrichment_artifact.get("filename") or _html_filename(state))
        files.extend(
            [
                _archive_file(
                    path=f"enrichment/{markdown_name}",
                    role="enrichment_markdown",
                    media_type="text/markdown",
                    content=str(enrichment_artifact.get("markdown") or ""),
                ),
                _archive_file(
                    path=f"enrichment/{html_name}",
                    role="enrichment_html",
                    media_type="text/html",
                    content=str(enrichment_artifact.get("html") or ""),
                ),
            ]
        )
    return files


def _archive_manifest(
    state: LearningState,
    *,
    files: list[dict[str, object]],
    notebooklm_bridge: dict[str, object],
    obsidian_note: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": SECOND_BRAIN_ARCHIVE_MANIFEST_SCHEMA_VERSION,
        "archive_id": f"second-brain-{state.session_id[:8]}",
        "session_id": state.session_id,
        "track": state.track,
        "files": [
            {key: file[key] for key in ["path", "role", "media_type", "bytes", "sha256"]}
            for file in files
        ],
        "obsidian_entrypoint": f"obsidian/{obsidian_note['filename']}",
        "notebooklm_bridge_status": notebooklm_bridge["status"],
        "review_queue": obsidian_note["review_queue"],
        "privacy": _privacy_flags(),
    }


def _archive_file(path: str, role: str, media_type: str, content: str) -> dict[str, object]:
    data = content.encode("utf-8")
    return {
        "path": path,
        "role": role,
        "media_type": media_type,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "content": content,
    }


def _source_references(state: LearningState) -> list[dict[str, object]]:
    source = state.source
    references: list[dict[str, object]] = []
    if source is not None:
        references.append(
            {
                "kind": "primary",
                "source_type": source.source_type,
                "reference": source.reference,
                "title": source.title,
                "excerpt_hash": source.excerpt_hash,
                "verified": source.verified,
            }
        )
    for item in state.enrichment_items:
        references.append(
            {
                "kind": "enrichment",
                "source_type": item.source_type,
                "reference": item.reference,
                "title": item.title,
                "excerpt_hash": item.excerpt_hash,
                "locator": item.locator,
                "provenance": _public_provenance(item.metadata.get("provenance")),
                "redaction_policy": item.metadata.get("redaction_policy") or "reference_only",
            }
        )
    return references


def _note_graph(state: LearningState, backlinks: list[str]) -> dict[str, object]:
    source = state.source
    assert source is not None
    nodes: list[dict[str, object]] = [
        {
            "id": f"session:{state.session_id}",
            "kind": "study_session",
            "label": source.title,
        },
        {
            "id": f"source:{source.excerpt_hash}",
            "kind": "primary_source",
            "label": source.reference,
        },
    ]
    edges: list[dict[str, object]] = [
        {
            "from": f"session:{state.session_id}",
            "to": f"source:{source.excerpt_hash}",
            "kind": "USES_SOURCE",
        }
    ]
    for item in state.enrichment_items:
        node_id = f"enrichment:{item.excerpt_hash}"
        nodes.append({"id": node_id, "kind": item.source_type, "label": item.title})
        edges.append({"from": f"session:{state.session_id}", "to": node_id, "kind": "ENRICHED_BY"})
    for backlink in backlinks:
        node_id = f"obsidian:{_slug(backlink)}"
        nodes.append({"id": node_id, "kind": "obsidian_backlink", "label": backlink})
        edges.append({"from": f"session:{state.session_id}", "to": node_id, "kind": "RELATED_NOTE"})
    return {"nodes": nodes, "edges": edges}


def _review_queue(state: LearningState) -> dict[str, object]:
    return {
        "mode": "manual_spaced_review",
        "prompt_count": len(state.quiz_items),
        "quiz_item_ids": [item.item_id for item in state.quiz_items],
        "mastery_level": state.mastery.level,
        "mastery_bloom": state.mastery.bloom,
        "suggested_next_action": "Re-answer prompts, then compare against source hashes and enrichment locators.",
    }


def _obsidian_backlinks(state: LearningState) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for item in state.enrichment_items:
        candidates: list[Any] = []
        raw_backlinks = item.metadata.get("obsidian_backlinks")
        raw_related = item.metadata.get("backlinks")
        if isinstance(raw_backlinks, list):
            candidates.extend(raw_backlinks)
        if isinstance(raw_related, list):
            candidates.extend(raw_related)
        if item.source_type == "obsidian_note":
            candidates.append(item.title)
        for candidate in candidates:
            link = _normalize_backlink(candidate)
            if link and link not in seen:
                seen.add(link)
                links.append(link)
    return links


def _normalize_backlink(value: Any) -> str | None:
    text = re.sub(r"[\r\n]+", " ", str(value or "")).strip()
    if not text:
        return None
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].strip()
    text = re.sub(r"\s*\|\s*", " - ", text)
    text = re.sub(r"[\[\]]+", "", text).strip()
    return f"[[{text}]]" if text else None


def _as_list_of_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _markdown_value(value: object) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {_markdown_value(item)}" for item in value) or "_No terms yet._"
    if isinstance(value, dict):
        return "\n".join(f"- **{key}**: {_markdown_value(item)}" for key, item in value.items())
    text = str(value or "").strip()
    return text or "_No content yet._"


def _privacy_flags() -> dict[str, bool]:
    return {
        "raw_source_text_included": False,
        "raw_enrichment_text_included": False,
        "learner_answers_included": False,
        "grading_feedback_included": False,
        "agent_endpoints_included": False,
        "agent_metadata_included": False,
        "secrets_included": False,
    }


def _public_provenance(value: Any) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "collector",
        "capture_method",
        "source_owner",
        "collected_at",
        "importer_plugin",
        "platform",
    }
    return {str(key): value[key] for key in sorted(value) if str(key) in allowed}


def _dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _handoff_filename(state: LearningState) -> str:
    return _json_filename(state, "second-brain-handoff")


def _json_filename(state: LearningState, prefix: str) -> str:
    source = state.source
    title = source.title if source else state.session_id
    return f"study-anything-{prefix}-{_slug(title) or 'session'}-{state.session_id[:8]}.json"


def _markdown_filename(state: LearningState, prefix: str) -> str:
    source = state.source
    title = source.title if source else state.session_id
    return f"{prefix}-{_slug(title) or 'session'}-{state.session_id[:8]}.md"


def _html_filename(state: LearningState) -> str:
    source = state.source
    title = source.title if source else state.session_id
    return f"study-anything-enrichment-{_slug(title) or 'session'}-{state.session_id[:8]}.html"


def _slug(value: object) -> str:
    slug = re.sub(r'[<>:"/\\|?*\x00-\x1f#^\[\]]+', "-", str(value or ""))
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff._ -]+", "-", slug)
    slug = re.sub(r"[\s._-]+", "-", slug).strip(" .-_").lower()
    if slug in {"con", "prn", "aux", "nul", *(f"com{index}" for index in range(1, 10)), *(f"lpt{index}" for index in range(1, 10))}:
        slug = f"study-anything-{slug}"
    return (slug[:96].strip(" .-_") or "study-anything")[:96]


def _tag_part(value: str) -> str:
    tag = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-")
    return tag or "general"


def _yaml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)
