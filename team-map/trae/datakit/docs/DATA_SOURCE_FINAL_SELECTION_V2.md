# 🎯 数据源综合选型报告 V2 — 含 a-stock-data 深度评估

> **生成日期**: 2026-07-07  
> **合并来源**: `DATA_SOURCE_VERSION_SURVEY.md` + `DATA_SOURCE_SELECTION.md` + `NODE_API_FIELD_MATRIX.md` + `a-stock-data` GitHub 仓库  
> **预算上限**: ¥100/月（可接受付费方案，单源/组合均可）  
> **当前总月费**: ¥199 (TickFlow Expert) + ¥89 (i问财进阶版) ≈ **¥288/月**
> **V2 新增**: a-stock-data (V3.3.0, 6.7k⭐, Apache 2.0) 独立深度评估 + 逐字段适配 + 三年 TCO

---

## 一、当前数据源总览（现状基线）

### 1.1 运行拓扑

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

### 1.2 TickFlow 各版本能力矩阵

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

**关键结论**: Pro (¥99/月) 具备除财务数据外的全部核心能力（分钟K/WS/五档盘口），可节省 50% 月费。当前本项目**未实际消费 Expert 独有的财务数据和除权因子**（代码探测通过但无调用路径）。

### 1.3 i问财 各渠道对比

| 渠道/版本 | 类型 | 价格 | 自动化 | 生产合规 | 本地在用 |
|-----------|------|------|--------|----------|----------|
| **iwencai.com Web** | 免费网页 | ¥0 | ❌ | ❌ | ❌ |
| **SkillHub 技能商店** | 免费技能市场 | ¥0 | ✅ | ✅ | ✅ 6个skills |
| **openapi.iwencai.com** | API 服务 | ⚠️ 未公开标价 | ✅ | ✅ | ✅ 当前主用 |
| **同花顺 iFinD** | 企业级 | ¥数万-数十万/年 | ✅ | ✅ | ❌ 超预算 |
| **SuperMind query_iwencai** | 平台函数 | 随平台 | ❌ 不可独立 | ❌ | ❌ |
| **pywencai (非官方)** | 社区工具 | ¥0 | ⚠️ | ❌ 禁止 | ❌ |

---

## 二、节点级数据需求（精确到字段 × 频率）

> 来源: `NODE_API_FIELD_MATRIX.md` 逐字段逆向分析

### 2.1 时间线 × API 调用总矩阵

```
时间        节点                TickFlow API              Eastmoney API            iwencai
─────────────────────────────────────────────────────────────────────────────────────────
08:00      data_preloader      klines/batch ×~32          sectors ×1              (离线payload)
08:00      data_source_gov     无                         (引用data_preload输出)   (引用离线payload)
09:15      auction_monitor     WS stream (持续10min)       live_sectors ×2         无
                                                                  +sector_map ×~22
09:25      decision_engine     无 (纯本地JSON)            无                      无
09:30      d2_engine           WS stream (持续10min)      无                      无
09:40      d2 结束             断开WS                     —                       —
10:01      decision_engine     quotes ×~N/50批            无                      无
  ↓        terminal_report     (取limit_up_stocks清单)
(降级)     d2_rest_fallback    klines/batch(1m) ×1        无                      无
                               +quotes ×~N/50批
─────────────────────────────────────────────────────────────────────────────────────────
```

### 2.2 每交易日 API 调用次数总账

| 源 | 调用次数 | 类型 |
|----|----------|------|
| TickFlow K线 | ~32 | REST GET |
| TickFlow WS | 2条连接 × 10min | WebSocket |
| TickFlow 终端报价 | ~N/50 批 | REST GET |
| Eastmoney 板块 | 1–3 次 | REST GET |
| Eastmoney 成分股 | 0–22 次 | REST GET |
| iwencai | 0（实时）+ 1（手动门控） | — |

### 2.3 每个节点对 TickFlow 的精确字段需求

| 节点 | 端点 | 必需字段 | 频率 | 关键程度 |
|------|------|----------|------|----------|
| **data_preloader** | `klines/batch?period=1d` | symbol, close[2], volume[2], amount[2], high[2], low[2] | 每日 ~32次HTTP | 🔴 P0 |
| **auction_monitor** | `ws/stream` | symbol, last_price, open, volume, amount, change_pct, timestamp(ms), name | 10分钟WS流 | 🔴 P0 |
| **d2_engine** | `ws/stream` | symbol, open, last_price, volume | 10分钟WS流 | 🔴 P0 |
| **decision_engine** | `quotes` | **仅** last_price, open | 每日 ~N/50次HTTP | 🟡 P1 |
| **d2_rest_fallback** | `klines/batch?period=1m` + `quotes` | close[0], last_price, volume | 降级时一次性 | 🟡 P1 |

### 2.4 替代数据源的最低字段门槛

**K线接口**:
```
symbol, date, open, high, low, close, volume(手), amount(元)
period=日线, 至少前2交易日
```

**实时行情接口**:
```
symbol, last_price, open, high, low, volume, amount, prev_close, change_pct, timestamp(ms), name
支持: 批量订阅(≥100只) + 单次快照(≥50只/批)
```

---

## 三、🆕 a-stock-data 独立深度评估

