# External Security Audit Kit

This directory is the source of truth for preparing an independent security
audit of Study Anything / Cognitive Black Box.

## Current State

`ready_for_independent_audit` means the scope, rules, evidence catalog, finding
format, and report format are ready for an external reviewer. It does not mean
an audit has run or passed.

The repository may generate and verify the audit pack. It may not identify
itself as the independent auditor or set the final audit decision.

## Auditor Start

1. Pin the exact repository commit and record it in the final report.
2. Read `threat-model.md` and `rules-of-engagement.md`.
3. Review `audit-plan.json` and confirm every in-scope area.
4. Run the listed deterministic gates, then perform independent source review
   and negative testing in an isolated environment.
5. Record each finding with
   `platform/schemas/security/external-security-audit-finding-v1.schema.json`.
6. Produce and sign a report following
   `platform/schemas/security/external-security-audit-report-v1.schema.json`.
7. Apply `remediation-policy.md`; rerun affected tests after fixes.

## Boundary

The distributable pack is metadata-only. It contains public documentation,
schemas, generated receipts, hashes, and commands. It excludes real secrets,
tokens, cookies, user-owned Agent credentials, raw learner data, raw source
text, production payloads, screenshots, and private exploit details.

An auditor uses a separate pinned repository checkout for source inspection and
test execution. Sensitive reproduction details must move through an agreed
private channel, not a public issue or generated evidence pack.
