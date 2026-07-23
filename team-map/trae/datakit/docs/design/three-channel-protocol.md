# 三通道数据协议 — 架构设计

> 同步自 OpenSpec change `datakit-three-channel-protocol`（2026-07-10）
> 状态：设计已定稿，待实施（34 tasks in 9 phases）

## Context

datakit v1 将所有数据源输出强制归一化为标准化 Quote/Kline/BlockInfo 模型。这带来了统一接口的便利，但也造成了结构性损失：原始时间戳精度、adapter 特有的元数据、以及异常信号在 normalize() 转换过程中被丢弃。

```
datakit v1 输出:  [Normalized]  ← 只有一种视图
                    ↓
需要原始数据:       无 Raw 通道 → 无法获取
需要溯源:           无 Provenance 通道 → 无法追踪
按意图路由:         不存在 → 无视图区分
```

三通道升级解决的是这一结构断层。

## Goals / Non-Goals

**Goals:**
- 输出从单通道升级为三通道（Raw → Normalized → Provenance），Normalized 保持向后兼容
- 引入 `ConsumptionIntent` 枚举（realtime-decision / backtest / audit / full-trace）
- 引入 `ForwardAnchorCalendar`：调用方自定义时间锚点，datakit 提供查询/校验/窗口判断
- 调用方可通过 `intent=FULL_TRACE` 获取全部三个数据通道

**Non-Goals:**
- 不修改现有调用方代码（Normalized 通道保持向后兼容）
- 不预设任何业务锚点（锚点内容完全由调用方定义）
- 不实现 Raw 数据的实时告警（仅存储和透传）

## Key Decisions

### Decision 1: 三通道模型 — 一次调用三个视图

```
adapter.fetch_quotes(["000001"])
  ├─→ RawRecord     # adapter 原始返回（JSON/WS frame），含原始 timestamp
  ├─→ Normalized    # Quote/Kline 对象（v1 行为，向后兼容）
  └─→ Provenance    # ProvenanceEntry[]：处理流水线标记链
```

返回 `FetchResult` 复合对象，`.normalized` 属性与 v1 完全兼容。

### Decision 2: Provenance 嵌入 Normalized 模型

`Quote._provenance` / `Kline._provenance` 字段（`frozenset[ProvenanceEntry]`），随数据一起传输。

### Decision 3: ConsumptionIntent 通道路由矩阵

| Intent | 返回数据 | 缓存策略 |
|--------|---------|---------|
| `REALTIME_DECISION` | Normalized + Provenance | 不走缓存 |
| `BACKTEST` | Normalized | 允许缓存 |
| `AUDIT` | Raw + Provenance | 不走缓存 |
| `FULL_TRACE` | Raw + Provenance + Normalized | 不走缓存 |

### Decision 4: 锚点日历 — 配置化而非硬编码

```yaml
anchors:
  trading_session:
    - { label: "T+0",    time: "09:15", tz: "Asia/Shanghai" }
    - { label: "T+5min", time: "09:20", tz: "Asia/Shanghai" }
```

datakit 不知道这些 label 的业务含义，只提供 `next_anchor()` / `validate_temporal()` / `current_window()` 查询。

### Decision 5: 向后兼容 — v1 API 零变更

```python
# v1（继续工作）
result = dk.quote("000001")
print(result.normalized["000001"].last_price)

# v2（可选）
result = dk.quote("000001", intent=ConsumptionIntent.AUDIT)
print(result.raw["000001"].payload)
print(result.provenance["000001"])
```

## Risks

| 风险 | 缓解 |
|------|------|
| RawRecord 体积大 | 仅按需传输（`FULL_TRACE` intent），默认不输出 |
| Provenance 改变 frozen dataclass hash | 使用 `frozenset[ProvenanceEntry]` 保持 hash 语义 |
| 新 intent 不够细粒度 | 枚举可扩展，新增不影响现有 intent |
| 锚点日历依赖系统时钟 | 使用 `datetime.now(tz)`，支持时区参数覆盖 |

## 实施计划

34 tasks in 9 phases:
1. Data Model Extension (types.py)
2. Core Modules (channel, provenance, calendar, router)
3. Adapter Updates (tickflow, eastmoney, iwencai)
4. Cache Extension (raw storage, provenance round-trip)
5. CLI Extension (--intent, --show-raw, --show-provenance, anchors commands)
6. Ops Extension (provenance verify, raw-records stats)
7. Config Extension (anchors + channel sections)
8. Public API (__init__.py)
9. Verify (regression + smoke tests)

完整 task list: `openspec/changes/datakit-three-channel-protocol/tasks.md`（位于 runtime 工作区）
