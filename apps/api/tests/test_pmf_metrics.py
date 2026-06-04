from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from _path import ROOT  # noqa: F401

from study_anything.core.pmf import LocalPmfInterestStore, build_pmf_export, compute_pmf_metrics
from study_anything.core.plugin_registry import PluginStatus
from study_anything.core.workflow import Answer, Mastery, submit_reading, new_session


class PmfMetricsTests(unittest.TestCase):
    def test_metrics_aggregate_without_private_learning_content(self) -> None:
        now = datetime(2026, 6, 4, tzinfo=timezone.utc)
        first = submit_reading(
            new_session("learner-1"),
            source_type="local_text",
            reference="demo://private",
            title="Private Source Title",
            text="Private reading prose that must not appear in PMF metrics.",
        )
        first = replace(
            first,
            stage="completed",
            answers=[Answer(item_id="q1", text="Private answer")],
            mastery=Mastery(level=0.5, bloom="understand"),
            insights=["Private generated insight"],
            updated_at=now.isoformat(),
        )
        second = replace(new_session("learner-1"), stage="reading_submitted", updated_at=now.isoformat())

        metrics = compute_pmf_metrics(
            [first, second],
            [PluginStatus(None, "/tmp/plugin", "ready", "ok")],
            {"total": 1, "services": {"neural_sync": 1}, "local_only": True},
            now=now,
        )
        serialized = json.dumps(metrics, ensure_ascii=False)

        self.assertEqual(metrics["sessions"]["total"], 2)
        self.assertEqual(metrics["sessions"]["completed"], 1)
        self.assertEqual(metrics["sessions"]["completion_rate"], 0.5)
        self.assertEqual(metrics["learners"]["repeat"], 1)
        self.assertEqual(metrics["learning"]["average_mastery_delta"], 0.5)
        self.assertEqual(metrics["plugins"]["ready"], 1)
        self.assertEqual(metrics["signals"]["hosted_waitlist_count"], 1)
        self.assertNotIn("Private", serialized)
        self.assertNotIn("learner-1", serialized)

    def test_interest_store_hashes_contact_and_summarizes_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LocalPmfInterestStore(Path(tmpdir) / "pmf.json")

            intent = store.record(
                user_id="pmf-user",
                services=["neural_sync", "neural_publish"],
                contact="person@example.com",
                source="Private Source Name",
                locale="zh",
                comment="I want hosted sync.",
            )
            summary = store.summary()
            persisted = Path(tmpdir, "pmf.json").read_text(encoding="utf-8")

        self.assertTrue(intent.public_dict()["contact_provided"])
        self.assertEqual(intent.public_dict()["contact_type"], "email")
        self.assertEqual(intent.public_dict()["source"], "api")
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["services"]["neural_sync"], 1)
        self.assertEqual(summary["with_comment"], 1)
        self.assertNotIn("person@example.com", persisted)
        self.assertNotIn("I want hosted sync", persisted)

    def test_interest_store_rejects_unknown_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LocalPmfInterestStore(Path(tmpdir) / "pmf.json")

            with self.assertRaises(ValueError):
                store.record(user_id="pmf-user", services=["unknown"])

    def test_pmf_export_requires_consent_and_excludes_individual_hashes(self) -> None:
        metrics = {
            "sessions": {"completed": 1},
            "learners": {"unique": 1},
            "learning": {"average_mastery_delta": 0.5},
            "plugins": {"ready": 1},
            "signals": {"hosted_waitlist_count": 1},
            "hosted_interest": {
                "total": 1,
                "services": {"neural_sync": 1},
                "contact_hash": "must-not-export",
            },
        }
        summary = {
            "schema_version": "pmf-interest-v1",
            "total": 1,
            "with_contact": 1,
            "with_comment": 1,
            "services": {"neural_sync": 1},
            "sources": {"web-ui": 1},
            "contact_hash": "must-not-export",
        }

        with self.assertRaises(ValueError):
            build_pmf_export(metrics, summary, consent_to_share=False)

        exported = build_pmf_export(
            metrics,
            summary,
            consent_to_share=True,
            destination="github_discussion",
            note="Private note should not appear.",
        )
        serialized = json.dumps(exported)

        self.assertEqual(exported["schema_version"], "pmf-export-v1")
        self.assertEqual(exported["destination"], "github_discussion")
        self.assertTrue(exported["consent"]["granted"])
        self.assertTrue(exported["consent"]["note_provided"])
        self.assertEqual(exported["hosted_interest"]["total"], 1)
        self.assertNotIn("must-not-export", serialized)
        self.assertNotIn("Private note", serialized)
        self.assertNotIn("contact_hash", exported["hosted_interest"])


if __name__ == "__main__":
    unittest.main()