> **GitHub**: https://github.com/simonlin1212/a-stock-data  
> **版本**: V3.3.0 (2026-06-28) | **Stars**: 6,700+ | **Forks**: 1,300+  
> **协议**: Apache 2.0 | **月费**: ¥0 | **依赖**: `mootdx requests pandas stockstats`

### 3.1 架构本质

a-stock-data **不是传统 API/SDK**——它是一个 AI 编程助手的 Skill 文件（SKILL.md），内嵌可直接执行的 Python 代码段，聚合了 **13 个免费数据源**的调用逻辑：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    a-stock-data = SKILL.md (Apache 2.0)               │
│                                                                      │
│  pip install mootdx requests pandas stockstats                       │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 第1层: 行情层 (不封IP)                                         │  │
│  │   mootdx(TCP :7709) → K线(多周期)+五档盘口+逐笔成交+46字段行情  │  │
│  │   腾讯财经(HTTP)    → 日K+MA均线+PE/PB/市值/换手率              │  │
│  │   百度股市通(HTTP)  → 日K+MA5/10/20                             │  │
│  │                                                                  │  │
│  │ 第2层: 研报层                                                   │  │
│  │   东财 reportapi → 个股/行业研报+三年EPS预测+PDF下载             │  │
│  │   同花顺一致预期 → EPS一致预期                                   │  │
│  │   iwencai(需Key) → NL语义跨主题研报检索                          │  │
│  │                                                                  │  │
│  │ 第3层: 信号层                                                   │  │
│  │   同花顺热点   → 强势股+题材归因                                  │  │
│  │   同花顺HSGTCG → 北向资金(分钟级实时262点+历史自缓存)            │  │
│  │   东财push2    → 行业板块排名+资金流向(超大/大/中/小单)          │  │
│  │   东财datacenter → 龙虎榜席位+限售解禁日历                        │  │
│  │                                                                  │  │
│  │ 第4层: 资金面/筹码层 (V3.0)                                      │  │
│  │   东财datacenter → 两融明细/大宗交易/股东户数/分红送转            │  │
│  │   东财push2     → 120日个股资金流                                 │  │
│  │                                                                  │  │
│  │ 第5层: 新闻层                                                   │  │
│  │   东财search-api-web → 个股新闻流                                 │  │
│  │   东财np-weblist     → 全球7×24财经资讯                           │  │
│  │                                                                  │  │
│  │ 第6层: 基础数据层                                                │  │
│  │   mootdx → 季报37字段快照+F10九大类公司资料                       │  │
│  │   新浪   → 三表(资产/利润/现金流)                                 │  │
│  │                                                                  │  │
│  │ 第7层: 公告层                                                   │  │
│  │   巨潮cninfo → 沪深北全量公告(6198只股,dynamic orgId)            │  │
│  │                                                                  │  │
│  │ 第8层: 打板层 (V3.3)                                            │  │
│  │   东财push2ex → 涨停池/炸板池/跌停池/昨日涨停池                    │  │
│  │   同花顺      → 涨停原因题材+封板成功率+连板梯队                  │  │
│  │                                                                  │  │
│  │ 第9层: ETF期权层 (V3.3)                                          │  │
│  │   新浪 → T型报价+希腊字母(Delta/Gamma/Theta/Vega)+隐含波动率      │  │
│  │                                                                  │  │
│  │ 第10层: 舆情互动层 (V3.3)                                        │  │
│  │   巨潮cninfo → 互动易问答(投资者提问+公司回复)                    │  │
│  │   同花顺     → 热榜                                              │  │
│  │   东财       → 人气榜+个股概念命中                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  10层 × 40端点 × 13数据源  |  除iwencai外全部免费无Key               │
│  数据源优先级: mootdx/腾讯 > 同花顺 > 百度/新浪/巨潮 > 东财           │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 逐节点精确字段映射（a-stock-data 替代 TickFlow）

以下基于 `NODE_API_FIELD_MATRIX.md` 中每个节点消费的每个字段，标注 a-stock-data 中的具体替代路径：

#### 节点 1: data_preloader（K线 → mootdx 日K）

| TickFlow 字段 | 代码行 | a-stock-data 替代 | 替代源 | 变更 |
|-------------|--------|------------------|--------|------|
| `close[0]` (prev_close) | 112 | `bars[-2].close` | mootdx ` bars(symbol, frequency=9, offset=1)` | 取倒数第二根K线 |
| `close[1]` (close) | 113 | `bars[-1].close` | mootdx 同上 | — |
| `volume[1]` | 119 | `bars[-1].vol` | mootdx 同上 | 字段名 vol→volume |
| `amount[1]` | 122 | `bars[-1].amount` | mootdx 同上 | ✅ 直接提供 |
| `high[1]` | 128 | `bars[-1].high` | mootdx 同上 | — |
| `low[1]` | 130 | `bars[-1].low` | mootdx 同上 | — |

> ⚠️ **不复权警告**: mootdx K线为原始价不复权。跨除权除息日时 close 会有价格跳变。本项目仅用前 2 个交易日，**除权概率极低**。若发生，可切换腾讯财经日K（前复权，但无 amount 字段）作为降级。

#### 节点 2: auction_monitor（实时流 → mootdx TCP 订阅）

