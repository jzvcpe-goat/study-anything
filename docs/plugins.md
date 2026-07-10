# Plugin API

For the machine-readable SDK contract, see `docs/plugin-sdk.md`.
For registry digest, review, and signature policy, see `docs/plugin-registry.md`.

Plugins extend Study Anything without changing the core workflow.

## Manifest

Each plugin ships a `plugin.json` file:

```json
{
  "id": "example-exporter",
  "name": "Example Exporter",
  "version": "0.1.0",
  "apiVersion": "0.1",
  "entrypoint": "plugin.py",
  "hooks": ["exporter"],
  "permissions": ["read:sessions"],
  "publisher": {
    "name": "Example Maintainer",
    "url": "https://example.invalid"
  },
  "review": {
    "status": "self_reviewed",
    "reviewedBy": "Example Maintainer",
    "reviewedAt": "2026-06-04",
    "notesUrl": "https://example.invalid/review"
  },
  "signature": {
    "type": "minisign",
    "signer": "Example Maintainer",
    "value": "signature-metadata-placeholder"
  },
  "homepage": "https://example.invalid/plugin",
  "sourceUrl": "https://example.invalid/source"
}
```

Only `id`, `name`, `version`, `apiVersion`, `entrypoint`, `hooks`, and `permissions` are required.
New plugins should also include `schemaVersion: plugin-manifest-v1`, `description`, and `capabilities`.
Trust metadata is optional in the alpha and is treated as review context, not proof of authenticity.

Supported review statuses:

- `unreviewed`
- `self_reviewed`
- `community_reviewed`
- `maintainer_reviewed`

## MVP Hooks

- `importer`: ingest readings or source material.
- `model_provider`: deprecated compatibility hook for one alpha release.
- `agent_provider`: register an agent provider.
- `agent_tool`: expose a backend tool available to an agent adapter.
- `agent_panel`: register a future client panel for agent status or configuration.
- `enrichment`: build redacted learning enrichment artifacts.
- `source_verifier`: validate ISBN, DOI, arXiv, repo, or local source references.
- `quiz_generator`: generate source-bound quiz items.
- `grader`: grade answers.
- `exporter`: export sessions, cards, or mastery logs.
- `ui_panel`: register a future client panel.

## Discovery

The API scans `STUDY_ANYTHING_PLUGIN_DIRS`, defaulting to `plugins` and `data/plugins` locally and `/app/plugins:/data/study-anything/plugins` in Docker. Each direct child directory with a `plugin.json` file is validated and returned by `GET /v1/plugins`.

File-facing API operations use the separate `STUDY_ANYTHING_PLUGIN_SOURCE_DIRS` intake allowlist, defaulting to the bundled `plugins` directory plus `data/plugin-intake` locally. The request sends one direct child directory name, never an absolute or traversal path. Hosted OIDC mode blocks all `/v1/plugins` routes until plugin administration has its own operator authorization boundary.

Bundled plugins are listed in `plugins/registry.json`. The registry is local metadata, not a remote
marketplace. It can pin `sourceDigest` for each plugin and can include trusted Ed25519 public keys
for registry signatures. Study Anything verifies registry digest/signature metadata when present,
but still never downloads or executes remote plugin code during preview or install.

Bundled examples:

- `plugins/example-exporter`: a read-only session exporter.
- `plugins/example-agent-provider`: an agent provider template for a user-owned HTTP gateway.
- `plugins/example-web-importer`: an importer template that turns a user-approved web excerpt into
  `learning-context-package-v1`.
- `plugins/example-note-importer`: an importer template that turns Markdown or Obsidian note excerpts
  into `learning-context-package-v1` with backlink metadata.
- `plugins/example-enrichment-importer`: an importer plus enrichment template for micro-lesson
  artifacts.

## SDK Surfaces

- `GET /v1/plugins/sdk`: typed hook contract, permissions, capabilities, and privacy boundary.
- `GET /v1/plugins/capabilities`: installed plugin capability index with trust summaries.
- `POST /v1/plugins/validate-package`: validate one intake directory name without install or execution.

## Platform Adoption Kit

The platform adoption pack includes `plugins/registry.json` and the bundled sample plugin manifests
and sources. After editing a bundled plugin, its manifest, or registry metadata, run:

```bash
python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check
python3 scripts/verify_plugin_quarantine.py
python3 scripts/generate_platform_adoption_pack.py --check
```

`plugin-ecosystem-adoption-kit-v1` proves the sample plugins remain digest-verified, the
quarantine-first trust policy is intact, platform packs include the plugin evidence command, and no
plugin entrypoint is executed during validation.

## Importer SDK Shape

Importer plugins should produce a Learning Context Package rather than mutating Study Anything state
directly. The package is then passed to:

- `POST /v1/importers/{plugin_id}/run`
- `POST /v1/context-packages/validate`
- `POST /v1/sessions/from-context-package`
- `POST /v1/sessions/{session_id}/context-package`

Discovery, preview, install, and registry review remain metadata-only. `POST /v1/importers/{plugin_id}/run`
is the only alpha endpoint that executes an importer entrypoint. It requires:

- the plugin manifest to be valid and locally discoverable
- the `importer` hook
- `write:context` permission
- exact `confirmed_permissions`
- `allow_network=true` when the manifest requests `network:http`
- a valid `learning-context-package-v1` return value from `build_context_package(...)`

