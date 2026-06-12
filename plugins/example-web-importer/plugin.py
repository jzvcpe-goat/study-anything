"""Example web importer plugin.

The alpha runtime validates and discovers manifests only. This module shows the
shape a platform Agent can use after it fetches or clips a user-approved web
source outside Study Anything.
"""

from __future__ import annotations

from typing import Dict, Optional


def build_context_package(
    *,
    url: str,
    title: str,
    excerpt: str,
    locator: Optional[str] = None,
    language: str = "zh",
) -> Dict[str, object]:
    return {
        "schema_version": "learning-context-package-v1",
        "package_id": "example-web-import",
        "title": title,
        "reference": url,
        "producer": "example-web-importer",
        "language": language,
        "items": [
            {
                "source_type": "web",
                "reference": url,
                "title": title,
                "text": excerpt,
                "locator": locator,
                "metadata": {
                    "importer_plugin": "example-web-importer",
                    "user_approved_source": True,
                },
            }
        ],
    }
