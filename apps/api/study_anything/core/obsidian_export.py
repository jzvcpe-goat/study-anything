"""Obsidian-compatible markdown export for completed learning sessions."""

from __future__ import annotations

import re
from typing import Any

from .workflow import LearningState


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
    lines = [
        "---",
        f"study_anything_session: {state.session_id}",
        f"track: {state.track}",
        f"stage: {state.stage}",
        f"mastery_level: {state.mastery.level}",
        f"mastery_bloom: {state.mastery.bloom}",
        f"source_reference: {source.reference}",
        f"source_excerpt_hash: {source.excerpt_hash}",
        "tags:",
        "  - study-anything",
        f"  - study-anything/{state.track.lower()}",
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
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title).strip("-").lower()
    if not slug:
        slug = "study-anything"
    return f"study-anything-{slug}-{state.session_id[:8]}.md"
