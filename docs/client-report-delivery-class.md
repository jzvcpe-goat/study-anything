# Client Report Delivery Class Handoff

This slice maps the Delivery Trust Case Pack into a second concrete delivery
class: a metadata-only client report handoff. It answers a narrow question:
when may an AI-assisted report, memo, or analysis artifact be treated as
controlled customer handoff evidence?

It does not send customer messages, publish externally, certify legal or
financial advice, guarantee complete factual correctness, replace
customer-specific compliance review, or approve production mutation.

## Artifacts

- `client-report-handoff-case-v1`: one metadata-only handoff case.
- `client-report-delivery-class-verification-v1`: verifier report for pass and
  blocked fixtures.
- `fixtures/client-report-delivery-class/*/client-report-handoff-case.json`:
  deterministic pass and blocked examples.
- `platform/generated/study-anything-client-report-delivery-class.json`:
  generated machine-readable report.
- `platform/generated/study-anything-client-report-delivery-class.html`: static
  HTML report for human inspection.

## Gate Logic

The pass fixture is allowed only when all required loops pass:

- Product Loop evidence exists.
- Dual Loop gate is allowed.
- Delivery Trust Case is allowed.
- Customer handoff package is ready.
- Human reconstruction checkpoint passed.
- Sandbox risk remains within budget.
- Source-grounding citations are present.
- Recipient scope is bounded.
- Claim boundary is present.
- Rollback or correction plan is present.

The blocked fixtures prove the non-negotiable boundaries:

- Missing human reconstruction blocks handoff, even if the sandbox side is
  otherwise healthy.
- Sandbox risk outside budget blocks handoff, even if human reconstruction is
  present.
- Unbounded recipient scope blocks handoff, even if the report artifact exists.
- AI-summary-only evidence blocks handoff; external eval receipts are supporting
  evidence only and cannot replace Product Loop or Dual Loop evidence.

## Privacy Boundary

The client-report delivery class is metadata-only. It must not include raw
report text, raw customer payload, raw source text, screenshots, keystrokes,
mouse coordinates, eye tracking, biometrics, cookies, bearer tokens, signed
URLs, real secrets, or user-owned Agent credentials.

The CLI and verifier do not call models, start daemons, mutate production,
send customer messages, publish reports, or upload customer files.

## Commands

Generate deterministic local artifacts:

```bash
python3 scripts/client_report_delivery_class_handoff.py --case all
```

Refresh fixtures and generated reports:

```bash
python3 scripts/verify_client_report_delivery_class_handoff.py --write
```

Verify the delivery class:

```bash
python3 scripts/verify_client_report_delivery_class_handoff.py --check
```

The verifier also runs negative checks that reject raw report text, raw customer
payloads, automatic customer sending, external publication, and treating
external eval receipts as sufficient by themselves.
