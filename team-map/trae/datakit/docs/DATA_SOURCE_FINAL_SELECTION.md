# 🎯 数据源综合选型报告 — 晨间竞价 DAG 系统

> **生成日期**: 2026-07-07  
> **合并来源**: `DATA_SOURCE_VERSION_SURVEY.md` + `DATA_SOURCE_SELECTION.md` + `NODE_API_FIELD_MATRIX.md`  
> **预算上限**: ¥100/月（可接受付费方案，单源/组合均可）  
> **当前总月费**: ¥199 (TickFlow Expert) + ¥89 (i问财进阶版) ≈ **¥288/月**

---

## 一、当前数据源总览（现状基线）

### 1.1 当前在用 + 订阅状态

```
┌──────────────────────────────────────────────────────────────────────┐
│                        当前数据源运行拓扑                              │
│                                                                      │
│  ┌─────────────────────────┐          ┌──────────────────────────┐  │
│  │ TickFlow Expert         │          │ i问财 SkillHub            │  │
│  │ ¥199/月  → 到期 7/16 ⚠️ │          │ ¥268/季 (≈¥89/月)        │  │
│  │ Key: tk_b35f...10e7     │          │ 到期 2026/10/01           │  │
│  │                         │          │ Key: sk-proj-00-rCTAM...  │  │
│  │ ✅ K线 (日+分钟)         │          │ 进阶版会员                 │  │
│  │ ✅ 实时行情 (WS+REST)    │          │ ✅ 6 个 hithink-* skills  │  │
│  │ ✅ 五档盘口              │  离线预取  │ ✅ 涨停原因覆盖 100%       │  │
│  │ ✅ 财务数据+除权因子      │◄─────────│ ✅ 388 个概念板块          │  │
│  │ ✅ 专线加速              │          │ CLI 0.0.4 → openapi      │  │
│  └──────────┬──────────────┘          └───────────┬──────────────┘  │
│             │                                     │                  │
│             ▼                                     ▼                  │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                     东方财富 (免费补充)                           │ │
│  │  push2delay.eastmoney.com — 行业/概念板块排名 + 成分股映射        │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 TickFlow 各版本完整能力矩阵

> 数据来源：TickFlow 官网定价页 (2026-07-07 采集) + 本地代码反向工程

| 能力 | Free | Starter | Pro | **Expert ✅** |
|------|------|---------|-----|-------------|
| **月费** | ¥0 | ¥49 | ¥99 | **¥199** |
| 注册要求 | 无需 | 需注册 | 需注册 | 需注册 |
| API Key | 不需要 | 需要 | 需要 | 需要 `tk_...` |
| A股日K (1d/1w/1M/1Q/1Y) | ✅ | ✅ | ✅ | ✅ |
| 实时行情 REST | ❌ | ✅ | ✅ | ✅ |
| 分钟K (1m/5m/15m/30m/60m) | ❌ | ❌ | ✅ (12月) | ✅ (全量) |
| 日内分时 | ❌ | ❌ | ✅ | ✅ |
| WebSocket 实时推送 | ❌ | ❌ | ✅ (100标的) | ✅ (100标的) |
| 五档盘口 | ❌ | ❌ | ✅ | ✅ |
| 财务数据 | ❌ | ❌ | ❌ | ✅ |
| 除权因子 | ❌ | ❌ | ❌ | ✅ |
| 专线加速 | ❌ | ❌ | ❌ | ✅ |
| **本项目最低可用** | ❌ | ❌ | ⚠️ 缺财务+除权 | ✅ 全覆盖 |

**版本降级可行性**: Pro (¥99/月) 具备除财务数据外的全部核心能力（分钟K/WS/五档盘口），可节省 50% 月费。当前本项目**未实际消费财务数据和除权因子**（代码探测通过但无调用路径）。

### 1.3 i问财 各渠道完整对比

| 渠道/版本 | 类型 | 价格 | 自动化 | 生产合规 | 本地在用 |
|-----------|------|------|--------|----------|----------|
| **iwencai.com Web** | 免费网页 | ¥0 | ❌ | ❌ | ❌ |
| **SkillHub 技能商店** | 免费技能市场 | ¥0 | ✅ | ✅ | ✅ 6个skills |
| **openapi.iwencai.com** | API 服务 | ⚠️ 未公开标价 | ✅ | ✅ | ✅ 当前主用 |
| **同花顺 iFinD** | 企业级 | ¥数万-数十万/年 | ✅ | ✅ | ❌ 超预算 |
| **SuperMind query_iwencai** | 平台函数 | 随平台 | ❌ 不可独立 | ❌ | ❌ |
| **pywencai (非官方)** | 社区工具 | ¥0 | ⚠️ | ❌ 禁止 | ❌ |

**平台会员等级**:

| 等级 | 价格 | AI选股 | 导出 | 推理模型 | 大模型 | 金融DB |
|------|------|--------|------|----------|--------|--------|
| 免费版 | ¥0 | 100次/天 | 2次/天 | ❌ | ❌ | ❌ |
| **进阶版 ✅** | **¥268/季** | 500次/天/skill | 1000条/天 | ❌ | ❌ | ❌ |
| 专业版 | 未标价 | 不限 | 1000次/天 | ✅ | ✅(1000次) | ❌ |
| 企业版 | 商务洽谈 | 不限 | 200次/天 | ✅ | ✅ | ✅ |

---

## 二、节点级数据需求（精确到字段 × 频率）

> 来源: `NODE_API_FIELD_MATRIX.md` 逐字段逆向分析

### 2.1 各节点对数据源的依赖矩阵

```
时间线:  08:00 ────── 09:15 ──── 09:25 ──── 09:30 ──── 09:40 ──── 10:01
节点:    preloader  auction    decision_1  d2_engine  d2_end    terminal
         │           │          │           │          │          │
