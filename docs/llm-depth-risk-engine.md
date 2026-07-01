# LLM Depth Risk Engine / 大模型深度风险引擎

`LLMDepthRiskEngine` extends the existing Cognitive Loop `RiskEngine`.

The original risk layer answers: "Is this project change safe to promote?"
The depth layer adds: "Is the model behavior itself good enough to trust?"

`LLMDepthRiskEngine` 扩展现有 Cognitive Loop `RiskEngine`。原来的风险层回答：
“这个工程变更能不能提升？”新的深度层补上：“模型行为本身是否足够可靠？”

## Boundary

- Local-first and metadata-only by default.
- No model calls in the verifier.
- No stored model API keys, evaluator keys, Agent credentials, or private endpoints.
- No raw source text, raw learner answers, or raw prompt bodies in generated evidence.
- External judge/eval tools run only in the user's own eval environment.

## Evidence Contracts

The verifier emits `llm-depth-risk-engine-verification-v1`, containing:

- `prompt-evidence-v1`: versioned prompt hashes, prompt diff metadata, prompt lint, Promptfoo-compatible red-team and injection-test metadata.
- `hallucination-evidence-v1`: claim hashes, citation coverage, faithfulness, unsupported-claim ratio, and answer-source contradiction count.
- `rag-evidence-v1`: Ragas-compatible redacted dataset rows, context precision/recall, faithfulness, answer relevancy, and citation accuracy.
- `context-budget-evidence-v1`: context packing receipts, token budget, compression ratio, and lost-in-the-middle probes.
- `cost-quality-evidence-v1`: latency/tokens/cost/quality metadata and a cost-quality frontier so expensive models are not chosen by default.
- `llm-depth-risk-gate-v1`: promotion gate requiring both engineering risk and model risk to pass.

## Commands

```bash
python3 scripts/llm_depth_risk_engine.py build \
  --input fixtures/llm-depth-risk/pass.json \
  --summary

python3 scripts/verify_llm_depth_risk_engine.py --check
```

To refresh generated evidence:

```bash
python3 scripts/verify_llm_depth_risk_engine.py --write
```

Generated artifacts:

- `platform/generated/study-anything-llm-depth-risk-engine.json`
- `platform/generated/study-anything-llm-depth-risk-engine.html`

## Promotion Rule

Promotion is allowed only when both sides pass:

```text
engineering_risk_status == pass
model_risk_status == pass
```

If the sandbox/engineering side passes but hallucination, RAG, prompt, context,
or cost-quality evidence fails, promotion is blocked. If model evidence passes
but engineering risk fails, promotion is also blocked.

## External Eval Path

This layer creates the stable local evidence bridge. It does not replace mature
external eval frameworks.

- Promptfoo: prompt red-team, injection, contract regression.
- DeepEval: judge-model teaching quality and task completion.
- Ragas: grounding, context precision/recall, faithfulness, answer relevancy.
- LangChain AgentEvals: trajectory and tool-step quality comparison.

Study Anything never stores those evaluator credentials.

## Real-Agent Eval Bridge

The next layer is now `real-agent-eval-bridge-v1`. Users can run Promptfoo,
Ragas, DeepEval, or LangChain AgentEvals in their own model/eval environment and
import only `external-eval-adapter-receipt-v1` metadata into Study Anything.

Verification commands:

```bash
python3 scripts/verify_real_agent_eval_bridge.py --check
python3 scripts/verify_workbuddy_real_agent_learning_quality.py --check
```

The WorkBuddy/Kimi/Codex learning-quality harness compares deterministic demo,
user-owned HTTP Agent, and platform-Agent evidence on the same task. The
deterministic path is explicitly demo-only; it cannot satisfy real teaching
quality, citation grounding, hallucination-risk, or cost-quality promotion
requirements.