| TickFlow WS 字段 | 代码行 | a-stock-data 替代 | 替代源 | 变更 |
|-----------------|--------|------------------|--------|------|
| `symbol` | 401,82,86-90 | `quote['code']` | mootdx `Quotes.factory(market='std').quotes(symbols)` | 格式: `600001` (无后缀) |
| `last_price` | 82,326,55,528 | `quote['price']` | mootdx 同上 (字段索引3) | 字段名 price→last_price |
| `open` | 55,82,326,529 | `quote['open']` | mootdx (索引4) | — |
| `high` | 528,529 | `quote['high']` | mootdx (索引33) | — |
| `low` | 528,529 | `quote['low']` | mootdx (索引34) | — |
| `volume` | 83,119-128,327,530 | `quote['cur_vol']` | mootdx (索引6) | 需确认单位(手)一致 |
| `amount` | 84,119-123,530 | `quote['amount']` | mootdx (索引37) | ✅ 直接提供 |
| `prev_close` | 531 | `quote['pre_close']` | mootdx (索引5) | — |
| `change_pct` | 86-88,135,525 | 需计算 | `(price - pre_close) / pre_close` | mootdx 不直接提供涨跌幅 |
| `name` | 89,526 | `quote['name']` | mootdx (索引1) | — |
| `timestamp` | 321,532 | `int(time.time()*1000)` | 本地 | mootdx TCP 推送不带时间戳，需本地打时间戳 |

#### 节点 3: auction_monitor（板块数据 → 东财 push2）

| 东方财富 push2delay 字段 | a-stock-data 替代 | 替代源 |
|-------------------------|------------------|--------|
| `f12` (板块代码) | 板块代码 | 东财 push2 (同接口) |
| `f14` (板块名) | 板块名 | 同上 |
| `f3` (涨跌幅) | 涨跌幅 | 同上 |
| `f62` (成交额) | 成交额 | 同上 |
| `f104/f105` (涨跌家数) | 涨跌家数 | 同上 |
| `f140/f128/f136` (领涨股) | 领涨股 | 同上 |
| — 🆕 | 主力/大单/中单/小单净流入 | push2 分钟级资金流向 (新增能力) |

#### 节点 4: d2_engine（实时流 → mootdx TCP 订阅）

| TickFlow WS 字段 | 代码行 | a-stock-data 替代 | 替代源 |
|-----------------|--------|------------------|--------|
| `data[].symbol` | 353-357,385-386 | `quote['code']` | mootdx 批量订阅 |
| `data[].open` | 357 | `quote['open']` | mootdx |
| `data[].last_price` | 205,231,233,270,277,357 | `quote['price']` | mootdx |
| `data[].volume` | 206 | `quote['cur_vol']` | mootdx |

#### 节点 5: decision_engine（终端报价 → mootdx 快照）

| TickFlow REST 字段 | 代码行 | a-stock-data 替代 | 替代源 |
|-------------------|--------|------------------|--------|
| `last_price` | 145,165 | `quote['price']` | mootdx `quotes(symbols)` 批量快照 |
| `open` | 145,165 | `quote['open']` | mootdx 同上 |

#### 节点 6: d2_rest_fallback（分钟K + 报价 → mootdx）

| TickFlow REST 字段 | a-stock-data 替代 | 替代源 |
|-------------------|------------------|--------|
| `data[symbol]["close"][0]` | `bars[0].close` | mootdx 1m K线 `bars(symbol, frequency=8, count=5)` |
| `data[].last_price` | `quote['price']` | mootdx 快照 |
| `data[].volume` | `quote['cur_vol']` | mootdx 快照 |

#### 节点 7: 涨停原因（i问财离线 → 同花顺涨停揭秘）

| iwencai 离线字段 | a-stock-data 替代 | 替代源 | 说明 |
|-----------------|------------------|--------|------|
| `涨停原因[YYYYMMDD]` | 涨停原因题材 | 同花顺涨停揭秘 | **在线获取**，盘后 15:30 更新 |
| `连续涨停天数` | 连板数 | 同上 | — |
| `封流比` | 封单/流通股 | 可计算 | — |
| `所属同花顺行业` | 同花顺行业 | 同花顺热点接口另取 | — |

> ⚠️ **模式变更**: 当前 iwencai 数据为离线预取（`rebuild_manifest/`），运行时不调 HTTP。切换为同花顺涨停揭秘则变为在线调用。需在 `data_source_governance.py` 中新增同花顺源注册。

### 3.3 核心工程问题：mootdx TCP 替代 TickFlow WebSocket

这是 a-stock-data 方案最关键的技术决策。两者协议、库、行为完全不同：