TickFlow │ K线×32     │ WS 10min  │ (本地)    │ WS 10min  │         │ quotes×N/50
Eastmoney│ 板块×1     │ 板块×2+   │           │           │         │
         │            │ 映射×22   │           │           │         │
iwencai  │ (离线)     │          │           │           │         │
```

### 2.2 每个节点对 TickFlow 的精确字段需求

| 节点 | 端点 | 必需字段 | 频率 | 关键程度 |
|------|------|----------|------|----------|
| **data_preloader** | `klines/batch?period=1d` | symbol, close[2], volume[2], amount[2], high[2], low[2] | 每日 ~32次HTTP | 🔴 P0 |
| **auction_monitor** | `ws/stream` | symbol, last_price, open, volume, amount, change_pct, timestamp(ms), name | 10分钟WS流 | 🔴 P0 |
| **d2_engine** | `ws/stream` | symbol, open, last_price, volume | 10分钟WS流 | 🔴 P0 |
| **decision_engine** | `quotes` | **仅** last_price, open | 每日 ~N/50次HTTP | 🟡 P1 |
| **d2_rest_fallback** | `klines/batch?period=1m` + `quotes` | close[0], last_price, volume | 降级时一次性 | 🟡 P1 |

### 2.3 替代数据源的最低字段门槛

**K线接口（替代 TickFlow klines/batch）**:
```
symbol, date, open, high, low, close, volume(手), amount(元)
period=日线, 至少前2交易日
```

**实时行情接口（替代 TickFlow WS + REST quotes）**:
```
symbol, last_price, open, high, low, volume, amount, prev_close, change_pct, timestamp(ms), name
支持: 批量订阅(≥100只) + 单次快照(≥50只/批)
```

---

## 三、候选替代数据源全景对比

### 3.1 全网候选源一览

| # | 名称 | 类型 | 月费 | A股 | WS | 竞价 | 板块 | 分钟K | 批量 |
|---|------|------|------|-----|----|------|------|-------|------|
| 1 | **TickFlow Pro** (降级) | API | ¥99 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| 2 | **a-stock-data** 🆕 | AI Skill 内嵌代码 | ¥0 | ✅ | ⚠️ TCP | ✅ 五档 | ✅ 双源 | ✅ | ✅ |
| 3 | **黑狼数据 fxyz** | API | ¥30-80 | ✅ | ❌ HTTP | ✅ | ⚠️资金流 | ✅ | ✅ |
| 4 | **StockApi.cn** | API | ¥30-50 | ✅ | ❌ HTTP | ✅ | ⚠️ | ✅ | ⚠️ |
| 5 | **iTick Free** | API | ¥0 | ✅ | ✅ WS | ⚠️ depth | ❌ | ❌ | ❌ 5次/分 |
| 6 | **iTick Pro** | API | ~$50 (¥360) | ✅ | ✅ | ⚠️ | ❌ | ✅ | ✅ |
| 7 | **XTick** | API | 未公开 | ✅ | ✅ WS全推 | ✅ | ❌ | ✅ | ✅ |
| 8 | **AKShare** | Python库 | ¥0 | ✅ | ❌ | ❌ | ✅ | ✅ | ⚠️ |
| 9 | **SuperMind** | 平台 | ¥0免费版 | ✅ | ⚠️ | ✅ | ✅ | ✅ | ⚠️ 3000次/月 |
| 10 | **Tushare Pro** | API | 积分制 | ✅ | ❌ | ❌ | ✅ | ⚠️ 需积分 | ✅ |
| 11 | **AllTick** | API | $99 (¥700) | ⚠️ 弱 | ✅ | ❌ | ❌ | ✅ | ✅ |
| 12 | **Ashare** | Python库 | ¥0 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 13 | **adata** | Python库 | ¥0 | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ |

### 3.2 各源与本项目需求的逐项匹配

| 需求维度 | TickFlow Pro | a-stock-data 🆕 | 黑狼 | StockApi | iTick Free | iTick Pro | XTick | AKShare | SuperMind |
|----------|-------------|-----------------|------|----------|------------|-----------|-------|---------|-----------|
| **日K线(全市场)** | ✅ | ✅ mootdx+腾讯+百度 | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **实时行情推送** | ✅ WS 100标的 | ⚠️ TCP 46字段多标的 | ❌ HTTP | ❌ HTTP | ✅ WS | ✅ WS | ✅ WS全推 | ❌ | ⚠️ |
| **实时行情 REST** | ✅ | ✅ mootdx快照 | ✅ 53字段 | ✅ | ✅ 限5次/分 | ✅ | ✅ | ✅ | ✅ |
| **分钟K线** | ✅ 12月 | ✅ mootdx多周期 | ✅ 多周期 | ✅ | ❌ | ✅ 15年 | ✅ | ✅ | ✅ |
| **集合竞价** | ✅ WS间接 | ✅ 五档盘口+逐笔 | ✅ 竞价接口 | ✅ 竞价+一字板 | ⚠️ depth | ⚠️ depth | ✅ | ❌ | ✅ |
| **行业/概念板块** | ❌ | ✅ 东财slist+push2+同花顺热点 | ⚠️ 资金流向 | ❌ | ❌ | ❌ | ❌ | ✅ 双源 | ✅ |
| **板块-成分股映射** | ❌ | ✅ 东财slist | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **涨停原因解释** | ❌ | ✅ 同花顺涨停揭秘 | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ 涨停列表 | ✅ 核心 |
| **批量查询(≥50只)** | ✅ | ✅ mootdx批量 | ✅ | ⚠️ | ❌ | ✅ | ✅ | ⚠️ 逐只 | ⚠️ |
| **月费** | ¥99 | **¥0** | ¥30-80 | ¥30-50 | ¥0 | ~¥360 | 未公开 | ¥0 | ¥0(受限) |
| **集成方式** | REST+WS | 提取SKILL.md内嵌Python→mootdx库 | HTTP | HTTP | REST+WS | REST+WS | REST+WS | pip install | 平台内 |
| **IP要求** | 无 | ⚠️ mootdx需国内IP | 无 | 无 | 无 | 无 | 无 | 无 | 无 |

---

### 3.3 🆕 a-stock-data 深度评估

> **GitHub**: https://github.com/simonlin1212/a-stock-data  
> **版本**: V3.3.0 | **协议**: Apache 2.0 | **月费**: ¥0  
> **架构**: 非传统 API/SDK — 是一个内嵌 Python 代码的 Markdown SKILL 文件，放入 AI 助手上下文目录后由助手执行  

#### 3.3.1 架构本质

```
┌─────────────────────────────────────────────────────────────────┐
│                    a-stock-data = SKILL.md                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 内嵌 Python 代码段 (可独立提取执行)                        │   │
│  │                                                          │   │
│  │  pip install mootdx requests pandas stockstats            │   │
│  │                                                          │   │
│  │  ┌─ mootdx (通达信 TCP :7709)                             │   │
│  │  │   ├─ K线(日/周/月/分钟) + 五档盘口 + 逐笔成交          │   │
│  │  │   ├─ 实时46字段行情推送 (TCP 流)                       │   │
│  │  │   ├─ 季报快照 (EPS/ROE/净利润 37字段)                  │   │
│  │  │   └─ F10 公司资料 (9大类)                              │   │
│  │  ├─ 腾讯财经 HTTP                                         │   │
│  │  │   └─ 日K+MA均线 + PE/PB/市值/换手率                    │   │
│  │  ├─ 百度股市通 HTTP                                       │   │
│  │  │   └─ 日K线+MA5/MA10/MA20                              │   │
│  │  ├─ 东财 HTTP (datacenter/push2/reportapi/search...)      │   │
│  │  │   ├─ 板块归属+龙头股(slist)                            │   │
│  │  │   ├─ 行业板块排名+资金流向(push2)                      │   │
│  │  │   ├─ 龙虎榜+解禁+两融+大宗+分红+股东户数               │   │
│  │  │   ├─ 涨停池/炸板池/跌停池(push2ex)                     │   │
│  │  │   ├─ 个股研报+行业研报+PDF(reportapi)                  │   │
│  │  │   └─ 个股新闻+全球资讯(search-api-web/np-weblist)      │   │
│  │  ├─ 同花顺 HTTP                                           │   │
│  │  │   ├─ 强势股+题材归因(热点)                             │   │
│  │  │   ├─ 北向资金(实时262点+历史自缓存)                    │   │
│  │  │   ├─ 涨停揭秘(原因/封板率/一字换手T字)                 │   │
│  │  │   ├─ 一致预期 EPS                                      │   │
│  │  │   └─ 人气榜                                            │   │
│  │  ├─ 新浪财经 HTTP                                         │   │
│  │  │   ├─ 三表(资产负债/利润/现金流)                        │   │
│  │  │   └─ ETF期权(T型报价/希腊字母/IV)                      │   │
│  │  ├─ 巨潮 cninfo HTTP                                      │   │
│  │  │   ├─ 全量公告                                          │   │
│  │  │   └─ 互动易问答                                        │   │
│  │  └─ iwencai (可选，需Key)                                  │   │
│  │      └─ NL语义跨主题研报搜索                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  10层 × 40端点 × 13数据源  |  除iwencai外全部免费无Key           │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 节点级适配分析

