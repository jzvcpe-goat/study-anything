"""Build a real-Agent delivery review set from a frozen public submission."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from study_anything.cbb.protocol.canonical import (
    assert_safe_metadata,
    canonical_sha256,
    pretty_json,
)
from study_anything.cbb.protocol.models import StrictProtocolModel


REAL_AGENT_SUITE_ID: Literal["real-agent-delivery-v0.1"] = "real-agent-delivery-v0.1"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_SHA_PATTERN = r"^[0-9a-f]{40}$"
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._:-]{0,159}$"


class RealAgentSelectionProtocolV1(StrictProtocolModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["real-agent-selection-protocol-v1"]
    suite_id: Literal["real-agent-delivery-v0.1"]
    source_repository: str = Field(pattern=r"^https://", max_length=500)
    source_revision: str = Field(pattern=GIT_SHA_PATTERN)
    submission_path: str = Field(min_length=1, max_length=500)
    predictions_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    results_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    agent_name: str = Field(min_length=1, max_length=160)
    model_name: str = Field(min_length=1, max_length=160)
    language: Literal["typescript"]
    selection_seed: str = Field(min_length=1, max_length=160)
    selection_order: Literal["sha256-seed-outcome-task-id"]
    passed_case_count: int = Field(ge=1, le=100)
    failed_case_count: int = Field(ge=1, le=100)
    max_cases_per_repository_per_stratum: Literal[1]
    task_context_source: Literal["public-github-issue-or-pull-request"]
    raw_candidate_payload_vendored: Literal[False] = False
    raw_issue_body_vendored: Literal[False] = False
    local_official_scorer_reexecuted: Literal[False] = False
    target_scope: Literal["personal_local"]
    claim_boundary: str = Field(min_length=1, max_length=1600)


class RealAgentDeliveryCaseV1(StrictProtocolModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["real-agent-delivery-case-v1"]
    suite_id: Literal["real-agent-delivery-v0.1"]
    case_id: str = Field(pattern=IDENTIFIER_PATTERN)
    upstream_task_id: str = Field(min_length=1, max_length=240)
    repository: str = Field(min_length=3, max_length=240)
    issue_number: int = Field(ge=1)
    issue_uri: str = Field(pattern=r"^https://", max_length=1000)
    issue_kind: Literal["issue", "pull_request"]
    issue_title: str = Field(min_length=1, max_length=500)
    issue_title_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    issue_body_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    issue_snapshot_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_patch_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_patch_bytes: int = Field(ge=1, le=20_000_000)
    changed_file_count: int = Field(ge=1, le=10_000)
    added_line_count: int = Field(ge=0, le=1_000_000)
    deleted_line_count: int = Field(ge=0, le=1_000_000)
    review_material_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    published_functional_outcome: Literal["passed", "failed"]
    published_result_ref: str = Field(pattern=r"^https://", max_length=1000)
    published_result_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    official_submission_accepted: Literal[True]
    local_official_scorer_reexecuted: Literal[False] = False
    clearance_reference_status: Literal["pending_blinded_human_adjudication"]
    raw_candidate_payload_included: Literal[False] = False
    raw_issue_body_included: Literal[False] = False

    @model_validator(mode="after")
    def validate_case(self) -> RealAgentDeliveryCaseV1:
        if self.added_line_count + self.deleted_line_count == 0:
            raise ValueError("real Agent candidate patch has no changed lines")
        return self


class RealAgentCaseSetV1(StrictProtocolModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["real-agent-case-set-v1"]
    suite_id: Literal["real-agent-delivery-v0.1"]
    protocol_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    source_repository: str = Field(pattern=r"^https://", max_length=500)
    source_revision: str = Field(pattern=GIT_SHA_PATTERN)
    submission_path: str = Field(min_length=1, max_length=500)
    agent_name: str = Field(min_length=1, max_length=160)
    model_name: str = Field(min_length=1, max_length=160)
    selection_seed: str = Field(min_length=1, max_length=160)
    cases: list[RealAgentDeliveryCaseV1] = Field(min_length=2, max_length=200)
    source_material_verified_at_generation: Literal[True]
    paired_agent_review_completed: Literal[False] = False
    human_adjudication_completed: Literal[False] = False
    effectiveness_claim_allowed: Literal[False] = False
    claim_boundary: str = Field(min_length=1, max_length=1600)

    @model_validator(mode="after")
    def validate_set(self) -> RealAgentCaseSetV1:
        case_ids = [case.case_id for case in self.cases]
        task_ids = [case.upstream_task_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("real Agent case set contains duplicate case IDs")
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("real Agent case set contains duplicate task IDs")
        return self


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def load_real_agent_protocol(path: Path) -> RealAgentSelectionProtocolV1:
    payload = _read_json(path, label="real Agent selection protocol")
    assert_safe_metadata(payload, label="real Agent selection protocol")
    return RealAgentSelectionProtocolV1.model_validate(payload)


def _task_identity(task_id: str) -> tuple[str, str, int]:
    if task_id.count("__") != 1:
        raise ValueError(f"unsupported SWE task identity: {task_id}")
    owner, repository_and_number = task_id.split("__", 1)
    repository, separator, number_text = repository_and_number.rpartition("-")
    if not owner or not repository or separator != "-" or not number_text.isdigit():
        raise ValueError(f"unsupported SWE task identity: {task_id}")
    return owner, repository, int(number_text)


def _repository_key(task_id: str) -> str:
    owner, repository, _ = _task_identity(task_id)
    return f"{owner}/{repository}".lower()


def _patch_stats(patch: str) -> tuple[int, int, int]:
    if not patch.strip() or not patch.startswith("diff --git "):
        raise ValueError("real Agent candidate is not a non-empty unified Git patch")
    changed_files: set[str] = set()
    added = 0
    deleted = 0
    for line in patch.splitlines():
        if line.startswith("diff --git a/"):
            parts = line.split(" ", 3)
            if len(parts) < 4 or not parts[2].startswith("a/") or not parts[3].startswith("b/"):
                raise ValueError("candidate patch contains an invalid diff header")
            changed_files.add(parts[3][2:])
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            deleted += 1
    if not changed_files:
        raise ValueError("candidate patch contains no changed files")
    return len(changed_files), added, deleted


def _selected_task_ids(
    *,
    predictions: dict[str, Any],
    results: dict[str, Any],
    protocol: RealAgentSelectionProtocolV1,
) -> list[tuple[str, Literal["passed", "failed"]]]:
    selections: list[tuple[str, Literal["passed", "failed"]]] = []
    strata: tuple[tuple[Literal["passed", "failed"], str, int], ...] = (
        ("passed", "success_ids", protocol.passed_case_count),
        ("failed", "failure_ids", protocol.failed_case_count),
    )
    for outcome, result_key, count in strata:
        values = results.get(result_key)
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError(f"published results have no valid {result_key}")
        candidates = sorted(
            set(values).intersection(predictions),
            key=lambda task_id: _sha256_text(f"{protocol.selection_seed}:{outcome}:{task_id}"),
        )
        selected: list[str] = []
        repositories: set[str] = set()
        for task_id in candidates:
            repository = _repository_key(task_id)
            if repository in repositories:
                continue
            selected.append(task_id)
            repositories.add(repository)
            if len(selected) == count:
                break
        if len(selected) != count:
            raise ValueError(f"not enough cross-repository {outcome} candidates")
        selections.extend((task_id, outcome) for task_id in selected)
    return selections


def selected_real_agent_task_ids(
    *,
    predictions: dict[str, Any],
    results: dict[str, Any],
    protocol: RealAgentSelectionProtocolV1,
) -> list[tuple[str, Literal["passed", "failed"]]]:
    """Return the frozen cross-repository selection without reading patch content."""

    return _selected_task_ids(
        predictions=predictions,
        results=results,
        protocol=protocol,
    )


def _issue_material(issue: dict[str, Any], *, repository: str, number: int) -> tuple[str, str]:
    expected_api_uri = f"https://api.github.com/repos/{repository}/issues/{number}"
    repository_api = issue.get("repository_url")
    if repository_api != f"https://api.github.com/repos/{repository}":
        raise ValueError("GitHub issue response repository does not match the task")
    if issue.get("number") != number:
        raise ValueError("GitHub issue response number does not match the task")
    html_uri = issue.get("html_url")
    title = issue.get("title")
    body = issue.get("body")
    if not isinstance(html_uri, str) or not html_uri.startswith("https://github.com/"):
        raise ValueError("GitHub issue response has no public HTML URI")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("GitHub issue response has no title")
    if body is None:
        body = ""
    if not isinstance(body, str):
        raise ValueError("GitHub issue response body is invalid")
    kind = "pull request" if isinstance(issue.get("pull_request"), dict) else "issue"
    markdown = (
        f"# {title.strip()}\n\n"
        f"- Source: {html_uri}\n"
        f"- API snapshot: {expected_api_uri}\n"
        f"- Repository: {repository}\n"
        f"- Kind: {kind}\n\n"
        f"{body.rstrip()}\n"
    )
    return title.strip(), markdown


def _evidence_item(
    *,
    case_id: str,
    evidence_type: str,
    status: Literal["passed", "missing"],
    summary_code: str,
    blocking: bool,
) -> dict[str, Any]:
    payload = {
        "evidence_ref": f"real-agent:{case_id}:{evidence_type}",
        "evidence_type": evidence_type,
        "status": status,
        "summary_code": summary_code,
        "blocking": blocking,
    }
    payload["evidence_digest_sha256"] = canonical_sha256(payload)
    return payload


def _reviewer_packet(case: RealAgentDeliveryCaseV1) -> dict[str, Any]:
    packet = {
        "schema_version": "reviewer-case-packet-v1",
        "suite_id": case.suite_id,
        "case_id": case.case_id,
        "candidate": {
            "candidate_id": f"candidate:{case.case_id}",
            "candidate_digest_sha256": case.candidate_patch_digest_sha256,
            "subject_digest_sha256": case.candidate_patch_digest_sha256,
            "source_snapshot_digest_sha256": case.issue_snapshot_digest_sha256,
            "context_digest_sha256": case.review_material_digest_sha256,
            "task_summary_code": "real-github-agent-generated-patch",
            "declared_risk_level": "high",
            "target_scope": "personal_local",
            "intended_recipient_role": "local-project-owner",
            "risk_owner_role": "local-project-owner",
            "prohibited_use_codes": [
                "customer-handoff",
                "production-execution",
                "public-release",
            ],
            "tool_permission_ids": ["read-local-review-material"],
            "issue_title": case.issue_title,
            "changed_file_count": case.changed_file_count,
            "added_line_count": case.added_line_count,
            "deleted_line_count": case.deleted_line_count,
            "review_material_digest_sha256": case.review_material_digest_sha256,
            "visible_evidence": [
                _evidence_item(
                    case_id=case.case_id,
                    evidence_type="source-provenance",
                    status="passed",
                    summary_code="public-submission-and-task-snapshot-bound",
                    blocking=True,
                ),
                _evidence_item(
                    case_id=case.case_id,
                    evidence_type="candidate-material",
                    status="passed",
                    summary_code="real-agent-patch-available-for-review",
                    blocking=True,
                ),
                _evidence_item(
                    case_id=case.case_id,
                    evidence_type="scorer-result",
                    status="missing",
                    summary_code="official-result-withheld-for-blinded-review",
                    blocking=True,
                ),
                _evidence_item(
                    case_id=case.case_id,
                    evidence_type="rollback-or-containment",
                    status="passed",
                    summary_code="patch-can-be-reverted-before-release",
                    blocking=True,
                ),
                _evidence_item(
                    case_id=case.case_id,
                    evidence_type="responsibility-boundary",
                    status="passed",
                    summary_code="local-project-owner-retains-final-responsibility",
                    blocking=True,
                ),
            ],
        },
        "review_material_digest_sha256": case.review_material_digest_sha256,
        "review_material_available_locally": True,
        "official_scorer_result_included": False,
        "reference_label_included": False,
        "hidden_tests_included": False,
        "raw_candidate_payload_included": False,
        "raw_issue_body_included": False,
    }
    assert_safe_metadata(packet, label=f"real Agent reviewer packet {case.case_id}")
    return packet


def _report_markdown(case_set: RealAgentCaseSetV1) -> str:
    rows = "\n".join(
        "| {case_id} | `{task}` | {title} | {files} | +{added}/-{deleted} | {outcome} |".format(
            case_id=case.case_id,
            task=case.upstream_task_id,
            title=case.issue_title.replace("|", "\\|"),
            files=case.changed_file_count,
            added=case.added_line_count,
            deleted=case.deleted_line_count,
            outcome=case.published_functional_outcome,
        )
        for case in case_set.cases
    )
    return f"""# 真实 Agent 交付候选评测集 v0.1

