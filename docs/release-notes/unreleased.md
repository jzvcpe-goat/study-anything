# Unreleased Main Development Line

## Delivery Clearance Outcomes And Trust Degradation

- Made `Delivery Clearance / AI Delivery Clearance Protocol / AI 交付放行协议` the
  public GitHub identity with the rule `未经放行，不得交付。`
- Added `cbb.delivery-outcome-receipt.v1`, bounded post-delivery sampling, typed
  incidents/complaints/near misses/claim violations/affected-party challenges, and
  rollback outcomes.
- Added deterministic `maintain_current_ceiling`, `narrow_scope`, `freeze_recipe`, and
  `revoke_clearance` actions. Outcome evidence can never increase source authority.
- Bound every outcome envelope to a separate local Ed25519 signature, expiry, replay
  nonce, verifier identity, and revocation handle before it can update local trust state.
- Failed rollback and substantiated claim/evidence violations revoke the local source
  handle; open affected-party challenges freeze the recipe and require follow-up.
- Added five outcome fixtures, source-binding and revocation negative tests, CLI,
  verifier, release receipt fields, and external-audit preparation evidence.
- This is metadata-only local proof, not customer-success evidence, production
  approval, global revocation, or independent audit completion.

## CBB Protocol v1 Local Provenance

- Extended `cbb.receipt-provenance.v1` with canonical policy, evidence,
  reconstruction, decision, and package-binding digests; local Ed25519 signer
  metadata; expiry; replay nonce; and revocation references.
- Added owner-only local key generation, scope-bounded signing, and offline package
  verification that replays the deterministic Trust Kernel.
- Added signed, unsigned, expired, revoked, replay, object-tamper, signature-tamper,
  and wrong-public-key fixtures plus independent provenance and tamper verifiers.
- Local signatures prove content integrity and embedded-key possession only. They do
  not prove third-party identity, production approval, customer outcomes, global
  revocation status, or independent audit completion.

## CBB Protocol v1 Deterministic Trust Kernel

- Added a pure canonical evaluator from Trust Policy, Evidence Bundle, and
  Qualified Reconstruction to Gate Decision.
- Added fail-closed hard-deny, failed/missing/stale evidence, reference-integrity,
  reviewer-role, and claim-boundary scope checks.
- Routed the shipped v0 CBB gate and v0-to-v1 Dual Loop mapping through the
  canonical kernel while preserving existing v0 output contracts.
- Added seven deterministic kernel fixtures, a kernel verifier, and a static
  runtime-isolation verifier with no model, RAG, network, subprocess, or legacy
  runtime imports.
- Added the kernel gates to CBB protocol release receipts. This remains local
  deterministic proof, not portable signing, production approval, or independent
  audit completion.

This file records changes on `main` after the tagged `v0.3.31-alpha` release.
It is not a release tag or published-image claim.

## Product

- Delivery Clearance is the public project identity: an open, local-first AI Delivery
  Clearance Protocol with this repository as its reference harness.
- Dual Loop is the core controlled-failure plus qualified-human-reconstruction
  mechanism, not the complete protocol identity.
- Study Anything remains the compatible Human Reconstruction / Learning Adapter,
  Python package, API namespace, and repository distribution name.
- Cognitive Loop remains an internal evidence and evolution workflow, not the
  top-level product name.
- A deterministic positioning verifier now blocks obsolete current branding while
  preserving historical release notes and compatibility identifiers.
- Protocol v1 now has seven strict canonical contract schemas, deterministic JSON
  bytes, and explicit v0 compatibility adapters. Pass, missing-evidence, hard-deny,
  stale, secret-like, malformed, naive-timestamp, invalid-state, and scope-expansion
  fixtures prove mappings preserve or narrow delivery authority and never expand it.
  This is a local unsigned contract layer, not the final Trust Kernel or portable
  cryptographic attestation.

## Security

- The independent security audit pack now carries the canonical CBB Protocol v1
  schemas, fixtures, verifier receipts, and protocol documents, while keeping the
  local-path-bearing Phase 31 audit record in the pinned repository rather than the
  public metadata-only ZIP.

- Repository-level security posture now distinguishes a green PR from a clean
  alert ledger. Read-only live verification fails on any open Code Scanning or
  Dependabot alert. Retrieval evals no longer expose caught exception text;
  network plugin endpoints resolve only single-name packages from configured
  intake roots; environment diagnostics omit raw untrusted values; and customer
  handoff JSON is metadata-only validated before persistence. Synthetic
  negative-fixture writes use narrow query-specific CodeQL annotations rather
  than workflow or repository-wide exclusions.
- A deterministic external security audit preparation pack now bundles the threat model, rules of
  engagement, remediation SLA, finding/report schemas, SBOM and public trust evidence, manifest,
  archive, and SHA-256 sidecar. Security CI and release gates verify its metadata-only privacy and
  reject self-certified `audit_passed` status. The pack is `ready_for_independent_audit`; no
  independent audit, penetration test, or production security certification is claimed.
- Optional `oidc_jwt` mode validates RS256/ES256 bearer tokens against an operator-supplied static
  public JWKS, binds opaque principals to issuer + tenant + subject, ignores request-body identity
  spoofing, tenant-filters sessions/workspaces, and principal-scopes non-demo Agent providers.
  Cross-tenant session lookups return `404`; unscoped local PMF/Sync/plugin/recovery surfaces are
  blocked in hosted mode. This is an application-layer foundation, not managed IdP lifecycle,
  database RLS, hosted infrastructure certification, or an independent external audit.
