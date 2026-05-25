"""Example exporter plugin.

Real plugins will be loaded through the plugin registry in a later alpha. This
file demonstrates the expected shape without requiring runtime imports.
"""

from __future__ import annotations

from typing import Mapping


def export_session(session: Mapping[str, object]) -> str:
    title = session.get("session_id", "unknown-session")
    mastery = session.get("mastery", {})
    return f"# Neural Console Export\n\nSession: {title}\n\nMastery: {mastery}\n"

