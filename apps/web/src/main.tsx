import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Locale = "zh" | "en";
type ViewKey = "learn" | "agent" | "launch";

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

type PluginManifest = {
  plugin_id: string;
  name: string;
  version: string;
  api_version: string;
  entrypoint: string;
  hooks: string[];
  permissions: string[];
};

type PluginTrustReport = {
  source_digest: string | null;
  review_status: string;
  signature_status: string;
  risk_level: string;
  install_recommendation: string;
  warnings: string[];
  local_only: boolean;
  remote_code_downloads_allowed: boolean;
  entrypoints_executed_during_install: boolean;
  raw_secrets_allowed: boolean;
};

type PermissionDetail = {
  permission: string;
  label: string;
  risk: string;
  description: string;
};

type PluginStatus = {
  manifest: PluginManifest | null;
  permission_details: PermissionDetail[];
  path: string;
  status: string;
  message: string;
  trust: PluginTrustReport | null;
  install_dir?: string;
  requires_confirmation?: boolean;
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
  workspace_id: string | null;
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

type PmfMetrics = {
  schema_version: string;
  generated_at: string;
  sessions: {
    total: number;
    completed: number;
    discarded: number;
    open_hitl: number;
    agent_interrupts: number;
    completion_rate: number;
  };
  learners: {
    unique: number;
    active_7d: number;
    active_30d: number;
    repeat: number;
    repeat_rate: number;
  };
  learning: {
    answered_sessions: number;
    total_answers: number;
    insight_sessions: number;
    average_mastery_level: number;
    average_mastery_delta: number;
  };
  plugins: {
    ready: number;
    invalid: number;
  };
  hosted_interest: PmfInterestSummary;
  signals: {
    weekly_active_learners: number;
    completion_rate: number;
    repeat_learning_rate: number;
    plugin_installs: number;
    hosted_waitlist_count: number;
  };
  privacy: {
    local_only: boolean;
    raw_contact_stored: boolean;
    raw_user_identifiers_exposed: boolean;
    privacy_exclusions: string[];
  };
};

type PmfInterestSummary = {
  schema_version: string;
  total: number;
  with_contact: number;
  with_comment: number;
  services: Record<string, number>;
  sources: Record<string, number>;
  local_only: boolean;
  raw_contact_stored: boolean;
  privacy_exclusions: string[];
};

type PmfExport = {
  schema_version: string;
  generated_at: string;
  destination: string;
  consent: {
    granted: boolean;
    statement: string;
    note_provided: boolean;
  };
  metrics: {
    sessions: Record<string, number>;
    learners: Record<string, number>;
    learning: Record<string, number>;
    plugins: Record<string, number>;
    signals: Record<string, number>;
  };
  hosted_interest: {
    total: number;
    with_contact: number;
    with_comment: number;
    services: Record<string, number>;
    sources: Record<string, number>;
    raw_contact_stored: boolean;
  };
  privacy: {
    shareable_after_consent: boolean;
    raw_contact_stored: boolean;
    raw_user_identifiers_exposed: boolean;
    individual_contact_hashes_exposed: boolean;
    individual_user_hashes_exposed: boolean;
    freeform_comments_exposed: boolean;
    privacy_exclusions: string[];
  };
};

type WorkspaceMember = {
  user_hash: string;
  role: string;
  display_name: string;
};

type WorkspaceSummary = {
  workspace_id: string;
  name: string;
  slug: string;
  owner_hash: string;
  members: WorkspaceMember[];
  local_only: boolean;
};

type WorkspaceStatus = {
  schema_version: string;
  local_only: boolean;
  account_required: boolean;
  raw_user_ids_stored: boolean;
  default_workspace: WorkspaceSummary;
  workspaces: WorkspaceSummary[];
  role_permissions: Record<string, string[]>;
  commercial_boundary: {
    hosted_sync_enabled: boolean;
    billing_enabled: boolean;
    remote_identity_provider: string | null;
  };
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

const INTEREST_SERVICES = ["neural_sync", "neural_publish", "neural_teams", "catalyst", "hosted_alpha"];

const DEMO_SOURCE = {
  title: "Asymptotic Theory Reading",
  reference: "demo://reading/asymptotic-theory",
  text: "A precise learning system should bind every generated question to a source, grade answers with a rubric, and update mastery only when evidence supports the change."
};

const copy = {
  zh: {
    appMode: "本地优先学习系统",
    navLearn: "学习",
    navAgent: "Agent",
    navLaunch: "上线",
    navLearnHint: "自然语言学习空间",
    navAgentHint: "连接你自己的推理系统",
    navLaunchHint: "本地 PMF 与部署信号",
    workspaceLabel: "本地工作区",
    recent: "最近学习",
    emptyRecent: "还没有学习记录。",
    refresh: "刷新",
    learnTitle: "今天想学什么？",
    learnSubtitle: "粘贴材料或直接描述目标，Study Anything 会生成带来源约束的练习并追踪掌握度。",
    agentReady: "Agent 已连接",
    demoAgentReady: "演示 Agent 可用",
    agentMissing: "未连接 Agent",
    setupTitle: "第一次使用，从这里开始",
    setupLead: "先用演示 Agent 跑通学习闭环，再把真实推理交给你自己的 Agent。",
    setupDemoTitle: "1. 跑通本地演示",
    setupDemoBody: "不需要任何密钥，验证提问、作答、评分和掌握度更新。",
    setupSourceTitle: "2. 换成你的材料",
    setupSourceBody: "粘贴文章、笔记或课程片段，问题会绑定到来源。",
    setupAgentTitle: "3. 接入你的 Agent",
    setupAgentBody: "真实模型、工具和凭证留在你的网关里。",
    runDemo: "运行演示",
    useOwnNotes: "使用我的材料",
    connectAgent: "连接 Agent",
    dismissGuide: "稍后再说",
    inputPlaceholder: "例如：帮我学习这段关于渐近理论的材料，生成测验，并在我回答后评估掌握度。",
    answerPlaceholder: "直接回答当前问题。系统会基于材料和评分标准给出反馈。",
    answerRequired: "先写下你的回答，再提交评分。",
    start: "开始学习",
    answer: "提交回答",
    useSource: "使用学习材料",
    newRound: "新学习",
    sourceTitle: "学习材料",
    title: "标题",
    reference: "来源",
    sourceText: "正文",
    sourceTextPlaceholder: "粘贴你要学习的材料。可以是课堂笔记、论文片段、项目文档或阅读摘录。",
    sourceRequired: "先粘贴学习材料，或在上方输入你要学习的内容。",
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
    welcome: "把你要学习的内容放进输入框，或者先完善材料区。",
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
    agentSetupHint: "如果你暂时没有自己的 Agent，可以继续使用演示 Agent；一旦保存 HTTP Agent，后续学习会默认交给它处理。",
    pluginTrustTitle: "插件信任与安装",
    pluginTrustLead: "只安装你在本机明确选择的插件目录。Study Anything 会先校验 manifest，并要求你确认权限。",
    pluginSourcePath: "插件目录",
    pluginPathPlaceholder: "例如：plugins/example-exporter 或 /path/to/plugin",
    pluginPathRequired: "先填写本机插件目录。",
    previewPlugin: "预览权限",
    installPlugin: "确认权限并安装",
    installedPlugins: "已发现插件",
    noPlugins: "还没有发现插件。",
    pluginPermissions: "请求权限",
    pluginConfirmHint: "逐项勾选后才可以安装。安装只复制文件，不下载、不执行插件代码。",
    pluginInstallBlocked: "请先确认全部权限。",
    pluginInstalled: "插件已安装",
    pluginHooks: "Hooks",
    pluginInstallDir: "安装目录",
    pluginRiskLevel: "风险等级",
    pluginReviewStatus: "审查状态",
    pluginSignatureStatus: "签名状态",
    pluginRecommendation: "安装建议",
    pluginDigest: "源码摘要",
    pluginWarnings: "注意",
    permissionRisk: "风险",
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
    loadingPluginPreview: "正在读取插件 manifest",
    loadingPluginInstall: "正在安装插件",
    loadingRefresh: "正在刷新",
    launchTitle: "上线准备不是猜出来的",
    launchLead: "用本机聚合指标观察学习闭环、重复使用和插件生态，不上传正文、答案、洞察或真实联系方式。",
    launchSignalTitle: "PMF 信号",
    launchPrivacyTitle: "隐私边界",
    launchInterestTitle: "未来服务意向",
    launchInterestLead: "可选记录你对 Sync、Publish、Teams 或 Catalyst 的兴趣。数据只保存在本机。",
    launchExportTitle: "分享 PMF 包",
    launchExportLead: "生成一个可分享的聚合包，用于社区 PMF 反馈或 hosted waitlist。需要你明确同意。",
    completedSessions: "完成学习",
    completionRate: "完成率",
    activeLearners: "7日活跃学习者",
    repeatLearners: "重复学习者",
    averageMasteryDelta: "平均掌握提升",
    pluginInstalls: "已就绪插件",
    hostedInterest: "本地意向",
    contactOptional: "联系方式（可选，仅保存 hash）",
    interestComment: "备注（可选，只记录是否填写）",
    recordInterest: "记录本地意向",
    interestRecorded: "已记录本地意向",
    exportConsent: "我同意生成仅含聚合数据的 PMF 分享包。",
    exportPmf: "生成分享包",
    exportReady: "分享包已生成",
    exportBlocked: "请先确认分享同意。",
    exportDestination: "分享目的",
    exportSchema: "导出版本",
    localOnly: "本地保存",
    noRawContact: "不保存原始联系方式",
    noRawLearningData: "不暴露正文、答案或洞察",
    services: {
      neural_sync: "Neural Sync",
      neural_publish: "Neural Publish",
      neural_teams: "Neural Teams",
      catalyst: "Catalyst",
      hosted_alpha: "Hosted Alpha"
    },
    loadingInterest: "正在记录意向",
    loadingExport: "正在生成分享包"
  },
  en: {
    appMode: "Local-first learning system",
    navLearn: "Learn",
    navAgent: "Agent",
    navLaunch: "Launch",
    navLearnHint: "Natural-language study space",
    navAgentHint: "Connect your own reasoning system",
    navLaunchHint: "Local PMF and deploy signals",
    workspaceLabel: "Local workspace",
    recent: "Recent",
    emptyRecent: "No learning sessions yet.",
    refresh: "Refresh",
    learnTitle: "What do you want to learn today?",
    learnSubtitle: "Paste source material or describe a goal. Study Anything turns it into grounded practice and tracks mastery.",
    agentReady: "Agent connected",
    demoAgentReady: "Demo Agent ready",
    agentMissing: "Agent not connected",
    setupTitle: "Start here",
    setupLead: "Run the demo loop first, then move real reasoning into your own agent.",
    setupDemoTitle: "1. Run the local demo",
    setupDemoBody: "No key required. Verify quiz, answer, grading, and mastery updates.",
    setupSourceTitle: "2. Use your material",
    setupSourceBody: "Paste notes, readings, or docs. Questions stay bound to the source.",
    setupAgentTitle: "3. Connect your agent",
    setupAgentBody: "Keep real models, tools, and credentials inside your gateway.",
    runDemo: "Run demo",
    useOwnNotes: "Use my notes",
    connectAgent: "Connect agent",
    dismissGuide: "Later",
    inputPlaceholder: "Example: help me study this passage, generate a quiz, and evaluate my mastery after I answer.",
    answerPlaceholder: "Answer the current question. The system will grade it against the source and rubric.",
    answerRequired: "Write your answer before submitting it for grading.",
    start: "Start learning",
    answer: "Submit answer",
    useSource: "Use study material",
    newRound: "New study",
    sourceTitle: "Study Material",
    title: "Title",
    reference: "Source",
    sourceText: "Text",
    sourceTextPlaceholder: "Paste the material you want to study. Notes, paper excerpts, docs, and course snippets all work.",
    sourceRequired: "Paste study material first, or describe what you want to learn above.",
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
    welcome: "Put learning material into the input box, or start from the source area.",
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
    agentSetupHint: "If you do not have your own agent yet, keep using the demo agent. Once you save an HTTP agent, future learning uses it by default.",
    pluginTrustTitle: "Plugin Trust and Install",
    pluginTrustLead: "Install only a local plugin directory you explicitly choose. Study Anything validates the manifest and asks you to confirm permissions first.",
    pluginSourcePath: "Plugin directory",
    pluginPathPlaceholder: "Example: plugins/example-exporter or /path/to/plugin",
    pluginPathRequired: "Enter a local plugin directory first.",
    previewPlugin: "Preview permissions",
    installPlugin: "Confirm and install",
    installedPlugins: "Discovered plugins",
    noPlugins: "No plugins discovered.",
    pluginPermissions: "Requested permissions",
    pluginConfirmHint: "Check each permission before installing. Install copies files only; it does not download or execute plugin code.",
    pluginInstallBlocked: "Confirm every permission first.",
    pluginInstalled: "Plugin installed",
    pluginHooks: "Hooks",
    pluginInstallDir: "Install directory",
    pluginRiskLevel: "Risk level",
    pluginReviewStatus: "Review status",
    pluginSignatureStatus: "Signature status",
    pluginRecommendation: "Recommendation",
    pluginDigest: "Source digest",
    pluginWarnings: "Warnings",
    permissionRisk: "Risk",
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
    loadingPluginPreview: "Reading plugin manifest",
    loadingPluginInstall: "Installing plugin",
    loadingRefresh: "Refreshing",
    launchTitle: "Launch Readiness Is Measured",
    launchLead: "Read local aggregate signals for the learning loop, repeat usage, and plugin ecosystem without uploading source text, answers, insights, or raw contact details.",
    launchSignalTitle: "PMF Signals",
    launchPrivacyTitle: "Privacy Boundary",
    launchInterestTitle: "Future Service Interest",
    launchInterestLead: "Optionally record interest in Sync, Publish, Teams, or Catalyst. The record stays on this machine.",
    launchExportTitle: "Share PMF Package",
    launchExportLead: "Generate a shareable aggregate package for community PMF feedback or hosted waitlist review. Explicit consent is required.",
    completedSessions: "Completed sessions",
    completionRate: "Completion rate",
    activeLearners: "7d active learners",
    repeatLearners: "Repeat learners",
    averageMasteryDelta: "Avg mastery delta",
    pluginInstalls: "Ready plugins",
    hostedInterest: "Local interest",
    contactOptional: "Contact (optional, hash only)",
    interestComment: "Comment (optional, presence only)",
    recordInterest: "Record local interest",
    interestRecorded: "Local interest recorded",
    exportConsent: "I consent to generate a PMF package containing aggregate data only.",
    exportPmf: "Generate package",
    exportReady: "Share package generated",
    exportBlocked: "Confirm sharing consent first.",
    exportDestination: "Destination",
    exportSchema: "Export schema",
    localOnly: "Local only",
    noRawContact: "No raw contact stored",
    noRawLearningData: "No source text, answers, or insights exposed",
    services: {
      neural_sync: "Neural Sync",
      neural_publish: "Neural Publish",
      neural_teams: "Neural Teams",
      catalyst: "Catalyst",
      hosted_alpha: "Hosted Alpha"
    },
    loadingInterest: "Recording interest",
    loadingExport: "Generating share package"
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

function formatPercent(value = 0) {
  return `${Math.round(value * 100)}%`;
}

function formatDigest(value: string | null) {
  if (!value) return "n/a";
  if (value.length <= 28) return value;
  return `${value.slice(0, 18)}...${value.slice(-8)}`;
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

function serviceLabel(service: string, labels: Partial<Record<string, string>>) {
  return labels[service] ?? service;
}

function App() {
  const [locale, setLocale] = useState<Locale>("zh");
  const [view, setView] = useState<ViewKey>("learn");
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [workspaceStatus, setWorkspaceStatus] = useState<WorkspaceStatus | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [hitlTasks, setHitlTasks] = useState<HitlInterrupt[]>([]);
  const [title, setTitle] = useState(DEMO_SOURCE.title);
  const [reference, setReference] = useState(DEMO_SOURCE.reference);
  const [sourceText, setSourceText] = useState(DEMO_SOURCE.text);
  const [composer, setComposer] = useState("");
  const [providerKind, setProviderKind] = useState("http_agent");
  const [providerLabel, setProviderLabel] = useState("Local HTTP Agent");
  const [providerEndpoint, setProviderEndpoint] = useState("http://127.0.0.1:8787");
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const [agentTest, setAgentTest] = useState<string | null>(null);
  const [plugins, setPlugins] = useState<PluginStatus[]>([]);
  const [pluginSourcePath, setPluginSourcePath] = useState("plugins/example-exporter");
  const [pluginPreview, setPluginPreview] = useState<PluginStatus | null>(null);
  const [confirmedPluginPermissions, setConfirmedPluginPermissions] = useState<string[]>([]);
  const [pluginInstallResult, setPluginInstallResult] = useState<string | null>(null);
  const [pmfMetrics, setPmfMetrics] = useState<PmfMetrics | null>(null);
  const [pmfSummary, setPmfSummary] = useState<PmfInterestSummary | null>(null);
  const [selectedInterestServices, setSelectedInterestServices] = useState<string[]>(["neural_sync"]);
  const [interestContact, setInterestContact] = useState("");
  const [interestComment, setInterestComment] = useState("");
  const [interestResult, setInterestResult] = useState<string | null>(null);
  const [pmfShareConsent, setPmfShareConsent] = useState(false);
  const [pmfExport, setPmfExport] = useState<PmfExport | null>(null);
  const [pmfExportResult, setPmfExportResult] = useState<string | null>(null);
  const [guideDismissed, setGuideDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("study-anything-onboarding-dismissed") === "true";
  });
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const t = copy[locale];
  const answeredIds = new Set(session?.answers.map((answer) => answer.item_id) ?? []);
  const activeQuiz = session?.quiz_items.find((item) => !answeredIds.has(item.item_id)) ?? null;
  const latestGrade = session?.grading_results[session.grading_results.length - 1] ?? null;
  const defaultQuizProviderId = agentStatus?.defaults["quiz.generate"] ?? null;
  const defaultQuizProvider =
    agentStatus?.providers.find((provider) => provider.provider_id === defaultQuizProviderId) ?? null;
  const agentReady = Boolean(defaultQuizProviderId);
  const realAgentReady = Boolean(defaultQuizProvider && defaultQuizProvider.kind !== "fake_agent");
  const firstRun = sessions.length === 0 && !session;
  const showOnboarding = firstRun && !guideDismissed;
  const sourceStats = { words: wordCount(sourceText), chars: sourceText.length };
  const previewPermissions = pluginPreview?.manifest?.permissions ?? [];
  const canInstallPlugin =
    Boolean(pluginPreview?.manifest) &&
    previewPermissions.every((permission) => confirmedPluginPermissions.includes(permission));
  const heroHint =
    view === "learn" ? t.navLearnHint : view === "agent" ? t.navAgentHint : t.navLaunchHint;
  const heroQuestion =
    view === "learn" ? t.learnTitle : view === "agent" ? t.agentTitle : t.launchTitle;
  const heroSentence =
    view === "learn" ? t.learnSubtitle : view === "agent" ? t.agentLead : t.launchLead;

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
      const [agents, workspace, sessionList, hitl, pluginList, metrics, pmfInterest] = await Promise.all([
        api<AgentStatus>("/v1/agents/status"),
        api<WorkspaceStatus>("/v1/workspaces/status"),
        api<Session[]>("/v1/sessions"),
        api<HitlInterrupt[]>("/v1/hitl"),
        api<PluginStatus[]>("/v1/plugins"),
        api<PmfMetrics>("/v1/metrics/pmf"),
        api<PmfInterestSummary>("/v1/pmf/summary")
      ]);
      setAgentStatus(agents);
      setWorkspaceStatus(workspace);
      setSessions(sessionList);
      setHitlTasks(hitl);
      setPlugins(pluginList);
      setPmfMetrics(metrics);
      setPmfSummary(pmfInterest);
      if (currentSessionId) {
        setSession(await api<Session>(`/v1/sessions/${currentSessionId}`));
      }
    });
  }

  async function startLearning(source: { title: string; reference: string; text: string }) {
    await runTask(t.loadingStart, async () => {
      const created = await api<Session>("/v1/sessions", {
        method: "POST",
        body: JSON.stringify({
          user_id: "local-user",
          track: "ACADEMIC",
          use_demo_agent: !realAgentReady,
          workspace_id: workspaceStatus?.default_workspace.workspace_id
        })
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
    if (!text.trim()) {
      setError(t.answerRequired);
      return;
    }
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
      if (!sourceText.trim()) {
        setError(t.sourceRequired);
        return;
      }
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
      text: value.length > 24 || !sourceText.trim() ? value : sourceText
    });
  }

  async function startFromSource() {
    if (!sourceText.trim()) {
      setError(t.sourceRequired);
      return;
    }
    await startLearning({ title, reference, text: sourceText });
  }

  function dismissGuide() {
    setGuideDismissed(true);
    window.localStorage.setItem("study-anything-onboarding-dismissed", "true");
  }

  function prepareOwnNotes() {
    setTitle(locale === "zh" ? "我的学习材料" : "My study material");
    setReference("local://my-notes");
    setSourceText("");
  }

  async function runDemoSource() {
    setTitle(DEMO_SOURCE.title);
    setReference(DEMO_SOURCE.reference);
    setSourceText(DEMO_SOURCE.text);
    await startLearning(DEMO_SOURCE);
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

  async function previewPlugin() {
    const sourcePath = pluginSourcePath.trim();
    if (!sourcePath) {
      setError(t.pluginPathRequired);
      return;
    }
    await runTask(t.loadingPluginPreview, async () => {
      const preview = await api<PluginStatus>("/v1/plugins/preview", {
        method: "POST",
        body: JSON.stringify({ source_path: sourcePath })
      });
      setPluginPreview(preview);
      setConfirmedPluginPermissions([]);
      setPluginInstallResult(null);
    });
  }

  function togglePluginPermission(permission: string) {
    setConfirmedPluginPermissions((current) =>
      current.includes(permission)
        ? current.filter((item) => item !== permission)
        : [...current, permission]
    );
  }

  async function installPlugin() {
    if (!pluginPreview?.manifest) return;
    if (!canInstallPlugin) {
      setError(t.pluginInstallBlocked);
      return;
    }
    await runTask(t.loadingPluginInstall, async () => {
      const installed = await api<PluginStatus>("/v1/plugins/install", {
        method: "POST",
        body: JSON.stringify({
          source_path: pluginSourcePath.trim(),
          confirmed_permissions: confirmedPluginPermissions
        })
      });
      setPluginInstallResult(`${t.pluginInstalled}: ${installed.manifest?.name ?? installed.path}`);
      setPluginPreview(null);
      setConfirmedPluginPermissions([]);
      await refresh();
    });
  }

  function toggleInterestService(service: string) {
    setSelectedInterestServices((current) =>
      current.includes(service)
        ? current.filter((item) => item !== service)
        : [...current, service]
    );
  }

  async function recordInterest() {
    const services = selectedInterestServices.length ? selectedInterestServices : ["neural_sync"];
    await runTask(t.loadingInterest, async () => {
      await api("/v1/pmf/interest", {
        method: "POST",
        body: JSON.stringify({
          user_id: "local-user",
          services,
          contact: interestContact,
          comment: interestComment,
          source: "web-ui",
          locale
        })
      });
      setInterestResult(t.interestRecorded);
      setInterestContact("");
      setInterestComment("");
      await refresh();
    });
  }

  async function createPmfExport() {
    if (!pmfShareConsent) {
      setError(t.exportBlocked);
      return;
    }
    await runTask(t.loadingExport, async () => {
      const exported = await api<PmfExport>("/v1/pmf/export", {
        method: "POST",
        body: JSON.stringify({
          consent_to_share: true,
          destination: "self_archive",
          note: "generated-from-web-ui"
        })
      });
      setPmfExport(exported);
      setPmfExportResult(t.exportReady);
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
      <div className="ambientStudy" aria-hidden="true" />

      <header className="siteHeader">
        <button className="brandButton" onClick={() => setView("learn")}>
          <div className="brandMark">SA</div>
          <div>
            <p className="eyebrow">{t.appMode}</p>
            <strong>Study Anything</strong>
          </div>
        </button>

        <nav className="navList" aria-label="Primary">
          <button className={view === "learn" ? "navItem active" : "navItem"} onClick={() => setView("learn")}>
            <span>{t.navLearn}</span>
            <small>{t.navLearnHint}</small>
          </button>
          <button className={view === "agent" ? "navItem active" : "navItem"} onClick={() => setView("agent")}>
            <span>{t.navAgent}</span>
            <small>{t.navAgentHint}</small>
          </button>
          <button className={view === "launch" ? "navItem active" : "navItem"} onClick={() => setView("launch")}>
            <span>{t.navLaunch}</span>
            <small>{t.navLaunchHint}</small>
          </button>
        </nav>

        <div className="headerTools">
          <div className="segmentedControl" aria-label="Language">
            <button className={locale === "zh" ? "active" : ""} onClick={() => setLocale("zh")}>
              中文
            </button>
            <button className={locale === "en" ? "active" : ""} onClick={() => setLocale("en")}>
              EN
            </button>
          </div>
          <span className={`statusPill ${agentReady ? "good" : "warn"}`}>
            {realAgentReady ? t.agentReady : agentReady ? t.demoAgentReady : t.agentMissing}
          </span>
          {workspaceStatus && (
            <span className="statusPill workspacePill">
              {t.workspaceLabel}: {workspaceStatus.default_workspace.name}
            </span>
          )}
        </div>
      </header>

      <section className={`heroStage ${view !== "learn" ? "agentStage" : ""}`}>
        <div className="heroCopy">
          <p className="eyebrow">{heroHint}</p>
          <h1>Study Anything</h1>
          <p className="heroQuestion">{heroQuestion}</p>
          <p className="heroSentence">{heroSentence}</p>
        </div>

        <div className="heroProduct">
          {error && <section className="notice bad">{error}</section>}
          {loading && <section className="notice neutral">{loading}</section>}

          {view === "learn" ? (
            <LearningWorkspace
              activeQuiz={activeQuiz}
              composer={composer}
              hitlTasks={hitlTasks}
              onConnectAgent={() => setView("agent")}
              latestGrade={latestGrade}
              onComposerChange={setComposer}
              onDismissGuide={dismissGuide}
              onResolve={resolveTask}
              onStartFromSource={startFromSource}
              onRunDemo={runDemoSource}
              onUseOwnNotes={prepareOwnNotes}
              onSubmit={handleComposer}
              progress={progressFor(session?.stage)}
              realAgentReady={realAgentReady}
              reference={reference}
              session={session}
              setReference={setReference}
              setSourceText={setSourceText}
              setTitle={setTitle}
              sourceStats={sourceStats}
              sourceText={sourceText}
              showOnboarding={showOnboarding}
              t={t}
              title={title}
            />
          ) : view === "agent" ? (
            <AgentWorkspace
              agentStatus={agentStatus}
              agentTest={agentTest}
              canInstallPlugin={canInstallPlugin}
              confirmedPluginPermissions={confirmedPluginPermissions}
              installPlugin={installPlugin}
              pluginInstallResult={pluginInstallResult}
              pluginPreview={pluginPreview}
              plugins={plugins}
              pluginSourcePath={pluginSourcePath}
              previewPlugin={previewPlugin}
              providerEndpoint={providerEndpoint}
              providerKind={providerKind}
              providerLabel={providerLabel}
              realAgentReady={realAgentReady}
              saveProvider={saveProvider}
              selectedProviderId={selectedProviderId}
              setProviderEndpoint={setProviderEndpoint}
              setProviderKind={setProviderKind}
              setProviderLabel={setProviderLabel}
              setSelectedProviderId={setSelectedProviderId}
              setPluginSourcePath={setPluginSourcePath}
              t={t}
              testProvider={testProvider}
              togglePluginPermission={togglePluginPermission}
            />
          ) : (
            <LaunchWorkspace
              interestComment={interestComment}
              interestContact={interestContact}
              interestResult={interestResult}
              metrics={pmfMetrics}
              onCreatePmfExport={createPmfExport}
              onRecordInterest={recordInterest}
              onToggleService={toggleInterestService}
              pmfExport={pmfExport}
              pmfExportResult={pmfExportResult}
              pmfShareConsent={pmfShareConsent}
              selectedServices={selectedInterestServices}
              setInterestComment={setInterestComment}
              setInterestContact={setInterestContact}
              setPmfShareConsent={setPmfShareConsent}
              summary={pmfSummary}
              t={t}
            />
          )}
        </div>
      </section>

      <section className="recentShelf" aria-label={t.recent}>
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
    </main>
  );
}

function LearningWorkspace(props: {
  activeQuiz: QuizItem | null;
  composer: string;
  hitlTasks: HitlInterrupt[];
  latestGrade: GradingResult | null;
  onConnectAgent: () => void;
  onComposerChange: (value: string) => void;
  onDismissGuide: () => void;
  onResolve: (taskId: string) => void;
  onRunDemo: () => void;
  onStartFromSource: () => void;
  onSubmit: () => void;
  onUseOwnNotes: () => void;
  progress: number;
  realAgentReady: boolean;
  reference: string;
  session: Session | null;
  setReference: (value: string) => void;
  setSourceText: (value: string) => void;
  setTitle: (value: string) => void;
  sourceStats: { words: number; chars: number };
  sourceText: string;
  showOnboarding: boolean;
  t: (typeof copy)[Locale];
  title: string;
}) {
  const {
    activeQuiz,
    composer,
    hitlTasks,
    latestGrade,
    onConnectAgent,
    onComposerChange,
    onDismissGuide,
    onResolve,
    onRunDemo,
    onStartFromSource,
    onSubmit,
    onUseOwnNotes,
    progress,
    realAgentReady,
    reference,
    session,
    setReference,
    setSourceText,
    setTitle,
    sourceStats,
    sourceText,
    showOnboarding,
    t,
    title
  } = props;
  const latestInsight = session?.insights[session.insights.length - 1];
  const openTasks = hitlTasks.filter((task) => task.status === "open");

  return (
    <div className="learningGrid">
      <section className="conversationPanel naturalComposer">
        <div className="panelHeading">
          <h3>{t.navLearn}</h3>
          <span className="statusPill">{stageLabel(session?.stage, t.stages)}</span>
        </div>
        {showOnboarding && (
          <FirstRunGuide
            onConnectAgent={onConnectAgent}
            onDismissGuide={onDismissGuide}
            onRunDemo={onRunDemo}
            onUseOwnNotes={onUseOwnNotes}
            realAgentReady={realAgentReady}
            t={t}
          />
        )}
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
            <textarea
              placeholder={t.sourceTextPlaceholder}
              value={sourceText}
              onChange={(event) => setSourceText(event.target.value)}
            />
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

function FirstRunGuide(props: {
  onConnectAgent: () => void;
  onDismissGuide: () => void;
  onRunDemo: () => void;
  onUseOwnNotes: () => void;
  realAgentReady: boolean;
  t: (typeof copy)[Locale];
}) {
  const { onConnectAgent, onDismissGuide, onRunDemo, onUseOwnNotes, realAgentReady, t } = props;

  return (
    <section className="firstRunGuide" aria-label={t.setupTitle}>
      <div className="firstRunCopy">
        <p className="eyebrow">{realAgentReady ? t.agentReady : t.demoAgentReady}</p>
        <h3>{t.setupTitle}</h3>
        <p>{t.setupLead}</p>
      </div>
      <div className="guideSteps">
        <article>
          <strong>{t.setupDemoTitle}</strong>
          <p>{t.setupDemoBody}</p>
          <button className="primary" onClick={onRunDemo}>
            {t.runDemo}
          </button>
        </article>
        <article>
          <strong>{t.setupSourceTitle}</strong>
          <p>{t.setupSourceBody}</p>
          <button onClick={onUseOwnNotes}>{t.useOwnNotes}</button>
        </article>
        <article>
          <strong>{t.setupAgentTitle}</strong>
          <p>{t.setupAgentBody}</p>
          <button onClick={onConnectAgent}>{t.connectAgent}</button>
        </article>
      </div>
      <button className="textButton" onClick={onDismissGuide}>
        {t.dismissGuide}
      </button>
    </section>
  );
}

function LaunchWorkspace(props: {
  interestComment: string;
  interestContact: string;
  interestResult: string | null;
  metrics: PmfMetrics | null;
  onCreatePmfExport: () => void;
  onRecordInterest: () => void;
  onToggleService: (service: string) => void;
  pmfExport: PmfExport | null;
  pmfExportResult: string | null;
  pmfShareConsent: boolean;
  selectedServices: string[];
  setInterestComment: (value: string) => void;
  setInterestContact: (value: string) => void;
  setPmfShareConsent: (value: boolean) => void;
  summary: PmfInterestSummary | null;
  t: (typeof copy)[Locale];
}) {
  const {
    interestComment,
    interestContact,
    interestResult,
    metrics,
    onCreatePmfExport,
    onRecordInterest,
    onToggleService,
    pmfExport,
    pmfExportResult,
    pmfShareConsent,
    selectedServices,
    setInterestComment,
    setInterestContact,
    setPmfShareConsent,
    summary,
    t
  } = props;
  const interestSummary = summary ?? metrics?.hosted_interest ?? null;
  const metricItems = [
    { label: t.completedSessions, value: metrics?.sessions.completed ?? 0 },
    { label: t.completionRate, value: formatPercent(metrics?.sessions.completion_rate ?? 0) },
    { label: t.activeLearners, value: metrics?.learners.active_7d ?? 0 },
    { label: t.repeatLearners, value: metrics?.learners.repeat ?? 0 },
    { label: t.averageMasteryDelta, value: (metrics?.learning.average_mastery_delta ?? 0).toFixed(2) },
    { label: t.pluginInstalls, value: metrics?.plugins.ready ?? 0 },
    { label: t.hostedInterest, value: interestSummary?.total ?? 0 }
  ];

  return (
    <div className="launchGrid">
      <section className="conversationPanel launchSignals">
        <div className="panelHeading">
          <h3>{t.launchSignalTitle}</h3>
          <span className="statusPill good">pmf-v1</span>
        </div>
        <div className="metricBoard">
          {metricItems.map((item) => (
            <article className="metricTile" key={item.label}>
              <strong>{item.value}</strong>
              <span>{item.label}</span>
            </article>
          ))}
        </div>
        <p className="feedbackText">
          {metrics ? `${t.localOnly} · ${formatTime(metrics.generated_at)}` : t.loadingRefresh}
        </p>
      </section>

      <section className="sidePanel privacyPanel">
        <h3>{t.launchPrivacyTitle}</h3>
        <div className="privacyList">
          <span>{t.localOnly}</span>
          <span>{t.noRawContact}</span>
          <span>{t.noRawLearningData}</span>
        </div>
        <p className="feedbackText">
          {metrics?.privacy.privacy_exclusions.slice(0, 6).join(" · ") ?? ""}
        </p>
        <div className="exportPanel">
          <h3>{t.launchExportTitle}</h3>
          <p className="pluginMeta">{t.launchExportLead}</p>
          <label className="interestChoice">
            <input
              checked={pmfShareConsent}
              onChange={(event) => setPmfShareConsent(event.target.checked)}
              type="checkbox"
            />
            <span>{t.exportConsent}</span>
          </label>
          <button disabled={!pmfShareConsent} onClick={onCreatePmfExport}>
            {t.exportPmf}
          </button>
          {pmfExportResult && <p className="feedbackText good">{pmfExportResult}</p>}
          {pmfExport && (
            <dl className="exportSummary">
              <dt>{t.exportSchema}</dt>
              <dd>{pmfExport.schema_version}</dd>
              <dt>{t.exportDestination}</dt>
              <dd>{pmfExport.destination}</dd>
              <dt>{t.completedSessions}</dt>
              <dd>{pmfExport.metrics.sessions.completed ?? 0}</dd>
              <dt>{t.hostedInterest}</dt>
              <dd>{pmfExport.hosted_interest.total}</dd>
            </dl>
          )}
        </div>
      </section>

      <section className="sidePanel interestPanel">
        <h3>{t.launchInterestTitle}</h3>
        <p className="pluginMeta">{t.launchInterestLead}</p>
        <div className="interestChoices">
          {INTEREST_SERVICES.map((service) => (
            <label className="interestChoice" key={service}>
              <input
                checked={selectedServices.includes(service)}
                onChange={() => onToggleService(service)}
                type="checkbox"
              />
              <span>{serviceLabel(service, t.services)}</span>
            </label>
          ))}
        </div>
        <label>
          {t.contactOptional}
          <input value={interestContact} onChange={(event) => setInterestContact(event.target.value)} />
        </label>
        <label>
          {t.interestComment}
          <textarea value={interestComment} onChange={(event) => setInterestComment(event.target.value)} />
        </label>
        <button className="primary" onClick={onRecordInterest}>
          {t.recordInterest}
        </button>
        {interestResult && <p className="feedbackText good">{interestResult}</p>}
      </section>
    </div>
  );
}

function AgentWorkspace(props: {
  agentStatus: AgentStatus | null;
  agentTest: string | null;
  canInstallPlugin: boolean;
  confirmedPluginPermissions: string[];
  installPlugin: () => void;
  pluginInstallResult: string | null;
  pluginPreview: PluginStatus | null;
  plugins: PluginStatus[];
  pluginSourcePath: string;
  previewPlugin: () => void;
  providerEndpoint: string;
  providerKind: string;
  providerLabel: string;
  realAgentReady: boolean;
  saveProvider: () => void;
  selectedProviderId: string | null;
  setProviderEndpoint: (value: string) => void;
  setProviderKind: (value: string) => void;
  setProviderLabel: (value: string) => void;
  setSelectedProviderId: (value: string | null) => void;
  setPluginSourcePath: (value: string) => void;
  t: (typeof copy)[Locale];
  testProvider: (providerId?: string | null) => void;
  togglePluginPermission: (permission: string) => void;
}) {
  const {
    agentStatus,
    agentTest,
    canInstallPlugin,
    confirmedPluginPermissions,
    installPlugin,
    pluginInstallResult,
    pluginPreview,
    plugins,
    pluginSourcePath,
    previewPlugin,
    providerEndpoint,
    providerKind,
    providerLabel,
    realAgentReady,
    saveProvider,
    selectedProviderId,
    setProviderEndpoint,
    setProviderKind,
    setProviderLabel,
    setSelectedProviderId,
    setPluginSourcePath,
    t,
    testProvider,
    togglePluginPermission
  } = props;
  const previewManifest = pluginPreview?.manifest;

  return (
    <div className="agentGrid">
      <section className="conversationPanel agentIntro">
        <h3>{t.agentTitle}</h3>
        <div className="trustNote">{t.noSecrets}</div>
        <p className={`agentModeNote ${realAgentReady ? "good" : ""}`}>
          {realAgentReady ? t.agentReady : t.agentSetupHint}
        </p>
        <p className="capabilitySentence">{t.capabilityLabels.join(" · ")}</p>
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

      <section className="sidePanel pluginTrust">
        <div className="pluginInstall">
          <div>
            <h3>{t.pluginTrustTitle}</h3>
            <p>{t.pluginTrustLead}</p>
          </div>
          <label>
            {t.pluginSourcePath}
            <input
              placeholder={t.pluginPathPlaceholder}
              value={pluginSourcePath}
              onChange={(event) => setPluginSourcePath(event.target.value)}
            />
          </label>
          <div className="composerActions">
            <button onClick={previewPlugin}>{t.previewPlugin}</button>
            <button className="primary" disabled={!canInstallPlugin} onClick={installPlugin}>
              {t.installPlugin}
            </button>
          </div>
          {pluginPreview && (
            <div className="permissionReview">
              <div className="panelHeading">
                <h3>{previewManifest?.name ?? pluginPreview.status}</h3>
                <span className={`statusPill ${pluginPreview.status === "ready" ? "good" : "warn"}`}>
                  {pluginPreview.status}
                </span>
              </div>
              <small>{pluginPreview.message}</small>
              {previewManifest && (
                <>
                  <p className="pluginMeta">
                    {t.pluginHooks}: {previewManifest.hooks.join(", ")}
                  </p>
                  {pluginPreview.trust && (
                    <div className="trustSummary">
                      <div>
                        <small>{t.pluginRiskLevel}</small>
                        <strong>{pluginPreview.trust.risk_level}</strong>
                      </div>
                      <div>
                        <small>{t.pluginReviewStatus}</small>
                        <strong>{pluginPreview.trust.review_status}</strong>
                      </div>
                      <div>
                        <small>{t.pluginSignatureStatus}</small>
                        <strong>{pluginPreview.trust.signature_status}</strong>
                      </div>
                      <div>
                        <small>{t.pluginRecommendation}</small>
                        <strong>{pluginPreview.trust.install_recommendation}</strong>
                      </div>
                      <div className="trustDigest">
                        <small>{t.pluginDigest}</small>
                        <strong>{formatDigest(pluginPreview.trust.source_digest)}</strong>
                      </div>
                      {pluginPreview.trust.warnings.length > 0 && (
                        <p className="pluginMeta">
                          {t.pluginWarnings}: {pluginPreview.trust.warnings.join(" ")}
                        </p>
                      )}
                    </div>
                  )}
                  <strong>{t.pluginPermissions}</strong>
                  <div className="permissionList">
                    {pluginPreview.permission_details.map((detail) => (
                      <label className={`permissionItem ${detail.risk}`} key={detail.permission}>
                        <input
                          checked={confirmedPluginPermissions.includes(detail.permission)}
                          onChange={() => togglePluginPermission(detail.permission)}
                          type="checkbox"
                        />
                        <span>
                          <b>{detail.label}</b>
                          <small>
                            {detail.permission} · {t.permissionRisk}: {detail.risk}
                          </small>
                          <p>{detail.description}</p>
                        </span>
                      </label>
                    ))}
                  </div>
                  <p className="feedbackText">{t.pluginConfirmHint}</p>
                  {pluginPreview.install_dir && (
                    <small>
                      {t.pluginInstallDir}: {pluginPreview.install_dir}
                    </small>
                  )}
                </>
              )}
            </div>
          )}
          {pluginInstallResult && <p className="feedbackText good">{pluginInstallResult}</p>}
        </div>

        <div className="pluginDiscovery">
          <h3>{t.installedPlugins}</h3>
          <div className="providerList">
            {plugins.map((plugin) => (
              <div className="providerCard pluginCard" key={`${plugin.path}-${plugin.manifest?.plugin_id ?? plugin.status}`}>
                <strong>{plugin.manifest?.name ?? plugin.path}</strong>
                <small>{plugin.manifest?.plugin_id ?? plugin.message}</small>
                {plugin.manifest && <small>{plugin.manifest.permissions.join(" · ")}</small>}
                {plugin.trust && (
                  <small>
                    {t.pluginRiskLevel}: {plugin.trust.risk_level} · {t.pluginRecommendation}:{" "}
                    {plugin.trust.install_recommendation}
                  </small>
                )}
                <small>{plugin.path}</small>
              </div>
            ))}
            {plugins.length === 0 && <p className="emptyState">{t.noPlugins}</p>}
          </div>
        </div>
      </section>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
