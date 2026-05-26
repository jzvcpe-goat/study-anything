"""LangGraph adapter boundary.

The alpha workflow is deterministic and dependency-light for OSS smoke tests.
This module centralizes the future production adapter so API contracts do not
change when the executor swaps to LangGraph with Postgres checkpointing.
"""

from __future__ import annotations

from typing import Any

from .workflow import LearningWorkflow


LANGGRAPH_NODE_ORDER = LearningWorkflow.NODE_ORDER


def langgraph_available() -> bool:
    try:
        import langgraph  # noqa: F401
    except ImportError:
        return False
    return True


def build_langgraph_placeholder() -> Any:
    """Return a LangGraph placeholder or raise a clear alpha-stage error."""

    if not langgraph_available():
        raise RuntimeError("LangGraph is not installed in this environment.")
    raise NotImplementedError(
        "The v0.1 alpha uses the deterministic executor. The LangGraph "
        "production adapter is staged for v0.2."
    )

