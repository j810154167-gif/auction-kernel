# 节点级 API 字段与频率矩阵

> 生成时间: 2026-07-07 | 基于 5 核心节点源代码的逐字段逆向分析

---

## 时间线总览

```
08:00 ─────────────────── 09:15 ──────── 09:25 ──── 09:30 ──────── 09:40 ──── 10:01
 │                            │              │          │               │          │
 ▼                            ▼              ▼          ▼               ▼          ▼
data_preloader          auction_monitor  decision_1   d2_engine      d2_end   terminal
(批处理, ~32次HTTP)      (WS持续流,10min)  (纯本地)   (WS持续流,10min)  (结束)  (1次HTTP)
 │                            │                           │                      │
 ▼                            ▼                           ▼                      ▼
TickFlow K线                TickFlow WS                TickFlow WS          TickFlow REST
Eastmoney 板块               Eastmoney 板块              (与auction_monitor   quotes
                             TickFlow REST (降级)        不同订阅列表)
```

---

## 节点 1: data_preloader（数据预加载）

### 时间窗口: 08:00–09:00（盘前一次性运行）

### API 调用 A: TickFlow 日K线批量查询

| 维度 | 详情 |
|------|------|
| **端点** | `GET https://api.tickflow.org/v1/klines/batch` |
| **认证** | `x-api-key: {TICKFLOW_API_KEY}` |
| **超时** | 20s，2次重试（429 用 1.5s×指数退避） |
| **批次大小** | 100只/次 |
| **总调用次数** | ~32次（~3194 只主板股 ÷ 100） |
| **批次间延迟** | 100ms |
| **调用频率** | 每交易日 1 次 |

#### 请求参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `symbols` | `600001.SH,000002.SZ,...` | 逗号分隔，每批100只 |
| `period` | `1d` | 日K线 |
| `count` | `2` | 取2根K线（昨天+前天） |
| `end_date` | `YYYY-MM-DD` (昨天 CST) | 截止日期 |
| `adjust` | `none` | 不复权 |

#### 响应字段逐字段使用表

| 字段路径 | 类型 | 代码行 | 用途 |
|----------|------|--------|------|
| `r["ok"]` | bool | 101 | 请求是否成功；失败则跳过该批次 |
| `r["error"]` | str | 104 | 错误信息（前100字符打到stderr） |
| `r["data"]["data"][symbol]` | dict | 106 | 单只股票K线数据容器 |
| `[symbol]["close"][0]` | float | 112 | **prev_close** — 前天收盘，分母 |
| `[symbol]["close"][1]` | float | 113 | **close** — 昨天收盘，涨跌幅分子 |
| `[symbol]["volume"][1]` | float | 119 | **volume_lots** — 昨天成交量(手) |
| `[symbol]["amount"][1]` | float | 122 | **amount** — 昨天成交额(元) |
| `[symbol]["high"][1]` | float | 128 | **high** — 昨天最高价 |
| `[symbol]["low"][1]` | float | 130 | **low** — 昨天最低价 |

#### 本地计算字段（从API响应派生）

| 计算字段 | 公式 | 用途 |
|----------|------|------|
| `change_pct` | `(close - prev_close) / prev_close` | 涨停候选筛选（≥9.8%） |
| `vwap` | `amount / (volume * 100)` | 均价锚点 |
| `vwap_floor` | `round(vwap, 4)` | 闸1下限 |
| `vwap_ceiling` | `round(vwap * 1.07, 4)` | 闸1上限(+7%) |
| `vwap_ceiling_pct` | `7.0` | 硬编码天花板百分比 |

### API 调用 B: 东方财富板块排名

| 维度 | 详情 |
|------|------|
| **端点** | `GET https://push2delay.eastmoney.com/api/qt/clist/get` |
| **认证** | 无（仅 Referer 头） |
| **超时** | 10s，无重试 |
| **调用频率** | 每交易日 1 次 |

