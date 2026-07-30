# MCP 客户端接入

QMT-MCP 暴露一个 streamable HTTP endpoint：

```text
https://qmt.example.com/mcp
Authorization: Bearer <credential>
```

服务端主推最新稳定协议 `2026-07-28`。同一个 `/mcp` 自动兼容
`2025-11-25`、`2025-06-18` 和 `2025-03-26` 客户端，不需要维护两套 URL
或手动选择协议。

`tools/list` 使用标准 opaque cursor 分页，服务端决定页大小。客户端应持续请求
`nextCursor` 直到该字段缺失；qmtctl 会自动完成这个过程。服务端还会在客户端
接受 gzip 时压缩足够大的 JSON 响应，SSE 不压缩。Codex、Claude Code、
WorkBuddy 等标准 HTTP 客户端通常无需额外配置。

最小连通性检查：

```bash
curl -fsS https://qmt.example.com/livez
```

容器创建或重启后，需要先 RDP 登录一次桌面，MCP 才会随会话 autostart。

## 认证模式

| 模式 | 适用场景 | 服务端接受的凭证 |
|---|---|---|
| `static` | 个人 NAS、受控内网；默认且向后兼容 | `QMT_MCP_TOKEN` |
| `oauth` | 公网、多用户、需要最小权限 | 外部 AS 签发并由本服务用 JWKS 校验的 JWT |
| `hybrid` | 从静态 token 迁移到 OAuth | 上述两者之一 |

QMT-MCP 是 OAuth protected resource，不是 authorization server。登录页、
用户认证、同意、authorization code 和 token 签发都属于外部 AS；QMT-MCP
负责发布 RFC 9728 metadata、校验 JWT，并按 scope 裁剪工具。它不接收或转发
上游第三方服务 token。

### 静态模式

```env
QMT_MCP_AUTH_MODE=static
QMT_MCP_TOKEN=<openssl-rand-hex-32>
```

未设置 `QMT_MCP_AUTH_MODE` 时仍按 `static` 处理。

### OAuth / hybrid 模式

```env
QMT_MCP_AUTH_MODE=oauth
QMT_MCP_PUBLIC_BASE_URL=https://qmt.example.com
QMT_MCP_OAUTH_ISSUER=https://auth.example.com
QMT_MCP_OAUTH_AUTHORIZATION_SERVERS=https://auth.example.com
QMT_MCP_OAUTH_JWKS_URL=https://auth.example.com/.well-known/jwks.json
QMT_MCP_OAUTH_RESOURCE=https://qmt.example.com/mcp
QMT_MCP_OAUTH_RESOURCE_NAME=QMT MCP
QMT_MCP_OAUTH_SCOPES=qmt:read qmt:market qmt:account qmt:manage qmt:admin
QMT_MCP_OAUTH_ALGORITHMS=RS256 ES256
```

`hybrid` 使用同样的 OAuth 配置，并额外要求强 `QMT_MCP_TOKEN`。生产 URL
必须是 HTTPS；仅 loopback 开发允许 HTTP。

外部 AS 签发的 access token 必须是带 `kid` 的非对称 JWT，并包含：

- 与 `QMT_MCP_OAUTH_ISSUER` 精确相等的 `iss`
- 包含 `QMT_MCP_OAUTH_RESOURCE` 的 `aud`
- 有效的 `exp`，以及可选的 `nbf`
- `client_id` 或 `azp`
- 字符串 `scope`，或字符串数组 `scp`

服务启动时不会从不可信 token 动态发现 issuer。JWKS URL、算法、超时、响应
大小和缓存 TTL 都由运维配置钉住；新 `kid` 会触发一次受限刷新。

客户端可发现：

```text
https://qmt.example.com/.well-known/oauth-protected-resource
https://qmt.example.com/.well-known/oauth-protected-resource/mcp
```

未认证返回 401；已认证但权限不足返回 403 `insufficient_scope`，两者都带
`WWW-Authenticate` step-up 信息。

## Scope 与工具

| Scope | 可见/可调用能力 |
|---|---|
| `qmt:read` | 必选基础 scope；core 健康与能力工具 |
| `qmt:market` | xtdata 行情、搜索、期权、参考数据的只读工具 |
| `qmt:account` | xttrade 账户查询与 portfolio 分析 |
| `qmt:manage` | 在已有 family scope 上增加订阅、缓存、下载、受管板块/公式等非交易 mutation |
| `qmt:admin` | 当前启动策略允许的完整工具面 |

权限始终是多层交集：

```text
feature gate ∩ startup profile/allowlist/denylist ∩ token scope
```

因此 `qmt:admin` 不能打开服务启动时未注册或被 Profile 禁掉的工具，
`qmt:manage` 也不会独立授予行情、账户或任何交易权限。`tools/list` 会动态过滤，
`tools/call` 会再次独立校验。

## qmtctl

qmtctl 优先使用 `2026-07-28`，对旧服务自动回退到 2025 initialize/session。
`qmtctl tools` 会合并所有目录页面，并通过 Go 标准 HTTP transport 自动解压
gzip；不需要分页或压缩参数。

静态 token：

```bash
export QMT_MCP_URL=https://qmt.example.com/mcp
export QMT_MCP_TOKEN=<token>
qmtctl health
```

