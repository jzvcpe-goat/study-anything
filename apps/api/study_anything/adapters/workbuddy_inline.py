"""WorkBuddy inline learning adapter.

This adapter lets a platform Agent such as WorkBuddy/Kimi own real model calls,
search, files, and conversation context while Study Anything records a
source-bound learning package without starting a local HTTP server.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, replace
from hashlib import sha256
from typing import Any, Iterable, Mapping

from study_anything.core.events import utc_now
from study_anything.core.security import sha256_text
from study_anything.core.workflow import (
    Answer,
    GradingResult,
    LearningState,
    Mastery,
    QuizItem,
    append_event,
    new_session,
    submit_answers,
    submit_reading,
)


INPUT_SCHEMA_VERSION = "workbuddy-learning-input-v1"
OUTPUT_SCHEMA_VERSION = "workbuddy-learning-output-v1"
SUPPORTED_PHASES = {"start", "teach", "quiz", "grade", "export", "resume", "complete"}
SUPPORTED_PRIVACY_MODES = {"metadata_only", "excerpts_only", "full_context"}
DEFAULT_PRIVACY_MODE = "excerpts_only"
PROXY_ENV_KEYS = frozenset(
    {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    }
)
LOW_QUALITY_PHRASES = (
    "is a key idea in this source",
    "key idea in the source",
    "important concept in this source",
    "this source explains the topic",
    "connect this back to the source",
)

SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|apikey|access[_-]?token|authorization|client[_-]?secret|cookie|password|secret|token)\s*[:=]\s*['\"]?[^\s,'\"}]+"
    ),
)
ABSOLUTE_PATH_PATTERN = re.compile(r"/Users/[^\s,'\"<>]+|/private/(?:tmp|var/folders)/[^\s,'\"<>]+")
FORBIDDEN_RAW_OUTPUT_PROBES = (
    "RAW_PRIVATE_INTERVIEW_NOTE_SHOULD_NOT_LEAK",
    "PRIVATE_SOURCE_SHOULD_NOT_LEAK",
    "PRIVATE_ANSWER_SHOULD_NOT_LEAK",
)


class WorkBuddyInlineError(RuntimeError):
    """Readable WorkBuddy inline adapter failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sanitize_runtime_env(env: Mapping[str, str] | None = None) -> tuple[dict[str, str], list[str]]:
    """Return an env copy without proxy vars so inline mode is not proxy-sensitive."""

    values = dict(env or {})
    removed = sorted(key for key in values if key in PROXY_ENV_KEYS)
    for key in removed:
        values.pop(key, None)
    return values, removed


