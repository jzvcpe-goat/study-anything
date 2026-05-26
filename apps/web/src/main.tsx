import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type ProviderStatus = {
  provider_id: string;
  kind: string;
  label: string;
  endpoint?: string;
  capabilities: string[];
  enabled: boolean;
};

type AgentStatus = {
  providers: ProviderStatus[];
  defaults: Record<string, string | null>;
};

type ReadingSource = {
  source_type: string;
  reference: string;
  title: string;
  text: string;
  excerpt_hash: string;
  verified: boolean;
};

type QuizItem = {
  item_id: string;
  prompt: string;
  source_ref: string;
  excerpt_hash: string;
  rubric: string;
};

type GradingResult = {
  item_id: string;
  score: number;
  feedback: string;
  reward: number;
};

type AgentEventMetadata = {
  provider_id?: string;
  task_type?: string;
  status?: string;
  latency_ms?: number;
};

type EventPayload = {
  agent?: AgentEventMetadata;
  agents?: AgentEventMetadata[];
  stage?: string;
  count?: number;
  average?: number;
  level?: number;
  bloom?: string;
  kind?: string;
  message?: string;
};

type StudyEvent = {
  event_id: string;
  type: string;
  node: string;
  created_at: string;
  payload?: EventPayload;
};

type HitlInterrupt = {
  task_id: string;
  kind: string;
  message: string;
  payload: Record<string, unknown>;
  status: string;
};

type Session = {
  session_id: string;
  stage: string;
  track: string;
  source: ReadingSource | null;
  quiz_items: QuizItem[];
  answers: Array<{ item_id: string; text: string }>;
  grading_results: GradingResult[];
  mastery: { level: number; bloom: string };
  insights: string[];
  scribe_log: string[];
  hitl_interrupts: HitlInterrupt[];
  events: StudyEvent[];
  discarded: boolean;
  created_at: string;
  updated_at: string;
};

type SystemStatus = {
  status: string;
  version: string;
  data_dir: string;
  session_store?: string;
  session_count: number;
  open_hitl_count: number;
  langgraph_available: boolean;
  agent_status: AgentStatus;
  plugin_count: number;
};

type PluginStatus = {
  manifest: null | {
    plugin_id: string;
    name: string;
    version: string;
    api_version: string;
    entrypoint: string;
    hooks: string[];
    permissions: string[];
  };
  path: string;
  status: string;
  message: string;
};

type IntegrationStatus = {
  name: string;
  category: string;
  target: string;
  status: string;
  runtime_check: string;
  product_surface: string;
  next_step: string;
};

