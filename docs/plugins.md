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

Plugins must declare permissions. The alpha validator rejects missing IDs, unsupported hook names, and unsupported permissions.

## Local Installation

Install a plugin from an explicitly selected local directory:

```bash
python3 scripts/install_local_plugin.py /path/to/plugin
```

The installer validates `plugin.json`, copies the directory into `data/plugins`, excludes cache files, and refuses implicit overwrites. Use `--replace` only when you intentionally want to update an installed plugin.

The alpha installer does not download code, execute plugin entrypoints, or bypass manifest permissions. Remote registries, signing, review metadata, and an install UI remain future trust-layer work.
