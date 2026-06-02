# Security Policy

## Supported Versions

The alpha line is supported on a best-effort basis until the first stable release.

| Version | Supported |
| --- | --- |
| 0.2.x-alpha | Yes |
| 0.1.x-alpha | No |

## Reporting

Please do not open public issues for vulnerabilities, leaked secrets, or privacy-impacting bugs. Email the project maintainers or use the private advisory channel once the GitHub repository is published.

## Security Defaults

- Telemetry is disabled by default.
- Demo model output is deterministic and local.
- Real provider credentials must not be returned by the API.
- Logs and traces should use user hashes and redact secrets.
- Generate `.env` with `python3 scripts/setup_env.py`; never deploy placeholder values from `.env.example`.
- `APP_ENV=production` should pass `python3 scripts/check_env.py --strict` before public exposure.
