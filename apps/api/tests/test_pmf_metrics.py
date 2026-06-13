from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from _path import ROOT  # noqa: F401

from study_anything.core.pmf import (
    LocalPmfInterestStore,
    build_adoption_telemetry,
    build_pmf_export,
    build_pmf_readiness,
    compute_pmf_metrics,
)
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
        self.assertEqual(exported["adoption_telemetry"]["schema_version"], "adoption-telemetry-v1")
        self.assertEqual(exported["pmf_readiness"]["schema_version"], "pmf-readiness-v1")
        self.assertTrue(exported["adoption_telemetry"]["privacy"]["aggregate_only"])
        self.assertNotIn("must-not-export", serialized)
        self.assertNotIn("Private note", serialized)
        self.assertNotIn("contact_hash", exported["hosted_interest"])

    def test_adoption_telemetry_and_pmf_readiness_are_aggregate_only(self) -> None:
        metrics = {
            "sessions": {
                "total": 6,
                "completed": 4,
                "discarded": 0,
                "open_hitl": 0,
                "completion_rate": 0.6667,
                "private_source": "Private source text",
            },
            "learners": {
                "unique": 3,
                "active_7d": 3,
                "active_30d": 3,
                "repeat": 3,
                "repeat_rate": 1.0,
                "raw_user_id": "raw-user",
            },
            "learning": {
                "answered_sessions": 4,
                "average_mastery_delta": 0.6,
                "private_answer": "Private learner answer",
                "private_insight": "Private generated insight",
            },
            "plugins": {"ready": 2, "invalid": 0},
            "signals": {"hosted_waitlist_count": 5},
        }
        interest = {
            "total": 5,
            "with_contact": 3,
            "with_comment": 2,
            "services": {"neural_sync": 5},
            "sources": {"skill-mode": 5},
            "freeform_comment": "Private freeform comment",
        }
        adoption_proof = {
            "schema_version": "adoption-proof-v1",
            "status": "ok",
            "within_target_minutes": True,
            "runtime": {
                "runtime": "skill-mode",
                "commands": {
                    "platform_tools": {
                        "status": "ok",
                        "tool_count": 34,
                        "agent_endpoint": "http://127.0.0.1:8787/secret",
                    },
                    "agent_eval_baseline": {"status": "ok"},
                    "retrieval_eval_runner": {"status": "ok"},
                    "operator_drill": {"openapi_path_count": 29},
                },
            },
            "private_context": "Private browser/video/app context",
        }

        telemetry = build_adoption_telemetry(metrics, interest, adoption_proof=adoption_proof)
        readiness = build_pmf_readiness(telemetry)
        serialized = json.dumps({"telemetry": telemetry, "readiness": readiness}, ensure_ascii=False)

        self.assertEqual(telemetry["schema_version"], "adoption-telemetry-v1")
        self.assertEqual(readiness["schema_version"], "pmf-readiness-v1")
        self.assertTrue(telemetry["collection"]["aggregate_only"])
        self.assertFalse(telemetry["collection"]["automatic_upload"])
        self.assertTrue(telemetry["adoption"]["tool_import_success"])
        self.assertTrue(telemetry["quality"]["agent_eval_passed"])
        self.assertFalse(readiness["commercial_boundary"]["sell_standalone_app_now"])
        for private_fragment in [
            "Private source text",
            "Private learner answer",
            "Private generated insight",
            "raw-user",
            "127.0.0.1:8787",
            "Private browser/video/app context",
            "Private freeform comment",
        ]:
            self.assertNotIn(private_fragment, serialized)


if __name__ == "__main__":
    unittest.main()
