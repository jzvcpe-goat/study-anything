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

type ViewKey = "learn" | "agents" | "ops" | "plugins";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

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

  async function startDemo() {
    await runTask("Starting learning flow", async () => {
      const created = await api<Session>("/v1/sessions", {
        method: "POST",
        body: JSON.stringify({ user_id: "local-user", track: "ACADEMIC", use_demo_agent: true })
      });
      const withReading = await api<Session>(`/v1/sessions/${created.session_id}/reading`, {
        method: "POST",
        body: JSON.stringify({ source_type: "local_text", reference, title, text })
      });
      const running = await api<Session>(`/v1/sessions/${withReading.session_id}/run`, {
        method: "POST"
      });
      setSession(running);
      setAnswer("");
      await refreshAll(running.session_id);
    });
  }

  async function loadSession(sessionId: string) {
    await runTask("Loading session", async () => {
      setSession(await api<Session>(`/v1/sessions/${sessionId}`));
      setActiveView("learn");
    });
  }

  async function addProvider() {
    await runTask("Saving agent provider", async () => {
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
    await runTask("Testing agent", async () => {
      const health = await api<{ status: string; message: string }>("/v1/agents/test", {
        method: "POST",
        body: JSON.stringify({ provider_id: providerId })
      });
      setAgentTest(`${health.status}: ${health.message}`);
      await refreshAgents();
    });
  }

  async function submitAnswer() {
    if (!session || !activeQuiz) return;
    await runTask("Submitting answer", async () => {
      const updated = await api<Session>(`/v1/sessions/${session.session_id}/answers`, {
        method: "POST",
        body: JSON.stringify({ answers: { [activeQuiz.item_id]: answer } })
      });
      setSession(updated);
      setAnswer("");
      await refreshAll(updated.session_id);
    });
  }

  async function resume() {
    if (!session) return;
    await runTask("Resuming workflow", async () => {
      const updated = await api<Session>(`/v1/sessions/${session.session_id}/resume`, {
        method: "POST"
      });
      setSession(updated);
      await refreshAll(updated.session_id);
    });
  }

  async function discard() {
    if (!session) return;
    await runTask("Discarding session", async () => {
      const updated = await api<Session>(`/v1/sessions/${session.session_id}/discard`, {
        method: "POST"
      });
      setSession(updated);
      await refreshAll(updated.session_id);
    });
  }

  async function resolveHitl(taskId: string) {
    if (!session) return;
    await runTask("Resolving HITL", async () => {
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
            <p className="eyebrow">Self-host Alpha</p>
            <h1>Study Anything</h1>
          </div>
        </div>

        <nav className="navList" aria-label="Primary">
          {[
            ["learn", "Learn", "Run the source-bound learning loop"],
            ["agents", "Agents", "Configure Bring Your Own Agent"],
            ["ops", "System", "Inspect runtime health and HITL"],
            ["plugins", "Plugins", "Review extension surfaces"]
          ].map(([key, label, helper]) => (
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
            <h2>Recent Sessions</h2>
            <button className="iconButton" onClick={() => refreshAll()} title="Refresh sessions">
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
            {sessions.length === 0 && <p className="emptyState">No saved sessions yet.</p>}
          </div>
        </section>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Branch: codex/ui-dashboard-foundation</p>
            <h2>{viewTitle(activeView)}</h2>
          </div>
          <div className="topbarActions">
            <span className={`statusPill ${agentStatus?.defaults["quiz.generate"] ? "good" : "warn"}`}>
              {agentStatus?.defaults["quiz.generate"] ? "Agent ready" : "Agent setup needed"}
            </span>
            <button onClick={() => refreshAll()} disabled={Boolean(loading)}>
              Refresh
            </button>
          </div>
        </header>

        {error && <section className="notice bad">{error}</section>}
        {loading && <section className="notice neutral">{loading}</section>}

        {activeView === "learn" && (
          <LearnView
            activeQuiz={activeQuiz}
            answer={answer}
            discard={discard}
            latestGrade={latestGrade}
            openInterrupts={openInterrupts}
            reference={reference}
            resolveHitl={resolveHitl}
            resume={resume}
            session={session}
            setAnswer={setAnswer}
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
            hitlTasks={hitlTasks}
            integrations={integrations}
            session={session}
            systemStatus={systemStatus}
          />
        )}

        {activeView === "plugins" && <PluginView plugins={plugins} />}
      </section>
    </main>
  );
}

function viewTitle(view: ViewKey) {
  if (view === "agents") return "Agent Control Plane";
  if (view === "ops") return "System Operations";
  if (view === "plugins") return "Plugin Ecosystem";
  return "Learning Workspace";
}

function LearnView(props: {
  activeQuiz?: QuizItem;
  answer: string;
  discard: () => void;
  latestGrade?: GradingResult;
  openInterrupts: HitlInterrupt[];
  reference: string;
  resolveHitl: (taskId: string) => void;
  resume: () => void;
  session: Session | null;
  setAnswer: (value: string) => void;
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
    discard,
    latestGrade,
    openInterrupts,
    reference,
    resolveHitl,
    resume,
    session,
    setAnswer,
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
    <div className="learnGrid">
      <section className="toolPanel sourcePanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">Input</p>
            <h3>Reading Source</h3>
          </div>
          <span className={`statusPill ${sourceStats.reference === "linked" ? "good" : "warn"}`}>
            {sourceStats.reference}
          </span>
        </div>
        <label>
          Title
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label>
          Source reference
          <input value={reference} onChange={(event) => setReference(event.target.value)} />
        </label>
        <label>
          Source text
          <textarea className="sourceText" value={text} onChange={(event) => setText(event.target.value)} />
        </label>
        <div className="metricStrip">
          <span>{sourceStats.words} words</span>
          <span>{sourceStats.chars} chars</span>
          <span>{session?.source?.verified ? "verified" : "local draft"}</span>
        </div>
        <button className="primary wide" onClick={startDemo}>
          Start learning flow
        </button>
      </section>

      <section className="toolPanel mainFlow">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">Workflow</p>
            <h3>{session?.stage ?? "No active session"}</h3>
          </div>
          <span className="idTag">{session ? shortId(session.session_id) : "idle"}</span>
        </div>

        <div className="workflowMap">
          {WORKFLOW_STEPS.map(([node, label], index) => {
            const completed = session?.events.some((event) => event.node === node);
            return (
              <div className={completed ? "workflowStep done" : "workflowStep"} key={node}>
                <span>{index + 1}</span>
                <strong>{label}</strong>
                <small>{node}</small>
              </div>
            );
          })}
        </div>

        {openInterrupts.length > 0 && (
          <div className="notice warn">
            {openInterrupts.map((item) => (
              <div className="interruptRow" key={item.task_id}>
                <span>{item.message}</span>
                <button onClick={() => resolveHitl(item.task_id)}>Resolve</button>
              </div>
            ))}
          </div>
        )}

        {activeQuiz ? (
          <div className="quizBlock">
            <p className="eyebrow">Source-bound quiz</p>
            <h4>{activeQuiz.prompt}</h4>
            <p>{activeQuiz.rubric}</p>
            <textarea
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              placeholder="Answer with a source-grounded explanation."
            />
            <div className="actionRow">
              <button className="primary" onClick={submitAnswer}>
                Submit answer
              </button>
              <button onClick={resume}>Resume</button>
              <button onClick={discard}>Discard</button>
            </div>
          </div>
        ) : (
          <div className="emptyPanel">
            <h4>Start with a reading source.</h4>
            <p>The demo flow creates a session, binds the source, generates a quiz, and waits for an answer.</p>
          </div>
        )}
      </section>

      <section className="toolPanel evidencePanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">Evidence</p>
            <h3>Mastery And Events</h3>
          </div>
          <div className="masteryBadge">{session?.mastery.level.toFixed(1) ?? "0.0"}</div>
        </div>
        <dl className="definitionGrid">
          <dt>Bloom</dt>
          <dd>{session?.mastery.bloom ?? "remember"}</dd>
          <dt>Latest score</dt>
          <dd>{latestGrade ? latestGrade.score.toFixed(2) : "none"}</dd>
          <dt>Updated</dt>
          <dd>{formatTime(session?.updated_at)}</dd>
        </dl>
        {latestGrade && <p className="feedback">{latestGrade.feedback}</p>}
        <EventList events={session?.events ?? []} />
      </section>
    </div>
  );
}

function AgentView(props: {
  agentStatus: AgentStatus | null;
  agentTest: string | null;
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
            <p className="eyebrow">Bring Your Own Agent</p>
            <h3>Provider Setup</h3>
          </div>
          <span className="statusPill neutral">No model keys stored</span>
        </div>
        <label>
          Provider kind
          <select value={providerKind} onChange={(event) => setProviderKind(event.target.value)}>
            <option value="http_agent">Local HTTP Agent</option>
            <option value="fake_agent">Fake demo agent</option>
            <option value="cli_agent">CLI agent adapter</option>
            <option value="mcp_agent">MCP agent adapter</option>
          </select>
        </label>
        <label>
          Label
          <input value={providerLabel} onChange={(event) => setProviderLabel(event.target.value)} />
        </label>
        <label>
          Endpoint
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
            Save defaults
          </button>
          <button disabled={!savedProviderId} onClick={() => testProvider(savedProviderId)}>
            Test saved
          </button>
        </div>
        {agentTest && <p className="feedback">{agentTest}</p>}
      </section>

      <section className="toolPanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">Registry</p>
            <h3>Providers And Defaults</h3>
          </div>
          <span className="idTag">{readyProviders.length} enabled</span>
        </div>
        <div className="providerList">
          {agentStatus?.providers.map((provider) => (
            <div className="providerRow" key={provider.provider_id}>
              <div>
                <strong>{provider.label}</strong>
                <small>
                  {provider.kind} / {provider.endpoint || "local"}
                </small>
              </div>
              <div className="providerActions">
                <button onClick={() => setSavedProviderId(provider.provider_id)}>Select</button>
                <button onClick={() => testProvider(provider.provider_id)}>Test</button>
              </div>
            </div>
          ))}
          {agentStatus?.providers.length === 0 && <p className="emptyState">No providers configured.</p>}
        </div>
        <h4>Capability defaults</h4>
        <dl className="definitionGrid">
          {CAPABILITIES.map((capability) => (
            <React.Fragment key={capability}>
              <dt>{capability}</dt>
              <dd>{agentStatus?.defaults[capability] ? shortId(String(agentStatus.defaults[capability])) : "unset"}</dd>
            </React.Fragment>
          ))}
        </dl>
      </section>
    </div>
  );
}

function OpsView(props: {
  hitlTasks: HitlInterrupt[];
  integrations: IntegrationStatus[];
  session: Session | null;
  systemStatus: SystemStatus | null;
}) {
  const { hitlTasks, integrations, session, systemStatus } = props;
  return (
    <div className="opsLayout">
      <section className="toolPanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">Runtime</p>
            <h3>System Health</h3>
          </div>
          <span className={`statusPill ${toneForStatus(systemStatus?.status ?? "unknown")}`}>
            {systemStatus?.status ?? "unknown"}
          </span>
        </div>
        <div className="statGrid">
          <Stat label="Version" value={systemStatus?.version ?? "unknown"} />
          <Stat label="Sessions" value={systemStatus?.session_count ?? 0} />
          <Stat label="HITL" value={systemStatus?.open_hitl_count ?? 0} />
          <Stat label="Store" value={systemStatus?.session_store ?? "unknown"} />
          <Stat label="LangGraph" value={systemStatus?.langgraph_available ? "available" : "alpha executor"} />
          <Stat label="Plugins" value={systemStatus?.plugin_count ?? 0} />
        </div>
        <p className="pathText">{systemStatus?.data_dir ?? "No data directory reported."}</p>
      </section>

      <section className="toolPanel">
        <div className="panelHeading">
          <div>
            <p className="eyebrow">Boundaries</p>
            <h3>Integration Matrix</h3>
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
            <p className="eyebrow">Human Review</p>
            <h3>Open Interrupts</h3>
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
          {hitlTasks.length === 0 && <p className="emptyState">No HITL interrupts.</p>}
        </div>
        {session && <EventList events={session.events} />}
      </section>
    </div>
  );
}

function PluginView({ plugins }: { plugins: PluginStatus[] }) {
  return (
    <section className="toolPanel">
      <div className="panelHeading">
        <div>
          <p className="eyebrow">Extensions</p>
          <h3>Plugin Registry</h3>
        </div>
        <span className="idTag">{plugins.length} discovered</span>
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
        {plugins.length === 0 && <p className="emptyState">No plugins discovered.</p>}
      </div>
    </section>
  );
}

function EventList({ events }: { events: StudyEvent[] }) {
  return (
    <div className="eventList">
      <h4>Event Timeline</h4>
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
      {events.length === 0 && <p className="emptyState">No events yet.</p>}
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
