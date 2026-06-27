# Study Anything Platform Plugin Downloads

Schema: `platform-plugin-downloads-v1`
Version: `v0.3.31-alpha`
Status: `pass`

Use the GitHub Release page as the public download entrypoint:

`https://github.com/jzvcpe-goat/study-anything/releases/tag/v0.3.31-alpha`

These are import helpers for user-owned platform Agents. They do not contain
real model keys, do not publish a marketplace listing, and still call a local or
private Study Anything runtime.

| Platform | Archive | Manifest | Checksum |
| --- | --- | --- | --- |
| `codex` | `study-anything-codex-plugin-pack.zip` | `study-anything-codex-plugin-pack.json` | `study-anything-codex-plugin-pack.sha256` |
| `kimi` | `study-anything-kimi-plugin-pack.zip` | `study-anything-kimi-plugin-pack.json` | `study-anything-kimi-plugin-pack.sha256` |
| `workbuddy` | `study-anything-workbuddy-plugin-pack.zip` | `study-anything-workbuddy-plugin-pack.json` | `study-anything-workbuddy-plugin-pack.sha256` |

## Verification

- `python3 scripts/generate_platform_plugin_packs.py --check`
- `python3 scripts/verify_platform_plugin_packs.py --check`
- `python3 scripts/generate_platform_plugin_downloads.py --check`
- `python3 scripts/verify_platform_plugin_downloads.py --check`

## Privacy

No raw source text, learner answers, Agent endpoint secrets, real model keys,
local absolute paths, or private browser/app/video context are included.
