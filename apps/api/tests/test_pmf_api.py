from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.pmf import LocalPmfInterestStore
from study_anything.core.plugin_registry import PluginRegistry
from study_anything.core.store import InMemorySessionStore
from study_anything.core.workflow import Answer, Mastery, new_session


class PmfApiTests(unittest.TestCase):
    def _client(self, store: InMemorySessionStore, interest_store: LocalPmfInterestStore) -> tuple[TestClient, ExitStack]:
        stack = ExitStack()
        stack.enter_context(patch.object(api_main, "store", store))
        stack.enter_context(patch.object(api_main, "plugins", PluginRegistry([])))
        stack.enter_context(patch.object(api_main, "pmf_interest_store", interest_store))
        return TestClient(api_main.create_app()), stack

    def test_pmf_metrics_returns_aggregate_counts_only(self) -> None:
        store = InMemorySessionStore()
        now = datetime(2026, 6, 4, tzinfo=timezone.utc).isoformat()
        state = replace(
            new_session("api-pmf-user"),
            stage="completed",
            answers=[Answer(item_id="q1", text="Private API answer")],
            mastery=Mastery(level=0.5, bloom="understand"),
            insights=["Private API insight"],
            updated_at=now,
        )
        store.save(state)
        with tempfile.TemporaryDirectory() as tmpdir:
            client, stack = self._client(store, LocalPmfInterestStore(Path(tmpdir) / "pmf.json"))
            with stack, client:
                response = client.get("/v1/metrics/pmf")

        body = response.json()
        serialized = response.text
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["schema_version"], "pmf-v1")
        self.assertEqual(body["sessions"]["completed"], 1)
        self.assertEqual(body["learning"]["total_answers"], 1)
        self.assertTrue(body["privacy"]["local_only"])
        self.assertNotIn("api-pmf-user", serialized)
        self.assertNotIn("Private API", serialized)

    def test_pmf_interest_api_stores_local_hashed_intent(self) -> None:
        store = InMemorySessionStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            interest_store = LocalPmfInterestStore(Path(tmpdir) / "pmf.json")
            client, stack = self._client(store, interest_store)
            with stack, client:
                created = client.post(
                    "/v1/pmf/interest",
                    json={
                        "user_id": "waitlist-user",
                        "services": ["neural_sync", "catalyst"],
                        "contact": "person@example.com",
                        "comment": "Call me when hosted sync exists.",
                        "source": "web-ui",
                        "locale": "zh",
                    },
                )
                summary = client.get("/v1/pmf/summary")
                metrics = client.get("/v1/metrics/pmf")
            persisted = Path(tmpdir, "pmf.json").read_text(encoding="utf-8")

        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()["contact_provided"])
        self.assertNotIn("person@example.com", created.text)
        self.assertEqual(summary.json()["total"], 1)
        self.assertEqual(metrics.json()["signals"]["hosted_waitlist_count"], 1)
        self.assertNotIn("person@example.com", persisted)
        self.assertNotIn("Call me", persisted)

    def test_pmf_interest_api_rejects_unknown_services(self) -> None:
        store = InMemorySessionStore()
        with tempfile.TemporaryDirectory() as tmpdir:
            client, stack = self._client(store, LocalPmfInterestStore(Path(tmpdir) / "pmf.json"))
            with stack, client:
                response = client.post("/v1/pmf/interest", json={"services": ["bogus"]})

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
