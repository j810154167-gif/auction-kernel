# 防守体系 — 数据陷阱

## TickFlow 分钟K线

- **拉历史**: `/v1/klines?symbol=X&period=1m&start_time=<ms>&end_time=<ms>&count=240`
- **不用** `/v1/klines/intraday` — 只返回今日数据
- **不用** `date` 参数 — 对分钟K无效，会导致返回今日数据
- **period 是 `1m`** — 不能用 `1min`
- **时间戳是毫秒**, 非秒。CST 时区计算: `datetime(2026,7,10,9,0,tzinfo=CST).timestamp()*1000`

## TickFlow WebSocket

- **SOCKS 阻断**: macOS 系统代理 127.0.0.1:2080 阻断 Python websockets
- **绕过**: 清空所有 proxy 环境变量 + `NO_PROXY='*'` + api_key 走 URL 参数
- **websockets 15.0.1**: 订阅用 `'op':'subscribe'` (非 `'action'`)
- **depth 格式**: `bid_prices`/`ask_prices` 并行数组，非 `bids`/`asks` dict
- **api_key**: 不支持 `extra_headers` 参数，必须在 URL query string 中传递

## 跨日时间边界

`plan` 在 0713 盘后跑，`monitor` 在 0714 凌晨/开盘跑时 `TODAY=0714` 会找错目录。
修复: `latest_handoff_dir()` → 找最近一个有 `defense_plan.json` 的 handoff 目录。
`suspended.json` 同理，必须和 plan 同目录。

## change_pct 双重乘100

`auction_engine.py:152` 已将 TickFlow raw `change_pct` (decimal, e.g. 0.00985) 转为 snapshot 中的 `change_pct: 0.985`。二次处理时如果再做 `abs < 1 → *100`，结果变成 98.5 (错误)。**处理 snapshot 值时不乘100。**

## 进攻引擎硬编码日期

`auction_engine.py:23-24` TODAY/YESTERDAY 需要每日手动更新。新交易日首次点火前必须修改这两行。

## data_preload 格式

`data_preload.json` 用 `limit_up_stocks` (list)，非 `stocks` (dict)。`auction_engine.py:119` 已修复为 list→dict 转换。若引擎重写需注意此格式差异。

## 竞价量 ≠ 实时量

09:25 分钟K的 volume 是真实拍卖量。09:30后的 volume 已是连续竞价累计量。
回测/盘后分析不可用 post-auction volume 做 Gate② 量能判断。
约束系统统一惩罚(-8)，不试图据此区分。

## 股票列表过滤

`all_stocks_20260306.csv` 格式: `sh.600000` → 转 `600000.SH`
独立建池过滤: 排除 000(指数) 8/4(北交) 688/300/301(科创/创业) ST
主板: 60xxxx.SH, 00xxxx.SZ, 002xxx.SZ, 003xxx.SZ
