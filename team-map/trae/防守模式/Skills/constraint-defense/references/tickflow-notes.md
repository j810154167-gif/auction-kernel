# TickFlow 数据接入要点

## WS SOCKS 绕过 (macOS)

系统级 SOCKS proxy (127.0.0.1:2080) 阻断 Python WebSocket。

```python
import os, json
for k in list(os.environ.keys()):
    if 'proxy' in k.lower() or 'PROXY' in k:
        os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'

import websockets
# websockets 15.0.1 不支持 extra_headers → api_key 走 URL query
uri = 'wss://api.tickflow.org/v1/ws/stream?api_key=xxx'
async with websockets.connect(uri, ping_interval=20, close_timeout=5) as ws:
    sub = json.dumps({'op':'subscribe','channel':'quotes','symbols':['600000.SH']})
    await ws.send(sub)
```

- 订阅用 `'op': 'subscribe'` 非 `'action'`
- 深度字段: `bid_prices`/`ask_prices` 非 `bids`/`asks`
- 仅 L2 触发时拉盘口确认，不破位不拉

## 分钟K线历史数据

```bash
# 必须用 /v1/klines (非 /v1/klines/intraday)
# period=1m (非 1min)
# start_time/end_time 毫秒时间戳，date 参数无效
curl "https://api.tickflow.org/v1/klines?symbol=SYM&period=1m&start_time=<ms>&end_time=<ms>&count=240"
```

Python 时间戳计算:
```python
from datetime import datetime, timezone, timedelta
CST = timezone(timedelta(hours=8))
d = datetime(2026, 7, 10).replace(tzinfo=CST)
start = int(d.replace(hour=9, minute=0).timestamp() * 1000)
end = int(d.replace(hour=15, minute=0).timestamp() * 1000)
```

### 响应格式 — 列式数组
```json
{"data": {
  "timestamp": [1783353600000, ...],
  "open": [69.01, ...],
  "high": [73.23, ...],
  "low": [68.70, ...],
  "close": [71.06, ...],
  "volume": [1031292, ...],
  "amount": [7359232001.0, ...]
}}
```
- 非行式，需 `sorted(zip(ts, op, hi, lo, cl, vol, amt))` 组合
- 日K count=5 返回最近5日，bar[-2]=昨日, bar[-1]=今日

## change_pct 双重乘100陷阱

`auction_snapshot.json` 中的 change_pct 已经被引擎处理过（`*100`），
二次导入时不要再乘100——否则会出现 +98.5% 等虚高值。

验证: 002975.SZ raw change_pct=0.00985(≈0.985%) → engine×100=0.985 → 再用会误×100=98.5

```python
# auction_engine.py 已做: ext.change_pct * 100 → 存入 snapshot
# 直接从 snapshot 读取时: 直接用，不要再乘
```

## 股票列表

路径: `/Users/fiona/.openclaw/workspace/runtime/20260618-morning-auction/data/static/all_stocks_20260306.csv`
格式: `code,tradeStatus,code_name` (如 `sh.600000,1,浦发银行`)

主板过滤 (Scoring回测/防守建池):
- ✅ 上海: 60xxxx → .SH
- ✅ 深圳: 00xxxx(非000), 002xxx, 003xxx → .SZ
- ❌ 科创板: 688xxx
- ❌ 创业板: 300xxx, 301xxx
- ❌ 北交所: 8xxxxx, 4xxxxx
- ❌ 指数: 000xxx
- ❌ ST: code_name 含 'ST'
