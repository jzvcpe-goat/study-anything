# CBB Protocol v1 Deterministic Trust Kernel

The Trust Kernel is the non-agentic decision core for canonical CBB Protocol v1
objects. It consumes one `cbb.trust-policy.v1`, one
`cbb.evidence-bundle.v1`, and one `cbb.qualified-reconstruction.v1`, then emits
one `cbb.gate-decision.v1`.

```text
TrustPolicy + EvidenceBundle + QualifiedReconstruction
  -> deterministic Trust Kernel
  -> GateDecision
```

## Decision Order

The evaluator applies these rules in order:

1. Cross-receipt subject and policy references must match.
2. Duplicate evidence types and unknown hard-deny signals block.
3. A passed `hard_deny:<policy-deny>` signal blocks every scope.
4. Failed blocking evidence blocks; missing or stale evidence returns
   `needs_evidence` with blocked scope.
5. Required reviewer roles must be backed by passed, active, fresh Qualified
   Reconstruction evidence.
6. The allowed scope is the minimum of policy, evidence, reconstruction, and
   their claim-boundary ceilings.

Hard-deny observations use typed evidence items such as:

```json
{
  "evidence_type": "hard_deny:production_mutation",
  "status": "passed",
  "supported_scope": "blocked",
  "source_schema_version": "cbb.hard-deny-signal.v1"
}
```

`passed` means that the deny condition was positively observed, not that the
candidate passed. Unknown deny identifiers fail closed.

## Runtime Boundary

The canonical kernel is a pure Python function. Its import graph contains only
Python data helpers and canonical CBB Protocol contracts. It has no filesystem,
network, subprocess, browser, model-provider, Agent framework, RAG, or legacy
runtime dependency.

Agentic components may later discover candidate boundaries or collect typed
evidence. They cannot import authority into the kernel, rewrite a policy, or
turn their own interpretation into an allow decision.

The runtime-isolation verifier is a static code-boundary check. It is not a
production sandbox and does not replace independent security review.

## V0 Compatibility

The shipped v0 CBB gate keeps its existing CLI, schemas, fixture names, reasons,
and output shape. Its four input receipts are now mapped to canonical v1 policy,
evidence, and reconstruction objects before the allow/block authority is
computed. The result is then rendered back into the unchanged v0 receipt.

The historical `--dual-loop-only` release mode intentionally runs without project
dependencies. In that mode the v0 gate retains its original dependency-free
decision path; canonical v1 verifiers are marked integrated but not passed. With
project dependencies present, compatibility fixtures prove that canonical routing
and the v0 decision path produce the same public result.

The Dual Loop compatibility chain also uses the canonical evaluator. The source
v0 `delivery-trust-receipt-v1` remains a compatibility ceiling and provenance
source; it is not circularly required as evidence for the gate that precedes the
canonical delivery receipt.

## Verification

```bash
python3 scripts/verify_cbb_v1_kernel.py --check
python3 scripts/verify_cbb_runtime_isolation.py --check
python3 scripts/verify_cbb_gate.py --check
python3 scripts/verify_cbb_v0_compatibility.py --check
./scripts/release_check.sh --cbb-protocol-only
```

Generated reports:

```text
platform/generated/study-anything-cbb-v1-kernel.json
platform/generated/study-anything-cbb-runtime-isolation.json
```

## Claim Boundary

This phase proves deterministic local policy evaluation, fail-closed evidence
handling, scope monotonicity, v0 compatibility, and static runtime isolation. Local
signing and supplied-registry revocation checks are a separate provenance layer;
the kernel itself does not prove signer identity, production sandboxing, customer
outcomes, safe Agentic evidence collection, or independent audit completion.
