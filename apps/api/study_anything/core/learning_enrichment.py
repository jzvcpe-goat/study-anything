"""Learning enrichment exports for platform-agent teaching surfaces."""

from __future__ import annotations

from html import escape
import re
from typing import Any

from .workflow import LearningState


LEARNING_ENRICHMENT_ARTIFACT_SCHEMA_VERSION = "learning-enrichment-artifact-v1"


def build_learning_enrichment_artifact(state: LearningState) -> dict[str, object]:
    """Build a redacted Markdown and HTML micro-lesson from enrichment context.

    Platform agents own the original browser, document, video, app, Markdown, or
    Obsidian sources. This artifact gives them a compact teaching surface with
    source references and hashes, without returning raw source or enrichment text.
    """

    if state.source is None:
        raise ValueError("Session needs a source before exporting an enrichment artifact.")
    if not state.enrichment_items:
        raise ValueError("Session needs enrichment context before exporting an enrichment artifact.")

    source_refs = _source_refs(state)
    micro_lesson = {
        "title": f"{state.source.title} enrichment brief",
        "overview": _layer_content(state, "overview")
        or "Use the cited enrichment references to explain the topic before asking source-bound questions.",
        "glossary": _layer_content(state, "glossary") or [],
        "practice_prompt": "Ask the learner to connect the primary source to at least one enrichment reference.",
        "review_cue": "Re-answer the quiz, then reopen only the cited references whose hashes you cannot recall.",
    }
    markdown = "\n".join(_markdown_lines(state, source_refs, micro_lesson))
    html = _html_document(state, source_refs, micro_lesson)
    return {
        "schema_version": LEARNING_ENRICHMENT_ARTIFACT_SCHEMA_VERSION,
        "session_id": state.session_id,
        "format": "markdown+html",
        "filename": _filename(state),
        "intended_consumers": [
            "platform_agent",
            "kimi_work",
            "codex",
            "workbuddy",
            "notebooklm_bridge",
            "obsidian_pipeline",
        ],
        "source_references": source_refs,
        "micro_lesson": micro_lesson,
        "markdown": markdown,
        "html": html,
        "privacy": {
            "raw_source_text_included": False,
            "raw_enrichment_text_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "secrets_included": False,
        },
    }


def _source_refs(state: LearningState) -> list[dict[str, object]]:
    source = state.source
    refs: list[dict[str, object]] = []
    if source is not None:
        refs.append(
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
        refs.append(
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
    return refs


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


def _layer_content(state: LearningState, layer_name: str) -> Any:
    for layer in state.teaching_layers:
        if isinstance(layer, dict) and layer.get("layer") == layer_name:
            return layer.get("content")
    return None


def _markdown_lines(
    state: LearningState,
    source_refs: list[dict[str, object]],
    micro_lesson: dict[str, object],
) -> list[str]:
    source = state.source
    assert source is not None
    lines = [
        f"# {micro_lesson['title']}",
        "",
        "## Teaching Brief",
        "",
        _markdown_value(micro_lesson["overview"]),
        "",
        "## Professional Terms",
        "",
        _markdown_value(micro_lesson["glossary"]),
        "",
        "## Source Map",
        "",
    ]
    for ref in source_refs:
        locator = f" locator={ref['locator']}" if ref.get("locator") else ""
        lines.append(
            f"- `{ref['kind']}` `{ref['source_type']}` {ref['title']}: "
            f"{ref['reference']} (`{ref['excerpt_hash']}`{locator})"
        )
    lines.extend(
        [
            "",
            "## Practice",
            "",
            f"- {micro_lesson['practice_prompt']}",
            f"- {micro_lesson['review_cue']}",
        ]
    )
    return lines


def _markdown_value(value: object) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {_markdown_value(item)}" for item in value) or "_No terms yet._"
    if isinstance(value, dict):
        return "\n".join(f"- **{key}**: {_markdown_value(item)}" for key, item in value.items())
    text = str(value or "").strip()
    return text or "_No content yet._"


def _html_document(
    state: LearningState,
    source_refs: list[dict[str, object]],
    micro_lesson: dict[str, object],
) -> str:
    source = state.source
    assert source is not None
    refs_html = "\n".join(
        "<li>"
        f"<code>{escape(str(ref['kind']))}</code> "
        f"<strong>{escape(str(ref['title']))}</strong> "
        f"<span>{escape(str(ref['reference']))}</span> "
        f"<code>{escape(str(ref['excerpt_hash']))}</code>"
        f"{' <em>' + escape(str(ref['locator'])) + '</em>' if ref.get('locator') else ''}"
        "</li>"
        for ref in source_refs
    )
    return "\n".join(
        [
            '<article class="study-anything-enrichment" data-schema="learning-enrichment-artifact-v1">',
            f"  <h1>{escape(str(micro_lesson['title']))}</h1>",
            "  <section>",
            "    <h2>Teaching Brief</h2>",
            f"    {_html_value(micro_lesson['overview'])}",
            "  </section>",
            "  <section>",
            "    <h2>Professional Terms</h2>",
            f"    {_html_value(micro_lesson['glossary'])}",
            "  </section>",
            "  <section>",
            "    <h2>Source Map</h2>",
            f"    <ul>{refs_html}</ul>",
            "  </section>",
            "  <section>",
            "    <h2>Practice</h2>",
            f"    <p>{escape(str(micro_lesson['practice_prompt']))}</p>",
            f"    <p>{escape(str(micro_lesson['review_cue']))}</p>",
            "  </section>",
            "</article>",
        ]
    )


def _html_value(value: object) -> str:
    if isinstance(value, list):
        items = "\n".join(f"<li>{_html_value(item)}</li>" for item in value)
        return f"<ul>{items}</ul>" if items else "<p>No terms yet.</p>"
    if isinstance(value, dict):
        items = "\n".join(
            f"<li><strong>{escape(str(key))}</strong>: {_html_value(item)}</li>"
            for key, item in value.items()
        )
        return f"<ul>{items}</ul>" if items else "<p>No content yet.</p>"
    text = str(value or "").strip()
    return f"<p>{escape(text)}</p>" if text else "<p>No content yet.</p>"


def _filename(state: LearningState) -> str:
    source = state.source
    title = source.title if source else state.session_id
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title).strip("-").lower()
    return f"study-anything-enrichment-{slug or 'session'}-{state.session_id[:8]}.html"
