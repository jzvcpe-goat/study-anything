# External Security Audit Pack

- Schema: `external-security-audit-pack-v1`
- Status: `ready_for_independent_audit`
- Version: `v0.3.31-alpha`
- Scope areas: `7`
- Source/evidence files: `46`
- Archive SHA-256: `b551f64e723b2c36188fa6882dc69874d79ec286d5c423e03718b2bbf3c0e518`

This pack is ready for an external human-led security audit at a pinned commit.
It does not claim that an audit, penetration test, or production certification
has completed. AI-only review and repository self-certification are forbidden.

Verification:

```bash
python3 scripts/generate_external_security_audit_pack.py --check
python3 scripts/verify_external_security_audit_pack.py --check
```
