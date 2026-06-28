# WorkBuddy / CodeBuddy Marketplace

Schema: `workbuddy-codebuddy-marketplace-v1`
Version: `0.3.31-alpha`
Status: `pass`

## Install

- `/plugin marketplace add jzvcpe-goat/study-anything`
- `/plugin install study-anything@study-anything`

## Files

| Path | SHA-256 |
| --- | --- |
| `.codebuddy-plugin/marketplace.json` | `a8cf5cdfacfa5041e1a7e2465e7bb902c0e7ad61c7a973fad7a2a47f21892447` |
| `plugins/study-anything/.codebuddy-plugin/plugin.json` | `3fedf621289461042c6869896d04d849f042c03754d8ee098b1b27f7c3df1e36` |
| `plugins/study-anything/skills/study-anything/SKILL.md` | `a899be0a7138a88d5bbf24b8c41291f604f7f9a45f19526a9a2a7b5ca90b6a49` |
| `plugins/study-anything/commands/start.md` | `f2a729c57780fc0dc18239b6acc83f5fa9962ba2d4b00fc57a540b2e40aa1cb7` |
| `plugins/study-anything/commands/learn.md` | `ee387180a8f6f17278453fde5d1b5a7a7ccf75be13a52e86a7156cfd31552bff` |
| `plugins/study-anything/commands/diagnose.md` | `3ca08e6a599b16f4b7fa2aeb518792a4e4b838186068e7a3a5f99991bd563fd2` |
| `plugins/study-anything/commands/export.md` | `a30b093a4a9a2777a5bef3cb6583fc8c43b470a90435806270ee8b057823063d` |
| `docs/use-with-workbuddy.md` | `563157f7655b732a338ef0ed42a36ab0b372fe0d4d2726386ed53a1116f82363` |
| `platform/generated/study-anything-platform-openapi.json` | `2dac20f2e3277491f23930b90e8cb52f0d0a78b04e4bfa8458b8c48e0127e3f1` |

## Verify

- `python3 scripts/generate_workbuddy_plugin_marketplace.py --check`
- `python3 scripts/verify_workbuddy_plugin_marketplace.py --check`

## Boundary

This is an installable CodeBuddy/WorkBuddy plugin wrapper around the local
Study Anything runtime. It supports OpenAPI/local HTTP today. MCP remains a
planned extension and is not claimed as shipped in this plugin.
