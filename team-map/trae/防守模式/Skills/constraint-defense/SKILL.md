---
name: constraint-defense
description: >
  Constraint防守体系 v3 — L0(昨日双点区间)/L1(人工题材标注)/L2(跳空15分/盘中5分持续破位)。
  每天都是新的买入，无成本锚。台账: ledger.csv(status=active/suspended/sold)。
  四词点火: 建区间/监控/查防守/强化(中英文双通)。
  零共享面: 与进攻壳物理隔离。
  USE WHEN 用户说 防守/持仓监控/止损/锚点/对手盘/建区间/监控。
related: [scoring-strategy, hermes-auction-execution, profiles-defense]
---

# Constraint 防守体系 v3

## 架构定位

防守体系不替代进攻体系，是独立常驻的第二颗脑。

| | Scoring（进攻） | Constraint（防守） |
|------|------|------|
| 时区 | 盘中 09:15-09:35 | 盘后15:00-次日09:00 + 盘中静默监控 |
| 输出 | ★1~N排序 | 🔴卖出 / 🟡预警 |
| 决策权 | 你选+你入 | 你确认卖/不卖 |
| 关系 | 你手动维护 ledger.csv | plan 自动读 CSV，过滤 sold |

与进攻壳物理隔离——不同 workspace、不共享 core/scripts/config/handoff/memories/datakit。零共享面，唯一接口是人类（更新 ledger.csv 和 l1_map.json）。

### 核心原则

1. **每天都是新的买入。** 没有成本锚执念、没有浮盈/浮亏阶段概念。今天破了就卖，没破就继续——等于今天再次买入。
2. **沉默是正常。** 防守Agent 99%时间不输出任何东西。只在L2触发时弹出一条3秒可消化的消息。
3. **交互完归位。** 你决策后Agent立刻回到监控态，不追问、不追加分析。

### 交互协议

| 状态 | Agent | Jackson带宽 |
|------|------|:--:|
| 监控态 | 沉默，WS后台吃数据 | 0 |
| 触发点 | 弹出事实: "标的 现价 破区间下沿 持续X分钟 L1状态" | 3秒 |
| 交互态 | 展开L0+L1+L2全貌+WS盘口 | 决策 |
| 归位 | 卖/持有(=今日再次买入)，回监控 | 0 |

**只报事实。不决策。不追问。不报平安。**

## L0区间 — v3共识区间（2026-07-14）

### 演进

| 版本 | 算法 | 问题 | 实盘失败 |
|------|------|------|------|
| v1 | Top5量能分钟VWAP | 单点爆量坍缩（09:31占75%权重） | 合肥城建 跌停价在区间内→漏判 |
| v2 | 日K [最低, 爆量均价] | 恐慌锚（最低价被竞价幽灵压低） | 合肥城建 跌停=开盘价→锚失效 |
| v3 | Top5排除前三根→共识±2% | 当前 | 通过 |

### v3算法

1. 拉分钟K，按量排序取Top5
2. **排除开盘前三根**（09:31/32/33）——竞价消化/跟风/余波
3. 过滤后Top5加权均价 = **共识价**
4. 区间 = [共识×0.98, 共识×1.02]

### 不使用

- 日最低价（竞价幽灵打印——09:25的集中竞价最低价，不是真实换手价）
- 单分钟爆量加权（权重坍缩——09:31一分钟占全日量能75%）
- 开盘前三根（恐慌/跟风/假突破，不反映主力意图）

**对手盘分析**（入场时做一次，不滚动）：

| 位置 | 含义 |
|------|------|
| 成本 < 区间下沿 | 接恐慌盘，对手全被套，最优 |
| 成本在区间内 | 和主力同一价格带 |
| 成本 > 区间上沿 | 买在主力之上，对手随时可抛 |

### L1 — 题材方向（人，每日标注）

题材叙事是活的人类语言。**机器不自动推断、不编码、不固化。** 用户每日标注：标的当前被什么题材资金群体交易。

用户给一句标注，引擎用对标池计算方向：

