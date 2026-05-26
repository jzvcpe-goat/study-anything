"""Session stores used by the API and tests."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .events import StudyEvent
from .workflow import (
    Answer,
    GradingResult,
    HitlInterrupt,
    LearningState,
    Mastery,
    QuizItem,
    ReadingSource,
)


class InMemorySessionStore:
    backend = "memory"

    def __init__(self) -> None:
        self.sessions: Dict[str, LearningState] = {}

    def save(self, state: LearningState) -> LearningState:
        self.sessions[state.session_id] = state
        return state

    def get(self, session_id: str) -> LearningState:
        return self.sessions[session_id]

    def list_hitl(self) -> List[HitlInterrupt]:
        interrupts: List[HitlInterrupt] = []
        for state in self.sessions.values():
            interrupts.extend([item for item in state.hitl_interrupts if item.status == "open"])
        return interrupts

    def list_sessions(self) -> List[LearningState]:
        return list(self.sessions.values())


class JsonSessionStore:
    """Durable, file-backed store for self-host alpha deployments."""

    backend = "json"

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.session_dir = self.data_dir / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: LearningState) -> LearningState:
        target = self._path_for(state.session_id)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)
        return state

    def get(self, session_id: str) -> LearningState:
        target = self._path_for(session_id)
        if not target.exists():
            raise KeyError(session_id)
        return learning_state_from_dict(json.loads(target.read_text(encoding="utf-8")))

    def list_sessions(self) -> List[LearningState]:
        sessions: List[LearningState] = []
        for path in sorted(self.session_dir.glob("*.json")):
            sessions.append(learning_state_from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return sessions

    def list_hitl(self) -> List[HitlInterrupt]:
        interrupts: List[HitlInterrupt] = []
        for state in self.list_sessions():
            interrupts.extend([item for item in state.hitl_interrupts if item.status == "open"])
        return interrupts

    def _path_for(self, session_id: str) -> Path:
        if "/" in session_id or "\\" in session_id or session_id.startswith("."):
            raise KeyError(session_id)
        return self.session_dir / f"{session_id}.json"


class PostgresSessionStore:
    """Postgres-backed session store for self-host deployments."""

    backend = "postgres"

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is required for PostgresSessionStore.")
        self.database_url = database_url
        self._ensure_schema()

    def save(self, state: LearningState) -> LearningState:
        payload = json.dumps(asdict(state), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO study_anything_sessions
                    (session_id, user_hash, user_id, stage, payload, created_at, updated_at)
                VALUES
                    (%s, %s, %s, %s, %s::jsonb, now(), now())
                ON CONFLICT (session_id) DO UPDATE SET
                    user_hash = EXCLUDED.user_hash,
                    user_id = EXCLUDED.user_id,
                    stage = EXCLUDED.stage,
                    payload = EXCLUDED.payload,
                    updated_at = now()
                """,
                (state.session_id, state.user_hash, state.user_id, state.stage, payload),
            )
        return state

    def get(self, session_id: str) -> LearningState:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM study_anything_sessions WHERE session_id = %s",
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return learning_state_from_dict(payload)

    def list_sessions(self) -> List[LearningState]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM study_anything_sessions ORDER BY updated_at DESC"
            ).fetchall()
        sessions: List[LearningState] = []
        for row in rows:
            payload = row[0]
            if isinstance(payload, str):
                payload = json.loads(payload)
            sessions.append(learning_state_from_dict(payload))
        return sessions

    def list_hitl(self) -> List[HitlInterrupt]:
        interrupts: List[HitlInterrupt] = []
        for state in self.list_sessions():
            interrupts.extend([item for item in state.hitl_interrupts if item.status == "open"])
        return interrupts

    def _connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("Install psycopg to use SESSION_STORE=postgres.") from exc
        return psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS study_anything_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_hash TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS study_anything_sessions_updated_at_idx
                ON study_anything_sessions (updated_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS study_anything_sessions_user_hash_idx
                ON study_anything_sessions (user_hash)
                """
            )
            conn.execute(
                """
                DO $$
                BEGIN
                    IF to_regclass('public.neural_console_sessions') IS NOT NULL THEN
                        INSERT INTO study_anything_sessions
                            (session_id, user_hash, user_id, stage, payload, created_at, updated_at)
                        SELECT
                            session_id,
                            user_hash,
                            user_id,
                            stage,
                            payload,
                            created_at,
                            updated_at
                        FROM neural_console_sessions
                        ON CONFLICT (session_id) DO NOTHING;
                    END IF;
                END $$;
                """
            )


def create_session_store(
    *,
    data_dir: Path,
    database_url: Optional[str] = None,
    backend: str = "json",
) -> JsonSessionStore | PostgresSessionStore:
    backend_value = backend.strip().lower()
    if backend_value == "postgres":
        if not database_url:
            raise ValueError("SESSION_STORE=postgres requires DATABASE_URL.")
        return PostgresSessionStore(database_url)
    if backend_value == "json":
        return JsonSessionStore(data_dir)
    raise ValueError(f"Unsupported SESSION_STORE={backend}. Use json or postgres.")


def learning_state_from_dict(values: Dict[str, Any]) -> LearningState:
    source: Optional[ReadingSource] = None
    if values.get("source") is not None:
        source = ReadingSource(**values["source"])

    return LearningState(
        session_id=values["session_id"],
        user_id=values.get("user_id", "local-user"),
        user_hash=values["user_hash"],
        track=values.get("track", "ACADEMIC"),
        stage=values.get("stage", "created"),
        source=source,
        quiz_items=[QuizItem(**item) for item in values.get("quiz_items", [])],
        answers=[Answer(**item) for item in values.get("answers", [])],
        grading_results=[GradingResult(**item) for item in values.get("grading_results", [])],
        mastery=Mastery(**values.get("mastery", {})),
        insights=list(values.get("insights", [])),
        scribe_log=list(values.get("scribe_log", [])),
        hitl_interrupts=[HitlInterrupt(**item) for item in values.get("hitl_interrupts", [])],
        events=[StudyEvent(**item) for item in values.get("events", [])],
        audit_log=list(values.get("audit_log", [])),
        discarded=bool(values.get("discarded", False)),
        created_at=values.get("created_at"),
        updated_at=values.get("updated_at"),
    )
