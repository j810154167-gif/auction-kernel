## Scope Boundary

This design belongs to the **datakit adjacent data capability layer**. It is intentionally not a LingGuanOS workflow-kernel redesign.

LingGuanOS may later consume the resulting RawRecord / Normalized / Provenance views as upstream data products, but this change must not alter LingGuanOS daily startup governance, node consensus cards, modular map contracts, AgentPacket/HumanCard contracts, or human-final-judgment boundaries.

## Context

datakit v1 将所有数据源输出强制归一化为标准化 `Quote`/`Kline`/`BlockInfo` 模型。这带来了统一接口的便利，但也造成了一个结构性损失：原始时间戳精度、adapter 特有的元数据（如 TickFlow 的 push 延迟、东财的更新间隔）、以及异常信号（WS 断线前最后一条记录、超时后降级返回的近似值）在 `normalize()` 转换过程中被丢弃。

这个损失的后果不是功能性的（v1 API 正常工作），而是**结构性的**：

```
datakit v1 输出:  [Normalized Quote]  ← 只有一种视图
                    ↓
需要原始数据:       无 Raw 通道 → 无法获取
需要溯源:           无 Provenance 通道 → 无法追踪
按意图路由:         不存在（所有数据看起来一样）→ 无视图区分
```

三通道升级解决的是这一结构断层：
- **RawRecord** 保留 normalize 之前的原始信号 → 所有需要原始数据的场景直接可用
- **Provenance** 标记每条数据的完整处理流水线 → 审计回放可追溯，数据质量可归因
- **Consumption Router** 按意图路由到正确通道 → 调用方无需手工拼接数据视图
- **Forward Anchor Calendar** 调用方自定义时间锚点 → 时序校验不再依赖数据自带时间戳

## Goals / Non-Goals

**Goals:**
- datakit 输出从单通道升级为三通道（Raw → Normalized → Provenance），Normalized 通道保持向后兼容
- 每个 adapter 的 `fetch_*()` 返回 `(Normalized, RawRecord)` 元组，调用方按需选择
- 引入 `ConsumptionIntent` 枚举（realtime-decision / backtest / audit / full-trace），Router 按意图路由到正确通道
- 引入 `ForwardAnchorCalendar`：调用方在 config 中自定义时间锚点组，datakit 提供锚点查询、时序校验和窗口判断——不预设任何业务锚点
- 调用方可通过 `intent=FULL_TRACE` 获取 Raw + Provenance + Normalized 全部三个数据通道
- `data-cache` 扩展支持 RawRecord 存储，`ops-workflows` 新增 provenance 验证命令

**Non-Goals:**
- 不修改 datakit 现有调用方的代码（Normalized 通道保持向后兼容，调用方可选择是否使用新通道）
- 不在本次 change 中实现调用方侧的通道集成（那是调用方自身的责任）
- 不实现 Raw 数据的实时告警或异常检测（仅存储和透传）
- 不在 datakit config 中预设任何业务锚点（锚点内容完全由调用方定义）

## Decisions

### Decision 1: 三通道模型（Raw ↔ Normalized ↔ Provenance）

每个 adapter 调用返回三层数据，consumer 按需选择：

```
adapter.fetch_quotes(["000001"])
  │
  ├─→ RawRecord     # dict: adapter 原始返回（JSON/WS frame），含原始 timestamp
  ├─→ Normalized    # Quote/Kline 对象（v1 行为，向后兼容）
  └─→ Provenance    # ProvenanceEntry[]：处理流水线标记链
```

**理由**：三层不是三个独立调用，而是一次调用的三个视图。这避免了额外 API 调用的延迟开销（Raw 和 Provenance 在 normalize 过程中可以同步收集）。

**替代方案**：
- 方案 A（分离式 API：`fetch_raw()` + `fetch_normalized()`）：两次调用，延迟翻倍，竞价时段不可接受
- 方案 B（Raw 嵌入 Normalized 的 `_raw` 字段）：污染 Normalized 模型，所有消费者都付出内存代价
- 方案 C（只加 Provenance，不加 Raw）：治理层仍然没有门控素材，核心矛盾未解决

**选择方案：返回 `FetchResult` 复合对象**：
```python
@dataclass
class FetchResult:
    normalized: dict[str, Quote | Kline]         # v1 兼容
    raw: dict[str, RawRecord]                     # adapter 原始返回
    provenance: dict[str, list[ProvenanceEntry]]   # 逐 symbol 溯源链
```

`Datakit().quote("000001")` 返回 `FetchResult`，属性访问 `.normalized` 获得与 v1 完全相同的数据。现有引擎节点无需任何代码变更。

### Decision 2: Provenance 作为 Normalized 模型的嵌入字段（非独立存储）

Provenance 链嵌入 `Quote._provenance` / `Kline._provenance` 字段（`frozenset[ProvenanceEntry]`），而非存入独立数据库。

**理由**：
1. 每条数据的溯源链随数据一起传输——consumer 不需要查另一个表
2. `_provenance` 以 `_` 前缀标记为元数据字段，引擎节点可忽略
3. `frozenset` 不可变，保持 `Quote`/`Kline` 的 `frozen=True` 语义