| 对标池状态 | 信号 |
|------|:--:|
| 3+只全部上涨 | 🟢 bullish |
| 3+只全部下跌 | 🔴 bearish |
| 分化 | 🟡 mixed |

**关键规则**：用户换一句话，对标池就换。规则不固化，意识不衰减。

**来源**：合肥城建按行业是地产，但市场在交易长鑫IPO概念——静态行业分类在A股等于噪音。

### L2 — 破位检测（机器，盘中监控）

| 破位类型 | 阈值 | 逻辑 |
|------|:--:|------|
| **跌停/逼近跌停**（change_pct ≤ -9.5%） | **即时** | 不等破位，跌停本身就是最强信号 |
| 跳空低开（开盘价 < 区间下沿） | 15分钟 | 开盘消化，给更长时间验证 |
| 盘中破位 | 5分钟 | 盘中阴跌，快速确认 |

### 判定矩阵

| L2 | L1 | 判定 |
|:--:|:--:|------|
| 触发 | 🔴 bearish | **🔴 卖出** |
| 触发 | 🟢 bullish | 🟡 洗盘，暂持 |
| 触发 | 🟡 mixed | 🟡 观察 |
| 未触发 | — | ● 持有 |
| 个股突破区间上沿 | 任意 | 🟢 强势，L1不降级 |

**L1 bullish + L2触发 ≠ 卖出。** 板块在涨、个股低开=洗盘消化，不是破位（华天0709校准）。

**个股在区间上沿以上时，L1 bearish不拖累。** 板块弱但个股强=龙头特征（魅视科技0713校准）。

## WS 实时流

WS 已打通（quotes + depth），用于 L2 破位瞬间的二次确认：破位时拉盘口买卖比——承接还在=多等，卖盘堆积买盘消失=立刻确认。

**WS SOCKS 绕过**：
```python
# 清空代理环境变量
for k in list(os.environ.keys()):
    if 'proxy' in k.lower(): os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'

# api_key 走 URL 参数（websockets 15.0.1 不支持 extra_headers）
uri = 'wss://api.tickflow.org/v1/ws/stream?api_key=...'
# 订阅用 'op': 'subscribe'（非 'action'）
sub = json.dumps({'op':'subscribe','channel':'quotes','symbols':[...]})
```

## 强化防守挂件

悬置状态下按需调用。触发词 `强化 SYM`。详见 `references/reinforcement-module.md`。

核心能力：
- 全周期量能剖面（60日日K + 分钟K）→ 识别博弈带/入场区/空区/蓄力区
- 入场日大单方向分析（价格带买卖占比）→ 判断机构吸筹 vs 蜜罐陷阱
- 悬置处理策略：收紧防线（区间上移5%）或直接剔除（注意力释放）

**悬置状态只能由人类打破。机器报事实，不替人决策。**

## 不在框架内的

- **收盘决策** → 归人类。机器脑不替人做收盘判断。
- **动态参数**（赔率、周期定位）→ 未来函数，机器脑噪音。
- **全球金融潮汐** → 超越 A 股盘面，不纳入。
- **L2a 盘中新区间检测** → 盘中噪音，盘后复盘时有价值但不出现在实时监控中。
- **L1自动推断** → 题材叙事是活的，机器不编码。

## 校准案例

详见 `references/calibration-cases.md`。

| 案例 | L2 | L1 | 判定 | 结果 |
|------|:--:|:--:|------|:--:|
| 天奇 0706 | 🔴盘中破位 | 🔴智装全跌 | 🔴卖出 | ✅ 止损-1.3% |
| 华天 0709 | 跳空破位 | 🟢封测全涨 | 🟡洗盘 | ✅ 持有→涨停 |
| 华天 0713 | 跳空破位(短暂) | 🟡封测分化 | ●持有 | 未触发,但用户区间失效判定→卖出+15% |
| 魅视 0713 | 跳空→1分收回 | 🔴AI全跌 | 🟢强势 | 现价突破区间上沿 |
| 魅视 0714 | 持续19分破位 | 🔴AI全跌 | 🔴卖出 | 朱雀未发酵→开盘崩，浮亏超成本 |
| 合肥城建 0713 | 跳空→多次收回 | 🟡长鑫分化 | ●持有 | L1从地产🔴→长鑫🟡避免误触发 |
| 合肥城建 0714 | 一字跌停-10% | 🟡长鑫 | 🔴跌停 | 跌停价>旧区间下沿→v2漏判。v3共识区间+跌停检测修复 |

