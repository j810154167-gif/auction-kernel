#!/usr/bin/env python3
"""TickFlow WS 竞价长连接监控 — 涨停池实时行情
用法: TICKFLOW_API_KEY=xxx python3 -u scripts/ws_auction_monitor.py
后台: terminal(background=True) 配合 python3 -u 避免缓冲
"""
import asyncio, json, os, sys
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
API_KEY = os.environ.get("TICKFLOW_API_KEY", "")
WS_URL = f"wss://api.tickflow.org/v1/ws/stream?api_key={API_KEY}"

# 从 handoff/<上一交易日>/scoring_preload_mainboard.json 提取标的
# 脚本启动时自动读取；也可硬编码回退列表
PRELOAD_PATH = None  # 由调用方在运行时注入或脚本自发现

def ts():
    return datetime.now(CST).strftime("%H:%M:%S")

def fmt_row(sym, d):
    name = d.get('name', '?')
    price = d.get('last_price', 0)
    chg = d.get('change_pct', 0)
    vol = d.get('volume', 0)
    chg_str = f"{chg:+.4f}" if isinstance(chg, (int, float)) else str(chg)
    return f"{sym:12s} {name:6s}  {price:>8.2f}  {chg_str:>8s}  {vol:>8d}"

def load_symbols():
    """从最新 handoff preload 文件读取标的列表"""
    import glob
    pattern = os.path.expanduser("~/.hermes/workspace/handoff/*/scoring_preload_mainboard.json")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        print(f"[{ts()}] ❌ 未找到 preload 文件", flush=True)
        sys.exit(1)
    with open(files[0]) as f:
        data = json.load(f)
    symbols = [s['symbol'] for s in data['limit_up_stocks']]
    print(f"[{ts()}] 📂 读取 {files[0]} → {len(symbols)}只", flush=True)
    return symbols

async def monitor(symbols):
    try:
        import websockets
    except ImportError:
        print(f"[{ts()}] ❌ pip3 install websockets", flush=True)
        return

    latest = {}
    update_count = 0

    while True:
        try:
            print(f"[{ts()}] 🔌 连接 TickFlow WS ...", flush=True)
            async with websockets.connect(WS_URL, open_timeout=10, ping_timeout=60, proxy=None) as ws:
                print(f"[{ts()}] ✅ 已连接", flush=True)
                sub = json.dumps({"op": "subscribe", "channel": "quotes", "symbols": symbols})
                await ws.send(sub)
                ack = await asyncio.wait_for(ws.recv(), timeout=10)
                ack_data = json.loads(ack)
                print(f"[{ts()}] 📡 订阅: {ack_data.get('channel','?')} | {ack_data.get('count',len(symbols))}只", flush=True)

                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("op") != "quotes":
                        continue
                    items = msg.get("data", [])
                    for item in items:
                        sym = item.get("symbol", "?")
                        latest[sym] = {
                            "name": item.get("name", item.get("ext", {}).get("name", "?")),
                            "last_price": item.get("last_price", 0),
                            "change_pct": item.get("change_pct", item.get("ext", {}).get("change_pct", 0)),
                            "volume": item.get("volume", 0),
                            "open": item.get("open", 0),
                            "prev_close": item.get("prev_close", 0),
                        }
                    update_count += 1
                    if update_count % 5 == 0:
                        ranked = sorted(latest.items(), key=lambda x: abs(x[1].get("change_pct", 0)), reverse=True)
                        print(f"\n[{ts()}] 第{update_count}轮 |chg%|排序", flush=True)
                        for sym, d in ranked:
                            print(fmt_row(sym, d))
                    else:
                        for item in items:
                            print(f"[{ts()}] {fmt_row(item.get('symbol','?'), latest[item.get('symbol','?')])}")
        except asyncio.TimeoutError:
            print(f"[{ts()}] ⚠️ 超时，5s重连...", flush=True)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[{ts()}] ❌ {type(e).__name__}: {e}", flush=True)
            await asyncio.sleep(3)

if __name__ == "__main__":
    symbols = load_symbols()
    print(f"[{ts()}] 🚀 竞价WS监控 | {len(symbols)}只 | 截止09:30", flush=True)
    asyncio.run(monitor(symbols))