type ViewKey = "learn" | "agents" | "ops" | "plugins" | "branches";
type Locale = "zh" | "en";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const COPY = {
  zh: {
    branch: "分支：codex/ui-dashboard-foundation",
    selfHost: "本地优先 Alpha",
    recentSessions: "最近学习",
    refresh: "刷新",
    agentReady: "Agent 已就绪",
    agentSetupNeeded: "需要配置 Agent",
    noSessions: "还没有学习记录。",
    nav: [
      ["learn", "学习", "用自然语言启动学习流"],
      ["agents", "Agents", "配置用户自己的 Agent"],
      ["ops", "系统", "检查运行状态和人工介入"],
      ["plugins", "插件", "查看扩展生态"],
      ["branches", "分支", "保持主干干净可发布"]
    ],
    titles: {
      learn: "学习工作台",
      agents: "Agent 控制台",
      ops: "系统运行",
      plugins: "插件生态",
      branches: "分支指挥中心"
    },
    runway: {
      agent: "Agent 通道",
      learning: "学习通道",
      stack: "全栈通道",
      extension: "扩展通道",
      routed: "已路由 Provider",
      needsDefault: "需要默认 Provider",
      providers: "个 Provider 已注册",
      idle: "空闲",
      startSession: "开始一次学习",
      langgraph: "LangGraph 可用",
      alphaExecutor: "Alpha 执行器",
      plugins: "个插件",
      boundaries: "个集成边界"
    },
    command: {
      eyebrow: "自然语言入口",
      title: "告诉 Study Anything 你想学什么",
      startPlaceholder:
        "粘贴一段材料，或直接说：帮我围绕这段内容生成带出处的测验并评估掌握度。",
      answerPlaceholder: "直接用自然语言回答当前题目，Study Anything 会按来源和评分规则评估。",
      start: "开始学习流",
      submit: "提交自然语言回答",
      demo: "使用右侧材料开始",
      resume: "继续运行",
      discard: "丢弃"
    },
    source: {
      input: "材料",
      title: "阅读来源",
      titleLabel: "标题",
      reference: "来源引用",
      text: "材料正文",
      linked: "已链接",
      missing: "缺少引用",
      words: "词",
      chars: "字符",
      verified: "已验证",
      localDraft: "本地草稿"
    },
    flow: {
      workflow: "流程",
      noSession: "暂无会话",
      steps: ["初始化", "规划", "验证", "测验", "评分", "掌握", "综合", "记录", "孵化"],
      quiz: "来源绑定测验",
      emptyTitle: "先用自然语言或材料开始。",
      emptyBody: "系统会创建会话、绑定来源、生成测验，并等待你的回答。",
      resolve: "解决",
      mastery: "掌握度与事件",
      evidence: "证据",
      bloom: "Bloom",
      latestScore: "最新得分",
      updated: "更新",
      never: "尚未更新",
      none: "无",
      eventTimeline: "事件时间线",
      noEvents: "暂无事件"
    },
    readiness: {
      eyebrow: "商业化距离",
      title: "商业化就绪度",
      estimate: "约 35%",
      note: "当前更像可公开 Alpha，不是可收费 SaaS。",
      strengths: "已完成：开源基础、Docker 栈、BYO Agent、学习闭环、插件雏形、CI。",
      gaps: "缺口：账户/权限、加密同步、支付、团队空间、插件市场、可观测 SLA、规模化安全审计。"
    },
    agentView: {
      byoa: "用户自带 Agent",
      setup: "Provider 配置",
      noKeys: "不保存模型密钥",
      providerKind: "Provider 类型",
      localHttp: "本地 HTTP Agent",
      fakeDemo: "Fake demo agent",
      cli: "CLI agent adapter",
      mcp: "MCP agent adapter",
      label: "名称",
      endpoint: "Endpoint",
      save: "保存默认配置",
      testSaved: "测试已保存",
      registry: "注册表",
      defaults: "Providers 与默认能力",
      enabled: " 个启用",
      none: "还没有配置 Provider。",
      capabilityDefaults: "能力默认路由",
      select: "选择",
      test: "测试",
      unset: "未设置",
      local: "local"
    },
    opsView: {
      runtime: "运行时",
      systemHealth: "系统健康",
      version: "版本",
      sessions: "会话",
      hitl: "人工介入",
      store: "存储",
      langgraph: "LangGraph",
      plugins: "插件",
      available: "可用",
      alphaExecutor: "Alpha 执行器",
      noDataDir: "未报告数据目录。",
      boundaries: "边界",
      integrationMatrix: "集成矩阵",
      humanReview: "人工审核",
      openInterrupts: "开放中断",
      noHitl: "没有人工介入任务。"
    },
    pluginsView: {
      extensions: "扩展",
      registry: "插件注册表",
      discovered: " 个已发现",
      none: "没有发现插件。"
    },
    branchView: {
      eyebrow: "OSS 上线流",
      title: "主干保持可发布，实验进入分支。",
      lanes: [
        ["main", "受保护主干", "可发布代码、绿色检查、公开标签。"],
        ["codex/ui-*", "UI 工作分支", "多分区前端改动和视觉 QA。"],
        ["feature/*", "产品功能", "每个 PR 一个可交付行为。"],
        ["fix/*", "缺陷修复", "小补丁和聚焦测试。"],
        ["docs/*", "文档通道", "开源指南、发布说明和架构文档。"],
        ["dependabot/*", "依赖通道", "React、Vite、Actions 分组升级。"],
        ["release/v*", "发布通道", "公开标签前的短期稳定分支。"]
      ],
      gates: "必需检查",
      uiBranch: "UI 分支",
      dependencyRule: "依赖规则",
      gateValue: "api-tests / web-build / compose-smoke",
      uiValue: "review 前保持 draft PR",
      dependencyValue: "peer 依赖分组升级"
    },
    loading: {
      start: "正在启动学习流",
      load: "正在加载会话",
      saveAgent: "正在保存 Agent Provider",
      testAgent: "正在测试 Agent",
      submit: "正在提交回答",
      resume: "正在继续运行",
      discard: "正在丢弃会话",
      hitl: "正在解决人工介入任务"
    }
  },
  en: {
    branch: "Branch: codex/ui-dashboard-foundation",
    selfHost: "Self-host Alpha",
    recentSessions: "Recent Sessions",
    refresh: "Refresh",
    agentReady: "Agent ready",
    agentSetupNeeded: "Agent setup needed",
    noSessions: "No saved sessions yet.",
    nav: [
      ["learn", "Learn", "Start from natural language"],
      ["agents", "Agents", "Configure Bring Your Own Agent"],
      ["ops", "System", "Inspect runtime health and HITL"],
      ["plugins", "Plugins", "Review extension surfaces"],
      ["branches", "Branches", "Keep main clean and shippable"]
    ],
    titles: {
      learn: "Learning Workspace",
      agents: "Agent Control Plane",
      ops: "System Operations",
      plugins: "Plugin Ecosystem",
      branches: "Branch Command Center"
    },
    runway: {
      agent: "Agent Lane",
      learning: "Learning Lane",
      stack: "Stack Lane",
      extension: "Extension Lane",
      routed: "Provider routed",
      needsDefault: "Needs default",
      providers: " providers registered",
      idle: "Idle",
      startSession: "start a session",
      langgraph: "LangGraph available",
      alphaExecutor: "alpha executor",
      plugins: " plugins",
      boundaries: " integration boundaries"
    },
    command: {
      eyebrow: "Natural language entry",
      title: "Tell Study Anything what you want to learn",
      startPlaceholder: "Paste source text, or ask for a source-bound quiz and mastery evaluation.",
      answerPlaceholder: "Answer the current question in natural language. Study Anything will grade it against the source.",
      start: "Start learning flow",
      submit: "Submit natural answer",
      demo: "Start from source",
      resume: "Resume",
      discard: "Discard"
    },
    source: {
      input: "Input",
      title: "Reading Source",
      titleLabel: "Title",
      reference: "Source reference",
      text: "Source text",
      linked: "linked",
      missing: "missing",
      words: "words",
      chars: "chars",
      verified: "verified",
      localDraft: "local draft"
    },
    flow: {
      workflow: "Workflow",
      noSession: "No active session",
      steps: ["Initialize", "Architect", "Verify", "Quiz", "Grade", "Mastery", "Synthesize", "Scribe", "Incubate"],
      quiz: "Source-bound quiz",
      emptyTitle: "Start with natural language or a reading source.",
      emptyBody: "The system creates a session, binds the source, generates a quiz, and waits for an answer.",
      resolve: "Resolve",
      mastery: "Mastery And Events",
      evidence: "Evidence",
      bloom: "Bloom",
      latestScore: "Latest score",
      updated: "Updated",
      never: "Never",
      none: "none",
      eventTimeline: "Event Timeline",
      noEvents: "No events yet."
    },
    readiness: {
      eyebrow: "Commercial distance",
      title: "Commercial readiness",
      estimate: "About 35%",
      note: "This is a public Alpha foundation, not a paid SaaS yet.",
      strengths: "Done: OSS base, Docker stack, BYO Agent, learning loop, plugin seed, CI.",
      gaps: "Gaps: accounts, permissions, encrypted sync, billing, team spaces, marketplace, observability SLA, security audit."
    },
    agentView: {
      byoa: "Bring Your Own Agent",
      setup: "Provider Setup",
      noKeys: "No model keys stored",
      providerKind: "Provider kind",
      localHttp: "Local HTTP Agent",
      fakeDemo: "Fake demo agent",
      cli: "CLI agent adapter",
      mcp: "MCP agent adapter",
      label: "Label",
      endpoint: "Endpoint",
      save: "Save defaults",
      testSaved: "Test saved",
      registry: "Registry",
      defaults: "Providers And Defaults",
      enabled: " enabled",
      none: "No providers configured.",
      capabilityDefaults: "Capability defaults",
      select: "Select",
      test: "Test",
      unset: "unset",
      local: "local"
    },
    opsView: {
      runtime: "Runtime",
      systemHealth: "System Health",
      version: "Version",
      sessions: "Sessions",
      hitl: "HITL",
      store: "Store",
      langgraph: "LangGraph",
      plugins: "Plugins",
      available: "available",
      alphaExecutor: "alpha executor",
      noDataDir: "No data directory reported.",
      boundaries: "Boundaries",
      integrationMatrix: "Integration Matrix",
      humanReview: "Human Review",
      openInterrupts: "Open Interrupts",
      noHitl: "No HITL interrupts."
    },
    pluginsView: {
      extensions: "Extensions",
      registry: "Plugin Registry",
      discovered: " discovered",
      none: "No plugins discovered."
    },
    branchView: {
      eyebrow: "OSS Launch Flow",
      title: "Main stays clean; experiments travel by branch.",
      lanes: [
        ["main", "Protected trunk", "Release-ready code, green checks, public tags."],
        ["codex/ui-*", "UI worktree", "Multi-zone frontend changes and visual QA."],
        ["feature/*", "Product feature", "One shippable behavior change per PR."],
        ["fix/*", "Regression fix", "Small patches with focused tests."],
        ["docs/*", "Docs lane", "OSS guides, release notes, and architecture docs."],
        ["dependabot/*", "Dependency lane", "Grouped React, Vite, and Actions updates."],
        ["release/v*", "Release lane", "Short stabilization branch before a public tag."]
      ],
      gates: "Required gates",
      uiBranch: "UI branch",
      dependencyRule: "Dependency rule",
      gateValue: "api-tests / web-build / compose-smoke",
      uiValue: "draft PR until reviewed",
      dependencyValue: "group peer updates"
    },
    loading: {
      start: "Starting learning flow",
      load: "Loading session",
      saveAgent: "Saving agent provider",
      testAgent: "Testing agent",
      submit: "Submitting answer",
      resume: "Resuming workflow",
      discard: "Discarding session",
      hitl: "Resolving HITL"
    }
  }
} as const;

