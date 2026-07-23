# 昨日涨停对照池 — 构建方法

> P0 关键操作。禁止使用缓存、fixture或小范围预加载作为昨日涨停池。

## 步骤

### 1. 加载标的全集

```python
import csv
symbols = []
with open('all_stocks_20260306.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        code = row['code']
        if row.get('tradeStatus', '1') != '1':
            continue
        if code.startswith('sh.'):
            sym = code[3:] + '.SH'
        elif code.startswith('sz.'):
            sym = code[3:] + '.SZ'
        else:
            continue
        # 主板块过滤
        if sym[:3] in ('600','601','603','605','000','001','002','003'):
            symbols.append(sym)
```

预期: ~3406 主板标的。

### 2. 批量拉取K线

```python
# count=3 是关键: closes[-3]=T-2, closes[-2]=T-1(昨日), closes[-1]=今日
for batch in chunks(symbols, 150):
    kd = tickflow(f"/klines/batch?symbols={','.join(batch)}&period=1d&count=3")
    for sym, bars in kd['data'].items():
        closes = bars['close']
        highs = bars['high']
        volumes = bars['volume']
        amounts = bars['amount']
        
        if len(closes) >= 3:
            close_yesterday = closes[-2]  # T-1
            close_today = closes[-1]      # T (今日开盘价)
            high_yesterday = highs[-2]
            change_pct = round((close_yesterday / closes[-3] - 1) * 100, 2)
            
            # 真实涨停判定
            is_near_high = close_yesterday >= high_yesterday * 0.98
            has_volume = amounts[-2] > 10_000_000  # >10M CNY
            
            if change_pct >= 9.5 and is_near_high and has_volume:
                limit_ups.append(sym)
```

### 3. 输出格式

保存到 `handoff/2026-07-XX/data_preload.json`:

```json
{
  "meta": {"date": "2026-07-XX", "scanned": 3406, "valid": 3374},
  "limit_up_stocks": [
    {
      "symbol": "000524.SZ",
      "name": "岭南控股",
      "close_0708": 9.85,
      "change_pct": 10.06,
      "vwap": 9.82,
      "vwap_floor": 9.16,
      "vwap_ceiling": 10.54
    }
  ],
  "count": 51
}
```

## 常见错误

| 错误 | 后果 | 修复 |
|------|------|------|
| count=2 | change_pct全是0(缺T-2基准) | count=3 |
| 用小范围池 | 漏掉大量涨停 | 全量3406扫描 |
| 不加near_high过滤 | ST/僵尸股混入 | close≥high×0.98 |
| 不加volume过滤 | 无量涨停混入 | amount>10M CNY |
| 索引[-2]/[-3]写反 | 拿到T-2的涨停不是昨日的 | closes[-2]=T-1, closes[-3]=T-2 |

## 快速重建（从 filtered_pool.json）

当 `data_preload.json` 缺失但同目录存在 `filtered_pool.json` 时，可跳过全量3406扫描，直接从 filtered_pool 重建：

```python
import json
from pathlib import Path

fp = json.loads(Path('handoff/<昨>/filtered_pool.json').read_text())
stocks = [{
    "symbol": c["symbol"],
    "name": c["name"],
    "vwap": c["vwap"],
    "vwap_floor": c.get("vwap_floor", c["vwap"] * 0.85),
    "prev_close": c["vwap"],
    "change_pct": c["change_pct"],
} for c in fp["active_candidates"]]

preload = {
    "meta": {"date": "<昨>", "source": "reconstructed from filtered_pool"},
    "limit_up_stocks": stocks,
    "count": len(stocks)
}
Path('handoff/<昨>/data_preload.json').write_text(json.dumps(preload, ensure_ascii=False, indent=2))
```

注意：此方法生成的池规模=filtered_pool 候选数（37量级），非全量3406扫描的原始池。适用于快启，不替代完整扫描。
