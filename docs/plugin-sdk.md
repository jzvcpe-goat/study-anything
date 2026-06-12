# Plugin SDK

Study Anything plugins are local-first extension packages. The SDK goal is to
let Kimi, Codex, WorkBuddy, and local operators inspect plugin capabilities
without executing plugin code or turning Study Anything into a model-key store.

## Runtime Boundary

- Study Anything validates manifests, permissions, source digests, registry
  metadata, and typed hook contracts.
- Study Anything executes only the narrow importer runtime in the current
  alpha: `POST /v1/importers/{plugin_id}/run`.
- Platform Agents own browsing, files, video slicing, outside tools, real model
  credentials, and user-facing conversation.
- Plugins must not store or return model API keys, raw secrets, agent endpoint
  secrets, full source bodies, learner answers, grading feedback, or private
  Agent metadata through registry, SDK, or validation surfaces.

## Manifest Contract

Use `schemaVersion: plugin-manifest-v1`:

```json
{
  "schemaVersion": "plugin-manifest-v1",
  "id": "example-exporter",
  "name": "Example Exporter",
  "description": "Template exporter for redacted Study Anything artifacts.",
  "version": "0.1.0",
  "apiVersion": "0.1",
  "entrypoint": "plugin.py",
  "hooks": ["exporter"],
  "capabilities": ["export.markdown", "export.second_brain_handoff"],
  "permissions": ["read:sessions"]
}
```

Required fields are `id`, `name`, `version`, `apiVersion`, `entrypoint`,
`hooks`, and `permissions`. `schemaVersion`, `description`, and `capabilities`
are optional for old alpha plugins, but new plugins should include them.

## Typed Hooks

`GET /v1/plugins/sdk` returns `plugin-sdk-v1`, the machine-readable source of
truth for hook contracts. Current hooks include:

- `importer`: exposes `build_context_package(...)` and returns
  `learning-context-package-v1`.
- `enrichment`: describes micro-lesson or visual learning artifact builders.
- `exporter`: describes redacted Markdown, Obsidian, and second-brain exports.
- `source_verifier`: validates references and citations without copying source
  bodies into registry metadata.
- `agent_provider`: templates user-owned Agent gateway configuration.
- `agent_tool`: describes tool contracts for platform Agent adapters.
- `agent_panel`: describes future UI panel metadata.

Deprecated compatibility hooks remain documented by the SDK response, but new
plugins should prefer `agent_provider` and `agent_panel` over model/UI legacy
names.

## Capability Index

`GET /v1/plugins/capabilities` returns `plugin-capability-index-v1` with:

- plugin id, name, version, hooks, and declared/inferred capabilities
- permission risk summaries
- trust report and alpha runtime notes
- privacy flags proving entrypoints were not executed

Use this endpoint when a platform Agent wants to decide whether it can run an
importer flow, offer an Obsidian/NotebookLM handoff, or show a local plugin
status summary.

## Package Validation

`POST /v1/plugins/validate-package` validates one local path without copying or
executing it:

```json
{
  "source_path": "plugins/example-exporter"
}
```

The response schema is `plugin-package-validation-v1`. It includes required
permission confirmations, hook contracts, inferred capabilities, trust summary,
and validation errors such as missing required hook permissions. It always
returns:

- `execution_allowed_by_validation: false`
- `privacy.entrypoints_executed: false`
- `privacy.package_copied: false`

Install remains a separate explicit action through `POST /v1/plugins/install`.

## Example Plugins

- `plugins/example-note-importer`: Markdown/Obsidian note importer.
- `plugins/example-web-importer`: user-approved web excerpt importer.
- `plugins/example-enrichment-importer`: importer plus enrichment artifact
  template.
- `plugins/example-exporter`: Markdown and second-brain exporter template.
- `plugins/example-agent-provider`: user-owned HTTP Agent gateway template.

