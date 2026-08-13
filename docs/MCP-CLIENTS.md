# MCP 客户端接入

QMT-MCP 暴露一个 streamable HTTP endpoint：

```text
https://qmt.example.com/mcp
Authorization: Bearer <credential>
```

QMT-MCP 1.0 只支持稳定协议 `2026-07-28`，并使用无会话 Streamable HTTP。
客户端必须支持 `server/discover`、每请求 `_meta` 和标准 MCP 路由头；服务端不会
接受 2025 协议、`initialize` 生命周期或 `Mcp-Session-Id`。

从 0.x 升级时，应先升级 MCP Host 和 qmtctl，再升级服务端。旧客户端会收到
`-32022 Unsupported MCP protocol version`，不会自动建立兼容会话。

`tools/list` 使用标准 opaque cursor 分页，服务端决定页大小。客户端应持续请求
`nextCursor` 直到该字段缺失；qmtctl 会自动完成这个过程。服务端还会在客户端
接受 gzip 时压缩足够大的 JSON 响应，SSE 不压缩。Codex、Claude Code、
WorkBuddy 等标准 HTTP 客户端通常无需额外配置。

稳定版还提供 `io.modelcontextprotocol/tasks` 长任务扩展。只有明确声明该扩展
的客户端才会收到任务句柄；未声明扩展的现代客户端继续获得同步工具结果，
不会被服务端强行切换执行语义。

行情 profile 还会发布 `io.modelcontextprotocol/ui` MCP Apps 扩展。客户端声明该
扩展并在设置中包含 `text/html;profile=mcp-app` 后，调用
`qmt_xtdata_kline_chart` 可按工具 `_meta.ui.resourceUri` 读取
`ui://qmt-mcp/kline-chart-v1.html`，在沙箱 iframe 内渲染交互式 K 线。未声明 Apps
的客户端仍按普通 `tools/call` 处理，获得简短文字摘要与完整
`structuredContent`；这不是错误或降级告警。

模板与行情数据分离，客户端可以缓存版本化 HTML。模板不加载外部脚本、不访问
第三方网络，也不申请设备权限。日周月/复权切换依赖 Host 的 `serverTools`
能力；不支持时初始图表照常显示，相关控件保持不可用。

新版 Tasks 还支持任务内多轮输入。任务可进入 `input_required`，并在
`inputRequests` 中嵌入标准 MCP `{method, params}` 请求；客户端用
`tasks/update.inputResponses` 按相同键回答。这个能力同样只在上述稳定版
Tasks 路径启用，不影响未声明扩展的现代客户端。

支持订阅的稳定版客户端可以在 `subscriptions/listen` 的
`params.notifications.taskIds` 中请求任务。服务端先确认实际授权的 ID，再发送
当前和后续 `notifications/tasks` 完整状态。通知是可选加速层，不取代
`tasks/get`；只实现轮询的客户端和断线重连都继续可用。服务端不会
发送旧草案里的 `notifications/tasks/status`。

最小连通性检查：

```bash
curl -fsS https://qmt.example.com/livez
```

推荐的 `QMT_DESKTOP_MODE=persistent` 会在容器启动时创建桌面并启动 MCP，不需要
先连接 RDP；但券商 QMT 仍可能要求人工登录，此前行情工具会报告 degraded。
兼容模式 `manual` 才需要先 RDP 登录来触发 autostart。

需要客户端保存桌面密码或使用 Android/轻量客户端时，可叠加
`docker-compose.vnc.yml`。VNC 与 RDP 连接同一个持久 Xorg/QMT，不会创建第二个
终端。raw VNC 不加密且认证只使用密码前 8 个字符，必须保持回环绑定并通过
SSH/VPN 访问；这与 MCP 的 static/OAuth 认证是两条独立安全边界。

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

## Tasks 兼容策略

Tasks 用于下载历史数据、批量下载财务数据、批量公式、因子生成和缓存刷新等
长操作。声明扩展的客户端先收到持久化 task ID，再通过 `tasks/get` 查询、
`tasks/cancel` 取消；协议没有自定义的 `tasks/list` 或 `tasks/result`。

任务与创建它的 OAuth principal 和原始工具 scope 绑定。刷新后的同一身份可
继续访问；换用户或丢失原 scope 时统一返回 `-32602`，不泄漏 task 是否存在。
静态 token 部署使用单一 deployment principal。任务记录不保存工具参数或
凭证，服务重启会将中断任务明确标为失败。

当前 qmtctl 完整声明并消费 Tasks。Codex、Claude Code 和 WorkBuddy 是否声明
扩展取决于各自版本；未声明时服务端自动同步回退。不要仅因为客户端能连接
`2026-07-28` 就假定它已经支持 Tasks。

若客户端实现 SEP-2575/SEP-2663，可订阅一个或多个自己有权访问的 task ID。
确认帧之后会先收到当前快照，因此断线后重新订阅不依赖服务端保存事件回放。
任务 ID 会同时检查创建 principal 和原始工具 scope；未知、过期和越权 ID
都不会出现在确认帧中。

