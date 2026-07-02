"""Customer handoff package contracts for Cognitive Black Box.

CustomerHandoffPackage is a portable packaging layer above
DeliveryTrustReceipt. It is not a new trust source: it cannot approve a
handoff, expand scope, call models, mutate production, or send anything to a
customer. It only bundles scoped metadata evidence that an already-allowed
DeliveryTrustReceipt references.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
import zipfile

from study_anything.core import delivery_trust, dual_loop


CUSTOMER_HANDOFF_PACKAGE_SCHEMA_VERSION = "customer-handoff-package-v1"
CUSTOMER_HANDOFF_REPORT_SCHEMA_VERSION = "customer-handoff-package-verification-v1"

PACKAGE_STATUS = "ready_for_controlled_customer_handoff"
PACKAGE_DECISION = "package_controlled_customer_handoff"

PACKAGE_PRIVACY_FLAGS = {
    **delivery_trust.DELIVERY_PRIVACY_FLAGS,
    "raw_customer_payload_included": False,
    "attention_streams_included": False,
    "model_prompts_included": False,
    "platform_agent_credentials_included": False,
    "production_mutation_performed": False,
    "automatic_customer_sending_performed": False,
}

ZIP_ROOT = "study-anything-customer-handoff-package"


class CustomerHandoffError(ValueError):
    """Raised when a CustomerHandoffPackage is unsafe or malformed."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CustomerHandoffError(f"Expected object JSON at {path}")
    return payload


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_json(dict(payload)), encoding="utf-8")


def sha256_payload(payload: Any) -> str:
    return dual_loop.sha256_text(dump_json(payload))


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping):
        raise CustomerHandoffError(f"{label} must include privacy flags")
    for key, expected in PACKAGE_PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise CustomerHandoffError(f"{label}.privacy.{key} must be {expected!r}")


def _require_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise CustomerHandoffError(f"customer handoff package {key} must be an object")
    return value


