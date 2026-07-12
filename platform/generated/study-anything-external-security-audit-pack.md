# External Security Audit Pack

- Schema: `external-security-audit-pack-v1`
- Status: `ready_for_independent_audit`
- Version: `v0.3.32-alpha`
- Scope areas: `7`
- Source/evidence files: `167`
- Archive SHA-256: `5dbe5671d8430effe78b836943958b3cdf55404a4c698ea1c113a6bd8313cfb6`

This pack is ready for an external human-led security audit at a pinned commit.
It does not claim that an audit, penetration test, or production certification
has completed. AI-only review and repository self-certification are forbidden.

Verification:

```bash
python3 scripts/generate_external_security_audit_pack.py --check
python3 scripts/verify_external_security_audit_pack.py --check
```
