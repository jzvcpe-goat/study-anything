# Security Policy

## Supported Versions

The alpha line is supported on a best-effort basis until the first stable release.

| Version | Supported |
| --- | --- |
| 0.3.x-alpha | Yes |
| 0.2.x-alpha | Best effort |
| 0.1.x-alpha | No |

## Reporting

Please do not open public issues for vulnerabilities, leaked secrets, or privacy-impacting bugs. Email the project maintainers or use the private advisory channel once the GitHub repository is published.

## Security Defaults

- Telemetry is disabled by default.
- Demo model output is deterministic and local.
- Real provider credentials must not be returned by the API.
- Real model credentials should stay inside the user's own Agent gateway or
  platform Agent environment, not inside Study Anything.
- Logs and traces should use user hashes and redact secrets.
- Generate `.env` with `python3 scripts/setup_env.py`; never deploy placeholder values from `.env.example`.
- `APP_ENV=production` should pass `python3 scripts/check_env.py --strict` before public exposure.
- Local backup manifests are checksum verified and reject unsafe file paths.
- Sync restore preview must remain non-destructive and return only counts,
  hashes, conflicts, and warnings rather than plaintext learning data.

## Recovery Hardening Checks

Run the current security recovery verifier before public release or risky local
upgrades:

```bash
python3 scripts/verify_security_recovery_hardening.py
```

The verifier covers backup manifest tamper detection, path traversal rejection,
wrong-passphrase redaction, restore-preview privacy, and the disabled destructive
restore API boundary.

See `docs/security.md` for the local-first security model and operational
recovery expectations.
