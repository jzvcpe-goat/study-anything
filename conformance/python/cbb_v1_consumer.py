#!/usr/bin/env python3
"""Dependency-light, package-independent consumer for CBB Protocol v1 fixtures.

This file intentionally does not import the Study Anything package. It independently
implements the bounded canonicalization, scope, gate, provenance, outcome, and
evolution rules exercised by the public conformance pack.
"""

from __future__ import annotations

import argparse
from base64 import urlsafe_b64decode
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, TypedDict


IMPLEMENTATION_ID = "delivery-clearance-independent-python-consumer"
IMPLEMENTATION_VERSION = "1"
SUPPORTED_PROTOCOL_VERSION = (1, 0, 0)
CANONICALIZATION = "cbb-json-c14n-v1"
SCOPE_ORDER = {
    "blocked": 0,
    "personal_local": 1,
    "sandbox_only": 2,
    "public_demo": 3,
    "internal_handoff": 4,
    "controlled_customer_handoff": 5,
    "limited_beta": 6,
    "production_candidate": 7,
}
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
PROTECTED_EVOLUTION_FLAGS = {
    "touches_hard_denies": "protected_change:hard_denies",
    "weakens_required_evidence": "protected_change:required_evidence",
    "expands_delivery_scope": "protected_change:delivery_scope",
    "expands_tool_authority": "protected_change:tool_authority",
    "changes_verifier_or_signing": "protected_change:verifier_or_signing",
    "changes_revocation_semantics": "protected_change:revocation",
    "requests_automatic_apply": "protected_change:automatic_apply",
    "requests_production_mutation": "protected_change:production_mutation",
}


class ToolContract(TypedDict):
    effect: str
    max_input_refs: int
    max_output_refs: int
    accepts_untrusted_input: bool
    requires_quarantine: bool


TOOL_REGISTRY: dict[str, ToolContract] = {
    "cbb.receipt.lookup": {
        "effect": "read_metadata",
        "max_input_refs": 20,
        "max_output_refs": 20,
        "accepts_untrusted_input": False,
        "requires_quarantine": False,
    },
    "cbb.memory.search": {
        "effect": "query_quarantine",
        "max_input_refs": 50,
        "max_output_refs": 50,
        "accepts_untrusted_input": True,
        "requires_quarantine": True,
    },
    "cbb.evolution.propose": {
        "effect": "propose_candidate",
        "max_input_refs": 50,
        "max_output_refs": 10,
        "accepts_untrusted_input": True,
        "requires_quarantine": True,
    },
}
REQUIRED_EVOLUTION_CONTROLS = {
    "deterministic_replay",
    "canary",
    "rollback",
    "human_reconstruction",
    "risk_owner_acceptance",
    "maintainer_approval",
}
HUMAN_EVOLUTION_CONTROLS = {
    "human_reconstruction",
    "risk_owner_acceptance",
    "maintainer_approval",
}
FORBIDDEN_KEYS = {
    "api_key",
    "bearer_token",
    "cookie",
    "credentials",
    "eye_tracking",
    "keystrokes",
    "model_api_key",
    "mouse_coordinates",
    "password",
    "prompt_text",
    "raw_attention_stream",
    "raw_customer_payload",
    "raw_report_text",
    "raw_source_text",
    "screenshots",
    "secret",
    "signed_url",
    "source_text",
    "token",
    "user_owned_agent_credentials",
}
FORBIDDEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/[U]sers/[^\s\"']+"),
    re.compile(r"/[p]rivate/(?:tmp|var/folders)/[^\s\"']+"),
)


