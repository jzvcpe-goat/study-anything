# Python Supply Chain

Study Anything resolves application dependencies into `uv.lock`, a universal lock covering the
supported Python 3.11 and 3.12 range. Docker, CI, and Skill Mode consume generated pip requirement
files with exact versions and SHA-256 hashes.

## Trust Boundary

- `pyproject.toml` declares the allowed ranges.
- `uv.lock` is the cross-platform resolution truth source.
- `requirements/locked-*.txt` are pip-compatible installation projections.
- `study-anything-python-sbom.cdx.json` is the CycloneDX 1.5 inventory.
- `study-anything-python-supply-chain.json` records hashes, counts, privacy boundaries, and claims.

The receipt does not claim that dependencies are vulnerability-free. GitHub dependency review
blocks newly introduced high-severity advisories in pull requests. CodeQL, Dependabot, and an
external security review remain separate evidence layers.

## Maintainer Flow

```bash
python3 scripts/generate_python_supply_chain.py --refresh
python3 scripts/generate_python_supply_chain.py --check
```

The check is offline and fails when `pyproject.toml`, `uv.lock`, an exported requirement file, the
SBOM, or the receipt is stale. Network access is only required when a maintainer intentionally
refreshes the lock.

Supported Python is `>=3.11,<3.13`. Python 3.13 and newer are outside the current tested matrix and
must not be inferred from the lock.