| 节点 | 当前 TickFlow 调用 | a-stock-data 替代方式 | 适配难度 |
|------|-------------------|----------------------|----------|
| **data_preloader** | `klines/batch?period=1d` ×32次 | mootdx 批量日K (TCP) / 腾讯日K+MA (HTTP) | 🟡 中 — mootdx 不复权，需切换腾讯前复权 |
| **auction_monitor** | `ws/stream` 10分钟WS流 | mootdx TCP 实时订阅 (46字段推送) | 🔴 高 — WS→TCP协议转换，需重写连接管理 |
| **d2_engine** | `ws/stream` 10分钟WS流 | mootdx TCP 实时订阅 | 🔴 高 — 同上，还需处理不同订阅列表 |
| **decision_engine** | `quotes?symbols=...` REST快照 | mootdx 实时快照 (46字段) | 🟢 低 — REST→函数调用，字段映射清晰 |
| **d2_rest_fallback** | `klines/batch?period=1m` + `quotes` | mootdx 分钟K + 快照 | 🟢 低 — 功能对等 |
| **板块排名** | 东方财富 push2delay | 保留东方财富 或 切换东财push2 (同源) | 🟢 低 — 同源升级 |
| **涨停原因** | iwencai SkillHub (离线) | 同花顺涨停揭秘 (在线,盘后15:30更新) | 🟡 中 — 离线→在线，数据时效不同 |

