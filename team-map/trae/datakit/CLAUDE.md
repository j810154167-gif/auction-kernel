# CLAUDE.md — datakit 统一数据流工具包

## 项目身份

你是 **datakit**——一个独立、模块化、即插即用的多源金融数据统一访问工具包。你提供 CLI + Python API 双模接口，自动降级路由，结构化日志和配额追踪。

**你不是业务系统。** 你不知道"早盘竞价"、"治理层"、"引擎节点"。你只提供数据管道原语。

## 核心设计原则

1. **零业务耦合** — 不预设任何业务场景、时间窗口、策略偏好
2. **适配器插件化** — 新增数据源只需新增一个 adapter 文件，registry 自动发现
3. **降级链由 config 定义** — Router 不知道"为什么"切换，只按 YAML 配置执行
4. **调用方决定缓存策略** — `--mode realtime|cache-ok|auto` 由调用方声明
5. **运维原语无调度** — 提供 `ops check` / `ops report`，何时调用由外部决定
6. **三通道数据视图** — RawRecord（原始）/ Normalized（标准）/ Provenance（溯源）三个通道，调用方按需选择

## 工作区结构

```
datakit/                         独立 git 仓库
├── README.md                    ← 快速开始
├── CLAUDE.md                    ← 本文件
├── .gitignore
├── .codegraph/
├── datakit/
│   ├── __init__.py              ← Datakit 公开 API
│   ├── __main__.py              ← python -m datakit 入口
│   ├── config.yaml              ← 降级链/TTL/端点（进 git）
│   ├── guard.py                 ← 未来函数风险门控
│   ├── inject.py                ← API Key 注入器
│   ├── crontab.example          ← 参考 cron（不嵌入逻辑）
│   ├── core/
│   │   ├── engine.py            ← Router（降级链路由）
│   │   ├── registry.py          ← 适配器自动发现
│   │   ├── types.py             ← Quote/Kline/BlockInfo/HealthStatus
│   │   └── db.py                ← SQLite 自迁移
│   ├── adapters/
│   │   ├── base.py              ← BaseAdapter ABC
│   │   ├── tickflow.py          ← REST + WebSocket
│   │   ├── eastmoney.py         ← HTTP 免费源
│   │   └── iwencai.py           ← 离线优先 + 门控探活
│   ├── services/
│   │   ├── health.py            ← HealthChecker
│   │   ├── cache.py             ← Parquet 缓存
│   │   └── ledger.py            ← 配额账本
│   ├── ops/
│   │   ├── logger.py            ← JSONL 结构化日志
│   │   └── cron.py              ← 运维原语
│   └── cli/
│       ├── __main__.py
│       └── commands.py          ← 命令树
├── docs/                        ← 调查报告 + 设计文档
│   ├── design/                  ← 架构设计文档
│   └── *.md                     ← 数据源选型/调查
└── cache/                       ← 运行时 Parquet 缓存 (.gitignore)
```

## 适配器发现机制

所有 adapter 通过 `adapters/` 目录下的 `ADAPTER` 模块级变量自动注册。新增数据源只需：

1. 在 `adapters/` 下创建新文件
2. 实现 `BaseAdapter` 接口
3. 导出 `ADAPTER = YourAdapter()` 实例
4. `registry.discover()` 自动发现

## API Key 注入

- 每个 adapter 独立读取各自 key（环境变量或 `_FILE` 路径）
- `python -m datakit inject status` → Agent 可检查哪些 key 已配
- `python -m datakit inject guide` → 人类可读注入指引
- Key 值始终遮蔽（`tk_b35f2...`），不裸输出
- datakit 不写 `.env` 文件，只读 `os.environ`

## 未来函数风险门控

`guard.py` 在首次 CLI 调用时检查 `~/.datakit_consensus`：
- 不存在 → 打印四项高危风险警告 → exit 77 → Agent 必须暂停请求人类共识
- 存在 → 零开销，完全不感知

四项风险：
1. 信息时间 ≠ 信号时间 ≠ 决策时间
2. T 日 partial bar 禁止消费
3. 回放数据静默混入
4. 数据静默运行

## 向后兼容承诺

- v1 API（`Datakit().quote()` / `.klines()` / `.blocks()`）永不破坏
- 新功能通过可选参数激活（`intent=` / `--show-raw`）
- Normalized 通道始终可用
- 调用方可以永远不升级到三通道用法

## 开发纪律

| 场景 | 你必须做什么 |
|------|------------|
| 新增 adapter | 实现 `BaseAdapter` 全部抽象方法 + 导出 `ADAPTER` |
| 修改数据模型 | 更新 `core/types.py` + 所有 adapter + `core/engine.py` Router |
| 新增 CLI 命令 | 在 `cli/commands.py` 添加 handler + `cli/__main__.py` 注册 |
| 修改 config.yaml | 同时更新 `crontab.example` 中的示例 |
| 每次变更后 | `codegraph build` 重建索引 |
