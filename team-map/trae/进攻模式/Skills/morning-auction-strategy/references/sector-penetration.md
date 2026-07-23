# 题材穿透识别 — Sector Penetration Workflow

在竞价/开盘窗口内对指定题材做快速穿透分析，识别D1可行域内的标的。

## 触发

用户说题材名（如"CPO""人形机器人""商业航天""贵金属"），期望看到Gate⓪→Gate①→D1管线的全链穿透结果。

## 四步穿透

### ① iWencai拉取成分股

```bash
TRACE=$(python3 -c "import secrets; print(secrets.token_hex(32))")
curl -sS --max-time 15 \
  -H "Authorization: Bearer ${IWENCAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "X-Claw-Call-Type: normal" \
  -H "X-Claw-Skill-Id: hithink-sector-selector" \
  -H "X-Claw-Skill-Version: 1.0.0" \
  -H "X-Claw-Plugin-Id: none" -H "X-Claw-Plugin-Version: none" \
  -H "X-Claw-Trace-Id: ${TRACE}" \
  -d '{"query":"<题材>板块成分股 涨幅排名","page":"1","limit":"30","is_cache":"1","expand_index":"true"}' \
  "${IWENCAI_BASE_URL}/v1/query2data"
```

解析 `datas[]` 中的 `股票代码`/`股票简称`/`最新价`/`最新涨跌幅`。

### ② Gate⓪交叉 — 与昨日涨停池取交集

```python
import json
with open('handoff/2026-07-09/data_preload.json') as f:
    pool = json.load(f)
pool_syms = {s['symbol'] for s in pool['limit_up_stocks']}

sector_syms = set(extracted_codes)
hits = sector_syms & pool_syms
misses = sector_syms - pool_syms
# hits → Gate⓪通过, misses → 硬排除
```

### ③ Gate①实时竞价闸 — TickFlow REST

```bash
curl -sS --noproxy '*' -H "x-api-key: ${TICKFLOW_API_KEY}" \
  "https://api.tickflow.org/v1/quotes?symbols=${HIT_CODES}"
```

逐只检查 `price ∈ [vwap_floor, prev_close×1.07]`。

### ④ D1管线标记 — 从filtered_pool.json读取

```python
with open('handoff/2026-07-10/filtered_pool.json') as f:
    fp = json.load(f)
for c in fp['candidates']:
    if c['symbol'] in double_pass:
        m = c['marks']  # vwap_position, risk_odds, pool_type, anti_hft, orderbook
```

## 输出格式

分三层呈现:
- **Gate⓪+①双重通过** (D1可行域内): 表格含实时价/涨跌/VWAP/赔率/池类型
- **Gate⓪通过但①FAIL**: 标注失败原因（超天花板/跌破底）
- **Gate⓪排除**: 列表(不在昨日涨停池)

末尾附穿透率 `hits/total` 和板块强度概述。

## 交叉分析

多个题材穿透结果可做交集:
- 同一标的出现在多个题材 → 多栖标的, 题材叠加强度高
- 例: 0710中京电子 002579.SZ 三栖(人形机器人+CPO+商业航天)

## 已知局限

- **iWencai `is_cache=0`可能返回空**: QTime ~600-2300ms, 数据有时滞
- **sector_filter模块0匹配**: Eastmoney `fs=b:block_name`对概念板块不适用, 防御管线第一层全量标记 `sector: unknown`。穿透识别用iWencai替代Eastmoney做题材归因
- **WS阻断时反量化/筹码供需标记unknown**: 不影响穿透分析(Gate检查不依赖WS)
