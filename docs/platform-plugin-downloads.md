# Platform Plugin Downloads

Use this page when you want to download a platform-specific import pack from a
GitHub Release instead of cloning the repository first.

Release page:

`https://github.com/jzvcpe-goat/study-anything/releases/tag/v0.3.31-alpha`

Download one platform pack:

- Codex: `study-anything-codex-plugin-pack.zip`
- Kimi-compatible: `study-anything-kimi-plugin-pack.zip`
- WorkBuddy-style HTTP: `study-anything-workbuddy-plugin-pack.zip`

For CodeBuddy/WorkBuddy, prefer the installable marketplace wrapper when the
host supports plugin marketplaces:

```text
/plugin marketplace add jzvcpe-goat/study-anything
/plugin install study-anything@study-anything
```

That wrapper lives in:

- `.codebuddy-plugin/marketplace.json`
- `plugins/study-anything/.codebuddy-plugin/plugin.json`
- `plugins/study-anything/skills/study-anything/SKILL.md`
- `plugins/study-anything/commands/{start,learn,diagnose,export}.md`

Read `docs/use-with-workbuddy.md` for the beginner flow.

Each pack has a sidecar manifest and checksum:

- `study-anything-*-plugin-pack.json`
- `study-anything-*-plugin-pack.sha256`

Verify a downloaded archive:

```bash
shasum -a 256 -c study-anything-codex-plugin-pack.sha256
```

Then unzip the archive, read `PLUGIN_PACK_README.md`, and import only the
assets listed in `manifest.json`.

These packs are import helpers, not official marketplace listings. They do not
contain real model keys, do not call model providers directly, and still expect
Study Anything to run locally or behind your private endpoint. Your platform
Agent owns model credentials, browser access, external tools, and any private
network setup.

Maintainers regenerate and verify the public download index with:

```bash
python3 scripts/generate_platform_plugin_packs.py --check
python3 scripts/verify_platform_plugin_packs.py --check
python3 scripts/generate_platform_plugin_downloads.py --check
python3 scripts/verify_platform_plugin_downloads.py --check
python3 scripts/generate_workbuddy_plugin_marketplace.py --check
python3 scripts/verify_workbuddy_plugin_marketplace.py --check
```
