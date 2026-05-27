import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Locale = "zh" | "en";
type ViewKey = "learn" | "agent";

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
  reference: string;
  title: string;
  text: string;
  verified: boolean;
};

type QuizItem = {
  item_id: string;
  prompt: string;
  rubric: string;
};

type GradingResult = {
  item_id: string;
  score: number;
  feedback: string;
};

type HitlInterrupt = {
  task_id: string;
  message: string;
  status: string;
};

type Session = {
  session_id: string;
  stage: string;
  source: ReadingSource | null;
  quiz_items: QuizItem[];
  answers: Array<{ item_id: string; text: string }>;
  grading_results: GradingResult[];
  mastery: { level: number; bloom: string };
  insights: string[];
  hitl_interrupts: HitlInterrupt[];
  discarded: boolean;
  updated_at: string;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const CAPABILITIES = [
  "quiz.generate",
  "answer.grade",
  "insight.synthesize",
  "source.verify",
  "memory.retrieve",
  "embedding.create"
];

const copy = {
  zh: {
    appMode: "本地优先学习系统",
    navLearn: "学习",
    navAgent: "Agent",
    navLearnHint: "自然语言学习空间",
    navAgentHint: "连接你自己的推理系统",
    recent: "最近学习",
    emptyRecent: "还没有学习记录。",
    refresh: "刷新",
    learnTitle: "今天想学什么？",
    learnSubtitle: "粘贴材料或直接描述目标，Study Anything 会生成带来源约束的练习并追踪掌握度。",
    agentReady: "Agent 已连接",
    agentMissing: "未连接 Agent",
    inputPlaceholder: "例如：帮我学习这段关于渐近理论的材料，生成测验，并在我回答后评估掌握度。",
    answerPlaceholder: "直接回答当前问题。系统会基于材料和评分标准给出反馈。",
    start: "开始学习",
    answer: "提交回答",
    useSource: "使用右侧材料",
    newRound: "新学习",
    sourceTitle: "学习材料",
    title: "标题",
    reference: "来源",
    sourceText: "正文",
    verified: "来源已校验",
    draft: "本地草稿",
    words: "词",
    chars: "字符",
    progressTitle: "学习进度",
    mastery: "掌握度",
    score: "最新得分",
    feedback: "反馈",
    insight: "综合理解",
    noFeedback: "完成回答后会显示反馈。",
    needsReview: "需要你确认",
    resolve: "确认",
    stages: {
      idle: "准备开始",
      initialized: "已创建学习",
      awaiting_reading: "等待材料",
      reading_submitted: "理解材料",
      awaiting_answers: "等待作答",
      completed: "已完成",
      discarded: "已丢弃"
    },
    welcome: "把你要学习的内容放进输入框，或者使用右侧材料开始。",
    quizIntro: "先回答这个问题：",
    agentTitle: "连接你的 Agent",
    agentLead: "真实推理、凭证和工具都留在你自己的 Agent 中。Study Anything 只发送学习任务、校验结构化输出并记录学习状态。",
    kind: "类型",
    label: "名称",
    endpoint: "地址",
    saveAgent: "保存并设为默认",
    testAgent: "测试连接",
    configuredAgents: "已配置 Agent",
    noAgents: "还没有配置 Agent。",
    capabilities: "学习能力",
    noSecrets: "Study Anything 不保存你的推理凭证。",
    healthy: "连接正常",
    localAgent: "本地 HTTP Agent",
    fakeAgent: "演示 Agent",
    cliAgent: "CLI Agent",
    mcpAgent: "MCP Agent",
    capabilityLabels: ["生成练习", "评分反馈", "总结理解", "校验来源", "检索记忆", "创建向量"],
    loadingStart: "正在开始学习",
    loadingAnswer: "正在提交回答",
    loadingAgent: "正在保存 Agent",
    loadingTest: "正在测试连接",
    loadingRefresh: "正在刷新"
  },
  en: {
    appMode: "Local-first learning system",
    navLearn: "Learn",
    navAgent: "Agent",
    navLearnHint: "Natural-language study space",
    navAgentHint: "Connect your own reasoning system",
    recent: "Recent",
    emptyRecent: "No learning sessions yet.",
    refresh: "Refresh",
    learnTitle: "What do you want to learn today?",
    learnSubtitle: "Paste source material or describe a goal. Study Anything turns it into grounded practice and tracks mastery.",
    agentReady: "Agent connected",
    agentMissing: "Agent not connected",
    inputPlaceholder: "Example: help me study this passage, generate a quiz, and evaluate my mastery after I answer.",
    answerPlaceholder: "Answer the current question. The system will grade it against the source and rubric.",
    start: "Start learning",
    answer: "Submit answer",
    useSource: "Use source panel",
    newRound: "New study",
    sourceTitle: "Study Material",
    title: "Title",
    reference: "Source",
    sourceText: "Text",
    verified: "Source verified",
    draft: "Local draft",
    words: "words",
    chars: "chars",
    progressTitle: "Progress",
    mastery: "Mastery",
    score: "Latest score",
    feedback: "Feedback",
    insight: "Synthesis",
    noFeedback: "Feedback appears after you answer.",
    needsReview: "Needs your review",
    resolve: "Confirm",
    stages: {
      idle: "Ready",
      initialized: "Created",
      awaiting_reading: "Waiting for source",
      reading_submitted: "Reading",
      awaiting_answers: "Waiting for answer",
      completed: "Completed",
      discarded: "Discarded"
    },
    welcome: "Put learning material into the input box, or start from the source panel.",
    quizIntro: "Answer this first:",
    agentTitle: "Connect Your Agent",
    agentLead: "Real reasoning, credentials, and tools stay inside your own agent. Study Anything sends learning tasks, validates structured output, and records learning state.",
    kind: "Type",
    label: "Name",
    endpoint: "Endpoint",
    saveAgent: "Save as default",
    testAgent: "Test connection",
    configuredAgents: "Configured agents",
    noAgents: "No agents configured.",
    capabilities: "Learning capabilities",
    noSecrets: "Study Anything never stores your reasoning credentials.",
    healthy: "Connection ok",
    localAgent: "Local HTTP Agent",
    fakeAgent: "Demo Agent",
    cliAgent: "CLI Agent",
    mcpAgent: "MCP Agent",
    capabilityLabels: ["Generate practice", "Grade answers", "Synthesize", "Verify source", "Retrieve memory", "Create embeddings"],
    loadingStart: "Starting learning",
    loadingAnswer: "Submitting answer",
    loadingAgent: "Saving agent",
    loadingTest: "Testing connection",
    loadingRefresh: "Refreshing"
  }
} as const;

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

function wordCount(value: string) {
  return value.trim().split(/\s+/).filter(Boolean).length;
}

function formatTime(value?: string) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(
    new Date(value)
  );
}

