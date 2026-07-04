# Product Owner Prioritization Gate

Product Owner Prioritization Gate is the next boundary after External Feedback
Backlog Bridge. It consumes a metadata-only `product-loop-backlog-item-v1` and
emits a `product-owner-prioritization-receipt-v1`.

It can create a `product-spec-eval-candidate-v1`, but only as metadata in the
spec/eval candidate queue. It does not assign priority, execute work, send
customer-visible messages, publish externally, mutate production, or skip to the
Delivery Trust Harness.

## What It Proves

- A backlog item requires active Product Owner boundary reconstruction.
- Blocked backlog sources cannot enter the spec/eval candidate queue.
- Automatic priority assignment is blocked.
- Automatic execution is blocked.
- Customer-visible action, external publication, and production mutation are
  blocked.
- The only allowed next boundary is `product_spec_eval_candidate_queue`.
- A queued candidate remains `priority_state: unassigned`.

## Artifacts

- `product-owner-prioritization-receipt-v1`: allow/block gate receipt.
- `product-spec-eval-candidate-v1`: metadata-only candidate created only for the
  pass case.
- `product-owner-prioritization-gate-verification-v1`: verifier report for
  pass/block cases and privacy-injection checks.
- `fixtures/product-owner-prioritization-gate/*/product-owner-prioritization-receipt.json`:
  deterministic gate fixtures.
- `fixtures/product-owner-prioritization-gate/pass/product-spec-eval-candidate.json`:
  the only deterministic candidate fixture.
- `platform/generated/study-anything-product-owner-prioritization-gate.json`:
  machine-readable verification report.
- `platform/generated/study-anything-product-owner-prioritization-gate.md`:
  operator-readable summary.
- `platform/generated/study-anything-product-owner-prioritization-gate.html`:
  static HTML report for artifact-console style review.

## Cases

- `pass`: valid backlog item plus active Product Owner reconstruction creates
  one spec/eval candidate.
- `blocked-missing-owner-reconstruction`: no active owner reconstruction.
- `blocked-automatic-priority`: automatic priority assignment was requested.
- `blocked-skip-to-delivery-harness`: requester tried to skip directly to
  Delivery Trust Harness.
- `blocked-automatic-execution`: requester tried to execute work immediately.
- `blocked-production-mutation`: requester tried to mutate production.
- `blocked-customer-visible-action`: requester tried to send or expose a
  customer-visible action.
- `blocked-blocked-backlog-source`: blocked External Feedback bridge output has
  no backlog item and cannot enter prioritization.

## Run

```bash
python3 scripts/verify_product_owner_prioritization_gate.py --check
```

To refresh deterministic fixtures and generated reports:

```bash
python3 scripts/verify_product_owner_prioritization_gate.py --write
```

To gate one local backlog item:

```bash
python3 scripts/product_owner_prioritization_gate.py \
  --backlog-item fixtures/external-feedback-backlog-bridge/pass/product-loop-backlog-item.json \
  --output-dir .cognitive-loop/artifacts/product-owner-prioritization
```

## Claim Boundary

This gate only claims that metadata-only backlog evidence can become a
metadata-only spec/eval candidate after active Product Owner boundary
reconstruction. It does not claim priority assignment, automatic execution,
customer-visible delivery, production readiness, external publication, or
Delivery Trust Harness readiness.
