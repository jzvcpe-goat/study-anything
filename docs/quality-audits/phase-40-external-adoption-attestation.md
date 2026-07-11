# Phase 40 External Adopter Attestation Audit

Audit date: 2026-07-11 PDT

Project: Delivery Clearance Protocol v1 external-adopter attestation extension

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/v0.3.300-external-adoption-attestation`

Audit base: `cc9a5aa1f5739cd667addfa774d6301f7873efda`

Auditor: Codex

Authority: operator-provided `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

Decision: **Ready for pull request. Merge remains contingent on protected GitHub
checks; external adoption and independent audit remain open human checkpoints.**

The implementation closes the previous engineering gap between the reserved
`external_adopter` class and a real independently supplied observation. An optional
Protocol v1 extension accepts a detached Ed25519 attestation only when an expected
scope supplied outside the envelope pre-pins the adopter organization, human observer,
key fingerprint, independence reference, release commit, source package, clearance
receipt, revocation handle, source scope, conformance digest, and exact Controlled
Adoption case digest.

The extension does not create Delivery Clearance. It can only let the existing
Controlled Adoption evaluator recognize that an observation came from a separately
trusted external actor. The evaluator then preserves its original non-increasing scope,
incident, rollback, revocation, and reopen rules.

All repository fixtures remain synthetic. The hermetic external-path test proves the
code path only and is not counted as real adopter evidence. The generated report must
continue to record zero real external adopters until an external actor supplies signed
evidence under a trust root pinned outside repository automation.

## S0-S3 Source, Boundary, And Product Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Active source | Pass | Isolated worktree on `codex/v0.3.300-external-adoption-attestation` |
| No-touch boundary | Pass | Protected historical workspace was not modified |
| Product contract | Pass | Delivery Clearance remains the final protocol before scoped responsibility transfer |
| Included delivery | Pass | Extension contracts, intake, integration, CLI, fixtures, schemas, verifier, docs, release and distribution gates |
| Excluded delivery | Pass | No production mutation, customer send, model call, network call, external actor invention, customer outcome claim, or audit closure |
| Canonical protocol | Pass | Eight canonical Protocol v1 objects remain unchanged; attestation is an optional extension |
| Real adopter evidence | Pending | Generated fixture report explicitly records zero |

## S4-S8 Loop, Information, Data, And Action Surface

The external-adopter attestation loop is:

1. an operator pins the exact expected scope and independent adopter identity outside
   the submitted envelope;
2. the adopter signs canonical metadata for one exact Controlled Adoption case;
3. intake verifies the actual public-key fingerprint, detached signature, actor
   independence, trust-root match, commit, package, receipt, revocation handle, source
   scope, conformance digest, case id, and case digest;
4. rejected and synthetic states remain distinct from external verification;
5. Controlled Adoption replays the original expected scope and signed envelope, then
   checks the resulting receipt against the actual case;
6. the final adoption receipt may record real evidence but cannot expand source scope
   or grant customer/production authority.

| Surface | Authority boundary |
| --- | --- |
| Expected scope | Operator-controlled trust root; not accepted from the envelope |
| Detached signature | Proves key possession over canonical attestation bytes only |
| Adopter trust record | Must exactly match an independently pinned identity |
| Attestation receipt | Audit record only; its caller-supplied booleans are not a trust root |
| Controlled Adoption | Replays the signed envelope and may only maintain or reduce source scope |
| Hermetic path test | Contract behavior only; not real external execution |
| Repository fixtures | Synthetic evidence with a permanent real-evidence count of zero |

## S9 Security, Privacy, And Permission

| Boundary | Result |
| --- | --- |
| Wrong release commit | Rejected |
| Wrong Controlled Adoption case digest | Rejected |
| Wrong source package, receipt, revocation handle, scope, or conformance digest | Rejected |
| Invalid detached signature | Rejected |
| Declared fingerprint not matching the actual public key | Rejected |
| Self-asserted external identity absent from expected trust roots | Rejected |
| Repository actor self-attestation | Rejected |
| Class-name or boolean-only external claim | Blocked |
| Missing expected scope or signed envelope for external case | Blocked |
| Signed envelope replayed against another case | Blocked |
| Production mutation or automatic customer send | Forbidden |
| Secret-like metadata | Rejected |
| Raw source, customer payload, prompts, attention stream, or credentials | Excluded |