### 任务输入

任务等待输入时，`tasks/get` 返回：

```json
{
  "status": "input_required",
  "inputRequests": {
    "confirmation": {
      "method": "elicitation/create",
      "params": {
        "mode": "form",
        "message": "Confirm operation",
        "requestedSchema": {
          "type": "object",
          "properties": {"confirm": {"type": "boolean"}},
          "required": ["confirm"]
        }
      }
    }
  }
}
```

客户端可以只回答部分键；服务端会继续返回剩余请求。未知、重复和已满足键在
鉴权后幂等忽略。等待问题的快照会持久化，回答值不会写入任务数据库、日志或
审计。服务重启不会重放执行，而是将等待中的任务标为失败。

客户端必须把确认交给用户或调用方，不应自动构造 `accept`。当前生产工具尚未
新增需要输入的流程；这套运行时用于后续经过单独安全设计的工具，并由 CI 隔离
fixture 验证。

## qmtctl

qmtctl 只使用 `2026-07-28`；若服务端不支持现代 discovery，它会返回协议错误，
不会发送 2025 initialize 或继续调用业务工具。
`qmtctl tools` 会合并所有目录页面，并通过 Go 标准 HTTP transport 自动解压
gzip；不需要分页或压缩参数。

qmtctl 默认 `--task-mode wait`，长工具执行完后仍输出普通工具结果。脱离模式
会立即输出可恢复的 task ID：

```bash
qmtctl --task-mode detach --json cache refresh --force
qmtctl task get tsk_<id>
qmtctl task wait tsk_<id>
qmtctl task cancel tsk_<id>
qmtctl task update tsk_<id> \
  --responses-json \
  '{"confirmation":{"action":"accept","content":{"confirm":true}}}'
```

等待模式先开 `subscriptions/listen`，严格校验确认帧、subscription ID、
task ID、完整状态和时间戳；服务端不支持、未确认、返回坏帧或中途断流时自动
按 `pollIntervalMs` 回到 `tasks/get`。`--timeout` 控制普通单次 HTTP 请求，
`--task-timeout` 控制通知与轮询合计的完整等待周期。`--task-mode sync` 仍使用
现代协议，但不声明 Tasks 扩展，用于验证同步 `tools/call` 路径。

默认等待如果遇到 `input_required`，qmtctl 会停止轮询并返回
`task_input_required`；JSON 错误数据包含 `taskId` 和完整
`inputRequests`。`--responses-json` 必须是最多 16 项、最大 64 KiB 的 JSON
对象。qmtctl 不读取 stdin 猜测答案，也不会自动接受确认。

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
| `connection refused` | 检查容器健康和 `QMT_DESKTOP_MODE`；仅 `manual` 模式需要先 RDP 登录。 |
| `Unsupported MCP protocol version` | 客户端或服务端仍是 0.x/2025 协议实现；先升级 MCP Host 和 qmtctl，再升级服务端。 |
| VNC 无法连接 | 确认使用了 `docker-compose.vnc.yml`、persistent 模式和回环隧道，并查看 desktop status 的 `vnc_state`。 |
| `401 invalid_token` | 检查签名、`kid`、issuer、resource audience、时间和 JWT 算法；服务端不会在错误里泄漏细节。 |
| `403 insufficient_scope` | 按 challenge 申请缺少的 family/management scope，重新登录。 |
| OAuth 找不到 AS | 检查公开 HTTPS URL、issuer、authorization servers 和两种 RFC 9728 metadata 路径。 |
| OAuth 登录后工具很少 | 查看 token scope，再检查 startup Profile、allow/deny 与 feature gate；它们取交集。 |
| qmtctl 没复用登录 | `auth status` 检查 resource 是否完全相同；显式 token 会覆盖保存的会话。 |
| 长命令立即返回 task ID | qmtctl 使用了 `--task-mode detach`；用 `task wait <id>` 恢复，或改回默认 `wait`。 |
| `task_input_required` | 审阅错误数据中的 `inputRequests`，显式运行 `task update <id> --responses-json ...`，再 `task wait`；不要自动接受确认。 |
| `server does not support MCP Tasks` | 服务端或当前协议未广告扩展；普通命令可用 `--task-mode sync`，显式 `task` 命令需升级服务端。 |
| 任务等待仍出现 `tasks/get` | 客户端或服务端没有任务通知、task ID 未确认，或 SSE 已断开；qmtctl 会自动回退，不影响正确性。 |
| `task ... returned insufficient/invalid params` | 检查 task ID、OAuth 身份和创建时所需 scope；服务端会故意隐藏未知与越权的区别。 |
| 客户端只显示部分工具 | 客户端需支持标准 `nextCursor`；先用 `qmtctl tools --json` 验证完整目录，再升级客户端。 |
| 能连上但没有行情 | QMT 未登录或 xtdata 未 ready；查看 `qmt_health`。 |
| Claude Code 看不到工具 | `/mcp` 检查连接和授权，并确认所申请 scope。 |
| Codex 看不到工具 | `bearer_token_env_var` 应是变量名，不是 token 值。 |
