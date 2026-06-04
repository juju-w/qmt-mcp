# MCP 客户端接入

QMT-MCP 暴露的是 streamable HTTP MCP endpoint：

```text
http://<host>:18765/mcp
Authorization: Bearer <QMT_MCP_TOKEN>
```

先确认服务已经起来：

```bash
curl -fsS http://<host>:18765/livez
```

容器重建后需要先 RDP 登录一次 QMT 桌面，MCP 会随桌面会话 autostart。

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

## 常见问题

| 现象 | 处理 |
|---|---|
| `connection refused` | 容器起来后还没 RDP 登录；登录 QMT 桌面，等待 MCP autostart。 |
| `401` / unauthorized | token 不对，确认客户端传了 `Authorization: Bearer ...`。 |
| 能连上但没有行情 | QMT 未登录或 xtdata 未 ready；看 `qmt_health` 的 readiness。 |
| Claude Code 看不到工具 | 运行 `/mcp` 检查 server 状态和权限；确认 scope 是当前项目可见的配置。 |
| Codex 看不到工具 | 确认 `~/.codex/config.toml` 里 `bearer_token_env_var` 是环境变量名，不是 token 值。 |
