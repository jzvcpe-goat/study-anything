"""Example importer plus enrichment plugin.

This plugin is intentionally small and deterministic so authors can copy its
shape. Platform Agents still gather external context; this plugin only packages
bounded excerpts and builds a redacted micro-lesson artifact.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional


def build_context_package(
    *,
    note_reference: str,
    title: str,
    markdown_excerpt: str,
    key_terms: Optional[Iterable[str]] = None,
    language: str = "zh",
) -> Dict[str, object]:
    terms = list(key_terms or [])
    return {
        "schema_version": "learning-context-package-v1",
        "package_id": "example-enrichment-import",
        "title": title,
        "reference": note_reference,
        "producer": "example-enrichment-importer",
        "language": language,
        "items": [
            {
                "source_type": "markdown_note",
                "reference": note_reference,
                "title": title,
                "text": markdown_excerpt,
                "locator": "note-selection",
                "provenance": {
                    "collector": "example-enrichment-importer",
                    "capture_method": "markdown_excerpt",
                    "source_owner": "user",
                },
                "redaction_policy": "reference_only",
                "metadata": {
                    "importer_plugin": "example-enrichment-importer",
                    "key_terms": terms,
                },
            }
        ],
    }


def build_enrichment_artifact(
    *,
    title: str,
    key_terms: Optional[Iterable[str]] = None,
    language: str = "zh",
) -> Dict[str, object]:
    terms = list(key_terms or [])
    term_lines = "\n".join(f"- {term}: 待学习者用自己的话解释" for term in terms) or "- 核心概念: 待补充"
    markdown = f"# {title}\n\n## 专业名词\n\n{term_lines}\n\n## 自测\n\n用一个具体例子解释本课最重要的概念。"
    html_terms = "".join(f"<li><strong>{term}</strong>: 待学习者用自己的话解释</li>" for term in terms)
    if not html_terms:
        html_terms = "<li><strong>核心概念</strong>: 待补充</li>"
    return {
        "schema_version": "learning-enrichment-artifact-v1",
        "producer": "example-enrichment-importer",
        "language": language,
        "title": title,
        "markdown": markdown,
        "html": f"<article><h1>{title}</h1><h2>专业名词</h2><ul>{html_terms}</ul></article>",
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_metadata_included": False,
        },
    }
