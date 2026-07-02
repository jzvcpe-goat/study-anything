"""Tamper-evident Cognitive Black Box receipt chains.

This module extends the CBB protocol core with a metadata-only receipt chain and
self-intake reference implementation. It uses PR #285 as a deterministic real
repository delivery sample without reading raw diffs, raw source, customer data,
model prompts, secrets, or browser/session traces.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from study_anything.core import cbb_protocol, dual_loop


CBB_RECEIPT_CHAIN_SCHEMA_VERSION = "cbb-receipt-chain-v1"
CBB_SELF_INTAKE_RECEIPT_SCHEMA_VERSION = "cbb-self-intake-receipt-v1"
CBB_DELIVERY_EVIDENCE_PACK_SCHEMA_VERSION = "cbb-delivery-evidence-pack-v1"

CBB_RECEIPT_CHAIN_REPORT_SCHEMA_VERSION = "cbb-receipt-chain-verification-v1"
CBB_SELF_INTAKE_REPORT_SCHEMA_VERSION = "cbb-self-intake-verification-v1"

PROJECT_ID = "study-anything"
REPOSITORY = "jzvcpe-goat/study-anything"
PR_285_NUMBER = 285
PR_285_TITLE = "Add Cognitive Black Box protocol core"
PR_285_URL = "https://github.com/jzvcpe-goat/study-anything/pull/285"
PR_285_HEAD_REF = "codex/v0.3.157-cbb-protocol-core"
PR_285_BASE_REF = "main"
PR_285_MERGE_COMMIT = "f88d2ddbe4142c59d0a0f98bb9c7930b824d0fd4"
PR_285_MERGED_AT = "2026-07-02T11:39:49Z"

REQUIRED_CI_CHECKS = ("api-tests", "compose-smoke")

PR_285_CHECKS = [
    {
        "name": "api-tests",
        "status": "pass",
        "duration_seconds": 131,
        "run_ref": "actions/runs/28587029112/jobs/84761086096",
    },
    {
        "name": "compose-smoke",
        "status": "pass",
        "duration_seconds": 71,
        "run_ref": "actions/runs/28587029112/jobs/84761086090",
    },
]

ALLOWED_SELF_INTAKE_DECISIONS = (
    "self_intake_passed",
    "block_self_intake",
)


class CBBReceiptChainError(ValueError):
    """Raised when CBB receipt-chain evidence is unsafe or invalid."""


def _base_artifact(schema_version: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(cbb_protocol.CBB_PRIVACY_FLAGS),
    }


def _require_object(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise CBBReceiptChainError(f"{label}.{key} must be an object")
    return value


def _require_list(payload: Mapping[str, Any], key: str, *, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise CBBReceiptChainError(f"{label}.{key} must be a list")
    return value


def _require_nonempty_list(payload: Mapping[str, Any], key: str, *, label: str) -> list[Any]:
    value = _require_list(payload, key, label=label)
    if not value:
        raise CBBReceiptChainError(f"{label}.{key} must be non-empty")
    return value


def digest_payload(payload: Mapping[str, Any]) -> str:
    """Return the deterministic digest used by CBB receipt chains."""

    return dual_loop.sha256_text(cbb_protocol.dump_json(payload))


def _digest_shape(payload: Mapping[str, Any], *, omit: set[str]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in payload.items() if key not in omit}


def compute_receipt_chain_digest(payload: Mapping[str, Any]) -> str:
    return digest_payload(_digest_shape(payload, omit={"chain_digest"}))


def compute_evidence_pack_digest(payload: Mapping[str, Any]) -> str:
    return digest_payload(_digest_shape(payload, omit={"pack_digest"}))


def default_pr_285_source(*, merge_commit: str = PR_285_MERGE_COMMIT) -> dict[str, Any]:
    return {
        "source_type": "github_pull_request",
        "repository": REPOSITORY,
        "pr_number": PR_285_NUMBER,
        "pr_url": PR_285_URL,
        "title": PR_285_TITLE,
        "head_ref": PR_285_HEAD_REF,
        "base_ref": PR_285_BASE_REF,
        "merge_commit": merge_commit,
        "merged_at": PR_285_MERGED_AT,
    }


def default_pr_285_checks(*, missing_ci: bool = False) -> list[dict[str, Any]]:
    checks = deepcopy(PR_285_CHECKS)
    if missing_ci:
        return [check for check in checks if check["name"] != "compose-smoke"]
    return checks


def _pr_285_claim_boundary(*, scope_expansion: bool = False) -> dict[str, Any]:
    claim = cbb_protocol.claim_boundary_demo()
    claim.update(
        {
            "claim_id": "claim-boundary-pr-285",
            "project_id": PROJECT_ID,
            "candidate_artifact_ref": f"github-pr:{PR_285_NUMBER}@{PR_285_MERGE_COMMIT[:12]}",
            "current_claim": (
                "PR 285 may be treated as a controlled CBB reference-implementation "
                "handoff after local CBB gates and required GitHub CI checks passed."
            ),
            "allowed_scope": (
                "controlled_customer_handoff" if not scope_expansion else "production_customer_handoff"
            ),
            "not_claimed": [
                "production customer trust",
                "legal certification",
                "security certification",
                "regulatory approval",
                "general model correctness",
            ],
            "requires_before_production": [
                "domain owner acceptance",
                "deployment owner approval",
                "recipient-specific rollback plan",
                "production security review",
            ],
            "evidence_refs": {
                "github_pr": "github-pr:285",
                "merge_commit": PR_285_MERGE_COMMIT,
                "api_tests": "github-check:api-tests",
                "compose_smoke": "github-check:compose-smoke",
                "receipt_chain": "receipt-chain.json",
            },
        }
    )
    return claim


def _pr_285_trust_root(*, ai_review_only: bool = False) -> dict[str, Any]:
    trust = cbb_protocol.trust_root_demo(ai_review_only=ai_review_only)
    if not ai_review_only:
        trust["accepted_evidence"] = [
            *trust["accepted_evidence"],
            "receipt_chain",
            "github_ci_checks",
            "self_intake_receipt",
        ]
    trust.update(
        {
            "trust_root_id": "trust-root-pr-285",
            "project_id": PROJECT_ID,
            "claim_boundary": {
                "reference_implementation_only": True,
                "not_claimed": [
                    "production customer trust",
                    "legal certification",
                    "general model correctness",
                ],
            },
        }
    )
    return trust


def _pr_285_reviewer_reconstruction(*, missing: bool = False) -> dict[str, Any] | None:
    if missing:
        return None
    reviewer = cbb_protocol.reviewer_reconstruction_demo(qualified=True)
    reviewer.update(
        {
            "reviewer_receipt_id": "reviewer-reconstruction-pr-285",
            "project_id": PROJECT_ID,
            "reviewer_ref": "reviewer:maintainer-operator",
            "qualification": {
                "qualified_for_scope": True,
                "scope_ref": "controlled_reference_handoff",
                "qualification_basis": [
                    "can reconstruct claim boundary",
                    "can reconstruct CI evidence boundary",
                    "can reconstruct receipt-chain tamper boundary",
                ],
            },
            "reconstruction": {
                "status": "passed",
                "active_reconstruction": True,
                "passive_attention_only": False,
                "claim_boundary_reconstructed": True,
                "risk_owner_scope_reconstructed": True,
                "receipt_chain_reconstructed": True,
                "minimum_reconstructable_units_passed": 4,
                "minimum_reconstructable_units_required": 4,
            },
        }
    )
    return reviewer


def _pr_285_risk_owner_scope() -> dict[str, Any]:
    scope = cbb_protocol.risk_owner_scope_demo(recipient_risk_known=True)
    scope.update(
        {
            "scope_id": "owner-scope-pr-285",
            "project_id": PROJECT_ID,
            "risk_owner_ref": "owner:maintainer-operator",
            "recipient_ref": "recipient:controlled-reference-consumer",
            "risk_budget": {
                "maximum_scope": "controlled_customer_handoff",
                "requires_recipient_context": True,
                "recipient_context_known": True,
                "production_mutation_allowed": False,
            },
        }
    )
    return scope


def build_pr_285_protocol_receipts(
    *,
    missing_reviewer: bool = False,
    scope_expansion: bool = False,
    ai_review_only: bool = False,
) -> dict[str, dict[str, Any]]:
    claim = _pr_285_claim_boundary(scope_expansion=scope_expansion)
    trust = _pr_285_trust_root(ai_review_only=ai_review_only)
    reviewer = _pr_285_reviewer_reconstruction(missing=missing_reviewer)
    scope = _pr_285_risk_owner_scope()
    decision = cbb_protocol.evaluate_cbb_gate(claim, trust, reviewer, scope)
    decision.update(
        {
            "decision_id": "delivery-decision-pr-285",
            "project_id": PROJECT_ID,
            "evidence_refs": {
                **decision["evidence_refs"],
                "github_pr_ref": "github-pr:285",
                "receipt_chain_ref": "receipt-chain.json",
            },
        }
    )
    artifacts = {
        "claim-boundary.json": claim,
        "trust-root.json": trust,
        "risk-owner-scope.json": scope,
        "delivery-decision-receipt.json": decision,
    }
    if reviewer is not None:
        artifacts["reviewer-reconstruction-receipt.json"] = reviewer
    return artifacts


def receipt_record(filename: str, payload: Mapping[str, Any], *, role: str) -> dict[str, Any]:
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version:
        raise CBBReceiptChainError(f"receipt {filename} missing schema_version")
    return {
        "receipt_ref": filename,
        "receipt_type": schema_version,
        "role": role,
        "sha256": digest_payload(payload),
    }


def build_receipt_chain(
    receipts: Mapping[str, Mapping[str, Any]],
    *,
    source: Mapping[str, Any] | None = None,
    chain_id: str = "cbb-receipt-chain-pr-285",
) -> dict[str, Any]:
    role_map = {
        "claim-boundary.json": "claim_boundary",
        "trust-root.json": "trust_root",
        "reviewer-reconstruction-receipt.json": "reviewer_reconstruction",
        "risk-owner-scope.json": "risk_owner_scope",
        "delivery-decision-receipt.json": "delivery_decision",
    }
    records = [
        receipt_record(filename, receipts[filename], role=role_map[filename])
        for filename in sorted(role_map)
        if filename in receipts
    ]
    chain = {
        **_base_artifact(CBB_RECEIPT_CHAIN_SCHEMA_VERSION),
        "chain_id": chain_id,
        "project_id": PROJECT_ID,
        "source": dict(source or default_pr_285_source()),
        "hash_algorithm": "sha256",
        "canonicalization": "json-sort-keys-v1",
        "receipts": records,
        "required_receipt_roles": list(role_map.values()),
        "tamper_evidence": {
            "receipt_hashes_bound": True,
            "source_commit_bound": True,
            "chain_digest_bound": True,
            "raw_payload_access_required": False,
        },
    }
    chain["chain_digest"] = compute_receipt_chain_digest(chain)
    return validate_receipt_chain(chain, receipts)


def _required_receipt_roles_present(chain: Mapping[str, Any]) -> set[str]:
    return {str(item.get("role")) for item in _require_nonempty_list(chain, "receipts", label="chain")}


def validate_receipt_chain(
    payload: Mapping[str, Any],
    receipt_payloads: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    expected_merge_commit: str | None = PR_285_MERGE_COMMIT,
) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=CBB_RECEIPT_CHAIN_SCHEMA_VERSION)
    if payload.get("schema_version") != CBB_RECEIPT_CHAIN_SCHEMA_VERSION:
        raise CBBReceiptChainError("Invalid receipt chain schema_version")
    for key in (
        "chain_id",
        "project_id",
        "source",
        "hash_algorithm",
        "canonicalization",
        "receipts",
        "required_receipt_roles",
        "tamper_evidence",
        "chain_digest",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBReceiptChainError(f"receipt chain missing {key}")
    if payload.get("hash_algorithm") != "sha256":
        raise CBBReceiptChainError("receipt chain hash algorithm must be sha256")
    source = _require_object(payload, "source", label="receipt_chain")
    if expected_merge_commit is not None and source.get("merge_commit") != expected_merge_commit:
        raise CBBReceiptChainError("receipt chain source commit is stale")
    roles = _required_receipt_roles_present(payload)
    required_roles = set(str(role) for role in _require_nonempty_list(payload, "required_receipt_roles", label="receipt_chain"))
    missing_roles = sorted(required_roles - roles)
    if missing_roles:
        raise CBBReceiptChainError(f"receipt chain missing required roles: {missing_roles}")
    if payload.get("chain_digest") != compute_receipt_chain_digest(payload):
        raise CBBReceiptChainError("receipt chain digest mismatch")
    if receipt_payloads is not None:
        by_ref = {str(item["receipt_ref"]): item for item in payload["receipts"]}
        for receipt_ref, record in by_ref.items():
            if receipt_ref not in receipt_payloads:
                raise CBBReceiptChainError(f"receipt chain missing payload for {receipt_ref}")
            if digest_payload(receipt_payloads[receipt_ref]) != record.get("sha256"):
                raise CBBReceiptChainError("receipt hash mismatch")
        if "claim-boundary.json" in receipt_payloads:
            cbb_protocol.validate_claim_boundary(receipt_payloads["claim-boundary.json"])
        if "trust-root.json" in receipt_payloads:
            cbb_protocol.validate_trust_root(receipt_payloads["trust-root.json"])
        if "reviewer-reconstruction-receipt.json" in receipt_payloads:
            cbb_protocol.validate_reviewer_reconstruction_receipt(
                receipt_payloads["reviewer-reconstruction-receipt.json"]
            )
        if "risk-owner-scope.json" in receipt_payloads:
            cbb_protocol.validate_risk_owner_scope(receipt_payloads["risk-owner-scope.json"])
        if "delivery-decision-receipt.json" in receipt_payloads:
            cbb_protocol.validate_delivery_decision_receipt(
                receipt_payloads["delivery-decision-receipt.json"]
            )
    dual_loop.validate_isolation(payload, label="receipt_chain")
    cbb_protocol._validate_privacy(payload, label="receipt_chain")  # noqa: SLF001
    return dict(payload)


def _ci_checks_passed(checks: list[Mapping[str, Any]]) -> bool:
    statuses = {str(check.get("name")): check.get("status") for check in checks}
    return all(statuses.get(name) == "pass" for name in REQUIRED_CI_CHECKS)


def build_self_intake_receipt(
    receipts: Mapping[str, Mapping[str, Any]],
    receipt_chain: Mapping[str, Any],
    *,
    source: Mapping[str, Any] | None = None,
    ci_checks: list[Mapping[str, Any]] | None = None,
    self_intake_id: str = "cbb-self-intake-pr-285",
) -> dict[str, Any]:
    source_payload = dict(source or default_pr_285_source())
    ci_payload = [dict(item) for item in (ci_checks or default_pr_285_checks())]
    reasons: list[str] = []
    try:
        chain = validate_receipt_chain(receipt_chain, receipts)
    except Exception as exc:  # noqa: BLE001 - receipt captures deterministic failure reason.
        chain = dict(receipt_chain)
        reasons.append(str(exc))
    reviewer_present = "reviewer-reconstruction-receipt.json" in receipts
    if not reviewer_present:
        reasons.append("missing reviewer reconstruction")
    if source_payload.get("merge_commit") != PR_285_MERGE_COMMIT:
        reasons.append("stale source commit")
    if not _ci_checks_passed(ci_payload):
        reasons.append("CI evidence missing")
    claim = receipts.get("claim-boundary.json")
    if claim is not None and claim.get("allowed_scope") != "controlled_customer_handoff":
        reasons.append("scope expansion")
    trust = receipts.get("trust-root.json")
    if trust is not None and "ai_review_only" in trust.get("accepted_evidence", []):
        reasons.append("AI-review-only evidence rejected")
    decision = receipts.get("delivery-decision-receipt.json", {})
    if decision.get("status") != "allowed":
        reasons.append("delivery decision blocked")
    status = "passed" if not reasons else "blocked"
    checks = {
        "source_commit_matches": source_payload.get("merge_commit") == PR_285_MERGE_COMMIT,
        "ci_required_checks_passed": _ci_checks_passed(ci_payload),
        "receipt_chain_valid": not any("chain" in reason or "hash" in reason for reason in reasons),
        "reviewer_reconstruction_present": reviewer_present,
        "no_scope_expansion": claim is not None
        and claim.get("allowed_scope") == "controlled_customer_handoff",
        "ai_review_only_rejected": trust is not None
        and "ai_review_only" not in trust.get("accepted_evidence", []),
        "metadata_only": True,
        "production_mutation_blocked": True,
        "model_calls_performed": False,
        "full_release_check_claimed": False,
    }
    receipt = {
        **_base_artifact(CBB_SELF_INTAKE_RECEIPT_SCHEMA_VERSION),
        "self_intake_id": self_intake_id,
        "project_id": PROJECT_ID,
        "source": source_payload,
        "ci_checks": ci_payload,
        "receipt_chain": {
            "chain_id": chain.get("chain_id"),
            "chain_digest": chain.get("chain_digest"),
            "receipt_count": len(chain.get("receipts", [])),
            "chain_ref": "receipt-chain.json",
        },
        "status": status,
        "decision": "self_intake_passed" if status == "passed" else "block_self_intake",
        "reasons": reasons,
        "checks": checks,
        "reviewer_reconstruction_summary": {
            "present": reviewer_present,
            "active_reconstruction_required": True,
            "passive_attention_only_sufficient": False,
            "receipt_ref": "reviewer-reconstruction-receipt.json" if reviewer_present else None,
        },
        "claim_boundary": {
            "current_claim": (
                "PR 285 CBB Protocol Core has metadata-only self-intake evidence for "
                "controlled reference handoff."
            ),
            "not_claimed": [
                "production customer trust",
                "legal certification",
                "security certification",
                "general model correctness",
                "full release validation",
            ],
        },
    }
    return validate_self_intake_receipt(receipt, receipt_chain=chain)


def validate_self_intake_receipt(
    payload: Mapping[str, Any],
    *,
    receipt_chain: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=CBB_SELF_INTAKE_RECEIPT_SCHEMA_VERSION)
    if payload.get("schema_version") != CBB_SELF_INTAKE_RECEIPT_SCHEMA_VERSION:
        raise CBBReceiptChainError("Invalid self-intake schema_version")
    if payload.get("decision") not in ALLOWED_SELF_INTAKE_DECISIONS:
        raise CBBReceiptChainError("self-intake decision is invalid")
    for key in (
        "self_intake_id",
        "project_id",
        "source",
        "ci_checks",
        "receipt_chain",
        "status",
        "decision",
        "reasons",
        "checks",
        "reviewer_reconstruction_summary",
        "claim_boundary",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBReceiptChainError(f"self-intake receipt missing {key}")
    source = _require_object(payload, "source", label="self_intake")
    checks = _require_object(payload, "checks", label="self_intake")
    ci_checks = _require_nonempty_list(payload, "ci_checks", label="self_intake")
    reviewer = _require_object(payload, "reviewer_reconstruction_summary", label="self_intake")
    claim_boundary = _require_object(payload, "claim_boundary", label="self_intake")
    _require_nonempty_list(claim_boundary, "not_claimed", label="self_intake.claim_boundary")
    if source.get("merge_commit") != PR_285_MERGE_COMMIT:
        raise CBBReceiptChainError("stale source commit")
    if not _ci_checks_passed([dict(item) for item in ci_checks if isinstance(item, Mapping)]):
        raise CBBReceiptChainError("CI evidence missing")
    if reviewer.get("present") is not True:
        raise CBBReceiptChainError("missing reviewer reconstruction")
    required_true = (
        "source_commit_matches",
        "ci_required_checks_passed",
        "receipt_chain_valid",
        "reviewer_reconstruction_present",
        "no_scope_expansion",
        "ai_review_only_rejected",
        "metadata_only",
        "production_mutation_blocked",
    )
    for key in required_true:
        if checks.get(key) is not True:
            message = {
                "source_commit_matches": "stale source commit",
                "ci_required_checks_passed": "CI evidence missing",
                "receipt_chain_valid": "receipt chain invalid",
                "reviewer_reconstruction_present": "missing reviewer reconstruction",
                "no_scope_expansion": "scope expansion",
                "ai_review_only_rejected": "AI-review-only evidence rejected",
            }.get(key, f"self-intake check failed: {key}")
            raise CBBReceiptChainError(message)
    if checks.get("model_calls_performed") is not False:
        raise CBBReceiptChainError("self-intake must not perform model calls")
    if checks.get("full_release_check_claimed") is not False:
        raise CBBReceiptChainError("self-intake must not claim full release validation")
    if receipt_chain is not None:
        chain_ref = _require_object(payload, "receipt_chain", label="self_intake")
        if chain_ref.get("chain_digest") != receipt_chain.get("chain_digest"):
            raise CBBReceiptChainError("self-intake receipt chain digest mismatch")
    if payload.get("status") == "passed" and payload.get("reasons"):
        raise CBBReceiptChainError("passed self-intake must not include block reasons")
    dual_loop.validate_isolation(payload, label="self_intake")
    cbb_protocol._validate_privacy(payload, label="self_intake")  # noqa: SLF001
    return dict(payload)


def build_delivery_evidence_pack(
    receipts: Mapping[str, Mapping[str, Any]],
    receipt_chain: Mapping[str, Any],
    self_intake: Mapping[str, Any],
    *,
    pack_id: str = "cbb-delivery-evidence-pack-pr-285",
) -> dict[str, Any]:
    included = [
        {
            "artifact_ref": filename,
            "schema_version": str(payload.get("schema_version")),
            "sha256": digest_payload(payload),
        }
        for filename, payload in sorted(receipts.items())
    ]
    included.extend(
        [
            {
                "artifact_ref": "receipt-chain.json",
                "schema_version": CBB_RECEIPT_CHAIN_SCHEMA_VERSION,
                "sha256": digest_payload(receipt_chain),
            },
            {
                "artifact_ref": "self-intake-receipt.json",
                "schema_version": CBB_SELF_INTAKE_RECEIPT_SCHEMA_VERSION,
                "sha256": digest_payload(self_intake),
            },
        ]
    )
    pack = {
        **_base_artifact(CBB_DELIVERY_EVIDENCE_PACK_SCHEMA_VERSION),
        "pack_id": pack_id,
        "project_id": PROJECT_ID,
        "source": default_pr_285_source(),
        "status": "ready" if self_intake.get("status") == "passed" else "blocked",
        "receipt_chain_ref": {
            "chain_id": receipt_chain.get("chain_id"),
            "chain_digest": receipt_chain.get("chain_digest"),
            "artifact_ref": "receipt-chain.json",
        },
        "self_intake_ref": {
            "self_intake_id": self_intake.get("self_intake_id"),
            "artifact_ref": "self-intake-receipt.json",
            "sha256": digest_payload(self_intake),
        },
        "included_artifacts": included,
        "claim_boundary": {
            "current_claim": (
                "This evidence pack is a metadata-only proof package for PR 285 "
                "controlled reference handoff."
            ),
            "not_claimed": [
                "production customer trust",
                "legal certification",
                "security certification",
                "general model correctness",
            ],
        },
    }
    pack["pack_digest"] = compute_evidence_pack_digest(pack)
    return validate_delivery_evidence_pack(pack, receipt_chain=receipt_chain, self_intake=self_intake)


def validate_delivery_evidence_pack(
    payload: Mapping[str, Any],
    *,
    receipt_chain: Mapping[str, Any] | None = None,
    self_intake: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=CBB_DELIVERY_EVIDENCE_PACK_SCHEMA_VERSION)
    if payload.get("schema_version") != CBB_DELIVERY_EVIDENCE_PACK_SCHEMA_VERSION:
        raise CBBReceiptChainError("Invalid delivery evidence pack schema_version")
    for key in (
        "pack_id",
        "project_id",
        "source",
        "status",
        "receipt_chain_ref",
        "self_intake_ref",
        "included_artifacts",
        "claim_boundary",
        "pack_digest",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBReceiptChainError(f"delivery evidence pack missing {key}")
    source = _require_object(payload, "source", label="delivery_evidence_pack")
    if source.get("merge_commit") != PR_285_MERGE_COMMIT:
        raise CBBReceiptChainError("delivery evidence pack source commit is stale")
    _require_nonempty_list(payload, "included_artifacts", label="delivery_evidence_pack")
    if payload.get("pack_digest") != compute_evidence_pack_digest(payload):
        raise CBBReceiptChainError("delivery evidence pack digest mismatch")
    if receipt_chain is not None:
        chain_ref = _require_object(payload, "receipt_chain_ref", label="delivery_evidence_pack")
        if chain_ref.get("chain_digest") != receipt_chain.get("chain_digest"):
            raise CBBReceiptChainError("delivery evidence pack chain digest mismatch")
    if self_intake is not None:
        self_ref = _require_object(payload, "self_intake_ref", label="delivery_evidence_pack")
        if self_ref.get("sha256") != digest_payload(self_intake):
            raise CBBReceiptChainError("delivery evidence pack self-intake digest mismatch")
    dual_loop.validate_isolation(payload, label="delivery_evidence_pack")
    cbb_protocol._validate_privacy(payload, label="delivery_evidence_pack")  # noqa: SLF001
    return dict(payload)


def build_pr_285_self_intake_artifacts(
    *,
    missing_reviewer: bool = False,
    stale_source_commit: bool = False,
    scope_expansion: bool = False,
    missing_ci: bool = False,
    ai_review_only: bool = False,
) -> dict[str, dict[str, Any]]:
    source = default_pr_285_source(
        merge_commit="70697083d3c576d758fbd9639df3fe3b582ec72a"
        if stale_source_commit
        else PR_285_MERGE_COMMIT
    )
    receipts = build_pr_285_protocol_receipts(
        missing_reviewer=missing_reviewer,
        scope_expansion=scope_expansion,
        ai_review_only=ai_review_only,
    )
    chain = build_receipt_chain(receipts, source=source)
    self_intake = build_self_intake_receipt(
        receipts,
        chain,
        source=source,
        ci_checks=default_pr_285_checks(missing_ci=missing_ci),
    )
    pack = build_delivery_evidence_pack(receipts, chain, self_intake)
    return {
        **receipts,
        "receipt-chain.json": chain,
        "self-intake-receipt.json": self_intake,
        "delivery-evidence-pack.json": pack,
    }


def tamper_receipt_hash_mismatch(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    chain = deepcopy(artifacts["receipt-chain.json"])
    chain["receipts"][0]["sha256"] = "0" * 64
    chain["chain_digest"] = compute_receipt_chain_digest(chain)
    return chain


def write_artifact_set(output_dir: str | Path, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        cbb_protocol.write_json(target / filename, payload)
