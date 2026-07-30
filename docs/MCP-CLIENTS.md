# MCP 客户端接入

QMT-MCP 暴露的是 streamable HTTP MCP endpoint：

```text
http://<host>:18765/mcp
Authorization: Bearer <QMT_MCP_TOKEN>
```

服务端主推最新稳定协议 `2026-07-28`：新客户端走
`server/discover` 和无会话请求；尚未升级的客户端仍可在同一个 `/mcp`
地址使用 `2025-11-25`、`2025-06-18` 或 `2025-03-26`
initialize/session 流程，不需要改连接 URL。`qmtctl` 也会先尝试新版并自动回退。

先确认服务已经起来：

```bash
curl -fsS http://<host>:18765/livez
```

容器重建后需要先 RDP 登录一次 QMT 桌面，MCP 会随桌面会话 autostart。

## 认证模式

默认模式仍然是静态 bearer token，适合个人 NAS、内网和受控客户端：

```text
Authorization: Bearer <QMT_MCP_TOKEN>
```

为了兼容支持 OAuth 发现流程的新 MCP 客户端，QMT-MCP 也可以作为 OAuth 2.1 protected resource server 暴露资源元数据。它不负责登录页、授权码、刷新 token 或动态注册；这些仍由外部 authorization server 提供。

启用 discovery metadata：

```env
QMT_MCP_PUBLIC_BASE_URL=https://qmt.example.com
QMT_MCP_OAUTH_AUTHORIZATION_SERVERS=https://auth.example.com
QMT_MCP_OAUTH_SCOPES=qmt:read
QMT_MCP_OAUTH_RESOURCE=https://qmt.example.com/mcp
QMT_MCP_OAUTH_RESOURCE_NAME=QMT MCP
```

启用后，客户端可以访问：

```text
https://qmt.example.com/.well-known/oauth-protected-resource
```

未授权请求会收到类似下面的 challenge：

```text
WWW-Authenticate: Bearer resource_metadata="https://qmt.example.com/.well-known/oauth-protected-resource", scope="qmt:read"
```

这对接的是 MCP 2025 之后的授权发现模型：MCP server 作为 resource server，authorization server 负责发 token，客户端通过 Protected Resource Metadata 找到授权服务器。生产环境应放在 HTTPS 后面，并让授权服务器签发 audience/resource 绑定到该 MCP endpoint 的 token。

当前边界要特别注意：

- 服务端已支持 Protected Resource Metadata 和 `WWW-Authenticate` discovery。
- `qmtctl` 已支持 `auth discover`，也能发送已有 OAuth access token。
- QMT-MCP 本身还没有 authorization code、动态客户端注册、token refresh 或
  JWT/JWKS 验证；正式 OAuth access token 应由前置网关验证并转成当前服务接受的
  bearer，完整内置 OAuth 仍是后续功能。

## Codex

Codex CLI 和 Codex Desktop 共用 `~/.codex/config.toml` 里的 MCP 配置。推荐不要把 token 明文写进配置，而是让 Codex 从环境变量读取：

```toml
[mcp_servers.qmt]
enabled = true
url = "http://<host>:18765/mcp"
bearer_token_env_var = "QMT_MCP_TOKEN"
```

启动 Codex 前设置：

```bash
export QMT_MCP_TOKEN=<token>
codex
```

检查：

```bash
codex mcp list
```

也可以先用 CLI 添加 URL，再手动补 `bearer_token_env_var`：

```bash
codex mcp add qmt --url http://<host>:18765/mcp
```

## Claude Code

本机个人配置：

```bash
export QMT_MCP_TOKEN=<token>
claude mcp add --transport http qmt http://<host>:18765/mcp \
  --header "Authorization: Bearer ${QMT_MCP_TOKEN}"
```

团队项目配置可以放在仓库根目录 `.mcp.json`。不要提交真实 token，使用环境变量占位：

