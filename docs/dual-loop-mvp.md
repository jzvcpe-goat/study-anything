# Dual-Loop MVP / 双闭环 MVP

Study Anything / Cognitive Black Box now has a local-first Dual-Loop MVP. It
combines two equal-weight environments:

- **Controlled Failure Environment**: AI work may fail only inside an
  observable, reversible sandbox.
- **Human Attention Reconstruction Environment**: human control is measured by
  reconstructing key failure boundaries, not by clicking through every AI step.

The two environments are physically isolated in v0.1. They communicate only
through metadata-only JSON artifacts. There are no model calls, no daemon, no
hosted service, no production mutation, and no raw user data capture.

## What Shipped

Implemented artifacts:

```text
failure-contract-v1
sandbox-receipt-v1
attention-reconstruction-trace-v1
attention-reconstruction-summary-v1
dual-loop-gate-receipt-v1
```

Implemented CLIs:

```bash
python3 scripts/failure_sandbox_lite.py demo --html
python3 scripts/attention_reconstruction_lite.py demo --html
python3 scripts/dual_loop_gate.py evaluate \
  --failure-contract .cognitive-loop/artifacts/dual-loop/failure-sandbox-lite/failure-contract.json \
  --sandbox-receipt .cognitive-loop/artifacts/dual-loop/failure-sandbox-lite/sandbox-receipt.json \
  --attention-summary .cognitive-loop/artifacts/dual-loop/attention-reconstruction-lite/attention-reconstruction-summary.json
```

Required verifier commands:

```bash
python3 scripts/verify_dual_loop_contracts.py --check
python3 scripts/verify_failure_sandbox_lite.py --check
python3 scripts/verify_attention_reconstruction_lite.py --check
python3 scripts/verify_dual_loop_gate.py --check
```

The verifiers emit metadata-only reports under `platform/generated/` and pass/fail
fixtures under `fixtures/dual-loop/`.

## Boundary Model

### Controlled Failure Environment

The failure sandbox receives only task metadata, artifact refs, risk budget, and
rollback requirements. It emits:

- `failure-contract-v1`: allowed failure modes, forbidden propagation paths,
  risk budget, rollback requirement, and required Minimum Reconstructable Units.
- `sandbox-receipt-v1`: deterministic sandbox result, contained failures,
  mutation summary, rollback rehearsal, and risk-budget status.

The sandbox cannot:

- mutate production;
- expose real users;
- perform irreversible external effects;
- call models;
- store raw source text, raw report text, secrets, cookies, signed URLs, or
  user-owned Agent credentials.

### Human Attention Reconstruction Environment

The attention layer receives only the structured failure contract and records
metadata-only reconstruction checkpoints. It emits:

- `attention-reconstruction-trace-v1`: weak passive attention metadata plus
  strong active reconstruction checkpoints.
- `attention-reconstruction-summary-v1`: whether required MRUs passed, missing
  MRUs, focus queue refs, and autonomy expansion recommendation.

Passive attention is weak evidence. Active reconstruction checkpoints are strong
evidence. The attention layer does not collect screenshots, keystrokes, mouse
coordinates, eye tracking, biometrics, or raw report/source text.

### Structured Artifact Bridge

The bridge between both sides is JSON only:

```text
failure-contract-v1 + sandbox-receipt-v1
        ↓
dual-loop-gate-receipt-v1
        ↑
attention-reconstruction-summary-v1
```

AI never receives fine-grained real-time attention streams. The human cognition
layer never receives production execution authority.

## Dual-Loop Propagation Gate

The gate reads both sides and emits `dual-loop-gate-receipt-v1`.

It allows promotion only when:

- sandbox status is passed;
- sandbox failures are contained;
- sandbox risk is within budget;
- human reconstruction summary is present and passed;
- physical isolation and structured-artifact bridge constraints are intact;
- both loops are evaluated with equal weight.

It blocks when:

- sandbox passes but human reconstruction is missing;
- human reconstruction passes but sandbox risk is outside budget;
- either side tries to weaken privacy, isolation, or rollback boundaries.

## Delivery Trust Layer

The next layer consumes the Dual-Loop gate and emits `delivery-trust-receipt-v1`.
This receipt answers a narrower customer-handoff question: may the candidate AI
delivery be handed to a customer inside the current controlled scope?

```bash
python3 scripts/verify_delivery_trust_receipt.py --check
```

The delivery receipt keeps the same metadata-only boundary. It allows controlled
handoff only when the Dual-Loop gate is allowed, human reconstruction is present,
sandbox risk is inside budget, AI eval receipts are supporting evidence only,
and the claim boundary states what is not proven.

## Customer Handoff Package Layer

The portable package layer consumes an allowed `delivery-trust-receipt-v1` and
emits `customer-handoff-package-v1` JSON/HTML/ZIP artifacts.

```bash
python3 scripts/verify_customer_handoff_package.py --check
```

This layer is not a new trust source. It cannot approve blocked delivery trust,
expand the scoped customer delivery boundary, rely on eval receipts as
sufficient proof, omit high-risk rollback, omit claim boundaries, ship digest
drift, or ask WorkBuddy/Hermes/Codex agents for production mutation.

## Deterministic Fixtures

Verifier-managed fixtures live under:

```text
fixtures/dual-loop/pass/
fixtures/dual-loop/blocked-missing-attention/
fixtures/dual-loop/blocked-risk-budget/
fixtures/customer-handoff/pass/
fixtures/customer-handoff/block-missing-delivery-trust/
fixtures/customer-handoff/block-scope-expansion/
fixtures/customer-handoff/block-missing-claim-boundary/
fixtures/customer-handoff/block-secret-like-content/
```

These fixtures prove the two required blocking paths:

- `blocked-missing-attention`: the sandbox passes, but the human reconstruction
  summary is absent.
- `blocked-risk-budget`: human reconstruction passes, but sandbox risk is
  outside budget.

## Privacy Contract

Every Dual-Loop artifact and report must stay metadata-only. The verifier rejects
private-looking fields or values for:

- raw source text;
- raw report text;
- screenshots;
- keystrokes;
- mouse coordinates;
- eye tracking;
- biometrics;
- real secrets;
- cookies;
- bearer tokens;
- signed URLs;
- user-owned Agent credentials;
- model API keys or model calls.

## v0.1 Non-Goals

This is not a runtime daemon, hosted service, browser monitor, real model
executor, production deployment system, or surveillance layer. It is a
deterministic local artifact harness that makes the two loops auditable before
any future autonomy expansion.
