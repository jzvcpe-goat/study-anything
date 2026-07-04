# External Feedback Backlog Bridge

External Feedback Backlog Bridge is the next boundary after External Feedback
Receipt. It turns an accepted `external-feedback-receipt-v1` into one
metadata-only `product-loop-backlog-item-v1`.

It does not import raw feedback, requester identity, ticket bodies, screenshots,
model credentials, customer-visible replies, production payloads, or external
publication content.

## What It Proves

- Only `accepted_for_product_loop` feedback receipts can create backlog items.
- Blocked feedback receipts cannot enter the product backlog.
- The only destination is `product_loop_backlog`.
- The next boundary is `product_owner_prioritization`.
- Backlog items do not skip into the Delivery Trust Harness.
- No customer-visible reply, production mutation, model call, hosted service, or
  external publication is performed.

## Artifacts

- `external-feedback-backlog-bridge-v1`: bridge decision for accepted or blocked
  feedback receipts.
- `product-loop-backlog-item-v1`: metadata-only backlog item created only for
  accepted feedback.
- `external-feedback-backlog-bridge-verification-v1`: verifier report for
  pass/block cases and privacy-injection checks.
- `fixtures/external-feedback-backlog-bridge/*/external-feedback-backlog-bridge.json`:
  deterministic bridge fixtures.
- `fixtures/external-feedback-backlog-bridge/pass/product-loop-backlog-item.json`:
  the only deterministic backlog item fixture.
- `platform/generated/study-anything-external-feedback-backlog-bridge.json`:
  machine-readable verification report.
- `platform/generated/study-anything-external-feedback-backlog-bridge.md`:
  operator-readable summary.
- `platform/generated/study-anything-external-feedback-backlog-bridge.html`:
  static HTML report for artifact-console style review.

## Cases

- `pass`: accepted support-response feedback creates one Product Loop backlog
  item.
- `blocked-raw-feedback`: blocked receipt cannot create a backlog item.
- `blocked-identity`: unbounded requester identity cannot create a backlog item.
- `blocked-production-mutation`: feedback requesting production mutation cannot
  create a backlog item.
- `blocked-ai-review-only`: passive or AI-only review cannot create a backlog
  item.

## Run

```bash
python3 scripts/verify_external_feedback_backlog_bridge.py --check
```

To refresh deterministic fixtures and generated reports:

```bash
python3 scripts/verify_external_feedback_backlog_bridge.py --write
```

To bridge one local receipt file:

```bash
python3 scripts/external_feedback_backlog_bridge.py \
  --receipt fixtures/external-feedback-receipt/pass/external-feedback-receipt.json \
  --output-dir .cognitive-loop/artifacts/external-feedback-backlog
```

## Claim Boundary

This bridge only claims that accepted feedback can become metadata-only backlog
evidence. It does not claim automatic prioritization, customer satisfaction,
truth certification, customer-visible replies, production changes, or readiness
for customer handoff.
