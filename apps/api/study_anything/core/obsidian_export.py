"""Obsidian-compatible markdown export for completed learning sessions."""

from __future__ import annotations

import re
import json
from typing import Any, Optional

from .workflow import LearningState

WINDOWS_RESERVED_FILENAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def build_obsidian_markdown_export(state: LearningState) -> dict[str, object]:
    source = state.source
    if source is None:
        raise ValueError("Session needs a source before exporting Obsidian markdown.")

    sections = [
        "frontmatter",
        "source",
        "teaching_layers",
        "quiz_review",
        "mastery",
        "insights",
        "enrichment",
        "backlinks",
    ]
    markdown = "\n".join(_markdown_lines(state))
    return {
        "schema_version": "obsidian-markdown-export-v1",
        "session_id": state.session_id,
        "format": "markdown",
        "filename": _filename(state),
        "sections": sections,
        "markdown": markdown,
        "privacy": {
            "raw_source_text_included": False,
            "source_references_included": True,
            "learner_answers_included": bool(state.answers),
            "grading_feedback_included": bool(state.grading_results),
            "agent_endpoints_included": False,
            "secrets_included": False,
        },
    }


def _markdown_lines(state: LearningState) -> list[str]:
    source = state.source
    assert source is not None
    title = source.title or "Study Anything Session"
    backlinks = _obsidian_backlinks(state)
    lines = [
        "---",
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
        "---",
        "",
        f"# {title}",
        "",
        "## Source",
        "",
        f"- Type: `{source.source_type}`",
        f"- Reference: {source.reference}",
        f"- Excerpt hash: `{source.excerpt_hash}`",
        "",
        "## Teaching Layers",
        "",
    ]
    if state.teaching_layers:
        for layer in state.teaching_layers:
            layer_name = str(layer.get("layer") or "layer")
            lines.extend([f"### {layer_name.title()}", "", _stringify(layer.get("content")), ""])
    else:
        lines.extend(["_No teaching layers generated yet._", ""])

    lines.extend(["## Quiz Review", ""])
    if state.quiz_items:
        answers = {answer.item_id: answer.text for answer in state.answers}
        grades = {grade.item_id: grade for grade in state.grading_results}
        for index, item in enumerate(state.quiz_items, start=1):
            grade = grades.get(item.item_id)
            lines.extend(
                [
                    f"### Question {index}",
                    "",
                    f"- Prompt: {item.prompt}",
                    f"- Source: {item.source_ref}",
                    f"- Excerpt hash: `{item.excerpt_hash}`",
                    f"- Answer: {answers.get(item.item_id, '_Not answered yet._')}",
                ]
            )
            if grade is not None:
                lines.extend([f"- Score: {grade.score:.2f}", f"- Feedback: {grade.feedback}"])
            lines.append("")
    else:
        lines.extend(["_No quiz generated yet._", ""])

    lines.extend(
        [
            "## Mastery",
            "",
            f"- Level: {state.mastery.level:.1f}",
            f"- Bloom: {state.mastery.bloom}",
            "",
            "## Insights",
            "",
        ]
    )
    if state.insights:
        lines.extend([f"- {insight}" for insight in state.insights])
    else:
        lines.append("_No synthesis yet._")
    lines.extend(["", "## Enrichment Context", ""])
    if state.enrichment_items:
        for item in state.enrichment_items:
            locator = f" locator={item.locator}" if item.locator else ""
            lines.append(
                f"- `{item.source_type}` {item.title}: {item.reference}"
                f" (`{item.excerpt_hash}`{locator})"
            )
    else:
        lines.append("_No enrichment context attached._")
    lines.extend(["", "## Backlinks", ""])
    if backlinks:
        lines.extend([f"- {backlink}" for backlink in backlinks])
    else:
        lines.append("_No Obsidian backlinks provided._")
    lines.extend(["", "## Review Cue", "", "- Re-answer the quiz without opening the source."])
    return lines


def _stringify(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {_stringify(item)}" for item in value)
    if isinstance(value, dict):
        return "\n".join(f"- **{key}**: {_stringify(item)}" for key, item in value.items())
    text = str(value or "").strip()
    return text or "_Empty layer output._"


def _filename(state: LearningState) -> str:
    source = state.source
    title = source.title if source else state.session_id
    slug = re.sub(r'[<>:"/\\|?*\x00-\x1f#^\[\]]+', "-", title)
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff._ -]+", "-", slug)
    slug = re.sub(r"[\s._-]+", "-", slug).strip(" .-_").lower()
    if not slug:
        slug = "study-anything"
    if slug in WINDOWS_RESERVED_FILENAMES:
        slug = f"study-anything-{slug}"
    slug = slug[:96].strip(" .-_") or "study-anything"
    return f"study-anything-{slug}-{state.session_id[:8]}.md"


def _yaml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _tag_part(value: str) -> str:
    tag = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-")
    return tag or "general"


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


def _normalize_backlink(value: Any) -> Optional[str]:
    text = re.sub(r"[\r\n]+", " ", str(value or "")).strip()
    if not text:
        return None
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].strip()
    text = re.sub(r"\s*\|\s*", " - ", text)
    text = re.sub(r"[\[\]]+", "", text).strip()
    if not text:
        return None
    return f"[[{text}]]"
