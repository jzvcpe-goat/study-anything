from __future__ import annotations

import unittest

from _path import ROOT

from study_anything.core.cognitive_loop_contracts import (
    ARTIFACT_DOCTOR_SCHEMA_VERSION,
    ARTIFACT_INDEX_SCHEMA_VERSION,
    BOOTSTRAP_SCHEMA_VERSION,
    CLI_ARTIFACT_SCHEMA_VERSION,
    CognitiveLoopContractError,
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    EVENT_INDEX_SCHEMA_VERSION,
    HUMAN_GATE_ARTIFACT_SCHEMA_VERSION,
    PROJECT_SNAPSHOT_SCHEMA_VERSION,
    REPAIR_PLAN_SCHEMA_VERSION,
    RUN_ONCE_ARTIFACT_SCHEMA_VERSION,
    build_artifact_doctor_artifact,
    build_artifact_index_artifact,
    build_cli_artifact_report,
    build_evidence_bundle_artifact,
    build_event_index_artifact,
    build_human_gate_artifact,
    build_project_snapshot_artifact,
    build_repair_plan_artifact,
    build_run_once_artifact,
    render_cli_artifact_html,
    validate_all_public_objects,
    validate_contract_files,
    validate_decision_card,
    validate_project_event,
    write_default_contract_files,
)

REPO_ROOT = ROOT.parents[1]