| 维度 | TickFlow WS | mootdx TCP |
|------|------------|------------|
| **协议** | JSON over WebSocket (wss://) | 通达信二进制协议 (TCP :7709) |
| **库** | `websockets` (Python) | `mootdx` (Python, 封装通达信协议) |
| **连接** | `await websockets.connect(url)` | `Quotes.factory(market='std').connect()` |
| **订阅** | `json.dumps({"op":"subscribe","symbols":[...]})` | `client.subscribe(['600001','000002',...])` |
| **推送格式** | JSON `{"op":"quotes","data":[{...}]}` | mootdx 解析后的 dict，46字段 |
| **心跳** | 25s ping（应用层） | TCP keepalive（系统级） |
| **重连** | `websockets` 自动重连 | **需手动实现**（指数退避+订阅恢复） |
| **IP要求** | 无限制 | **必须国内 IP**（海外 TCP 超时） |
| **SLA** | 商业 API（有保障） | 通达信官方服务器（免费，无 SLA） |
| **延迟** | ~50-200ms (WebSocket) | ~100-500ms (TCP，通达信推送间隔) |
| **数据频率** | 按需推送（每 tick） | 通达信固定周期推送（~3秒间隔） |

#### 对拍卖/竞价场景的精确影响

```
auction_monitor (09:15-09:25):
  TickFlow WS:  每个 tick 立即推送 → 动量计算基于真实 tick 时间戳
  mootdx TCP:   ~3秒周期推送 → 动量窗口(120秒)需容纳 ~40个数据点 → 仍可行
                但 momentum_slope 时序精度降低

d2_engine (09:30-09:40):
  TickFlow WS:  每个 tick 立即推送 → VWAP 曲线精确
  mootdx TCP:   ~3秒周期 → VWAP 累计算法不变，但粒度降低
                last_price 采样间隔从 ~100ms 扩大到 ~3s

关键判断: 对于本项目 10分钟级别的竞价/D2窗口，3秒粒度完全可接受。
           动量斜率(VWAP/PA)使用的是分钟级趋势，而非毫秒级。
```

#### 适配工作量估算

| 文件 | 改动范围 | 预估行数 | 关键难点 |
|------|----------|----------|----------|
| `auction_monitor.py` | 重写 WS→TCP 连接+消息循环 | ~150行 | TCP 重连 + 订阅恢复 |
| `d2_engine.py` | 同上，不同订阅列表 | ~120行 | 与 auction_monitor 共享 TCP 连接还是各自独立 |
| `data_preloader.py` | REST 批量→mootdx 批量K线 | ~80行 | 不复权处理 + 符号格式转换 |
| `decision_engine.py` | REST→mootdx 快照 | ~30行 | 符号格式: `600001.SH`→`600001` |
| `d2_rest_fallback.py` | REST→mootdx 分钟K+快照 | ~40行 | — |
| `data_source_governance.py` | 新增 mootdx/腾讯/东财/同花顺 源注册 | ~60行 | 多源冲突解决逻辑 |
| `requirements.txt` | 新增依赖 | +2行 | `mootdx`, `stockstats` |
| **合计** | | **~480行** | 5个节点 + 治理层 |

### 3.4 东财风控对本项目的实际影响

a-stock-data 内置了东财接口的完整限流机制，需要评估本项目调用频率是否触发：

| 东财风控阈值 | 本项目峰值 | 是否触发 | 说明 |
|-------------|-----------|----------|------|
| 每秒 > 5 次 | **≤2 次/秒** (板块查询+成分股) | ❌ 不触发 | 本项目调用量极低 |
| 并发 ≥ 10 | **单线程** (所有 DAG 节点串行) | ❌ 不触发 | — |
| 1分钟 ≥ 200 次 | **≤3 次/分钟** | ❌ 不触发 | — |
| 5分钟 ≥ 300 次 | **≤6 次/5分钟** | ❌ 不触发 | — |

> ✅ **结论**: 本项目东财调用量远低于风控阈值。a-stock-data 内置的串行限流（≥1s间隔+随机抖动）完全满足需求且不会触发封禁。

### 3.5 a-stock-data 与现有 SkillHub 生态的关系

a-stock-data 已作为 Skill 安装在 `/Users/fiona/.claude/skills/a-stock-data/`。这意味着：

- ✅ 本地 AI 助手已可直接调用 a-stock-data 内嵌代码获取数据
- ✅ 与现有 iwencai SkillHub skills 数据源互补（前者管行情+基本面，后者管涨停原因）
- ⚠️ **但 DAG 节点是独立 Python 脚本，不能直接"调用 skill"**——需从 SKILL.md 中提取内嵌 Python 代码为可 import 的独立模块
- ✅ a-stock-data 内置了 4 套调研流程（单票估值 30s、批量对比 1min、主题研报 2min、新标的调研 1min），可在治理层引用

---

## 四、候选方案全景对比

### 4.1 所有候选源一览

| # | 名称 | 类型 | 月费 | WS实时 | 竞价 | 板块 | 分钟K | 批量 | 日K |
|---|------|------|------|--------|------|------|-------|------|-----|
| 1 | **TickFlow Pro** (降级) | API | ¥99 | ✅ WS | ✅ | ❌ | ✅ | ✅ | ✅ |
| 2 | **a-stock-data** 🆕 | 内嵌代码 | **¥0** | ⚠️ TCP | ✅ 五档 | ✅ 双源 | ✅ | ✅ | ✅ 三源 |
| 3 | **黑狼数据 fxyz** | API | ¥30-80 | ❌ HTTP | ✅ | ⚠️ | ✅ | ✅ | ✅ |
| 4 | **StockApi.cn** | API | ¥30-50 | ❌ HTTP | ✅ | ⚠️ | ✅ | ⚠️ | ✅ |
| 5 | **iTick Free** | API | ¥0 | ✅ WS | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| 6 | **iTick Pro** | API | ~¥360 | ✅ WS | ⚠️ | ❌ | ✅ | ✅ | ✅ |
| 7 | **XTick** | API | 未公开 | ✅ WS | ✅ | ❌ | ✅ | ✅ | ✅ |
| 8 | **AKShare** | Python库 | ¥0 | ❌ | ❌ | ✅ | ✅ | ⚠️ | ✅ |
| 9 | **SuperMind** | 平台 | ¥0(受限) | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ✅ |

### 4.2 维度匹配矩阵

| 需求维度 | TickFlow Pro | a-stock-data 🆕 | 黑狼 | iTick Free | AKShare |
|----------|-------------|-----------------|------|------------|---------|
| **日K线(全市场)** | ✅ | ✅ mootdx+腾讯+百度 | ✅ | ❌ | ✅ |
| **实时行情推送** | ✅ WS 100标的 | ⚠️ TCP ~3s间隔 | ❌ HTTP | ✅ WS | ❌ |
| **实时行情 REST** | ✅ | ✅ mootdx 46字段 | ✅ 53字段 | ✅ (限5次/分) | ✅ |
| **分钟K线** | ✅ 12月 | ✅ mootdx多周期 | ✅ | ❌ | ✅ |
| **集合竞价** | ✅ WS间接 | ✅ 五档盘口+逐笔 | ✅ 竞价接口 | ⚠️ depth | ❌ |
| **板块排名** | ❌ | ✅ 东财push2+同花顺 | ⚠️ | ❌ | ✅ 双源 |
| **板块-成分股映射** | ❌ | ✅ 东财slist | ❌ | ❌ | ✅ |
| **涨停原因解释** | ❌ | ✅ 同花顺涨停揭秘 | ❌ | ❌ | ⚠️ |
| **批量查询(≥50只)** | ✅ | ✅ mootdx批量 | ✅ | ❌ | ⚠️ 逐只 |
| **月费** | ¥99 | **¥0** | ¥30-80 | ¥0 | ¥0 |
| **供应商锁定** | 🔴 单点 | 🟢 13源多路 | 🟡 单源 | 🟡 单源 | 🟢 开源 |
| **IP要求** | 无 | ⚠️ mootdx需国内 | 无 | 无 | 无 |

---

## 五、五大方案详细对比

### 方案 A: TickFlow Pro 降级（最平滑）

```
TickFlow Pro (¥99/月) + 东方财富 (免费) + i问财 SkillHub (已有)
```

| 优点 | 缺点 |
|------|------|
| **零代码变更**（同一 API 体系，仅改 Key） | 失去 Expert 财务数据/除权因子（当前未实际使用） |
| WS+REST 协议完全兼容 | 分钟K 从"全量"降为"12个月"（本项目只用当天1mK，完全不受影响） |
| 省 ¥100/月 (50%) | 仍然单点依赖 TickFlow |
| 7/16 前可完成切换 | — |

### 方案 B: 黑狼数据 + AKShare（最经济付费）

```
黑狼数据 fxyz (¥30-80/月) + AKShare (免费) + i问财 SkillHub (已有)
```

| 优点 | 缺点 |
|------|------|
| 月费最低 ¥30-80 | **无 WebSocket**（核心风险，需 HTTP 轮询替代） |
| 黑狼53字段实时行情 + 竞价接口 | 轮询延迟增加，竞价精度下降 |
| AKShare 覆盖板块+涨停双源 | 必须写全新 adapter 层（两个全新 API） |
| 摆脱 TickFlow 单点依赖 | 迁移工作量大（~600行） |

### 方案 C: iTick Free WS + AKShare（零成本实验）

```
iTick Free WS (¥0) + AKShare (免费) + i问财 SkillHub (已有)
```

| 优点 | 缺点 |
|------|------|
| 完全免费 | iTick 免费版 REST 限速 5次/分钟 |
| WS 实时推送保留 | **无分钟K线** |
| Python SDK 现成 | 竞价数据弱（仅 depth，无集合竞价阶段数据） |
| 快速验证概念 | **无法独立支撑 DAG 全部节点** |

### 方案 D: 黑狼 + iTick WS + AKShare（组合最优）

```
黑狼数据 (¥30-80) + iTick Free WS (¥0) + AKShare (¥0) + i问财 (已有)
月费: ¥30-80
```

| 优点 | 缺点 |
|------|------|
| 黑狼主力 + iTick WS补实时 | 架构复杂：**3个适配器**，3套重连逻辑 |
| 所有维度全覆盖 | iTick free WS 可靠性未知（免费服务） |
| ¥30-80/月，远低预算 | 任一源故障影响链路 |

### 🆕 方案 E: a-stock-data 单源（零成本，最大自主权）

```
a-stock-data mootdx (¥0) + 腾讯财经 (¥0) + 东财 (¥0) + 同花顺 (¥0) + i问财 SkillHub (已有)
月费: ¥0
```

| 优点 | 缺点 |
|------|------|
| **完全免费**，无订阅/无到期/无配额焦虑 | WS→mootdx TCP 需重写 ~480 行适配代码 |
| 10层×40端点，远超本项目需求（仅需6个端点） | **mootdx 需国内 IP**（当前部署环境在国内 ✅） |
| 可顺便替换东方财富免费补充源（同花顺涨停揭秘替代i问财离线） | mootdx K线不复权，需腾讯前复权降级路径 |
| 13源多路冗余，无单点故障 | 东财有频率风控（本项目调用量远低阈值，不触发） |
| Apache 2.0，零供应商锁定 | 无商业 SLA，通达信服务器故障时无技术支持 |
| 本地已装 Skill，可立即启动影子运行 | — |

---

## 六、三年总拥有成本 (TCO) 对比

| 方案 | 月费 | 1年 | 3年 | 适配工时 (人日) | 适配折算成本 | **3年 TCO** |
|------|------|-----|-----|----------------|-------------|------------|
| **A: TickFlow Pro** | ¥99 | ¥1,188 | ¥3,564 | 0 | ¥0 | **¥3,564** |
| **B: 黑狼+AKShare** | ¥55(中位) | ¥660 | ¥1,980 | 5天 | ¥5,000 | **¥6,980** |
| **C: iTick+AKShare** | ¥0 | ¥0 | ¥0 | 3天 | ¥3,000 | **¥3,000** |
| **D: 黑狼+iTick+AKShare** | ¥55(中位) | ¥660 | ¥1,980 | 7天 | ¥7,000 | **¥8,980** |
| **E: a-stock-data** | **¥0** | **¥0** | **¥0** | 4天 | ¥4,000 | **¥4,000** |

> 适配折算成本按 ¥1,000/人日估算（内部开发机会成本）。
> 方案 A 适配成本为 0（仅改 Key，零代码变更）。

---

## 七、最终推荐

### 🥇 首选（立即行动）: 方案 A — 降级 TickFlow Pro (¥99/月)

**理由**:
- TickFlow Expert **到期 2026/7/16（仅剩 9 天）**，必须决策
- 本项目**未实际消费** Expert 独有的财务数据和除权因子
- Pro (¥99/月) 完全覆盖 5 个核心节点的全部必需字段
- **零代码变更，零迁移风险** — 只需改 `.env` 中的 Key
- 月费从 ¥199 → ¥99，降幅 50%

**行动清单**:
1. 🔴 **7/16 前**: 确认 TickFlow 官方是否支持 Expert→Pro 降级续费；若不支持，新购 Pro Key
2. 更新 `.env` 中 `TICKFLOW_API_KEY`
3. 运行 `tests/` 验证
4. 将 Key 从 `.env` 迁移到 `~/.openclaw/keys.env` 外挂引用

### 🥈 中长期目标（双轨并行）: 方案 E — a-stock-data (¥0/月)

**核心理由**:

1. **完全免费 + Apache 2.0**，零供应商锁定
2. 10层×40端点，本项目只需 ~6 个端点，绰绰有余
3. 覆盖 TickFlow Pro 不具备的板块/概念/龙虎榜/涨停揭秘——可顺便减少 i问财依赖
4. 13源多路冗余（mootdx 主 + 腾讯/东财/同花顺降级）
5. 3年 TCO = ¥4,000（仅一次性适配成本），vs 方案 A 的 ¥3,564

**双轨并行策略**:

```
                   现在                      2-4周后                   验证后
                    │                         │                         │
轨道 1 (生产):  TickFlow Pro ¥99/月  ────────→ 继续运行  ────────→ 降级为备用源
                    │                         │                         │
轨道 2 (影子):  a-stock-data ¥0/月  ──→ 静默采集+交叉验证 ──→ 切换为主源 → 停 TickFlow
                                                                       │
                                                                       ▼
                                                                  月费归零 ¥0
```

**影子运行四阶段**:

```
Phase 1 (第1周): 提取适配层
  ├── 从 SKILL.md 提取 mootdx/腾讯/东财/同花顺 内嵌代码
  ├── 封装为 mootdx_adapter.py (~200行)
  ├── 单元测试: 对标 TickFlow 字段名+格式
  └── 验证: 取5只样本股实时行情，逐字段对比 TickFlow

Phase 2 (第1-2周): 旁路部署
  ├── adapter 部署到 DAG 节点旁路 (IF_SHADOW=1 开关)
  ├── 输出 shadow_handoff/ 与主链路产物同级
  ├── 验证: auction_snapshot 字段完整度≥95%
  └── 验证: d2_decision 候选池重叠率≥80%

Phase 3 (第2-4周): 交叉验证 (5+ 交易日)
  ├── 日结对比: 每交易日 10:30 自动运行 compare_products.py
  ├── 对比维度: auction_snapshot / d2_decision / terminal_packet 三份产物
  ├── 对比指标: 候选池重叠率、PnL偏差、信号一致性
  └── 容差: PnL偏差 <5%, 信号方向一致率 >90%

Phase 4 (验证通过后): 全量切换
  ├── 向 data_source_governance.py 注册 mootdx 为 Tier-1
  ├── 将 TickFlow Pro 降级为 Tier-2 (仅 TCP 故障时启动)
  ├── 停 TickFlow Pro 订阅 (保留 Key 30天观察期)
  └── 月费归零
```

### 🥉 备选: 方案 D — 黑狼 + iTick WS + AKShare (¥30-80/月)

**适用场景**: a-stock-data 验证失败（如 mootdx TCP 不稳定）时的中间方案

---

## 八、i问财独立决策

| 决策 | 结论 | 理由 |
|------|------|------|
| 继续使用？ | ✅ 短期保留 | 进阶版 ¥268/季 到期 10/01，涨停原因覆盖率 100% |
| 长期去留？ | 🟡 取决于方案 E | 若 a-stock-data 同花顺涨停揭秘验证通过，可降级为免费版 |
| 升级专业版？ | ❌ 不推荐 | 价格未公开，且本项目不需要推理模型/大模型 |
| OpenAPI 配额 | 🟡 **待确认** | `sk-proj-` Key 是否包含在进阶版会员中还是另需付费 |

---

## 九、费用总账

### 短期 (7/16 前推荐)

| 项目 | 当前 | 推荐 (方案 A) | 节省 |
|------|------|------|------|
| TickFlow | ¥199/月 (Expert) | ¥99/月 (Pro) | **-¥100/月** |
| i问财 SkillHub | ¥89/月 (进阶版) | ¥89/月 (不变) | ¥0 |
| 东方财富 | ¥0 | ¥0 | ¥0 |
| **合计** | **¥288/月** | **¥188/月** | **-¥100/月 (35%)** |

### 中长期 (双轨验证后目标)

| 项目 | 短期 (方案 A) | 目标 (方案 E) | 节省 |
|------|------|------|------|
| TickFlow | ¥99/月 (Pro) | **¥0 (停用)** | **-¥99/月** |
| i问财 SkillHub | ¥89/月 (进阶版) | ¥89/月 (或降级免费版) | ¥0-89 |
| a-stock-data (mootdx+腾讯+东财+同花顺) | — | **¥0** | — |
| **合计** | **¥188/月** | **¥0–89/月** | **-¥99–188/月 (53–100%)** |

---

## 十、数据源字段映射速查

### TickFlow → a-stock-data (mootdx 实时行情 46字段)

| TickFlow 字段 | mootdx 字段 | 索引 | 说明 |
|---------------|------------|------|------|
| `symbol` | `code` | — | 格式: `600001` (mootdx) vs `600001.SH` (TickFlow)，需加后缀映射 |
| `last_price` | `price` | 3 | 最新价 |
| `open` | `open` | 4 | 开盘价 |
| `high` | `high` | 33 | 最高价 |
| `low` | `low` | 34 | 最低价 |
| `volume` | `cur_vol` | 6 | 现量(手) |
| `amount` | `amount` | 37 | 成交额(元) |
| `change_pct` | `pct_chg` (计算) | — | `(price - pre_close) / pre_close` |
| `prev_close` | `pre_close` | 5 | 前收盘 |
| `name` | `name` | 1 | 股票名称 |
| `bid1..5` / `ask1..5` | `bid1_price..bid5_price` + `bid1_vol..bid5_vol` | 9-28 | 五档盘口 |

> 完整 46 字段含：内外盘、委比委差、量比、换手率、市盈率等，远超本项目需求。

### TickFlow → a-stock-data (腾讯财经 K线，前复权)

| TickFlow K线字段 | 腾讯财经字段 | 说明 |
|-----------------|-------------|------|
| `close[0]`, `close[1]` | K线数组 close | **前复权**，优于 mootdx 原始价 |
| `volume[1]` | K线数组 volume | 成交量(手) |
| `amount[1]` | ⚠️ volume×price 估算 | 腾讯不直接提供成交额；或切回 mootdx 日K(提供 amount) |
| `high[1]`, `low[1]` | K线数组 high/low | — |

> ⚠️ **建议**: K线优先用腾讯（前复权），实时流用 mootdx TCP（速度快，46字段全）。
> data_preloader 中 `amount` 从腾讯 volume×close 近似，或切回 mootdx 日K（直接提供 amount 字段但不复权）。

### TickFlow → a-stock-data (同花顺 涨停揭秘 vs iwencai 离线)

| iwencai 离线字段 | 同花顺涨停揭秘字段 | 说明 |
|-----------------|-------------------|------|
| `涨停原因[YYYYMMDD]` | 涨停原因题材 | 在线获取，盘后 15:30 更新 |
| `连续涨停天数` | 连板数 | — |
| `封流比` | 封单/流通股 | 可计算 |
| `涨停封单额` | 封单额 | — |
| `所属同花顺行业` | — | 同花顺热点接口另取 |

### 东方财富 → a-stock-data (东财 push2 同源升级)

| 东方财富 push2delay | a-stock-data 东财 push2 | 说明 |
|--------------------|------------------------|------|
| `f12` (板块代码) | 板块代码 | — |
| `f14` (板块名) | 板块名 | — |
| `f3` (涨跌幅) | 涨跌幅 | — |
| `f62` (成交额) | 成交额 | — |
| `f104/f105` (涨跌家数) | 涨跌家数 | — |
| `f140/f128/f136` (领涨股) | 领涨股 | 同接口 |
| — 🆕 | 主力/大单/中单/小单净流入 | **新增能力** (分钟级资金流向) |
| — 🆕 | 个股概念命中+热度值 | **新增能力** |

---

## 十一、关键风险清单

| # | 风险 | 等级 | 应对 |
|---|------|------|------|
| 1 | TickFlow Expert 7/16 到期断服 | 🔴 P0 | 立即降级续费 Pro（方案 A） |
| 2 | API Key 明文暴露在 `.env` | 🔴 安全 | 迁移到 `~/.openclaw/keys.env` 外挂引用 |
| 3 | TickFlow 升级 v2 API 不兼容 | 🟡 P1 | 增加 `X-API-Version` 头校验 |
| 4 | i问财 OpenAPI 配额未知 | 🟡 P1 | 联系确认 `sk-proj-` Key 限额 |
| 5 | SkillHub CLI 0.0.4 → 后续版本兼容性 | 🟢 P2 | 锁定 6 个 skill 版本号哈希 |
| 6 | 黑狼数据/AKShare 数据质量未验证 | 🟢 P2 | Phase 1 影子运行交叉验证 |
| 7 | WebSocket 缺失场景下 HTTP 轮询精度不足 | 🟡 P1 | 竞价时段提速至 500ms 轮询 |
| 8 🆕 | **mootdx TCP 稳定性不及 TickFlow WS** | 🟡 P1 | 双轨并行验证 5+ 交易日；保留 TickFlow Pro 为降级源（方案 E Phase 4 后） |
| 9 🆕 | **mootdx 需国内 IP（海外部署不可用）** | 🟡 P1 | 当前部署环境在国内 ✅；若迁海外：走代理或切腾讯 HTTP |
| 10 🆕 | **通达信 K 线不复权，跨除权除息日价格跳变** | 🟢 P2 | 本项目只用前 2 个交易日日K，除权概率低；降级切腾讯前复权日K |
| 11 🆕 | **东财风控封 IP** | 🟢 P2 | 本项目东财调用量远低于风控阈值（见 3.4 节）；内置限流已处理 |
| 12 🆕 | **同花顺涨停揭秘在线获取 vs iwencai 离线预取模式不同** | 🟡 P1 | 需在 `data_source_governance.py` 中新增同花顺源，改用在线调用模式 |

---

## 十二、影子运行验证脚本设计

以下为 Phase 2-3 的自动验证脚本框架：

```python
# compare_products.py — 每日 10:30 自动运行
# 对比主链路(TickFlow)和影子链路(a-stock-data)三份关键产物

import json
import sys
from pathlib import Path

HANDOFF = Path("handoff")
SHADOW = Path("shadow_handoff")
DATE = sys.argv[1] if len(sys.argv) > 1 else None

PRODUCTS = [
    ("auction_snapshot.json", "symbol", ["last_price", "open", "volume", "amount", "change_pct"]),
    ("filtered_pool.json",   "symbol", ["auction_price", "score", "gate_penalty", "change_pct"]),
    ("d2_decision.json",     "symbol", ["entry_price", "confidence"]),
]

TOLERANCE = {
    "price": 0.02,     # 2% 价格偏差容忍
    "overlap": 0.80,   # 候选池重叠率 ≥80%
    "direction": 0.90, # PnL 方向一致率 ≥90%
}

def compare():
    for product, key_field, check_fields in PRODUCTS:
        main = load_json(HANDOFF / DATE / product)
        shadow = load_json(SHADOW / DATE / product)

        overlap, main_only, shadow_only = set_overlap(main, shadow, key_field)
        print(f"[{product}] 重叠={overlap:.1%} main独有={len(main_only)} shadow独有={len(shadow_only)}")

        if overlap < TOLERANCE["overlap"]:
            print(f"  ⚠️ 重叠率 {overlap:.1%} < 阈值 {TOLERANCE['overlap']:.0%}")

        for f in check_fields:
            diffs = field_diffs(main, shadow, key_field, f, TOLERANCE["price"])
            if diffs:
                print(f"  ⚠️ {f}: {len(diffs)} 只偏差>2%")

    # terminal_packet PnL 对比
    main_pnl = load_json(HANDOFF / DATE / "terminal_packet.json")
    shadow_pnl = load_json(SHADOW / DATE / "terminal_packet.json")
    direction_match = pnl_direction_match(main_pnl, shadow_pnl)
    print(f"[terminal_packet] PnL方向一致率={direction_match:.1%}")
```

---

## 十三、执行路线图

```
现在 (7/7)
  │
  ├─ 🔴 P0: 确认 TickFlow Expert→Pro 降级续费可行性
  │
  ├─ 🟡 P1: 联系 i问财 确认 sk-proj- Key 配额
  │
  ├─ 🟢 P2: 启动 a-stock-data 影子运行 (Phase 1)
  │          ├── 从 SKILL.md 提取适配代码
  │          ├── 封装 mootdx_adapter.py
  │          └── 取5只样本股逐字段验证
  │
7/16 ← Expert 到期
  │
  ├─ 方案A已就位: TickFlow Pro ¥99/月 运行中
  │
  ├─ 继续 Phase 2-3: 5+ 交易日交叉验证
  │
7/21-8/1 (验证完成)
  │
  ├─ 若 mootdx 验证通过 → Phase 4 全量切换 → 停 TickFlow → 月费归零
  │
  └─ 若 mootdx 不稳定 → 继续方案 A，评估方案 D
```

---

> **Sources — 本报告引用**:
> - [a-stock-data GitHub](https://github.com/simonlin1212/a-stock-data) — V3.3.0, Apache 2.0, 6.7k⭐, 10层×40端点×13数据源
> - TickFlow 官网定价页 (tickflow.org, 2026-07-07)
> - i问财 SkillHub (iwencai.com/skillhub, 2026-07-07)
> - [AKShare GitHub](https://github.com/akfamily/akshare) — 14,000+ stars
> - [黑狼数据 fxyz](http://www.fxyz.site)
> - [iTick 官网](https://itick.org)
> - 本仓库: `data_source_governance.py`, `NODE_API_FIELD_MATRIX.md`, `DATA_SOURCE_VERSION_SURVEY.md`, `.env`