推荐使用 Client ID Metadata Document 启动 OAuth Authorization Code + PKCE：

```bash
qmtctl --url https://qmt.example.com/mcp auth login \
  --client-id-metadata-url https://client.example.com/qmtctl.json \
  --scope 'qmt:read qmt:market'
```

也可以使用 AS 预注册的 public client：

```bash
qmtctl --url https://qmt.example.com/mcp auth login \
  --client-id qmtctl-public \
  --scope 'qmt:read qmt:market qmt:account'
```

只有旧 AS 无法使用前两种方式时，才显式启用已弃用的 DCR 兼容路径：

```bash
qmtctl --url https://qmt.example.com/mcp auth login --dynamic-registration
```

无桌面环境加 `--no-browser`，qmtctl 会打印 URL 并继续监听 loopback callback。
会话按 resource 保存到用户配置目录，Unix 目录/文件权限为 0700/0600；refresh
token 轮换会原子写回。状态不输出 access/refresh token：

```bash
qmtctl --url https://qmt.example.com/mcp auth status
qmtctl --url https://qmt.example.com/mcp auth logout
qmtctl --url https://qmt.example.com/mcp auth discover --json
```

已有 access token 可通过 `QMT_MCP_ACCESS_TOKEN` 或 `--access-token` 传入。显式
access/static token 的优先级高于已保存 OAuth 会话。可用
`QMTCTL_AUTH_STORE` 或 `--auth-store` 修改存储路径。

## Codex

Codex CLI 与 Codex Desktop 共用 `~/.codex/config.toml`。静态 token 是兼容性
最明确的配置，token 只通过环境变量读取：

```toml
[mcp_servers.qmt]
enabled = true
url = "https://qmt.example.com/mcp"
bearer_token_env_var = "QMT_MCP_TOKEN"
```

```bash
export QMT_MCP_TOKEN=<token>
codex mcp list
```

也可以先添加 URL，再补环境变量字段：

```bash
codex mcp add qmt --url https://qmt.example.com/mcp
```

Codex 各版本对远程 MCP OAuth 的 UI/注册方式可能不同。启用前应以当前安装版本
的官方说明为准；无内置 OAuth 时可继续用静态模式，或用 qmtctl 独立完成 OAuth
连通性和 scope 验证。

## Claude Code

静态模式：

```bash
export QMT_MCP_TOKEN=<token>
claude mcp add --transport http qmt https://qmt.example.com/mcp \
  --header "Authorization: Bearer ${QMT_MCP_TOKEN}"
```

支持远程 MCP OAuth 的 Claude Code 版本可以只添加 URL，再在 `/mcp` 中选择
qmt 并完成浏览器登录：

```bash
claude mcp add --transport http qmt https://qmt.example.com/mcp
```

外部 AS 仍需允许该客户端使用的注册方式和 loopback/客户端 redirect URI。
Claude Code 会安全存储并自动刷新其自己的 token；QMT-MCP 只验证最终 JWT。
行为与命令以
[Anthropic 官方 MCP 文档](https://docs.anthropic.com/en/docs/claude-code/mcp)
为准。

团队 `.mcp.json` 不要提交真实 token：

```json
{
  "mcpServers": {
    "qmt": {
      "type": "http",
      "url": "https://qmt.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${QMT_MCP_TOKEN}"
      }
    }
  }
}
```

## WorkBuddy

确认当前版本支持 streamable HTTP 后，静态兼容配置为：

```json
{
  "mcpServers": {
    "qmt": {
      "type": "http",
      "url": "https://qmt.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${QMT_MCP_TOKEN}"
      }
    }
  }
}
```

有些版本使用 `"transport": "streamable-http"`。若当前版本明确支持远程 MCP
OAuth discovery，可只保留 URL，让客户端跟随 401 challenge 和 protected
resource metadata；否则使用静态 header。只支持旧 SSE transport 的版本不能
直连本服务。

## 常见问题

| 现象 | 处理 |
|---|---|
| `connection refused` | 先 RDP 登录桌面并等待 MCP autostart。 |
| `401 invalid_token` | 检查签名、`kid`、issuer、resource audience、时间和 JWT 算法；服务端不会在错误里泄漏细节。 |
| `403 insufficient_scope` | 按 challenge 申请缺少的 family/management scope，重新登录。 |
| OAuth 找不到 AS | 检查公开 HTTPS URL、issuer、authorization servers 和两种 RFC 9728 metadata 路径。 |
| OAuth 登录后工具很少 | 查看 token scope，再检查 startup Profile、allow/deny 与 feature gate；它们取交集。 |
| qmtctl 没复用登录 | `auth status` 检查 resource 是否完全相同；显式 token 会覆盖保存的会话。 |
| 客户端只显示部分工具 | 客户端需支持标准 `nextCursor`；先用 `qmtctl tools --json` 验证完整目录，再升级客户端。 |
| 能连上但没有行情 | QMT 未登录或 xtdata 未 ready；查看 `qmt_health`。 |
| Claude Code 看不到工具 | `/mcp` 检查连接和授权，并确认所申请 scope。 |
| Codex 看不到工具 | `bearer_token_env_var` 应是变量名，不是 token 值。 |