#### 3.3.3 核心风险：mootdx TCP 替代 WebSocket

这是整个方案最关键的工程问题。TickFlow WS 和 mootdx TCP 的对比：

| 维度 | TickFlow WS | mootdx TCP |
|------|------------|------------|
| **协议** | JSON over WebSocket | 通达信二进制协议 (TCP :7709) |
| **库** | `websockets` | `mootdx` (Python) |
| **连接方式** | `wss://api.tickflow.org/v1/ws/stream?api_key=` | `mootdx.quotes.Quotes.factory(market='std').connect()` |
| **订阅** | JSON `{"op":"subscribe","symbols":[...]}` | `client.subscribe(['600001','000002',...])` |
| **推送格式** | JSON `{"op":"quotes","data":[{...}]}` | mootdx 解析后的 dict，含46个字段 |
| **心跳** | 25s ping 日志 | TCP keepalive (系统级) |
| **重连** | `websockets` 自带 | 需手动实现 |
| **IP要求** | 无 | **必须国内 IP** (海外服务器 TCP 超时) |
| **可靠性** | 商业 API SLA | 通达信官方服务器（免费但无 SLA） |

**适配工作量估算**：

| 文件 | 改动范围 | 预估行数 | 说明 |
|------|----------|----------|------|
| `auction_monitor.py` | 重写 WS 连接+消息处理 | ~150行 | `websockets` → `mootdx` |
| `d2_engine.py` | 重写 WS 连接+消息处理 | ~120行 | 同上，不同订阅列表 |
| `data_preloader.py` | 替换 K线获取 | ~80行 | REST批量→mootdx批量K线 |
| `decision_engine.py` | 替换终端报价 | ~30行 | REST→mootdx快照 |
| `d2_rest_fallback.py` | 替换分钟K+报价 | ~40行 | REST→mootdx |
| `requirements.txt` | 新增依赖 | +2行 | `mootdx`, `stockstats` |
| **合计** | | **~420行** | 5个节点 + 依赖 |