type Copy = (typeof COPY)[Locale];

const CAPABILITIES = [
  "quiz.generate",
  "answer.grade",
  "insight.synthesize",
  "source.verify",
  "memory.retrieve",
  "embedding.create"
];

const WORKFLOW_STEPS = [
  ["initialize_session", "Initialize"],
  ["architect_node", "Architect"],
  ["gap_filler", "Verify"],
  ["quiz_generator", "Quiz"],
  ["quiz_grader", "Grade"],
  ["mastery_evaluator", "Mastery"],
  ["synthesist_node", "Synthesize"],
  ["scribe_node", "Scribe"],
  ["incubation_detector", "Incubate"]
];

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

function shortId(value: string, size = 8) {
  return value.slice(0, size);
}

function formatTime(value?: string) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    day: "numeric"
  }).format(new Date(value));
}

function wordCount(value: string) {
  const words = value.trim().split(/\s+/).filter(Boolean);
  return words.length;
}

function eventAgent(event: StudyEvent) {
  return event.payload?.agent ?? event.payload?.agents?.[0];
}

function toneForStatus(status: string) {
  if (["ok", "ready", "valid", "completed", "public", "available", "enabled"].includes(status)) return "good";
  if (["pending", "docs_only", "skipped"].includes(status)) return "warn";
  if (["error", "invalid", "failed"].includes(status)) return "bad";
  return "neutral";
}