The deterministic fixture key is derived in code and only exercises verification. The
private key is never emitted into schemas, fixtures, reports, archives, or distributions.
The intake kernel hard-rejects that public fixture fingerprint as an external trust root,
even if a caller places it in an expected scope.

## S10-S13 Commercial, Production, UI, Copy, And Legacy

- No customer delivery, hosted service, production operation, or commercial clearance
  is introduced.
- No UI is added; the operator surface remains explicit JSON, CLI, and short docs.
- Public positioning remains Delivery Clearance / AI Delivery Clearance Protocol /
  AI 交付放行协议 and “未经放行，不得交付。”
- The extension proves why an external observation may enter evidence; it does not
  prove the AI deliverable was correct or broadly safe.
- Existing local shadow, dogfood, audit-intake, canonical Protocol v1, and v0
  compatibility behavior remains available.

## S14 Automated Evidence

| Gate | Current result |
| --- | --- |
| Generated adoption/attestation/audit assets | Pass; 27 schemas, reports, and fixtures current |
| External-adoption attestation verifier | Pass; seven public cases, hermetic integration, and 20 named checks |
| Existing Controlled Adoption verifier | Pass |
| Existing external audit intake verifier | Pass |
| Focused unit tests | Pass; 11 adoption/audit and release-script tests |
| Ruff | Pass across the repository |
| Strict mypy | Pass on five new and changed core modules |
| External audit pack convergence | Pass; 167 declared files, 169 archive entries, offline hash validation |
| External audit pack SHA-256 | Pass; use the checked-in `.sha256` sidecar to avoid a self-referential archive digest |
| Platform/adoption/topology convergence | Pass; 59 nodes, 70 hard dependencies, 18 feedback dependencies |
| Full API suite | Pass; 1001 tests |
| Partial release modes | Pass; Dual-Loop-only, CBB-protocol-only, and skip-clean-clone each retained partial claim boundaries |
| Full clean-clone release | Pass; full, clean-clone, and dependency-install receipts true; known issue none |
| Protected GitHub checks | Pending PR |
| Real external adopter evidence | Not present |
| Independent human security audit | Pending issue #414 |

## Gate Matrix

| Rule | Gate | Merge blocking |
| --- | --- | --- |
| Signed attestation requires pre-pinned identity | `verify_cbb_external_adoption_attestation.py --check` | Yes |
| Actual key fingerprint must match declared fingerprint | attestation verifier negative case | Yes |
| Public deterministic fixture key cannot become an external trust root | attestation verifier negative case | Yes |
| Attestation must bind the exact case and source clearance | attestation verifier and Controlled Adoption integration | Yes |
| Controlled Adoption receipt identity binds attestation ref and digest | attestation verifier | Yes |
| Synthetic fixtures cannot produce real evidence | generated report and unit tests | Yes |
| Controlled Adoption cannot expand source scope | existing adoption verifier | Yes |
| New evidence reaches audit and platform distributions | audit-pack and topology gates | Yes |
| Release receipt names the new verifier | `release_check.sh` and release-script tests | Yes |

## S15 Decision

Local implementation and release evidence are complete. Open the pull request and do
not merge until protected GitHub checks are green. After merge, re-pin the exact merge
commit and final package digests in the separate external-adopter coordination issue and
external security audit issue #414.

After merge, the only valid next transition is external: assign a real independent
adopter or auditor, pin their identity outside the submitted envelope, and ingest their
signature. Until then preserve:

- `independent_external_adopter_assigned: false`;
- `external_signed_attestation_received: false`;
- `real_external_adopter_evidence_count: 0`;
- `external_auditor_assigned: false` and `audit_completed: false`.

This phase authorizes an evidence-request channel, not production, customer delivery,
external adoption claims, broad trust, or independent audit completion.