class CognitiveLoopContractsTests(unittest.TestCase):
    def test_repo_contract_files_validate(self) -> None:
        reports = validate_contract_files(REPO_ROOT)

        self.assertEqual(len(reports), 4)
        self.assertEqual({report.status for report in reports}, {"pass"})
        self.assertEqual(
            {report.name for report in reports},
            {"config", "permissions", "evals", "risk"},
        )

    def test_public_objects_validate(self) -> None:
        objects = validate_all_public_objects(
            {
                "project_event": {
                    "event_id": "evt-1",
                    "project_id": "study-anything",
                    "actor": "agent",
                    "event_type": "schema_changed",
                    "summary": "Contract bootstrap validation changed.",
                    "timestamp": "2026-06-17T00:00:00Z",
                    "refs": ["doc:docs/cognitive-loop-contracts.md"],
                },
                "decision_card": {
                    "decision_id": "dec-1",
                    "project_id": "study-anything",
                    "title": "Add contract bootstrap",
                    "status": "approved",
                    "summary": "Add local Cognitive Loop contracts before runtime migration.",
                    "event_ids": ["evt-1"],
                    "evidence_refs": ["doc:docs/cognitive-loop-contracts.md"],
                    "risk": {"level": "medium", "score": 0.4, "reasons": ["public contract"]},
                    "human_mastery_gate": {"required": False, "status": "not_required"},
                    "verification": {"status": "passed", "commands": ["python3 scripts/verify_cognitive_loop_contracts.py --check"]},
                    "rollback": {"strategy": "patch_reverse"},
                },
                "loop_run": {
                    "run_id": "loop-1",
                    "project_id": "study-anything",
                    "objective": "Validate Cognitive Loop contracts.",
                    "status": "succeeded",
                    "started_at": "2026-06-17T00:00:00Z",
                    "project_event_ids": ["evt-1"],
                    "decision_card_ids": ["dec-1"],
                },
                "mastery_record": {
                    "record_id": "mastery-1",
                    "project_id": "study-anything",
                    "subject": "Cognitive Loop contracts",
                    "level": 0.75,
                    "bloom": "understand",
                    "evidence_refs": ["dec-1"],
                    "updated_at": "2026-06-17T00:00:00Z",
                },
                "evolution_report": {
                    "report_id": "evo-1",
                    "project_id": "study-anything",
                    "status": "approved",
                    "proposed_changes": ["Add validators"],
                    "decision_card_ids": ["dec-1"],
                    "verification_refs": ["python3 scripts/verify_cognitive_loop_contracts.py --check"],
                    "risk_summary": "No runtime daemon or model-key custody is introduced.",
                    "created_at": "2026-06-17T00:00:00Z",
                },
            }
        )

        self.assertEqual(objects["project_event"]["schema_version"], "project-event-v1")
        self.assertEqual(objects["decision_card"]["schema_version"], "decision-card-v1")

    def test_rejects_secret_like_values(self) -> None:
        with self.assertRaises(CognitiveLoopContractError):
            validate_project_event(
                {
                    "event_id": "evt-secret",
                    "project_id": "study-anything",
                    "actor": "agent",
                    "event_type": "schema_changed",
                    "summary": "Authorization: Bearer secretsecretsecret",
                    "timestamp": "2026-06-17T00:00:00Z",
                }
            )

    def test_high_risk_decision_requires_human_gate(self) -> None:
        with self.assertRaises(CognitiveLoopContractError):
            validate_decision_card(
                {
                    "decision_id": "dec-high",
                    "project_id": "study-anything",
                    "title": "Unsafe high risk",
                    "status": "approved",
                    "summary": "A high risk decision cannot skip human mastery.",
                    "event_ids": ["evt-1"],
                    "evidence_refs": ["doc:docs/architecture.md"],
                    "risk": {"level": "high", "score": 0.91, "reasons": ["auth"]},
                    "human_mastery_gate": {"required": False, "status": "not_required"},
                    "verification": {"status": "not_run", "commands": []},
                    "rollback": {"strategy": "patch_reverse"},
                }
            )

    def test_rejects_raw_excerpt_fields(self) -> None:
        with self.assertRaises(CognitiveLoopContractError):
            validate_decision_card(
                {
                    "decision_id": "dec-raw",
                    "project_id": "study-anything",
                    "title": "Raw source evidence",
                    "status": "proposed",
                    "summary": "A public decision cannot include raw excerpts.",
                    "event_ids": ["evt-1"],
                    "evidence_refs": ["doc:docs/architecture.md"],
                    "risk": {"level": "medium", "score": 0.5, "reasons": ["contract"]},
                    "human_mastery_gate": {"required": False, "status": "not_required"},
                    "verification": {"status": "not_run", "commands": []},
                    "rollback": {"strategy": "patch_reverse"},
                    "excerpt": "raw private source text",
                }
            )

    def test_bootstrap_schema_constant_is_public(self) -> None:
        self.assertEqual(BOOTSTRAP_SCHEMA_VERSION, "cognitive-loop-contract-bootstrap-v1")

    def test_cli_artifact_report_renders_static_html(self) -> None:
        report = build_cli_artifact_report(REPO_ROOT, generated_at="2026-06-17T00:20:00Z")
        html = render_cli_artifact_html(report)

        self.assertEqual(report["schema_version"], CLI_ARTIFACT_SCHEMA_VERSION)
        self.assertIn("Cognitive Black Box Protocol", html)
        self.assertIn("Decision Card", html)
        self.assertIn("Contract Files", html)
        self.assertFalse(report["privacy"]["standalone_frontend_required"])
        self.assertFalse(report["privacy"]["real_model_keys_included"])

    def test_init_writes_valid_contract_files(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = write_default_contract_files(
                root,
                project_id="external-adopter-project",
                project_name="External Adopter Project",
            )

            self.assertEqual({report.status for report in reports}, {"written"})
            validated = validate_contract_files(root)
            self.assertEqual({report.name for report in validated}, {"config", "permissions", "evals", "risk"})

    def test_run_once_artifact_builds_governed_loop_evidence(self) -> None:
        report = build_run_once_artifact(
            REPO_ROOT,
            generated_at="2026-06-17T00:40:00Z",
            artifact_ref=".cognitive-loop/artifacts/run-once.html",
        )
        html = render_cli_artifact_html(report)

        self.assertEqual(report["schema_version"], RUN_ONCE_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(report["loop_run"]["status"], "succeeded")
        self.assertEqual(report["decision_card"]["status"], "approved")
        self.assertIn("Loop Run", html)
        self.assertFalse(report["privacy"]["watcher_daemon_started"])
        self.assertFalse(report["privacy"]["mastra_runtime_started"])

    def test_run_once_high_risk_requires_human_mastery_gate(self) -> None:
        report = build_run_once_artifact(
            REPO_ROOT,
            risk_level="high",
            generated_at="2026-06-17T00:41:00Z",
        )

        self.assertEqual(report["loop_run"]["status"], "suspended")
        self.assertEqual(report["decision_card"]["status"], "needs_human_mastery")
        self.assertTrue(report["decision_card"]["human_mastery_gate"]["required"])

    def test_project_snapshot_artifact_records_paths_without_contents(self) -> None:
        report = build_project_snapshot_artifact(
            REPO_ROOT,
            paths=["README.md", "docs/cognitive-loop-contracts.md"],
            generated_at="2026-06-17T00:50:00Z",
        )
        html = render_cli_artifact_html(report)

        self.assertEqual(report["schema_version"], PROJECT_SNAPSHOT_SCHEMA_VERSION)
        self.assertEqual(report["snapshot"]["changed_path_count"], 2)
        self.assertFalse(report["snapshot"]["diff_body_included"])
        self.assertFalse(report["snapshot"]["file_contents_included"])
        self.assertFalse(report["privacy"]["watcher_daemon_started"])
        self.assertIn("Project Snapshot", html)

    def test_human_gate_artifact_records_approval_without_private_context(self) -> None:
        report = build_human_gate_artifact(
            REPO_ROOT,
            decision_id="dec-sensitive-runtime",
            resolution="approved",
            rationale="Operator verified evidence, risk, and rollback plan.",
            generated_at="2026-06-17T01:00:00Z",
        )
        html = render_cli_artifact_html(report)

        self.assertEqual(report["schema_version"], HUMAN_GATE_ARTIFACT_SCHEMA_VERSION)
        self.assertEqual(report["status"], "approved")
        self.assertEqual(report["decision_card"]["human_mastery_gate"]["status"], "approved")
        self.assertEqual(report["loop_run"]["status"], "succeeded")
        self.assertFalse(report["privacy"]["raw_source_text_included"])
        self.assertFalse(report["privacy"]["agent_endpoints_included"])
        self.assertIn("Human Mastery Gate", html)

    def test_human_gate_artifact_records_rejection(self) -> None:
        report = build_human_gate_artifact(
            REPO_ROOT,
            decision_id="dec-risky-change",
            resolution="rejected",
            rationale="Operator rejected the decision until verification evidence improves.",
            generated_at="2026-06-17T01:01:00Z",
        )

        self.assertEqual(report["status"], "rejected")
        self.assertEqual(report["decision_card"]["status"], "rejected")
        self.assertEqual(report["loop_run"]["status"], "rejected")

    def test_human_gate_rejects_secret_like_rationale(self) -> None:
        with self.assertRaises(CognitiveLoopContractError):
            build_human_gate_artifact(
                REPO_ROOT,
                resolution="approved",
                rationale="api_key = secretsecretsecret",
            )

    def test_evidence_bundle_records_hashes_without_contents(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_default_contract_files(
                root,
                project_id="external-adopter-project",
                project_name="External Adopter Project",
            )
            event_path = root / ".cognitive-loop" / "events" / "run-once.json"
            html_path = root / ".cognitive-loop" / "artifacts" / "gate.html"
            event_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.parent.mkdir(parents=True, exist_ok=True)
            event_path.write_text('{"schema_version":"example"}', encoding="utf-8")
            html_path.write_text("<html>redacted artifact</html>", encoding="utf-8")

            report = build_evidence_bundle_artifact(
                root,
                artifact_paths=[
                    ".cognitive-loop/events/run-once.json",
                    ".cognitive-loop/artifacts/gate.html",
                ],
                generated_at="2026-06-17T01:10:00Z",
            )
            html = render_cli_artifact_html(report)

        self.assertEqual(report["schema_version"], EVIDENCE_BUNDLE_SCHEMA_VERSION)
        self.assertEqual(report["evidence_bundle"]["artifact_count"], 2)
        self.assertFalse(report["evidence_bundle"]["content_included"])
        self.assertTrue(all(not item["content_included"] for item in report["evidence_bundle"]["artifacts"]))
        self.assertFalse(report["privacy"]["artifact_contents_included"])
        self.assertIn("Evidence Bundle", html)

    def test_event_index_records_event_metadata_without_contents(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_default_contract_files(
                root,
                project_id="external-adopter-project",
                project_name="External Adopter Project",
            )
            event_path = root / ".cognitive-loop" / "events" / "run-once.json"
            event_path.parent.mkdir(parents=True, exist_ok=True)
            event_path.write_text(
                """{
                  "schema_version": "cognitive-loop-run-once-artifact-v1",
                  "status": "succeeded",
                  "generated_at": "2026-06-17T01:20:00Z",
                  "project_event": {
                    "event_id": "evt-1",
                    "event_type": "verification_completed"
                  },
                  "decision_card": {
                    "decision_id": "dec-1",
                    "status": "approved"
                  },
                  "loop_run": {
                    "run_id": "loop-1",
                    "status": "succeeded"
                  }
                }""",
                encoding="utf-8",
            )

            report = build_event_index_artifact(
                root,
                event_paths=[".cognitive-loop/events/run-once.json"],
                generated_at="2026-06-17T01:21:00Z",
            )
            html = render_cli_artifact_html(report)

        self.assertEqual(report["schema_version"], EVENT_INDEX_SCHEMA_VERSION)
        self.assertEqual(report["event_index"]["entry_count"], 1)
        self.assertFalse(report["event_index"]["content_included"])
        self.assertFalse(report["event_index"]["entries"][0]["content_included"])
        self.assertEqual(report["event_index"]["entries"][0]["kind"], "loop_run")
        self.assertEqual(report["event_index"]["entries"][0]["project_event_id"], "evt-1")
        self.assertFalse(report["privacy"]["event_contents_included"])
        self.assertFalse(report["privacy"]["watcher_daemon_started"])
        self.assertIn("Event Index", html)

    def test_artifact_doctor_passes_clean_metadata_pairs(self) -> None:
        import hashlib
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_default_contract_files(
                root,
                project_id="external-adopter-project",
                project_name="External Adopter Project",
            )
            event_dir = root / ".cognitive-loop" / "events"
            artifact_dir = root / ".cognitive-loop" / "artifacts"
            event_dir.mkdir(parents=True, exist_ok=True)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            run_event = {
                "schema_version": "cognitive-loop-run-once-artifact-v1",
                "status": "succeeded",
                "generated_at": "2026-06-17T01:30:00Z",
            }
            run_event_path = event_dir / "run-once.json"
            run_event_path.write_text(json.dumps(run_event), encoding="utf-8")
            (artifact_dir / "run-once.html").write_text("<html>run once artifact</html>", encoding="utf-8")
            event_hash = hashlib.sha256(run_event_path.read_bytes()).hexdigest()
            index_event = {
                "schema_version": "cognitive-loop-event-index-v1",
                "status": "ready",
                "generated_at": "2026-06-17T01:31:00Z",
                "event_index": {
                    "entries": [
                        {
                            "path": ".cognitive-loop/events/run-once.json",
                            "sha256": event_hash,
                        }
                    ]
                },
            }
            (event_dir / "cognitive-loop-event-index.json").write_text(json.dumps(index_event), encoding="utf-8")
            (artifact_dir / "cognitive-loop-event-index.html").write_text(
                "<html>event index artifact</html>",
                encoding="utf-8",
            )

            report = build_artifact_doctor_artifact(
                root,
                generated_at="2026-06-17T01:32:00Z",
            )
            html = render_cli_artifact_html(report)

        self.assertEqual(report["schema_version"], ARTIFACT_DOCTOR_SCHEMA_VERSION)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["artifact_doctor"]["issue_count"], 0)
        self.assertFalse(report["artifact_doctor"]["content_included"])
        self.assertFalse(report["privacy"]["event_contents_included"])
        self.assertIn("Artifact Doctor", html)

    def test_artifact_doctor_detects_missing_html_and_duplicate_hash(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_default_contract_files(
                root,
                project_id="external-adopter-project",
                project_name="External Adopter Project",
            )
            event_dir = root / ".cognitive-loop" / "events"
            event_dir.mkdir(parents=True, exist_ok=True)
            payload = '{"schema_version":"cognitive-loop-run-once-artifact-v1","status":"succeeded"}'
            (event_dir / "one.json").write_text(payload, encoding="utf-8")
            (event_dir / "two.json").write_text(payload, encoding="utf-8")

            report = build_artifact_doctor_artifact(root, generated_at="2026-06-17T01:33:00Z")

        codes = {issue["code"] for issue in report["artifact_doctor"]["issues"]}
        self.assertEqual(report["status"], "needs_attention")
        self.assertIn("missing_html_pair", codes)
        self.assertIn("duplicate_hash", codes)
        self.assertIn("missing_event_index", codes)
        self.assertFalse(report["privacy"]["artifact_contents_included"])

    def test_artifact_doctor_detects_stale_event_index_hash(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_default_contract_files(
                root,
                project_id="external-adopter-project",
                project_name="External Adopter Project",
            )
            event_dir = root / ".cognitive-loop" / "events"
            artifact_dir = root / ".cognitive-loop" / "artifacts"
            event_dir.mkdir(parents=True, exist_ok=True)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (event_dir / "run-once.json").write_text(
                '{"schema_version":"cognitive-loop-run-once-artifact-v1","status":"succeeded"}',
                encoding="utf-8",
            )
            (artifact_dir / "run-once.html").write_text("<html>run once artifact</html>", encoding="utf-8")
            stale_index = {
                "schema_version": "cognitive-loop-event-index-v1",
                "status": "ready",
                "event_index": {
                    "entries": [
                        {
                            "path": ".cognitive-loop/events/run-once.json",
                            "sha256": "0" * 64,
                        }
                    ]
                },
            }
            (event_dir / "cognitive-loop-event-index.json").write_text(json.dumps(stale_index), encoding="utf-8")

            report = build_artifact_doctor_artifact(root, generated_at="2026-06-17T01:34:00Z")

        codes = {issue["code"] for issue in report["artifact_doctor"]["issues"]}
        self.assertIn("stale_event_index_hash_mismatch", codes)
        self.assertFalse(report["privacy"]["watcher_daemon_started"])

    def test_repair_plan_passes_clean_doctor(self) -> None:
        import hashlib
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_default_contract_files(
                root,
                project_id="external-adopter-project",
                project_name="External Adopter Project",
            )
            event_dir = root / ".cognitive-loop" / "events"
            artifact_dir = root / ".cognitive-loop" / "artifacts"
            event_dir.mkdir(parents=True, exist_ok=True)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            run_event_path = event_dir / "run-once.json"
            run_event_path.write_text(
                '{"schema_version":"cognitive-loop-run-once-artifact-v1","status":"succeeded"}',
                encoding="utf-8",
            )
            (artifact_dir / "run-once.html").write_text("<html>run once artifact</html>", encoding="utf-8")
            event_hash = hashlib.sha256(run_event_path.read_bytes()).hexdigest()
            index_event = {
                "schema_version": "cognitive-loop-event-index-v1",
                "status": "ready",
                "event_index": {
                    "entries": [
                        {
                            "path": ".cognitive-loop/events/run-once.json",
                            "sha256": event_hash,
                        }
                    ]
                },
            }
            (event_dir / "cognitive-loop-event-index.json").write_text(json.dumps(index_event), encoding="utf-8")
            (artifact_dir / "cognitive-loop-event-index.html").write_text(
                "<html>event index artifact</html>",
                encoding="utf-8",
            )

            report = build_repair_plan_artifact(root, generated_at="2026-06-17T01:35:00Z")
            html = render_cli_artifact_html(report)

        self.assertEqual(report["schema_version"], REPAIR_PLAN_SCHEMA_VERSION)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["repair_plan"]["action_count"], 0)
        self.assertTrue(report["repair_plan"]["manual_only"])
        self.assertFalse(report["repair_plan"]["auto_apply"])
        self.assertFalse(report["privacy"]["repair_actions_executed"])
        self.assertIn("Repair Plan", html)

    def test_repair_plan_maps_doctor_issues_to_manual_actions(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_default_contract_files(
                root,
                project_id="external-adopter-project",
                project_name="External Adopter Project",
            )
            event_dir = root / ".cognitive-loop" / "events"
            event_dir.mkdir(parents=True, exist_ok=True)
            payload = '{"schema_version":"cognitive-loop-run-once-artifact-v1","status":"succeeded"}'
            (event_dir / "one.json").write_text(payload, encoding="utf-8")
            (event_dir / "two.json").write_text(payload, encoding="utf-8")

            report = build_repair_plan_artifact(root, generated_at="2026-06-17T01:36:00Z")

        actions = report["repair_plan"]["actions"]
        codes = {action["issue_code"] for action in actions}
        self.assertEqual(report["status"], "needs_attention")
        self.assertIn("missing_html_pair", codes)
        self.assertIn("duplicate_hash", codes)
        self.assertIn("missing_event_index", codes)
        self.assertTrue(all(action["execution_mode"] == "manual_only" for action in actions))
        self.assertTrue(all(action["auto_apply"] is False for action in actions))
        self.assertFalse(report["privacy"]["artifact_contents_included"])

    def test_artifact_index_links_local_artifacts_without_contents(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_default_contract_files(
                root,
                project_id="external-adopter-project",
                project_name="External Adopter Project",
            )
            event_path = root / ".cognitive-loop" / "events" / "run-once.json"
            html_path = root / ".cognitive-loop" / "artifacts" / "run-once.html"
            event_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.parent.mkdir(parents=True, exist_ok=True)
            event_path.write_text(
                """{
                  "schema_version": "cognitive-loop-run-once-artifact-v1",
                  "status": "succeeded",
                  "generated_at": "2026-06-17T01:40:00Z",
                  "project_event": {"event_id": "evt-1", "event_type": "verification_completed"},
                  "decision_card": {"decision_id": "dec-1", "status": "approved"},
                  "loop_run": {"run_id": "loop-1", "status": "succeeded"}
                }""",
                encoding="utf-8",
            )
            html_path.write_text("<html>private local artifact body</html>", encoding="utf-8")

            report = build_artifact_index_artifact(
                root,
                artifact_paths=[
                    ".cognitive-loop/events/run-once.json",
                    ".cognitive-loop/artifacts/run-once.html",
                ],
                generated_at="2026-06-17T01:41:00Z",
            )
            html = render_cli_artifact_html(report)

        self.assertEqual(report["schema_version"], ARTIFACT_INDEX_SCHEMA_VERSION)
        self.assertEqual(report["artifact_index"]["entry_count"], 2)
        self.assertEqual(report["artifact_index"]["html_count"], 1)
        self.assertEqual(report["artifact_index"]["event_json_count"], 1)
        self.assertFalse(report["artifact_index"]["content_included"])
        self.assertFalse(report["artifact_index"]["standalone_frontend_required"])
        self.assertFalse(report["privacy"]["artifact_contents_included"])
        self.assertFalse(report["privacy"]["standalone_frontend_required"])
        self.assertTrue(all(not item["content_included"] for item in report["artifact_index"]["entries"]))
        by_path = {item["path"]: item for item in report["artifact_index"]["entries"]}
        self.assertEqual(by_path[".cognitive-loop/events/run-once.json"]["href"], "../events/run-once.json")
        self.assertEqual(by_path[".cognitive-loop/artifacts/run-once.html"]["href"], "run-once.html")
        self.assertIn("Artifact Index", html)
        self.assertNotIn("private local artifact body", html)


if __name__ == "__main__":
    unittest.main()
