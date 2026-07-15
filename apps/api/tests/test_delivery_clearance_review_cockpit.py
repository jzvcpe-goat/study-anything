from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.cbb.benchmark.adapters import benchmark_privacy
from study_anything.cbb.benchmark.fixtures import PILOT_SUITE_ID, pilot_assets
from study_anything.cbb.benchmark.human_reconstruction import boundary_questions
from study_anything.cbb.benchmark.models import (
    BenchmarkSource,
    HumanReviewSessionV1,
    ScorerExecutionReceiptV1,
)
from study_anything.cbb.benchmark.review_cockpit import (
    ReviewCockpit,
    create_review_cockpit_app,
    load_canonical_mode_configs,
)
from study_anything.cbb.benchmark.runner import reviewer_candidate_view
from study_anything.cbb.protocol.canonical import canonical_sha256


BENCHMARK_TIMESTAMP = "2026-07-13T12:00:00Z"


def _review_packet(case_id: str = "dojo-01") -> dict[str, object]:
    case, candidate = next(
        (case, candidate) for case, candidate in pilot_assets() if case.case_id == case_id
    )
    return {
        "schema_version": "reviewer-case-packet-v1",
        "suite_id": case.suite_id,
        "case_id": case.case_id,
        "target_scope": case.target_scope.value,
        "source": case.source.model_dump(mode="json"),
        "candidate": reviewer_candidate_view(candidate),
        "official_scorer_result_included": False,
        "reference_label_included": False,
        "hidden_tests_included": False,
    }


