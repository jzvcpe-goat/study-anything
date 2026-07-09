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
| `plugins/study-anything/skills/study-anything/SKILL.md` | `0d098b6b576fbe92acf4ca36df72765d7267a0440c5068c0a74f3288bf42993c` |
| `plugins/study-anything/commands/start.md` | `e99dc14d7e79294eb921b3eb43400bac7ededc72c038be379f1d26a04b31db03` |
| `plugins/study-anything/commands/learn.md` | `32219417f6c36424162b9ae062e7f44d8f9ec82b621b9b2cb352c667c5260040` |
| `plugins/study-anything/commands/diagnose.md` | `315abecda77bf53df22fa7e583f13745298d74cf6b5bac4c1812f8cf0e0f2970` |
| `plugins/study-anything/commands/export.md` | `620e2e6fbe177317695661826c00b65e1e45ea8b9a219e4a6883ba281a04e9cd` |
| `docs/use-with-workbuddy.md` | `4b9f437e04d1e563605ed65f922452fffa1053bdb4447a7dceb736522e14c228` |
| `scripts/workbuddy_learning_flow.py` | `6fe90b6a7753fb57bba9ff1394262c5c453684f13b26e8daed6b6f2c7147d00c` |
| `scripts/verify_workbuddy_inline_learning_flow.py` | `2cab9e288db5474ffdef612b75588c49c9da3134e782995be942bb280748608b` |
| `platform/schemas/workbuddy-learning-input-v1.schema.json` | `eda257e79f33117bd255e5421e33d55c20f05c76a45b0b1e2c516d24dd71191e` |
| `platform/schemas/workbuddy-learning-output-v1.schema.json` | `ddb75f6d2652ec853fd4b37758f2f7dca41ff4e58ccc1aaeeecec149ca5795fa` |
| `fixtures/workbuddy-learning-flow/deepseek-pm-interview/input.json` | `1565443f015655ae2184ad2b19fd63c22d6a92fce0df278df0b44db2b9634755` |
| `fixtures/workbuddy-learning-flow/deepseek-pm-interview/expected-boundary.json` | `278baaf1946043fc486c40ba085e33f6cc72f5595242c36fe0b431e934749120` |
| `platform/generated/study-anything-workbuddy-inline-learning-flow.json` | `913e6b6dca6f8a52a0cd86b8d261569c0b421ff6aa69fcf30584f511ca797e3d` |
| `platform/generated/study-anything-platform-openapi.json` | `f557f2b5bf3fae701f5e0a277244e14e7add9e6fa89bac81d90f46912ff1c9cd` |

## Verify

- `python3 scripts/verify_workbuddy_inline_learning_flow.py --check`
- `python3 scripts/generate_workbuddy_plugin_marketplace.py --check`
- `python3 scripts/verify_workbuddy_plugin_marketplace.py --check`

## Boundary

This is an installable CodeBuddy/WorkBuddy plugin wrapper around the local
Study Anything learning workflow kernel. It supports WorkBuddy inline learning
today, keeps OpenAPI/local HTTP as fallback, and keeps MCP as a planned
extension rather than a shipped runtime claim.
