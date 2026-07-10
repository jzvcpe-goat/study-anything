# Hosted Identity And Tenancy Foundation

Study Anything includes an optional hosted authentication and application-layer
tenant-isolation foundation. It is disabled by default and does not change the
account-free local-first workflow.

## Choose One Authentication Mode

| Mode | Intended use | Identity boundary |
| --- | --- | --- |
| `local_only` | Default single-user loopback use | Request `user_id` values are local labels |
| `token` | Private self-host operated by one trusted party | One shared operator token, no tenant identity |
| `oidc_jwt` | Hosted integration foundation | Signed principal and tenant claims from an external IdP |

Install the optional dependency for a source checkout:

```bash
python -m pip install -e '.[hosted]'
```

The Docker full image already installs the `full` extra, which includes the hosted
dependency.

## OIDC JWT Configuration

```bash
APP_ENV=production
API_BIND_HOST=0.0.0.0
STUDY_ANYTHING_API_AUTH_MODE=oidc_jwt
STUDY_ANYTHING_OIDC_ISSUER=https://identity.example
STUDY_ANYTHING_OIDC_AUDIENCE=study-anything-api
STUDY_ANYTHING_OIDC_TENANT_CLAIM=org_id
STUDY_ANYTHING_OIDC_JWKS_JSON={"keys":[...]}
STUDY_ANYTHING_OIDC_JWKS_FILE=
STUDY_ANYTHING_OIDC_LEEWAY_SECONDS=30
STUDY_ANYTHING_OIDC_MAX_TOKEN_AGE_SECONDS=3600
```

Configure exactly one of `STUDY_ANYTHING_OIDC_JWKS_JSON` and
`STUDY_ANYTHING_OIDC_JWKS_FILE`. Only public RSA/EC signing keys are accepted;
private JWK fields are rejected. Study Anything does not fetch JWKS or discovery
metadata over the network. Rotate the static public JWKS through deployment
configuration and restart the API.

Accepted JWTs must have:

- an `RS256` or `ES256` signature and a known `kid`;
- a `typ` header of `JWT` or `at+jwt`;
- matching `iss` and `aud` claims;
- non-empty `sub` and configured tenant claims;
- numeric `iat` and `exp` claims within the configured maximum lifetime;
- no dependence on a request-body `user_id` for authorization.

Run the preflight before starting:

```bash
python3 scripts/check_env.py --env .env --strict
```

## Isolation Behavior

Hosted principal IDs are opaque hashes bound to `issuer + tenant + subject`.
Tenant IDs are separate opaque hashes. Raw OIDC subject and tenant values are not
stored in sessions/workspaces or returned by public APIs.

- `GET /v1/identity/me` returns the authenticated opaque principal and tenant IDs.
- Session reads and lists are tenant-filtered; cross-tenant IDs return `404`.
- Workspace roles enforce `read_sessions`, `create_sessions`, `write_sessions`,
  and administrative permissions inside the authenticated tenant.
- Request-body user/owner fields cannot replace the authenticated principal.
- Non-demo Agent providers are scoped to the authenticated principal. Since the
  principal ID is tenant-bound, the same IdP subject in another tenant cannot see
  or invoke that provider.
- Agent targets remain subject to the production exact-origin allowlist.

The following global local-operator routes are blocked in hosted mode until their
storage and behavior become tenant-scoped:

- `/v1/adoption/*`
- `/v1/importers/*`
- `/v1/metrics/*`
- `/v1/pmf/*`
- `/v1/plugins/*`
- `/v1/recovery/*`
- `/v1/sync/*`

## Verification

```bash
python3 scripts/verify_hosted_identity_tenancy.py --check
python3 scripts/verify_agent_endpoint_policy.py --check
python3 scripts/verify_container_security.py --check
```

The hosted verifier generates an ephemeral signing key and temporary local stores.
It performs no model calls, external network calls, or production mutation, and its
output contains booleans only.

## Claim Boundary

This phase proves offline JWT validation and logical isolation in the API/storage
application layer. It does **not** prove managed IdP provisioning, account recovery,
SCIM, database row-level security, a database per tenant, retention/deletion
operations, billing/entitlements, production infrastructure security, penetration
testing, or an independent external audit. Hosted paid services remain `not_ready`.

## 中文说明

`oidc_jwt` 是可选的托管身份与应用层租户隔离基础，不改变默认的本地免账号模式。
系统只接受外部 IdP 签发的短期 JWT，并用 `issuer + tenant + subject` 生成不可逆的
principal ID；请求体里的 `user_id` 不能覆盖真实身份。会话按租户过滤，工作区按角色
授权，跨租户资源统一返回 `404`，用户自有 Agent 配置按 principal 隔离。

当前仍不能宣称“托管服务已经可商用”。数据库 RLS/独立租户库、账号恢复、SCIM、
保留与删除、计费、事故响应、生产基础设施验证和外部安全审计尚未完成。上述 verifier
证明的是代码层边界，不是渗透测试证书。
