# Cognitive Black Box Protocol

Study Anything is moving toward a broader Cognitive Black Box protocol: a
local-first governance harness for AI delivery. The protocol does not try to
prove that a model is generally correct. It decides whether a specific AI
delivery candidate has enough structured evidence to move into the next
controlled handoff scope.

## Minimal Boundary

The v0.1 protocol is intentionally narrow.

- Metadata-only receipts are the only bridge between layers.
- The deterministic trust kernel does not call models.
- AI review is never sufficient by itself.
- Human control is active reconstruction of key boundaries, not full manual
  re-review of every output.
- Risk ownership and recipient scope must be explicit before handoff.
- Production mutation and irreversible external effects are forbidden.

The protocol may allow a controlled customer handoff. It does not claim
production readiness, legal certification, security certification, regulatory
approval, or general model correctness.

## Protocol Layers

1. Claim Boundary
   - States what the AI delivery candidate is allowed to claim.
   - States what is explicitly not claimed.
   - Points to structured evidence references.

2. Trust Root
   - Defines which evidence classes can support trust.
   - Forbids AI-review-only trust.
   - Requires the deterministic kernel to avoid model calls and production
     mutation.

3. Reviewer Reconstruction
   - Records whether a qualified reviewer actively reconstructed the claim and
     risk boundaries.
   - Passive attention is weak evidence and cannot pass by itself.

4. Risk Owner Scope
   - Identifies the operator-owned risk boundary and recipient context.
   - Blocks delivery when recipient risk is unknown.

5. Delivery Decision
   - Emits `delivery-decision-receipt-v1`.
   - Allows controlled handoff only when every protocol layer passes.

6. Receipt Chain
   - Emits `cbb-receipt-chain-v1`.
   - Binds the five protocol receipts to a deterministic digest.
   - Rejects receipt hash mismatch and stale source commit evidence.

7. Self-Intake
   - Emits `cbb-self-intake-receipt-v1` and
     `cbb-delivery-evidence-pack-v1`.
   - Uses PR metadata, required CI check metadata, reviewer reconstruction,
     risk-owner scope, and delivery decision receipts to intake a real
     repository delivery.
   - The first reference fixture self-intakes PR
     [#285](https://github.com/jzvcpe-goat/study-anything/pull/285) at merge
     commit `f88d2ddbe4142c59d0a0f98bb9c7930b824d0fd4`.

8. Delivery Scenario Harness
   - Emits `cbb-delivery-scenario-v1`,
     `cbb-external-feedback-intake-v1`, and `cbb-tri-loop-run-v1`.
   - Maps the protocol onto three equal-weight loops: Agentic Coding,
     Developer Feedback, and External Feedback.
   - Allows promotion to the next sandbox level only when the receipt chain is
     current, self-intake passes, developer reconstruction is present, external
     feedback is structured and attributed, and risk stays inside budget.
   - Blocks stale receipt chains, missing developer reconstruction, sandbox risk
     overflow, external scope expansion, and AI-review-only evidence.

## Reference Implementation Boundary

This repository is a deterministic reference implementation. It is useful for
building and testing the protocol shape, but it is not a production trust
service. Real deployment would need domain acceptance tests, security review,
legal review when required, deployment approval, and customer-specific rollback.

## Verifier Commands

```bash
python3 scripts/verify_cbb_protocol_contracts.py --check
python3 scripts/verify_cbb_gate.py --check
python3 scripts/verify_cbb_receipt_chain.py --check
python3 scripts/verify_cbb_self_intake.py --check
python3 scripts/verify_cbb_delivery_harness.py --check
./scripts/release_check.sh --cbb-protocol-only
```

`--cbb-protocol-only` is partial verification. It must not be described as a
full release validation.
