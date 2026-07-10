# Receipt Protocol

The Cognitive Black Box protocol uses receipts as structured evidence. A
receipt is not a log dump and not a hidden reasoning trace. It is a compact,
metadata-only contract that states what was checked, what failed, what passed,
and what is still outside scope.

## Required Receipts

### `claim-boundary-v1`

Defines the current claim, the allowed handoff scope, explicit non-claims, and
the evidence references used by the gate.

It must not contain raw source text, raw report text, screenshots, secrets,
model prompts, customer payloads, or production payloads.

### `trust-root-v1`

Defines which evidence classes may support the delivery decision. In v0.1 it
requires controlled failure evidence, human attention reconstruction, Dual Loop
gate evidence, claim boundary evidence, and risk owner scope evidence.

It must forbid AI-review-only trust.

### `reviewer-reconstruction-receipt-v1`

Records whether a qualified reviewer actively reconstructed the claim boundary
and risk owner scope. This is not a full manual re-review. It is a focused
boundary reconstruction receipt.

Passive attention is weak evidence and cannot pass alone.

### `risk-owner-scope-v1`

Records the operator-owned risk boundary, recipient reference, known recipient
risk, allowed delivery modes, and explicit production mutation blocks.

Unknown recipient risk blocks handoff.

### `delivery-decision-receipt-v1`

Records the deterministic gate decision. It may allow controlled customer
handoff or block delivery. It carries reasons, checks, evidence references, and
a claim boundary for the decision itself.

It must not become a new trust source. It only summarizes the gate result.

### `cbb-receipt-chain-v1`

Binds a protocol receipt set into a deterministic digest manifest. The chain
stores receipt IDs, schema versions, paths, hashes, source PR metadata, and the
chain digest. It does not store raw diffs, raw source text, customer data,
model prompts, browser records, or user Agent credentials.

The verifier rejects hash mismatches and stale source commits before any
self-intake receipt can be trusted.

### `cbb-self-intake-receipt-v1`

Records a metadata-only self-intake of a real repository delivery. For the
reference fixture, PR `#285` is checked against its merge commit, required CI
checks, reviewer reconstruction summary, risk-owner scope, and delivery
decision receipt.

Self-intake is blocked when reviewer reconstruction is missing, the source
commit is stale, the scope expands beyond the claim boundary, required CI
evidence is missing, or the evidence is AI-review-only.

### `cbb-delivery-evidence-pack-v1`

Packages the receipt chain and self-intake receipt into a portable evidence
set. The pack is a manifest of metadata-only artifacts and hashes; it is not a
raw archive of implementation text, prompts, screenshots, secrets, browser
records, or customer payloads.

### `cbb-delivery-scenario-v1`

Defines one controlled AI delivery scenario and its three required loops:
Agentic Coding, Developer Feedback, and External Feedback. The scenario carries
risk budget, allowed promotion scope, and candidate evidence references. It
does not contain raw implementation text, raw user feedback, prompts, customer
payloads, or production credentials.

### `cbb-external-feedback-intake-v1`

Reduces external feedback into metadata-only scope, severity, attribution, and
handling signals. It explicitly records that original external feedback text,
private platform context, user identity, and raw feedback payloads are not
included.

### `cbb-tri-loop-run-v1`

Records the deterministic tri-loop gate decision. It can promote the candidate
to the next sandbox level only when all three loops pass. It blocks when any
one loop fails; no loop may dominate the others.

## Privacy Boundary

Receipts must stay metadata-only.

Forbidden content includes raw source text, raw report text, screenshots,
keystrokes, mouse coordinates, eye tracking, biometrics, real secrets, cookies,
bearer tokens, signed URLs, user-owned Agent credentials, model prompts,
customer payloads, and production payloads.

## Claim Boundary

Every receipt that supports delivery must keep its claim boundary explicit:

- Current claim: the narrow thing this receipt proves.
- Not claimed: production readiness, legal certification, security
  certification, regulatory approval, model correctness, or customer outcome.
- Required before production: domain tests, operator approval, security and
  legal review when required, and customer-specific rollback.

## Deterministic Kernel

The current reference kernel is deterministic and local. It does not call models, browse,
start daemons, send customer messages, or mutate production systems.

## Verifier Commands

```bash
python3 scripts/verify_cbb_positioning.py --check
python3 scripts/verify_cbb_protocol_contracts.py --check
python3 scripts/verify_cbb_gate.py --check
python3 scripts/verify_cbb_receipt_chain.py --check
python3 scripts/verify_cbb_self_intake.py --check
python3 scripts/verify_cbb_delivery_harness.py --check
```

These commands prove the local reference contracts, positive fixtures, and
negative fixtures. They do not claim production customer trust or full release
validation.
