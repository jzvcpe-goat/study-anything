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

type QuizItem = {
  item_id: string;
  prompt: string;
  source_ref: string;
  rubric: string;
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
};

type Session = {
  session_id: string;
  stage: string;
  track: string;
  quiz_items: QuizItem[];
  mastery: { level: number; bloom: string };
  insights: string[];
  hitl_interrupts: Array<{ task_id: string; kind: string; message: string; status: string }>;
  events: Array<{
    event_id: string;
    type: string;
    node: string;
    created_at: string;
    payload?: EventPayload;
  }>;
  discarded: boolean;
};

type SystemStatus = {
  status: string;
  version: string;
  data_dir: string;
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

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

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

function App() {
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [plugins, setPlugins] = useState<PluginStatus[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
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
  const [error, setError] = useState<string | null>(null);

  const activeQuiz = session?.quiz_items[0];
  const openInterrupts = useMemo(
    () => session?.hitl_interrupts.filter((item) => item.status === "open") ?? [],
    [session]
  );

  const defaultCapabilities = [
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
    "source.verify",
    "memory.retrieve",
    "embedding.create"
  ];

  async function refreshAgents() {
    setAgentStatus(await api<AgentStatus>("/v1/agents/status"));
  }

  async function refreshOps() {
    const [status, pluginList, integrationList] = await Promise.all([
      api<SystemStatus>("/v1/system/status"),
      api<PluginStatus[]>("/v1/plugins"),
      api<IntegrationStatus[]>("/v1/system/integrations")
    ]);
    setSystemStatus(status);
    setPlugins(pluginList);
    setIntegrations(integrationList);
  }

  async function startDemo() {
    setError(null);
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
    await refreshAgents();
    await refreshOps();
  }

  async function addProvider() {
    setError(null);
    const provider = await api<ProviderStatus>("/v1/agents/providers", {
      method: "POST",
      body: JSON.stringify({
        kind: providerKind,
        label: providerLabel,
        endpoint: providerEndpoint,
        capabilities: defaultCapabilities,
        metadata: { configured_from: "web-ui", secret_storage: "user-agent-only" }
      })
    });
    await Promise.all(
      defaultCapabilities.map((capability) =>
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
    await refreshAgents();
  }

  async function testSavedAgent() {
    if (!savedProviderId) return;
    setError(null);
    const health = await api<{ status: string; message: string }>("/v1/agents/test", {
      method: "POST",
      body: JSON.stringify({ provider_id: savedProviderId })
    });
    setAgentTest(`${health.status}: ${health.message}`);
  }

  async function submitAnswer() {
    if (!session || !activeQuiz) return;
    const updated = await api<Session>(`/v1/sessions/${session.session_id}/answers`, {
      method: "POST",
      body: JSON.stringify({ answers: { [activeQuiz.item_id]: answer } })
    });
    setSession(updated);
  }

  async function discard() {
    if (!session) return;
    setSession(
      await api<Session>(`/v1/sessions/${session.session_id}/discard`, {
        method: "POST"
      })
    );
  }

  function agentForEvent(event: Session["events"][number]) {
    return event.payload?.agent ?? event.payload?.agents?.[0];
  }

  useEffect(() => {
    refreshAgents().catch((err) => setError(String(err)));
    refreshOps().catch((err) => setError(String(err)));
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Self-host Alpha</p>
          <h1>Neural Console</h1>
        </div>
        <div className="statusPill">
          <span className="dot" />
          {agentStatus?.defaults["quiz.generate"] ? "Agent ready" : "Agent setup needed"}
        </div>
      </header>

      {error && <section className="error">{error}</section>}

      <section className="workspace">
        <aside className="panel setup">
          <h2>Reading</h2>
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
            <textarea value={text} onChange={(event) => setText(event.target.value)} />
          </label>
          <button className="primary" onClick={startDemo}>
            Start demo flow
          </button>

          <div className="divider" />
          <h2>Agent Provider</h2>
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
              value={providerEndpoint}
              onChange={(event) => setProviderEndpoint(event.target.value)}
              placeholder="http://127.0.0.1:8787"
            />
          </label>
          <div className="capabilityList">
            {defaultCapabilities.map((capability) => (
              <span key={capability}>{capability}</span>
            ))}
          </div>
          <div className="actions">
            <button onClick={addProvider}>Save as default</button>
            <button onClick={testSavedAgent} disabled={!savedProviderId}>
              Test
            </button>
          </div>
          {agentTest && <p className="testResult">{agentTest}</p>}
        </aside>

        <section className="panel flow">
          <div className="panelHeader">
            <h2>Workflow</h2>
            <span>{session?.stage ?? "idle"}</span>
          </div>
          <div className="timeline">
            {[
              "initialize",
              "architect",
              "gap",
              "quiz",
              "grade",
              "mastery",
              "synthesize",
              "scribe",
              "incubate"
            ].map((step, index) => (
              <div className="step" key={step}>
                <span>{index + 1}</span>
                {step}
              </div>
            ))}
          </div>

          {openInterrupts.length > 0 && (
            <div className="interrupt">
              {openInterrupts.map((item) => (
                <p key={item.task_id}>{item.message}</p>
              ))}
            </div>
          )}

          {activeQuiz && (
            <div className="quiz">
              <p className="eyebrow">Source-bound quiz</p>
              <h3>{activeQuiz.prompt}</h3>
              <p>{activeQuiz.rubric}</p>
              <textarea
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                placeholder="Write an answer grounded in the source."
              />
              <div className="actions">
                <button className="primary" onClick={submitAnswer}>
                  Submit answer
                </button>
                <button onClick={discard}>Discard</button>
              </div>
            </div>
          )}
        </section>

        <aside className="panel metrics">
          <h2>System</h2>
          <div className="opsGrid">
            <span>API</span>
            <strong>{systemStatus?.status ?? "unknown"}</strong>
            <span>Sessions</span>
            <strong>{systemStatus?.session_count ?? 0}</strong>
            <span>HITL</span>
            <strong>{systemStatus?.open_hitl_count ?? 0}</strong>
            <span>LangGraph</span>
            <strong>{systemStatus?.langgraph_available ? "ready" : "pending"}</strong>
          </div>

          <h2>Mastery</h2>
          <div className="masteryValue">{session?.mastery.level.toFixed(1) ?? "0.0"}</div>
          <p>{session?.mastery.bloom ?? "remember"}</p>

          <h2>Agents</h2>
          <ul className="modelList">
            {agentStatus?.providers.map((provider) => (
              <li key={provider.provider_id}>
                <span>{provider.label}</span>
                <small>{provider.endpoint || provider.kind}</small>
              </li>
            ))}
          </ul>

          <h2>Integrations</h2>
          <ul className="modelList compactList">
            {integrations.slice(0, 6).map((integration) => (
              <li key={integration.name}>
                <span>{integration.name}</span>
                <small>{integration.status}</small>
              </li>
            ))}
          </ul>

          <h2>Plugins</h2>
          <ul className="modelList">
            {plugins.map((plugin) => (
              <li key={plugin.path}>
                <span>{plugin.manifest?.name ?? plugin.path}</span>
                <small>{plugin.status}</small>
              </li>
            ))}
            {plugins.length === 0 && (
              <li>
                <span>No plugins discovered</span>
                <small>empty</small>
              </li>
            )}
          </ul>

          <h2>Events</h2>
          <ul className="events">
            {session?.events.slice(-7).map((event) => {
              const agent = agentForEvent(event);
              return (
              <li key={event.event_id}>
                <span>{event.type}</span>
                <small>
                  {agent?.provider_id
                    ? `${event.node} / ${agent.task_type ?? "agent"} / ${agent.provider_id.slice(0, 8)}`
                    : event.node}
                </small>
              </li>
              );
            })}
          </ul>
        </aside>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
