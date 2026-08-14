# MCP App 原型约定

QMT-MCP 的新 App 在接入真实工具和 `ui://` 资源前，先交付一个可离线打开的
故事原型。原型用于一起评审 Agent 为什么调用工具、结果如何进入对话，以及用户
下一步如何操作，而不只是评审一张脱离宿主的 App 截图。

## 先判断是否需要 App

| 用户需要 | 推荐呈现 | 示例 |
|---|---|---|
| 一个明确事实或一句解释 | 普通 Agent 文本 | 合约详情、权限说明、错误原因 |
| 从少量候选中确认一个对象 | 对话内确认结果 | 名称/拼音搜索后的标的确认 |
| 查看图形、探索时间序列 | MCP App | K 线、波动率曲面 |
| 比较多个对象或切换排序口径 | MCP App | ETF 流动性/费率/跟踪误差比较 |
| 查看组合结构或风险分布 | MCP App | 行业集中度、持仓暴露 |
| 确认高风险或不可逆操作 | MCP App 确认页 | 条件交易计划、清仓计划 |

不要为了展示界面而把简单回复包装成 App。App 应当承担文本难以高效表达的
可视化、比较、编辑或确认任务。

## 原型必须包含

1. 一个生成后的单 HTML 文件，CSS、JavaScript、图标和夹具全部内联。
2. 左侧按类型组织的场景入口；需要 App 的场景放在独立的 “MCP App 页面” 分组。
3. 右侧模拟 Codex/Claude 一类真实宿主的完整对话：用户消息、Agent 说明、工具调用、
   可选的 App、最终结论和追问输入框。
4. 真实工具名、结构化结果形状和权限状态，但不包含凭据、账户、地址或真实交易。
5. 中英文、明暗主题、桌面/移动预览和可分享的场景 URL。
6. 内容自然增长并支持页面滚动，不能依赖只适合截图的固定高度。
7. 核心控件有本地状态，原型运行时不连接 MCP、QMT、账户或网络服务。

当前基准原型是 [`qmt-mcp-app-story.html`](prototypes/qmt-mcp-app-story.html)。

## 开发流程

1. 在对应 spec 中写清用户问题、工具链、App 的必要性和权限边界。
2. 在 `src/story/scenes.ts` 增加类型化双语夹具，并选择 `presentation`：
   `conversation`、`confirmation`、`app` 或 `status`。
3. 只有 `presentation: "app"` 才增加独立 App renderer；其他场景留在宿主对话中。
4. 先评审单 HTML 故事原型，再实现生产 MCP tool、`structuredContent` 和 `ui://` 资源。
5. 使用桌面、平板、390px 移动端做截图与交互检查，并验证无外部请求和横向溢出。

```bash
cd appliance/mcp/apps/kline
npm ci
npm run dev:story
npm run typecheck
npm test
npm run build:story
```

CI 会重建 `docs/prototypes/qmt-mcp-app-story.html` 并检查是否存在未提交的构建漂移。