#### 请求参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `pn` | `1` | 第1页 |
| `pz` | `10` | 取前10个板块 |
| `po` | `1` | 降序 |
| `fid` | `f62` | 按成交额排序 |
| `fs` | `m:90+t:2` | 行业板块 |
| `fields` | `f2,f3,f12,f14,f20,f62,f104,f105,f128,f136,f140` | 请求字段 |

#### 响应字段

| 字段 | 映射到 | 类型 | 用途 |
|------|--------|------|------|
| `data["rc"]` | — | int | 必须=0 |
| `data["data"]["diff"][i]["f12"]` | `code` | str | 板块代码(BK0470) |
| `data["data"]["diff"][i]["f14"]` | `name` | str | 板块中文名 |
| `data["data"]["diff"][i]["f3"]` | `change_pct` | float/null | 板块涨跌幅 |
| `data["data"]["diff"][i]["f62"]` | `turnover_amount` | float/null | 板块成交额 |
| `data["data"]["diff"][i]["f104"]` | `up_count` | int/null | 上涨家数 |
| `data["data"]["diff"][i]["f105"]` | `down_count` | int/null | 下跌家数 |
| `data["data"]["diff"][i]["f140"]` | `leading_stock_code` | str | 领涨股代码 |
| `data["data"]["diff"][i]["f128"]` | `leading_stock_name` | str | 领涨股名称 |
| `data["data"]["diff"][i]["f136"]` | `leading_change` | float/null | 领涨股涨幅 |

#### 输出文件
- `handoff/{date}/data_preload.json` — 包含 `limit_up_stocks[]` + `top_sectors[]`

---

## 节点 2: auction_monitor（集合竞价采集）

### 时间窗口: 09:15:00–09:25:00（连续10分钟）

### API 调用 A: TickFlow WebSocket 实时行情流 ⭐ 主力通道

| 维度 | 详情 |
|------|------|
| **端点** | `wss://api.tickflow.org/v1/ws/stream?api_key={KEY}` |
| **库** | `websockets` |
| **连接超时** | 10s open, 15s ping |
| **接收超时** | 3s（超时检查是否到09:25） |
| **心跳/进度** | 每25秒输出进度日志 |
| **最大订阅** | 100只（按昨日涨跌幅排序取前100） |
| **调用频率** | 每交易日 1 次连接，持续10分钟流式推送 |

#### WebSocket 出站消息（客户端→服务端）

```json
{
  "op": "subscribe",
  "channel": "quotes",
  "symbols": ["605081.SH", "601121.SH", ...]
}
```

| 字段 | 说明 |
|------|------|
| `op` | `"subscribe"` |
| `channel` | `"quotes"` |
| `symbols` | 最多100只，按昨日 `change_pct` 降序排列 |

#### WebSocket 入站消息 ①: 订阅确认

```json
{"op": "subscribed", "total": 97}
```

| 字段 | 代码行 | 用途 |
|------|--------|------|
| `op` | 378 | 确认 `== "subscribed"` |
| `total` | 380 | 日志记录订阅数量 |

#### WebSocket 入站消息 ②: 实时报价推送（核心数据流）

```json
{
  "op": "quotes",
  "data": [
    {
      "symbol": "605081.SH",
      "last_price": 12.35,
      "open": 12.20,
      "high": 12.50,
      "low": 12.10,
      "volume": 150000,
      "amount": 18525000.0,
      "prev_close": 11.80,
      "change_pct": 0.0466,
      "name": "某某股份",
      "timestamp": 1750324512000,
      "ext": {
        "change_pct": 0.0466,
        "name": "某某股份"
      }
    }
  ]
}
```

#### 每条报价的逐字段使用表

