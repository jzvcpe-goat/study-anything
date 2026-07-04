# Real-Adopter Scenario Import

Real-Adopter Scenario Import turns one bounded WorkBuddy, Kimi, Codex, Hermes,
or generic HTTP-tools adoption issue summary into Product Loop evidence.

It is a metadata-only bridge. It does not store raw issue text, requester
identity, screenshots, platform logs, Agent traces, model keys, customer-visible
replies, external publication, or production mutations.

## What It Proves

- A real-adopter issue summary can enter the External Feedback Receipt path.
- Accepted feedback can create Product Loop backlog evidence.
- Product Owner reconstruction is required before a spec/eval candidate exists.
- Spec/Eval authoring reconstruction is required before a brief exists.
- Product Loop Brief Intake is required before the issue can become a Product
  Loop Harness candidate.
- Raw issue text, requester identity, AI-review-only evidence, and production
  mutation requests are blocked.

## Default Fixture

The default deterministic fixture represents a redacted WorkBuddy field report:

- deterministic mode quality was too low;
- the real platform Agent was not proven to have been invoked;
- repository/runtime version drift appeared;
- a proxy environment workaround was still required.

Only bounded tags, severity, platform id, hashes, and reconstruction checkpoints
are stored.

## Artifacts

- `real-adopter-issue-summary-v1`: bounded source summary.
- `real-adopter-scenario-import-v1`: verification report.
- `fixtures/real-adopter-scenario-import/pass/*`: deterministic pass chain.
- `platform/generated/study-anything-real-adopter-scenario-import.json`:
  machine-readable report.
- `platform/generated/study-anything-real-adopter-scenario-import.md`:
  operator summary.
- `platform/generated/study-anything-real-adopter-scenario-import.html`:
  static artifact-console style report.

## Run

```bash
python3 scripts/verify_real_adopter_scenario_import.py --check
```

To refresh deterministic fixtures and generated reports:

```bash
python3 scripts/verify_real_adopter_scenario_import.py --write
```

To import a custom metadata-only summary:

```bash
python3 scripts/real_adopter_scenario_import.py \
  --summary fixtures/real-adopter-scenario-import/pass/real-adopter-issue-summary.json \
  --output-dir .cognitive-loop/artifacts/real-adopter-import
```

## Claim Boundary

This harness only claims that bounded real-adopter feedback can be converted into
metadata-only Product Loop evidence and a concrete spec/eval brief candidate. It
does not claim the issue is globally representative, does not assign priority,
does not implement the fix, does not answer the adopter, and does not approve
customer delivery.