## 数据陷阱

- 分钟K拉历史：`/v1/klines?period=1m&start_time=<ms>&end_time=<ms>`，`date`参数无效
- `period=1m` 非 `1min`
- 不用 `/v1/klines/intraday`（只返回今日）
- 分钟K不含09:25竞价打印 → 日最低价 ≠ 分钟最低价（差可达0.15元）
- **L0区间v3**：不用日最低（幽灵价）、不用单分钟爆量（会坍缩）。用Top5排除前三根 → 共识±2%
- **跨日边界**：monitor 用 `latest_handoff_dir()` 而非 TODAY，防00:00后偏移
- **K线棒索引漂移**: 不能用固定索引查收盘价，必须解码timestamp建date_idx

## 引擎部署

完整拓扑位于 `/Users/fiona/.hermes/workspace/profiles-defense/`。

```
profiles-defense/
├── core/
│   ├── VERSION              ← 版本链: v→parent
│   └── defense/
│       ├── version.py       ← 预检: preflight()/read_version()/compute_module_sigs()
│       ├── zone.py          ← L0: get_zone()  opponent_analysis()
│       ├── breach.py        ← L2: check_breach()
│       ├── sector.py        ← L1: sector_signal()
│       └── reinforce.py     ← 强化: 多日量能+机构行为+悬置判定
├── scripts/
│   └── defense_engine.py    ← 主入口: plan / monitor / check
├── config/
│   ├── ledger.csv              ← 持仓台账 (替代旧update_list.json)
│   └── l1_map.json              ← 题材标注
├── data/
│   └── hermes-logs-0713.tar.gz  ← 溯源压缩包
├── memories/
│   └── defense-knowledge.md ← 持久记忆
├── datakit/                 ← 数据工具箱(备份, 50 files)
├── workflow.md              ← 人机协同四步法
└── handoff/{date}/
    ├── run_status.json       ← 预检产物
    ├── defense_plan.json     ← plan 产出
    └── breach_log.json       ← monitor 产出
```

### 版本链式管理

参照进攻体系规范。`core/VERSION` 定义版本链:

```
version: v20260713-defense-1
parent: v20260713
mode: constraint_defense
date: 2026-07-13
modules: zone(L0) breach(L2) sector(L1)
```

启动时 `plan`/`monitor` 自动执行 `core/defense/version.py preflight`:

| 检查项 | 内容 | 失败阻断 |
|------|------|:--:|
| VERSION | 文件存在+可解析 | ✅ |
| 日期对齐 | version date vs CST today | ✅ |
| 模块完整性 | zone.py/breach.py/sector.py 存在 | ✅ |
| 模块签名 | md5 散列 | ⚪ 仅记录 |
## 点火词

`建区间` / `监控` / `查防守 SYM` / `强化 SYM [成本]`
（五词封顶，和进攻壳对称。中英文双通：`plan`=`建区间`, `monitor`=`监控`, `check`=`查防守`, `reinforce`=`强化`）

### 强化防守（悬置状态）
盘后调用：`强化 001229.SZ 44.07`
分析多日量能结构 + 机构行为 + 外部催化剂依赖。
产出 `reinforce_*.json` → 你决定悬置 → 改 `ledger.csv` 一行 `active→suspended` + 更新 `entry_price=今收` → `建区间` 重跑。
次日监控自动标记 `⚠悬置`，和正常持仓一并监控，不区分老仓位新仓位。

### 引擎命令

```bash
cd profiles-defense
# 中文点火（推荐）
python3 scripts/defense_engine.py 建区间 2026-07-10
python3 scripts/defense_engine.py 监控
python3 scripts/defense_engine.py 查防守 002185.SZ
python3 scripts/defense_engine.py 强化 001229.SZ 44.07

# 英文兼容
python3 scripts/defense_engine.py plan 2026-07-10
python3 scripts/defense_engine.py monitor
python3 scripts/defense_engine.py check 002185.SZ
python3 scripts/defense_engine.py reinforce 001229.SZ 44.07
```

