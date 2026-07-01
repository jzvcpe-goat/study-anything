# Real-Agent Eval Bridge

Study Anything can import evidence from Promptfoo, Ragas, DeepEval, and
LangChain AgentEvals after the user runs those tools in their own Agent/eval
environment. The bridge validates metadata receipts only.

Study Anything does not store model keys, evaluator keys, raw prompts, raw
source text, raw answers, browser state, or evaluator output bodies. It records
adapter id, task ref, status, metrics, hashes, and privacy flags.

## Commands

```bash
python3 scripts/verify_real_agent_eval_bridge.py --check
python3 scripts/verify_workbuddy_real_agent_learning_quality.py --check
```

To build a report from a receipt fixture:

```bash
python3 scripts/real_agent_eval_bridge.py eval-bridge \
  --input fixtures/real-agent-eval-bridge/pass.json

python3 scripts/real_agent_eval_bridge.py learning-quality \
  --input fixtures/workbuddy-real-agent-learning-quality/pass.json
```

## Adapter Receipts

Each imported receipt uses `external-eval-adapter-receipt-v1` and must prove:

- the eval ran in a user-owned environment;
- an external model was actually called for real-agent claims;
- Study Anything did not call a model or store keys;
- raw prompt/source/answer/evaluator output bodies are excluded;
- adapter-specific quality metrics pass.

Required adapters:

- Promptfoo: prompt contract, injection, citation-fabrication gates.
- Ragas: context precision/recall, faithfulness, answer relevancy, citation accuracy.
- DeepEval: teaching quality, hallucination score, answer relevancy.
- LangChain AgentEvals: trajectory match, tool-call coverage, invalid tool calls.

## Learning Quality Harness

The WorkBuddy/Kimi/Codex quality harness compares the same learning task across:

- deterministic demo output;
- user-owned HTTP Agent output;
- platform Agent output from WorkBuddy, Kimi, and Codex.

The deterministic path is always demo-only. It can prove wiring, not teaching
quality. Real promotion requires external model-call evidence plus passing
teaching quality, citation grounding, hallucination risk, unsupported-claim,
mechanical-restatement, and cost-quality frontier gates.