本评测集从冻结的 SWE-bench-Live 官方提交中选择 12 个真实 GitHub 任务和真实
Agent 补丁。选择按通过/失败各 6 例分层，并在每个分层中限制为每个仓库最多
1 例。排序只由固定 seed、功能结果分层和任务 ID 的 SHA-256 决定，不读取补丁
内容进行挑选。

| Case | 上游任务 | 任务标题 | 文件数 | 行变更 | 已发布功能结果 |
| --- | --- | --- | ---: | ---: | --- |
{rows}

## 当前结论

- 已验证：公开预测文件与结果文件哈希、12 个任务身份、公开 issue/PR 快照、补丁
  非空性、补丁统计、分层选择规则、盲化 reviewer packet 和本地材料绑定。
- 未验证：本机重新执行官方 scorer、四组 Agent 配对审核、真人盲评、误放行率、
  误阻塞率、认知负担和成本效果。
- 因此，本结果只证明“真实候选评测集已经可复现地建立”，不证明 Delivery
  Clearance 已经有效，也不授权任何候选进入客户或生产范围。

## 放行边界

功能测试通过不等于交付放行。12 个案例的最终 clearance reference 都保持为
`pending_blinded_human_adjudication`。原始补丁和 issue/PR 正文只写入本地忽略目录，
仓库中仅保留哈希、统计量、来源与盲化包。
"""


def build_real_agent_case_set(
    *,
    protocol: RealAgentSelectionProtocolV1,
    predictions_path: Path,
    results_path: Path,
    issue_response_dir: Path,
    output_dir: Path,
    material_output_dir: Path,
    replace: bool = False,
) -> dict[str, Any]:
    if _sha256_file(predictions_path) != protocol.predictions_digest_sha256:
        raise ValueError("public predictions file digest drifted")
    if _sha256_file(results_path) != protocol.results_digest_sha256:
        raise ValueError("public results file digest drifted")
    predictions = _read_json(predictions_path, label="public Agent predictions")
    results = _read_json(results_path, label="published official results")
    if set(predictions) != set(results.get("submitted_ids", [])):
        raise ValueError("prediction coverage disagrees with published submitted IDs")
    if results.get("empty_patch") != 0 or results.get("incomplete") != 0:
        raise ValueError("source submission contains empty or incomplete candidates")
    if int(results.get("error", 0)) != len(results.get("error_ids", [])):
        raise ValueError("source submission error counts disagree")

    if output_dir.exists():
        if not replace:
            raise ValueError(f"output directory already exists: {output_dir}")
        shutil.rmtree(output_dir)
    if material_output_dir.exists():
        if not replace:
            raise ValueError(f"material output directory already exists: {material_output_dir}")
        shutil.rmtree(material_output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "reviewer-packets").mkdir()
    (output_dir / "oracle").mkdir()
    material_output_dir.mkdir(parents=True)

    protocol_digest = canonical_sha256(protocol)
    selected = _selected_task_ids(
        predictions=predictions,
        results=results,
        protocol=protocol,
    )
    cases: list[RealAgentDeliveryCaseV1] = []
    for outcome in ("passed", "failed"):
        stratum = [item for item in selected if item[1] == outcome]
        for index, (task_id, typed_outcome) in enumerate(stratum, start=1):
            owner, repository_name, issue_number = _task_identity(task_id)
            repository = f"{owner}/{repository_name}"
            issue_path = issue_response_dir / f"{task_id}.json"
            issue = _read_json(issue_path, label=f"GitHub issue response {task_id}")
            issue_title, issue_markdown = _issue_material(
                issue,
                repository=repository,
                number=issue_number,
            )
            prediction = predictions.get(task_id)
            if not isinstance(prediction, dict) or not isinstance(
                prediction.get("model_patch"), str
            ):
                raise ValueError(f"prediction has no model patch: {task_id}")
            patch = str(prediction["model_patch"])
            changed_files, added, deleted = _patch_stats(patch)
            case_id = f"agent-{outcome}-{index:02d}"
            issue_snapshot_basis = {
                "repository_url": issue.get("repository_url"),
                "html_url": issue.get("html_url"),
                "number": issue.get("number"),
                "title": issue_title,
                "body_digest_sha256": _sha256_text(str(issue.get("body") or "")),
                "updated_at": issue.get("updated_at"),
                "closed_at": issue.get("closed_at"),
                "kind": "pull_request" if isinstance(issue.get("pull_request"), dict) else "issue",
            }
            issue_snapshot_digest = canonical_sha256(issue_snapshot_basis)
            material_digest = sha256(
                issue_markdown.encode("utf-8") + b"\0" + patch.encode("utf-8")
            ).hexdigest()
            published_result_basis = {
                "source_revision": protocol.source_revision,
                "results_digest_sha256": protocol.results_digest_sha256,
                "upstream_task_id": task_id,
                "published_functional_outcome": typed_outcome,
            }
            case = RealAgentDeliveryCaseV1(
                schema_version="real-agent-delivery-case-v1",
                suite_id=protocol.suite_id,
                case_id=case_id,
                upstream_task_id=task_id,
                repository=repository,
                issue_number=issue_number,
                issue_uri=str(issue["html_url"]),
                issue_kind=(
                    "pull_request" if isinstance(issue.get("pull_request"), dict) else "issue"
                ),
                issue_title=issue_title,
                issue_title_digest_sha256=_sha256_text(issue_title),
                issue_body_digest_sha256=_sha256_text(str(issue.get("body") or "")),
                issue_snapshot_digest_sha256=issue_snapshot_digest,
                candidate_patch_digest_sha256=_sha256_text(patch),
                candidate_patch_bytes=len(patch.encode("utf-8")),
                changed_file_count=changed_files,
                added_line_count=added,
                deleted_line_count=deleted,
                review_material_digest_sha256=material_digest,
                published_functional_outcome=typed_outcome,
                published_result_ref=(
                    f"{protocol.source_repository}/blob/{protocol.source_revision}/"
                    f"{protocol.submission_path}/results.json"
                ),
                published_result_digest_sha256=canonical_sha256(published_result_basis),
                official_submission_accepted=True,
                local_official_scorer_reexecuted=False,
                clearance_reference_status="pending_blinded_human_adjudication",
                raw_candidate_payload_included=False,
                raw_issue_body_included=False,
            )
            cases.append(case)
            material_dir = material_output_dir / case_id
            material_dir.mkdir()
            (material_dir / "issue.md").write_text(issue_markdown, encoding="utf-8")
            (material_dir / "candidate.patch").write_text(patch, encoding="utf-8")
            (output_dir / "reviewer-packets" / f"{case_id}.json").write_text(
                pretty_json(_reviewer_packet(case)),
                encoding="utf-8",
            )
            oracle = {
                "schema_version": "real-agent-functional-oracle-v1",
                "suite_id": protocol.suite_id,
                "case_id": case_id,
                "candidate_patch_digest_sha256": case.candidate_patch_digest_sha256,
                "published_functional_outcome": typed_outcome,
                "published_result_ref": case.published_result_ref,
                "published_result_digest_sha256": case.published_result_digest_sha256,
                "local_official_scorer_reexecuted": False,
                "clearance_reference_status": "pending_blinded_human_adjudication",
                "raw_candidate_payload_included": False,
                "raw_hidden_tests_included": False,
            }
            assert_safe_metadata(oracle, label=f"real Agent oracle {case_id}")
            (output_dir / "oracle" / f"{case_id}.json").write_text(
                pretty_json(oracle),
                encoding="utf-8",
            )

    case_set = RealAgentCaseSetV1(
        schema_version="real-agent-case-set-v1",
        suite_id=protocol.suite_id,
        protocol_digest_sha256=protocol_digest,
        source_repository=protocol.source_repository,
        source_revision=protocol.source_revision,
        submission_path=protocol.submission_path,
        agent_name=protocol.agent_name,
        model_name=protocol.model_name,
        selection_seed=protocol.selection_seed,
        cases=cases,
        source_material_verified_at_generation=True,
        paired_agent_review_completed=False,
        human_adjudication_completed=False,
        effectiveness_claim_allowed=False,
        claim_boundary=protocol.claim_boundary,
    )
    (output_dir / "case-set.json").write_text(pretty_json(case_set), encoding="utf-8")
    result = {
        "schema_version": "real-agent-case-set-result-v1",
        "status": "pass",
        "suite_id": protocol.suite_id,
        "case_count": len(cases),
        "published_passed_count": sum(
            case.published_functional_outcome == "passed" for case in cases
        ),
        "published_failed_count": sum(
            case.published_functional_outcome == "failed" for case in cases
        ),
        "distinct_repository_count": len({case.repository.lower() for case in cases}),
        "source_material_verified_at_generation": True,
        "local_official_scorer_reexecuted": False,
        "paired_agent_review_completed": False,
        "human_adjudication_completed": False,
        "effectiveness_claim_allowed": False,
        "release_authorized": False,
        "maximum_scope": "personal_local_benchmark_rehearsal",
        "case_set_digest_sha256": canonical_sha256(case_set),
        "claim_boundary": protocol.claim_boundary,
    }
    assert_safe_metadata(result, label="real Agent case-set result")
    (output_dir / "result.json").write_text(pretty_json(result), encoding="utf-8")
    (output_dir / "report.zh-CN.md").write_text(
        _report_markdown(case_set),
        encoding="utf-8",
    )
    return result
