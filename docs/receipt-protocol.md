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

The v0.1 kernel is deterministic and local. It does not call models, browse,
start daemons, send customer messages, or mutate production systems.
