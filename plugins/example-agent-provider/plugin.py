"""Example agent provider plugin.

The alpha runtime validates and discovers manifests only. This module shows the
shape a future plugin loader can call to register a user-owned HTTP agent.
"""

from __future__ import annotations

from typing import Dict, List


CAPABILITIES: List[str] = [
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
    "source.verify",
    "memory.retrieve",
    "embedding.create",
]


def provider_template() -> Dict[str, object]:
    return {
        "kind": "http_agent",
        "label": "Example HTTP Agent",
        "endpoint": "http://host.docker.internal:8787",
        "capabilities": CAPABILITIES,
        "metadata": {
            "plugin_id": "example-agent-provider",
            "secret_storage": "user-agent-only",
        },
    }