#### 3.3.4 数据源优先级与风控

a-stock-data 内置了封 IP 风险排序和防封策略：

```
优先级 (低→高风险):
  1. mootdx (通达信) — 不封IP，可高频
  2. 腾讯财经 — 不封IP
  3. 同花顺 — 极低风险
  4. 百度/新浪/巨潮 — 低风险
  末位. 东财 — 有风控 (阈值: >5次/秒 | 并发≥10 | 1分钟≥200)
         → 内置限流: 串行≥1s间隔+随机抖动+会话复用+重试
```

#### 3.3.5 与现有 SkillHub 生态的关系

a-stock-data 已作为 Skill 安装在 `/Users/fiona/.claude/skills/` (见 skill catalog)。这意味着：

- ✅ 本地 AI 助手已可直接调用 a-stock-data 的内嵌代码获取数据
- ✅ 与现有 iwencai SkillHub skills 数据源互补（前者管行情+基本面，后者管涨停原因）
- ⚠️ 但 DAG 节点是独立 Python 脚本，不能直接"调用 skill"——需提取内嵌代码为可 import 的模块

---

## 四、推荐方案对比

### 方案 A: 降级 TickFlow Pro（最平滑）

```
TickFlow Pro (¥99/月) + 东方财富 (免费) + i问财 SkillHub (已有)
```

| 优点 | 缺点 |
|------|------|
| 零代码变更（同一 API 体系） | 失去财务数据、除权因子（当前未实际使用） |
| WS+REST 协议完全兼容 | 分钟K仅12个月历史（vs Expert 无限） |
| 省 ¥100/月 (50%) | 仍然单点依赖 TickFlow |
| Pro 具备本项目全部必需字段 | — |

### 方案 B: 黑狼数据 + AKShare（最经济）

```
黑狼数据 fxyz (¥30-80/月) + AKShare (免费) + i问财 SkillHub (已有)
```

| 优点 | 缺点 |
|------|------|
| 月费最低 ¥30-80 | **无 WebSocket**（核心风险） |
| 黑狼53字段实时行情 + 竞价接口 | HTTP轮询替代WS，竞价延迟增加 |
| AKShare 覆盖板块+涨停双源 | 必须写全新 adapter 层 |
| 摆脱 TickFlow 单点依赖 | 迁移工作量大 |

### 方案 C: iTick Free WS + AKShare（零成本实验）

```
iTick Free WS (¥0) + AKShare (免费) + i问财 SkillHub (已有)
```

| 优点 | 缺点 |
|------|------|
| 完全免费 | iTick 免费版限速 5次/分钟 REST |
| WS 实时推送保留 | 无分钟K线 |
| Python SDK 现成 | 竞价数据弱（仅 depth） |
| 快速验证概念 | 无法独立支撑 DAG 全部节点 |

### 方案 D: 组合（最优但超预算）

```
黑狼数据 (¥30-80) + iTick Free WS (¥0) + AKShare (¥0) + i问财 (已有)
月费: ¥30-80
```

