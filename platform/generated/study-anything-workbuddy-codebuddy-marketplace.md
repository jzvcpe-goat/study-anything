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
| `.codebuddy-plugin/marketplace.json` | `d6a6826fa8c4576a55fecf03f579b39ccedc16607ba0a09aad28a604ad16b1c3` |
| `plugins/study-anything/.codebuddy-plugin/plugin.json` | `5888d89d3d9689e29295e8a32d1f5bffe217975e4462a4608a27c542a0ef4401` |
| `plugins/study-anything/skills/study-anything/SKILL.md` | `2610d07e2dbb76609e3989fdfe9fc8d702ec2d299dcd611e7f85e07d81e70371` |
| `plugins/study-anything/commands/start.md` | `5fb6a4deddac61988255eddcc420abd574317ea33d6e3a8d6f0d360707b9bd85` |
| `plugins/study-anything/commands/learn.md` | `6cdbbc70caa5dc39f1986c5c14e5613456da05debd526bd5a86a0b877e546af0` |
| `plugins/study-anything/commands/diagnose.md` | `518f3f304899b807db275ed3981a26165fc289714a4baa9dbcbe6d266c6f04ed` |
| `plugins/study-anything/commands/export.md` | `620e2e6fbe177317695661826c00b65e1e45ea8b9a219e4a6883ba281a04e9cd` |
| `docs/use-with-workbuddy.md` | `5948ea220fb657606e48dadee9f7e2a694edb9a33201a83d23a6c5cf5a362d0a` |
| `scripts/workbuddy_learning_flow.py` | `bb501c94cbf8da1425b5ebc5fe29107b54fbfb7d27c5f47db3b17b66efac8d6d` |
| `scripts/verify_workbuddy_inline_learning_flow.py` | `4b907f58fe557637188efcce1ebf435b5e3dd6be1822610e8273af01d51ec813` |
| `platform/schemas/workbuddy-learning-input-v1.schema.json` | `3e547ab7a1a252bfe630c227152340fc199359db22cd6fa243415cdcf3a4cd2b` |
| `platform/schemas/workbuddy-learning-output-v1.schema.json` | `130baf0b5050dab6a23f4d27311d572033a43fa0af98bf88633c43879b07db24` |
| `fixtures/workbuddy-learning-flow/deepseek-pm-interview/input.json` | `5e17f5a2441d95646a9e4af8759b0cbd9bce9780cf2327fa36cc99749dff0715` |
| `fixtures/workbuddy-learning-flow/deepseek-pm-interview/expected-boundary.json` | `49419e92e8bc05e87176fcb307e497f75322952cbb2fb0c9632968804161a116` |
| `platform/generated/study-anything-workbuddy-inline-learning-flow.json` | `c2cedb257009bd0c03a608f3037e084eca3358f7ea4fc7fe51f30e166562af4c` |
| `platform/generated/study-anything-platform-openapi.json` | `2dac20f2e3277491f23930b90e8cb52f0d0a78b04e4bfa8458b8c48e0127e3f1` |

## Verify

- `python3 scripts/verify_workbuddy_inline_learning_flow.py --check`
- `python3 scripts/generate_workbuddy_plugin_marketplace.py --check`
- `python3 scripts/verify_workbuddy_plugin_marketplace.py --check`

## Boundary

This is an installable CodeBuddy/WorkBuddy plugin wrapper around the local
Study Anything learning workflow kernel. It supports WorkBuddy inline learning
today, keeps OpenAPI/local HTTP as fallback, and keeps MCP as a planned
extension rather than a shipped runtime claim.
