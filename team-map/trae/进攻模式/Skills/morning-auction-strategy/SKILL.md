---
name: morning-auction-strategy
description: >
  早盘竞价策略 — 点火词映射、前置检查清单、陷阱。
  USE WHEN 用户说 启动/监控/D1/延/T/竞价/早盘/对照池/涨停池。
---

# 早盘竞价策略

## ⛔ Agent 行为协议（不可违反）

加载本 Skill 后自动生效。违反任一条视为故障。

### 输出格式
- **D1 终端格式冻结**。当前为 markdown 表格（8 列）：

```
| ★ | symbol | name | price | chg% vs锚 | 得分 | L0 | 风控 |
|---|--------|------|------:|----------:|-----:|-----|------|
| ★1 | 603318.SH | 水发燃气(一字封板) | 9.30 | +8.77% | +15.8 | 🟢 | 🟢 |
```

- **列定义**：price=竞价价, chg%(vs VWAP)=竞 vs 昨VWAP, 得分=chg排序公式(×3×2已移除), L0=🟢/🟡/🔴, 风控=盘后风控灯。
- **渲染机制**：引擎 `print()` 输出 markdown 到 stdout, Agent 读取后直接在回复中渲染 markdown, 不重新排版。终端 stdout 与 Agent markdown 渲染是两套 UI——不可仅凭终端预览判断格式。
- **管线标记** 仅存于 JSON，不输出到终端。六模块通过 contextlib.redirect_stdout 静默。
- **未经用户明确指令，禁止修改列数、增删列、改变排序。**
- **输出格式修改流程：先仿写原文 → 用户对照确认 → 用户指定改动 → 再编码固化。禁止跳过仿写直接改。**

### 代码修改
- **先提案、等确认、再编码**。任何涉及输出格式、评分公式、排序逻辑的修改。
- **禁止自主优化**。"看看"≠"改"。
- **不要替用户加东西**。只做用户让做的事。

### 决策边界
- **排名归引擎，剃刀归人**。Agent 不替代人类判断。
- **数据校验归引擎，信号解读归人**。

### 运行窗口故障退出

任一点火节点失败时，Agent只输出四项并停止：

1. 失败节点；
2. 引擎或真实产物给出的事实；
3. 对当前运行链的影响；
4. `STOPPED / BLOCKED`状态。

禁止在进攻窗口读源码、补环境、修改生产、人工拼接或覆写正式产物。调查与恢复转到运维模式；运维交回固定入口与READY/BLOCKED状态后再继续运行。

## 博弈意识（0618起源）

A股 T+1 无卖空 + 中小资本无对冲 → 唯一防御 = 不下注在错的标的上。不是预测方向——是检测真金白银的多空对抗。

## 时间序 (v20260714)

```
盘后:  scan YYYY-MM-DD     ← 建池 (3045→N, ~70s)
       risk_scan YYYY-MM-DD ← 风控(标签+密区, ~30s)
       review YYYY-MM-DD    ← 挂起(数据管道保留)
盘前:  启动                 ← 链式校验
09:15: auction / WS启动     ← 竞价窗口起点，先启用行情采集并检查产物 meta.mode
09:25: D1                   ← Scoring ★1~N + 风控灯，读取已沉淀竞价快照
       ─── 人剃 ───
09:30: 延                   ← WS双快照追踪；必须渲染 extended_obs.json 表格
10:00: T                    ← 终审 P&L；必须渲染 terminal_review.json 表格
```

## 点火词

```
scan YYYY-MM-DD         → python3 scripts/auction_engine.py scan YYYY-MM-DD
风控 YYYY-MM-DD          → python3 scripts/auction_engine.py 风控 YYYY-MM-DD
review YYYY-MM-DD       → python3 scripts/auction_engine.py review YYYY-MM-DD
review_ready YYYY-MM-DD → python3 scripts/auction_engine.py review_ready YYYY-MM-DD
复盘 YYYY-MM-DD          → python3 scripts/auction_engine.py review_ready YYYY-MM-DD
启动                    → python3 scripts/auction_engine.py 启动
auction                 → python3 scripts/auction_engine.py auction  (09:15+；执行后必须检查 auction_snapshot.json 的 meta.mode/open/volume)
D1                      → python3 scripts/auction_engine.py D1
延                      → python3 scripts/auction_engine.py 延  (执行后必须读取 extended_obs.json 并渲染 R1/R2 表)
T                       → python3 scripts/auction_engine.py T   (执行后必须读取 terminal_review.json 并渲染终审表)
```