| 优点 | 缺点 |
|------|------|
| 黑狼主力 + iTick WS补实时 | 架构复杂，需维护三个适配器 |
| 所有维度全覆盖 | iTick free WS 可靠性未知 |
| ¥30-80/月，远低预算 | — |

### 🆕 方案 E: a-stock-data 单源（零成本，最大自主权）

```
a-stock-data mootdx (¥0) + 腾讯财经 (¥0) + 东财 (¥0) + 同花顺 (¥0) + i问财 SkillHub (已有)
月费: ¥0
```

| 优点 | 缺点 |
|------|------|
| **完全免费**，无订阅/无到期 | WS→mootdx TCP 需重写 ~420 行适配代码 |
| 10层×40端点覆盖，远超本项目需求 | **mootdx 必须国内 IP**（海外服务器不可用） |
| 覆盖 TickFlow Pro 没有的板块/概念/龙虎榜/涨停揭秘 | 通达信 K 线为不复权原始价，需切腾讯前复权 |
| 可完全替换 东方财富 免费补充源 | 东财有频率风控，需遵守内置限流 |
| Apache 2.0，无供应商锁定 | 无商业 SLA，通达信服务器故障时无技术支持 |
| 本地已装 Skill，可立即影子运行验证 | 分钟K 仅 mootdx 单源（不如 TickFlow 有多级降级） |

---

## 五、最终推荐 (含 a-stock-data)

### 🥇 首选：方案 A — 降级 TickFlow Pro (¥99/月)

**理由**:
- TickFlow Expert 到期 **2026/7/16（仅剩 9 天）**，必须立即决策
- 本项目**未实际消费** Expert 独有的财务数据和除权因子（仅探测确认存在，代码中无调用路径）
- Pro (¥99/月) 提供 WS、分钟K、实时行情、五档盘口——完全覆盖 5 个核心节点的全部必需字段
- **零代码变更，零迁移风险**
- 月费从 ¥199 → ¥99，降幅 50%，远在 ¥100/月预算内

**行动步骤**:
1. 🔴 7/16 前续费降级为 Pro（若官方支持降级）或新购 Pro Key
2. 更新 `.env` 中的 `TICKFLOW_API_KEY`
3. 运行 `tests/` 22 个用例验证通过

### 🥈 中长期首选：方案 E — a-stock-data (¥0/月)

**理由**:
- 10层×40端点覆盖，本项目只需其中 ~6 个端点，绰绰有余
- **完全免费 + Apache 2.0**，零供应商锁定，零预算压力
- 覆盖 TickFlow Pro 不具备的板块/概念/龙虎榜/涨停揭秘——可顺便**替换东方财富免费补充源**
- 本地已装 Skill，可立即启动影子运行验证数据质量
- 通达信官方协议 (mootdx)，数据源头可靠
- 唯一核心风险 (mootdx TCP 替代 WS) 为已知、可控、可验证的工程问题

**推荐策略: 双轨并行**:
```
轨道 1 (立即):  TickFlow Pro (¥99/月) — 保生产稳定，7/16 前降级
轨道 2 (影子):  a-stock-data mootdx — 静默采集 + 交叉验证 + 写 adapter
                ↓ 验证通过后 (预计 2-4 周)
轨道 1 (切换):  停 TickFlow，全量切 a-stock-data → 月费归零
```

**影子运行 Phase**:
- Phase 1: 提取 a-stock-data SKILL.md 内嵌 Python 为独立 `mootdx_adapter.py` (~200行)
- Phase 2: 部署 adapter 到 DAG 节点旁路，输出 `shadow_handoff/` 与主链路产物交叉对比
- Phase 3: 对比 5+ 个交易日的 auction_snapshot / d2_decision / terminal_packet 三份产物一致性
- Phase 4: 验证通过 → 写入 `data_source_governance.py` 注册为 Tier-1 → 停 TickFlow

### 🥉 备选：方案 D — 黑狼 + iTick WS + AKShare (¥30-80/月)

**适用场景**: a-stock-data 验证失败（如 mootdx TCP 不稳定）或 TickFlow 不可用时的中间方案

---

## 六、i问财决策

