from __future__ import annotations

import hashlib
import json
import unittest

from _path import ROOT  # noqa: F401

from study_anything.core.learning_package import build_learning_package_export
from study_anything.core.second_brain_handoff import build_second_brain_handoff
from study_anything.core.workflow import (
    Answer,
    EnrichmentItem,
    GradingResult,
    LearningState,
    Mastery,
    QuizItem,
    ReadingSource,
)


class SecondBrainHandoffTests(unittest.TestCase):
    def test_handoff_is_idempotent_redacted_and_archive_hashes_match(self) -> None:
        private_source = "Private source text that must never appear in the second-brain handoff."
        private_enrichment = "Private enrichment text that must stay outside archives."
        private_answer = "Private learner answer that belongs only to the learner session."
        state = LearningState(
            session_id="session-second-brain-12345678",
            user_id="private-user",
            user_hash="hash-user",
            track="PRODUCT",
            stage="completed",
            source=ReadingSource(
                source_type="article",
                reference="https://example.test/source",
                title="Second Brain Source",
                text=private_source,
                excerpt_hash="source-hash",
                verified=True,
            ),
            enrichment_items=[
                EnrichmentItem(
                    source_type="obsidian_note",
                    reference="obsidian://vault/AI PM/Note",
                    title="AI PM Note",
                    text=private_enrichment,
                    excerpt_hash="enrichment-hash",
                    locator="heading=Learning systems",
                    metadata={
                        "provenance": {
                            "collector": "test-platform-agent",
                            "capture_method": "obsidian_excerpt",
                            "source_owner": "user",
                        },
                        "redaction_policy": "reference_only",
                        "obsidian_backlinks": ["[[AI PM]]", "NotebookLM | Bridge"],
                    },
                )
            ],
            teaching_layers=[
                {
                    "layer": "overview",
                    "task_type": "teach.overview",
                    "content": "A generated overview is safe to reuse.",
                    "citations": ["source-hash"],
                    "confidence": 0.8,
                    "agent": {
                        "provider_id": "private-agent",
                        "endpoint": "http://127.0.0.1:8787/private-agent",
                        "metadata": {"endpoint": "http://127.0.0.1:8787/private-agent"},
                    },
                }
            ],
            quiz_items=[
                QuizItem(
                    item_id="quiz-1",
                    prompt="Explain the core idea.",
                    source_ref="https://example.test/source",
                    excerpt_hash="source-hash",
                    rubric="Ground the answer in the source.",
                )
            ],
            answers=[Answer(item_id="quiz-1", text=private_answer)],
            grading_results=[
                GradingResult(
                    item_id="quiz-1",
                    score=0.9,
                    feedback="Private grading feedback.",
                    reward=1.0,
                )
            ],
            mastery=Mastery(level=0.9, bloom="apply"),
            insights=["Generated insight is allowed in the user-owned handoff."],
        )

        learning_package = build_learning_package_export(state)
        first = build_second_brain_handoff(state)
        second = build_second_brain_handoff(state)

        package_serialized = json.dumps(learning_package, ensure_ascii=False)
        self.assertNotIn("127.0.0.1:8787/private-agent", package_serialized)
        self.assertEqual(
            learning_package["teaching_layers"][0]["agent"]["provider_id"],
            "private-agent",
        )
        self.assertFalse(learning_package["privacy"]["agent_endpoints_included"])
        self.assertFalse(learning_package["privacy"]["agent_metadata_included"])

        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], "second-brain-handoff-v1")
        self.assertEqual(first["obsidian"]["schema_version"], "second-brain-obsidian-note-v1")
        self.assertEqual(
            first["local_archive"]["manifest"]["schema_version"],
            "second-brain-archive-manifest-v1",
        )
        self.assertEqual(first["notebooklm_bridge"]["official_notebooklm_api_required"], False)
        self.assertIn("[[AI PM]]", first["obsidian"]["backlinks"])
        self.assertIn("[[NotebookLM - Bridge]]", first["obsidian"]["backlinks"])
        self.assertIn("## Review Queue", first["obsidian"]["markdown"])
        self.assertIn("Answer: _not included in second-brain handoff_", first["obsidian"]["markdown"])

        serialized = json.dumps(first, ensure_ascii=False)
        self.assertNotIn(private_source, serialized)
        self.assertNotIn(private_enrichment, serialized)
        self.assertNotIn(private_answer, serialized)
        self.assertNotIn("Private grading feedback.", serialized)
        self.assertNotIn("127.0.0.1:8787/private-agent", serialized)
        self.assertFalse(first["privacy"]["learner_answers_included"])
        self.assertFalse(first["privacy"]["grading_feedback_included"])
        self.assertFalse(first["privacy"]["agent_metadata_included"])

        files = first["local_archive"]["files"]
        manifest_files = {
            item["path"]: item for item in first["local_archive"]["manifest"]["files"]
        }
        self.assertGreaterEqual(len(files), 4)
        for file in files:
            digest = hashlib.sha256(str(file["content"]).encode("utf-8")).hexdigest()
            self.assertEqual(file["sha256"], digest)
            self.assertEqual(manifest_files[file["path"]]["sha256"], digest)


if __name__ == "__main__":
    unittest.main()
