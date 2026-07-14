from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from _path import ROOT  # noqa: F401

from study_anything.cbb.benchmark.human_reconstruction import boundary_questions
from study_anything.cbb.benchmark.real_agent_cases import (
    RealAgentCaseSetV1,
    RealAgentSelectionProtocolV1,
    build_real_agent_case_set,
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


if __name__ == "__main__":
    unittest.main()