def _text(value: Any, default: str = "") -> str:
    if isinstance(value, str):
        return value.strip()
    return default


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _public_id(value: str, prefix: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value.strip()).strip("-")
    return cleaned or prefix


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _assert_no_secret_like_values(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in {
                "api_key",
                "apikey",
                "secret",
                "token",
                "password",
                "cookie",
                "authorization",
                "bearer",
                "model_api_key",
                "agent_credentials",
            }:
                raise WorkBuddyInlineError(f"Forbidden credential-like field at {path}.{key}")
            _assert_no_secret_like_values(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_secret_like_values(child, f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in SECRET_PATTERNS:
            if pattern.search(value):
                raise WorkBuddyInlineError(f"Secret-like value found at {path}")


def _assert_public_output_safe(payload: Mapping[str, Any]) -> None:
    text = dump_json(payload)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise WorkBuddyInlineError("Output contains secret-like text.")
    if ABSOLUTE_PATH_PATTERN.search(text):
        raise WorkBuddyInlineError("Output contains local absolute path text.")
    for probe in FORBIDDEN_RAW_OUTPUT_PROBES:
        if probe in text:
            raise WorkBuddyInlineError(f"Output leaked raw private probe: {probe}")


def _source_text(item: Mapping[str, Any]) -> str:
    return _text(item.get("text")) or _text(item.get("excerpt"))


def _normalize_sources(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for index, item_any in enumerate(_list(payload.get("source_items")), start=1):
        item = _dict(item_any)
        source_id = _public_id(_text(item.get("source_id"), f"src_{index:03d}"), f"src_{index:03d}")
        text = _source_text(item)
        if not text:
            raise WorkBuddyInlineError(f"source_items[{index - 1}] requires text or excerpt.")
        sources.append(
            {
                "source_id": source_id,
                "title": _text(item.get("title"), f"Source {index}"),
                "source_type": _text(item.get("source_type"), "workbuddy_context"),
                "reference": _text(item.get("reference"), f"workbuddy://source/{source_id}"),
                "locator": _text(item.get("locator"), f"item-{index}"),
                "text": text,
                "excerpt_hash": sha256_text(text[:2000]),
            }
        )
    if not sources:
        raise WorkBuddyInlineError("At least one source_items entry is required.")
    return sources


def _normalize_evidence_refs(
    refs_any: Any,
    *,
    source_ids: set[str],
    path: str,
    required: bool,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for index, ref_any in enumerate(_list(refs_any), start=1):
        ref = _dict(ref_any)
        source_id = _text(ref.get("source_id"))
        if source_id not in source_ids:
            raise WorkBuddyInlineError(f"{path}[{index - 1}] references unknown source_id: {source_id}")
        excerpt = _text(ref.get("excerpt"))
        quote_hash = _text(ref.get("quote_hash"))
        if excerpt:
            expected_hash = "sha256:" + _hash_text(excerpt)
            if quote_hash and quote_hash != expected_hash:
                raise WorkBuddyInlineError(f"{path}[{index - 1}] quote_hash does not match excerpt.")
            quote_hash = expected_hash
        refs.append(
            {
                "source_id": source_id,
                "locator": _dict(ref.get("locator")) or {"type": "unknown", "value": _text(ref.get("locator"), "n/a")},
                "quote_hash": quote_hash or "sha256:" + _hash_text(f"{source_id}:{index}"),
            }
        )
    if required and not refs:
        raise WorkBuddyInlineError(f"{path} requires at least one evidence ref.")
    return refs


def _normalize_claims(claims_any: Any, *, source_ids: set[str], path: str) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for index, claim_any in enumerate(_list(claims_any), start=1):
        claim = _dict(claim_any)
        claim_type = _text(claim.get("claim_type"), "source_bound")
        if claim_type not in {"source_bound", "factual", "pedagogical", "analogy", "user_profile_based"}:
            raise WorkBuddyInlineError(f"{path}[{index - 1}] has unsupported claim_type: {claim_type}")
        text = _text(claim.get("text"))
        if not text:
            raise WorkBuddyInlineError(f"{path}[{index - 1}] requires text.")
        evidence_required = claim_type in {"source_bound", "factual"}
        claims.append(
            {
                "claim_id": _public_id(_text(claim.get("claim_id"), f"{path}-{index}"), f"claim_{index:03d}"),
                "claim_type": claim_type,
                "text": text,
                "evidence_refs": _normalize_evidence_refs(
                    claim.get("evidence_refs"),
                    source_ids=source_ids,
                    path=f"{path}[{index - 1}].evidence_refs",
                    required=evidence_required,
                ),
            }
        )
    return claims


def _normalize_teaching(payload: Mapping[str, Any], *, source_ids: set[str]) -> dict[str, Any]:
    teaching = _dict(payload.get("workbuddy_teaching"))
    overview = _normalize_claims(teaching.get("overview"), source_ids=source_ids, path="workbuddy_teaching.overview")
    glossary: list[dict[str, Any]] = []
    for index, item_any in enumerate(_list(teaching.get("glossary")), start=1):
        item = _dict(item_any)
        term = _text(item.get("term"))
        explanation = _text(item.get("explanation"))
        if not term or not explanation:
            raise WorkBuddyInlineError(f"workbuddy_teaching.glossary[{index - 1}] requires term and explanation.")
        claim_type = _text(item.get("claim_type"), "source_bound")
        glossary.append(
            {
                "term": term,
                "explanation": explanation,
                "technical_definition": _text(item.get("technical_definition")),
                "example": _text(item.get("example")),
                "claim_type": claim_type,
                "evidence_refs": _normalize_evidence_refs(
                    item.get("evidence_refs"),
                    source_ids=source_ids,
                    path=f"workbuddy_teaching.glossary[{index - 1}].evidence_refs",
                    required=claim_type in {"source_bound", "factual"},
                ),
            }
        )
    if not overview and not glossary:
        raise WorkBuddyInlineError("workbuddy_teaching requires overview claims or glossary terms.")
    return {"overview": overview, "glossary": glossary}


def _normalize_quiz(payload: Mapping[str, Any], *, source_ids: set[str]) -> list[dict[str, Any]]:
    quiz = _dict(payload.get("workbuddy_quiz"))
    items: list[dict[str, Any]] = []
    for index, item_any in enumerate(_list(quiz.get("items")), start=1):
        item = _dict(item_any)
        item_id = _public_id(_text(item.get("item_id"), f"q_{index:03d}"), f"q_{index:03d}")
        item_type = _text(item.get("item_type"), "source_bound")
        prompt = _text(item.get("prompt"))
        rubric = _text(item.get("rubric"))
        if not prompt or not rubric:
            raise WorkBuddyInlineError(f"workbuddy_quiz.items[{index - 1}] requires prompt and rubric.")
        items.append(
            {
                "item_id": item_id,
                "item_type": item_type,
                "prompt": prompt,
                "rubric": rubric,
                "expected_points": [str(value) for value in _list(item.get("expected_points"))],
                "evidence_refs": _normalize_evidence_refs(
                    item.get("evidence_refs"),
                    source_ids=source_ids,
                    path=f"workbuddy_quiz.items[{index - 1}].evidence_refs",
                    required=item_type in {"source_bound", "factual"},
                ),
            }
        )
    if not items:
        raise WorkBuddyInlineError("workbuddy_quiz.items requires at least one item.")
    return items


def _normalize_answers(payload: Mapping[str, Any]) -> dict[str, str]:
    answer = _dict(payload.get("workbuddy_answer"))
    values = answer.get("answers")
    if isinstance(values, Mapping):
        return {str(key): _text(value) for key, value in values.items() if _text(value)}
    item_id = _text(answer.get("item_id"))
    text = _text(answer.get("text"))
    return {item_id: text} if item_id and text else {}


def _normalize_grading(
    payload: Mapping[str, Any],
    *,
    quiz_ids: set[str],
    source_ids: set[str],
) -> list[dict[str, Any]]:
    grading = _dict(payload.get("workbuddy_grading"))
    results: list[dict[str, Any]] = []
    for index, item_any in enumerate(_list(grading.get("results")), start=1):
        item = _dict(item_any)
        item_id = _text(item.get("item_id"))
        if item_id not in quiz_ids:
            raise WorkBuddyInlineError(f"workbuddy_grading.results[{index - 1}] references unknown item_id: {item_id}")
        score = item.get("score")
        if not isinstance(score, (int, float)) or not 0 <= float(score) <= 1:
            raise WorkBuddyInlineError(f"workbuddy_grading.results[{index - 1}].score must be between 0 and 1.")
        feedback = _text(item.get("feedback"))
        if not feedback:
            raise WorkBuddyInlineError(f"workbuddy_grading.results[{index - 1}] requires feedback.")
        results.append(
            {
                "item_id": item_id,
                "score": round(float(score), 4),
                "feedback": feedback,
                "improvement": _text(item.get("improvement")),
                "evidence_refs": _normalize_evidence_refs(
                    item.get("evidence_refs"),
                    source_ids=source_ids,
                    path=f"workbuddy_grading.results[{index - 1}].evidence_refs",
                    required=False,
                ),
            }
        )
    return results


def _normalize_agent_evidence(payload: Mapping[str, Any], *, require_platform_agent: bool) -> dict[str, Any]:
    evidence = _dict(payload.get("agent_evidence"))
    generated = evidence.get("generated_by_platform_agent") is True
    platform_agent = _text(evidence.get("platform_agent"), "deterministic-fixture")
    model_label = _text(evidence.get("model_label"), "deterministic-fixture")
    evidence_mode = _text(evidence.get("mode"), "deterministic_fixture")
    lowered_label = model_label.lower()
    lowered_mode = evidence_mode.lower()

    if require_platform_agent:
        if not generated:
            raise WorkBuddyInlineError(
                "Real WorkBuddy run requires agent_evidence.generated_by_platform_agent=true. "
                "Use WorkBuddy/Kimi to create workbuddy_teaching, workbuddy_quiz, and workbuddy_grading first; "
                "use `demo` only for deterministic verifier checks."
            )
        if not model_label or any(marker in lowered_label for marker in ("fake", "deterministic", "dry-run", "demo")):
            raise WorkBuddyInlineError(
                "Real WorkBuddy run requires agent_evidence.model_label to name the platform-owned model "
                "or model family used by WorkBuddy/Kimi, not a deterministic demo label."
            )
        if lowered_mode in {"deterministic_fixture", "fake", "dry_run", "demo"}:
            raise WorkBuddyInlineError("Real WorkBuddy run cannot use deterministic/demo agent_evidence.mode.")

    return {
        "generated_by_platform_agent": generated,
        "platform_agent": platform_agent,
        "model_label": model_label,
        "mode": evidence_mode,
        "attestation": "platform_provided" if generated else "deterministic_fixture_only",
        "study_anything_called_model": False,
        "model_invocation_proven_by_study_anything": False,
    }


def _word_count(value: str) -> int:
    return len([part for part in re.split(r"\s+", value.strip()) if part])


def _assert_text_is_not_placeholder(value: str, path: str) -> None:
    lowered = value.lower()
    for phrase in LOW_QUALITY_PHRASES:
        if phrase in lowered:
            raise WorkBuddyInlineError(f"{path} looks like placeholder teaching text: {phrase}")


def _assert_teaching_quality(
    teaching: Mapping[str, Any],
    quiz_items: Iterable[Mapping[str, Any]],
    grading: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    overview = [_dict(item) for item in _list(teaching.get("overview"))]
    glossary = [_dict(item) for item in _list(teaching.get("glossary"))]
    quiz = [_dict(item) for item in quiz_items]
    grading_items = [_dict(item) for item in grading]

    if len(overview) + len(glossary) < 2:
        raise WorkBuddyInlineError("WorkBuddy teaching quality gate requires at least two teaching units.")
    for index, claim in enumerate(overview):
        text = _text(claim.get("text"))
        _assert_text_is_not_placeholder(text, f"workbuddy_teaching.overview[{index}].text")
        if claim.get("claim_type") in {"source_bound", "factual"} and _word_count(text) < 8:
            raise WorkBuddyInlineError(f"workbuddy_teaching.overview[{index}].text is too thin for source-bound teaching.")
    for index, item in enumerate(glossary):
        explanation = _text(item.get("explanation"))
        technical_definition = _text(item.get("technical_definition"))
        example = _text(item.get("example"))
        _assert_text_is_not_placeholder(explanation, f"workbuddy_teaching.glossary[{index}].explanation")
        if _word_count(explanation) < 10:
            raise WorkBuddyInlineError(f"workbuddy_teaching.glossary[{index}].explanation is too thin.")
        if item.get("claim_type") in {"source_bound", "factual"} and _word_count(technical_definition) < 6:
            raise WorkBuddyInlineError(
                f"workbuddy_teaching.glossary[{index}].technical_definition is required for source-bound terms."
            )
        if example and _word_count(example) < 6:
            raise WorkBuddyInlineError(f"workbuddy_teaching.glossary[{index}].example is too thin.")
    for index, item in enumerate(quiz):
        prompt = _text(item.get("prompt"))
        rubric = _text(item.get("rubric"))
        _assert_text_is_not_placeholder(prompt, f"workbuddy_quiz.items[{index}].prompt")
        if _word_count(prompt) < 8 or _word_count(rubric) < 8:
            raise WorkBuddyInlineError(f"workbuddy_quiz.items[{index}] is too thin.")
    for index, item in enumerate(grading_items):
        feedback = _text(item.get("feedback"))
        _assert_text_is_not_placeholder(feedback, f"workbuddy_grading.results[{index}].feedback")
        if _word_count(feedback) < 10:
            raise WorkBuddyInlineError(f"workbuddy_grading.results[{index}].feedback is too thin.")

    return {
        "placeholder_phrases_rejected": True,
        "overview_count": len(overview),
        "glossary_count": len(glossary),
        "quiz_count": len(quiz),
        "grading_count": len(grading_items),
    }


def _mastery_from_grading(results: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    scores = [float(item["score"]) for item in results]
    average = sum(scores) / len(scores) if scores else 0.0
    if average >= 0.85:
        bloom = "apply"
        level = 2.0
    elif average >= 0.7:
        bloom = "understand"
        level = 1.0
    else:
        bloom = "remember"
        level = 0.3
    return {"level": level, "bloom": bloom, "average_score": round(average, 4)}


def _resolve_data_dir_strategy(data_dir: str | None = None, env: Mapping[str, str] | None = None) -> str:
    values = dict(env or {})
    if data_dir:
        return "explicit_parameter"
    if values.get("STUDY_ANYTHING_DATA_DIR"):
        return "study_anything_data_dir"
    if values.get("WORKBUDDY_DATA_DIR"):
        return "workbuddy_data_dir"
    if values.get("XDG_DATA_HOME"):
        return "xdg_data_home"
    return "workspace_dot_workbuddy"


def _source_refs(sources: Iterable[Mapping[str, Any]], privacy_mode: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for source in sources:
        record = {
            "source_id": source["source_id"],
            "title": source["title"],
            "source_type": source["source_type"],
            "reference": source["reference"],
            "locator": source["locator"],
            "excerpt_hash": source["excerpt_hash"],
        }
        if privacy_mode == "full_context":
            record["context_included"] = True
        elif privacy_mode == "excerpts_only":
            record["context_included"] = "bounded_excerpt_refs_only"
        else:
            record["context_included"] = False
        refs.append(record)
    return refs


def _build_markdown(output: Mapping[str, Any]) -> str:
    card = _dict(output.get("study_card"))
    mastery = _dict(output.get("mastery"))
    lines = [
        f"# {card.get('title', 'Study Anything Learning Card')}",
        "",
        f"- Session: `{output.get('session_ref')}`",
        f"- Privacy mode: `{output.get('privacy_mode')}`",
        f"- Mastery: `{mastery.get('level')}` / `{mastery.get('bloom')}`",
        "",
        "## Overview",
    ]
    for claim in _list(card.get("overview")):
        claim = _dict(claim)
        lines.append(f"- {claim.get('text')} (`{claim.get('claim_type')}`)")
    lines.extend(["", "## Glossary"])
    for item in _list(card.get("glossary")):
        item = _dict(item)
        lines.append(f"- **{item.get('term')}**: {item.get('explanation')}")
    lines.extend(["", "## Quiz"])
    for item in _list(output.get("quiz_items")):
        item = _dict(item)
        lines.append(f"- `{item.get('item_id')}` {item.get('prompt')}")
    lines.extend(["", "## Grading"])
    for item in _list(output.get("grading_summary")):
        item = _dict(item)
        lines.append(f"- `{item.get('item_id')}` score={item.get('score')}: {item.get('feedback')}")
    lines.extend(["", "## Next Steps"])
    for item in _list(output.get("next_steps")):
        lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def build_workbuddy_learning_package(
    payload: Mapping[str, Any],
    *,
    data_dir: str | None = None,
    env: Mapping[str, str] | None = None,
    require_platform_agent: bool = False,
    proxy_env_removed: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build a credential-free source-bound package from WorkBuddy model output."""

    if payload.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise WorkBuddyInlineError(f"schema_version must be {INPUT_SCHEMA_VERSION}.")
    _assert_no_secret_like_values(payload)

    phase = _text(payload.get("phase"), "complete")
    if phase not in SUPPORTED_PHASES:
        raise WorkBuddyInlineError(f"Unsupported phase: {phase}.")
    privacy_mode = _text(payload.get("privacy_mode"), DEFAULT_PRIVACY_MODE)
    if privacy_mode not in SUPPORTED_PRIVACY_MODES:
        raise WorkBuddyInlineError(f"Unsupported privacy_mode: {privacy_mode}.")

    topic = _text(payload.get("topic"), "Untitled WorkBuddy Learning Session")
    learner_profile = _dict(payload.get("learner_profile"))
    sources = _normalize_sources(payload)
    source_ids = {source["source_id"] for source in sources}
    teaching = _normalize_teaching(payload, source_ids=source_ids)
    quiz_items = _normalize_quiz(payload, source_ids=source_ids)
    quiz_ids = {item["item_id"] for item in quiz_items}
    answers = _normalize_answers(payload)
    grading = _normalize_grading(payload, quiz_ids=quiz_ids, source_ids=source_ids)
    mastery = _mastery_from_grading(grading)
    agent_evidence = _normalize_agent_evidence(payload, require_platform_agent=require_platform_agent)
    quality_gate = _assert_teaching_quality(teaching, quiz_items, grading)

    session_ref = _text(payload.get("session_ref")) or "wb-" + _hash_text(topic)[:12]
    state = new_session(
        user_id=_text(learner_profile.get("learner_ref"), "workbuddy-user"),
        track=_text(payload.get("track"), "WORKBUDDY"),
        workspace_id=_text(payload.get("workspace_ref"), "workbuddy-inline"),
    )
    combined_source = "\n\n---\n\n".join(
        f"{source['title']}\nReference: {source['reference']}\nLocator: {source['locator']}\n\n{source['text']}"
        for source in sources
    )
    state = submit_reading(
        state,
        source_type="workbuddy_context_bundle",
        reference=f"workbuddy://inline/{session_ref}",
        title=topic,
        text=combined_source,
    )
    state = replace(
        state,
        session_id=session_ref,
        teaching_layers=[
            {"layer": "overview", "content": teaching["overview"], "agent": {"provider_id": "workbuddy-owned-agent"}},
            {"layer": "glossary", "content": teaching["glossary"], "agent": {"provider_id": "workbuddy-owned-agent"}},
        ],
        quiz_items=[
            QuizItem(
                item_id=item["item_id"],
                prompt=item["prompt"],
                source_ref=sources[0]["reference"],
                excerpt_hash=sources[0]["excerpt_hash"],
                rubric=item["rubric"],
            )
            for item in quiz_items
        ],
        mastery=Mastery(level=float(mastery["level"]), bloom=str(mastery["bloom"])),
    )
    if answers:
        state = submit_answers(
            state,
            [
                Answer(item_id=item_id, text=answer_text)
                for item_id, answer_text in answers.items()
                if item_id in quiz_ids
            ],
        )
    if grading:
        state = replace(
            state,
            grading_results=[
                GradingResult(
                    item_id=item["item_id"],
                    score=float(item["score"]),
                    feedback=item["feedback"],
                    reward=float(item["score"]),
                )
                for item in grading
            ],
            stage="workbuddy_inline_completed",
        )
    state = append_event(
        state,
        event_type="workbuddy_inline.package_built",
        node="workbuddy_inline_adapter",
        payload={
            "phase": phase,
            "privacy_mode": privacy_mode,
            "source_count": len(sources),
            "quiz_count": len(quiz_items),
            "grading_count": len(grading),
        },
    )

    output: dict[str, Any] = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "package_type": "credential-free-source-bound-learning-package",
        "generated_at_utc": utc_now(),
        "phase": phase,
        "privacy_mode": privacy_mode,
        "session_ref": session_ref,
        "runtime": {
            "mode": "workbuddy_inline",
            "http_server_started": False,
            "localhost_required": False,
            "background_process_required": False,
            "model_calls_performed_by_study_anything": False,
            "data_dir_strategy": _resolve_data_dir_strategy(data_dir=data_dir, env=env),
            "proxy_env_sanitized": True,
            "proxy_env_removed_count": len(list(proxy_env_removed or [])),
        },
        "agent_evidence": agent_evidence,
        "quality_gate": quality_gate,
        "study_card": {
            "title": topic,
            "learner_profile": {
                "role": _text(learner_profile.get("role")),
                "goal": _text(learner_profile.get("goal")),
                "experience_level": _text(learner_profile.get("experience_level")),
            },
            "overview": teaching["overview"],
            "glossary": teaching["glossary"],
        },
        "source_refs": _source_refs(sources, privacy_mode),
        "quiz_items": quiz_items,
        "answer_refs": [
            {
                "item_id": item_id,
                "answer_hash": "sha256:" + _hash_text(answer_text),
                "raw_answer_included": False,
            }
            for item_id, answer_text in sorted(answers.items())
        ],
        "grading_summary": grading,
        "mastery": mastery,
        "exports": {
            "markdown": True,
            "obsidian_markdown": True,
            "notebooklm_context_package": {
                "schema_version": "notebooklm-context-package-v1",
                "source_refs": [source["source_id"] for source in sources],
                "raw_source_included": privacy_mode == "full_context",
                "recommended_use": "Import the markdown summary and source references; keep private source files local.",
            },
        },
        "audit": {
            "state_stage": state.stage,
            "event_count": len(state.events),
            "raw_source_in_output": False,
            "raw_answer_in_output": False,
            "real_model_keys_in_output": False,
            "workbuddy_owns_model_credentials": True,
            "http_fallback_available": True,
            "mcp_runtime_shipped": False,
        },
        "next_steps": [
            "Use WorkBuddy to ask the learner the quiz item conversationally.",
            "Keep session_ref in hidden WorkBuddy context; do not ask the learner to manage it.",
            "Export the markdown summary to Obsidian or NotebookLM when the learner asks.",
        ],
    }
    output["exports"]["markdown_text"] = _build_markdown(output)
    _assert_public_output_safe(output)
    return output
