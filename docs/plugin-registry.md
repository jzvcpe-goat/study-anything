# Plugin Registry

The Study Anything registry is a local trust ledger, not a remote marketplace.
It helps users and platform Agents review plugin metadata before installation.

## Registry Shape

Bundled registry metadata lives at `plugins/registry.json`:

```json
{
  "schemaVersion": "plugin-registry-v1",
  "apiVersion": "0.1",
  "trustedKeys": [],
  "plugins": [
    {
      "id": "example-exporter",
      "name": "Example Exporter",
      "version": "0.1.0",
      "path": "plugins/example-exporter",
      "category": "exporter",
      "status": "bundled",
      "sourceDigest": "sha256:..."
    }
  ]
}
```

The registry may pin `sourceDigest` values and optional Ed25519 registry
signatures. Manifest-level signatures are treated as metadata only in the alpha.

## Review Endpoint

`GET /v1/plugins/registry-review` returns `plugin-registry-review-v1`.
It compares discovered local plugins with local registry metadata and reports:

- verified digest count
- verified registry-signature count
- update candidates by registry version
- blocked entries such as digest mismatches
- manual review requirements
- per-plugin actions such as `ready`, `confirm_update_review`,
  `manual_review_required`, `block_install`, or `add_to_signed_registry`

The endpoint is metadata-only. It does not download code, install updates,
execute entrypoints, contact a marketplace, or store secrets.

## Digest Policy

Source digests include install-relevant files and ignore generated or local-only
artifacts:

- ignored directories/files: `__pycache__`, `.git`, `.DS_Store`
- ignored suffixes: `.pyc`, `.pyo`

When plugin code or `plugin.json` changes, recompute and update `sourceDigest`.
The release verifier requires bundled examples to remain digest-verified.

## Commercial Boundary

The alpha registry is intentionally free and local. A future hosted ecosystem
may add maintainer review queues, signed distribution, and convenience hosting,
but the OSS core must keep local install, local review, and local export paths
usable without an account.

