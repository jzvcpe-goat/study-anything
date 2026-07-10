from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "reliability_evidence_index.py"


def load_script():
    script_dir = str(SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("reliability_evidence_index", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


indexer = load_script()


def soak(*, strict: bool = True):
    samples = 721 if strict else 20
    interval = 10.0 if strict else 2.0
    return {
        "schema_version": "self-host-soak-receipt-v1",
        "status": "pass",
        "classification": "healthy_window",
        "started_at": "2026-07-09T00:00:00Z",
        "finished_at": "2026-07-09T02:00:00Z",
        "endpoint": {
            "scope": "loopback",
            "tls_enabled": False,
            "host_included": False,
            "url_included": False,
        },
        "sampling": {
            "sample_count": samples,
            "interval_seconds": interval,
            "success_count": samples - (4 if strict else 3),
            "failure_count": 4 if strict else 3,
            "success_ratio": 0.9945 if strict else 0.85,
            "longest_consecutive_failure_run": 4 if strict else 3,
            "recovery_count": 1,
            "recovered_after_failure": True,
            "failure_categories": {
                "healthy": samples - (4 if strict else 3),
                "unavailable": 4 if strict else 3,
            },
        },
        "thresholds": {
            "minimum_success_ratio": 0.99 if strict else 0.4,
            "maximum_consecutive_failures": 8 if strict else 10,
            "recovery_after_failure_required": True,
        },
        "latency_ms": {"minimum": 1, "maximum": 8, "p50": 4, "p95": 7},
        "blocked_reasons": [],
        "privacy": {
            "metadata_only": True,
            "health_response_body_included": False,
            "api_url_included": False,
            "api_token_included": False,
            "docker_logs_included": False,
            "local_absolute_paths_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_metadata_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": "Bounded fixture receipt only.",
    }


def matrix(mode: str, *, strict: bool = True, head_sha: str = "a" * 40):
    return {
        "schema_version": "self-host-reliability-matrix-receipt-v1",
        "status": "pass",
        "mode": mode,
        "started_at": "2026-07-09T00:00:00Z",
        "finished_at": "2026-07-09T02:05:00Z" if strict else "2026-07-09T00:01:00Z",
        "schedule": {
            "samples_requested": 721 if strict else 20,
            "interval_seconds": 10.0 if strict else 2.0,
            "fault_after_seconds": 600.0 if strict else 4.0,
            "fault_duration_seconds": 45.0 if strict else 6.0,
            "real_elapsed_time_required": True,
            "accelerated_clock_used": False,
        },
        "runtime": {
            "api_flow_completed": True,
            "source_build_completed": mode == "source-build",
            "published_image_pull_completed": mode == "published-image",
            "controlled_restart_attempted": True,
            "controlled_restart_completed": True,
            "recovery_after_failure_observed": True,
            "pre_restart_session_recovery_completed": True,
            "compose_start_attempts": 1,
            "published_tag": "main" if mode == "published-image" else None,
            "published_image_digest": "sha256:" + "b" * 64 if mode == "published-image" else None,
            "source_revision_sha": head_sha if mode == "source-build" else None,
            "source_worktree_dirty": False if mode == "source-build" else None,
            "image_reference_included": False,
            "compose_project_included": False,
        },
        "soak": soak(strict=strict),
        "failure": {
            "phase": None,
            "category": None,
            "raw_error_included": False,
            "command_output_included": False,
        },
        "privacy": {
            "metadata_only": True,
            "api_url_included": False,
            "env_file_path_included": False,
            "compose_project_name_included": False,
            "docker_logs_included": False,
            "command_stdout_included": False,
            "command_stderr_included": False,
            "local_absolute_paths_included": False,
            "secrets_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
            "disposable_test_volumes_only": True,
        },
        "claim_boundary": "Bounded fixture matrix receipt only.",
    }


class ReliabilityEvidenceIndexTests(unittest.TestCase):
    def entry(self, run_id="1001", *, strict=True):
        return indexer.build_run_entry(
            run_id=run_id,
            event="workflow_dispatch",
            head_sha="a" * 40,
            source_receipt=matrix("source-build", strict=strict),
            published_receipt=matrix("published-image", strict=strict),
        )

    def test_strict_dual_pass_requires_both_modes(self) -> None:
        entry = self.entry()

        self.assertEqual(entry["decision"], "strict_dual_pass")
        self.assertTrue(entry["modes"]["source-build"]["strict_evidence"])
        self.assertTrue(entry["modes"]["published-image"]["strict_evidence"])

    def test_diagnostic_run_does_not_count_as_strict(self) -> None:
        entry = self.entry(strict=False)
        index = indexer.build_index(entry=entry)

        self.assertEqual(entry["decision"], "diagnostic_only")
        self.assertEqual(index["summary"]["strict_dual_pass_count"], 0)
        self.assertFalse(index["summary"]["longitudinal_trend_claimable"])

    def test_early_blocked_receipts_without_soak_are_preserved(self) -> None:
        source = matrix("source-build")
        published = matrix("published-image")
        for receipt in (source, published):
            receipt["status"] = "blocked"
            receipt["soak"] = None
            receipt["failure"]["phase"] = "compose_start"
            receipt["failure"]["category"] = "command_failed_after_retries"
        published["runtime"]["published_image_digest"] = None

        entry = indexer.build_run_entry(
            run_id="1001",
            event="workflow_dispatch",
            head_sha="a" * 40,
            source_receipt=source,
            published_receipt=published,
        )

        self.assertEqual(entry["decision"], "blocked")
        self.assertEqual(entry["modes"]["source-build"]["profile"], "diagnostic")

    def test_three_strict_runs_unlock_only_bounded_trend(self) -> None:
        index = indexer.build_index(entry=self.entry("1001"))
        index = indexer.build_index(entry=self.entry("1002"), previous_index=index)
        index = indexer.build_index(entry=self.entry("1003"), previous_index=index)

        self.assertTrue(index["summary"]["longitudinal_trend_claimable"])
        self.assertFalse(index["summary"]["production_slo_claimable"])

    def test_conflicting_duplicate_run_is_rejected(self) -> None:
        entry = self.entry()
        index = indexer.build_index(entry=entry)
        changed = copy.deepcopy(entry)
        changed["event"] = "schedule"

        with self.assertRaises(indexer.ReliabilityIndexError):
            indexer.build_index(entry=changed, previous_index=index)

    def test_tampered_previous_index_is_rejected(self) -> None:
        diagnostic = self.entry(strict=False)
        index = indexer.build_index(entry=diagnostic)
        index["runs"][0]["strict_dual_pass"] = True

        with self.assertRaises(indexer.ReliabilityIndexError):
            indexer.build_index(entry=self.entry("1002"), previous_index=index)

    def test_passing_receipt_must_satisfy_its_thresholds(self) -> None:
        source = matrix("source-build")
        source["soak"]["sampling"]["success_ratio"] = 0.5

        with self.assertRaises(indexer.ReliabilityIndexError):
            indexer.build_run_entry(
                run_id="1001",
                event="schedule",
                head_sha="a" * 40,
                source_receipt=source,
                published_receipt=matrix("published-image"),
            )

    def test_source_revision_must_match_workflow_head(self) -> None:
        with self.assertRaises(indexer.ReliabilityIndexError):
            indexer.build_run_entry(
                run_id="1001",
                event="schedule",
                head_sha="a" * 40,
                source_receipt=matrix("source-build", head_sha="c" * 40),
                published_receipt=matrix("published-image"),
            )

    def test_private_payload_is_rejected(self) -> None:
        source = matrix("source-build")
        source["runtime"]["operator_note"] = "Bearer private-verification-token"

        with self.assertRaises(indexer.ReliabilityIndexError):
            indexer.build_run_entry(
                run_id="1001",
                event="schedule",
                head_sha="a" * 40,
                source_receipt=source,
                published_receipt=matrix("published-image"),
            )

    def test_written_index_uses_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "index.json"
            indexer.write_index(target, indexer.build_index(entry=self.entry()))

            self.assertEqual(target.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
