# Protocol v1 Outcome Receipts And Trust Degradation

`cbb.delivery-outcome-receipt.v1` connects an already signed Delivery Clearance
decision to bounded evidence observed after handoff. The outcome receipt is also
locally Ed25519 signed so its degradation or revocation effect can be verified before
use. It exists so trust can move down when reality contradicts the pre-delivery case.

It does not certify customer success. A monitored outcome with no adverse signal
means only that the declared sample did not reduce the existing ceiling. Trust never increases scope
from elapsed time, repeated passes, or model confidence.

## Input Boundary

The deterministic outcome evaluator accepts:

- an offline-verifiable, locally signed `cbb.delivery-trust-receipt.v1` package;
- a bounded sampling window and selection reference;
- typed incident, complaint, near-miss, claim-violation, evidence-invalidation, and
  affected-party challenge events;
- rollback requirement, attempt, status, and evidence refs;
- the Trust Recipe ref whose future use may be narrowed, frozen, or revoked.

The source package is replayed through canonical digest, signature, historical
validity, supplied revocation-registry, and deterministic gate checks before outcome
evaluation. An unsigned, never-valid, revoked, tampered, or non-allow source package
fails closed. A source package that expired after the handoff may still anchor a later
outcome record; that historical reference never restores or extends its delivery
authority.

The resulting outcome envelope is separately signed and carries its own expiry,
replay nonce, local revocation handle, verifier identity, and local-self-asserted
signer limitation. Neither signature proves an external identity.

## Deterministic Actions

The evaluator emits one non-increasing action:

| Action | Result |
|---|---|
| `maintain_current_ceiling` | Keep the existing ceiling; do not increase trust |
| `narrow_scope` | Reduce future authority to `sandbox_only` and require replay |
| `freeze_recipe` | Block future delivery until replay and policy reconstruction |
| `revoke_clearance` | Block future delivery and add the source handle to the local revocation registry |

Precedence is fail closed:

- failed rollback, substantiated claim violation, invalidated evidence, or
  substantiated high/critical incident revokes the source clearance;
- partial or unattempted required rollback, an open affected-party challenge, or an
  unresolved serious adverse signal freezes the recipe;
- lower-severity complaints, near misses, resolved adverse events, and successful
  rollback narrow the future scope when a lower non-blocked scope remains;
- only confirmed clean delivery observations with no adverse event or rollback can
  maintain the current ceiling.

Successful rollback does not erase the event. Resolved evidence remains available as
counter-evidence and can inform a later policy proposal, but this receipt never
mutates policy automatically.

## Receipt Contents

The canonical receipt binds:

- source delivery receipt ref and digest;
- source package ref, digest, historical validity anchor, verification time, checks,
  and local signer limitation;
- source revocation handle, subject, policy, scenario, and approved scope;
- sampling strategy, time window, population, sample count, and limitations;
- typed outcome events and affected-party refs;
- rollback result;
- resulting scope, recipe state, replay requirements, and counter-evidence refs;
- revocation-registry updates when the source clearance is revoked;
- a strict claim boundary and metadata-only privacy flags.

The source-binding verifier recomputes refs and digests from the signed package. It
also replays the shared deterministic degradation policy and checks the fixed verifier
identity. A well-formed, locally signed outcome with a substituted source digest or an
under-degraded trust update is rejected.

## Affected Parties

An unresolved `affected_party_challenge` freezes the recipe, blocks future scope, and
requires follow-up. A risk owner cannot close or override that signal merely by
reasserting the original acceptance.

This is a protocol control, not proof that disclosure, appeal, redress, or compensation
has been completed.

## Revocation Boundary

`revoke_clearance` emits the original provenance revocation handle. Supplying that
handle to the local offline verifier makes the original signed package fail with
`not_revoked=false`.

This is a deterministic local registry update. It is not a global revocation service,
certificate authority, hosted coordination system, or guarantee that every downstream
copy has been withdrawn.

## Privacy And Authority

Outcome receipts remain metadata-only. They exclude raw customer payloads, report or
source text, attention streams, prompts, credentials, cookies, bearer tokens, signed
URLs, production mutation, and automatic customer sending.

The evaluator performs no model call, RAG lookup, network request, production action,
or automatic policy mutation. Agentic systems may propose or collect outcome evidence;
they cannot choose the trust action or rewrite its precedence.

## Commands

```bash
python3 scripts/generate_cbb_v1_contract_assets.py --check
python3 scripts/generate_cbb_v1_outcome_assets.py --check
python3 scripts/verify_cbb_v1_outcomes.py --check
```

Build from a signed package and an observation input:

```bash
python3 scripts/cbb_delivery_outcome.py build \
  --package signed-clearance-package.json \
  --observations outcome-observations.json \
  --private-key local-outcome-ed25519.key \
  --signer-id local-outcome-signer \
  --key-id local-outcome-key-1 \
  --expires-at 2026-08-10T00:00:00Z \
  --replay-nonce outcome-replay-nonce-0001 \
  --output delivery-outcome-receipt.json
```

The deterministic fixtures cover:

- monitored sample with no adverse signal;
- near miss that narrows scope;
- affected-party challenge that freezes the recipe;
- confirmed claim violation that revokes clearance;
- failed rollback that revokes clearance.

## Claim Boundary

A passing verifier proves schema validity, replayed deterministic non-increasing trust
actions, historical source binding, local source/outcome signatures, local revocation
effects, and the documented privacy boundary for the fixtures. It does not prove
customer success, production safety, legal or regulatory compliance, independent
signer identity, global revocation, or independent security audit completion.
