# GitHub And Container Security Baseline

This baseline hardens the public self-host alpha without changing its local-first or Bring Your Own
Agent trust boundaries. It covers repository automation and the Study Anything API image. It does
not certify third-party services in the optional `full` profile.

## API Container

The API and mock HTTP Agent images run as fixed UID/GID `10001:10001`. Package installation and
image assembly finish before the Dockerfile drops privileges. `/data/study-anything` is the only
application data volume and is owned by that runtime identity.

Compose applies these controls to both application containers:

- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges` enabled;
- an init shim for signal and child-process handling;
- bounded `/tmp` tmpfs with `noexec`, `nosuid`, and `nodev`;
- no privileged mode, host networking, or Docker socket mount;
- loopback host publishing by default.

Verify the source policy:

```bash
python3 scripts/verify_container_security.py --check
```

For a running Compose API, verify the actual container settings as well:

```bash
container_id="$(docker compose --env-file .env \
  -f infra/compose/docker-compose.yml ps -q api)"
python3 scripts/verify_container_security.py \
  --runtime-container-id "$container_id"
```

The runtime report records only booleans. It does not retain the container ID or raw `docker
inspect` payload.

## GitHub Security Automation

All GitHub Actions references are pinned to full 40-character commit SHAs and retain a human-readable
version comment. Dependabot continues to track the `github-actions` ecosystem so updates remain
reviewable.

The `security` workflow runs:

- CodeQL for Python with the `security-extended` query suite on pull requests, `main`, manual
  dispatch, and a weekly schedule;
- GitHub Dependency Review on pull requests, blocking newly introduced high or critical
  vulnerabilities;
- the deterministic container policy verifier.

The repository setting target is:

- secret scanning enabled;
- push protection enabled;
- Actions restricted to full-SHA references;
- `main` protected with strict required checks;
- force-push and branch deletion disabled;
- stale branches deleted after merge;
- dependency graph enabled so dependency review can execute;
- Dependabot alerts and security updates enabled when the repository owner token and plan allow it.

Repository settings are external state. They are not considered complete until a live GitHub API
readback confirms them after this workflow has merged and produced its first checks.

Dependabot may identify transitive vulnerabilities that cannot be patched without an upstream
compatible release. Fixable alerts block security completion. Any unfixable alert must retain a
documented exploitability boundary, upstream reference, and follow-up owner; it must not be silently
dismissed or described as resolved.

The deterministic contract is part of CI and the release check:

```bash
python3 scripts/verify_github_security_posture.py --check
```

After the settings are applied, perform a read-only live verification:

```bash
python3 scripts/verify_github_security_posture.py --live \
  --repo jzvcpe-goat/study-anything \
  --branch main
```

## Claim Boundary

This baseline reduces common container privilege and CI supply-chain risk. CodeQL and Dependency
Review are supporting controls, not proof that the repository is vulnerability-free. A repository
wide threat-led scan, remediation of any findings, image/SBOM review, and independent external
security audit remain separate acceptance stages before a hosted production claim.

## 中文说明

API 和 mock Agent 容器现在以固定非 root 身份运行，并启用只读根文件系统、丢弃全部
capability、`no-new-privileges` 和受限 `/tmp`。GitHub Actions 全部固定到完整 commit SHA，
并新增 CodeQL 与依赖变更审查。上述措施是安全基线，不等于“无漏洞”或生产安全认证；主干
保护、Dependabot 和其他 GitHub 设置必须在合并后通过实时 API 回读验收，独立安全审计仍是
人工断点。
