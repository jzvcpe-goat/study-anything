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
| `.codebuddy-plugin/marketplace.json` | `951a823da6025c262fd2062ca2e6261f2477981e666433f7cff433fe316a73e6` |
| `plugins/study-anything/.codebuddy-plugin/plugin.json` | `ab8e07e783dc2a4ae091c3b5dd92f1f3079657ce2f748a9d7f3fe26feebca9a8` |
| `plugins/study-anything/skills/study-anything/SKILL.md` | `4c2ea479eb5e7420e0dc4619182f5618899fc5623a32192c2a6cbc47114edbea` |
| `plugins/study-anything/commands/start.md` | `e99dc14d7e79294eb921b3eb43400bac7ededc72c038be379f1d26a04b31db03` |
| `plugins/study-anything/commands/learn.md` | `32219417f6c36424162b9ae062e7f44d8f9ec82b621b9b2cb352c667c5260040` |
| `plugins/study-anything/commands/diagnose.md` | `315abecda77bf53df22fa7e583f13745298d74cf6b5bac4c1812f8cf0e0f2970` |
| `plugins/study-anything/commands/export.md` | `620e2e6fbe177317695661826c00b65e1e45ea8b9a219e4a6883ba281a04e9cd` |
| `docs/use-with-workbuddy.md` | `24e820edfa859f07ea6e03bdc065bc3a14b7b70d931b33fb983103a76412941c` |
| `scripts/workbuddy_learning_flow.py` | `6fe90b6a7753fb57bba9ff1394262c5c453684f13b26e8daed6b6f2c7147d00c` |
| `scripts/verify_workbuddy_inline_learning_flow.py` | `2cab9e288db5474ffdef612b75588c49c9da3134e782995be942bb280748608b` |
| `platform/schemas/workbuddy-learning-input-v1.schema.json` | `eda257e79f33117bd255e5421e33d55c20f05c76a45b0b1e2c516d24dd71191e` |
| `platform/schemas/workbuddy-learning-output-v1.schema.json` | `ddb75f6d2652ec853fd4b37758f2f7dca41ff4e58ccc1aaeeecec149ca5795fa` |
| `fixtures/workbuddy-learning-flow/deepseek-pm-interview/input.json` | `1565443f015655ae2184ad2b19fd63c22d6a92fce0df278df0b44db2b9634755` |
| `fixtures/workbuddy-learning-flow/deepseek-pm-interview/expected-boundary.json` | `278baaf1946043fc486c40ba085e33f6cc72f5595242c36fe0b431e934749120` |
| `platform/generated/study-anything-workbuddy-inline-learning-flow.json` | `913e6b6dca6f8a52a0cd86b8d261569c0b421ff6aa69fcf30584f511ca797e3d` |
| `platform/generated/study-anything-platform-openapi.json` | `d9cfb624863efa53480d7d374bace9d35d40692ee6fb40e6ae3ac0c5c340a550` |

## Verify

- `python3 scripts/verify_workbuddy_inline_learning_flow.py --check`
- `python3 scripts/generate_workbuddy_plugin_marketplace.py --check`
- `python3 scripts/verify_workbuddy_plugin_marketplace.py --check`

## Boundary

This is an installable CodeBuddy/WorkBuddy plugin wrapper around the local
Study Anything Human Reconstruction / Learning Adapter. It supports WorkBuddy
inline learning today, keeps OpenAPI/local HTTP as fallback, and keeps MCP as a
planned extension rather than a shipped runtime claim.
