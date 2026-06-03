# QMT-MCP Appliance · 券商无关的 QMT 接入网关

把 Windows 版 **QMT / MiniQMT 终端**用 Wine 跑在原生 Linux 容器里，通过 **MCP（Model Context Protocol）** 把行情与账户能力安全地暴露给 AI Agent。

**核心理念：基础镜像与券商无关，换券商只换一个"broker pack"，镜像永不重建。**

---

## 这是什么 / 解决什么

QMT（迅投）是国内主流的量化交易终端，但它是 Windows 程序、且各券商版本（金阳光、海通、华泰、银河…）各不相同。本项目：

- 用 **Wine（new WoW64）** 在 **原生 amd64 Linux** 上跑 QMT 终端，桌面通过 **RDP** 访问；
- 把 `xtquant`（行情 `xtdata` + 交易 `xttrader`）封装成 **MCP 工具**，带鉴权、健康检查、审计、结构化输出；
- **基础镜像（base image）完全 broker 中立**：不含任何券商终端 / xtquant / 账户数据。

```
┌─────────────────────────────────────────────┐
│  不可变基础镜像  qmt-appliance-base            │
│  Wine wow64 + Windows Python 3.12 + 中文字体   │
│  + MCP 服务 + xrdp + detect-broker            │
│  —— 所有券商通用，一次构建到处用                │
└─────────────────────────────────────────────┘
        ▲ 运行时只读/读写挂载
┌───────────────────────┐   ┌──────────────────┐
│ broker pack (挂到 /broker)│ │ broker.yaml       │
│ 某券商 QMT 终端解压目录   │  │ 终端exe/路径/账户  │
│ + 配套 xtquant          │  │ /xtquant/模式      │
└───────────────────────┘   └──────────────────┘
```

**换券商 = 换挂载的 broker pack + broker.yaml，基础镜像不动**，一台机可并行多券商。

---

## 能力现状

| 能力 | 状态 | 说明 |
|---|---|---|
| 启动 QMT 终端 + RDP 登录 | ✅ | 登录后自动拉起终端 + MCP |
| **行情 `xtdata`（快照/K线/合约/板块/日历）** | ✅ 可用 | 通过 MCP 工具返回结构化 JSON |
| 账户查询 / 交易 `xttrader` | ⚠️ 需券商权限 | 见下方"交易权限"，未开通时优雅降级 |

### ⚠️ 关于交易/账户权限（重要）

外部 `xtquant` 连接交易接口（下单**和**账户查询）需要券商为账户开通
**「程序化交易 / 外部 Python 接口」权限**（账户授权位 `m_nPythonConnectNet`）。
未开通时 `XtQuantTrader.connect()` 返回 `-1`，账户/交易类工具会报
`not_authorized` 而非崩溃。**行情不受此限制。** 开通通常需满足券商资产门槛并签署
程序化交易协议——请联系你的券商。

---

## 快速开始

> 必须在**原生 amd64 主机**上构建运行。Apple Silicon 仅能在模拟下运行，
> QMT 原生行情/模型服务可能触发 Rosetta AVX 崩溃。

```bash
cd qmt-wine-rdp

# 1) 构建 broker 中立的基础镜像（不含任何券商终端/xtquant）
docker compose build

# 2) 用券商安装包 + 配套 xtquant 制作一个 broker pack（每个券商环境一次）
scripts/make-broker-pack.sh /path/to/setup_qmt.exe /path/to/xtquant_xxxxxx.rar \
    brokers/<broker-id>/pack

# 3) 配置并运行（.env 内含 token / 端口 / pack 路径）
docker compose up -d
```

连接：

```text
RDP:  <host>:13389   用户 wineuser / 密码见 .env（务必用真正的 RDP 客户端，如 Windows App，不要用 VNC）
MCP:  http://<host>:18765/sse   需 Authorization: Bearer <QMT_MCP_TOKEN>
```

登录 RDP 后在 QMT 终端里登录你的资金账号（交易需勾选**独立交易/极简模式**）。

更多：[broker pack 制作与切换](qmt-wine-rdp/docs/BROKER-PACK.md)

---

## 重要约束（踩过的坑）

- **原生 amd64**：不要在 Apple Silicon 上跑生产。
- **broker pack / 构建目录必须放在真实磁盘**，绝不能放 `tmpfs`（内存盘，如某些系统的 `/tmp`）——
  QMT 缓存会撑满内存导致 OOM、会话闪退。
- **GBK 区域**：QMT 是 GBK(cp936) 中文程序，镜像用 `zh_CN.GBK` 构建 Wine prefix，否则
  读取中文数据（如板块列表）会编码报错。
- **密钥不入镜像/Git**：token、账号密码只在运行时 `.env` / RDP 登录会话里，永不烤进镜像。

---

## 目录结构

```text
qmt-wine-rdp/            # 可部署的 appliance
├── Dockerfile          # broker 中立基础镜像（base 已钉 digest）
├── docker-compose.yml  # 挂载 /broker、参数化端口/token/实例
├── scripts/            # detect-broker / 启动 / 制作 pack / 自愈
├── mcp/                # MCP 服务
│   ├── qmt_mcp_core/   # 服务底座：鉴权/健康/审计/注册表/线程池
│   ├── qmt_mcp_xtdata/ # 行情工具（xtdata）
│   └── vendor/         # 复用的 qmt-trade-mcp（MIT）
├── brokers/<id>/       # broker.yaml（示例已脱敏）+ pack/（不入库）
└── docs/BROKER-PACK.md
specs/                  # Spec-Driven Development：001~005 规格/计划/任务
.specify/               # spec-kit + 项目宪章 constitution.md
```

## 开发方式

本项目用 **Spec-Driven Development（spec-kit）** 管理，一次一个 feature，先 spec 后实现。
原则见 [`.specify/memory/constitution.md`](.specify/memory/constitution.md)，AI 协作见
[`AGENT.md`](AGENT.md)。

## 赞助支持 ☕

这个项目是我用业余时间开发和维护的，完全开源免费。开发过程里很依赖 AI 编程助手
（Claude 等），订阅费用不便宜 😅。如果这个项目帮到了你，欢迎请我喝杯咖啡 / 支持一下
AI 订阅费，让它能持续更新——非常感谢你的支持！🙏

| 微信 | 支付宝 |
|:---:|:---:|
| <img src="docs/sponsor/wechat.jpg" width="220" alt="微信赞赏码"> | <img src="docs/sponsor/alipay.jpg" width="220" alt="支付宝收款码"> |

哪怕只是点个 ⭐ Star，也是对我莫大的鼓励！

## 致谢 / 许可

- 本仓库以 **MIT 许可证**发布，见 [`LICENSE`](LICENSE)。
- MCP 工具部分 vendor 自 [`qmt-trade-mcp`](https://github.com/yywx55/qmt-trade-mcp)（MIT），
  见 `qmt-wine-rdp/mcp/vendor/` 与 `qmt-wine-rdp/mcp/NOTICE`。
- 基础镜像基于 [`scottyhardy/docker-wine`](https://github.com/scottyhardy/docker-wine)。
- QMT 终端、xtquant 为各券商/迅投所有，**不包含在本仓库**，由使用者自行获取。

安全问题请按 [`SECURITY.md`](SECURITY.md) 私下报告；贡献流程见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。