| 决策 | 结论 | 理由 |
|------|------|------|
| 继续使用？ | ✅ 保留 | 进阶版 ¥268/季到期 10/01，涨停原因覆盖率 100%，替换成本高 |
| 升级专业版？ | ❌ 不推荐 | 价格未公开，且本项目不需要推理模型/大模型 |
| OpenAPI 配额 | 🟡 待确认 | `sk-proj-` Key 是否包含在进阶版会员中还是另需付费 |

---

## 七、费用总账

### 短期 (推荐)

| 项目 | 当前 | 推荐 (方案 A) | 节省 |
|------|------|------|------|
| TickFlow | ¥199/月 (Expert) | ¥99/月 (Pro) | -¥100/月 |
| i问财 SkillHub | ¥89/月 (进阶版) | ¥89/月 (不变) | ¥0 |
| 东方财富 | ¥0 | ¥0 | ¥0 |
| **合计** | **¥288/月** | **¥188/月** | **-¥100/月 (35%)** |

### 中长期目标 (双轨验证后)

| 项目 | 当前 | 目标 (方案 E) | 节省 |
|------|------|------|------|
| TickFlow | ¥199/月 (Expert) | ¥0 (停用) | -¥199/月 |
| i问财 SkillHub | ¥89/月 (进阶版) | ¥89/月 (不变) | ¥0 |
| a-stock-data (mootdx+腾讯+东财+同花顺) | — | **¥0** | — |
| **合计** | **¥288/月** | **¥89/月** | **-¥199/月 (69%)** |

---

## 八、关键风险清单

| # | 风险 | 等级 | 应对 |
|---|------|------|------|
| 1 | TickFlow Expert 7/16 到期断服 | 🔴 P0 | 立即降级续费 Pro |
| 2 | API Key 明文暴露在 `.env` | 🔴 安全 | 迁移到 `~/.openclaw/keys.env` 外挂 |
| 3 | TickFlow 升级 v2 API 不兼容 | 🟡 P1 | 增加版本协商机制 (`X-API-Version` 头校验) |
| 4 | i问财 OpenAPI 配额未知 | 🟡 P1 | 联系确认 `sk-proj-` Key 限额 |
| 5 | SkillHub CLI 0.0.4 → 后续版本兼容性 | 🟢 P2 | 锁定 6 个 skill 版本号哈希 |
| 6 | 黑狼数据/AKShare 数据质量未验证 | 🟢 P2 | Phase 1 影子运行交叉验证 |
| 7 | WebSocket 缺失场景下轮询精度不足 | 🟡 P1 | 竞价时段提速至 500ms；iTick free WS 兜底 |
| 8 🆕 | **mootdx TCP 稳定性不及 TickFlow WS** | 🟡 P1 | 双轨并行验证 5+ 交易日；保留 TickFlow Pro 为降级源 |
| 9 🆕 | **mootdx 需国内 IP（海外服务器不可用）** | 🟡 P1 | 当前部署环境在国内，不影响；若迁海外需走代理 |
| 10 🆕 | **通达信 K 线不复权，跨除权除息日价格跳变** | 🟢 P2 | 本项目只用前 2 个交易日日K，除权概率低；或用腾讯前复权日K降级 |
| 11 🆕 | **东财风控封 IP（a-stock-data 源之一）** | 🟢 P2 | 优先用 mootdx/腾讯，东财仅取其独有字段(板块/龙虎榜)；内置限流已处理 |

---

## 九、数据源字段映射速查

### TickFlow → a-stock-data (mootdx)

| TickFlow 字段 | mootdx 字段 | 索引 | 说明 |
|---------------|------------|------|------|
| `symbol` | `code` | — | 格式: `600001` (mootdx) vs `600001.SH` (TickFlow)，需加后缀映射 |
| `last_price` | `price` | 3 | 最新价 |
| `open` | `open` | 4 | 开盘价 |
| `high` | `high` | 33 | 最高价 |
| `low` | `low` | 34 | 最低价 |
| `volume` | `cur_vol` | 6 | 现量(手) |
| `amount` | `amount` | 37 | 成交额(元) |
| `change_pct` | `pct_chg` (需计算) | — | `(price - pre_close) / pre_close` |
| `prev_close` | `pre_close` | 5 | 前收盘 |
| `name` | `name` | 1 | 股票名称 |
| `bid1..5` / `ask1..5` | `bid1..5_price` + `bid1..5_vol` | 9-28 | 五档盘口（mootdx 提供，TickFlow Pro 也有） |