- Production HTTP Agent egress now requires a non-empty exact-origin allowlist;
  non-loopback origins require HTTPS, endpoints are revalidated before invocation,
  and redirects are rejected. Local single-operator mode keeps operator-selected
  endpoints without presenting that mode as a hosted SSRF boundary.
- Low advisory `GHSA-866g-f22w-33x8` has a metadata-only, time-bounded reachability
  acceptance through 2026-08-10. The scheduled security workflow and release gate
  fail when that review date expires or the dependency becomes directly reachable.
- Python 3.11/3.12 dependencies now resolve through a universal `uv.lock`. Docker, CI, Skill Mode,
  and repository policy jobs consume exact, SHA-256-bound requirements; a deterministic CycloneDX
  1.5 SBOM and metadata-only claim receipt are checked in and verified offline.
- The API and mock HTTP Agent run as fixed non-root UID/GID `10001:10001` with read-only roots,
  dropped capabilities, `no-new-privileges`, init shims, and hardened tmpfs mounts.
- GitHub Actions are pinned to full commit SHAs. CodeQL, dependency review, and container-policy jobs
  now provide a reviewable security baseline without replacing a threat-led or independent audit.
- Docker API publication defaults to `127.0.0.1`.
- Browser cross-origin access is disabled unless exact trusted origins are set.
- Production or non-loopback exposure requires bearer-token mode.
- CLI requests can read the private API token from environment or `.env` and
  never place it in the API URL.
- Public status and plugin responses do not expose local absolute data paths.

## Claim Boundary

These changes harden a private local/self-host API and add an optional OIDC JWT plus application-layer
tenant authorization foundation. They do not implement managed hosted accounts, account recovery,
SCIM, database row-level security, separate tenant databases, billing, paid services, production
mutation, or a realtime hosted console.

## Engineering Gates

- `verify_cbb_v1_contracts.py` and `verify_cbb_v0_compatibility.py` now block the
  CBB protocol release path when canonical schemas, fixtures, deterministic bytes,
  runtime isolation, or non-expanding compatibility mappings drift.

- PR #407 is recorded as the current metadata-only release-stack group after all protected GitHub
  checks passed. This terminal self-intake does not require another self-intake under the recursion
  stop rule.
- Strict reliability run `29060766261` now has a verified metadata-only `strict_dual_pass` index,
  rebuilt by bounded replay run `29066220685`; it remains one run, not a trend or production SLO.
- Completed reliability runs can now replay only their metadata index by source run ID. The replay
  binds same-repository artifacts to the original reliability workflow, event, and head commit; it
  cannot rerun, repair, or relax failed or diagnostic mode receipts.
- PR #405 is recorded as the current metadata-only release-stack group after all six required
  GitHub checks passed. This terminal self-intake does not require another self-intake under the
  recursion stop rule.
- PR #401 is recorded as the current metadata-only release-stack group after both required GitHub
  checks passed. This terminal self-intake does not require another self-intake under the recursion
  stop rule.
- The scheduled published-image reliability path now permits Compose to pull missing dependency
  images after the API image is explicitly pulled and identified. This fixes clean GitHub runners
  that do not already cache Postgres. Compose startup now uses three bounded, auditable attempts for
  transient runner failures, and reliability receipts use the Node 24 artifact action.
- PR #398 is recorded as the current metadata-only release-stack group after both required GitHub
  checks passed. This terminal self-intake does not require another self-intake under the recursion
  stop rule.
- PR #396 is recorded as the current metadata-only release-stack group after both required GitHub
  checks passed. This terminal self-intake does not require another self-intake under the recursion
  stop rule.
- `generated_evidence_topology.py` now checks the complete declared release-distribution evidence
  chain in one run and reports every stale node instead of stopping at the first failure.
- Refresh mode orders hard dependencies and explicitly converges the adoption-pack consumer feedback
  edges over at most three passes. Its receipt excludes command output, environment values, secrets,
  source text, answers, and local paths.
- CI and the release gate now verify deterministic self-host soak aggregation; Compose smoke runs a
  short real health window before backup/restore rollback.
- `self-host-soak-receipt-v1` records availability, latency, failure categories, consecutive failures,
  and observed recovery without response bodies, tokens, URLs, source text, answers, or local paths.
- The self-host launcher now stops early with a non-destructive recovery message when a regenerated
  `.env` no longer matches an existing Postgres volume; it never resets the volume automatically.
- The soak command refuses to forward a locally loaded API token to a non-loopback host unless the
  operator explicitly confirms the destination with `--allow-network-token`.
- Health probes reject HTTP redirects instead of forwarding authorization to another origin.
- CI runs Ruff across the Python package, tests, scripts, and plugins.
- CI runs strict mypy for the two explicit local API security targets while
  skipping traversal into third-party dependency stubs.
- Full-package strict mypy is not claimed yet. Existing dynamic artifact and
  optional-integration modules still have tracked annotation debt; expanding
  the type-check scope must happen by fixing those errors, not by globally
  suppressing them.

The short soak does not prove a multi-hour production SLO, incident response, retention enforcement,
or disaster recovery across every source-build and published-image environment.
