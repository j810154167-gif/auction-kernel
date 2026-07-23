## Scope Boundary

This change is an **adjacent datakit capability-layer protocol**, not the LingGuanOS workflow-kernel subject.

It is included in this workspace only as a downgraded, explicitly labeled data-capability change because LingGuanOS may consume datakit outputs later. It must not redefine LingGuanOS project identity, daily governance, node orchestration, AgentPacket/HumanCard contracts, or the archived `workflow-ground-up-refactor` kernel.

## Why

datakit v1 将所有数据源输出强制归一化为标准化 Quote/Kline 模型——原始时间戳、异常信号、数据源特有的结构信息在归一化过程中被丢弃。这导致三个技术问题：(1) 需要消费原始信号做判断的调用方拿不到 Raw 数据；(2) 所有数据看起来一样，无法按意图区分数据视图；(3) 数据的时间顺序校验只能依赖数据自带时间戳，无法利用外部时间锚点做前向校验。三个问题共享同一个根因：单通道输出。升级为 RawRecord + Normalized + Provenance 三通道，三者同时消失。

## What Changes

- **BREAKING**: `unified-data-access` 的输出从单一标准化模型变为三通道（Raw → Normalized → Provenance）。现有 `Datakit().quote()` / `Datakit().kline()` 的 Normalized 通道保持向后兼容；新增 `raw` 和 `provenance` 通道通过可选参数激活
- 新增 `raw-record-channel` capability：每个 adapter 在返回标准化数据的同时，保留一份未经处理的原始记录（含原始 timestamp、source-specific metadata、网络延迟标记）
- 新增 `provenance-chain` capability：每条数据记录附带完整溯源链（source → adapter → normalization_step → cache_hit → consumer），以 `_provenance` 字段嵌入 Normalized 模型
- 新增 `consumption-router` capability：按调用方声明的数据获取意图（realtime-decision / backtest / audit / full-trace）路由到正确的数据通道视图
- 新增 `forward-anchor-calendar` capability：调用方可在 config 中定义任意时间锚点，datakit 提供锚点查询、时序校验和窗口判断——锚点内容完全由调用方定义，datakit 不预设任何业务锚点
- 扩展现有 `data-cache` 和 `ops-workflows`：缓存层支持 RawRecord 存储，运维层增加 provenance verify 命令

## Capabilities

### New Capabilities
- `raw-record-channel`: 原始数据记录通道——在归一化之前保存 adapter 原始返回，保留时间戳精度、source-specific 字段、传输延迟标记和异常信号，供需要原始数据的调用方使用
- `provenance-chain`: 数据溯源链——每条 Normalized 记录内嵌完整处理流水线标记（source → adapter → normalizer → cache → consumer），支持审计回放和数据质量归因
- `consumption-router`: 消费视图路由——按声明意图（realtime-decision / backtest / audit / full-trace）自动选择返回哪些数据通道，调用方无需手工拼接
- `forward-anchor-calendar`: 通用时间锚点工具——调用方在 config 中定义任意 `(label, time, timezone)` 锚点组，datakit 提供 `next_anchor()`、`validate_temporal()`、`current_window()` 查询。锚点内容不由 datakit 预设

### Modified Capabilities
- `unified-data-access`: 输出从单通道 Normalized 模型扩展为三通道——保持 `quote()`/`kline()` 向后兼容，新增 `intent` 参数控制返回视图
- `data-cache`: 缓存层扩展存储 RawRecord（Parquet），原 Normalized 缓存不受影响
- `ops-workflows`: 运维检查新增 `provenance verify` 命令（验证溯源链完整性）和 `raw-records stats` 命令（原始记录统计）

## Impact

- datakit 独立工作区：相邻 `datakit/` 能力层仓库或本工作区中的 `datakit/` 指针（具体版本化边界另行确认）
- 受影响的 adapter：`tickflow.py`、`eastmoney.py`、`iwencai.py`（每个 adapter 的 `fetch_*()` 返回从单一模型变为 `(Normalized, RawRecord)` 元组）
- 新增核心模块：`core/channel.py`（通道管理）、`core/provenance.py`（溯源链）、`core/calendar.py`（锚点日历）
- 扩展 `core/engine.py` Router：新增 `intent` 参数，按意图路由到正确的数据通道组合
- 扩展数据模型：`core/types.py` 新增 `RawRecord`、`ProvenanceEntry`、`ConsumptionIntent`、`AnchorPoint`、`FetchResult`
- 缓存层变更：新增 `cache/raw/` 子目录存储原始记录 Parquet
- 不破坏现有 API：`Datakit().quote("000001")` 返回 `FetchResult`，`.normalized` 属性与 v1 行为完全一致