盘后完整链：`scan → 风控 → review → review_ready`。`review`只生成分钟K复盘缓存，不代表READY；`review_ready`才汇总并验收对照池、review、risk_labels、risk_zones。

## 三优化点 (0714)

| # | 内容 | 状态 |
|:--:|------|:--:|
| 一 | WS主链路竞价 | ⚪ 已编码，待竞价窗口实测 |
| 二 | 盘后分钟K review | ⚪ 挂起 |
| 三 | 链式校验层 | ✅ 测通 |

## 链式校验 (0714)

`MARKET_RULES`(前置) → ⓪时间 → ①数据源 → ②数据校验(违规自动重建池) → ③版本 → PROCEED/BLOCKED。主板tolerance=11.0%。ST=±10%。

## L0 生命线

昨日 VWAP 为基准线。D1 输出得分后一列。三级判定：竞 < VWAP → 🔴 破线｜竞 > VWAP×1.15 → 🔴 极端溢价｜竞 > VWAP×1.10 → 🟡 高溢价｜其余 🟢。VWAP 从昨日分钟K的 (H+L)/2 加权计算。显示前十行，计算覆盖全 28 只。

## 盘后风控 / T-1 risk_scan

T-1 盘后执行。产出两份数据：

- **risk_labels.json**: 涨停类型标签。一字封板(首5分四值等)/开盘冲(首段量>50%)/盘中推(三段均衡)/尾盘偷袭(尾段>中段×2)。D1 挂 name 列括号: `水发燃气(一字封板)`。
- **risk_zones.json**: 筹码密集带。涨停日分钟K价格-量分桶，取覆盖 60% 成交量的最窄连续价格带。自适应分档: 均价<10→0.01元/档, <50→0.05元/档, ≥50→0.10元/档。T日竞 < 下沿 → 🔴(昨天最密集成交被套)，其余 🟢。

任一产物缺失即判定 `T-1 risk_scan 缺位/跳位`：

| 缺失文件 | 失效能力 | D1 表现 |
|---|---|---|
| risk_labels.json | 涨停类型标签 | name 无括号标签 |
| risk_zones.json | 风控灯 | 风控列显示 `·` |

`name` 无括号标签 = 无 `risk_labels` 数据，不等于该股没有标签。`风控=·` = 无 `risk_zones` 数据，不等于安全。

### T-1 risk_scan 回补提示

- 09:10 前：提示回补命令 `python3 scripts/auction_engine.py 风控 {YESTERDAY}`。
- 09:10 后：只报缺失状态，不建议动作。
- 09:15 后：竞价窗口内不回补，不占用竞价-D1窗口。
- D1 后：只解释事实，不追问、不自动回补。
- 影响：D1 name 标签缺失，风控列显示 `·`。
- 此检查不 BLOCK D1。

D1 8 列:
```
| ★ | symbol | name | price | chg% vs锚 | 得分 | L0 | 风控 |
|---|--------|------|------:|----------:|-----:|-----|------|
| ★1 | 603318.SH | 水发燃气(一字封板) | 9.30 | +8.77% | +15.8 | 🟢 | 🟢 |
```

## 输出渲染陷阱与节点上报协议 (0714/0715)

**引擎 `print()` 输出到 stdout 的 markdown 表格 vs Agent 回复消息中渲染的 markdown 表格——格式相同但 UI 表现不同。** 终端 stdout 可能被截断或不渲染表格。确认 D1 输出的唯一正确方式：Agent 读取 stdout 后直接在回复中渲染 markdown。禁止仅凭终端预览判断格式。55 轮修改的核心根因。

### auction / D1 数据契约

auction 产物 `handoff/{TODAY}/auction_snapshot.json` 必须做语义质量检查，不得以“有 quotes/能 D1”替代“竞价数据有效”。检查项：`meta.mode`、quotes 数、last_price/open/volume/amount 有效数。

