#!/bin/zsh
set -u

cd "$(dirname "$0")" || exit 1

clear
cat <<'EOF'
Study Anything 一键启动

你不用先懂 Docker、Agent、API Key 或模型配置。
这个窗口会自动跑一次本地学习 demo。

成功标志：
  Done. You have proved the local learning loop once.

现在开始。

EOF

if ./scripts/start_here.sh --demo; then
  cat <<'EOF'

启动成功。

下一步只选一个：
  1. 想正式让本地学习引擎保持运行：
     ./scripts/start_here.sh --keep-running

  2. 想给 Kimi / Codex / WorkBuddy 调用：
     先保持本地学习引擎运行，再让它们调用本地 API。

  3. 想看超短说明：
     打开 QUICKSTART.md

EOF
else
  cat <<'EOF'

启动没有成功，但先不要乱改配置。

按这个顺序做：
  1. 确认你在普通终端里运行，不是在会禁止 localhost 的沙箱里。
  2. 运行：./scripts/start_here.sh --check-only
  3. 运行：python3 scripts/diagnose_adoption.py
  4. 把脱敏报告发给维护者，不要贴学习材料、答案或模型 Key。

EOF
fi

printf "按回车关闭这个窗口..."
IFS= read -r _ || true