| 字段路径 | 类型 | 代码行 | 用途 |
|----------|------|--------|------|
| `symbol` | str | 401, 82, 86-90 | 股票标识（字典key，传参给过滤器） |
| `last_price` | float | 82, 326, 55, 528 | **竞价实时价**（主信号） |
| `open` | float | 55, 82, 326, 529 | 开盘价（last_price 为空时降级） |
| `high` | float | 528, 529 | 日内最高（快照输出） |
| `low` | float | 528, 529 | 日内最低（快照输出） |
| `volume` | float | 83, 119-128, 327, 530 | 成交量(手)；闸2用、动量用 |
| `amount` | float | 84, 119-123, 530 | 成交额(元)；闸2用 |
| `prev_close` | float | 531 | 前收盘（快照输出） |
| `change_pct` (顶层) | float | 86-88, 135, 525 | 涨跌幅（闸3用、评分用） |
| `name` (顶层) | str | 89, 526 | 股票名称（候选输出） |
| `timestamp` | int | 321, 532 | 报价时间戳(ms)，用于120秒动量窗口 |
| `ext.change_pct` | float | 87-88, 525 | 涨跌幅降级（若顶层不存在） |
| `ext.name` | str | 89, 526 | 名称降级（若顶层不存在） |

#### 本地计算字段（注入快照）

| 注入字段 | 代码行 | 算法 |
|----------|--------|------|
| `momentum_slope` | 164, 421 | 最近120秒内 `last_price` 线性回归斜率 |
| `momentum_vol_accel` | 165, 422 | 最近120秒内 `volume` 变化率（加速度） |

### API 调用 B: TickFlow REST 快照（降级模式）

| 维度 | 详情 |
|------|------|
| **端点** | `GET https://api.tickflow.org/v1/quotes?symbols=...` |
| **触发条件** | 非竞价时间（09:25之后调用） 或 WS 断开 |
| **批次大小** | 50只/次 |
| **超时** | 10s |
| **调用频率** | 仅在降级路径触发 |

响应字段与 WS `quotes` 消息中的 `data[]` 数组元素完全一致（同上表）。

### API 调用 C: 东方财富实时板块涨跌

| 维度 | 详情 |
|------|------|
| **端点** | `GET https://push2delay.eastmoney.com/api/qt/clist/get` |
| **调用次数** | 2次/运行（WS路径1次 + REST路径1次） |
| **超时** | 8s |

#### 请求参数

| 参数 | 值 |
|------|-----|
| `fields` | `f2,f3,f12,f14,f62` |
| `fs` | `m:90+t:2` |
| 其他 | 同 data_preloader |

#### 响应字段

| 字段 | 用途 |
|------|------|
| `f14` | 板块名（字典key） |
| `f3` | 板块涨跌幅（字典value） |

### API 调用 D: 东方财富板块-成分股映射（可选）

| 维度 | 详情 |
|------|------|
| **端点** | `GET https://push2delay.eastmoney.com/api/qt/clist/get` × N次 |
| **调用次数** | 最多22次（2种板块类型 × top10 × 每板块1次查成员） |
| **超时** | 6s（板块列表），5s（成员查询） |

#### 板块排行请求
- `fields=f3,f12,f14`, `fs=m:90+t:2` 或 `m:90+t:3`

#### 成分股请求（每个板块1次）
- `fields=f12`, `fs=b:{bk_code}`, `pz=200`
- 响应: `f12` = 6位股票代码

#### 输出文件
- `handoff/{date}/auction_snapshot.json` — 原始快照（所有订阅股票的最终报价）
- `handoff/{date}/filtered_pool.json` — 三闸过滤后的候选池

#### filtered_pool.json 候选字段（供下游消费）