状态分级：
- READY：quotes 与 last_price 基本齐备，且 volume/amount 至少有有效字段参与 D1。
- DEGRADED：价格可用但 open/volume/amount 不完整；D1 可跑，但必须声明排序退化。
- INVALID：auction_snapshot 缺失、quotes 严重不足或 last_price 严重不足；不得输出正常交易排序，只输出诊断。

`volume=0` 不自动等于真实市场无量；若来自 REST 快照字段缺失，应视为采集路径降级，不得伪装成正常竞价信号。

### iWencai 09:25 最终竞价快照回补

TickFlow 历史 K 线不保存 09:15-09:25 集合竞价过程，`/quotes` 也不是历史快照接口；但 iWencai OpenAPI 可回补 09:25 最终竞价快照字段。实测查询形如：

```text
{symbol} {YYYY年M月D日} 09:25 集合竞价 成交量 成交额 开盘价
```

可返回：`竞价匹配价/开盘价`、`竞价匹配量/竞价量`、`竞价匹配金额/竞价金额`、`竞价涨幅`、`竞价未匹配量/金额`、`竞价异动类型/评级`。边界：只能回补 09:25 最终快照，不能回补 09:15-09:25 逐秒/逐tick/盘口撤单过程。

若 TickFlow auction_snapshot 出现 `mode=rest` 且 open/volume/amount 全缺失，应优先尝试 iWencai 回补 09:25 最终竞价快照，并将产物标记为 `mode=iwencai_replay` 或在 `data_quality` 中注明来源。

D1 输出前必须提示数据契约状态；`decision_1.json` 必须写入 `data_quality`，记录 `auction_contract`/auction_status、ranking_validity、缺失原因。auction_contract 至少包含 `volume_valid`、open_valid、amount_valid、quotes、mode。若 `top10_range` 分差过小且竞价量全缺失，必须提示排序区分度不足。

### 延 上报协议
每次执行 `python3 scripts/auction_engine.py 延` 后，必须：
1. 原样回传 stdout；
2. 读取 `handoff/{TODAY}/extended_obs.json`；
3. 渲染 R1/R2 两个表，列固定为：`symbol | 竞价价 | 当前价 | 变化 | 方向`。

禁止只报 `▲0 →2 ▼8` 或只报 `✓ extended_obs.json`。

### T 上报协议
每次执行 `python3 scripts/auction_engine.py T` 后，必须：
1. 原样回传 stdout；
2. 读取 `handoff/{TODAY}/terminal_review.json`；
3. 渲染终审表：`symbol | name | entry | exit | PnL | result`；
4. 渲染 summary：`total | wins | win_rate | total_pnl`。

禁止只报 `Terminal: 0/5 wins` 或只报 stdout。

## 评分公式 (v20260714 — ×3×2 已移除)

```
score = chg - max(0, dev-7) + min(vol/10000, 5) + vol_bonus - penalty × 0.4
```

chg×3 和 dev×2 乘法系数已移除。自然梯度，无断崖。

## 工作区

```
/Users/fiona/.hermes/workspace/
├── core/v20260713/          ← 当前引擎
└── scripts/auction_engine.py
```

## 陷阱

1. K线棒索引漂移: 解码 timestamp 建 date_idx，count=10。
2. 09:15 是竞价窗口起点。09:15+ 用户要求“启用 WS / auction / 进攻启动”时立即执行行情采集入口，并检查产物 `meta.mode`；不得以旧规则回复“09:25+ 再执行”。
3. `close_t1` vs `prev_close`：池里 prev_close 是 T-2 收盘。open_chg_pct 用 close_t1。
4. 链式校验：数据违规自动重建池，重建后仍有违规才 BLOCKED。
5. ⛔ 评分回测必须独立建池。
6. 延节点不自动停止——用户说"延"即拉新轮；执行后必须读取 `extended_obs.json` 并渲染 R1/R2 表。
7. T 节点执行后必须读取 `terminal_review.json` 并渲染终审表 + summary。
8. WS 已修复：清空 proxy 环境变量 + api_key 走 URL 参数；但若产物 `meta.mode=rest`，必须按事实说明不是 WS 常驻流。
9. **治理会话重跑会覆盖运行时产物**。评审必须看 session_search 原文。
10. **55轮修改根因**: Agent 跳过仿写直接改格式，每轮自以为"优化"。输出格式修改必须先仿写原文→用户确认→再改。协议已写入本 Skill 及 scoring-strategy 联动。不再犯。
