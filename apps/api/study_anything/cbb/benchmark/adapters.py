"""Read-only adapters for public benchmark task identities.

The adapters deliberately do not vendor upstream task prompts, patches, database
states, or injection payloads. They create immutable metadata references and
label-free candidate packets that can later be replaced by observed Agent runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from study_anything.cbb.benchmark.models import (
    BenchmarkCaseV1,
    BenchmarkSource,
    CandidateDeliveryV1,
    CaseClass,
    ClearanceDisposition,
    EvidenceObservationV1,
    EvidenceStatus,
    OfficialScorerOutcome,
    ReferenceDecisionV1,
    UpstreamSourceV1,
)
from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import DeliveryScope, PrivacyBoundaryV1


PILOT_SUITE_ID: Final = "pilot-v0.1"
STANDARD_REVIEW_TOOLS: Final = [
    "read_candidate_metadata",
    "read_evidence_metadata",
    "request_additional_evidence",
    "emit_clearance_decision",
]
SELECTION_LOCKED_AT: Final = "2026-07-12T00:00:00Z"
SELECTION_PROTOCOL_DIGEST: Final = canonical_sha256(
    {
        "schema_version": "paired-benchmark-selection-protocol-v0.1",
        "suite_id": PILOT_SUITE_ID,
        "safe_case_count": 20,
        "dangerous_case_count": 20,
        "replacement_after_scorer_execution_allowed": False,
    }
)


@dataclass(frozen=True)
class SourceDefinition:
    benchmark_id: BenchmarkSource
    version: str
    repository_uri: str
    task_data_revision: str
    scorer_revision: str
    license_id: Literal["MIT", "CC-BY-NC-4.0"]
    license_uri: str
    license_use_scope: Literal["permissive", "personal_noncommercial"]
    third_party_asset_terms_reviewed: bool


@dataclass(frozen=True)
class PublicCaseSeed:
    case_id: str
    task_id: str
    source_path: str
    task_snapshot_ref: str
    source_uri: str
    official_scorer_ref: str
    safe: bool
    task_summary_code: str
    dangerous_outcome: OfficialScorerOutcome
    dangerous_reason: str
    impact_severity: Literal["low", "medium", "high", "critical"]
    selection_amendment_ref: str | None = None
    selection_amendment_digest_sha256: str | None = None


SOURCE_DEFINITIONS: Final = {
    BenchmarkSource.SWE_BENCH_LIVE: SourceDefinition(
        benchmark_id=BenchmarkSource.SWE_BENCH_LIVE,
        version="multilang-js-2026-07-12",
        repository_uri="https://github.com/microsoft/SWE-bench-Live",
        task_data_revision="608f7ae9ab8ea1f9f0d030fe04562cf6bd1a0c8b",
        scorer_revision="70ec57e852e3f2d195790fe71f553e272c691833",
        license_id="MIT",
        license_uri=(
            "https://github.com/microsoft/SWE-bench-Live/blob/"
            "70ec57e852e3f2d195790fe71f553e272c691833/LICENSE"
        ),
        license_use_scope="permissive",
        third_party_asset_terms_reviewed=True,
    ),
    BenchmarkSource.TUA_BENCH: SourceDefinition(
        benchmark_id=BenchmarkSource.TUA_BENCH,
        version="2026-07-12",
        repository_uri="https://github.com/facebookresearch/TUA-Bench",
        task_data_revision="3497fd320abcafaf4797424192c891a593fd7964",
        scorer_revision="3497fd320abcafaf4797424192c891a593fd7964",
        license_id="CC-BY-NC-4.0",
        license_uri=(
            "https://github.com/facebookresearch/TUA-Bench/blob/"
            "3497fd320abcafaf4797424192c891a593fd7964/LICENSE"
        ),
        license_use_scope="personal_noncommercial",
        third_party_asset_terms_reviewed=False,
    ),
    BenchmarkSource.TAU_BENCH: SourceDefinition(
        benchmark_id=BenchmarkSource.TAU_BENCH,
        version="tau3-base-2026-07-12",
        repository_uri="https://github.com/sierra-research/tau2-bench",
        task_data_revision="1901a301961cbbe3fd11f3e84a2a376530c759e3",
        scorer_revision="1901a301961cbbe3fd11f3e84a2a376530c759e3",
        license_id="MIT",
        license_uri=(
            "https://github.com/sierra-research/tau2-bench/blob/"
            "1901a301961cbbe3fd11f3e84a2a376530c759e3/LICENSE"
        ),
        license_use_scope="permissive",
        third_party_asset_terms_reviewed=True,
    ),
    BenchmarkSource.AGENTDOJO: SourceDefinition(
        benchmark_id=BenchmarkSource.AGENTDOJO,
        version="v1.2.2",
        repository_uri="https://github.com/ethz-spylab/agentdojo",
        task_data_revision="089ed468cf3ed0322acc66b0211f26d9d90dbf60",
        scorer_revision="089ed468cf3ed0322acc66b0211f26d9d90dbf60",
        license_id="MIT",
        license_uri=(
            "https://github.com/ethz-spylab/agentdojo/blob/"
            "089ed468cf3ed0322acc66b0211f26d9d90dbf60/LICENSE"
        ),
        license_use_scope="permissive",
        third_party_asset_terms_reviewed=True,
    ),
}


def benchmark_privacy() -> PrivacyBoundaryV1:
    return PrivacyBoundaryV1(
        metadata_only=True,
        raw_source_text_included=False,
        raw_report_text_included=False,
        raw_customer_payload_included=False,
        attention_stream_included=False,
        model_prompts_included=False,
        model_credentials_included=False,
        cookies_or_bearer_tokens_included=False,
        signed_urls_included=False,
        production_mutation_performed=False,
        automatic_customer_send_performed=False,
    )


class PublicBenchmarkAdapter:
    """Convert one pinned public task identity into benchmark contracts."""

    def __init__(self, source: SourceDefinition) -> None:
        self.source = source

    def build(self, seed: PublicCaseSeed) -> tuple[BenchmarkCaseV1, CandidateDeliveryV1]:
        environment_digest = canonical_sha256(
            {
                "benchmark_id": self.source.benchmark_id.value,
                "task_data_revision": self.source.task_data_revision,
                "scorer_revision": self.source.scorer_revision,
                "source_path": seed.source_path,
                "task_id": seed.task_id,
                "task_snapshot_ref": seed.task_snapshot_ref,
                "official_scorer_ref": seed.official_scorer_ref,
            }
        )
        source = UpstreamSourceV1(
            benchmark_id=self.source.benchmark_id,
            benchmark_version=self.source.version,
            upstream_task_id=seed.task_id,
            source_uri=seed.source_uri,
            source_revision=self.source.task_data_revision,
            scorer_source_uri=self.source.repository_uri,
            scorer_source_revision=self.source.scorer_revision,
            source_path=seed.source_path,
            task_snapshot_ref=seed.task_snapshot_ref,
            environment_digest_sha256=environment_digest,
            digest_basis="task_data_plus_scorer_identity",
            environment_digest_basis="declared_source_identities",
            official_scorer_ref=seed.official_scorer_ref,
            license_id=self.source.license_id,
            license_uri=self.source.license_uri,
            license_use_scope=self.source.license_use_scope,
            third_party_asset_terms_reviewed=self.source.third_party_asset_terms_reviewed,
            upstream_payload_vendored=False,
        )

        safe = seed.safe
        safe_recipe = {
            BenchmarkSource.SWE_BENCH_LIVE: "gold-patch-control",
            BenchmarkSource.TUA_BENCH: "verified-success-artifact-control",
            BenchmarkSource.TAU_BENCH: "policy-compliant-trajectory-control",
            BenchmarkSource.AGENTDOJO: "utility-success-no-attack-control",
        }[self.source.benchmark_id]
        dangerous_recipe = {
            BenchmarkSource.SWE_BENCH_LIVE: "deterministic-patch-regression-variant",
            BenchmarkSource.TUA_BENCH: "deterministic-verifier-failure-variant",
            BenchmarkSource.TAU_BENCH: "deterministic-policy-violation-variant",
            BenchmarkSource.AGENTDOJO: "frozen-injection-attack-variant",
        }[self.source.benchmark_id]
        candidate_recipe_code = safe_recipe if safe else dangerous_recipe
        candidate_recipe_digest = canonical_sha256(
            {
                "suite_id": PILOT_SUITE_ID,
                "case_id": seed.case_id,
                "upstream_task_id": seed.task_id,
                "candidate_recipe_code": candidate_recipe_code,
                "selection_protocol_digest_sha256": SELECTION_PROTOCOL_DIGEST,
            }
        )
        scorer_outcome = OfficialScorerOutcome.PASSED if safe else seed.dangerous_outcome
        scorer_status = EvidenceStatus.PASSED if safe else EvidenceStatus.FAILED
        scorer_summary = "official-scorer-passed" if safe else seed.dangerous_reason
        subject_digest = canonical_sha256(
            {
                "suite_id": PILOT_SUITE_ID,
                "case_id": seed.case_id,
                "task_id": seed.task_id,
                "fixture_variant": "safe" if safe else "dangerous",
            }
        )
        context_digest = canonical_sha256(
            {
                "task_summary_code": seed.task_summary_code,
                "target_scope": DeliveryScope.PERSONAL_LOCAL.value,
                "tool_permission_ids": STANDARD_REVIEW_TOOLS,
            }
        )
        evidence = [
            self._evidence(
                evidence_type="source-provenance",
                status=EvidenceStatus.PASSED,
                evidence_ref=f"source:{seed.case_id}",
                summary_code="source-revision-and-task-pinned",
                blocking=True,
                seed=seed,
            ),
            self._evidence(
                evidence_type="scorer-result",
                status=scorer_status,
                evidence_ref=f"synthetic-scorer-fixture:{seed.case_id}",
                summary_code=scorer_summary,
                blocking=True,
                seed=seed,
            ),
            self._evidence(
                evidence_type="scope-boundary",
                status=EvidenceStatus.PASSED,
                evidence_ref=f"scope:{seed.case_id}",
                summary_code="personal-local-only",
                blocking=True,
                seed=seed,
            ),
            self._evidence(
                evidence_type="rollback-or-containment",
                status=EvidenceStatus.PASSED,
                evidence_ref=f"rollback:{seed.case_id}",
                summary_code="fixture-reset-available",
                blocking=True,
                seed=seed,
            ),
            self._evidence(
                evidence_type="responsibility-boundary",
                status=EvidenceStatus.PASSED,
                evidence_ref=f"responsibility:{seed.case_id}",
                summary_code="local-project-owner-responsible",
                blocking=True,
                seed=seed,
            ),
        ]
        candidate = CandidateDeliveryV1(
            schema_version="candidate-delivery-v1",
            suite_id=PILOT_SUITE_ID,
            case_id=seed.case_id,
            candidate_id=f"candidate:{seed.case_id}",
            subject_digest_sha256=subject_digest,
            source_snapshot_digest_sha256=environment_digest,
            context_digest_sha256=context_digest,
            task_summary_code=seed.task_summary_code,
            evidence_origin="mechanism_fixture",
            declared_risk_level=seed.impact_severity,
            target_scope=DeliveryScope.PERSONAL_LOCAL,
            intended_recipient_role="local-project-owner",
            risk_owner_role="local-project-owner",
            prohibited_use_codes=["customer-handoff", "production-execution"],
            scorer_outcome=scorer_outcome,
            scorer_execution_origin="synthetic_mechanism_fixture",
            official_scorer_executed=False,
            scorer_trace_digest_sha256=None,
            evidence=evidence,
            tool_permission_ids=list(STANDARD_REVIEW_TOOLS),
            reference_label_included=False,
            hidden_tests_included=False,
            privacy=benchmark_privacy(),
        )
        candidate_digest = canonical_sha256(candidate)
        reference = ReferenceDecisionV1(
            disposition=(ClearanceDisposition.CLEARED if safe else ClearanceDisposition.HELD),
            release_authorized=safe,
            maximum_scope=(DeliveryScope.PERSONAL_LOCAL if safe else DeliveryScope.BLOCKED),
            rationale_codes=(
                ["official-scorer-passed", "scope-within-personal-local"]
                if safe
                else [seed.dangerous_reason, "blocking-evidence-failed"]
            ),
            adjudication_basis="synthetic_scorer_fixture_plus_frozen_clearance_policy",
            adjudication_trace_digest_sha256=None,
        )
        case = BenchmarkCaseV1(
            schema_version="benchmark-case-v1",
            suite_id=PILOT_SUITE_ID,
            case_id=seed.case_id,
            case_class=CaseClass.SAFE if safe else CaseClass.DANGEROUS,
            impact_severity=seed.impact_severity,
            target_scope=DeliveryScope.PERSONAL_LOCAL,
            source=source,
            candidate_ref=f"candidate:{seed.case_id}",
            candidate_digest_sha256=candidate_digest,
            candidate_assignment=(
                "known_safe_control" if safe else "precommitted_dangerous_variant"
            ),
            candidate_recipe_code=candidate_recipe_code,
            candidate_recipe_digest_sha256=candidate_recipe_digest,
            selection_protocol_digest_sha256=SELECTION_PROTOCOL_DIGEST,
            selection_locked_at=SELECTION_LOCKED_AT,
            selection_amendment_ref=seed.selection_amendment_ref,
            selection_amendment_digest_sha256=seed.selection_amendment_digest_sha256,
            reference=reference,
            reference_hidden_from_reviewers=True,
            license_review_complete=True,
        )
        return case, candidate

    @staticmethod
    def _evidence(
        *,
        evidence_type: str,
        status: EvidenceStatus,
        evidence_ref: str,
        summary_code: str,
        blocking: bool,
        seed: PublicCaseSeed,
    ) -> EvidenceObservationV1:
        return EvidenceObservationV1(
            evidence_type=evidence_type,
            status=status,
            evidence_ref=evidence_ref,
            evidence_digest_sha256=canonical_sha256(
                {
                    "case_id": seed.case_id,
                    "evidence_type": evidence_type,
                    "status": status.value,
                    "summary_code": summary_code,
                }
            ),
            summary_code=summary_code,
            blocking=blocking,
        )


def adapters() -> dict[BenchmarkSource, PublicBenchmarkAdapter]:
    return {
        source_id: PublicBenchmarkAdapter(definition)
        for source_id, definition in SOURCE_DEFINITIONS.items()
    }
