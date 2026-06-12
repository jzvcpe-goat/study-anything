"""Example exporter plugin.

Real plugins will be loaded through the plugin registry in a later alpha. This
file demonstrates the expected shape without requiring runtime imports.
"""

from __future__ import annotations

from typing import Mapping


def export_session(session: Mapping[str, object]) -> str:
    title = session.get("session_id", "unknown-session")
    mastery = session.get("mastery", {})
    return f"# Study Anything Export\n\nSession: {title}\n\nMastery: {mastery}\n"


def export_second_brain_handoff(handoff: Mapping[str, object]) -> str:
    obsidian = handoff.get("obsidian", {})
    if not isinstance(obsidian, Mapping):
        obsidian = {}
    filename = obsidian.get("filename", "study-anything-note.md")
    markdown = obsidian.get("markdown", "")
    return f"<!-- Study Anything second-brain export: {filename} -->\n\n{markdown}"
