# Security Finding Remediation Policy

| Severity | Initial notification | Fix target | Release effect |
| --- | --- | --- | --- |
| Critical | Immediate, within 4 hours | 24 hours or disable affected surface | Blocks every release and hosted use |
| High | Within 1 business day | 7 calendar days | Blocks hosted commercial launch |
| Medium | Within 3 business days | 30 calendar days | Requires owner, plan, and bounded acceptance |
| Low | Normal triage | 90 calendar days | Track in backlog with review date |
| Informational | Normal triage | No fixed SLA | Document disposition |

## Closure Evidence

A finding is not closed by a code change alone. Closure requires:

1. A remediation commit or explicit time-bounded risk acceptance.
2. A regression test or verifier that fails on the original condition.
3. Protected CI evidence for the remediation commit.
4. External auditor retest for critical and high findings.
5. A signed report update or addendum.

Risk acceptance must identify the owner, reason, compensating controls, expiry,
and review date. It may not be labeled as a fix or false positive unless the
external auditor agrees with that classification.

## Commercial Gate

Hosted commercial launch requires zero open critical or high findings. Medium
findings require a named owner, approved treatment, and deadline. The repository
must continue to report `ready_for_independent_audit`, not `audit_passed`, until
the signed external report and retest evidence exist.
