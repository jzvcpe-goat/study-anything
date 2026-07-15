from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.cbb.benchmark.human_reconstruction import boundary_questions
from study_anything.cbb.benchmark.models import HumanReviewSessionV1
from study_anything.cbb.benchmark.real_agent_cases import (
    RealAgentCaseSetV1,
    RealAgentSelectionProtocolV1,
    build_real_agent_case_set,
)
from study_anything.cbb.benchmark.review_cockpit import (
    ReviewCockpit,
    ReviewCockpitError,
    ReviewQueue,
    create_review_cockpit_app,
    load_canonical_mode_configs,
)


class RealAgentCaseSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.predictions_path = self.root / "preds.json"
        self.results_path = self.root / "results.json"
        self.issues = self.root / "issues"
        self.issues.mkdir()
        self.task_outcomes = {
            "alpha__one-1": "passed",
            "beta__two-2": "passed",
            "gamma__three-3": "failed",
            "delta__four-4": "failed",
        }
        predictions = {
            task_id: {
                "model_name_or_path": "fixture-agent",
                "model_patch": (
                    f"diff --git a/{task_id}.txt b/{task_id}.txt\n"
                    f"--- a/{task_id}.txt\n"
                    f"+++ b/{task_id}.txt\n"
                    "@@ -1 +1 @@\n"
                    "-before\n"
                    "+after\n"
                ),
            }
            for task_id in self.task_outcomes
        }
        self.predictions_path.write_text(json.dumps(predictions, sort_keys=True), encoding="utf-8")
        results = {
            "submitted": 4,
            "submitted_ids": list(predictions),
            "success_ids": [
                task for task, outcome in self.task_outcomes.items() if outcome == "passed"
            ],
            "failure_ids": [
                task for task, outcome in self.task_outcomes.items() if outcome == "failed"
            ],
            "error_ids": [],
            "incomplete_ids": [],
            "empty_patch_ids": [],
            "success": 2,
            "failure": 2,
            "error": 0,
            "incomplete": 0,
            "empty_patch": 0,
        }
        self.results_path.write_text(json.dumps(results, sort_keys=True), encoding="utf-8")
        for task_id in self.task_outcomes:
            owner, remainder = task_id.split("__", 1)
            repository, number_text = remainder.rsplit("-", 1)
            issue = {
                "repository_url": f"https://api.github.com/repos/{owner}/{repository}",
                "html_url": f"https://github.com/{owner}/{repository}/pull/{number_text}",
                "number": int(number_text),
                "title": f"Fix {task_id}",
                "body": f"Public task context for {task_id}.",
                "updated_at": "2026-07-01T00:00:00Z",
                "closed_at": "2026-07-02T00:00:00Z",
                "pull_request": {"url": "https://example.invalid/pull"},
            }
            (self.issues / f"{task_id}.json").write_text(
                json.dumps(issue, sort_keys=True), encoding="utf-8"
            )
        self.protocol = RealAgentSelectionProtocolV1(
            schema_version="real-agent-selection-protocol-v1",
            suite_id="real-agent-delivery-v0.1",
            source_repository="https://github.com/example/submission",
            source_revision="a" * 40,
            submission_path="submissions/typescript/agent/model",
            predictions_digest_sha256=sha256(self.predictions_path.read_bytes()).hexdigest(),
            results_digest_sha256=sha256(self.results_path.read_bytes()).hexdigest(),
            agent_name="fixture Agent",
            model_name="fixture Model",
            language="typescript",
            selection_seed="fixture-real-agent-v0.1",
            selection_order="sha256-seed-outcome-task-id",
            passed_case_count=2,
            failed_case_count=2,
            max_cases_per_repository_per_stratum=1,
            task_context_source="public-github-issue-or-pull-request",
            raw_candidate_payload_vendored=False,
            raw_issue_body_vendored=False,
            local_official_scorer_reexecuted=False,
            target_scope="personal_local",
            claim_boundary="Fixture input only; no effectiveness or release claim.",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_builds_blinded_metadata_and_local_review_materials(self) -> None:
        output = self.root / "committed-results"
        materials = self.root / "local-materials"
        result = build_real_agent_case_set(
            protocol=self.protocol,
            predictions_path=self.predictions_path,
            results_path=self.results_path,
            issue_response_dir=self.issues,
            output_dir=output,
            material_output_dir=materials,
        )
        self.assertEqual(result["case_count"], 4)
        self.assertEqual(result["published_passed_count"], 2)
        self.assertEqual(result["published_failed_count"], 2)
        self.assertFalse(result["effectiveness_claim_allowed"])
        self.assertFalse(result["release_authorized"])

        case_set = RealAgentCaseSetV1.model_validate_json(
            (output / "case-set.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(case_set.cases), 4)
        self.assertEqual(len({case.repository for case in case_set.cases}), 4)
        for case in case_set.cases:
            packet = json.loads(
                (output / "reviewer-packets" / f"{case.case_id}.json").read_text(encoding="utf-8")
            )
            self.assertFalse(packet["official_scorer_result_included"])
            self.assertFalse(packet["reference_label_included"])
            self.assertFalse(packet["raw_candidate_payload_included"])
            delivery_context = packet["delivery_context"]
            self.assertEqual(delivery_context["delivering_party_type"], "ai-agent")
            self.assertEqual(delivery_context["delivering_agent_name"], "fixture Agent")
            self.assertEqual(delivery_context["delivering_model_name"], "fixture Model")
            self.assertEqual(delivery_context["deliverable_type"], "candidate-code-patch")
            self.assertEqual(delivery_context["deliverable_title"], case.issue_title)
            self.assertEqual(delivery_context["source_repository"], case.repository)
            self.assertEqual(delivery_context["source_task_uri"], case.issue_uri)
            self.assertEqual(delivery_context["intended_recipient_role"], "local-project-owner")
            self.assertEqual(
                delivery_context["clearance_state"],
                "pending-human-review-not-cleared",
            )
            self.assertEqual(len(boundary_questions(packet)), 5)
            scorer = next(
                item
                for item in packet["candidate"]["visible_evidence"]
                if item["evidence_type"] == "scorer-result"
            )
            self.assertEqual(scorer["status"], "missing")
            self.assertTrue((materials / case.case_id / "candidate.patch").is_file())
            self.assertTrue((materials / case.case_id / "issue.md").is_file())
        self.assertEqual(list(output.rglob("candidate.patch")), [])
        self.assertEqual(list(output.rglob("issue.md")), [])

        incomplete_packet = json.loads(
            (output / "reviewer-packets" / f"{case_set.cases[0].case_id}.json").read_text(
                encoding="utf-8"
            )
        )
        incomplete_packet.pop("delivery_context")
        with self.assertRaisesRegex(
            ReviewCockpitError,
            "missing its delivery context",
        ):
            ReviewQueue._candidate_summary(incomplete_packet)

    def test_rejects_source_digest_drift(self) -> None:
        self.predictions_path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "predictions file digest drifted"):
            build_real_agent_case_set(
                protocol=self.protocol,
                predictions_path=self.predictions_path,
                results_path=self.results_path,
                issue_response_dir=self.issues,
                output_dir=self.root / "results-drift",
                material_output_dir=self.root / "materials-drift",
            )

    def test_rejects_local_material_access_from_boundary_mode(self) -> None:
        protocol_path = self.root / "invalid-human-protocol.json"
        protocol_path.write_text(
            json.dumps(
                {
                    "schema_version": "benchmark-human-protocol-v1",
                    "boundary_reconstruction": {
                        "packet_dir": "packets",
                        "local_material_dir": "local-materials",
                        "output": "human-sessions.jsonl",
                        "reviewer_role": "local-project-owner",
                        "order_seed": "invalid-boundary-material",
                        "max_items_per_batch": 1,
                    },
                    "privacy": {
                        "raw_answers_included": False,
                        "attention_stream_included": False,
                        "screenshots_included": False,
                        "keystrokes_included": False,
                        "biometrics_included": False,
                    },
                    "claim_boundary": {
                        "maximum_scope": "personal_local",
                        "independent_reviewer_claimed": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            ReviewCockpitError,
            "local review material is allowed only for full_review_reference",
        ):
            load_canonical_mode_configs(self.root, protocol_path, max_items=1)

    def test_full_review_reads_digest_bound_local_material_without_persisting_it(self) -> None:
        output = self.root / "committed-results"
        materials = self.root / "local-materials"
        build_real_agent_case_set(
            protocol=self.protocol,
            predictions_path=self.predictions_path,
            results_path=self.results_path,
            issue_response_dir=self.issues,
            output_dir=output,
            material_output_dir=materials,
        )
        protocol_path = self.root / "human-protocol.json"
        protocol_path.write_text(
            json.dumps(
                {
                    "schema_version": "benchmark-human-protocol-v1",
                    "boundary_reconstruction": {
                        "packet_dir": "committed-results/reviewer-packets",
                        "output": "human-sessions.jsonl",
                        "reviewer_role": "local-project-owner",
                        "order_seed": "real-agent-boundary",
                        "max_items_per_batch": 4,
                    },
                    "full_review_reference": {
                        "packet_dir": "committed-results/reviewer-packets",
                        "local_material_dir": "local-materials",
                        "output": "human-sessions.jsonl",
                        "reviewer_role": "local-project-owner",
                        "order_seed": "real-agent-full",
                        "max_items_per_batch": 4,
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
        cockpit = ReviewCockpit(load_canonical_mode_configs(self.root, protocol_path, max_items=4))
        client = TestClient(create_review_cockpit_app(cockpit))

        boundary_state = client.get("/api/review/boundary_reconstruction").json()
        self.assertNotIn("local_material", boundary_state)
        self.assertNotIn("diff --git", json.dumps(boundary_state))
        delivery_context = boundary_state["candidate"]["delivery_context"]
        self.assertTrue(delivery_context["context_complete"])
        self.assertEqual(delivery_context["delivering_agent_name"], "fixture Agent")
        self.assertEqual(delivery_context["deliverable_type"], "candidate-code-patch")
        self.assertEqual(delivery_context["intended_recipient_role"], "local-project-owner")
        self.assertEqual(
            delivery_context["clearance_state"],
            "pending-human-review-not-cleared",
        )
        self.assertEqual(
            boundary_state["questions"][0]["prompt"],
            "该审核包最多支持到哪一级交付范围？",
        )
        blocked = client.get(
            "/api/review/boundary_reconstruction/material",
            params={"item_token": boundary_state["item_token"]},
            headers={"X-Review-Token": boundary_state["review_token"]},
        )
        self.assertEqual(blocked.status_code, 409)

        full_state = client.get("/api/review/full_review_reference").json()
        self.assertTrue(full_state["local_material"]["available"])
        unauthorized = client.get(
            "/api/review/full_review_reference/material",
            params={"item_token": full_state["item_token"]},
        )
        self.assertEqual(unauthorized.status_code, 403)
        cross_origin = client.get(
            "/api/review/full_review_reference/material",
            params={"item_token": full_state["item_token"]},
            headers={
                "Origin": "https://example.invalid",
                "X-Review-Token": full_state["review_token"],
            },
        )
        self.assertEqual(cross_origin.status_code, 403)
        rejected = client.get(
            "/api/review/full_review_reference/material",
            params={"item_token": "stale-item-token"},
            headers={"X-Review-Token": full_state["review_token"]},
        )
        self.assertEqual(rejected.status_code, 409)
        material_response = client.get(
            "/api/review/full_review_reference/material",
            params={"item_token": full_state["item_token"]},
            headers={"X-Review-Token": full_state["review_token"]},
        )
        self.assertEqual(material_response.status_code, 200, material_response.text)
        material = material_response.json()
        self.assertIn("diff --git", material["candidate_patch"])
        self.assertIn("Public task context", material["issue_markdown"])
        self.assertFalse(material["persisted_to_human_session"])

        active_case_id = cockpit.queues["full_review_reference"].case_ids[0]
        patch_path = materials / active_case_id / "candidate.patch"
        original_patch = patch_path.read_text(encoding="utf-8")
        patch_path.write_text(original_patch + "\n# tampered\n", encoding="utf-8")
        tampered = client.get(
            "/api/review/full_review_reference/material",
            params={"item_token": full_state["item_token"]},
            headers={"X-Review-Token": full_state["review_token"]},
        )
        self.assertEqual(tampered.status_code, 409)
        self.assertIn("digest does not match", tampered.json()["detail"])
        patch_path.write_text(original_patch, encoding="utf-8")

        symlink_target = patch_path.with_name("candidate-copy.patch")
        symlink_target.write_text(original_patch, encoding="utf-8")
        patch_path.unlink()
        patch_path.symlink_to(symlink_target.name)
        symlinked = client.get(
            "/api/review/full_review_reference/material",
            params={"item_token": full_state["item_token"]},
            headers={"X-Review-Token": full_state["review_token"]},
        )
        self.assertEqual(symlinked.status_code, 409)
        self.assertIn("symbolic links", symlinked.json()["detail"])
        patch_path.unlink()
        patch_path.write_text(original_patch, encoding="utf-8")

        active_packet = json.loads(
            (output / "reviewer-packets" / f"{active_case_id}.json").read_text(encoding="utf-8")
        )
        answers = [
            str(
                next(
                    index
                    for index, option in enumerate(question.options, start=1)
                    if option.code == question.expected_code
                )
            )
            for question in boundary_questions(active_packet)
        ]
        submitted = client.post(
            "/api/review/submit",
            headers={"X-Review-Token": full_state["review_token"]},
            json={
                "mode": "full_review_reference",
                "item_token": full_state["item_token"],
                "answers": answers,
                "active_review_ms": 10,
                "nasa_tlx_score": 35,
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        session_text = (self.root / "human-sessions.jsonl").read_text(encoding="utf-8")
        session = HumanReviewSessionV1.model_validate_json(session_text)
        self.assertEqual(session.review_mode, "full_review_reference")
        self.assertFalse(session.measurement.raw_answers_included)
        session_payload = json.loads(session_text)
        self.assertNotIn("answers", session_payload)
        self.assertNotIn("raw_answers", session_payload)
        self.assertNotIn("diff --git", session_text)
        self.assertNotIn("Public task context", session_text)


if __name__ == "__main__":
    unittest.main()
