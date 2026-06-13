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

    def test_pmf_export_requires_consent_and_returns_shareable_aggregate(self) -> None:
        store = InMemorySessionStore()
        state = replace(
            new_session("export-user"),
            stage="completed",
            answers=[Answer(item_id="q1", text="Private export answer")],
            mastery=Mastery(level=0.5, bloom="understand"),
            insights=["Private export insight"],
        )
        store.save(state)
        with tempfile.TemporaryDirectory() as tmpdir:
            interest_store = LocalPmfInterestStore(Path(tmpdir) / "pmf.json")
            interest_store.record(
                user_id="export-user",
                services=["neural_publish"],
                contact="export@example.com",
                comment="Private export comment",
                source="web-ui",
            )
            client, stack = self._client(store, interest_store)
            with stack, client:
                blocked = client.post("/v1/pmf/export", json={"destination": "self_archive"})
                exported = client.post(
                    "/v1/pmf/export",
                    json={
                        "consent_to_share": True,
                        "destination": "hosted_waitlist",
                        "note": "Private export note",
                    },
                )

        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(exported.status_code, 200)
        body = exported.json()
        serialized = exported.text
        self.assertEqual(body["schema_version"], "pmf-export-v1")
        self.assertEqual(body["destination"], "hosted_waitlist")
        self.assertEqual(body["metrics"]["sessions"]["completed"], 1)
        self.assertEqual(body["hosted_interest"]["services"]["neural_publish"], 1)
        self.assertTrue(body["privacy"]["shareable_after_consent"])
        self.assertNotIn("export-user", serialized)
        self.assertNotIn("export@example.com", serialized)
        self.assertNotIn("Private export", serialized)
        self.assertNotIn("contact_hash", body["hosted_interest"])

    def test_adoption_telemetry_and_pmf_readiness_routes_are_redacted(self) -> None:
        store = InMemorySessionStore()
        state = replace(
            new_session("telemetry-user"),
            stage="completed",
            answers=[Answer(item_id="q1", text="Private telemetry answer")],
            mastery=Mastery(level=0.6, bloom="apply"),
            insights=["Private telemetry insight"],
        )
        store.save(state)
        with tempfile.TemporaryDirectory() as tmpdir:
            interest_store = LocalPmfInterestStore(Path(tmpdir) / "pmf.json")
            interest_store.record(
                user_id="telemetry-user",
                services=["neural_sync"],
                contact="telemetry@example.com",
                comment="Private telemetry comment",
                source="skill-mode",
            )
            client, stack = self._client(store, interest_store)
            with stack, client:
                telemetry = client.get("/v1/adoption/telemetry")
                readiness = client.get("/v1/pmf/readiness")

        self.assertEqual(telemetry.status_code, 200)
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(telemetry.json()["schema_version"], "adoption-telemetry-v1")
        self.assertEqual(readiness.json()["schema_version"], "pmf-readiness-v1")
        self.assertTrue(telemetry.json()["privacy"]["aggregate_only"])
        self.assertFalse(telemetry.json()["collection"]["automatic_upload"])
        self.assertFalse(readiness.json()["commercial_boundary"]["sell_standalone_app_now"])
        serialized = telemetry.text + readiness.text
        self.assertNotIn("telemetry-user", serialized)
        self.assertNotIn("telemetry@example.com", serialized)
        self.assertNotIn("Private telemetry", serialized)


if __name__ == "__main__":
    unittest.main()