This runtime is intentionally narrow. It does not download code, store model keys, or grant browser/file
access to plugins. Platform Agents should gather external data first and pass bounded excerpts into the
importer inputs.

The stable package schema is `learning-context-package-v1`:

```json
{
  "schema_version": "learning-context-package-v1",
  "title": "NotebookLM Style Learning Context",
  "reference": "notebooklm-style://manual/demo",
  "producer": "platform-agent-or-plugin-id",
  "language": "zh",
  "track": "PRODUCT",
  "items": [
    {
      "source_type": "web",
      "reference": "https://example.invalid/source",
      "title": "Source title",
      "text": "Bounded excerpt selected by the user or platform Agent.",
      "locator": "section=overview",
      "metadata": {
        "importer_plugin": "example-web-importer"
      }
    }
  ]
}
```

Supported `source_type` values are `web`, `document`, `video_slice`, `app_context`, `markdown_note`,
and `obsidian_note`. Importers should keep excerpts bounded, preserve stable references and locators,
and keep external Agent credentials outside the package. Obsidian importers may include
`metadata.obsidian_backlinks`; the Obsidian export will preserve them as `[[Backlinks]]`.

## Permission Model

Plugins must declare permissions. The alpha validator rejects missing IDs, unsupported hook names, and unsupported permissions. Discovery and preview responses include permission labels, descriptions, and coarse risk levels so users can review what a plugin is asking for before installation.

## Trust Summary

Discovery, preview, and install responses include a `trust` object:

- `source_digest`: stable SHA-256 digest of install-relevant files, excluding cache files, `.git`, and local OS metadata.
- `review_status`: manifest review metadata or `unreviewed`.
- `signature_status`: `unsigned` or `metadata_only`.
- `registry_status`: `not_listed`, `digest_verified`, `digest_mismatch`, or `missing_digest`.
- `risk_level`: highest permission risk across the manifest.
- `install_recommendation`: `allow_with_confirmation`, `review_required`, or `do_not_install`.
- `warnings`: human-readable reasons to slow down before install.

The trust policy is available at `GET /v1/plugins/trust-policy`. It states the alpha install rules:
local directories only, no remote code downloads, no entrypoint execution during install, and no raw
secrets stored by Study Anything.

Registry review is available at `GET /v1/plugins/registry-review`. It compares local registry metadata
with discovered local plugins and returns:

- verified digest count
- verified registry-signature count
- update candidates by registry version
- blocked entries such as digest mismatches
- plugins or registry entries requiring manual review
- per-plugin actions such as `ready`, `confirm_update_review`, `manual_review_required`,
  `block_install`, or `add_to_signed_registry`

This endpoint is metadata-only. It does not download plugin source, install updates, execute plugin
entrypoints, or contact a remote marketplace. Use it before installing or updating community plugins,
then perform source review and local installation explicitly.

Manifest `signature` fields remain metadata-only. Registry entries can add `sourceDigest` and an
Ed25519 signature over:

```text
study-anything-plugin-registry-v1
<plugin_id>
<version>
<source_digest>
```

When a matching trusted public key is present in the local registry, Study Anything reports
`signature_status=registry_signature_verified`; mismatched digests or invalid signatures return
`do_not_install`. Remote marketplace payments and automatic updates remain future trust-layer work.

## Local Installation

Review a plugin from an explicitly configured intake directory:

1. Copy the plugin directory under `plugins` or `data/plugin-intake`, or configure another trusted root with `STUDY_ANYTHING_PLUGIN_SOURCE_DIRS`.
2. Send only that directory name as `source_path`; absolute paths, nested paths, and traversal are rejected.
3. Preview the manifest.
4. Review and check every requested permission.
5. Quarantine the plugin after the permission list is confirmed.
6. Install only after reviewing the quarantined copy and sending explicit approval.

The same flow is available through the API:

- `POST /v1/plugins/preview`
- `POST /v1/plugins/validate-package`
- `POST /v1/plugins/install`

Example request body: `{"source_path": "example-exporter"}`.

`/v1/plugins/install` requires the caller to send `confirmed_permissions` matching the manifest exactly. A missing or partial confirmation is rejected with `409`.
By default the endpoint returns `lifecycle_status=quarantined`, copies the package to `STUDY_ANYTHING_PLUGIN_QUARANTINE_DIR`, executes no entrypoints, and does not make the plugin appear in `GET /v1/plugins`.
Send `approve_install=true` only after manual review to copy the same source into `STUDY_ANYTHING_PLUGIN_INSTALL_DIR` and make it discoverable.
Trust-policy blocks such as digest mismatches or invalid registry signatures return `409` before either copy is written.

You can also use the CLI:

```bash
python3 scripts/install_local_plugin.py /path/to/plugin
```

The CLI quarantines by default. Use `--approve-install` only after review:

```bash
python3 scripts/install_local_plugin.py /path/to/plugin --approve-install
```

The installer validates `plugin.json`, copies the directory into the quarantine or install directory, excludes cache files, and refuses implicit overwrites for approved installs. Use `--replace` only when you intentionally want to update an installed plugin.

The alpha installer does not download code, execute plugin entrypoints, or bypass manifest permissions.
Remote registries, review queues, update UX, and marketplace payments remain future trust-layer work.
