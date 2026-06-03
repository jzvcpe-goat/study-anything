# Plugin API

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
  "permissions": ["read:sessions"]
}
```

## MVP Hooks

- `importer`: ingest readings or source material.
- `model_provider`: deprecated compatibility hook for one alpha release.
- `agent_provider`: register an agent provider.
- `agent_tool`: expose a backend tool available to an agent adapter.
- `agent_panel`: register a frontend panel for agent status or configuration.
- `source_verifier`: validate ISBN, DOI, arXiv, repo, or local source references.
- `quiz_generator`: generate source-bound quiz items.
- `grader`: grade answers.
- `exporter`: export sessions, cards, or mastery logs.
- `ui_panel`: register a frontend panel.

## Discovery

The API scans `STUDY_ANYTHING_PLUGIN_DIRS`, defaulting to `plugins` and `data/plugins` locally and `/app/plugins:/data/study-anything/plugins` in Docker. Each direct child directory with a `plugin.json` file is validated and returned by `GET /v1/plugins`.

Bundled plugins are listed in `plugins/registry.json`. Future community registries should be append-only signed indexes rather than runtime code downloads.

Bundled examples:

- `plugins/example-exporter`: a read-only session exporter.
- `plugins/example-agent-provider`: an agent provider template for a user-owned HTTP gateway.

## Permission Model

Plugins must declare permissions. The alpha validator rejects missing IDs, unsupported hook names, and unsupported permissions. Discovery and preview responses include permission labels, descriptions, and coarse risk levels so users can review what a plugin is asking for before installation.

## Local Installation

Install a plugin from an explicitly selected local directory in the Web Agent page:

1. Paste a local or container-visible plugin directory path.
2. Preview the manifest.
3. Review and check every requested permission.
4. Install only after the permission list is confirmed.

The same flow is available through the API:

- `POST /v1/plugins/preview`
- `POST /v1/plugins/install`

`/v1/plugins/install` requires the caller to send `confirmed_permissions` matching the manifest exactly. A missing or partial confirmation is rejected with `409`.

You can also use the CLI:

```bash
python3 scripts/install_local_plugin.py /path/to/plugin
```

The installer validates `plugin.json`, copies the directory into the local plugin data directory, excludes cache files, and refuses implicit overwrites. Use `--replace` only when you intentionally want to update an installed plugin.

The alpha installer does not download code, execute plugin entrypoints, or bypass manifest permissions. Remote registries, signing, review metadata, and marketplace payments remain future trust-layer work.