**ProvenanceEntry 结构**：
```python
@dataclass(frozen=True)
class ProvenanceEntry:
    step: str          # "source_fetch" | "normalize" | "cache_hit" | "router_select"
    actor: str         # "tickflow" | "eastmoney" | "datakit.normalizer"
    timestamp: float   # time.time() when this step occurred
    detail: str        # 人类可读描述，如 "WS frame #42, latency=142ms"
```

### Decision 3: ConsumptionIntent 枚举 + 通道路由矩阵

```python
class ConsumptionIntent(Enum):
    REALTIME_DECISION = "realtime-decision"   # → Normalized + Provenance
    BACKTEST = "backtest"                     # → Normalized only (fast path)
    AUDIT = "audit"                           # → Raw + Provenance
    FULL_TRACE = "full-trace"       # → Raw + Provenance + health metadata
```

路由矩阵（在 `core/router.py` 中实现）：

| Intent | 返回数据 | 缓存策略 |
|--------|---------|---------|
| `REALTIME_DECISION` | Normalized + Provenance | 不走缓存 |
| `BACKTEST` | Normalized | 允许缓存 |
| `AUDIT` | Raw + Provenance | 不走缓存（必须溯源） |
| `FULL_TRACE` | Raw + Provenance + HealthStatus | 不走缓存 |

**理由**：Router 不需要"猜"调用方的意图——调用方显式声明。Agent 在启动时通过 CLI 声明 intent：

```bash
python -m datakit quote --symbols 000001 --intent full-trace --json
```

引擎节点通过 Python API：
```python
dk = Datakit()
result = dk.quote("000001", intent=ConsumptionIntent.REALTIME_DECISION)
print(result.normalized)  # 向后兼容
print(result.provenance)  # 可选读取
```

### Decision 4: 前向锚点日历作为 config.yaml 扩展

不内置时间概念的原则不变。但在 `config.yaml` 中新增 `anchors` 配置段，由调用方决定是否使用：

```yaml
anchors:
  trading_session:
    - { label: "T+0",   time: "09:15", tz: "Asia/Shanghai" }
    - { label: "T+5min", time: "09:20", tz: "Asia/Shanghai" }
    - { label: "T+10min", time: "09:25", tz: "Asia/Shanghai" }
    - { label: "T+15min", time: "09:30", tz: "Asia/Shanghai" }
```

`core/calendar.py` 提供 `AnchorCalendar` 类：
- `calendar.next_anchor()` → 返回下一个未到达的锚点
- `calendar.validate_temporal(data_timestamp, anchor_label)` → 校验数据时间是否在锚点之前
- `calendar.current_window()` → 返回当前所在的时间窗口位置（`before_first` / `between` / `after_last`）及前后锚点引用

**理由**：配置化而非硬编码——datakit 不知道"早盘竞价"是什么，只知道有一组时间锚点可以用来校验数据时序。

### Decision 5: 向后兼容——v1 API 零变更

现有引擎节点和 Agent 脚本不需要任何修改：

```python
# v1 调用（继续工作）
dk = Datakit()
quotes = dk.quote("000001")                      # → FetchResult
for symbol, q in quotes.normalized.items():       # 与 v1 完全相同的 Quote 对象
    print(q.last_price)

# v2 新能力（可选使用）
result = dk.quote("000001", intent=ConsumptionIntent.AUDIT)
print(result.raw["000001"].payload)               # 原始 JSON
print(result.provenance["000001"])                # 溯源链
```

CLI 同样保持向后兼容：
```bash
python -m datakit quote --symbols 000001 --json     # v1 输出：只显示 Normalized
python -m datakit quote --symbols 000001 --json --show-raw  # v2：追加 raw 字段
```

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| RawRecord 体积大（原封 adapter 返回），高并发实时数据流可能累积数十 MB | Raw 数据仅按需传输（`intent=AUDIT` / `FULL_TRACE`），不作默认输出。缓存层 TTL 设为 1 天滚动淘汰 |
| Provenance 嵌入 `frozen Quote` 会改变 `__hash__` 行为 | `ProvenanceEntry` 使用 `frozenset[ProvenanceEntry]` 保持 frozen dataclass 的 hash 语义。如需要不含 provenance 的 hash，提供 `.hash_no_provenance()` 方法 |
| ConsumptionIntent 可能不够细粒度，未来出现新意图 | 枚举值可扩展。新增 intent 只需加枚举值 + 路由矩阵条目，不影响现有 intent |
| 前向锚点日历依赖系统时钟准确 | `AnchorCalendar` 使用 `datetime.now(tz)` 而非 `time.time()`，支持时区。提供 `--tz` 参数覆盖 |
| adapter 修改工作量（3 个 adapter × 改 fetch_* 签名） | 每个 adapter ~30 行改动（构造 RawRecord + ProvenanceEntry），非侵入式 |

## Open Questions

- 调用方首次获得完整数据通道（Raw + Provenance + Normalized）后，如何集成到现有工作流中？→ 不在本 change 范围内，由调用方自行决定
- a-stock-data（mootdx）adapter 是否随此 change 加入？mootdx 的二进制协议天然携带丰富的原始元数据，三通道对其价值远大于 HTTP adapter。→ 建议作为并行 change
