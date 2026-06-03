# AGENT.md · AI 协作指南

给在本仓库工作的 AI Agent 的上手文档：项目地图、工作环境、构建/测试方法、以及一堆**踩过的坑**。先读这份，再动手。

## 项目本质

券商无关的 **QMT-MCP appliance**：Wine(new wow64) 在原生 amd64 上跑 Windows QMT 终端，
`xtquant` 能力经 MCP(SSE+token) 暴露给 Agent。基础镜像 broker 中立，券商相关的终端/xtquant/
配置作为运行时挂载的 **broker pack**（`/broker`）。详见 `README.md`。

## 当前状态（feature 进度）

| Feature | 分支 | 状态 |
|---|---|---|
| 001 基础镜像 + broker pack | `001-broker-pack-base` | ✅ 完成（含 exe 自愈、路径转义、client 优先级、密码、autostart 等修复）|
| 002 MCP server core | `002-mcp-server-core` | ✅ 实现+验证（`qmt_mcp_core`：鉴权/健康/审计/注册表/线程池/无写工具断言）|
| 003 行情工具 xtdata | `003-market-data-tools` | ✅ 完成——11/11 工具真机验证（含中文板块，经 zh_CN.GBK 修复）；见 specs/003/VERIFICATION.md |
| 004 账户只读查询 xttrade | spec | ⏸ 被券商权限硬卡（`m_nPythonConnectNet`），优雅降级 |
| 005 进程守护/就绪/autostart | spec | ⏳ 部分已落地（autostart、自愈），待系统化 |

每个 feature 的 `specs/<id>/` 下有 spec/plan/tasks/research/data-model/contracts。

## 工作环境（关键）

- 开发机写代码，**构建/运行在一台原生 amd64 Linux 主机上**（Wine 需要真 amd64；可本机或远程）。
- 若用远程主机，访问信息放本地 `.env`（如 `SSH_*`）——**已 gitignore，绝不提交**。
- 在该主机上用 docker 构建/部署。镜像 tag `qmt-appliance-base:local`，容器按实例命名（如 `qmt-<broker-id>`）。
- **构建上下文 / broker pack 放持久磁盘**，**不要用 `tmpfs`（如某些系统的 `/tmp`）**——QMT 缓存会撑满内存/磁盘 → OOM、wine 崩、磁盘满。

## 构建 / 部署 / 测试

```bash
# 构建（在 amd64 主机上，build 目录放持久盘）
docker build -t qmt-appliance-base:local <build-dir>
# 部署
docker compose --env-file inst-<id>.env -p qmt-<id> up -d --force-recreate
```

**测 MCP 行情工具（in-process，最可靠）**：用真实 config 构建 core，直接调注册表里的 callable，
绕开 SSE/鉴权，对 live xtdata 验证结构化输出：

```python
import sys, os; sys.path.insert(0, r'Z:\opt\qmt-mcp'); sys.path.insert(0, os.environ['QMT_XTQUANT_DIR_WIN'])
from qmt_mcp_core.config import CoreConfig
from qmt_mcp_core.app import create_app
cfg = CoreConfig(..., enable_xtdata=True, test_mode=True, allow_unauth_loopback=True)
_,_,health,registry = create_app(cfg)
registry._tools['qmt_xtdata_snapshot']['callable'](codes=['000001.SZ'])
```

在 Wine python 里跑：`wine /home/wineuser/.wine/drive_c/Python312/python.exe -u script.py`
（QMT 需已登录；行情走共享内存）。

## 踩过的坑（务必遵守）

1. **base 镜像必须钉 digest**。`scottyhardy/docker-wine:stable` 是浮动 tag，拉到不同 base 会
   产出**加载不出显示驱动**的 wine prefix（`nodrv_CreateWindow`）。升级 base 要显式重新钉。
2. **wine prefix 自愈**：start-qmt.sh 每个容器启动跑一次 `wineboot -u`（marker 防重复），
   否则烤进去的 prefix 可能没显示驱动、任何 wine GUI 都起不来。
3. **resolved env 值必须单引号**。Wine 路径含反斜杠（`Z:\broker\...`），`detect-broker` 写
   `/run/qmt/broker.env`、entrypoint 折叠进 `/opt/qmt-mcp/mcp.env` 时若不加单引号，bash
   `source` 会把反斜杠吃掉 → wine 打不开文件。启动客户端用 **unix 路径**（wine 接受）最稳。
4. **GBK/cp936**：QMT 是中文 GBK 程序。镜像用 `LANG=zh_CN.GBK` 建 prefix，否则 `get_sector_list`
   等读中文文件的路径会 UnicodeDecode/charmap 崩。`detect-broker` 读 broker.yaml 显式用 utf-8，不受影响。
5. **不要用 tmpfs 放数据**（见上）。
6. **docker exec 复杂命令用脚本文件**（scp 上去再 `bash file.sh`），别在 `ssh "... sudo bash -c '...'"`
   里塞多层引号/括号/heredoc——会被层层 shell 吃掉。heredoc 喂 `docker exec` 要加 `-i`。
7. **交易权限**：`xttrader.connect()==-1` 多半是账户没开 `m_nPythonConnectNet/程序化交易`
   （券商后台授权），不是代码问题。账户余额可从 mini 日志 `push accountdetail` 读到（非 API）。
8. **client 探测优先级**：真实 QMT 树里 `bin.x64` 同时有 `XtItClient.exe`(投研版) 和
   `XtMiniQmt.exe`。投研版 + 独立交易会拉起 `XtMiniQmt linkMini`。detect-broker 按优先级选
   `XtItClient.exe`；独立的 `XtMiniQmt.exe` 直接启在 wine 下不一定稳。

## 安全 / 开源前必做

- 永不提交：`.env`、token、broker 二进制（终端 exe / xtquant / setup_qmt）、`*/pack/`、workspace。
  这些已在 `.gitignore`。
- **开源前脱敏**：从 tracked 文档/spec 注释里清掉真实**账户号、余额数字、主机 IP/凭据**。
- 只读默认；交易工具须显式开关 + 账户白名单 + 审计（见 constitution）。

## 流程

Spec-Driven（spec-kit）：`/speckit-specify → clarify → plan → tasks → implement`，一次一个 feature，
plan 必过宪章检查（`.specify/memory/constitution.md`）。范围蔓延就新开 spec，不要往进行中的 spec 里塞。
