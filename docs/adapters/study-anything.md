# Study Anything Adapter

Study Anything is an adapter inside the Cognitive Black Box protocol. It is not
the protocol itself.

The adapter contributes learning and delivery evidence:

- source-bound learning sessions
- controlled failure receipts
- human attention reconstruction summaries
- Dual Loop gate receipts
- delivery trust receipts
- customer handoff packages

The CBB protocol consumes those receipts as structured evidence and decides
whether a candidate may move into the next controlled handoff scope.

## Adapter Boundary

Study Anything may produce or package evidence. It must not silently expand the
trust claim.

For example:

- `DeliveryTrustReceipt` decides whether controlled handoff can happen.
- `CustomerHandoffPackage` carries evidence, constraints, rollback, and
  reconstruction material.
- `delivery-decision-receipt-v1` records the protocol gate decision.

None of these artifacts alone prove production readiness.

## Platform Agents

Codex, Kimi, WorkBuddy, Hermes, or other platform Agents may call Study
Anything as a local tool or inline adapter. Model choice, browsing, external
tools, and platform credentials remain outside Study Anything.

Study Anything should receive structured task inputs and emit metadata-only
evidence. It should not store real model keys, user-owned Agent credentials, raw
customer data, or hidden reasoning traces.

## First Adapter Scenario

The first CBB adapter scenario is customer delivery readiness:

1. Study Anything emits Dual Loop and delivery trust evidence.
2. CBB receipts state the claim boundary, trust root, reviewer reconstruction,
   and risk owner scope.
3. The deterministic CBB gate emits `delivery-decision-receipt-v1`.
4. Controlled handoff is allowed only when every protocol layer passes.
