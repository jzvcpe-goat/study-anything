"""Local browser cockpit for observed human Delivery Clearance review."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import Any, Literal
from urllib.parse import urlparse
import webbrowser

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
import uvicorn

from study_anything.cbb.benchmark.adjudication import (
    RATIONALE_CODE_PATTERN,
    record_blinded_adjudication,
    validate_blinded_adjudication_packet,
    validate_blinded_adjudication_receipt,
)
from study_anything.cbb.benchmark.human_reconstruction import (
    boundary_questions,
    full_review_material,
    question_set_digest,
)
from study_anything.cbb.benchmark.models import (
    BlindedAdjudicationReceiptV1,
    ClearanceDisposition,
    HumanReviewSessionV1,
    ScorerExecutionReceiptV1,
)
from study_anything.cbb.benchmark.runner import record_human_review_session
from study_anything.cbb.protocol.canonical import assert_safe_metadata, canonical_sha256


ReviewMode = Literal[
    "boundary_reconstruction",
    "full_review_reference",
    "blinded_adjudication",
]

MODE_LABELS: dict[ReviewMode, str] = {
    "boundary_reconstruction": "Boundary reconstruction",
    "full_review_reference": "Full review reference",
    "blinded_adjudication": "Blinded adjudication",
}

DEFAULT_PROTOCOL_PATH = Path("docs/evaluation/pilot-v0.1-human-protocol.json")
DEFAULT_PORT = 8765


class ReviewCockpitError(RuntimeError):
    """Raised when the local review cockpit cannot preserve the frozen protocol."""


class ReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mode: ReviewMode
    item_token: str = Field(min_length=20, max_length=200)
    answers: list[Literal["1", "2", "3", "u"]] | None = None
    active_review_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    nasa_tlx_score: float | None = Field(default=None, ge=0, le=100)
    disposition: Literal["cleared", "restricted", "held", "denied"] | None = None
    rationale_codes: list[str] | None = Field(default=None, max_length=12)


@dataclass(frozen=True)
class ModeConfig:
    mode: ReviewMode
    packet_dir: Path
    output_path: Path
    role: str
    order_seed: str
    max_items: int


@dataclass
class ActiveItem:
    case_id: str
    token: str
    started_at: str
    started_monotonic: float


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewCockpitError(f"could not read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise ReviewCockpitError(f"{label} must be a JSON object")
    assert_safe_metadata(payload, label=label)
    return payload


def _repo_path(repo_root: Path, value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ReviewCockpitError(f"human protocol {field} is invalid")
    root = repo_root.resolve()
    resolved = (root / value).resolve()
    if resolved != root and root not in resolved.parents:
        raise ReviewCockpitError(f"human protocol {field} escapes the repository")
    return resolved


def load_canonical_mode_configs(
    repo_root: Path,
    protocol_path: Path,
    *,
    max_items: int,
) -> dict[ReviewMode, ModeConfig]:
    if max_items < 1:
        raise ReviewCockpitError("max-items must be at least one")
    protocol = _read_json(protocol_path, label="canonical human benchmark protocol")
    if protocol.get("schema_version") != "benchmark-human-protocol-v1":
        raise ReviewCockpitError("unsupported canonical human protocol version")
    claim = protocol.get("claim_boundary")
    privacy = protocol.get("privacy")
    if not isinstance(claim, dict) or claim.get("maximum_scope") != "personal_local":
        raise ReviewCockpitError("review cockpit requires a personal_local protocol")
    if claim.get("independent_reviewer_claimed") is not False:
        raise ReviewCockpitError("local cockpit cannot claim independent review")
    if not isinstance(privacy, dict) or any(
        privacy.get(field) is not False
        for field in (
            "raw_answers_included",
            "attention_stream_included",
            "screenshots_included",
            "keystrokes_included",
            "biometrics_included",
        )
    ):
        raise ReviewCockpitError("canonical human protocol privacy boundary drifted")

    configs: dict[ReviewMode, ModeConfig] = {}
    for mode in MODE_LABELS:
        mode_payload = protocol.get(mode)
        if mode_payload is None:
            continue
        if not isinstance(mode_payload, dict):
            raise ReviewCockpitError(f"canonical human protocol mode is invalid: {mode}")
        cap = mode_payload.get("max_items_per_batch")
        if not isinstance(cap, int) or cap < 1:
            raise ReviewCockpitError(f"canonical batch cap is invalid for {mode}")
        if max_items > cap:
            raise ReviewCockpitError(f"max-items exceeds the canonical {mode} batch cap of {cap}")
        role_field = "adjudicator_role" if mode == "blinded_adjudication" else "reviewer_role"
        role = mode_payload.get(role_field)
        order_seed = mode_payload.get("order_seed")
        if not isinstance(role, str) or not role:
            raise ReviewCockpitError(f"canonical {role_field} is invalid for {mode}")
        if not isinstance(order_seed, str) or not order_seed:
            raise ReviewCockpitError(f"canonical order seed is invalid for {mode}")
        configs[mode] = ModeConfig(
            mode=mode,
            packet_dir=_repo_path(repo_root, mode_payload.get("packet_dir"), field="packet_dir"),
            output_path=_repo_path(repo_root, mode_payload.get("output"), field="output"),
            role=role,
            order_seed=order_seed,
            max_items=max_items,
        )
    if not configs:
        raise ReviewCockpitError("canonical human protocol enables no review modes")
    return configs


def _append_jsonl(path: Path, payload: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                payload.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())


def _existing_sessions(path: Path) -> dict[str, HumanReviewSessionV1]:
    if not path.exists():
        return {}
    sessions: dict[str, HumanReviewSessionV1] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            session = HumanReviewSessionV1.model_validate_json(line)
        except ValueError as exc:
            raise ReviewCockpitError(f"invalid human review session at line {line_number}") from exc
        if session.session_id in sessions:
            raise ReviewCockpitError(f"duplicate human review session at line {line_number}")
        sessions[session.session_id] = session
    return sessions


def _existing_adjudications(path: Path) -> dict[str, BlindedAdjudicationReceiptV1]:
    if not path.exists():
        return {}
    receipts: dict[str, BlindedAdjudicationReceiptV1] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            receipt = validate_blinded_adjudication_receipt(
                BlindedAdjudicationReceiptV1.model_validate_json(line)
            )
        except ValueError as exc:
            raise ReviewCockpitError(f"invalid blinded adjudication at line {line_number}") from exc
        if receipt.receipt_id in receipts:
            raise ReviewCockpitError(f"duplicate blinded adjudication at line {line_number}")
        receipts[receipt.receipt_id] = receipt
    return receipts


class ReviewQueue:
    def __init__(self, config: ModeConfig) -> None:
        self.config = config
        self.lock = threading.Lock()
        self.packets = self._load_packets()
        ordered_case_ids = sorted(
            self.packets,
            key=lambda case_id: sha256(
                f"{config.order_seed}:{case_id}".encode("utf-8")
            ).hexdigest(),
        )
        completed = self._completed_case_ids()
        self.completed_before = len(completed)
        self.case_ids = [case_id for case_id in ordered_case_ids if case_id not in completed][
            : config.max_items
        ]
        self.batch_total = len(self.case_ids)
        self.completed_this_run = 0
        self.active: ActiveItem | None = None

    def _load_packets(self) -> dict[str, dict[str, Any]]:
        if not self.config.packet_dir.is_dir():
            raise ReviewCockpitError(f"packet directory does not exist: {self.config.packet_dir}")
        packets: dict[str, dict[str, Any]] = {}
        for path in sorted(self.config.packet_dir.glob("*.json")):
            payload = _read_json(path, label=f"{self.config.mode} packet")
            if self.config.mode == "blinded_adjudication":
                payload = validate_blinded_adjudication_packet(payload)
            else:
                if (
                    payload.get("reference_label_included") is not False
                    or payload.get("hidden_tests_included") is not False
                    or payload.get("official_scorer_result_included") is not False
                ):
                    raise ReviewCockpitError("human review packet is not label-free")
                boundary_questions(payload)
            case_id = payload.get("case_id")
            suite_id = payload.get("suite_id")
            if not isinstance(case_id, str) or not case_id:
                raise ReviewCockpitError("human review packet is missing its case ID")
            if not isinstance(suite_id, str) or not suite_id:
                raise ReviewCockpitError("human review packet is missing its suite ID")
            if case_id in packets:
                raise ReviewCockpitError("duplicate human review packet case ID")
            packets[case_id] = payload
        if not packets:
            raise ReviewCockpitError(f"no packets found for {self.config.mode}")
        return packets

    def _completed_case_ids(self) -> set[str]:
        if self.config.mode == "blinded_adjudication":
            return {
                item.case_id for item in _existing_adjudications(self.config.output_path).values()
            }
        return {
            item.case_id
            for item in _existing_sessions(self.config.output_path).values()
            if item.review_mode == self.config.mode and item.trial_index == 0
        }

    def _ensure_active(self) -> ActiveItem | None:
        if not self.case_ids:
            self.active = None
            return None
        case_id = self.case_ids[0]
        if self.active is None or self.active.case_id != case_id:
            self.active = ActiveItem(
                case_id=case_id,
                token=secrets.token_urlsafe(32),
                started_at=_utc_now(),
                started_monotonic=time.monotonic(),
            )
        return self.active

    @staticmethod
    def _candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
        evidence = candidate.get("visible_evidence", candidate.get("evidence", []))
        return {
            "task_summary_code": candidate.get("task_summary_code"),
            "declared_risk_level": candidate.get("declared_risk_level"),
            "target_scope": candidate.get("target_scope"),
            "intended_recipient_role": candidate.get("intended_recipient_role"),
            "risk_owner_role": candidate.get("risk_owner_role"),
            "prohibited_use_codes": candidate.get("prohibited_use_codes"),
            "tool_permission_ids": candidate.get("tool_permission_ids"),
            "visible_evidence": [
                {
                    "evidence_type": item.get("evidence_type"),
                    "status": item.get("status"),
                    "summary_code": item.get("summary_code"),
                    "blocking": item.get("blocking"),
                }
                for item in evidence
                if isinstance(item, dict)
            ],
        }

    def state(self, *, review_token: str) -> dict[str, Any]:
        with self.lock:
            active = self._ensure_active()
            base: dict[str, Any] = {
                "schema_version": "delivery-clearance.review-cockpit-state.v1",
                "mode": self.config.mode,
                "mode_label": MODE_LABELS[self.config.mode],
                "status": "complete" if active is None else "ready",
                "completed_before_run": self.completed_before,
                "completed_this_run": self.completed_this_run,
                "batch_total": self.batch_total,
                "remaining_in_batch": len(self.case_ids),
                "maximum_scope": "personal_local",
                "independent_reviewer_claimed": False,
                "raw_answers_included": False,
                "review_token": review_token,
            }
            if active is None:
                return base
            packet = self.packets[active.case_id]
            candidate = packet.get("candidate")
            if not isinstance(candidate, dict):
                raise ReviewCockpitError("active packet is missing its candidate")
            base.update(
                {
                    "display_label": (
                        f"Blinded item {self.completed_this_run + 1} of {self.batch_total}"
                    ),
                    "item_token": active.token,
                    "candidate": self._candidate_summary(candidate),
                }
            )
            if self.config.mode in {
                "boundary_reconstruction",
                "full_review_reference",
            }:
                questions = boundary_questions(packet)
                base["questions"] = [
                    {
                        "question_id": question.question_id,
                        "prompt": question.prompt,
                        "options": [option.label for option in question.options],
                    }
                    for question in questions
                ]
                if self.config.mode == "full_review_reference":
                    base["full_review_material"] = full_review_material(packet)
            else:
                scorer = ScorerExecutionReceiptV1.model_validate(packet.get("scorer_receipt"))
                base["official_scorer"] = {
                    "outcome": scorer.outcome.value,
                    "official_scorer_executed": scorer.official_scorer_executed,
                    "benchmark_id": scorer.benchmark_id,
                }
                base["dispositions"] = [
                    {"value": "cleared", "label": "Clear"},
                    {"value": "restricted", "label": "Restrict"},
                    {"value": "held", "label": "Hold"},
                    {"value": "denied", "label": "Deny"},
                ]
            assert_safe_metadata(base, label="review cockpit state")
            return base

    def _validate_active_time(self, submitted_ms: int | None, active: ActiveItem) -> int:
        if submitted_ms is None:
            raise ReviewCockpitError("active review time is required")
        server_elapsed_ms = int((time.monotonic() - active.started_monotonic) * 1000)
        if submitted_ms > server_elapsed_ms + 10_000:
            raise ReviewCockpitError("active review time exceeds the server session window")
        return submitted_ms

    def _submit_review(
        self,
        submission: ReviewSubmission,
        packet: dict[str, Any],
        active: ActiveItem,
    ) -> None:
        questions = boundary_questions(packet)
        if submission.answers is None or len(submission.answers) != len(questions):
            raise ReviewCockpitError("all five boundary questions require an answer")
        correct = 0
        unresolved = 0
        for answer, question in zip(submission.answers, questions, strict=True):
            if answer == "u":
                unresolved += 1
                continue
            option = question.options[int(answer) - 1]
            correct += int(option.code == question.expected_code)
        active_review_ms = self._validate_active_time(submission.active_review_ms, active)
        candidate = packet.get("candidate")
        if not isinstance(candidate, dict) or not isinstance(
            candidate.get("candidate_digest_sha256"), str
        ):
            raise ReviewCockpitError("review packet has no candidate digest")
        review_material_digest = canonical_sha256(packet)
        completed_at = _utc_now()
        session = record_human_review_session(
            suite_id=packet["suite_id"],
            case_id=active.case_id,
            trial_index=0,
            review_mode=self.config.mode,  # type: ignore[arg-type]
            reviewer_role=self.config.role,
            active_review_ms=active_review_ms,
            correct_answers=correct,
            unresolved_questions=unresolved,
            nasa_tlx_score=submission.nasa_tlx_score,
            completed_at=completed_at,
            candidate_digest_sha256=str(candidate["candidate_digest_sha256"]),
            review_material_digest_sha256=review_material_digest,
            collection_method=(
                "interactive_scored_boundary"
                if self.config.mode == "boundary_reconstruction"
                else "interactive_full_review"
            ),
            question_set_digest_sha256=question_set_digest(
                questions,
                review_material_digest_sha256=review_material_digest,
            ),
        )
        existing = _existing_sessions(self.config.output_path)
        if session.session_id in existing:
            raise ReviewCockpitError("human review session already exists")
        _append_jsonl(self.config.output_path, session)

    def _submit_adjudication(
        self,
        submission: ReviewSubmission,
        packet: dict[str, Any],
        active: ActiveItem,
    ) -> None:
        if submission.disposition is None:
            raise ReviewCockpitError("a clearance disposition is required")
        rationale_codes = submission.rationale_codes or []
        if not rationale_codes or any(
            RATIONALE_CODE_PATTERN.fullmatch(code) is None for code in rationale_codes
        ):
            raise ReviewCockpitError("rationale codes must be unique lowercase identifiers")
        if len(rationale_codes) != len(set(rationale_codes)):
            raise ReviewCockpitError("rationale codes must not be duplicated")
        disposition = ClearanceDisposition(submission.disposition)
        receipt = record_blinded_adjudication(
            packet,
            disposition=disposition,
            rationale_codes=rationale_codes,
            adjudicator_role=self.config.role,
            started_at=active.started_at,
            completed_at=_utc_now(),
        )
        existing = _existing_adjudications(self.config.output_path)
        if receipt.receipt_id in existing:
            raise ReviewCockpitError("blinded adjudication already exists")
        _append_jsonl(self.config.output_path, receipt)

    def submit(self, submission: ReviewSubmission, *, review_token: str) -> dict[str, Any]:
        with self.lock:
            active = self._ensure_active()
            if active is None:
                raise ReviewCockpitError("this review batch is already complete")
            if submission.mode != self.config.mode:
                raise ReviewCockpitError("review mode changed during submission")
            if not secrets.compare_digest(submission.item_token, active.token):
                raise ReviewCockpitError("review item token is stale")
            packet = self.packets[active.case_id]
            if self.config.mode == "blinded_adjudication":
                self._submit_adjudication(submission, packet, active)
            else:
                self._submit_review(submission, packet, active)
            self.case_ids.pop(0)
            self.completed_this_run += 1
            self.active = None
        return self.state(review_token=review_token)


class ReviewCockpit:
    def __init__(self, configs: dict[ReviewMode, ModeConfig]) -> None:
        self.review_token = secrets.token_urlsafe(40)
        self.queues = {mode: ReviewQueue(config) for mode, config in configs.items()}

    def state(self, mode: ReviewMode) -> dict[str, Any]:
        if mode not in self.queues:
            raise ReviewCockpitError(f"review mode is not enabled: {mode}")
        return self.queues[mode].state(review_token=self.review_token)

    def submit(self, submission: ReviewSubmission) -> dict[str, Any]:
        if submission.mode not in self.queues:
            raise ReviewCockpitError(f"review mode is not enabled: {submission.mode}")
        return self.queues[submission.mode].submit(
            submission,
            review_token=self.review_token,
        )


def _allowed_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    parsed = urlparse(origin)
    expected = request.url
    return (
        parsed.scheme == expected.scheme
        and parsed.hostname == expected.hostname
        and parsed.port == expected.port
    )


def create_review_cockpit_app(cockpit: ReviewCockpit) -> FastAPI:
    app = FastAPI(
        title="Delivery Clearance Human Review Cockpit",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )

    @app.middleware("http")
    async def response_boundaries(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        mode_buttons = "".join(
            (
                f'<button type="button" data-mode="{mode}" '
                f'aria-selected="{str(index == 0).lower()}">{MODE_LABELS[mode]}</button>'
            )
            for index, mode in enumerate(cockpit.queues)
        )
        initial_mode = next(iter(cockpit.queues))
        return REVIEW_COCKPIT_HTML.replace("<!-- REVIEW_MODE_BUTTONS -->", mode_buttons).replace(
            "__INITIAL_REVIEW_MODE__", json.dumps(initial_mode)
        )

    @app.get("/api/review/{mode}")
    def current(mode: ReviewMode) -> JSONResponse:
        try:
            return JSONResponse(cockpit.state(mode))
        except ReviewCockpitError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/review/submit")
    def submit(
        submission: ReviewSubmission,
        request: Request,
        x_review_token: str | None = Header(default=None),
    ) -> JSONResponse:
        if not _allowed_origin(request):
            raise HTTPException(status_code=403, detail="cross-origin review submission denied")
        if x_review_token is None or not secrets.compare_digest(
            x_review_token,
            cockpit.review_token,
        ):
            raise HTTPException(status_code=403, detail="review token is missing or invalid")
        try:
            return JSONResponse(cockpit.submit(submission))
        except ReviewCockpitError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


def build_app_from_protocol(
    *,
    repo_root: Path,
    protocol_path: Path,
    max_items: int,
) -> tuple[FastAPI, ReviewCockpit]:
    configs = load_canonical_mode_configs(
        repo_root,
        protocol_path,
        max_items=max_items,
    )
    cockpit = ReviewCockpit(configs)
    return create_review_cockpit_app(cockpit), cockpit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the local browser cockpit for canonical human review."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--protocol", default=DEFAULT_PROTOCOL_PATH.as_posix())
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    protocol_path = Path(args.protocol).expanduser()
    if not protocol_path.is_absolute():
        protocol_path = (repo_root / protocol_path).resolve()
    app, cockpit = build_app_from_protocol(
        repo_root=repo_root,
        protocol_path=protocol_path,
        max_items=args.max_items,
    )
    launch = {
        "schema_version": "delivery-clearance.review-cockpit-launch.v1",
        "status": "ready",
        "url": f"http://127.0.0.1:{args.port}",
        "maximum_scope": "personal_local",
        "raw_answers_included": False,
        "independent_reviewer_claimed": False,
        "modes": {
            mode: {
                "batch_total": queue.batch_total,
                "completed_before_run": queue.completed_before,
            }
            for mode, queue in cockpit.queues.items()
        },
    }
    assert_safe_metadata(launch, label="review cockpit launch receipt")
    print(json.dumps(launch, ensure_ascii=False, indent=2, sort_keys=True))
    if args.dry_run:
        return 0
    if not 1 <= args.port <= 65535:
        raise ReviewCockpitError("port must be between 1 and 65535")
    if not args.no_open:
        threading.Timer(0.8, webbrowser.open, args=(launch["url"],)).start()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
        access_log=False,
    )
    return 0


REVIEW_COCKPIT_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Delivery Clearance - Human Review Cockpit</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #17201b;
      background: #f5f7f5;
      --ink: #17201b;
      --muted: #607066;
      --line: #cfd8d1;
      --surface: #ffffff;
      --green: #1f6a43;
      --green-soft: #e8f2eb;
      --amber: #915e14;
      --amber-soft: #fff4db;
      --red: #9b3528;
      --red-soft: #fbeae7;
      --blue: #315f85;
    }
    * { box-sizing: border-box; }
    html, body { width: 100%; margin: 0; min-height: 100%; overflow-x: hidden; }
    body { background: #f5f7f5; }
    button, input { font: inherit; }
    button { cursor: pointer; }
    .topbar {
      min-height: 68px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 14px 24px;
      background: #17201b;
      color: #ffffff;
      border-bottom: 1px solid #2b3830;
    }
    .brand { display: flex; align-items: baseline; gap: 12px; min-width: 0; }
    .brand strong { font-size: 17px; }
    .brand span { color: #b9c7bd; font-size: 13px; }
    .scope { color: #d9e5dc; font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; }
    .modebar {
      display: flex;
      gap: 0;
      padding: 18px 24px 0;
      max-width: 1440px;
      margin: 0 auto;
      overflow-x: auto;
    }
    .modebar button {
      min-height: 38px;
      padding: 0 14px;
      color: var(--muted);
      background: transparent;
      border: 1px solid var(--line);
      border-right: 0;
      white-space: nowrap;
    }
    .modebar button:first-child { border-radius: 5px 0 0 5px; }
    .modebar button:last-child { border-right: 1px solid var(--line); border-radius: 0 5px 5px 0; }
    .modebar button[aria-selected="true"] { color: #ffffff; background: var(--green); border-color: var(--green); }
    .progress-wrap { max-width: 1440px; margin: 0 auto; padding: 14px 24px 0; }
    .progress-meta { display: flex; justify-content: space-between; gap: 16px; color: var(--muted); font-size: 13px; }
    .progress-track { height: 4px; margin-top: 8px; background: #dce3de; overflow: hidden; }
    .progress-fill { height: 100%; background: var(--green); transition: width 180ms ease; }
    .layout {
      max-width: 1440px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: minmax(280px, 0.78fr) minmax(480px, 1.7fr);
      gap: 28px;
      padding: 22px 24px 48px;
    }
    .context { border-right: 1px solid var(--line); padding-right: 28px; min-width: 0; }
    .workspace { min-width: 0; }
    h1 { font-size: 24px; line-height: 1.25; margin: 0; letter-spacing: 0; }
    h2 { font-size: 16px; margin: 0 0 12px; letter-spacing: 0; }
    h3 { font-size: 14px; margin: 22px 0 8px; letter-spacing: 0; }
    .eyebrow { color: var(--green); font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 6px; }
    .boundary-grid { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 7px 12px; font-size: 13px; }
    .boundary-grid dt { color: var(--muted); }
    .boundary-grid dd { margin: 0; overflow-wrap: anywhere; font-weight: 600; }
    .chip-list { display: flex; flex-wrap: wrap; gap: 6px; }
    .chip { padding: 4px 7px; border: 1px solid var(--line); border-radius: 4px; background: var(--surface); font-size: 12px; overflow-wrap: anywhere; }
    .evidence-table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 12px; }
    .evidence-table th, .evidence-table td { padding: 8px 6px; border-bottom: 1px solid var(--line); text-align: left; overflow-wrap: anywhere; vertical-align: top; }
    .evidence-table th { color: var(--muted); font-weight: 600; }
    .status-passed { color: var(--green); font-weight: 700; }
    .status-failed, .status-error, .status-timeout { color: var(--red); font-weight: 700; }
    .status-missing, .status-not_run { color: var(--amber); font-weight: 700; }
    .question { padding: 18px 0; border-bottom: 1px solid var(--line); }
    .question:first-of-type { border-top: 1px solid var(--line); }
    .question-title { margin: 0 0 10px; font-weight: 650; line-height: 1.45; }
    .option { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; align-items: start; padding: 8px 0; color: #26342b; }
    .option input { margin: 3px 0 0; accent-color: var(--green); }
    .full-material { margin: 0 0 22px; padding: 0; border-top: 1px solid var(--line); }
    .material-row { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 14px; padding: 9px 0; border-bottom: 1px solid var(--line); font-size: 13px; }
    .material-row span:first-child { color: var(--muted); }
    .material-row span:last-child { overflow-wrap: anywhere; }
    .decision-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--line); border-radius: 5px; overflow: hidden; }
    .decision-grid label { position: relative; border-right: 1px solid var(--line); }
    .decision-grid label:last-child { border-right: 0; }
    .decision-grid input { position: absolute; opacity: 0; }
    .decision-grid span { display: block; min-height: 42px; padding: 11px 8px; text-align: center; background: var(--surface); }
    .decision-grid input:checked + span { color: #ffffff; background: var(--green); }
    .field { margin-top: 20px; }
    .field label { display: block; margin-bottom: 7px; font-size: 13px; font-weight: 650; }
    .field input[type="text"] { width: 100%; min-height: 42px; padding: 9px 10px; border: 1px solid #9ca9a0; border-radius: 4px; background: var(--surface); }
    .range-row { display: grid; grid-template-columns: minmax(0, 1fr) 64px; gap: 12px; align-items: center; }
    .range-row input[type="range"] { width: 100%; accent-color: var(--green); }
    .range-value { text-align: right; font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; }
    .actionbar { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 24px; }
    .privacy { color: var(--muted); font-size: 12px; line-height: 1.45; }
    .primary { min-height: 42px; padding: 0 17px; border: 1px solid var(--green); border-radius: 5px; color: #ffffff; background: var(--green); font-weight: 700; white-space: nowrap; }
    .primary:hover { background: #185535; }
    .primary:disabled { cursor: not-allowed; opacity: 0.55; }
    .notice { margin: 0 0 18px; padding: 10px 12px; border-left: 3px solid var(--amber); background: var(--amber-soft); color: #62430f; font-size: 13px; }
    .error { display: none; margin: 0 0 18px; padding: 10px 12px; border-left: 3px solid var(--red); background: var(--red-soft); color: #72271d; font-size: 13px; }
    .complete { padding: 38px 0; border-top: 1px solid var(--line); }
    .complete p { color: var(--muted); max-width: 620px; }
    .loading { color: var(--muted); padding: 36px 0; }
    @media (max-width: 860px) {
      .topbar { align-items: flex-start; padding: 14px 16px; }
      .brand { display: grid; gap: 3px; }
      .modebar {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        padding-left: 16px;
        padding-right: 16px;
        overflow: visible;
      }
      .modebar button { min-width: 0; height: auto; padding: 8px 6px; line-height: 1.25; white-space: normal; }
      .progress-wrap { padding-left: 16px; padding-right: 16px; }
      .layout { grid-template-columns: minmax(0, 1fr); padding: 20px 16px 40px; }
      .context { border-right: 0; border-bottom: 1px solid var(--line); padding: 0 0 20px; }
      .decision-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .decision-grid label:nth-child(2) { border-right: 0; }
      .decision-grid label:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
      .actionbar { align-items: flex-start; flex-direction: column; }
      .primary { width: 100%; }
    }
    @media (max-width: 520px) {
      .scope { display: none; }
      h1, .question-title, .option { overflow-wrap: anywhere; }
      .evidence-table, .evidence-table tbody, .evidence-table tr, .evidence-table td { display: block; width: 100%; }
      .evidence-table thead { display: none; }
      .evidence-table tr { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 12px; padding: 9px 0; border-bottom: 1px solid var(--line); }
      .evidence-table td { padding: 0; border: 0; }
      .evidence-table td:nth-child(3) { grid-column: 1 / -1; color: var(--muted); }
      .material-row { grid-template-columns: minmax(0, 1fr); gap: 3px; }
      .boundary-grid { grid-template-columns: 96px minmax(0, 1fr); }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand"><strong>Delivery Clearance</strong><span>Human Review Cockpit</span></div>
    <div class="scope">personal_local / no independent-review claim</div>
  </header>
  <nav class="modebar" aria-label="Review mode">
    <!-- REVIEW_MODE_BUTTONS -->
  </nav>
  <div class="progress-wrap">
    <div class="progress-meta"><span id="progress-label">Loading review state</span><span id="active-time">00:00 active</span></div>
    <div class="progress-track" aria-hidden="true"><div class="progress-fill" id="progress-fill" style="width:0"></div></div>
  </div>
  <main class="layout">
    <aside class="context" id="context"><div class="loading">Loading boundary evidence...</div></aside>
    <section class="workspace">
      <div class="error" id="error" role="alert"></div>
      <div id="workspace"><div class="loading">Loading review item...</div></div>
    </section>
  </main>
  <script>
    const modes = [...document.querySelectorAll('[data-mode]')];
    const context = document.getElementById('context');
    const workspace = document.getElementById('workspace');
    const errorBox = document.getElementById('error');
    const progressLabel = document.getElementById('progress-label');
    const progressFill = document.getElementById('progress-fill');
    const activeTime = document.getElementById('active-time');
    let state = null;
    let mode = __INITIAL_REVIEW_MODE__;
    let activeMs = 0;
    let visibleSince = performance.now();
    let timer = null;
    const timingByToken = new Map();

    function esc(value) {
      return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    }
    function stopTimer() {
      if (document.visibilityState === 'visible' && visibleSince !== null) activeMs += performance.now() - visibleSince;
      if (state?.item_token) timingByToken.set(state.item_token, Math.round(activeMs));
      visibleSince = null;
      if (timer) clearInterval(timer);
      timer = null;
    }
    function startTimer() {
      activeMs = state?.item_token ? (timingByToken.get(state.item_token) || 0) : 0;
      visibleSince = document.visibilityState === 'visible' ? performance.now() : null;
      if (timer) clearInterval(timer);
      timer = setInterval(renderTime, 500);
      renderTime();
    }
    function currentActiveMs() {
      return Math.round(activeMs + (document.visibilityState === 'visible' && visibleSince !== null ? performance.now() - visibleSince : 0));
    }
    function renderTime() {
      const seconds = Math.floor(currentActiveMs() / 1000);
      activeTime.textContent = `${String(Math.floor(seconds / 60)).padStart(2,'0')}:${String(seconds % 60).padStart(2,'0')} active`;
    }
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden' && visibleSince !== null) {
        activeMs += performance.now() - visibleSince;
        visibleSince = null;
      } else if (document.visibilityState === 'visible' && visibleSince === null) {
        visibleSince = performance.now();
      }
    });
    function showError(message) {
      errorBox.textContent = message;
      errorBox.style.display = 'block';
    }
    function clearError() {
      errorBox.textContent = '';
      errorBox.style.display = 'none';
    }
    function chips(values) {
      return `<div class="chip-list">${(values || []).map(value => `<span class="chip">${esc(value)}</span>`).join('')}</div>`;
    }
    function evidenceTable(items) {
      return `<table class="evidence-table"><thead><tr><th>Evidence</th><th>Status</th><th>Summary</th></tr></thead><tbody>${(items || []).map(item => `<tr><td>${esc(item.evidence_type)}</td><td class="status-${esc(item.status)}">${esc(item.status)}</td><td>${esc(item.summary_code)}</td></tr>`).join('')}</tbody></table>`;
    }
    function renderContext() {
      const c = state.candidate;
      context.innerHTML = `<div class="eyebrow">${esc(state.display_label)}</div><h2>Delivery boundary</h2><dl class="boundary-grid"><dt>Task</dt><dd>${esc(c.task_summary_code)}</dd><dt>Risk</dt><dd>${esc(c.declared_risk_level)}</dd><dt>Scope</dt><dd>${esc(c.target_scope)}</dd><dt>Recipient</dt><dd>${esc(c.intended_recipient_role)}</dd><dt>Risk owner</dt><dd>${esc(c.risk_owner_role)}</dd></dl><h3>Prohibited use</h3>${chips(c.prohibited_use_codes)}<h3>Visible evidence</h3>${evidenceTable(c.visible_evidence)}`;
    }
    function questionMarkup(question, index) {
      const name = `q-${index}`;
      const options = question.options.map((label, optionIndex) => `<label class="option"><input type="radio" name="${name}" value="${optionIndex + 1}"><span>${esc(label)}</span></label>`).join('');
      return `<div class="question"><p class="question-title">${index + 1}. ${esc(question.prompt)}</p>${options}<label class="option"><input type="radio" name="${name}" value="u"><span>Unresolved / needs more evidence</span></label></div>`;
    }
    function materialMarkup(material) {
      const omit = new Set(['visible_evidence', 'schema_version']);
      return `<div class="full-material">${Object.entries(material).filter(([key]) => !omit.has(key)).map(([key, value]) => `<div class="material-row"><span>${esc(key)}</span><span>${esc(Array.isArray(value) ? value.join(', ') : value)}</span></div>`).join('')}</div>`;
    }
    function workloadMarkup() {
      return `<div class="field"><label for="workload">Mental workload (optional)</label><div class="range-row"><input id="workload" type="range" min="0" max="100" step="1" value="50"><span class="range-value" id="workload-value">not set</span></div></div>`;
    }
    function bindWorkload() {
      const input = document.getElementById('workload');
      const output = document.getElementById('workload-value');
      if (!input || !output) return;
      let touched = false;
      input.addEventListener('input', () => { touched = true; output.textContent = input.value; input.dataset.touched = 'true'; });
      input.addEventListener('change', () => { touched = true; output.textContent = input.value; input.dataset.touched = 'true'; });
      if (!touched) output.textContent = 'not set';
    }
    function renderReview() {
      const full = state.mode === 'full_review_reference' ? `<div class="notice">Arm decisions, reference labels, and hidden scorer material remain unavailable.</div><h2>Full metadata review</h2>${materialMarkup(state.full_review_material)}<h2>Boundary questions</h2>` : `<h1>Reconstruct the delivery boundary</h1>`;
      workspace.innerHTML = `${full}${state.questions.map(questionMarkup).join('')}${workloadMarkup()}<div class="actionbar"><span class="privacy">Only aggregate correctness, unresolved count, active time, and optional workload are stored.</span><button class="primary" id="submit">Record review</button></div>`;
      bindWorkload();
      document.getElementById('submit').addEventListener('click', submitReview);
    }
    function renderAdjudication() {
      const scorer = state.official_scorer;
      workspace.innerHTML = `<h1>Make the blinded clearance decision</h1><div class="notice">Official scorer: ${esc(scorer.outcome)}. Scorer evidence is supporting, not sufficient. Experimental arm identities and decisions remain hidden.</div><div class="decision-grid">${state.dispositions.map(item => `<label><input type="radio" name="disposition" value="${esc(item.value)}"><span>${esc(item.label)}</span></label>`).join('')}</div><div class="field"><label for="rationale">Rationale codes</label><input id="rationale" type="text" autocomplete="off" placeholder="scorer-passed, scope-bounded"></div><div class="actionbar"><span class="privacy">Free-form notes are not retained. Use bounded lowercase identifiers.</span><button class="primary" id="submit">Record decision</button></div>`;
      document.getElementById('submit').addEventListener('click', submitAdjudication);
    }
    function renderComplete() {
      stopTimer();
      context.innerHTML = `<div class="eyebrow">Batch complete</div><h2>${esc(state.mode_label)}</h2><dl class="boundary-grid"><dt>Recorded now</dt><dd>${state.completed_this_run}</dd><dt>Existing</dt><dd>${state.completed_before_run}</dd><dt>Scope</dt><dd>${esc(state.maximum_scope)}</dd></dl>`;
      workspace.innerHTML = `<div class="complete"><h1>Review batch complete</h1><p>The append-only receipts were written locally. No raw answers, screenshots, keystrokes, biometric data, or model-generated responses were stored.</p></div>`;
    }
    function render() {
      clearError();
      modes.forEach(button => button.setAttribute('aria-selected', String(button.dataset.mode === mode)));
      const done = state.completed_this_run;
      const total = state.batch_total;
      progressLabel.textContent = `${state.mode_label} / ${done} of ${total} recorded this run`;
      progressFill.style.width = `${total ? Math.round((done / total) * 100) : 100}%`;
      if (state.status === 'complete') { renderComplete(); return; }
      renderContext();
      startTimer();
      if (state.mode === 'blinded_adjudication') renderAdjudication(); else renderReview();
    }
    async function load(nextMode) {
      stopTimer();
      mode = nextMode;
      context.innerHTML = '<div class="loading">Loading boundary evidence...</div>';
      workspace.innerHTML = '<div class="loading">Loading review item...</div>';
      try {
        const response = await fetch(`/api/review/${mode}`, {cache: 'no-store'});
        if (!response.ok) throw new Error(`Review state failed (${response.status})`);
        state = await response.json();
        render();
      } catch (error) { showError(error.message); }
    }
    function reviewAnswers() {
      return state.questions.map((_, index) => document.querySelector(`input[name="q-${index}"]:checked`)?.value || null);
    }
    async function post(payload) {
      clearError();
      const button = document.getElementById('submit');
      button.disabled = true;
      stopTimer();
      try {
        const response = await fetch('/api/review/submit', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-Review-Token': state.review_token},
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `Submission failed (${response.status})`);
        timingByToken.delete(payload.item_token);
        state = data;
        render();
      } catch (error) {
        showError(error.message);
        button.disabled = false;
        startTimer();
      }
    }
    function workloadValue() {
      const input = document.getElementById('workload');
      return input?.dataset.touched === 'true' ? Number(input.value) : null;
    }
    async function submitReview() {
      const answers = reviewAnswers();
      if (answers.some(answer => answer === null)) { showError('Answer every boundary question or mark it unresolved.'); return; }
      await post({mode, item_token: state.item_token, answers, active_review_ms: currentActiveMs(), nasa_tlx_score: workloadValue()});
    }
    async function submitAdjudication() {
      const disposition = document.querySelector('input[name="disposition"]:checked')?.value;
      const rationaleCodes = document.getElementById('rationale').value.split(',').map(value => value.trim()).filter(Boolean);
      if (!disposition) { showError('Choose a clearance disposition.'); return; }
      if (!rationaleCodes.length) { showError('Provide at least one bounded rationale code.'); return; }
      await post({mode, item_token: state.item_token, disposition, rationale_codes: rationaleCodes});
    }
    modes.forEach(button => button.addEventListener('click', () => load(button.dataset.mode)));
    load(mode);
  </script>
</body>
</html>"""


if __name__ == "__main__":
    raise SystemExit(main())
