from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.cbb.benchmark.human_reconstruction import boundary_questions
from study_anything.cbb.benchmark.models import HumanReviewSessionV1
from study_anything.cbb.benchmark.project_scenarios import (
    ProjectScenarioCheckV1,
    RealProjectScenarioSetV1,
    RealProjectScenarioV1,
    run_real_project_scenarios,
)
from study_anything.cbb.benchmark.review_cockpit import (
    ReviewCockpit,
    create_review_cockpit_app,
    load_canonical_mode_configs,
)


def _run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


class RealProjectScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        _run_git(self.source, "init", "--quiet")
        _run_git(self.source, "config", "user.email", "delivery-clearance@example.invalid")
        _run_git(self.source, "config", "user.name", "Delivery Clearance Test")
        (self.source / "gate.txt").write_text("blocked\n", encoding="utf-8")
        _run_git(self.source, "add", "gate.txt")
        _run_git(self.source, "commit", "--quiet", "-m", "blocked state")
        self.blocked_commit = _run_git(self.source, "rev-parse", "HEAD")
        (self.source / "gate.txt").write_text("ready\n", encoding="utf-8")
        _run_git(self.source, "add", "gate.txt")
        _run_git(self.source, "commit", "--quiet", "-m", "ready state")
        self.ready_commit = _run_git(self.source, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _check(expected_exit_code: int) -> ProjectScenarioCheckV1:
        return ProjectScenarioCheckV1(
            check_id="fixture-release-check",
            argv=[
                "{python}",
                "-c",
                (
                    "from pathlib import Path; import sys; "
                    "sys.exit(0 if Path('gate.txt').read_text().strip() == 'ready' else 1)"
                ),
            ],
            timeout_seconds=10,
            expected_exit_code=expected_exit_code,
            expected_output_markers=[],
            expected_failed_node_ids=[],
        )

    def _scenario(
        self,
        *,
        case_id: str,
        commit: str,
        expected_status: str,
        expected_exit_code: int,
    ) -> RealProjectScenarioV1:
        return RealProjectScenarioV1.model_validate(
            {
                "schema_version": "real-project-scenario-v1",
                "case_id": case_id,
                "source_commit_sha": commit,
                "scenario_type": "fixture-project-state",
                "task_summary_code": "fixture-delivery-candidate",
                "declared_risk_level": "medium",
                "target_scope": "personal_local",
                "intended_recipient_role": "local-project-owner",
                "risk_owner_role": "local-project-owner",
                "prohibited_use_codes": ["customer-handoff", "production-execution"],
                "rollback_summary_code": "fixture-reset-available",
                "check": self._check(expected_exit_code).model_dump(mode="json"),
                "expected_machine_status": expected_status,
                "pass_summary_code": "fixture-check-passed",
                "failure_summary_code": "fixture-check-failed",
                "historical_evidence": ["fixture-commit-bound"],
            }
        )

    def test_real_project_replay_and_two_mode_human_cockpit(self) -> None:
        scenario_set = RealProjectScenarioSetV1(
            schema_version="real-project-scenario-set-v1",
            suite_id="real-project-v0.1",
            source_repository="https://example.invalid/delivery-clearance-fixture.git",
            evaluation_perspective="local_project_owner",
            cases=[
                self._scenario(
                    case_id="real-01-blocked",
                    commit=self.blocked_commit,
                    expected_status="blocked",
                    expected_exit_code=1,
                ),
                self._scenario(
                    case_id="real-02-ready",
                    commit=self.ready_commit,
                    expected_status="ready_for_human_review",
                    expected_exit_code=0,
                ),
            ],
            claim_boundary="Fixture replay only; no production or effectiveness claim.",
        )
        output = self.root / "results"
        report = run_real_project_scenarios(
            source_repo=self.source,
            scenario_set=scenario_set,
            output_dir=output,
            python_executable=Path(sys.executable),
        )
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocked_case_count"], 1)
        self.assertEqual(report["ready_for_human_review_count"], 1)
        self.assertFalse(report["release_authorized"])
        self.assertTrue(all(item["oracle_match"] for item in report["cases"]))

        blocked_packet = json.loads(
            (output / "reviewer-packets" / "real-01-blocked.json").read_text(encoding="utf-8")
        )
        failed_checks = [
            item
            for item in blocked_packet["candidate"]["visible_evidence"]
            if item["evidence_type"] == "project-release-check"
        ]
        self.assertEqual(failed_checks[0]["status"], "failed")

        protocol = self.root / "human-protocol.json"
        protocol.write_text(
            json.dumps(
                {
                    "schema_version": "benchmark-human-protocol-v1",
                    "boundary_reconstruction": {
                        "packet_dir": "results/reviewer-packets",
                        "output": "human-sessions.jsonl",
                        "reviewer_role": "local-project-owner",
                        "order_seed": "real-project-boundary",
                        "max_items_per_batch": 2,
                    },
                    "full_review_reference": {
                        "packet_dir": "results/reviewer-packets",
                        "output": "human-sessions.jsonl",
                        "reviewer_role": "local-project-owner",
                        "order_seed": "real-project-full",
                        "max_items_per_batch": 2,
                    },
                    "privacy": {
                        "raw_answers_included": False,
                        "reviewer_identity_required": False,
                        "attention_stream_included": False,
                        "screenshots_included": False,
                        "keystrokes_included": False,
                        "biometrics_included": False,
                    },
                    "claim_boundary": {
                        "maximum_scope": "personal_local",
                        "one_person_multiple_roles_must_be_disclosed": True,
                        "independent_reviewer_claimed": False,
                        "delivery_clearance_effectiveness_claimed": False,
                        "customer_delivery_validation_claimed": False,
                        "production_approval_claimed": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        configs = load_canonical_mode_configs(self.root, protocol, max_items=2)
        cockpit = ReviewCockpit(configs)
        client = TestClient(create_review_cockpit_app(cockpit))
        page = client.get("/")
        self.assertNotIn("Blinded adjudication", page.text)
        self.assertEqual(client.get("/api/review/blinded_adjudication").status_code, 404)

        state = client.get("/api/review/boundary_reconstruction").json()
        active_case_id = cockpit.queues["boundary_reconstruction"].case_ids[0]
        active_packet = json.loads(
            (output / "reviewer-packets" / f"{active_case_id}.json").read_text(encoding="utf-8")
        )
        answers: list[str] = []
        for question in boundary_questions(active_packet):
            answers.append(
                str(
                    next(
                        index
                        for index, option in enumerate(question.options, start=1)
                        if option.code == question.expected_code
                    )
                )
            )
        preparation = client.post(
            "/api/review/prepare",
            headers={"X-Review-Token": state["review_token"]},
            json={
                "mode": "boundary_reconstruction",
                "item_token": state["item_token"],
                "responsibility": "local_delivery_owner",
                "reviewable_materials": ["scope_and_responsibility"],
                "intended_next_step": "personal_local_validation",
            },
        )
        self.assertEqual(preparation.status_code, 200, preparation.text)
        response = client.post(
            "/api/review/submit",
            headers={"X-Review-Token": state["review_token"]},
            json={
                "mode": "boundary_reconstruction",
                "item_token": state["item_token"],
                "preparation_token": preparation.json()["preparation_token"],
                "answers": answers,
                "active_review_ms": 25,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        session_line = (
            (self.root / "human-sessions.jsonl").read_text(encoding="utf-8").splitlines()[0]
        )
        session = HumanReviewSessionV1.model_validate_json(session_line)
        self.assertEqual(session.suite_id, "real-project-v0.1")
        self.assertEqual(session.measurement.boundary_questions_correct, 5)


if __name__ == "__main__":
    unittest.main()