| 字段 | 含义 | 来源 |
|------|------|------|
| `symbol` | 股票代码 | WS quotes |
| `name` | 股票名称 | WS quotes |
| `auction_price` | 竞价价格 | `last_price` |
| `auction_volume` | 竞价量 | `volume` |
| `auction_amount` | 竞价额 | `amount` |
| `change_pct` | 涨跌幅 | WS quotes |
| `vwap` | 昨日均价 | data_preload |
| `vwap_floor` | 均价下限 | data_preload |
| `vwap_ceiling` | 均价上限(+7%) | data_preload |
| `vwap_distance_pct` | 偏离均价百分比 | 本地计算 |
| `momentum_slope` | 价格动量斜率 | 本地计算 |
| `momentum_vol_accel` | 量加速度 | 本地计算 |
| `gate_penalty` | 闸门罚分累计 | 本地计算 |
| `penalty_reasons` | 罚分原因列表 | 本地计算 |
| `score` | 综合评分 | 本地计算 |

---

## 节点 3: decision_engine（决策引擎）

### 时间窗口: 09:25:10（D1）+ 10:01:00（终端报告）

### API 调用: TickFlow 实时报价 ⭐ 仅终端报告阶段

| 维度 | 详情 |
|------|------|
| **端点** | `GET https://api.tickflow.org/v1/quotes?symbols=...` |
| **触发时机** | 仅在 `terminal_report()` 阶段（≥10:01） |
| **使用符号** | 来自 `data_preload.json` 中所有 `limit_up_stocks[].symbol` |
| **批次大小** | 50只/次 |
| **批次间延迟** | 150ms |
| **超时** | 10s |
| **异常处理** | 静默吞异常 |
| **调用频率** | 每交易日 1 次 |

#### 响应字段使用表 — 极其精简

| 字段 | 代码行 | 用途 |
|------|--------|------|
| `symbol` | 63 | 字典key |
| `last_price` | 145, 165 | **退出价**（计算PnL的主力字段） |
| `open` | 145, 165 | 退出价降级（last_price=0时） |

> ⚠️ 整个 quote 对象虽被整体存储（`quotes[symbol]=it`），但只有 `last_price` 和 `open` 被实际解引用。其他字段（volume、amount、change_pct 等）在本节点不使用。

#### 输入文件消费详情

**`data_preload.json` → decision_engine**
| 消费字段 | 用途 |
|----------|------|
| `limit_up_stocks[].symbol` | 收集所有符号→批量查quote |

> data_preload 的其他字段（change_pct, vwap, volume_lots 等）**不在 decision_engine 中使用**

**`filtered_pool.json` → decision_1()**
| 消费字段 | 代码行 | 用途 |
|----------|--------|------|
| `candidates` | 79 | 候选数组 |
| `candidates[].symbol` | 105, 117, 124 | 股票标识 |
| `candidates[].name` | 105, 117, 124 | 股票名称 |
| `candidates[].auction_price` | 95, 106, 117, 125 | **D1入场价** |
| `candidates[].auction_volume` | 91 | 量得分 |
| `candidates[].change_pct` | 87, 109, 125 | 涨跌幅 |
| `candidates[].vwap_distance_pct` | 88, 109, 126 | VWAP偏离% |
| `candidates[].momentum_slope` | 89 | 动量得分 |
| `candidates[].gate_penalty` | 90, 110, 123, 126 | 闸门罚分 |
| `candidates[].score` | 86, 97-99, 109, 112-113, 126 | 综合评分 |

**`d2_decision.json` → terminal_report()**
| 消费字段 | 代码行 | 用途 |
|----------|--------|------|
| `s2_decision` | 162 | D2决策对象（可为null） |
| `s2_decision.symbol` | 164, 169, 173, 175 | D2股票 |
| `s2_decision.entry_price` | 165, 169, 175, 176 | D2入场价 |
| `s2_decision.confidence` | 174, 176 | 置信度 |

#### 输出文件
- `handoff/{date}/terminal_packet.json` — 含 D1/D2 决策、PnL、胜率统计

---

## 节点 4: d2_engine（二次决策引擎）

### 时间窗口: 09:30:00–09:40:00（S1: 09:30-09:35, S2: 09:35-09:40）

### API 调用: TickFlow WebSocket 实时行情流

