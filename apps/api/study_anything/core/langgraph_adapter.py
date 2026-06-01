"""LangGraph execution and checkpoint boundaries for the learning workflow."""

from __future__ import annotations

from typing import Any, Callable, Optional, TypedDict

from .agent_registry import AgentRouter
from .events import StudyEvent
from .knowledge_graph import KnowledgeGraphSink
from .tracing import TraceSink
from .workflow import (
    Answer,
    GradingResult,
    HitlInterrupt,
    LearningState,
    LearningWorkflow,
    Mastery,
    QuizItem,
    ReadingSource,
)


LANGGRAPH_NODE_ORDER = LearningWorkflow.NODE_ORDER


class LangGraphState(TypedDict):
    state: LearningState


def _checkpoint_serializer() -> Any:
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    return JsonPlusSerializer(
        allowed_msgpack_modules=[
            Answer,
            GradingResult,
            HitlInterrupt,
            LearningState,
            Mastery,
            QuizItem,
            ReadingSource,
            StudyEvent,
        ]
    )


def langgraph_available() -> bool:
    try:
        import langgraph  # noqa: F401
    except ImportError:
        return False
    return True


class LangGraphCheckpointResource:
    """Own a LangGraph checkpointer and close Postgres connections cleanly."""

    def __init__(self, *, backend: str = "memory", database_url: Optional[str] = None) -> None:
        self.backend = backend.strip().lower()
        self._manager: Optional[Any] = None
        if self.backend == "memory":
            from langgraph.checkpoint.memory import InMemorySaver

            self.saver = InMemorySaver(serde=_checkpoint_serializer())
        elif self.backend == "postgres":
            if not database_url:
                raise ValueError("LANGGRAPH_CHECKPOINTER=postgres requires DATABASE_URL.")
            from langgraph.checkpoint.postgres import PostgresSaver

            self._manager = PostgresSaver.from_conn_string(database_url)
            self.saver = self._manager.__enter__()
            self.saver.serde = _checkpoint_serializer()
            try:
                self.saver.setup()
            except Exception:
                self.close()
                raise
        else:
            raise ValueError(
                f"Unsupported LANGGRAPH_CHECKPOINTER={backend}. Use memory or postgres."
            )

    def close(self) -> None:
        if self._manager is not None:
            manager, self._manager = self._manager, None
            manager.__exit__(None, None, None)


class LangGraphLearningWorkflow(LearningWorkflow):
    """Run existing business nodes through a compiled LangGraph StateGraph."""

    engine = "langgraph"

    def __init__(
        self,
        agent_router: AgentRouter,
        trace_sink: Optional[TraceSink] = None,
        knowledge_graph_sink: Optional[KnowledgeGraphSink] = None,
        *,
        checkpointer: Optional[Any] = None,
    ) -> None:
        super().__init__(
            agent_router,
            trace_sink=trace_sink,
            knowledge_graph_sink=knowledge_graph_sink,
        )
        if not langgraph_available():
            raise RuntimeError("LangGraph is not installed in this environment.")
        if checkpointer is None:
            checkpointer = LangGraphCheckpointResource(backend="memory").saver
        self.graph = self._build_graph(checkpointer)

    def run(self, state: LearningState) -> LearningState:
        result = self.graph.invoke(
            {"state": state},
            config={"configurable": {"thread_id": state.session_id}},
        )
        return result["state"]

    def _build_graph(self, checkpointer: Any) -> Any:
        from langgraph.graph import END, START, StateGraph

        builder = StateGraph(LangGraphState)
        for index, node_name in enumerate(self.NODE_ORDER):
            next_node = self.NODE_ORDER[index + 1] if index + 1 < len(self.NODE_ORDER) else END
            builder.add_node(node_name, self._invoke_node(node_name))
            if index == 0:
                builder.add_edge(START, node_name)
            builder.add_conditional_edges(node_name, self._route_after(node_name, next_node))
        return builder.compile(checkpointer=checkpointer, name="study-anything-learning-loop")

    def _invoke_node(self, node_name: str) -> Callable[[LangGraphState], LangGraphState]:
        def invoke(values: LangGraphState) -> LangGraphState:
            return {"state": getattr(self, node_name)(values["state"])}

        return invoke

    @staticmethod
    def _route_after(node_name: str, next_node: str) -> Callable[[LangGraphState], str]:
        from langgraph.graph import END

        def route(values: LangGraphState) -> str:
            state = values["state"]
            if state.hitl_interrupts and state.hitl_interrupts[-1].status == "open":
                return END
            if state.stage in {"awaiting_answers", "completed", "discarded"}:
                if node_name in {"quiz_generator", "incubation_detector"}:
                    return END
            return next_node

        return route


def build_learning_workflow(
    agent_router: AgentRouter,
    trace_sink: Optional[TraceSink] = None,
    knowledge_graph_sink: Optional[KnowledgeGraphSink] = None,
    *,
    engine: str = "langgraph",
    checkpointer: Optional[Any] = None,
) -> LearningWorkflow:
    engine_value = engine.strip().lower()
    if engine_value == "langgraph":
        return LangGraphLearningWorkflow(
            agent_router,
            trace_sink=trace_sink,
            knowledge_graph_sink=knowledge_graph_sink,
            checkpointer=checkpointer,
        )
    if engine_value == "deterministic":
        return LearningWorkflow(
            agent_router,
            trace_sink=trace_sink,
            knowledge_graph_sink=knowledge_graph_sink,
        )
    raise ValueError(f"Unsupported WORKFLOW_ENGINE={engine}. Use langgraph or deterministic.")
