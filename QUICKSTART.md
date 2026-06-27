# Study Anything 一分钟启动

这页只给第一次使用的人看。

## 你只需要做一件事

双击根目录里的：

```text
START_HERE.command
```

如果你不想双击，也可以在终端运行：

```bash
./scripts/start_here.sh
```

## 看到哪句话算成功

看到这句就成功：

```text
Done. You have proved the local learning loop once.
```

第一次启动不需要：

- Docker
- 真实模型 API Key
- Kimi
- Codex
- WorkBuddy
- 浏览器插件
- 任何云账号

## 成功后怎么正式用

让本地学习引擎一直开着：

```bash
./scripts/start_here.sh --keep-running
```

然后你可以让 Kimi、Codex、WorkBuddy 或自己的 Agent 调用它。

如果你的 Agent 运行环境会自动关掉后台进程，改用：

```bash
./scripts/start_here.sh --foreground
```

保持这个终端窗口打开。

## 失败了怎么办

不要先改代码，不要先配置模型 Key。

按顺序运行：

```bash
./scripts/start_here.sh --check-only
python3 scripts/diagnose_adoption.py
```

把脱敏报告发给维护者。

不要公开粘贴：

- 原始学习材料
- 你的答案
- 模型 API Key
- 私有 Agent endpoint
- 本机绝对路径

## 想看完整说明

打开：

```text
docs/getting-started.md
```