| 维度 | 详情 |
|------|------|
| **端点** | `wss://api.tickflow.org/v1/ws/stream?api_key={KEY}` |
| **连接时机** | 09:30:00 准时连接 |
| **订阅确认超时** | 10s |
| **S1采集** | 09:30-09:35（300秒），2s recv超时循环 |
| **S2采集** | 09:35-09:40（300秒），2s recv超时循环 |
| **调用频率** | 每交易日 1 次连接，持续10分钟 |

> ⚠️ 与 auction_monitor 使用**同一个 WS 端点**但**不同的订阅列表**（d2用的是从 Pool1+Pool2 合并去重的候选符号）

#### 响应字段使用表 — 极简

| 字段 | 代码行 | 用途 |
|------|--------|------|
| `data[].symbol` | 353, 354, 357, 385, 386 | 股票标识、字典key |
| `data[].open` | 357 | **开盘价**：每只股票首次出现时捕获一次 |
| `data[].last_price` | 205, 231, 233, 270, 277, 357 | **最新价**：VWAP曲线计算、PA分析、S1/S2报警 |
| `data[].volume` | 206 | **量**：VWAP公式分母 |

#### 本地计算的信号

| 信号 | 算法 | 用途 |
|------|------|------|
| `vwap_curve` | 累计 `(price × Δvol) / Δvol` 的EWMA | D2趋势判断核心 |
| `pa_below_vwap_ratio` | 最近N个tick中 `last_price < vwap` 的比例 | 弱势确认 |
| `vwap_trend` | VWAP曲线斜率 | 方向判断 |

#### 输入文件
- `auction_snapshot.json` — Pool1 市场池
- `data_preload.json` — Pool1 降级
- 历史 `filtered_pool.json` / `d2_decision.json` / `terminal_packet.json` (T-1~T-5) — Pool2 历史池

#### 输出文件
- `handoff/{date}/d2_decision.json` — 含 S1 flags + S2 决策（symbol, entry_price, confidence）
- `handoff/{date}/decision_2.json` — 规范格式

---

## 节点 5: d2_rest_fallback（REST 降级）

### 时间窗口: 无时间限制，按需调用（WS不可用时触发）

### API 调用 A: TickFlow 1分钟K线

| 维度 | 详情 |
|------|------|
| **端点** | `GET https://api.tickflow.org/v1/klines/batch?symbols=...&period=1m&count=5` |
| **超时** | 15s |
| **调用频率** | 降级时一次性 |

#### 响应字段

| 字段 | 用途 |
|------|------|
| `data[symbol]["close"]` | 检查存在性 |
| `data[symbol]["close"][0]` | **首根1分钟K线收盘价** = 近似开盘参考价 |

### API 调用 B: TickFlow 实时报价

| 维度 | 详情 |
|------|------|
| **端点** | `GET https://api.tickflow.org/v1/quotes?symbols=...` |
| **批次** | 50只/次 |
| **超时** | 10s |

#### 响应字段

| 字段 | 用途 |
|------|------|
| `data[].symbol` | 字典key |
| `data[].ext.name` / `data[].name` | 股票名（日志） |
| `data[].last_price` | **当前价**（反转检测：price < open → 弱势） |
| `data[].volume` | **量**（vol > 0 才产生信号） |

#### 降级 D2 决策逻辑（比 WS 版大幅简化）

| 条件 | 结果 |
|------|------|
| `last_price < open AND volume > 0` | 确认反转信号 |
| `drop > 5%` | confidence = "high" |
| `drop > 2%` | confidence = "medium" |
| 其他 | 无信号 |

---

## 节点 6: iwencai / 数据源治理层（非实时路径）

### 时间窗口: 08:00–09:00（盘前治理）

### API 调用

| 调用 | 端点 | 频率 | 说明 |
|------|------|------|------|
| iwencai 健康检查 | `GET {IWENCAI_BASE_URL}/health` | 手动/门控触发 | 仅检查 HTTP 状态码，不取数据 |
| SkillHub CLI | 间接（CLI→openapi.iwencai.com） | **离线** | 6个 hithink-* skill 通过 CLI 调 openapi，**不在实时运行中调用** |

