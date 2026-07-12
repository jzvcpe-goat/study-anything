# External Security Audit Pack

- Schema: `external-security-audit-pack-v1`
- Status: `ready_for_independent_audit`
- Version: `v0.3.31-alpha`
- Scope areas: `7`
- Source/evidence files: `167`
- Archive SHA-256: `9e02577c38649f8dbeb40c517708e802f09552f2f02da00455410502e2eb0a0d`

This pack is ready for an external human-led security audit at a pinned commit.
It does not claim that an audit, penetration test, or production certification
has completed. AI-only review and repository self-certification are forbidden.

Verification:

```bash
python3 scripts/generate_external_security_audit_pack.py --check
python3 scripts/verify_external_security_audit_pack.py --check
```
