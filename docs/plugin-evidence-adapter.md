# Plugin Evidence Adapter v0.1

Plugin Evidence Adapter converts bounded observations about one plugin-assisted run into
machine-checkable supporting evidence for the Personal Local Clearance MVP.

It exists because plugin installation metadata is not delivery evidence. A valid manifest,
matching package digest, or successful install says what code is present. It does not prove
that the runtime is ready, inputs are bound, external effects are absent, a native UI works,
or a professional conclusion is sound.

## Scope

The adapter can produce only three decisions:

| Decision | Resulting scope | Meaning |
|---|---|---|
| `allow_personal_local` | `personal_local` | The supplied evidence can support one personal-local candidate. |
| `needs_evidence` | `blocked` | Required runtime, input, native, or domain evidence is missing or expired. |
| `block` | `blocked` | A hard boundary failed. |

It cannot authorize customer delivery, production use, future external actions, plugin
installation, or independent review. Its receipt is supporting evidence, not the final
Personal Clearance receipt.

## Contracts

`delivery-clearance.plugin-evidence.v1` records:

- plugin ID, version, package digest, and manifest digest;
- declared capability classes;
- runtime and dependency readiness;
- Git-bound, local-unbound, or mutable-external input evidence;
- project, network, credential, and external-effect observations;
- required check results as hashes, not raw output;
- native verification for interactive surfaces;
- domain profile and qualified reconstruction for professional judgment;
- observation and expiry times;
- metadata-only privacy boundaries.

`delivery-clearance.plugin-evidence-decision.v1` records the deterministic decision,
individual checks, missing evidence, hard-deny reasons, approved scope, and claim boundary.

## Capability Rules

| Capability | Evidence required for `personal_local` |
|---|---|
| `local_read` | Package and manifest digests, ready runtime, bound inputs, passing checks. |
| `local_write` | The resulting project mutation must be bound to a post-run subject digest. |
| `external_read` | Network use must be declared and every external input must have a digest and unexpired validity window. |
| `external_write` | Always blocked in v0.1. |
| `interactive_ui` | Native browser/document/spreadsheet verification must pass. |
| `professional_judgment` | Domain profile, domain evaluator, and qualified reconstruction must pass. |

Observed external mutation, credential use, undeclared network access, unbound project
mutation, runtime failure, timeout, failed required checks, failed native verification, or
failed domain evidence are hard blocks.

Manifest-only evidence, a runtime that was not run, missing dependencies, unbound local
inputs, expired external snapshots, missing native verification, and missing domain evidence
return `needs_evidence`.

## CLI

Evaluate one bundle without running the plugin:

```bash
.venv/bin/delivery-clearance-plugin-evidence \
  .delivery-clearance/plugin-evidence.json
```

Optionally write the decision receipt:

```bash
.venv/bin/delivery-clearance-plugin-evidence \
  .delivery-clearance/plugin-evidence.json \
  --output .delivery-clearance/plugin-evidence-decision.json
```

Exit codes:

- `0`: `allow_personal_local`
- `2`: invalid or unsafe input
- `3`: `needs_evidence`
- `4`: `block`

The CLI does not execute, install, update, or repair a plugin. It performs no model calls or
external actions.

## Personal Clearance Integration

Use the installed command as a required Personal Clearance check. Omit `--output` so the
check does not mutate the project during the audit:

```json
{
  "check_id": "plugin-evidence",
  "argv": [
    "delivery-clearance-plugin-evidence",
    ".delivery-clearance/plugin-evidence.json"
  ],
  "timeout_seconds": 60,
  "required": true
}
```

The Personal Clearance workflow then hashes the adapter output and binds the final receipt to
the current Git-visible project state, the other configured checks, active boundary
reconstruction, explicit responsibility acceptance, and its own validity window.

This composition still cannot observe arbitrary side effects outside the project. Plugins with
external writes or credentials remain ineligible. External-read and professional workflows
must provide their own bounded source and domain evidence rather than relying on the Git
snapshot.

## Verify

```bash
.venv/bin/python scripts/verify_plugin_evidence_adapter.py --check
.venv/bin/python -m pytest -q apps/api/tests/test_plugin_evidence_adapter.py
```

The deterministic fixture matrix is in `fixtures/plugin-evidence/`. It includes narrow passing
cases and explicit boundaries for manifest-only evidence, unbound inputs, native UI,
professional judgment, external writes, external mutation, credential use, runtime failure,
and input expiry.

## Claim Boundary

Plugin Evidence Adapter v0.1 does not prove plugin or AI correctness. It does not prove that
all operating-system, network, browser, or external-service side effects were observed. It
only determines whether the supplied metadata is sufficient to support one personal-local
candidate under the stated capability and evidence rules.