class ConformanceError(ValueError):
    """Raised when a pack or vector violates the independent consumer contract."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConformanceError(f"expected JSON object: {path.name}")
    return value


def _parse_timestamp(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ConformanceError("timestamp must use UTC Z form")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ConformanceError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _normalize_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_")


def assert_safe_metadata(value: Any) -> None:
    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if _normalize_key(key) in FORBIDDEN_KEYS and child is not False:
                    raise ConformanceError("forbidden metadata field")
                walk(child)
            return
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if isinstance(node, str) and any(pattern.search(node) for pattern in FORBIDDEN_PATTERNS):
            raise ConformanceError("secret-like or local-path metadata")

    walk(value)


def canonical_bytes(value: Any) -> bytes:
    assert_safe_metadata(value)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ConformanceError("payload is not canonical JSON data") from exc
    return encoded.encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return urlsafe_b64decode(value + padding)
    except Exception as exc:  # noqa: BLE001 - normalized protocol failure.
        raise ConformanceError("invalid base64url") from exc


def scope_is_at_most(candidate: str, ceiling: str) -> bool:
    return candidate in SCOPE_ORDER and ceiling in SCOPE_ORDER and (
        SCOPE_ORDER[candidate] <= SCOPE_ORDER[ceiling]
    )


def _minimum_scope(scopes: Iterable[str]) -> str:
    return min(scopes, key=SCOPE_ORDER.__getitem__)


def _evidence_by_type(bundle: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    evidence = list(bundle["evidence"])
    counts = Counter(str(item["evidence_type"]) for item in evidence)
    duplicates = sorted(kind for kind, count in counts.items() if count > 1)
    return {str(item["evidence_type"]): dict(item) for item in evidence}, duplicates


def _triggered_hard_denies(
    policy: Mapping[str, Any], bundle: Mapping[str, Any]
) -> tuple[list[str], list[str]]:
    triggered: list[str] = []
    unknown: list[str] = []
    policy_denies = set(policy["hard_denies"])
    for item in bundle["evidence"]:
        evidence_type = str(item["evidence_type"])
        if not evidence_type.startswith("hard_deny:") or item["status"] != "passed":
            continue
        deny = evidence_type.removeprefix("hard_deny:")
        (triggered if deny in policy_denies else unknown).append(deny or "empty")
    return sorted(set(triggered)), sorted(set(unknown))


def _required_evidence_state(
    policy: Mapping[str, Any],
    evidence_by_type: Mapping[str, Mapping[str, Any]],
    reconstruction: Mapping[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    missing: list[str] = []
    failed: list[str] = []
    insufficient: list[str] = []
    for requirement in policy["required_evidence"]:
        if not requirement["blocking"]:
            continue
        evidence_type = str(requirement["evidence_type"])
        required_scope = str(requirement["required_for_scope"])
        if evidence_type == "qualified_reconstruction":
            status = reconstruction["status"]
            if status in {"missing", "stale"}:
                missing.append(evidence_type)
            elif status != "passed":
                failed.append(evidence_type)
            elif not scope_is_at_most(required_scope, str(reconstruction["qualified_scope"])):
                insufficient.append(evidence_type)
            continue
        item = evidence_by_type.get(evidence_type)
        if item is None or item["status"] in {"missing", "stale", "not_applicable"}:
            missing.append(evidence_type)
        elif item["status"] != "passed":
            failed.append(evidence_type)
        elif not scope_is_at_most(required_scope, str(item["supported_scope"])):
            insufficient.append(evidence_type)
    return sorted(set(missing)), sorted(set(failed)), sorted(set(insufficient))


def _role_state(
    policy: Mapping[str, Any],
    evidence_by_type: Mapping[str, Mapping[str, Any]],
    reconstruction: Mapping[str, Any],
) -> list[str]:
    missing: list[str] = []
    for role in policy["required_roles"]:
        if role == "qualified_reviewer" and reconstruction["status"] == "passed":
            continue
        if role == "risk_owner":
            evidence_type = policy["scenario"]["risk_owner"].get("acceptance_evidence_type")
            evidence = evidence_by_type.get(str(evidence_type or ""))
            if evidence is not None and evidence["status"] == "passed":
                continue
        if reconstruction["status"] == "passed" and role in reconstruction["reviewer_roles"]:
            continue
        missing.append(f"role:{role}")
    return sorted(set(missing))


def _qualification_state(
    policy: Mapping[str, Any], reconstruction: Mapping[str, Any]
) -> tuple[list[str], list[str], list[str]]:
    integrity: list[str] = []
    missing: list[str] = []
    failed: list[str] = []
    scenario = policy["scenario"]
    if reconstruction["scenario_ref"] != policy["scenario_ref"]:
        integrity.append("reconstruction_scenario_ref_mismatch")
    if reconstruction["project_ref"] != scenario["project_ref"]:
        integrity.append("reconstruction_project_ref_mismatch")
    profile = reconstruction["human_capability_profile"]
    if policy["scenario_ref"] not in profile["scenario_refs"]:
        integrity.append("human_capability_scenario_mismatch")
    if profile["project_ref"] != scenario["project_ref"]:
        integrity.append("human_capability_project_mismatch")
    results = {item["mru_ref"]: item for item in reconstruction["mru_results"]}
    for requirement in policy["required_mrus"]:
        result = results.get(requirement["mru_ref"])
        if result is None or result["status"] in {"missing", "stale"}:
            missing.append(requirement["mru_ref"])
        elif result["boundary_type"] != requirement["boundary_type"]:
            integrity.append(f"mru_boundary_mismatch:{requirement['mru_ref']}")
        elif result["status"] != "passed":
            failed.append(requirement["mru_ref"])
    return sorted(set(integrity)), sorted(set(missing)), sorted(set(failed))


def evaluate_gate(
    policy: Mapping[str, Any],
    bundle: Mapping[str, Any],
    reconstruction: Mapping[str, Any],
    *,
    decided_at: str,
) -> dict[str, Any]:
    evidence_by_type, duplicates = _evidence_by_type(bundle)
    hard_denies, unknown_denies = _triggered_hard_denies(policy, bundle)
    missing, failed, insufficient = _required_evidence_state(
        policy, evidence_by_type, reconstruction
    )
    qualification_integrity, qualification_missing, qualification_failed = (
        _qualification_state(policy, reconstruction)
    )
    missing.extend(_role_state(policy, evidence_by_type, reconstruction))
    missing.extend(qualification_missing)
    failed.extend(qualification_failed)
    missing = sorted(set(missing))
    integrity: list[str] = []
    if bundle["subject_ref"] != policy["subject_ref"]:
        integrity.append("subject_ref_mismatch")
    if bundle["policy_ref"] != policy["policy_id"]:
        integrity.append("evidence_policy_ref_mismatch")
    if reconstruction["policy_ref"] != policy["policy_id"]:
        integrity.append("reconstruction_policy_ref_mismatch")
    integrity.extend(qualification_integrity)
    integrity.extend(f"duplicate_evidence_type:{kind}" for kind in duplicates)
    integrity.extend(f"unknown_hard_deny_signal:{kind}" for kind in unknown_denies)
    blocking = sorted(
        set(
            integrity
            + [f"hard_deny:{deny}" for deny in hard_denies]
            + [f"evidence_failed:{kind}" for kind in failed]
        )
    )
    missing_reasons = sorted(
        set(missing + [f"insufficient_scope:{kind}" for kind in insufficient])
    )
    if blocking:
        status = "block"
        approved_scope = "blocked"
        reasons = blocking
        missing_evidence: list[str] = []
    elif missing_reasons:
        status = "needs_evidence"
        approved_scope = "blocked"
        reasons = ["required_evidence_unavailable"]
        missing_evidence = missing_reasons
    else:
        approved_scope = _minimum_scope(
            (
                str(policy["maximum_scope"]),
                str(policy["claim_boundary"]["maximum_scope"]),
                str(bundle["maximum_supported_scope"]),
                str(bundle["claim_boundary"]["maximum_scope"]),
                str(reconstruction["qualified_scope"]),
                str(reconstruction["claim_boundary"]["maximum_scope"]),
            )
        )
        status = "block" if approved_scope == "blocked" else "allow"
        reasons = ["scope_ceiling_blocked"] if status == "block" else []
        missing_evidence = []
    decision_digest = canonical_sha256(
        {
            "policy_sha256": canonical_sha256(policy),
            "evidence_bundle_sha256": canonical_sha256(bundle),
            "reconstruction_sha256": canonical_sha256(reconstruction),
            "decided_at": decided_at,
        }
    )
    source_refs = [f"policy:{policy['policy_id']}"]
    source_refs.extend(item["source_ref"] for item in bundle["evidence"])
    source_refs.extend(reconstruction["evidence_refs"])
    claim = (
        f"The deterministic CBB v1 kernel authorizes only {approved_scope}."
        if status == "allow"
        else "The deterministic CBB v1 kernel does not authorize delivery."
    )
    return {
        "schema_version": "cbb.gate-decision.v1",
        "decision_id": f"cbb-decision:{decision_digest[:32]}",
        "subject_ref": policy["subject_ref"],
        "policy_ref": policy["policy_id"],
        "evidence_bundle_ref": bundle["bundle_id"],
        "reconstruction_ref": reconstruction["reconstruction_id"],
        "status": status,
        "approved_scope": approved_scope,
        "reasons": reasons,
        "hard_denies_triggered": hard_denies,
        "missing_evidence_types": missing_evidence,
        "source_decision_refs": sorted(set(source_refs)),
        "claim_boundary": {
            "current_claim": claim,
            "maximum_scope": approved_scope,
            "not_claimed": [
                "production approval",
                "portable signed attestation",
                "customer outcome guarantee",
                "general model correctness",
                "authority beyond the evaluated policy and evidence",
            ],
        },
        "privacy": policy["privacy"],
        "decided_at": decided_at,
    }


def _signature_payload(provenance: Mapping[str, Any]) -> bytes:
    payload = dict(provenance)
    payload.pop("signature", None)
    return canonical_bytes(payload)


def _verify_ed25519(public_key: str, signature: str, payload: bytes) -> bool:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        Ed25519PublicKey.from_public_bytes(_b64url_decode(public_key)).verify(
            _b64url_decode(signature), payload
        )
    except (ImportError, InvalidSignature, ValueError, ConformanceError):
        return False
    return True


def _receipt_envelope_digest(receipt: Mapping[str, Any]) -> str:
    payload = dict(receipt)
    payload.pop("provenance", None)
    return canonical_sha256(payload)


def _verify_provenance_package(
    package: Mapping[str, Any], context: Mapping[str, Any], seen_nonces: set[str]
) -> tuple[bool, list[str]]:
    checks: dict[str, bool] = {}
    try:
        assert_safe_metadata(package)
        policy = package["trust_policy"]
        bundle = package["evidence_bundle"]
        reconstruction = package["qualified_reconstruction"]
        decision = package["gate_decision"]
        receipt = package["delivery_trust_receipt"]
        provenance = package["receipt_provenance"]
        binding = {
            "policy_digest_sha256": canonical_sha256(policy),
            "evidence_digest_sha256": canonical_sha256(bundle),
            "reconstruction_digest_sha256": canonical_sha256(reconstruction),
            "decision_digest_sha256": canonical_sha256(decision),
            "receipt_envelope_digest_sha256": _receipt_envelope_digest(receipt),
        }
        checks["subject_digest"] = provenance["subject_digest_sha256"] == canonical_sha256(
            {"subject_ref": policy["subject_ref"]}
        )
        for name, expected in binding.items():
            checks[name.removesuffix("_sha256")] = provenance[name] == expected
        checks["package_digest"] = provenance["package_digest_sha256"] == canonical_sha256(
            binding
        )
        checks["embedded_provenance"] = receipt["provenance"] == provenance
        verifier = provenance["verifier"]
        checks["verifier_digest"] = verifier["verifier_digest_sha256"] == canonical_sha256(
            {
                "verifier_id": verifier["verifier_id"],
                "verifier_version": verifier["verifier_version"],
            }
        )
        checks["receipt_status"] = receipt["status"] == decision["status"]
        checks["receipt_scope"] = receipt["approved_scope"] == decision["approved_scope"]
        checks["scope_not_expanded"] = scope_is_at_most(
            provenance["claim_boundary"]["maximum_scope"], decision["approved_scope"]
        )
        expected_decision = evaluate_gate(
            policy, bundle, reconstruction, decided_at=decision["decided_at"]
        )
        checks["deterministic_gate"] = expected_decision == decision
        now = _parse_timestamp(str(context["now"]))
        checks["not_before"] = now >= _parse_timestamp(provenance["created_at"])
        checks["not_expired"] = now < _parse_timestamp(provenance["expires_at"])
        checks["not_revoked"] = provenance["revocation"]["handle"] not in set(
            context.get("revoked_handles", [])
        )
        checks["locally_signed"] = provenance["signing_status"] == "locally_signed"
        signer = provenance.get("signer")
        signature = provenance.get("signature")
        checks["public_key_fingerprint"] = bool(signer) and (
            hashlib.sha256(_b64url_decode(signer["public_key"])).hexdigest()
            == signer["public_key_fingerprint_sha256"]
        )
        checks["signature"] = bool(signer and signature) and _verify_ed25519(
            signer["public_key"], signature, _signature_payload(provenance)
        )
        nonce = provenance["replay_nonce"]
        if context.get("consume_nonce"):
            checks["replay_nonce_unused"] = nonce not in seen_nonces
            if checks["replay_nonce_unused"] and all(checks.values()):
                seen_nonces.add(nonce)
        else:
            checks["replay_nonce_unused"] = True
    except (ConformanceError, KeyError, TypeError, ValueError):
        checks["well_formed"] = False
    reasons = sorted(name for name, passed in checks.items() if not passed)
    return not reasons, reasons


def _is_safe_outcome(event: Mapping[str, Any]) -> bool:
    return (
        event["event_type"] == "delivery_observation"
        and event["status"] == "confirmed"
        and event["severity"] == "info"
        and not event["external_effect_observed"]
        and not event["claim_boundary_violated"]
    )


def _is_substantiated(event: Mapping[str, Any]) -> bool:
    return event["status"] in {"confirmed", "resolved"}


def _is_open_outcome(event: Mapping[str, Any]) -> bool:
    return event["status"] in {"reported", "confirmed", "disputed"}


def determine_trust_action(
    previous_scope: str, events: list[Mapping[str, Any]], rollback: Mapping[str, Any]
) -> str:
    substantiated = [event for event in events if _is_substantiated(event)]
    if rollback["status"] == "failed":
        return "revoke_clearance"
    if any(
        event["event_type"] in {"claim_violation", "evidence_invalidated"}
        for event in substantiated
    ):
        return "revoke_clearance"
    if any(
        event["event_type"] == "incident" and SEVERITY_ORDER[event["severity"]] >= 3
        for event in substantiated
    ):
        return "revoke_clearance"
    if any(
        event["external_effect_observed"] and SEVERITY_ORDER[event["severity"]] >= 3
        for event in substantiated
    ):
        return "revoke_clearance"
    if rollback["required"] and rollback["status"] in {"partial", "not_attempted"}:
        return "freeze_recipe"
    if any(
        event["event_type"] == "affected_party_challenge" and event["status"] != "resolved"
        for event in events
    ):
        return "freeze_recipe"
    if any(
        _is_open_outcome(event)
        and (
            event["event_type"] in {"claim_violation", "evidence_invalidated"}
            or (event["event_type"] == "incident" and SEVERITY_ORDER[event["severity"]] >= 2)
            or (
                event["event_type"] in {"near_miss", "complaint"}
                and SEVERITY_ORDER[event["severity"]] >= 3
            )
        )
        for event in events
    ):
        return "freeze_recipe"
    adverse = rollback["status"] == "succeeded" or any(
        not _is_safe_outcome(event) for event in events
    )
    if adverse:
        return "narrow_scope" if SCOPE_ORDER[previous_scope] > SCOPE_ORDER["sandbox_only"] else "freeze_recipe"
    return "maintain_current_ceiling"


def _verify_outcome_vector(vector: Mapping[str, Any]) -> bool:
    receipt = vector["receipt"]
    expected = vector["expected"]
    action = determine_trust_action(
        receipt["source_approved_scope"], vector["inputs"]["events"], vector["inputs"]["rollback"]
    )
    derived = {
        "maintain_current_ceiling": (receipt["source_approved_scope"], "active", "monitored", False),
        "narrow_scope": ("sandbox_only", "active", "degraded", False),
        "freeze_recipe": ("blocked", "frozen", "frozen", False),
        "revoke_clearance": ("blocked", "revoked", "revoked", True),
    }[action]
    observed = {
        "action": action,
        "resulting_scope": derived[0],
        "recipe_state": derived[1],
        "status": derived[2],
        "source_clearance_revoked": derived[3],
    }
    return observed == expected and all(
        receipt["trust_update"][key] == value for key, value in expected.items() if key != "status"
    ) and receipt["status"] == expected["status"]


def _memory_disposition(entry: Mapping[str, Any], *, as_of: str) -> str | None:
    if _parse_timestamp(entry["observed_at"]) > _parse_timestamp(as_of):
        return "not_yet_observed"
    if _parse_timestamp(entry["expires_at"]) <= _parse_timestamp(as_of):
        return "expired"
    if entry["policy_directive_detected"]:
        return "policy_directive"
    if entry["injection_signals"]:
        return "injection_signal"
    if entry["source_trust"] == "untrusted":
        return "untrusted"
    if entry["counter_evidence_refs"]:
        return "counter_evidence_pending"
    if not entry["eligible_as_supporting_evidence"]:
        return "ineligible"
    return None


def _replay_memory(query: Mapping[str, Any]) -> dict[str, Any]:
    entries = sorted(query["considered_entries"], key=lambda item: item["memory_id"])
    eligible: list[str] = []
    ignored: list[dict[str, str]] = []
    counter_refs: set[str] = set()
    for entry in entries:
        counter_refs.update(entry["counter_evidence_refs"])
        reason = _memory_disposition(entry, as_of=query["as_of"])
        if reason is None:
            eligible.append(entry["memory_id"])
        else:
            ignored.append({"memory_id": entry["memory_id"], "reason": reason})
    return {
        "query_id": query["query_id"],
        "as_of": query["as_of"],
        "considered_entries": entries,
        "eligible_memory_ids": eligible,
        "ignored_entries": ignored,
        "unresolved_counter_evidence_refs": sorted(counter_refs),
        "policy_override_allowed": False,
        "trust_increase_allowed": False,
        "raw_content_returned": False,
    }


def _validate_agentic_tools(context: Mapping[str, Any]) -> set[str]:
    reasons: set[str] = set()
    plan = context["plan"]
    calls = {call["call_id"]: call for call in plan["calls"]}
    results = context["tool_results"]
    result_ids = [result["call_id"] for result in results]
    if len(result_ids) != len(set(result_ids)) or set(result_ids) != set(calls):
        reasons.add("tool_boundary:call_result_accounting")
    if any(
        plan[name]
        for name in (
            "policy_mutation_requested",
            "gate_decision_requested",
            "production_mutation_requested",
        )
    ) or plan["final_authority"] != "proposal_only":
        reasons.add("tool_boundary:plan_authority")
    for call in plan["calls"]:
        contract = TOOL_REGISTRY.get(call["tool_id"])
        if contract is None:
            reasons.add(f"tool_boundary:unknown_tool:{call['tool_id']}")
            continue
        if call["requested_effect"] != contract["effect"]:
            reasons.add(f"tool_boundary:effect_mismatch:{call['call_id']}")
        if len(call["input_refs"]) > contract["max_input_refs"]:
            reasons.add(f"tool_boundary:input_bound_exceeded:{call['call_id']}")
        if call["untrusted_input_present"] and not contract["accepts_untrusted_input"]:
            reasons.add(f"tool_boundary:untrusted_input_rejected:{call['call_id']}")
        if contract["requires_quarantine"] and not call["quarantine_acknowledged"]:
            reasons.add(f"tool_boundary:quarantine_missing:{call['call_id']}")
        if any(
            call[name]
            for name in (
                "requests_policy_mutation",
                "requests_gate_decision",
                "requests_production_mutation",
            )
        ):
            reasons.add(f"tool_boundary:call_authority:{call['call_id']}")
    for result in results:
        call = calls.get(result["call_id"])
        contract = TOOL_REGISTRY.get(result["tool_id"])
        if call is None or contract is None:
            reasons.add(f"tool_boundary:unplanned_result:{result['call_id']}")
            continue
        if result["tool_id"] != call["tool_id"] or result["effect"] != contract["effect"]:
            reasons.add(f"tool_boundary:result_contract_mismatch:{result['call_id']}")
        if len(result["output_refs"]) > contract["max_output_refs"]:
            reasons.add(f"tool_boundary:output_bound_exceeded:{result['call_id']}")
        if result["authority"] != "supporting_evidence_only" or any(
            result[name]
            for name in (
                "policy_override_allowed",
                "gate_decision_allowed",
                "production_mutation_performed",
            )
        ):
            reasons.add(f"tool_boundary:result_authority:{result['call_id']}")
    return reasons


def evaluate_evolution(
    proposal: Mapping[str, Any], context: Mapping[str, Any], controls: Mapping[str, Any]
) -> dict[str, Any]:
    block = set(_validate_agentic_tools(context))
    needs: set[str] = set()
    if _replay_memory(context["memory_query"]) != context["memory_query"]:
        block.add("memory_quarantine:deterministic_replay_mismatch")
    if context["memory_query"]["policy_override_allowed"]:
        block.add("memory_quarantine:policy_override_requested")
    if context["memory_query"]["unresolved_counter_evidence_refs"]:
        needs.add("memory_quarantine:counter_evidence_pending")
    for field, reason in PROTECTED_EVOLUTION_FLAGS.items():
        if proposal[field]:
            block.add(reason)
    controls_by_type = {item["control_type"]: item for item in controls["controls"]}
    if set(controls_by_type) != REQUIRED_EVOLUTION_CONTROLS:
        block.add("control_set:incomplete")
    elif any(
        controls_by_type[control]["actor_ref"] == proposal["proposer_ref"]
        for control in HUMAN_EVOLUTION_CONTROLS
    ):
        block.add("actor_separation:self_authorization")
    for control in controls["controls"]:
        if control["status"] == "failed":
            block.add(f"control_failed:{control['control_type']}")
        elif control["status"] == "missing":
            needs.add(f"control_missing:{control['control_type']}")
    eligible = set(context["memory_query"]["eligible_memory_ids"])
    needs.update(
        f"memory_not_eligible:{memory_id}"
        for memory_id in set(proposal["memory_refs"]).difference(eligible)
    )
    tool_outputs = {
        output_ref
        for result in context["tool_results"]
        if result["status"] == "passed"
        for output_ref in result["output_refs"]
    }
    needs.update(
        f"evidence_not_produced:{ref}"
        for ref in set(proposal["evidence_refs"]).difference(tool_outputs)
    )
    needs.update(
        f"tool_result_blocked:{result['call_id']}"
        for result in context["tool_results"]
        if result["status"] == "blocked"
    )
    proposal_digest = canonical_sha256(proposal)
    if block:
        status, state, reasons = "block", "rejected", sorted(block)
    elif needs:
        status, state, reasons = "needs_evidence", "pending", sorted(needs)
    else:
        status, state, reasons = "approved_for_local_candidate", "local_candidate", []
    return {
        "status": status,
        "candidate_state": state,
        "proposal_digest_sha256": proposal_digest,
        "reasons": reasons,
        "automatic_apply_allowed": False,
        "production_apply_allowed": False,
        "trust_kernel_mutation_performed": False,
        "release_performed": False,
        "tool_or_memory_authority_used_as_final_basis": False,
        "explicit_maintainer_apply_required": True,
    }


def _verify_evolution_vector(vector: Mapping[str, Any]) -> bool:
    receipt = vector["receipt"]
    provenance = receipt["provenance"]
    envelope = dict(receipt)
    envelope.pop("provenance")
    expected = evaluate_evolution(
        receipt["proposal"], receipt["agentic_evidence"], receipt["controls"]
    )
    signer = provenance["signer"]
    now = _parse_timestamp(receipt["issued_at"])
    checks = (
        expected == receipt["decision"],
        receipt["decision"]["status"] == vector["expected_status"],
        not receipt["automatic_apply_performed"],
        receipt["claim_boundary"]["maximum_scope"] == "blocked",
        provenance["envelope_digest_sha256"] == canonical_sha256(envelope),
        provenance["decision_digest_sha256"] == canonical_sha256(receipt["decision"]),
        provenance["verifier"]["verifier_id"] == "delivery-clearance-evolution-gate",
        provenance["verifier"]["verifier_version"] == "1",
        provenance["verifier"]["verifier_digest_sha256"]
        == canonical_sha256(
            {
                "verifier_id": "delivery-clearance-evolution-gate",
                "verifier_version": "1",
            }
        ),
        now >= _parse_timestamp(provenance["created_at"]),
        now < _parse_timestamp(provenance["expires_at"]),
        hashlib.sha256(_b64url_decode(signer["public_key"])).hexdigest()
        == signer["public_key_fingerprint_sha256"],
        _verify_ed25519(
            signer["public_key"], provenance["signature"], _signature_payload(provenance)
        ),
    )
    return all(checks)


def _parse_version(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ConformanceError("protocol version must be major.minor.patch")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def negotiate_version(requested: str, migration_available: bool) -> str:
    version = _parse_version(requested)
    if version == SUPPORTED_PROTOCOL_VERSION:
        return "accept"
    if version[0] == 0 and migration_available:
        return "compatibility_only"
    if version[0] != SUPPORTED_PROTOCOL_VERSION[0]:
        return "reject_major"
    return "reject_unsupported_version"


def _extension_decision(
    vector: Mapping[str, Any], registry: Mapping[str, Mapping[str, Any]]
) -> str:
    extension = registry.get(str(vector["extension_id"]))
    if vector["claims_authority"]:
        return "reject_authority_claim"
    if extension is None:
        return "ignore_unknown_informational"
    if extension["authority"] != "informational_only":
        return "reject_authority_claim"
    return "accept_registered_informational"


def _verify_file_manifest(root: Path, manifest: Mapping[str, Any]) -> bool:
    declared = {record["path"]: record for record in manifest["files"]}
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if set(declared) != actual:
        return False
    for relative, record in declared.items():
        path = root / relative
        data = path.read_bytes()
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            return False
    return True


def verify_pack(root: Path) -> dict[str, Any]:
    manifest = _load_json(root / "manifest.json")
    checks: dict[str, bool] = {
        "manifest_schema": manifest.get("schema_version") == "cbb.conformance-pack.v1",
        "canonicalization_declared": manifest.get("canonicalization") == CANONICALIZATION,
        "file_digests": _verify_file_manifest(root, manifest),
        "no_study_anything_runtime_required": True,
    }
    schema_records = manifest["schemas"]
    checks["eight_canonical_schemas"] = len(schema_records) == 8
    for record in schema_records:
        schema = _load_json(root / record["path"])
        if schema.get("$id") != record["schema_version"]:
            checks["eight_canonical_schemas"] = False

    canonical_vectors = _load_json(root / manifest["vectors"]["canonical"])
    canonical_pass = True
    for vector in canonical_vectors["vectors"]:
        encoded = canonical_bytes(vector["payload"])
        canonical_pass = canonical_pass and encoded.decode("utf-8") == vector["canonical_json"]
        canonical_pass = canonical_pass and hashlib.sha256(encoded).hexdigest() == vector["sha256"]
        canonical_pass = canonical_pass and vector["payload"]["schema_version"] == vector["schema_version"]
    checks["canonical_vectors"] = canonical_pass and len(canonical_vectors["vectors"]) == 8

    kernel_pass = True
    kernel_dir = root / manifest["vectors"]["kernel_dir"]
    for path in sorted(kernel_dir.glob("*.json")):
        vector = _load_json(path)
        inputs = vector["inputs"]
        observed = evaluate_gate(
            inputs["policy"],
            inputs["evidence_bundle"],
            inputs["qualified_reconstruction"],
            decided_at=vector["decision"]["decided_at"],
        )
        kernel_pass = kernel_pass and observed == vector["decision"]
    checks["deterministic_kernel_vectors"] = kernel_pass and len(list(kernel_dir.glob("*.json"))) == 7

    provenance_pass = True
    provenance_dir = root / manifest["vectors"]["provenance_dir"]
    for path in sorted(provenance_dir.glob("*.json")):
        vector = _load_json(path)
        seen: set[str] = set()
        first, _ = _verify_provenance_package(
            vector["package"], vector["verification_context"], seen
        )
        if vector["case_id"] == "replay":
            second, second_reasons = _verify_provenance_package(
                vector["package"], vector["verification_context"], seen
            )
            provenance_pass = provenance_pass and first and not second
            provenance_pass = provenance_pass and second_reasons == vector["expected_second_reasons"]
        else:
            provenance_pass = provenance_pass and (
                ("pass" if first else "fail") == vector["expected_status"]
            )
    checks["signed_provenance_vectors"] = provenance_pass and len(list(provenance_dir.glob("*.json"))) == 12

    outcome_pass = True
    outcome_dir = root / manifest["vectors"]["outcome_dir"]
    for path in sorted(outcome_dir.glob("*.json")):
        outcome_pass = outcome_pass and _verify_outcome_vector(_load_json(path))
    checks["outcome_degradation_vectors"] = outcome_pass and len(list(outcome_dir.glob("*.json"))) == 5

    evolution_pass = True
    evolution_dir = root / manifest["vectors"]["evolution_dir"]
    for path in sorted(evolution_dir.glob("*.json")):
        evolution_pass = evolution_pass and _verify_evolution_vector(_load_json(path))
    checks["evolution_gate_vectors"] = evolution_pass and len(list(evolution_dir.glob("*.json"))) == 6

    version_vectors = _load_json(root / manifest["vectors"]["version_negotiation"])
    checks["version_negotiation"] = all(
        negotiate_version(vector["requested"], vector["migration_available"])
        == vector["expected"]
        for vector in version_vectors["vectors"]
    )
    migration = _load_json(root / manifest["migration_map"])
    checks["v0_migration_narrows_only"] = bool(migration["mappings"]) and all(
        item["authority"] == "compatibility_only"
        and item["scope_rule"] == "may_narrow_never_expand"
        for item in migration["mappings"]
    )
    extension_payload = _load_json(root / manifest["vectors"]["extensions"])
    registry = {
        item["extension_id"]: item for item in extension_payload["registered_extensions"]
    }
    checks["extension_authority_fail_closed"] = all(
        _extension_decision(vector, registry) == vector["expected"]
        for vector in extension_payload["vectors"]
    )
    privacy_vectors = _load_json(root / manifest["vectors"]["privacy_negative"])
    privacy_pass = True
    for vector in privacy_vectors["vectors"]:
        try:
            assert_safe_metadata(vector["payload"])
        except ConformanceError:
            privacy_observed = "reject"
        else:
            privacy_observed = "accept"
        privacy_pass = privacy_pass and privacy_observed == vector["expected"]
    checks["privacy_negative_vectors"] = privacy_pass

    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": "cbb.external-consumer-verification.v1",
        "implementation": {
            "implementation_id": IMPLEMENTATION_ID,
            "implementation_version": IMPLEMENTATION_VERSION,
            "language": "python",
            "study_anything_imported": False,
            "model_or_network_runtime_required": False,
        },
        "protocol_version": manifest["protocol_version"],
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "counts": {
            "canonical_schemas": len(schema_records),
            "canonical_vectors": len(canonical_vectors["vectors"]),
            "kernel_vectors": len(list(kernel_dir.glob("*.json"))),
            "provenance_vectors": len(list(provenance_dir.glob("*.json"))),
            "outcome_vectors": len(list(outcome_dir.glob("*.json"))),
            "evolution_vectors": len(list(evolution_dir.glob("*.json"))),
        },
        "claim_boundary": (
            "This proves local cross-implementation conformance against the packaged "
            "Protocol v1 vectors. It does not establish a certification authority, "
            "production safety, global revocation, customer outcomes, or independent audit."
        ),
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "production_mutation_performed": False,
            "private_keys_included": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = verify_pack(Path(args.pack_root).resolve())
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