```json
{
  "mcpServers": {
    "qmt": {
      "type": "http",
      "url": "http://<host>:18765/mcp",
      "headers": {
        "Authorization": "Bearer ${QMT_MCP_TOKEN}"
      }
    }
  }
}
```

在 Claude Code 里运行：

```text
/mcp
```

确认 `qmt` 已连接并允许需要的工具。

## WorkBuddy

如果 WorkBuddy 支持 streamable HTTP MCP，按下面的通用配置接入：

```json
{
  "mcpServers": {
    "qmt": {
      "type": "http",
      "url": "http://<host>:18765/mcp",
      "headers": {
        "Authorization": "Bearer ${QMT_MCP_TOKEN}"
      }
    }
  }
}
```

有些客户端使用 `transport` 字段：

```json
{
  "mcpServers": {
    "qmt": {
      "transport": "streamable-http",
      "url": "http://<host>:18765/mcp",
      "headers": {
        "Authorization": "Bearer ${QMT_MCP_TOKEN}"
      }
    }
  }
}
```

如果 WorkBuddy 只支持 SSE transport，当前 QMT-MCP 不能直接连接；需要后续加 SSE bridge 或客户端升级到 streamable HTTP。

如果 WorkBuddy 支持 OAuth MCP discovery，优先配置 `url` 指向 `/mcp`，并在服务端设置上面的 `QMT_MCP_OAUTH_*` 变量；WorkBuddy 应通过 401 challenge 或 `.well-known/oauth-protected-resource` 自动发现 authorization server。若它只支持手填 header，则继续使用静态 bearer token 模式。

## 验证工具

接入成功后，客户端应能看到这些工具族：

- `qmt_health` / `qmt_capabilities`
- `qmt_xtdata_search_instruments`
- `qmt_xtdata_snapshot`
- `qmt_xtdata_bars`
- `qmt_xtdata_quote_subscribe`
- `qmt_xtdata_option_chain`
- `qmt_xtdata_volatility_index_inputs`

也可以用 `qmtctl` 做同样的连通性检查：

```bash
cd cli/qmtctl && go build -o qmtctl .
QMT_MCP_URL=http://<host>:18765/mcp QMT_MCP_TOKEN=<token> ./qmtctl health
QMT_MCP_URL=http://<host>:18765/mcp QMT_MCP_TOKEN=<token> ./qmtctl tools
```

检查 OAuth discovery 或使用网关签发的 access token：

```bash
QMT_MCP_URL=https://qmt.example.com/mcp ./qmtctl auth discover --json
QMT_MCP_URL=https://qmt.example.com/mcp \
  QMT_MCP_ACCESS_TOKEN=<access-token> ./qmtctl health
```

## 常见问题

| 现象 | 处理 |
|---|---|
| `connection refused` | 容器起来后还没 RDP 登录；登录 QMT 桌面，等待 MCP autostart。 |
| `401` / unauthorized | token 不对，确认客户端传了 `Authorization: Bearer ...`。 |
| 能连上但没有行情 | QMT 未登录或 xtdata 未 ready；看 `qmt_health` 的 readiness。 |
| Claude Code 看不到工具 | 运行 `/mcp` 检查 server 状态和权限；确认 scope 是当前项目可见的配置。 |
| Codex 看不到工具 | 确认 `~/.codex/config.toml` 里 `bearer_token_env_var` 是环境变量名，不是 token 值。 |
| OAuth 客户端找不到授权服务器 | 确认 `QMT_MCP_PUBLIC_BASE_URL` 是客户端可访问的 HTTPS 外部地址，并配置了 `QMT_MCP_OAUTH_AUTHORIZATION_SERVERS`。 |
| OAuth 登录成功但 MCP 仍 401 | 授权服务器签发的 token 没有被当前 bearer gate 接受；需要在网关层把 OAuth token 兑换/校验后转成 MCP 可接受的 bearer，或后续接入 JWT/JWKS 校验。 |