### iwencai 数据消费路径（离线预取 → 治理层引用）

本项目的 iwencai 数据**不走实时 HTTP**。流程如下：

```
SkillHub CLI (离线)
  hithink-astock-selector  →  rebuild_manifest/iwencai_limit_up_reason_full_20260630.json
  hithink-sector-selector  →  rebuild_manifest/iwencai_hithink_sector_selector_raw_top10.json
                                  │
                                  ▼
                          loop_governance.py  (门控：检查 payload 存在 + success=true)
                          data_source_governance.py  (碰撞对比：iwencai vs eastmoney)
                          runtime_loop.py  (直接引用 real payload 写入 collision)
```

### iwencai Payload 被引用的字段

**`iwencai_limit_up_reason_full_20260630.json`** (hithink-astock-selector 离线产出)

| 字段路径 | 用途 |
|----------|------|
| `.success` | 门控判断 |
| `.coverage.row_count` | 覆盖只数 |
| `.coverage.reason_coverage` | 涨停原因覆盖率(0-1) |
| `.rows[].股票代码` | 股票代码（e.g. "000004.SZ"） |
| `.rows[].股票简称` | 股票简称 |
| `.rows[].涨停原因[YYYYMMDD]` | ⭐ 核心字段 — 涨停原因解释文本 |
| `.rows[].所属同花顺行业` | 行业分类 |
| `.rows[].所属概念` | 概念分类 |
| `.rows[].连续涨停天数` | 连板天数 |
| `.rows[].几天几板` | 几板描述 |
| `.rows[].封流比` | 封单/流通股 |
| `.rows[].涨停封单量` | 封单手数 |
| `.rows[].涨停封单额` | 封单金额 |

### 治理层碰撞对比字段

`compare_explanation_sources(eastmoney, iwencai)` 对比以下维度：
- 板块名称重叠率 (sector_name_overlap)
- 股票→板块映射一致性 (mapping_consistency)
- 涨停原因覆盖率 (limit_up_reason_coverage)

---

## 时间线 × API 调用频率总矩阵

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

---

## 字段完整度评估

| 数据维度 | 来源 | 涉及节点 | 关键程度 |
|----------|------|----------|----------|
| **昨日K线(OHLCV)** | TickFlow klines/batch | data_preloader | 🔴 P0 |
| **实时报价(last_price)** | TickFlow WS + REST | auction_monitor, d2_engine, d2_rest_fallback, decision_engine | 🔴 P0 |
| **实时报价(volume/amount)** | TickFlow WS | auction_monitor, d2_engine, d2_rest_fallback | 🔴 P0 |
| **实时报价(timestamp)** | TickFlow WS | auction_monitor (动量窗口) | 🟡 P1 |
| **实时报价(change_pct)** | TickFlow WS | auction_monitor (闸3) | 🟡 P1 |
| **板块排名** | Eastmoney push2delay | data_preloader, auction_monitor | 🟡 P1 |
| **板块-成分股映射** | Eastmoney push2delay | auction_monitor (可选) | 🟢 P2 |
| **涨停原因解释** | iwencai SkillHub (离线) | 治理层(碰撞对比) | 🟢 P2 |
| **行业/概念分类** | iwencai SkillHub (离线) | 治理层(碰撞对比) | 🟢 P2 |

---

## 替代数据源的最低字段要求

基于以上逐字段分析，若替换 TickFlow，新数据源**至少**需提供：

### K线接口（替代 klines/batch）
```
symbol, date, open, high, low, close, volume(手), amount(元)
 period=日线, 至少前2个交易日
```

### 实时行情接口（替代 WS + REST quotes）
```
symbol, last_price, open, high, low, volume, amount, prev_close, change_pct, timestamp(ms), name
 支持: 批量订阅(≥100只) + 单次快照(≥50只/批)
```
