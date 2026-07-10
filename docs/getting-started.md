# Study Anything 新手入门

这份指南只解决一件事：第一次把 Study Anything 跑起来，并完成一次本地学习闭环。

默认路径不需要 Docker，不需要真实模型 API Key，也不需要先理解 Agent 架构。

## 先做这一件事

如果你在 macOS 上，直接双击根目录里的：

```text
START_HERE.command
```

如果你更习惯终端，再运行这一条：

```bash
./scripts/start_here.sh
```

它会自动运行零配置 demo：

1. 创建或复用本地 Python 环境。
2. 启动临时 Skill Mode API。
3. 跑一次确定性的学习流。
4. 验证 CLI、Agent eval、学习导出和基础证据。
5. 自动停止临时 API。

看到这句就表示第一次验收通过：

```text
Done. You have proved the local learning loop once.
```

第一次不要配置模型 Key，不要先开 Docker，也不要先接 Kimi/Codex/WorkBuddy。

## 你现在处在哪种模式

| 你想做什么 | 命令 |
| --- | --- |
| 只验证项目能跑 | `./scripts/start_here.sh` |
| 保持本地 API 常驻 | `./scripts/start_here.sh --keep-running` |
| Agent shell 不保活后台进程 | `./scripts/start_here.sh --foreground` |
| 只在沙箱里验证无 socket 契约 | `./scripts/start_here.sh --check-only` |
| 检查本机环境问题 | `./scripts/start_here.sh --doctor` |
| 启动 Docker 自托管 | `./scripts/start_here.sh --docker` |

## 持久运行

如果你想让 Kimi Work、Codex、WorkBuddy 或自己的终端 Agent 调用本地学习 API：

```bash
./scripts/start_here.sh --keep-running
```

然后试一下：

```bash
python3 scripts/study_anything_cli.py health
python3 scripts/study_anything_cli.py demo
```

停止：

```bash
./scripts/stop_skill_mode.sh
```

如果你在 Codex、Kimi Work、WorkBuddy 或其他 Agent shell 里发现命令结束后 API 也消失了，
改用前台模式：

```bash
./scripts/start_here.sh --foreground
```

保持这个终端打开，再让另一个终端或平台 Agent 调用本地 API。停止时按 `Ctrl-C`。

## 跑自己的第一课

常驻 API 启动后，可以直接用一条命令创建小课：

```bash
python3 scripts/study_anything_cli.py lesson \
  --title "检索练习" \
  --reference "local://retrieval-practice" \
  --text "检索练习通过主动回忆帮助学习者巩固长期记忆。" \
  --answer "主动回忆会加强记忆提取路径。"
```

查看结果：

```bash
python3 scripts/study_anything_cli.py sessions
python3 scripts/study_anything_cli.py show SESSION_ID
python3 scripts/study_anything_cli.py mastery SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
```

`SESSION_ID` 用上一步输出里的真实 id 替换。

## 接入自己的 Agent

Study Anything 不保存真实模型 API Key。真实推理由你自己的 Agent 或平台 Agent 负责。

先用零 key 网关验证本地通路：

```bash
AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --port 8787
```

保持这个终端打开，在另一个终端注册：

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --endpoint "http://127.0.0.1:8787/invoke" \
  --set-default

python3 scripts/study_anything_cli.py agent-test
```

真实模型接入时，把 `AGENT_LLM_BASE_URL`、`AGENT_LLM_API_KEY`、`AGENT_LLM_MODEL` 放在你的
Agent/Gateway 环境里，不要放进 Study Anything 的学习数据或公开支持材料。

## Docker 自托管

第一次不建议从 Docker 开始。确认 Skill Mode 能跑后，再执行：

```bash
./scripts/start_here.sh --docker
```

这个模式会依次运行 `.env` 生成、环境检查、`doctor.sh` 和 Docker Compose 启动。

如果 Docker Desktop 没启动，回到最小路径：

```bash
./scripts/start_here.sh --demo
```

## 常见失败

| 现象 | 先做什么 |
| --- | --- |
| `localhost_socket_blocked` | 在当前沙箱跑 `./scripts/start_here.sh --check-only`，再去正常终端跑 `./scripts/start_here.sh` |
| `API_PORT` 无效 | `unset API_PORT && ./scripts/start_here.sh` |
| 端口被占用 | `API_PORT=8013 ./scripts/start_here.sh` |
| Python 版本不受支持 | 安装 Python 3.11 或 3.12，或 `PYTHON_BIN=/path/to/python3.11 ./scripts/start_here.sh` |
| 依赖安装失败或下载超时 | 换到有网络的终端，配置 `PIP_INDEX_URL`，或用 `SKILL_PIP_INSTALL_TIMEOUT_SECONDS=1200 ./scripts/start_here.sh` 给慢网络更多时间 |
| Docker 报错 | 先启动 Docker Desktop；不想用 Docker 就跑 `./scripts/start_here.sh --demo` |
| Agent `502 Bad Gateway` | 先用 `AGENT_GATEWAY_MODE=dry_run`，再 `agent-test` |

沙箱里不能开 localhost socket 时，至少先跑：

```bash
python3 scripts/verify_openai_compatible_gateway.py --contract-only
python3 scripts/verify_agent_gateway_hardening.py --contract-only
python3 scripts/verify_external_agent_adapter_hardening.py --contract-only
```

这些检查只证明无 socket 代码契约，不替代正常终端里的 runtime smoke。

## 支持信息

遇到问题先生成脱敏报告：

```bash
python3 scripts/diagnose_adoption.py
```

不要把以下内容贴到公开 issue：

- 原始学习材料全文
- 学员答案
- 真实模型 API Key
- 私有 Agent endpoint
- 浏览器、视频、应用上下文原文
- 本机绝对路径