function progressFor(stage?: string) {
  if (stage === "completed") return 100;
  if (stage === "awaiting_answers") return 62;
  if (stage === "reading_submitted") return 44;
  if (stage === "awaiting_reading" || stage === "initialized") return 18;
  return 0;
}

function stageLabel(stage: string | undefined, labels: Record<string, string>) {
  return labels[stage ?? "idle"] ?? stage ?? labels.idle;
}

function agentKindLabel(
  kind: string,
  labels: { localAgent: string; fakeAgent: string; cliAgent: string; mcpAgent: string }
) {
  if (kind === "http_agent") return labels.localAgent;
  if (kind === "fake_agent") return labels.fakeAgent;
  if (kind === "cli_agent") return labels.cliAgent;
  if (kind === "mcp_agent") return labels.mcpAgent;
  return labels.localAgent;
}

function App() {
  const [locale, setLocale] = useState<Locale>("zh");
  const [view, setView] = useState<ViewKey>("learn");
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [hitlTasks, setHitlTasks] = useState<HitlInterrupt[]>([]);
  const [title, setTitle] = useState("Asymptotic Theory Reading");
  const [reference, setReference] = useState("demo://reading/asymptotic-theory");
  const [sourceText, setSourceText] = useState(
    "A precise learning system should bind every generated question to a source, grade answers with a rubric, and update mastery only when evidence supports the change."
  );
  const [composer, setComposer] = useState("");
  const [providerKind, setProviderKind] = useState("http_agent");
  const [providerLabel, setProviderLabel] = useState("Local HTTP Agent");
  const [providerEndpoint, setProviderEndpoint] = useState("http://127.0.0.1:8787");
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const [agentTest, setAgentTest] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const t = copy[locale];
  const answeredIds = useMemo(() => new Set(session?.answers.map((answer) => answer.item_id) ?? []), [session]);
  const activeQuiz = session?.quiz_items.find((item) => !answeredIds.has(item.item_id)) ?? null;
  const latestGrade = session?.grading_results[session.grading_results.length - 1] ?? null;
  const agentReady = Boolean(agentStatus?.defaults["quiz.generate"]);
  const sourceStats = { words: wordCount(sourceText), chars: sourceText.length };

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

  async function refresh(currentSessionId = session?.session_id) {
    await runTask(t.loadingRefresh, async () => {
      const [agents, sessionList, hitl] = await Promise.all([
        api<AgentStatus>("/v1/agents/status"),
        api<Session[]>("/v1/sessions"),
        api<HitlInterrupt[]>("/v1/hitl")
      ]);
      setAgentStatus(agents);
      setSessions(sessionList);
      setHitlTasks(hitl);
      if (currentSessionId) {
        setSession(await api<Session>(`/v1/sessions/${currentSessionId}`));
      }
    });
  }

  async function startLearning(source: { title: string; reference: string; text: string }) {
    await runTask(t.loadingStart, async () => {
      const created = await api<Session>("/v1/sessions", {
        method: "POST",
        body: JSON.stringify({ user_id: "local-user", track: "ACADEMIC", use_demo_agent: true })
      });
      const withReading = await api<Session>(`/v1/sessions/${created.session_id}/reading`, {
        method: "POST",
        body: JSON.stringify({ source_type: "local_text", ...source })
      });
      const running = await api<Session>(`/v1/sessions/${withReading.session_id}/run`, { method: "POST" });
      setSession(running);
      setComposer("");
      await refresh(running.session_id);
    });
  }

  async function submitAnswer(text: string) {
    if (!session || !activeQuiz) return;
    await runTask(t.loadingAnswer, async () => {
      const updated = await api<Session>(`/v1/sessions/${session.session_id}/answers`, {
        method: "POST",
        body: JSON.stringify({ answers: { [activeQuiz.item_id]: text } })
      });
      setSession(updated);
      setComposer("");
      await refresh(updated.session_id);
    });
  }

  async function handleComposer() {
    const value = composer.trim();
    if (!value && !activeQuiz) {
      await startLearning({ title, reference, text: sourceText });
      return;
    }
    if (activeQuiz) {
      await submitAnswer(value);
      return;
    }
    const naturalTitle = value.length > 42 ? `${value.slice(0, 42)}...` : value || title;
    await startLearning({
      title: naturalTitle,
      reference: reference.trim() || "local://study-anything",
      text: value.length > 24 ? value : sourceText
    });
  }

  async function loadSession(sessionId: string) {
    const loaded = await runTask(t.loadingRefresh, () => api<Session>(`/v1/sessions/${sessionId}`));
    if (loaded) {
      setSession(loaded);
      setView("learn");
    }
  }

  async function saveProvider() {
    await runTask(t.loadingAgent, async () => {
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
            body: JSON.stringify({ user_id: "local-user", capability, provider_id: provider.provider_id })
          })
        )
      );
      setSelectedProviderId(provider.provider_id);
      setAgentTest(null);
      await refresh();
    });
  }

  async function testProvider(providerId = selectedProviderId) {
    if (!providerId) return;
    await runTask(t.loadingTest, async () => {
      const health = await api<{ status: string; message: string }>("/v1/agents/test", {
        method: "POST",
        body: JSON.stringify({ provider_id: providerId })
      });
      setAgentTest(`${health.status}: ${health.message}`);
    });
  }

  async function resolveTask(taskId: string) {
    if (!session) return;
    const updated = await runTask(t.loadingRefresh, () =>
      api<Session>(`/v1/hitl/${taskId}/resolve`, {
        method: "POST",
        body: JSON.stringify({ session_id: session.session_id, payload: { resolved_from: "web-ui" } })
      })
    );
    if (updated) setSession(updated);
  }

  useEffect(() => {
    refresh().catch((err) => setError(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="appShell">
      <aside className="sidebar">
        <div className="brandBlock">
          <div className="brandMark">SA</div>
          <div>
            <p className="eyebrow">{t.appMode}</p>
            <h1>Study Anything</h1>
          </div>
        </div>

        <nav className="navList" aria-label="Primary">
          <button className={view === "learn" ? "navItem active" : "navItem"} onClick={() => setView("learn")}>
            <span>{t.navLearn}</span>
            <small>{t.navLearnHint}</small>
          </button>
          <button className={view === "agent" ? "navItem active" : "navItem"} onClick={() => setView("agent")}>
            <span>{t.navAgent}</span>
            <small>{t.navAgentHint}</small>
          </button>
        </nav>

        <section className="sessionRail">
          <div className="sectionTitle">
            <h2>{t.recent}</h2>
            <button className="iconButton" onClick={() => refresh()} title={t.refresh}>
              R
            </button>
          </div>
          <div className="sessionList">
            {sessions.slice(0, 8).map((item) => (
              <button
                className={session?.session_id === item.session_id ? "sessionItem active" : "sessionItem"}
                key={item.session_id}
                onClick={() => loadSession(item.session_id)}
              >
                <span>{item.source?.title ?? t.navLearn}</span>
                <small>
                  {stageLabel(item.stage, t.stages)} {formatTime(item.updated_at)}
                </small>
              </button>
            ))}
            {sessions.length === 0 && <p className="emptyState">{t.emptyRecent}</p>}
          </div>
        </section>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">{view === "learn" ? t.navLearnHint : t.navAgentHint}</p>
            <h2>{view === "learn" ? t.learnTitle : t.agentTitle}</h2>
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
            <span className={`statusPill ${agentReady ? "good" : "warn"}`}>{agentReady ? t.agentReady : t.agentMissing}</span>
          </div>
        </header>

        {error && <section className="notice bad">{error}</section>}
        {loading && <section className="notice neutral">{loading}</section>}

        {view === "learn" ? (
          <LearningWorkspace
            activeQuiz={activeQuiz}
            composer={composer}
            hitlTasks={hitlTasks}
            latestGrade={latestGrade}
            onComposerChange={setComposer}
            onResolve={resolveTask}
            onStartFromSource={() => startLearning({ title, reference, text: sourceText })}
            onSubmit={handleComposer}
            progress={progressFor(session?.stage)}
            reference={reference}
            session={session}
            setReference={setReference}
            setSourceText={setSourceText}
            setTitle={setTitle}
            sourceStats={sourceStats}
            sourceText={sourceText}
            t={t}
            title={title}
          />
        ) : (
          <AgentWorkspace
            agentStatus={agentStatus}
            agentTest={agentTest}
            providerEndpoint={providerEndpoint}
            providerKind={providerKind}
            providerLabel={providerLabel}
            saveProvider={saveProvider}
            selectedProviderId={selectedProviderId}
            setProviderEndpoint={setProviderEndpoint}
            setProviderKind={setProviderKind}
            setProviderLabel={setProviderLabel}
            setSelectedProviderId={setSelectedProviderId}
            t={t}
            testProvider={testProvider}
          />
        )}
      </section>
    </main>
  );
}

function LearningWorkspace(props: {
  activeQuiz: QuizItem | null;
  composer: string;
  hitlTasks: HitlInterrupt[];
  latestGrade: GradingResult | null;
  onComposerChange: (value: string) => void;
  onResolve: (taskId: string) => void;
  onStartFromSource: () => void;
  onSubmit: () => void;
  progress: number;
  reference: string;
  session: Session | null;
  setReference: (value: string) => void;
  setSourceText: (value: string) => void;
  setTitle: (value: string) => void;
  sourceStats: { words: number; chars: number };
  sourceText: string;
  t: (typeof copy)[Locale];
  title: string;
}) {
  const {
    activeQuiz,
    composer,
    hitlTasks,
    latestGrade,
    onComposerChange,
    onResolve,
    onStartFromSource,
    onSubmit,
    progress,
    reference,
    session,
    setReference,
    setSourceText,
    setTitle,
    sourceStats,
    sourceText,
    t,
    title
  } = props;
  const latestInsight = session?.insights[session.insights.length - 1];
  const openTasks = hitlTasks.filter((task) => task.status === "open");

  return (
    <div className="learningGrid">
      <section className="conversationPanel">
        <p className="lede">{t.learnSubtitle}</p>
        <div className="messageList">
          <article className="message assistant">
            <strong>{activeQuiz ? t.quizIntro : t.welcome}</strong>
            {activeQuiz && <p>{activeQuiz.prompt}</p>}
            {activeQuiz && <small>{activeQuiz.rubric}</small>}
          </article>
          {latestGrade && (
            <article className="message result">
              <strong>{t.feedback}</strong>
              <p>{latestGrade.feedback}</p>
            </article>
          )}
          {latestInsight && (
            <article className="message result">
              <strong>{t.insight}</strong>
              <p>{latestInsight}</p>
            </article>
          )}
        </div>
        <div className="composer">
          <textarea
            value={composer}
            onChange={(event) => onComposerChange(event.target.value)}
            placeholder={activeQuiz ? t.answerPlaceholder : t.inputPlaceholder}
          />
          <div className="composerActions">
            <button className="primary" onClick={onSubmit}>
              {activeQuiz ? t.answer : t.start}
            </button>
            {!activeQuiz && <button onClick={onStartFromSource}>{t.useSource}</button>}
          </div>
        </div>
        {openTasks.length > 0 && (
          <div className="reviewBox">
            <strong>{t.needsReview}</strong>
            {openTasks.map((task) => (
              <div className="reviewItem" key={task.task_id}>
                <span>{task.message}</span>
                <button onClick={() => onResolve(task.task_id)}>{t.resolve}</button>
              </div>
            ))}
          </div>
        )}
      </section>

      <aside className="detailRail">
        <section className="sidePanel">
          <div className="panelHeading">
            <h3>{t.sourceTitle}</h3>
            <span className={`statusPill ${session?.source?.verified ? "good" : "neutral"}`}>
              {session?.source?.verified ? t.verified : t.draft}
            </span>
          </div>
          <label>
            {t.title}
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            {t.reference}
            <input value={reference} onChange={(event) => setReference(event.target.value)} />
          </label>
          <label>
            {t.sourceText}
            <textarea value={sourceText} onChange={(event) => setSourceText(event.target.value)} />
          </label>
          <div className="metricStrip">
            <span>
              {sourceStats.words} {t.words}
            </span>
            <span>
              {sourceStats.chars} {t.chars}
            </span>
          </div>
        </section>

        <section className="sidePanel">
          <div className="panelHeading">
            <h3>{t.progressTitle}</h3>
            <strong>{stageLabel(session?.stage, t.stages)}</strong>
          </div>
          <div className="progressBar">
            <span style={{ width: `${progress}%` }} />
          </div>
          <dl className="progressStats">
            <dt>{t.mastery}</dt>
            <dd>{session?.mastery.level.toFixed(1) ?? "0.0"}</dd>
            <dt>{t.score}</dt>
            <dd>{latestGrade ? latestGrade.score.toFixed(2) : "-"}</dd>
          </dl>
          <p className="feedbackText">{latestGrade?.feedback ?? t.noFeedback}</p>
        </section>
      </aside>
    </div>
  );
}

function AgentWorkspace(props: {
  agentStatus: AgentStatus | null;
  agentTest: string | null;
  providerEndpoint: string;
  providerKind: string;
  providerLabel: string;
  saveProvider: () => void;
  selectedProviderId: string | null;
  setProviderEndpoint: (value: string) => void;
  setProviderKind: (value: string) => void;
  setProviderLabel: (value: string) => void;
  setSelectedProviderId: (value: string | null) => void;
  t: (typeof copy)[Locale];
  testProvider: (providerId?: string | null) => void;
}) {
  const {
    agentStatus,
    agentTest,
    providerEndpoint,
    providerKind,
    providerLabel,
    saveProvider,
    selectedProviderId,
    setProviderEndpoint,
    setProviderKind,
    setProviderLabel,
    setSelectedProviderId,
    t,
    testProvider
  } = props;

  return (
    <div className="agentGrid">
      <section className="conversationPanel agentIntro">
        <h3>{t.agentTitle}</h3>
        <p>{t.agentLead}</p>
        <div className="trustNote">{t.noSecrets}</div>
        <div className="capabilityGrid">
          {t.capabilityLabels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      </section>

      <section className="sidePanel agentSetup">
        <label>
          {t.kind}
          <select value={providerKind} onChange={(event) => setProviderKind(event.target.value)}>
            <option value="http_agent">{t.localAgent}</option>
            <option value="fake_agent">{t.fakeAgent}</option>
            <option value="cli_agent">{t.cliAgent}</option>
            <option value="mcp_agent">{t.mcpAgent}</option>
          </select>
        </label>
        <label>
          {t.label}
          <input value={providerLabel} onChange={(event) => setProviderLabel(event.target.value)} />
        </label>
        <label>
          {t.endpoint}
          <input
            disabled={providerKind !== "http_agent"}
            value={providerEndpoint}
            onChange={(event) => setProviderEndpoint(event.target.value)}
          />
        </label>
        <div className="composerActions">
          <button className="primary" onClick={saveProvider}>
            {t.saveAgent}
          </button>
          <button disabled={!selectedProviderId} onClick={() => testProvider(selectedProviderId)}>
            {t.testAgent}
          </button>
        </div>
        {agentTest && <p className="feedbackText">{agentTest}</p>}
      </section>

      <section className="sidePanel agentList">
        <h3>{t.configuredAgents}</h3>
        <div className="providerList">
          {agentStatus?.providers.map((provider) => (
            <button
              className={selectedProviderId === provider.provider_id ? "providerCard active" : "providerCard"}
              key={provider.provider_id}
              onClick={() => setSelectedProviderId(provider.provider_id)}
            >
              <strong>{provider.label}</strong>
              <small>
                {agentKindLabel(provider.kind, t)}
                {provider.endpoint ? ` · ${provider.endpoint}` : ""}
              </small>
            </button>
          ))}
          {agentStatus?.providers.length === 0 && <p className="emptyState">{t.noAgents}</p>}
        </div>
      </section>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