def _adjudication_packet(case_id: str = "dojo-01") -> dict[str, object]:
    case, candidate = next(
        (case, candidate) for case, candidate in pilot_assets() if case.case_id == case_id
    )
    scorer_payload: dict[str, object] = {
        "schema_version": "scorer-execution-receipt-v1",
        "receipt_id": f"scorer:{case_id}",
        "suite_id": PILOT_SUITE_ID,
        "case_id": case_id,
        "benchmark_id": case.source.benchmark_id.value,
        "upstream_task_id": case.source.upstream_task_id,
        "subject_digest_sha256": candidate.subject_digest_sha256,
        "source_environment_digest_sha256": candidate.source_snapshot_digest_sha256,
        "scorer_source_uri": case.source.scorer_source_uri,
        "scorer_source_revision": case.source.scorer_source_revision,
        "official_scorer_ref": case.source.official_scorer_ref,
        "dependency_lock_digest_sha256": "1" * 64,
        "asset_manifest_digest_sha256": "2" * 64,
        "runtime_image_digests_sha256": [],
        "command_digest_sha256": "3" * 64,
        "scorer_output_digest_sha256": "4" * 64,
        "outcome": candidate.scorer_outcome.value,
        "numeric_reward": (
            (1.0 if candidate.scorer_outcome.value == "passed" else 0.0)
            if case.source.benchmark_id in {BenchmarkSource.TUA_BENCH, BenchmarkSource.TAU_BENCH}
            else None
        ),
        "utility_passed": (True if case.source.benchmark_id == BenchmarkSource.AGENTDOJO else None),
        "security_passed": (
            candidate.scorer_outcome.value != "security_violation"
            if case.source.benchmark_id == BenchmarkSource.AGENTDOJO
            else None
        ),
        "exit_code": 0,
        "official_scorer_executed": True,
        "started_at": BENCHMARK_TIMESTAMP,
        "completed_at": BENCHMARK_TIMESTAMP,
        "raw_scorer_output_included": False,
        "raw_hidden_tests_included": False,
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    scorer = ScorerExecutionReceiptV1.model_validate(
        {**scorer_payload, "trace_digest_sha256": canonical_sha256(scorer_payload)}
    )
    candidate_payload = candidate.model_dump(mode="json")
    candidate_payload.update(
        {
            "evidence_origin": "observed_agent_run",
            "scorer_execution_origin": "observed_official_scorer",
            "official_scorer_executed": True,
            "scorer_trace_digest_sha256": scorer.trace_digest_sha256,
        }
    )
    for evidence in candidate_payload["evidence"]:
        if evidence["evidence_type"] == "scorer-result":
            evidence["evidence_ref"] = f"scorer-receipt:{scorer.receipt_id}"
            evidence["evidence_digest_sha256"] = scorer.trace_digest_sha256
    candidate = type(candidate).model_validate(candidate_payload)
    protocol = {
        "schema_version": "blinded-clearance-adjudication-protocol-v1",
        "maximum_authority": "personal_local",
        "arm_decisions_accessible": False,
        "arm_identities_accessible": False,
        "official_scorer_is_supporting_not_sufficient": True,
        "required_outputs": [
            "disposition",
            "release_authorized",
            "maximum_scope",
            "rationale_codes",
        ],
    }
    return {
        "schema_version": "blinded-adjudication-packet-v1",
        "suite_id": PILOT_SUITE_ID,
        "case_id": case_id,
        "candidate": candidate.model_dump(mode="json"),
        "scorer_receipt": scorer.model_dump(mode="json"),
        "protocol": protocol,
        "adjudication_protocol_digest_sha256": canonical_sha256(protocol),
        "arm_decisions_accessible": False,
        "arm_identities_accessible": False,
        "model_reviewer_outputs_included": False,
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }


class ReviewCockpitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        reviewer_packets = self.root / "reviewer-packets"
        adjudication_packets = self.root / "adjudication-packets"
        reviewer_packets.mkdir()
        adjudication_packets.mkdir()
        self.packet = _review_packet()
        (reviewer_packets / "dojo-01.json").write_text(json.dumps(self.packet), encoding="utf-8")
        (adjudication_packets / "dojo-01.json").write_text(
            json.dumps(_adjudication_packet()), encoding="utf-8"
        )
        self.protocol_path = self.root / "human-protocol.json"
        self.protocol_path.write_text(
            json.dumps(
                {
                    "schema_version": "benchmark-human-protocol-v1",
                    "boundary_reconstruction": {
                        "packet_dir": "reviewer-packets",
                        "output": "human-sessions.jsonl",
                        "reviewer_role": "local-project-owner",
                        "order_seed": "boundary-seed",
                        "max_items_per_batch": 10,
                    },
                    "full_review_reference": {
                        "packet_dir": "reviewer-packets",
                        "output": "human-sessions.jsonl",
                        "reviewer_role": "local-project-owner",
                        "order_seed": "full-seed",
                        "max_items_per_batch": 10,
                    },
                    "blinded_adjudication": {
                        "packet_dir": "adjudication-packets",
                        "output": "adjudications.jsonl",
                        "adjudicator_role": "local-project-owner-adjudicator",
                        "order_seed": "adjudication-seed",
                        "max_items_per_batch": 10,
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
        configs = load_canonical_mode_configs(
            self.root,
            self.protocol_path,
            max_items=1,
        )
        self.cockpit = ReviewCockpit(configs)
        self.client = TestClient(create_review_cockpit_app(self.cockpit))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _correct_answers(self) -> list[str]:
        answers: list[str] = []
        for question in boundary_questions(self.packet):
            answers.append(
                str(
                    next(
                        index
                        for index, option in enumerate(question.options, start=1)
                        if option.code == question.expected_code
                    )
                )
            )
        return answers

    def _prepare(
        self,
        mode: str,
        state: dict[str, object],
        *,
        responsibility: str = "local_delivery_owner",
        reviewable_materials: list[str] | None = None,
        intended_next_step: str = "personal_local_validation",
    ) -> dict[str, object]:
        materials = reviewable_materials or ["scope_and_responsibility"]
        response = self.client.post(
            "/api/review/prepare",
            headers={"X-Review-Token": str(state["review_token"])},
            json={
                "mode": mode,
                "item_token": state["item_token"],
                "responsibility": responsibility,
                "reviewable_materials": materials,
                "intended_next_step": intended_next_step,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_cockpit_is_blinded_and_sets_local_security_headers(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Human Review Cockpit", page.text)
        self.assertEqual(page.headers["cache-control"], "no-store")
        self.assertEqual(page.headers["x-frame-options"], "DENY")

        state = self.client.get("/api/review/boundary_reconstruction")
        self.assertEqual(state.status_code, 200)
        payload = state.json()
        serialized = json.dumps(payload)
        self.assertNotIn("dojo-01", serialized)
        self.assertNotIn("expected_code", serialized)
        self.assertEqual(payload["maximum_scope"], "personal_local")
        self.assertFalse(payload["independent_reviewer_claimed"])
        self.assertEqual(payload["default_presentation_profile"], "plain_language")
        self.assertFalse(payload["presentation_profile_changes_authority"])
        self.assertFalse(payload["professional_qualification_claimed"])
        self.assertTrue(payload["review_preflight"]["required_before_evidence_display"])
        self.assertFalse(payload["review_preflight"]["raw_answers_persisted"])
        self.assertEqual(len(payload["review_preflight"]["questions"]), 3)
        self.assertEqual(payload["preparation_status"], "required")
        self.assertNotIn("candidate", payload)
        self.assertNotIn("questions", payload)
        self.assertEqual(
            {item["profile_id"] for item in payload["presentation_profiles"]},
            {
                "plain_language",
                "product_owner",
                "software_engineer",
                "security_audit",
                "technical_codes",
            },
        )
        self._prepare("boundary_reconstruction", payload)
        payload = self.client.get("/api/review/boundary_reconstruction").json()
        self.assertEqual(payload["preparation_status"], "ready")
        assignment = payload["review_assignment"]
        self.assertFalse(assignment["professional_qualification_claimed"])
        self.assertIn("不要求阅读代码", assignment["views"]["plain_language"]["not_your_task"])
        for question in payload["questions"]:
            self.assertEqual(question["prompt"], question["views"]["plain_language"]["prompt"])
            self.assertEqual(
                len(question["views"]["plain_language"]["options"]),
                len(question["views"]["software_engineer"]["options"]),
            )
            self.assertEqual(len(question["views"]["technical_codes"]["options"]), 3)

    def test_boundary_and_full_review_write_aggregate_only_sessions(self) -> None:
        profiles = {
            "boundary_reconstruction": "plain_language",
            "full_review_reference": "software_engineer",
        }
        for mode in ("boundary_reconstruction", "full_review_reference"):
            state = self.client.get(f"/api/review/{mode}").json()
            preparation = self._prepare(
                mode,
                state,
                reviewable_materials=(
                    ["code_patch_and_tests"]
                    if mode == "full_review_reference"
                    else ["scope_and_responsibility"]
                ),
            )
            response = self.client.post(
                "/api/review/submit",
                headers={"X-Review-Token": state["review_token"]},
                json={
                    "mode": mode,
                    "item_token": state["item_token"],
                    "preparation_token": preparation["preparation_token"],
                    "presentation_profile": profiles[mode],
                    "answers": self._correct_answers(),
                    "active_review_ms": 250,
                    "nasa_tlx_score": 35,
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], "complete")

        lines = (self.root / "human-sessions.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        sessions = [HumanReviewSessionV1.model_validate_json(line) for line in lines]
        self.assertEqual(
            {session.review_mode for session in sessions},
            {
                "boundary_reconstruction",
                "full_review_reference",
            },
        )
        self.assertTrue(
            all(session.measurement.boundary_questions_correct == 5 for session in sessions)
        )
        self.assertTrue(
            all(session.measurement.raw_answers_included is False for session in sessions)
        )
        self.assertEqual(
            {session.measurement.presentation_profile for session in sessions},
            {"plain_language", "software_engineer"},
        )
        self.assertTrue(
            all(session.measurement.professional_qualification_claimed is False for session in sessions)
        )
        self.assertEqual(
            {session.measurement.review_entry_route for session in sessions},
            {"boundary_review_supported", "full_review_supported"},
        )
        self.assertTrue(
            all(session.measurement.review_preflight_method == "questionnaire_v1" for session in sessions)
        )
        self.assertTrue(
            all(
                session.measurement.review_preflight_policy_digest_sha256 is not None
                for session in sessions
            )
        )
        self.assertTrue(
            all(session.measurement.raw_preflight_answers_included is False for session in sessions)
        )
        self.assertEqual(
            len({session.question_set_digest_sha256 for session in sessions}),
            1,
        )
        self.assertTrue(all("answers" not in json.loads(line) for line in lines))

    def test_invalid_presentation_profile_is_rejected(self) -> None:
        state = self.client.get("/api/review/boundary_reconstruction").json()
        response = self.client.post(
            "/api/review/submit",
            headers={"X-Review-Token": state["review_token"]},
            json={
                "mode": "boundary_reconstruction",
                "item_token": state["item_token"],
                "presentation_profile": "pretend-expert",
                "answers": self._correct_answers(),
                "active_review_ms": 100,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_preflight_routes_scope_and_capability_before_review(self) -> None:
        boundary = self.client.get("/api/review/boundary_reconstruction").json()
        observer = self._prepare(
            "boundary_reconstruction",
            boundary,
            responsibility="observer_without_clearance_authority",
            reviewable_materials=["none_or_unsure"],
        )
        self.assertTrue(observer["can_begin_review"])
        self.assertEqual(observer["review_entry_route"], "observer_boundary_only")
        self.assertEqual(observer["recommended_presentation_profile"], "plain_language")
        self.assertNotIn("responsibility", observer)
        self.assertFalse(observer["raw_preflight_answers_persisted"])

        beyond_scope = self._prepare(
            "boundary_reconstruction",
            boundary,
            intended_next_step="customer_handoff",
        )
        self.assertFalse(beyond_scope["can_begin_review"])
        self.assertEqual(beyond_scope["review_entry_route"], "scope_escalation_required")

        full = self.client.get("/api/review/full_review_reference").json()
        routed = self._prepare("full_review_reference", full)
        self.assertFalse(routed["can_begin_review"])
        self.assertEqual(routed["review_entry_route"], "qualified_reviewer_required")
        self.assertIn("软件工程师", str(routed["required_reviewer"]))

        supported = self._prepare(
            "full_review_reference",
            full,
            responsibility="software_quality_reviewer",
            reviewable_materials=["code_patch_and_tests"],
        )
        self.assertTrue(supported["can_begin_review"])
        self.assertEqual(supported["review_entry_route"], "full_review_supported")
        self.assertEqual(supported["recommended_presentation_profile"], "software_engineer")

    def test_review_submission_requires_completed_preflight(self) -> None:
        state = self.client.get("/api/review/boundary_reconstruction").json()
        response = self.client.post(
            "/api/review/submit",
            headers={"X-Review-Token": state["review_token"]},
            json={
                "mode": "boundary_reconstruction",
                "item_token": state["item_token"],
                "answers": self._correct_answers(),
                "active_review_ms": 100,
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("preparation questionnaire is required", response.text)

    def test_adjudication_writes_bounded_receipt(self) -> None:
        state = self.client.get("/api/review/blinded_adjudication").json()
        preparation = self._prepare("blinded_adjudication", state)
        response = self.client.post(
            "/api/review/submit",
            headers={"X-Review-Token": state["review_token"]},
            json={
                "mode": "blinded_adjudication",
                "item_token": state["item_token"],
                "preparation_token": preparation["preparation_token"],
                "disposition": "restricted",
                "rationale_codes": ["scope-bounded", "scorer-supporting-only"],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        receipt = json.loads((self.root / "adjudications.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(receipt["maximum_scope"], "personal_local")
        self.assertFalse(receipt["arm_identities_accessible"])
        self.assertFalse(receipt["raw_adjudication_notes_included"])

    def test_submission_requires_same_origin_token(self) -> None:
        state = self.client.get("/api/review/boundary_reconstruction").json()
        payload = {
            "mode": "boundary_reconstruction",
            "item_token": state["item_token"],
            "answers": self._correct_answers(),
            "active_review_ms": 100,
        }
        missing = self.client.post("/api/review/submit", json=payload)
        self.assertEqual(missing.status_code, 403)
        cross_origin = self.client.post(
            "/api/review/submit",
            headers={
                "X-Review-Token": state["review_token"],
                "Origin": "https://example.com",
            },
            json=payload,
        )
        self.assertEqual(cross_origin.status_code, 403)
        cross_port = self.client.post(
            "/api/review/submit",
            headers={
                "X-Review-Token": state["review_token"],
                "Origin": "http://testserver:8765",
            },
            json=payload,
        )
        self.assertEqual(cross_port.status_code, 403)


if __name__ == "__main__":
    unittest.main()