- `plan [日期]`: 盘后建L0区间，输出 defense_plan.json
- `monitor`: 盘中L2检测，输出 breach_log.json。触发时打印 🔴 卖出
- `check SYM`: 单票快检
- `reinforce SYM [cost]`: 🆕 强化防守分析 — 多日量能剖面+机构行为+悬置判定

### WS 用法

- 订阅行情: `{'op':'subscribe','channel':'quotes','symbols':[...]}`
- 订阅深度: `{'op':'subscribe','channel':'depth','symbols':[...]}`
- 深度字段: `bid_prices/ask_prices` (非 bids/asks dict)
- 仅L2触发时拉盘口做二次确认，不破位时不拉、不存、不展示

## 持仓台账 (ledger.csv)

防守池由 CSV 台账统一管理。格式：

```csv
symbol,name,entry_date,entry_price,status,catalyst,note
001229.SZ,魅视科技,2026-07-09,44.07,suspended,商业航天 朱雀火箭,机构买盘衰退
002208.SZ,合肥城建,2026-07-10,20.33,active,长鑫IPO/国产替代,
002185.SZ,华天科技,2026-07-08,22.53,sold,存储/封测,0713午后破位卖出
```

`status` 三态：
- `active` — 正常持仓，建区间+监控
- `suspended` — 悬置状态。entry_price 手动更新为昨收。等同于"每天都是新的买入"
- `sold` — 已卖出。保留记录，不参与建区间和监控

`建区间` 读取 `ledger.csv`，过滤 `status=active|suspended`，对每只票拉分钟K建L0区间。

悬置状态的日常操作：`强化 SYM` → 看报告 → 你决定悬置 → 改 CSV 一行 `active→suspended` + 更新 `entry_price=今收` → `建区间` 重跑。无需额外文件。

## 产物路径 (profiles-defense)

```
profiles-defense/
├── core/defense/                ← 引擎模块
│   ├── zone.py / breach.py / sector.py / version.py / reinforce.py
├── scripts/
│   └── defense_engine.py        ← 主入口 (中英文双通)
├── config/
│   ├── ledger.csv               ← 持仓台账 (替代旧update_list.json)
│   └── l1_map.json              ← L1标注 (人工维护)
├── handoff/{date}/
│   ├── defense_plan.json        ← plan 产出
│   ├── breach_log.json          ← monitor 产出
│   ├── run_status.json          ← 预检产物
│   ├── reinforce_*.json         ← 强化分析产出
├── memories/
│   └── defense-knowledge.md     ← 持久记忆
├── data/
│   └── hermes-logs-0713.tar.gz  ← 对话溯源
├── datakit/                     ← 数据工具箱(备份)
└── workflow.md                  ← 人机协同工作流
```

## 跨日边界

`监控` 使用 `latest_handoff_dir()` 找最近一个含 `defense_plan.json` 的目录，不绑定 `TODAY`。解决 plan 在 0713 盘后建、监控在 0714 开盘跑的时间偏移问题。

## 人机协同四步法

| 步 | 动作 | 点火 | 人类带宽 |
|:--:|------|------|:--:|
| ① | 扫一眼 breach_log | 15:00 打开 handoff | 10秒 |
| ② | 标L1：每只票一句话 | 编辑 l1_map.json | 30秒 |
| ③ | 建区间 | `建区间 0710` | 5秒 |
| ④ | 忘掉它 | — | 0 |

⑤(可选): 强化分析 → 你决定悬置 → 改 ledger.csv 一行 `active→suspended` → `建区间` 重跑 → 归位

详见 `profiles-defense/workflow.md`。进攻节奏：启动→D1→延→T。防守节奏：扫→标→建→忘。

## 养成陷阱

- 盘后不扫 → 破位没人知道，第二天带病开盘
- L1标随意 → 一句话决定卖不卖
- 点火词膨胀 → 进攻的"延"拆了D1/D2/T才稳定。防守五词封顶