> **完整 46 字段清单**: mootdx 一个推送包含 46 个字段（含五档盘口、内外盘、委比委差、量比、换手率、市盈率等），远超本项目需求。

### TickFlow → a-stock-data (腾讯财经 K线)

| TickFlow K线字段 | 腾讯财经字段 | 说明 |
|-----------------|-------------|------|
| `close[0]`, `close[1]` | K线数组 close | **腾讯为前复权**，优于 mootdx 原始价 |
| `volume[1]` | K线数组 volume | 成交量(手) |
| `amount[1]` | 需 volume×price 估算 | 腾讯不直接提供成交额 |
| `high[1]`, `low[1]` | K线数组 high/low | — |

> ⚠️ **建议**: K线优先用腾讯（前复权），实时流用 mootdx TCP（速度快）。data_preloader 中 amount 需从腾讯 volume×close 近似或切换到 mootdx 日K（提供 amount 字段）。

### TickFlow → a-stock-data (同花顺 涨停揭秘)

| iwencai 离线字段 | 同花顺涨停揭秘字段 | 说明 |
|-----------------|-------------------|------|
| `涨停原因[YYYYMMDD]` | 涨停原因题材 | **在线获取**，盘后 15:30 更新 |
| `连续涨停天数` | 连板数 | — |
| `封流比` | 封单/流通股 | 可算 |
| `涨停封单额` | 封单额 | — |
| `所属同花顺行业` | — | 同花顺热点接口另取 |

### TickFlow → 黑狼数据

| TickFlow 字段 | 黑狼数据字段 | 接口 |
|---------------|-------------|------|
| `symbol` | code | 实时行情 |
| `last_price` | price | 实时行情 |
| `open` | open | 实时行情 |
| `high` | high | 实时行情 |
| `low` | low | 实时行情 |
| `volume` | volume | 实时行情 |
| `amount` | amount | 实时行情 |
| `change_pct` | pct_chg | 实时行情 |
| `prev_close` | pre_close | 实时行情 |
| `vwap` | (amount/volume 自行计算) | — |

### 东方财富 → a-stock-data (同源升级)

| 东方财富 push2delay 字段 | a-stock-data 东财 push2 字段 | 说明 |
|--------------------------|---------------------------|------|
| `f12` (板块代码) | 板块代码 | — |
| `f14` (板块名) | 板块名 | — |
| `f3` (涨跌幅) | 涨跌幅 | — |
| `f62` (成交额) | 成交额 | — |
| `f104/f105` (涨跌家数) | 涨跌家数 | — |
| `f140/f128/f136` (领涨股) | 领涨股 | 同接口 |
| — 🆕 | 主力/大单/中单/小单净流入 | push2 分钟级资金流向 |
| — 🆕 | 个股概念命中+热度值 | 新增能力 |

### 东方财富 → AKShare

| 东方财富字段 | AKShare 函数 |
|-------------|-------------|
| 板块排名 (f12,f14,f3,f62) | `stock_board_concept_name_em()` |
| 板块行情 (f3,f62) | `stock_board_concept_hist_em()` |
| 成分股 (f12) | `stock_board_concept_cons_em()` |
| 行业分类 | `stock_board_industry_cons_em()` |
| 涨停板 | `stock_zt_pool_em()` |
| 全量码表 | `stock_zh_a_spot_em()` |

---

> **Sources — 本报告引用**:
> - [a-stock-data GitHub](https://github.com/simonlin1212/a-stock-data) — V3.3.0, Apache 2.0, 10层×40端点×13数据源
> - TickFlow 官网定价页 (tickflow.org, 2026-07-07)
> - i问财 SkillHub (iwencai.com/skillhub, 2026-07-07)
> - [AKShare GitHub](https://github.com/akfamily/akshare) — 14,000+ stars
> - [黑狼数据 fxyz](http://www.fxyz.site)
> - [iTick 官网](https://itick.org)
> - [XTick GitHub Demo](https://github.com/xticktop/DemoXtickJava)
> - [StockApi.cn](https://www.stockapi.com.cn)
> - [知乎: A股实时数据源深度对比](https://zhuanlan.zhihu.com/p/2023293142783238466)
> - 本仓库 `data_source_governance.py`, `hermes_launcher.py`, `.env`