function App() {
  const [activeView, setActiveView] = useState<ViewKey>("learn");
  const [locale, setLocale] = useState<Locale>("zh");
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [plugins, setPlugins] = useState<PluginStatus[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [hitlTasks, setHitlTasks] = useState<HitlInterrupt[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [title, setTitle] = useState("Asymptotic Theory Reading");
  const [reference, setReference] = useState("demo://reading/asymptotic-theory");
  const [text, setText] = useState(
    "A precise learning system should bind every generated question to a source, grade answers with a rubric, and update mastery only when evidence supports the change."
  );
  const [answer, setAnswer] = useState("");
  const [providerKind, setProviderKind] = useState("http_agent");
  const [providerLabel, setProviderLabel] = useState("Local HTTP Agent");
  const [providerEndpoint, setProviderEndpoint] = useState("http://127.0.0.1:8787");
  const [savedProviderId, setSavedProviderId] = useState<string | null>(null);
  const [agentTest, setAgentTest] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const copy = COPY[locale];
  const [command, setCommand] = useState("");

  const answeredIds = useMemo(() => new Set(session?.answers.map((item) => item.item_id) ?? []), [session]);
  const activeQuiz = session?.quiz_items.find((item) => !answeredIds.has(item.item_id)) ?? session?.quiz_items[0];
  const latestGrade = session?.grading_results[session.grading_results.length - 1];
  const openInterrupts = session?.hitl_interrupts.filter((item) => item.status === "open") ?? [];
  const readyProviders = agentStatus?.providers.filter((provider) => provider.enabled) ?? [];
  const sourceStats = {
    words: wordCount(text),
    chars: text.length,
    reference: reference.trim() ? "linked" : "missing"
  };

  async function runTask<T>(label: string, task: () => Promise<T>) {
    setLoading(label);
    setError(null);
    try {
      return await task();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return null;
    } finally {
      setLoading(null);
    }
  }

  async function refreshAgents() {
    setAgentStatus(await api<AgentStatus>("/v1/agents/status"));
  }

  async function refreshOps() {
    const [status, pluginList, integrationList, hitlList, sessionList] = await Promise.all([
      api<SystemStatus>("/v1/system/status"),
      api<PluginStatus[]>("/v1/plugins"),
      api<IntegrationStatus[]>("/v1/system/integrations"),
      api<HitlInterrupt[]>("/v1/hitl"),
      api<Session[]>("/v1/sessions")
    ]);
    setSystemStatus(status);
    setPlugins(pluginList);
    setIntegrations(integrationList);
    setHitlTasks(hitlList);
    setSessions(sessionList);
  }

  async function refreshAll(nextSessionId = session?.session_id) {
    await Promise.all([refreshAgents(), refreshOps()]);
    if (nextSessionId) {
      setSession(await api<Session>(`/v1/sessions/${nextSessionId}`));
    }
  }

  async function startLearningFlow(source: { title: string; reference: string; text: string }) {
    await runTask(copy.loading.start, async () => {
      const created = await api<Session>("/v1/sessions", {
        method: "POST",
        body: JSON.stringify({ user_id: "local-user", track: "ACADEMIC", use_demo_agent: true })
      });
      const withReading = await api<Session>(`/v1/sessions/${created.session_id}/reading`, {
        method: "POST",
        body: JSON.stringify({ source_type: "local_text", ...source })
      });
      const running = await api<Session>(`/v1/sessions/${withReading.session_id}/run`, {
        method: "POST"
      });
      setSession(running);
      setAnswer("");
      await refreshAll(running.session_id);
    });
  }

  async function startDemo() {
    await startLearningFlow({ reference, title, text });
  }

  async function runNaturalCommand() {
    const value = command.trim();
    if (!value) return;
    if (session && activeQuiz) {
      await submitAnswerText(value);
      setCommand("");
      return;
    }
    const commandTitle = value.length > 42 ? `${value.slice(0, 42)}...` : value;
    await startLearningFlow({
      title: commandTitle || title,
      reference: reference.trim() || "natural://study-anything/session",
      text: value.length > 24 ? value : text
    });
    setCommand("");
  }

  async function loadSession(sessionId: string) {
    await runTask(copy.loading.load, async () => {
      setSession(await api<Session>(`/v1/sessions/${sessionId}`));
      setActiveView("learn");
    });
  }

  async function addProvider() {
    await runTask(copy.loading.saveAgent, async () => {
      const provider = await api<ProviderStatus>("/v1/agents/providers", {
        method: "POST",
        body: JSON.stringify({
          kind: providerKind,
          label: providerLabel,
          endpoint: providerKind === "http_agent" ? providerEndpoint : undefined,
          capabilities: CAPABILITIES,
          metadata: { configured_from: "web-ui", secret_storage: "user-agent-only" }
        })
      });
      await Promise.all(
        CAPABILITIES.map((capability) =>
          api<AgentStatus>("/v1/agents/defaults", {
            method: "POST",
            body: JSON.stringify({
              user_id: "local-user",
              capability,
              provider_id: provider.provider_id
            })
          })
        )
      );
      setSavedProviderId(provider.provider_id);
      setAgentTest(null);
      await refreshAll();
    });
  }

  async function testSavedAgent(providerId = savedProviderId) {
    if (!providerId) return;
    await runTask(copy.loading.testAgent, async () => {
      const health = await api<{ status: string; message: string }>("/v1/agents/test", {
        method: "POST",
        body: JSON.stringify({ provider_id: providerId })
      });
      setAgentTest(`${health.status}: ${health.message}`);
      await refreshAgents();
    });
  }

  async function submitAnswerText(answerText: string) {
    if (!session || !activeQuiz) return;
    await runTask(copy.loading.submit, async () => {
      const updated = await api<Session>(`/v1/sessions/${session.session_id}/answers`, {
        method: "POST",
        body: JSON.stringify({ answers: { [activeQuiz.item_id]: answerText } })
      });
      setSession(updated);
      setAnswer("");
      await refreshAll(updated.session_id);
    });
  }

  async function submitAnswer() {
    await submitAnswerText(answer);
  }

  async function resume() {
    if (!session) return;
    await runTask(copy.loading.resume, async () => {
      const updated = await api<Session>(`/v1/sessions/${session.session_id}/resume`, {
        method: "POST"
      });
      setSession(updated);
      await refreshAll(updated.session_id);
    });
  }

  async function discard() {
    if (!session) return;
    await runTask(copy.loading.discard, async () => {
      const updated = await api<Session>(`/v1/sessions/${session.session_id}/discard`, {
        method: "POST"
      });
      setSession(updated);
      await refreshAll(updated.session_id);
    });
  }

  async function resolveHitl(taskId: string) {
    if (!session) return;
    await runTask(copy.loading.hitl, async () => {
      const updated = await api<Session>(`/v1/hitl/${taskId}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          session_id: session.session_id,
          payload: { resolved_from: "web-ui" }
        })
      });
      setSession(updated);
      await refreshAll(updated.session_id);
    });
  }

  useEffect(() => {
    refreshAll().catch((err) => setError(String(err)));
  }, []);

  return (
    <main className="appShell">
      <aside className="sidebar" aria-label="Workspace">
        <div className="brandBlock">
          <div className="brandMark">SA</div>
          <div>
            <p className="eyebrow">{copy.selfHost}</p>
            <h1>Study Anything</h1>
          </div>
        </div>

        <nav className="navList" aria-label="Primary">
          {copy.nav.map(([key, label, helper]) => (
            <button
              className={activeView === key ? "navItem active" : "navItem"}
              key={key}
              onClick={() => setActiveView(key as ViewKey)}
            >
              <span>{label}</span>
              <small>{helper}</small>
            </button>
          ))}
        </nav>

        <section className="sessionRail" aria-label="Recent sessions">
          <div className="sectionTitle">
            <h2>{copy.recentSessions}</h2>
            <button className="iconButton" onClick={() => refreshAll()} title={copy.refresh}>
              R
            </button>
          </div>
          <div className="sessionList">
            {sessions.slice(0, 7).map((item) => (
              <button
                className={session?.session_id === item.session_id ? "sessionItem active" : "sessionItem"}
                key={item.session_id}
                onClick={() => loadSession(item.session_id)}
              >
                <span>{item.source?.title ?? item.track}</span>
                <small>
                  {item.stage} / {shortId(item.session_id)}
                </small>
              </button>
            ))}
            {sessions.length === 0 && <p className="emptyState">{copy.noSessions}</p>}
          </div>
        </section>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">{copy.branch}</p>
            <h2>{viewTitle(activeView, copy)}</h2>
          </div>
          <div className="topbarActions">
            <div className="segmentedControl" aria-label="Language">
              <button className={locale === "zh" ? "active" : ""} onClick={() => setLocale("zh")}>
                中文
              </button>
              <button className={locale === "en" ? "active" : ""} onClick={() => setLocale("en")}>
                EN
              </button>
            </div>
            <span className={`statusPill ${agentStatus?.defaults["quiz.generate"] ? "good" : "warn"}`}>
              {agentStatus?.defaults["quiz.generate"] ? copy.agentReady : copy.agentSetupNeeded}
            </span>
            <button onClick={() => refreshAll()} disabled={Boolean(loading)}>
              {copy.refresh}
            </button>
          </div>
        </header>

        {error && <section className="notice bad">{error}</section>}
        {loading && <section className="notice neutral">{loading}</section>}

        <Runway
          agentStatus={agentStatus}
          copy={copy}
          integrations={integrations}
          plugins={plugins}
          session={session}
          systemStatus={systemStatus}
        />

        {activeView === "learn" && (
          <LearnView
            activeQuiz={activeQuiz}
            answer={answer}
            command={command}
            copy={copy}
            discard={discard}
            latestGrade={latestGrade}
            openInterrupts={openInterrupts}
            reference={reference}
            resolveHitl={resolveHitl}
            resume={resume}
            runNaturalCommand={runNaturalCommand}
            session={session}
            setAnswer={setAnswer}
            setCommand={setCommand}
            setReference={setReference}
            setText={setText}
            setTitle={setTitle}
            sourceStats={sourceStats}
            startDemo={startDemo}
            submitAnswer={submitAnswer}
            text={text}
            title={title}
          />
        )}

        {activeView === "agents" && (
          <AgentView
            agentStatus={agentStatus}
            agentTest={agentTest}
            copy={copy}
            providerEndpoint={providerEndpoint}
            providerKind={providerKind}
            providerLabel={providerLabel}
            readyProviders={readyProviders}
            savedProviderId={savedProviderId}
            setProviderEndpoint={setProviderEndpoint}
            setProviderKind={setProviderKind}
            setProviderLabel={setProviderLabel}
            setSavedProviderId={setSavedProviderId}
            saveProvider={addProvider}
            testProvider={testSavedAgent}
          />
        )}

        {activeView === "ops" && (
          <OpsView
            copy={copy}
            hitlTasks={hitlTasks}
            integrations={integrations}
            session={session}
            systemStatus={systemStatus}
          />
        )}

        {activeView === "plugins" && <PluginView copy={copy} plugins={plugins} />}

        {activeView === "branches" && <BranchView copy={copy} />}
      </section>
    </main>
  );
}

function viewTitle(view: ViewKey, copy: Copy) {
  return copy.titles[view];
}

function Runway({
  agentStatus,
  copy,
  integrations,
  plugins,
  session,
  systemStatus
}: {
  agentStatus: AgentStatus | null;
  copy: Copy;
  integrations: IntegrationStatus[];
  plugins: PluginStatus[];
  session: Session | null;
  systemStatus: SystemStatus | null;
}) {
  const agentReady = Boolean(agentStatus?.defaults["quiz.generate"]);
  const composeReady = integrations.some((item) => item.name.toLowerCase().includes("postgres") && item.status === "available");
  return (
    <section className="runwayGrid" aria-label="Workspace lanes">
      <article className="runwayCard">
        <span className={`statusDot ${agentReady ? "good" : "warn"}`} />
        <div>
          <p className="eyebrow">{copy.runway.agent}</p>
          <strong>{agentReady ? copy.runway.routed : copy.runway.needsDefault}</strong>
          <small>
            {agentStatus?.providers.length ?? 0}
            {copy.runway.providers}
          </small>
        </div>
      </article>
      <article className="runwayCard">
        <span className={`statusDot ${session ? "good" : "neutral"}`} />
        <div>
          <p className="eyebrow">{copy.runway.learning}</p>
          <strong>{session?.stage ?? copy.runway.idle}</strong>
          <small>{session ? shortId(session.session_id) : copy.runway.startSession}</small>
        </div>
      </article>
      <article className="runwayCard">
        <span className={`statusDot ${composeReady || systemStatus?.status === "ok" ? "good" : "warn"}`} />
        <div>
          <p className="eyebrow">{copy.runway.stack}</p>
          <strong>{systemStatus?.session_store ?? "unknown store"}</strong>
          <small>{systemStatus?.langgraph_available ? copy.runway.langgraph : copy.runway.alphaExecutor}</small>
        </div>
      </article>
      <article className="runwayCard">
        <span className={`statusDot ${plugins.length ? "good" : "neutral"}`} />
        <div>
          <p className="eyebrow">{copy.runway.extension}</p>
          <strong>
            {plugins.length}
            {copy.runway.plugins}
          </strong>
          <small>
            {integrations.length}
            {copy.runway.boundaries}
          </small>
        </div>
      </article>
    </section>
  );
}

function LearnView(props: {
  activeQuiz?: QuizItem;
  answer: string;
  command: string;
  copy: Copy;
  discard: () => void;
  latestGrade?: GradingResult;
  openInterrupts: HitlInterrupt[];
  reference: string;
  resolveHitl: (taskId: string) => void;
  resume: () => void;
  runNaturalCommand: () => void;
  session: Session | null;
  setAnswer: (value: string) => void;
  setCommand: (value: string) => void;
  setReference: (value: string) => void;
  setText: (value: string) => void;
  setTitle: (value: string) => void;
  sourceStats: { words: number; chars: number; reference: string };
  startDemo: () => void;
  submitAnswer: () => void;
  text: string;
  title: string;
}) {
  const {
    activeQuiz,
    answer,
    command,
    copy,
    discard,
    latestGrade,
    openInterrupts,
    reference,
    resolveHitl,
    resume,
    runNaturalCommand,
    session,
    setAnswer,
    setCommand,
    setReference,
    setText,
    setTitle,
    sourceStats,
    startDemo,
    submitAnswer,
    text,
    title
  } = props;

  return (
    <div className="conversationGrid">
      <section className="toolPanel conversationPanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">{copy.command.eyebrow}</p>
            <h3>{copy.command.title}</h3>
          </div>
          <span className="idTag">{session ? shortId(session.session_id) : "idle"}</span>
        </div>

        {activeQuiz && (
          <div className="quizPrompt">
            <p className="eyebrow">{copy.flow.quiz}</p>
            <h4>{activeQuiz.prompt}</h4>
            <p>{activeQuiz.rubric}</p>
          </div>
        )}

        <textarea
          className="commandInput"
          value={command}
          onChange={(event) => {
            setCommand(event.target.value);
            if (activeQuiz) setAnswer(event.target.value);
          }}
          placeholder={activeQuiz ? copy.command.answerPlaceholder : copy.command.startPlaceholder}
        />
        <div className="actionRow commandActions">
          <button className="primary" onClick={runNaturalCommand}>
            {activeQuiz ? copy.command.submit : copy.command.start}
          </button>
          <button onClick={startDemo}>{copy.command.demo}</button>
          <button onClick={resume} disabled={!session}>
            {copy.command.resume}
          </button>
          <button onClick={discard} disabled={!session}>
            {copy.command.discard}
          </button>
        </div>

        {openInterrupts.length > 0 && (
          <div className="notice warn">
            {openInterrupts.map((item) => (
              <div className="interruptRow" key={item.task_id}>
                <span>{item.message}</span>
                <button onClick={() => resolveHitl(item.task_id)}>{copy.flow.resolve}</button>
              </div>
            ))}
          </div>
        )}

        {!activeQuiz && (
          <div className="emptyPanel">
            <h4>{copy.flow.emptyTitle}</h4>
            <p>{copy.flow.emptyBody}</p>
          </div>
        )}

        <section className="workflowPanel">
          <div className="panelHeading">
            <div>
              <p className="eyebrow">{copy.flow.workflow}</p>
              <h3>{session?.stage ?? copy.flow.noSession}</h3>
            </div>
          </div>
          <div className="workflowMap">
            {WORKFLOW_STEPS.map(([node, label], index) => {
              const completed = session?.events.some((event) => event.node === node);
              return (
                <div className={completed ? "workflowStep done" : "workflowStep"} key={node}>
                  <span>{index + 1}</span>
                  <strong>{copy.flow.steps[index] ?? label}</strong>
                  <small>{node}</small>
                </div>
              );
            })}
          </div>
        </section>
      </section>

      <aside className="contextRail">
        <section className="toolPanel sourcePanel">
          <div className="panelHeading">
            <div>
              <p className="eyebrow">{copy.source.input}</p>
              <h3>{copy.source.title}</h3>
            </div>
            <span className={`statusPill ${sourceStats.reference === "linked" ? "good" : "warn"}`}>
              {sourceStats.reference === "linked" ? copy.source.linked : copy.source.missing}
            </span>
          </div>
          <label>
            {copy.source.titleLabel}
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            {copy.source.reference}
            <input value={reference} onChange={(event) => setReference(event.target.value)} />
          </label>
          <label>
            {copy.source.text}
            <textarea className="sourceText" value={text} onChange={(event) => setText(event.target.value)} />
          </label>
          <div className="metricStrip">
            <span>
              {sourceStats.words} {copy.source.words}
            </span>
            <span>
              {sourceStats.chars} {copy.source.chars}
            </span>
            <span>{session?.source?.verified ? copy.source.verified : copy.source.localDraft}</span>
          </div>
        </section>

        <section className="toolPanel evidencePanel">
          <div className="panelHeading">
            <div>
              <p className="eyebrow">{copy.flow.evidence}</p>
              <h3>{copy.flow.mastery}</h3>
            </div>
            <div className="masteryBadge">{session?.mastery.level.toFixed(1) ?? "0.0"}</div>
          </div>
          <dl className="definitionGrid">
            <dt>{copy.flow.bloom}</dt>
            <dd>{session?.mastery.bloom ?? "remember"}</dd>
            <dt>{copy.flow.latestScore}</dt>
            <dd>{latestGrade ? latestGrade.score.toFixed(2) : copy.flow.none}</dd>
            <dt>{copy.flow.updated}</dt>
            <dd>{session?.updated_at ? formatTime(session.updated_at) : copy.flow.never}</dd>
          </dl>
          {latestGrade && <p className="feedback">{latestGrade.feedback}</p>}
          <EventList events={session?.events ?? []} title={copy.flow.eventTimeline} emptyLabel={copy.flow.noEvents} />
        </section>

        <section className="toolPanel readinessPanel">
          <div className="panelHeading">
            <div>
              <p className="eyebrow">{copy.readiness.eyebrow}</p>
              <h3>{copy.readiness.title}</h3>
            </div>
            <strong className="readinessScore">{copy.readiness.estimate}</strong>
          </div>
          <div className="readinessBar">
            <span />
          </div>
          <p>{copy.readiness.note}</p>
          <small>{copy.readiness.strengths}</small>
          <small>{copy.readiness.gaps}</small>
        </section>
      </aside>
    </div>
  );
}

function AgentView(props: {
  agentStatus: AgentStatus | null;
  agentTest: string | null;
  copy: Copy;
  providerEndpoint: string;
  providerKind: string;
  providerLabel: string;
  readyProviders: ProviderStatus[];
  savedProviderId: string | null;
  saveProvider: () => void;
  setProviderEndpoint: (value: string) => void;
  setProviderKind: (value: string) => void;
  setProviderLabel: (value: string) => void;
  setSavedProviderId: (value: string | null) => void;
  testProvider: (providerId?: string | null) => void;
}) {
  const {
    agentStatus,
    agentTest,
    copy,
    providerEndpoint,
    providerKind,
    providerLabel,
    readyProviders,
    savedProviderId,
    saveProvider,
    setProviderEndpoint,
    setProviderKind,
    setProviderLabel,
    setSavedProviderId,
    testProvider
  } = props;

  return (
    <div className="splitGrid">
      <section className="toolPanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">{copy.agentView.byoa}</p>
            <h3>{copy.agentView.setup}</h3>
          </div>
          <span className="statusPill neutral">{copy.agentView.noKeys}</span>
        </div>
        <label>
          {copy.agentView.providerKind}
          <select value={providerKind} onChange={(event) => setProviderKind(event.target.value)}>
            <option value="http_agent">{copy.agentView.localHttp}</option>
            <option value="fake_agent">{copy.agentView.fakeDemo}</option>
            <option value="cli_agent">{copy.agentView.cli}</option>
            <option value="mcp_agent">{copy.agentView.mcp}</option>
          </select>
        </label>
        <label>
          {copy.agentView.label}
          <input value={providerLabel} onChange={(event) => setProviderLabel(event.target.value)} />
        </label>
        <label>
          {copy.agentView.endpoint}
          <input
            disabled={providerKind !== "http_agent"}
            value={providerEndpoint}
            onChange={(event) => setProviderEndpoint(event.target.value)}
            placeholder="http://127.0.0.1:8787"
          />
        </label>
        <div className="capabilityGrid">
          {CAPABILITIES.map((capability) => (
            <span key={capability}>{capability}</span>
          ))}
        </div>
        <div className="actionRow">
          <button className="primary" onClick={saveProvider}>
            {copy.agentView.save}
          </button>
          <button disabled={!savedProviderId} onClick={() => testProvider(savedProviderId)}>
            {copy.agentView.testSaved}
          </button>
        </div>
        {agentTest && <p className="feedback">{agentTest}</p>}
      </section>

      <section className="toolPanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">{copy.agentView.registry}</p>
            <h3>{copy.agentView.defaults}</h3>
          </div>
          <span className="idTag">
            {readyProviders.length}
            {copy.agentView.enabled}
          </span>
        </div>
        <div className="providerList">
          {agentStatus?.providers.map((provider) => (
            <div className="providerRow" key={provider.provider_id}>
              <div>
                <strong>{provider.label}</strong>
                <small>
                  {provider.kind} / {provider.endpoint || copy.agentView.local}
                </small>
              </div>
              <div className="providerActions">
                <button onClick={() => setSavedProviderId(provider.provider_id)}>{copy.agentView.select}</button>
                <button onClick={() => testProvider(provider.provider_id)}>{copy.agentView.test}</button>
              </div>
            </div>
          ))}
          {agentStatus?.providers.length === 0 && <p className="emptyState">{copy.agentView.none}</p>}
        </div>
        <h4>{copy.agentView.capabilityDefaults}</h4>
        <dl className="definitionGrid">
          {CAPABILITIES.map((capability) => (
            <React.Fragment key={capability}>
              <dt>{capability}</dt>
              <dd>
                {agentStatus?.defaults[capability]
                  ? shortId(String(agentStatus.defaults[capability]))
                  : copy.agentView.unset}
              </dd>
            </React.Fragment>
          ))}
        </dl>
      </section>
    </div>
  );
}

function OpsView(props: {
  copy: Copy;
  hitlTasks: HitlInterrupt[];
  integrations: IntegrationStatus[];
  session: Session | null;
  systemStatus: SystemStatus | null;
}) {
  const { copy, hitlTasks, integrations, session, systemStatus } = props;
  return (
    <div className="opsLayout">
      <section className="toolPanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">{copy.opsView.runtime}</p>
            <h3>{copy.opsView.systemHealth}</h3>
          </div>
          <span className={`statusPill ${toneForStatus(systemStatus?.status ?? "unknown")}`}>
            {systemStatus?.status ?? "unknown"}
          </span>
        </div>
        <div className="statGrid">
          <Stat label={copy.opsView.version} value={systemStatus?.version ?? "unknown"} />
          <Stat label={copy.opsView.sessions} value={systemStatus?.session_count ?? 0} />
          <Stat label={copy.opsView.hitl} value={systemStatus?.open_hitl_count ?? 0} />
          <Stat label={copy.opsView.store} value={systemStatus?.session_store ?? "unknown"} />
          <Stat
            label={copy.opsView.langgraph}
            value={systemStatus?.langgraph_available ? copy.opsView.available : copy.opsView.alphaExecutor}
          />
          <Stat label={copy.opsView.plugins} value={systemStatus?.plugin_count ?? 0} />
        </div>
        <p className="pathText">{systemStatus?.data_dir ?? copy.opsView.noDataDir}</p>
      </section>

      <section className="toolPanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">{copy.opsView.boundaries}</p>
            <h3>{copy.opsView.integrationMatrix}</h3>
          </div>
        </div>
        <div className="integrationTable">
          {integrations.map((item) => (
            <div className="integrationRow" key={item.name}>
              <strong>{item.name}</strong>
              <span>{item.category}</span>
              <span className={`statusPill ${toneForStatus(item.status)}`}>{item.status}</span>
              <small>{item.next_step}</small>
            </div>
          ))}
        </div>
      </section>

      <section className="toolPanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">{copy.opsView.humanReview}</p>
            <h3>{copy.opsView.openInterrupts}</h3>
          </div>
          <span className="idTag">{hitlTasks.filter((item) => item.status === "open").length}</span>
        </div>
        <div className="hitlList">
          {hitlTasks.map((item) => (
            <div className="hitlRow" key={item.task_id}>
              <strong>{item.kind}</strong>
              <p>{item.message}</p>
              <small>{item.status}</small>
            </div>
          ))}
          {hitlTasks.length === 0 && <p className="emptyState">{copy.opsView.noHitl}</p>}
        </div>
        {session && <EventList events={session.events} />}
      </section>
    </div>
  );
}

function PluginView({ copy, plugins }: { copy: Copy; plugins: PluginStatus[] }) {
  return (
    <section className="toolPanel">
      <div className="panelHeading">
        <div>
          <p className="eyebrow">{copy.pluginsView.extensions}</p>
          <h3>{copy.pluginsView.registry}</h3>
        </div>
        <span className="idTag">
          {plugins.length}
          {copy.pluginsView.discovered}
        </span>
      </div>
      <div className="pluginGrid">
        {plugins.map((plugin) => (
          <article className="pluginItem" key={plugin.path}>
            <div>
              <strong>{plugin.manifest?.name ?? plugin.path}</strong>
              <small>{plugin.manifest?.plugin_id ?? plugin.path}</small>
            </div>
            <span className={`statusPill ${toneForStatus(plugin.status)}`}>{plugin.status}</span>
            <p>{plugin.message}</p>
            <div className="capabilityGrid">
              {(plugin.manifest?.hooks ?? []).map((hook) => (
                <span key={hook}>{hook}</span>
              ))}
            </div>
          </article>
        ))}
        {plugins.length === 0 && <p className="emptyState">{copy.pluginsView.none}</p>}
      </div>
    </section>
  );
}

function BranchView({ copy }: { copy: Copy }) {
  const lanes = copy.branchView.lanes;
  return (
    <section className="branchBoard">
      <div className="branchHero">
        <div>
          <p className="eyebrow">{copy.branchView.eyebrow}</p>
          <h3>{copy.branchView.title}</h3>
        </div>
        <span className="statusPill good">codex/ui-dashboard-foundation</span>
      </div>
      <div className="branchGrid">
        {lanes.map(([name, role, note]) => (
          <article className="branchLane" key={name}>
            <span className="idTag">{name}</span>
            <strong>{role}</strong>
            <small>{note}</small>
          </article>
        ))}
      </div>
      <div className="gateGrid">
        <Stat label={copy.branchView.gates} value={copy.branchView.gateValue} />
        <Stat label={copy.branchView.uiBranch} value={copy.branchView.uiValue} />
        <Stat label={copy.branchView.dependencyRule} value={copy.branchView.dependencyValue} />
      </div>
    </section>
  );
}

function EventList({
  emptyLabel = "No events yet.",
  events,
  title = "Event Timeline"
}: {
  emptyLabel?: string;
  events: StudyEvent[];
  title?: string;
}) {
  return (
    <div className="eventList">
      <h4>{title}</h4>
      {events.slice(-9).map((event) => {
        const agent = eventAgent(event);
        return (
          <div className="eventRow" key={event.event_id}>
            <span>{formatTime(event.created_at)}</span>
            <strong>{event.type}</strong>
            <small>
              {agent?.provider_id
                ? `${event.node} / ${agent.task_type ?? "agent"} / ${shortId(agent.provider_id)}`
                : event.node}
            </small>
          </div>
        );
      })}
      {events.length === 0 && <p className="emptyState">{emptyLabel}</p>}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="statItem">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
