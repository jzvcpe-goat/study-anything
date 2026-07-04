# External Feedback Receipt

External Feedback Receipt closes the third product-development loop: feedback
from an adopter, customer, support requester, or external operator can re-enter
the Product Loop only as bounded metadata.

It is not a customer-message store, support desk, analytics warehouse, model
evaluation shortcut, or automatic reply system.

## What It Proves

- The feedback source is bounded to a known delivery class.
- A human operator actively reconstructed the feedback boundary.
- Raw customer content and requester identity were not stored.
- AI-review-only feedback is rejected.
- Production mutation, customer-visible replies, external publication, and
  model-retraining payloads remain blocked.
- The only accepted next boundary is product-loop backlog evidence.

## Artifacts

- `external-feedback-receipt-v1`: one metadata-only feedback receipt.
- `external-feedback-receipt-verification-v1`: verifier report for pass/block
  cases and privacy-injection checks.
- `fixtures/external-feedback-receipt/*/external-feedback-receipt.json`:
  deterministic pass/block fixtures.
- `platform/generated/study-anything-external-feedback-receipt.json`:
  machine-readable verification report.
- `platform/generated/study-anything-external-feedback-receipt.md`:
  operator-readable summary.
- `platform/generated/study-anything-external-feedback-receipt.html`:
  static HTML report for artifact-console style review.

## Cases

- `pass`: bounded support-response feedback can enter product-loop backlog.
- `blocked-raw-feedback`: raw payload attachment is detected and blocked.
- `blocked-identity`: unbounded requester identity scope is blocked.
- `blocked-production-mutation`: feedback cannot request direct production
  mutation.
- `blocked-ai-review-only`: passive or AI-only review cannot replace active
  human triage.

## Privacy Boundary

External Feedback Receipt is metadata-only. It must not include raw feedback
text, raw customer messages, raw ticket payloads, requester identity, customer
identity, screenshots, keystrokes, mouse coordinates, eye tracking, biometrics,
cookies, bearer tokens, signed URLs, Agent endpoint secrets, model API keys, or
production payloads.

The verifier injects those fields into a passing fixture and proves they are
rejected.

## Run

```bash
python3 scripts/verify_external_feedback_receipt.py --check
```

To refresh deterministic fixtures and generated reports:

```bash
python3 scripts/verify_external_feedback_receipt.py --write
```

## Claim Boundary

This artifact only claims that external feedback can safely re-enter the Product
Loop as bounded metadata. It does not claim customer satisfaction, truth
certification, automatic customer response, automatic production change, or
replacement for product-owner prioritization.