def _require_list(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise CustomerHandoffError(f"customer handoff package {key} must be a list")
    return list(value)


def _scope_exceeds_delivery_trust(
    package_scope: Mapping[str, Any],
    receipt_scope: Mapping[str, Any],
) -> bool:
    if package_scope.get("scope_id") != receipt_scope.get("scope_id"):
        return True
    if package_scope.get("allowed_handoff") is not True:
        return True
    for key in (
        "production_mutation_allowed",
        "irreversible_external_effects_allowed",
        "real_customer_effects_allowed",
    ):
        if package_scope.get(key) is not False:
            return True
        if package_scope.get(key) != receipt_scope.get(key):
            return True
    receipt_materials = set(receipt_scope.get("allowed_material_refs") or [])
    package_materials = set(package_scope.get("allowed_material_refs") or [])
    return not package_materials.issubset(receipt_materials)


def _validate_external_eval_receipts(payload: Mapping[str, Any]) -> None:
    receipts = _require_mapping(payload, "external_eval_receipts")
    if receipts.get("role") != "supporting_only_not_sufficient":
        raise CustomerHandoffError("external eval receipts cannot be sufficient trust basis")
    if receipts.get("trust_sufficient") is not False:
        raise CustomerHandoffError("external eval receipts must not be marked sufficient")
    items = receipts.get("receipts")
    if not isinstance(items, list) or not items:
        raise CustomerHandoffError("customer handoff package must include eval receipt refs")
    for item in items:
        if not isinstance(item, Mapping):
            raise CustomerHandoffError("external eval receipt ref must be object")
        if item.get("status") != "pass":
            raise CustomerHandoffError("external eval receipt refs must pass")
        if item.get("raw_outputs_included") is not False:
            raise CustomerHandoffError("external eval refs must not include raw outputs")
        if item.get("real_model_or_eval_keys_stored") is not False:
            raise CustomerHandoffError("external eval refs must not store model or eval keys")


def _validate_agent_handoff_instructions(payload: Mapping[str, Any]) -> None:
    instructions = _require_list(payload, "agent_handoff_instructions")
    required_platforms = {"workbuddy", "hermes", "codex"}
    seen = set()
    for instruction in instructions:
        if not isinstance(instruction, Mapping):
            raise CustomerHandoffError("agent handoff instruction must be object")
        platform = str(instruction.get("platform_id") or "")
        seen.add(platform)
        if instruction.get("production_mutation_allowed") is not False:
            raise CustomerHandoffError("agent instructions must not request production mutation")
        if instruction.get("scope_escalation_allowed") is not False:
            raise CustomerHandoffError("agent instructions must not request scope escalation")
        if instruction.get("automatic_customer_sending_allowed") is not False:
            raise CustomerHandoffError("agent instructions must not auto-send to customers")
        allowed = instruction.get("allowed_actions")
        forbidden = instruction.get("forbidden_actions")
        if not isinstance(allowed, list) or not allowed:
            raise CustomerHandoffError("agent instructions must list allowed actions")
        if not isinstance(forbidden, list) or "production_mutation" not in forbidden:
            raise CustomerHandoffError("agent instructions must forbid production mutation")
        if "scope_escalation" not in forbidden:
            raise CustomerHandoffError("agent instructions must forbid scope escalation")
    missing = sorted(required_platforms - seen)
    if missing:
        raise CustomerHandoffError(f"missing platform handoff instructions: {missing}")


def _validate_artifact_digests(payload: Mapping[str, Any]) -> None:
    manifest = _require_mapping(payload, "manifest")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise CustomerHandoffError("customer handoff manifest must include artifacts")
    refs = _require_list(payload, "artifact_refs")
    ref_by_path = {
        item.get("path"): item
        for item in refs
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    }
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise CustomerHandoffError("manifest artifact must be object")
        key = artifact.get("package_key")
        path = artifact.get("path")
        expected = artifact.get("sha256")
        if not isinstance(key, str) or key not in payload:
            raise CustomerHandoffError(f"manifest artifact has invalid package_key: {key!r}")
        if not isinstance(path, str) or not isinstance(expected, str):
            raise CustomerHandoffError("manifest artifact missing path or sha256")
        actual = sha256_payload(payload[key])
        if actual != expected:
            raise CustomerHandoffError(f"artifact digest mismatch for {path}")
        ref = ref_by_path.get(path)
        if not isinstance(ref, Mapping) or ref.get("sha256") != expected:
            raise CustomerHandoffError(f"artifact ref mismatch for {path}")


def validate_customer_handoff_package(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=CUSTOMER_HANDOFF_PACKAGE_SCHEMA_VERSION)
    if payload.get("schema_version") != CUSTOMER_HANDOFF_PACKAGE_SCHEMA_VERSION:
        raise CustomerHandoffError("Invalid customer handoff package schema_version")
    if payload.get("status") != PACKAGE_STATUS:
        raise CustomerHandoffError("customer handoff package status is invalid")
    if payload.get("decision") != PACKAGE_DECISION:
        raise CustomerHandoffError("customer handoff package decision is invalid")
    for key in (
        "package_id",
        "manifest",
        "delivery_trust_receipt",
        "claim_boundary",
        "limitations",
        "rollback_strategy",
        "controlled_failure_summary",
        "human_reconstruction_summary",
        "dual_loop_gate_receipt",
        "external_eval_receipts",
        "artifact_refs",
        "agent_handoff_instructions",
        "provenance",
        "customer_delivery_scope",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CustomerHandoffError(f"customer handoff package missing {key}")

    dual_loop.validate_isolation(payload, label="customer_handoff_package")
    _validate_privacy(payload, label="customer_handoff_package")

    receipt = delivery_trust.validate_delivery_trust_receipt(
        _require_mapping(payload, "delivery_trust_receipt")
    )
    if receipt.get("status") != "allowed":
        raise CustomerHandoffError("blocked delivery trust cannot produce handoff package")
    if receipt["customer_delivery_scope"].get("allowed_handoff") is not True:
        raise CustomerHandoffError("delivery trust receipt did not allow handoff")

    gate = dual_loop.validate_gate_receipt(_require_mapping(payload, "dual_loop_gate_receipt"))
    if gate.get("status") != "allowed":
        raise CustomerHandoffError("dual-loop gate must be allowed for handoff package")

    claim_boundary = _require_mapping(payload, "claim_boundary")
    if not claim_boundary.get("current_claim"):
        raise CustomerHandoffError("customer handoff package must state a current claim")
    if not claim_boundary.get("not_claimed"):
        raise CustomerHandoffError("customer handoff package must state what is not claimed")
    if claim_boundary != receipt["claim_boundary"]:
        raise CustomerHandoffError("package claim boundary must match delivery trust receipt")

    scope = _require_mapping(payload, "customer_delivery_scope")
    if _scope_exceeds_delivery_trust(scope, receipt["customer_delivery_scope"]):
        raise CustomerHandoffError("customer handoff package scope exceeds delivery trust scope")

    rollback = _require_mapping(payload, "rollback_strategy")
    provenance = _require_mapping(payload, "provenance")
    if provenance.get("risk_level") in {"high", "blocked"}:
        if rollback.get("available") is not True or rollback.get("rehearsed") is not True:
            raise CustomerHandoffError("high-risk handoff requires available rehearsed rollback")
    if rollback.get("production_mutation_required") is not False:
        raise CustomerHandoffError("rollback strategy must not require production mutation")

    failure_summary = _require_mapping(payload, "controlled_failure_summary")
    if failure_summary.get("production_mutation") is not False:
        raise CustomerHandoffError("controlled failure summary must not include production mutation")
    if failure_summary.get("risk_within_budget") is not True:
        raise CustomerHandoffError("controlled failure summary must be within risk budget")

    reconstruction = _require_mapping(payload, "human_reconstruction_summary")
    if reconstruction.get("status") != "passed":
        raise CustomerHandoffError("human reconstruction summary must pass")
    if reconstruction.get("active_reconstruction_required") is not True:
        raise CustomerHandoffError("human reconstruction must be active")
    if reconstruction.get("passive_attention_only") is not False:
        raise CustomerHandoffError("passive attention cannot be sufficient")

    _validate_external_eval_receipts(payload)
    _validate_agent_handoff_instructions(payload)
    _validate_artifact_digests(payload)
    return dict(payload)


def _default_external_eval_receipts() -> dict[str, Any]:
    receipts = [
        {
            "adapter_id": "promptfoo",
            "receipt_ref": "external-eval:promptfoo-deepseek-lesson-pass",
            "status": "pass",
            "sha256": dual_loop.sha256_text("promptfoo-deepseek-lesson-pass"),
            "raw_outputs_included": False,
            "real_model_or_eval_keys_stored": False,
        },
        {
            "adapter_id": "ragas",
            "receipt_ref": "external-eval:ragas-deepseek-lesson-pass",
            "status": "pass",
            "sha256": dual_loop.sha256_text("ragas-deepseek-lesson-pass"),
            "raw_outputs_included": False,
            "real_model_or_eval_keys_stored": False,
        },
    ]
    return {
        "role": "supporting_only_not_sufficient",
        "trust_sufficient": False,
        "receipts": receipts,
    }


def _agent_handoff_instructions() -> list[dict[str, Any]]:
    return [
        {
            "platform_id": "workbuddy",
            "mode": "inline_learning_workflow",
            "entrypoint_ref": "platform:packs/workbuddy",
            "allowed_actions": [
                "open package",
                "inspect claim boundary",
                "show rollback and limitations",
                "ask user before any external customer action",
            ],
            "forbidden_actions": [
                "production_mutation",
                "scope_escalation",
                "automatic_customer_sending",
                "credential_request",
            ],
            "production_mutation_allowed": False,
            "scope_escalation_allowed": False,
            "automatic_customer_sending_allowed": False,
        },
        {
            "platform_id": "hermes",
            "mode": "agent_skill_http_tools",
            "entrypoint_ref": "platform:packs/hermes",
            "allowed_actions": [
                "validate package",
                "summarize evidence references",
                "prepare operator-owned handoff notes",
            ],
            "forbidden_actions": [
                "production_mutation",
                "scope_escalation",
                "automatic_customer_sending",
                "credential_request",
            ],
            "production_mutation_allowed": False,
            "scope_escalation_allowed": False,
            "automatic_customer_sending_allowed": False,
        },
        {
            "platform_id": "codex",
            "mode": "terminal_skill",
            "entrypoint_ref": "skills:study-anything",
            "allowed_actions": [
                "run verifier",
                "inspect metadata package",
                "prepare local audit notes",
            ],
            "forbidden_actions": [
                "production_mutation",
                "scope_escalation",
                "automatic_customer_sending",
                "credential_request",
            ],
            "production_mutation_allowed": False,
            "scope_escalation_allowed": False,
            "automatic_customer_sending_allowed": False,
        },
    ]


def _build_manifest(package: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    artifact_map = [
        ("delivery_trust_receipt", "delivery-trust-receipt.json", "delivery_trust_receipt"),
        ("claim_boundary", "claim-boundary.json", "claim_boundary"),
        ("limitations", "limitations.json", "limitations"),
        ("rollback_strategy", "rollback-strategy.json", "rollback_strategy"),
        ("controlled_failure_summary", "controlled-failure-summary.json", "controlled_failure_summary"),
        ("human_reconstruction_summary", "human-reconstruction-summary.json", "human_reconstruction_summary"),
        ("dual_loop_gate_receipt", "dual-loop-gate-receipt.json", "dual_loop_gate_receipt"),
        ("external_eval_receipts", "external-eval-receipts.json", "external_eval_receipts"),
        ("agent_handoff_instructions", "agent-handoff-instructions.json", "agent_handoff_instructions"),
        ("provenance", "provenance.json", "provenance"),
    ]
    artifacts: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    for key, path, kind in artifact_map:
        value = package[key]
        digest = sha256_payload(value)
        artifact = {
            "path": path,
            "package_key": key,
            "kind": kind,
            "sha256": digest,
            "bytes": len(dump_json(value).encode("utf-8")),
        }
        artifacts.append(artifact)
        refs.append(
            {
                "path": path,
                "kind": kind,
                "sha256": digest,
            }
        )
    manifest = {
        "schema_version": "customer-handoff-package-manifest-v1",
        "package_schema_version": CUSTOMER_HANDOFF_PACKAGE_SCHEMA_VERSION,
        "package_id": package["package_id"],
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "entrypoint": "customer-handoff-package.json",
        "artifacts": artifacts,
        "zip_root": ZIP_ROOT,
    }
    return manifest, refs


def build_customer_handoff_package(
    delivery_trust_receipt: Mapping[str, Any],
    failure_contract: Mapping[str, Any],
    sandbox_receipt: Mapping[str, Any],
    attention_summary: Mapping[str, Any],
    dual_loop_gate_receipt: Mapping[str, Any],
    *,
    external_eval_receipts: Mapping[str, Any] | None = None,
    package_id: str = "customer-handoff-package-demo-001",
) -> dict[str, Any]:
    receipt = delivery_trust.validate_delivery_trust_receipt(delivery_trust_receipt)
    if receipt.get("status") != "allowed":
        raise CustomerHandoffError("blocked delivery trust cannot produce handoff package")
    contract = dual_loop.validate_failure_contract(failure_contract)
    sandbox = dual_loop.validate_sandbox_receipt(sandbox_receipt)
    attention = dual_loop.validate_attention_summary(attention_summary)
    gate = dual_loop.validate_gate_receipt(dual_loop_gate_receipt)
    if gate.get("status") != "allowed":
        raise CustomerHandoffError("dual-loop gate must be allowed for handoff package")
    contract_id = contract["contract_id"]
    for artifact_name, artifact in (
        ("sandbox_receipt", sandbox),
        ("attention_summary", attention),
        ("dual_loop_gate_receipt", gate),
    ):
        if artifact.get("contract_id") != contract_id:
            raise CustomerHandoffError(f"{artifact_name} contract_id does not match")
    if receipt.get("candidate_artifact_ref") != contract.get("candidate_artifact_ref"):
        raise CustomerHandoffError("delivery trust candidate ref does not match contract")

    rollback = sandbox["rollback"]
    eval_receipts = (
        dict(external_eval_receipts)
        if external_eval_receipts is not None
        else _default_external_eval_receipts()
    )
    package: dict[str, Any] = {
        "schema_version": CUSTOMER_HANDOFF_PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "project_id": receipt["project_id"],
        "candidate_artifact_ref": receipt["candidate_artifact_ref"],
        "status": PACKAGE_STATUS,
        "decision": PACKAGE_DECISION,
        "manifest": {},
        "delivery_trust_receipt": dict(receipt),
        "claim_boundary": dict(receipt["claim_boundary"]),
        "limitations": {
            "not_claimed": list(receipt["claim_boundary"]["not_claimed"]),
            "requires_before_real_production": list(
                receipt["claim_boundary"]["requires_before_real_production"]
            ),
            "not_production_approval": True,
            "not_legal_compliance_or_security_certification": True,
            "not_customer_outcome_guarantee": True,
            "not_ai_review_black_box": True,
        },
        "rollback_strategy": {
            "available": bool(rollback.get("available")),
            "rehearsed": bool(rollback.get("rehearsed")),
            "rollback_ref": rollback.get("rollback_ref"),
            "production_mutation_required": False,
        },
        "controlled_failure_summary": {
            "contract_id": contract_id,
            "risk_level": contract["risk"]["level"],
            "budget_level": sandbox["risk_budget"]["budget_level"],
            "observed_level": sandbox["risk_budget"]["observed_level"],
            "risk_within_budget": bool(sandbox["risk_budget"]["within_budget"]),
            "sandbox_status": sandbox["status"],
            "contained_failure_count": len(sandbox.get("observed_failures", [])),
            "production_mutation": False,
            "irreversible_external_effects": False,
            "rollback_ref": rollback.get("rollback_ref"),
        },
        "human_reconstruction_summary": {
            "summary_id": attention["summary_id"],
            "contract_id": contract_id,
            "status": attention["status"],
            "required_mrus_total": attention["required_mrus_total"],
            "required_mrus_passed": attention["required_mrus_passed"],
            "strong_evidence_count": attention["strong_evidence_count"],
            "weak_evidence_count": attention["weak_evidence_count"],
            "active_reconstruction_required": True,
            "passive_attention_only": False,
        },
        "dual_loop_gate_receipt": dict(gate),
        "external_eval_receipts": eval_receipts,
        "artifact_refs": [],
        "agent_handoff_instructions": _agent_handoff_instructions(),
        "provenance": {
            "source": "local_deterministic_dual_loop_evidence",
            "created_by": "study-anything-cognitive-black-box",
            "risk_level": contract["risk"]["level"],
            "delivery_trust_receipt_id": receipt["receipt_id"],
            "dual_loop_gate_id": gate["gate_id"],
            "model_calls_performed": False,
            "production_mutation_performed": False,
            "automatic_customer_sending_performed": False,
        },
        "customer_delivery_scope": dict(receipt["customer_delivery_scope"]),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(PACKAGE_PRIVACY_FLAGS),
    }
    manifest, refs = _build_manifest(package)
    package["manifest"] = manifest
    package["artifact_refs"] = refs
    return validate_customer_handoff_package(package)


def render_html_report(title: str, payload: Mapping[str, Any]) -> str:
    return dual_loop.render_html_report(title, payload)


def write_html_report(path: str | Path, title: str, payload: Mapping[str, Any]) -> None:
    dual_loop.write_html_report(path, title, payload)


def write_zip_package(path: str | Path, package: Mapping[str, Any], html: str | None = None) -> None:
    validated = validate_customer_handoff_package(package)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    html_body = html or render_html_report("Customer Handoff Package", validated)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{ZIP_ROOT}/manifest.json", dump_json(validated["manifest"]))
        archive.writestr(f"{ZIP_ROOT}/customer-handoff-package.json", dump_json(validated))
        archive.writestr(f"{ZIP_ROOT}/customer-handoff-package.html", html_body)
        for artifact in validated["manifest"]["artifacts"]:
            key = artifact["package_key"]
            archive.writestr(f"{ZIP_ROOT}/{artifact['path']}", dump_json(validated[key]))


def validate_zip_package(path: str | Path) -> dict[str, Any]:
    with zipfile.ZipFile(path, "r") as archive:
        names = set(archive.namelist())
        package_name = f"{ZIP_ROOT}/customer-handoff-package.json"
        manifest_name = f"{ZIP_ROOT}/manifest.json"
        if package_name not in names or manifest_name not in names:
            raise CustomerHandoffError("customer handoff zip is missing package or manifest")
        package = json.loads(archive.read(package_name).decode("utf-8"))
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        if not isinstance(package, dict) or not isinstance(manifest, dict):
            raise CustomerHandoffError("customer handoff zip payload is invalid")
        if package.get("manifest") != manifest:
            raise CustomerHandoffError("customer handoff zip manifest does not match package")
        validated = validate_customer_handoff_package(package)
        for artifact in validated["manifest"]["artifacts"]:
            artifact_name = f"{ZIP_ROOT}/{artifact['path']}"
            if artifact_name not in names:
                raise CustomerHandoffError(f"customer handoff zip missing {artifact_name}")
            payload = json.loads(archive.read(artifact_name).decode("utf-8"))
            if sha256_payload(payload) != artifact["sha256"]:
                raise CustomerHandoffError(f"customer handoff zip digest mismatch: {artifact_name}")
        return validated
