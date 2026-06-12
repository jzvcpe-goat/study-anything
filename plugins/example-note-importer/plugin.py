"""Example Markdown and Obsidian importer plugin."""

from __future__ import annotations

from typing import Dict, Iterable, Optional


def build_context_package(
    *,
    note_reference: str,
    title: str,
    markdown_excerpt: str,
    obsidian_backlinks: Optional[Iterable[str]] = None,
    language: str = "zh",
) -> Dict[str, object]:
    backlinks = list(obsidian_backlinks or [])
    source_type = "obsidian_note" if backlinks else "markdown_note"
    return {
        "schema_version": "learning-context-package-v1",
        "package_id": "example-note-import",
        "title": title,
        "reference": note_reference,
        "producer": "example-note-importer",
        "language": language,
        "items": [
            {
                "source_type": source_type,
                "reference": note_reference,
                "title": title,
                "text": markdown_excerpt,
                "metadata": {
                    "importer_plugin": "example-note-importer",
                    "obsidian_backlinks": backlinks,
                },
            }
        ],
    }
