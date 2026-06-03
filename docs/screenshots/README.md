# Screenshots — 拍摄清单

把截图放到这个目录，文件名按下表。放好后告诉我（或自己在根 README 的「截图」一节
取消注释），我来接入到 README。建议 PNG，宽度 ~1200px，注意**打码任何账号/余额/token**。

| 建议文件名 | 拍什么 | 为什么（亮点） |
|---|---|---|
| `01-fuzzy-search.png` | 在 **Claude** 或 **GPT** 对话里问一句中文，例如「纳指 / 天岳 最近怎么样」，让 Agent 调 `qmt_xtdata_resolve_instrument` / `qmt_xtdata_search_instruments` 把中文/拼音解析成代码，再调 `qmt_xtdata_snapshot` 取行情 | **核心亮点**：模糊查找——不用记 QMT 代码 |
| `02-mcp-tools.png` | client（Claude Desktop / 其它 MCP 客户端）里展开本服务**已注册的 `qmt_*` 工具列表** | 直观展示提供了哪些工具 |
| `03-bars-or-snapshot.png` | 某次 `qmt_xtdata_bars` 或 `qmt_xtdata_snapshot` 返回的**结构化 JSON** | 证明返回干净可用 |
| `04-healthz.png`（可选） | `curl /healthz`（带 token）的输出，或 `/livez` | 展示健康/就绪可观测 |
| `05-rdp-qmt.png`（可选） | RDP 桌面里 QMT 终端登录后的样子 | 展示 Wine 跑 QMT 终端 |

> 脱敏提醒：截图里**不要**出现真实资金账号、持仓金额、token、内网 IP。行情类（指数/ETF）
> 截图最安全。
