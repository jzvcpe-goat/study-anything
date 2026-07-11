# CBB Protocol v1 Scenarios And Qualification

## Purpose

AI Delivery Clearance Protocol is the final open protocol before an AI delivery crosses a real-world
responsibility boundary. This layer determines which human reconstruction, actor,
safeguard, and model evidence a specific delivery scenario requires. It keeps the
human decision surface focused on unresolved boundaries instead of requiring a full
second reading of every generated artifact.

This work extends the existing six canonical Protocol v1 objects. It does not add a
new trust receipt family or let scenario classification authorize delivery by itself.

## Nested Policy Contracts

`cbb.trust-policy.v1` now carries nested, strict contracts for:

- delivery scenario and maximum propagation scope;
- recipient and prohibition on automatic execution authority;
- risk owner and accepted scope ceiling;
- affected parties and impact classes;
- disclosure, appeal, redress, and human fallback requirements;
- model capability evidence and known failure modes;
- Minimum Reconstructable Units required for the target scope.

The deterministic kernel rejects a policy that exceeds the scenario, model, risk
owner, claim, or MRU scope ceiling. Required safeguards and risk-owner acceptance
must also appear as blocking evidence requirements.

## Minimum Reconstructable Unit

An MRU is the smallest control boundary a human must actively reconstruct. It is not
a comprehension score and cannot be satisfied by passive attention alone. The
reference scenarios use these boundary types:

1. intent and non-goals;
2. critical failure path;
3. affected parties and recipient;
4. rollback trigger;
5. evidence weakness and limitations;
6. residual risk.

MRU evidence is bound to a project, scenario, reviewer, boundary type, scope, and
time window. Missing or stale MRUs produce `needs_evidence`; a failed blocking MRU
produces `block`.

## Capability Profiles

Human and model capability profiles are scoped evidence, not permanent labels.

- A human profile is project-, scenario-, role-, boundary-, scope-, and time-bound.
- Counter-evidence prevents an active human profile from authorizing the gate.
- A model profile is scenario- and task-bound, expires, records failure modes, and
  cannot treat vendor claims as sufficient evidence.
- Any recipient, model, affected-party, impact, or policy change changes canonical
  digests and forces deterministic reevaluation.

The reference harness does not certify professional credentials or create a global
ranking of people or models.

## Vibe-Coding Scenario Ladder

| Fixture | Maximum candidate scope | Expected decision |
|---|---|---|
| `personal-local-prototype` | `personal_local` | allow |
| `public-fake-data-demo` | `public_demo` | allow |
| `limited-beta` | `limited_beta` | allow candidate handoff |
| `paid-customer-candidate` | `controlled_customer_handoff` | allow candidate handoff |
| `production-candidate-blocked` | `production_candidate` | needs evidence; approved scope remains blocked |
| `regulated-or-irreversible-blocked` | `blocked` | hard-deny block |

`allow` means only that the deterministic metadata fixture satisfies its declared
candidate scope. It does not perform customer delivery, expose a real user, mutate
production, certify a professional reviewer, or approve an irreversible action.

The production fixture deliberately omits domain review, security review, deployment
approval, and affected-party protection evidence. The regulated/irreversible fixture
remains blocked even when human reconstruction passes, proving that human confidence
cannot override a hard deny.

## Compatibility Boundary

The v0 Delivery Trust receipt lacks the actor, safeguard, MRU, and capability context
required for a v1 customer scope. A previously allowed v0 controlled-customer chain
therefore maps only to `internal_handoff`. Compatibility may preserve or narrow a
claim; it may never expand one.

## Verification

```bash
python3 scripts/generate_cbb_v1_scenario_assets.py --check
python3 scripts/verify_cbb_v1_scenarios.py --check
python3 scripts/verify_cbb_v1_qualification.py --check
python3 scripts/verify_cbb_v1_contracts.py --check
python3 scripts/verify_cbb_v0_compatibility.py --check
python3 scripts/verify_cbb_v1_kernel.py --check
```

Passing these checks proves only deterministic local contract behavior over public,
metadata-only fixtures. It does not prove real customer adoption, affected-party
consent, professional qualification, outcome safety, production readiness, or
independent security-audit completion.
