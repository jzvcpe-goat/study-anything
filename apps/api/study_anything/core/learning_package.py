"""Portable learning package export for platform agents and knowledge tools."""

from __future__ import annotations

import re
from typing import Any

from .workflow import LearningState


def build_learning_package_export(state: LearningState) -> dict[str, object]:
    """Build a redacted, portable package for NotebookLM-style and agent workflows.

    The package is intentionally not a raw-source archive. Platform agents already
    own browser, file, video, and app access, so Study Anything exports the
    learning state, source references, hashes, and generated learning artifacts.
    """

    source = state.source
    if source is None:
        raise ValueError("Session needs a source before exporting a learning package.")

    return {
        "schema_version": "learning-package-v1",
        "session_id": state.session_id,
        "format": "json",
        "filename": _filename(state),
        "intended_consumers": [
            "platform_agent",
            "notebooklm_bridge",
            "obsidian_pipeline",
            "local_archive",
        ],
        "summary": {
            "track": state.track,
            "stage": state.stage,
            "mastery": {
                "level": state.mastery.level,
                "bloom": state.mastery.bloom,
            },
            "source": {
                "source_type": source.source_type,
                "reference": source.reference,
                "title": source.title,
                "excerpt_hash": source.excerpt_hash,
                "verified": source.verified,
            },
            "counts": {
                "enrichment_items": len(state.enrichment_items),
                "teaching_layers": len(state.teaching_layers),
                "quiz_items": len(state.quiz_items),
                "answers": len(state.answers),
                "grading_results": len(state.grading_results),
                "insights": len(state.insights),
            },
        },
        "source_references": _source_references(state),
        "teaching_layers": _teaching_layers(state),
        "quiz_review": _quiz_review(state),
        "mastery": {
            "level": state.mastery.level,
            "bloom": state.mastery.bloom,
            "review_cue": "Re-answer the quiz without opening the source.",
        },
        "insights": list(state.insights),
        "notebooklm_bridge": {
            "status": "ready_for_manual_import",
            "role": "Use this package as learning-state context. Upload original user-owned sources through the platform agent when the user wants NotebookLM analysis.",
            "suggested_sources": _source_references(state),
            "raw_source_text_included": False,
        },
        "privacy": {
            "raw_source_text_included": False,
            "raw_enrichment_text_included": False,
            "learner_answers_included": bool(state.answers),
            "grading_feedback_included": bool(state.grading_results),
            "generated_teaching_content_included": bool(state.teaching_layers),
            "agent_endpoints_included": False,
            "secrets_included": False,
        },
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
                "metadata_keys": sorted(str(key) for key in item.metadata),
            }
        )
    return references


def _teaching_layers(state: LearningState) -> list[dict[str, object]]:
    layers: list[dict[str, object]] = []
    for layer in state.teaching_layers:
        if not isinstance(layer, dict):
            continue
        layers.append(
            {
                "layer": layer.get("layer"),
                "task_type": layer.get("task_type"),
                "content": layer.get("content"),
                "citations": layer.get("citations") or [],
                "confidence": layer.get("confidence"),
                "agent": layer.get("agent") or {},
            }
        )
    return layers


def _quiz_review(state: LearningState) -> list[dict[str, object]]:
    answers = {answer.item_id: answer.text for answer in state.answers}
    grades = {grade.item_id: grade for grade in state.grading_results}
    review: list[dict[str, object]] = []
    for item in state.quiz_items:
        grade = grades.get(item.item_id)
        record: dict[str, object] = {
            "item_id": item.item_id,
            "prompt": item.prompt,
            "source_ref": item.source_ref,
            "excerpt_hash": item.excerpt_hash,
            "rubric": item.rubric,
            "answer": answers.get(item.item_id),
        }
        if grade is not None:
            record["score"] = grade.score
            record["feedback"] = grade.feedback
        review.append(record)
    return review


def _filename(state: LearningState) -> str:
    source = state.source
    title = source.title if source else state.session_id
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title).strip("-").lower()
    if not slug:
        slug = "study-anything"
    return f"study-anything-learning-package-{slug}-{state.session_id[:8]}.json"
