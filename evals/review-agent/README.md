# Cognitive Loop Review Agent Eval Fixtures

These fixtures are synthetic and safe to commit. They are used to evaluate whether an external
Cognitive Loop Review Agent can produce useful JSON reports before maintainers trust it in CI.

Run:

```bash
python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check
```

The harness verifies:

- approved, needs-review, and needs-fix decision paths
- critical security findings with CWE references
- low-confidence suppression
- privacy rejection for raw diff, file bodies, model keys, private Agent endpoints, and hidden reasoning

The cases include raw git diff text, but only for synthetic files created for eval. Study Anything
must not persist real operator diffs in generated evidence or platform packs.
