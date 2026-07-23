# 🔗 依赖清单 · Runtime 递归依赖完整追溯

> **仓库**: `20260618-morning-auction`（独立 runtime 仓库）  
> **生成日期**: 2026-07-07  
> **方法**: 全量 AST 解析 import → 文本正则提取文件引用/环境变量/URL → 交叉验证  
> **证据**: `requirements.txt`、`.env`/`.env.example`、全量 `.py` 源码、`runtime_trigger/gates.yaml`、`runtime_trigger/nodes.yaml`、`DIAGNOSIS_20260706.md`

---

## 一、文件清单（核心代码层）

```
仓库根 = /Users/fiona/.openclaw/workspace/runtime/20260618-morning-auction

【引擎层 — 31 个 .py】
auction_monitor.py          # D1 竞价采集 (TickFlow WS + REST fallback)
d2_engine.py                # D2 二次决策 (WS 订阅 → 嵌入预报)
d2_1mk_replay.py            # D2 历史回放
d2_rest_fallback.py         # D2 REST 降级通路
d2_rest_fallback_curl.py    # D2 curl 原生降级
data_preloader.py           # 数据预加载 (全量股票 + 盘口快照)
decision_engine.py          # 决策引擎 (三闸过滤 → generate)
data_source_governance.py   # 数据源治理 (碰撞检测 + 采购决策)
daily_topology_builder.py   # 每日拓扑构建 (YAML → 运行时 DAG)
loop_governance.py          # 循环治理 (门控 + 数据契约)
runtime_loop.py             # 主运行循环
runtime_guard.py            # 运行时守卫 (schema 校验)
runtime_reconciler.py       # 运行时对账 (artifact 一致性)
runtime_trigger_compiler.py # 触发器编译 (gates+nodes → prompt 包)
runtime_trigger_renderer.py # 触发器渲染 (YAML → 结构化 JSON)
master_launcher.py          # 主启动器 (编排 5 节点)
node_state_ledger.py        # 节点状态账本
node_validators.py          # 节点校验器
trigger_runtime_ledger.py   # 触发器运行时账本
harness.py                  # 执行骨架 (fixture 模式)
render.py                   # 终报渲染
rest_recovery.py            # REST 恢复探针
run_status.py               # 运行状态聚合
status_pusher.py            # 状态推送 (macOS 通知)
legacy_handoff_adapter.py   # 旧版 handoff 适配
paths.py                    # 共享路径解析 (+ API Key 加载)
agent_harness_acceptance.py # Agent harness 验收
main_algorithm_execution_graph.py # 主算法执行图
dry_run_validate.py         # 干运行校验
review_validate.py          # 评审校验
iwencai_live_probe.py       # i问财 实时探测

【合约层 — 6 个 .yaml】
trigger_dictionary.yaml         # 触发器字典
node_contracts.yaml             # 节点合约
full_stack.yaml                 # 全栈配置
goal.yaml                       # 目标定义
ignition_prompt.yaml            # 点火提示词
algorithm_data_type_mapping.yaml # 算法↔数据类型映射
run_topology.schema.yaml        # 运行拓扑 schema
llm_io_contracts.yaml           # LLM IO 合约

【工具脚本层 — 7 个 .py/.sh】
scripts/hermes_launcher.py      # Hermes 启动器
scripts/generate_decision_1.py  # D1 决策生成
scripts/dispatch_review.py      # 评审分发
scripts/preflight_check.py      # 起飞前检查
scripts/iwencai_gate_check.py   # i问财 门控检查
scripts/trading_day_check.py    # 交易日检查
scripts/daily_runner.sh         # 每日运行脚本

【测试层 — 22 个 test_*.py】
tests/                          # 22 个测试文件覆盖所有引擎模块

【运行时配置 — runtime_trigger/】
runtime_trigger/gates.yaml      # 三闸门控策略 (D1/D2/Terminal)
runtime_trigger/nodes.yaml      # 三节点拓扑定义

【数据文件】
data/static/all_stocks_20260306.csv  # A股全量股票码表
API_KEY_数据接口.txt                  # API 密钥说明
.env / .env.example                  # 环境变量
```

---

## 二、Python 第三方依赖（requirements.txt）

| 包名 | 版本约束 | 使用文件 | 用途 |
|------|---------|---------|------|
| `websockets` | ≥12.0 | `auction_monitor.py`, `d2_engine.py` | TickFlow WebSocket 实时数据流 |
| `PyYAML` | ≥6.0 | 7 个核心文件 | 所有 YAML 合约解析 |
| `cn-stock-holidays` | — (scripts 中使用) | `preflight_check.py`, `trading_day_check.py` | A 股交易日历 |
| `python-socketio` | — (scripts 中使用) | `hermes_launcher.py` | Hermes Socket.io 通信 |

**Python 标准库依赖**: `asyncio`, `json`, `datetime`, `pathlib`, `subprocess`, `sys`, `os`, `re`, `time`, `logging`, `textwrap`, `argparse`, `typing`, `uuid`, `hashlib`, `itertools`, `functools`, `dataclasses`, `collections`, `contextlib`, `copy`, `enum`, `io`, `math`, `shutil`, `tempfile`, `threading`, `traceback`, `urllib`

---

## 三、内部模块依赖图（核心 DAG）

```
                        ┌──────────────────┐
                        │  master_launcher  │  ← 人类入口 / cron 触发
                        └────────┬─────────┘
                                 │ subprocess 调用
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
  │data_preloader│    │ auction_monitor  │    │  decision_engine  │
  │              │    │ (TickFlow WS)    │    │  (三闸过滤→产出)   │
  └──────┬───────┘    └────────┬─────────┘    └────────┬─────────┘
         │                     │                       │
         │     ┌───────────────┴───────┐               │
         │     ▼                       ▼               │
         │  ┌──────────┐    ┌──────────────────┐       │
         │  │  d2_engine│    │d2_rest_fallback  │       │
         │  │ (WS 主路) │    │(REST 降级)       │       │
         │  └────┬─────┘    └────────┬─────────┘       │
         │       │                   │                  │
         │       └────────┬──────────┘                  │
         │                ▼                             │
         │     ┌─────────────────────────┐              │
         │     │ data_source_governance  │◄─────────────┘
         │     │ (碰撞检测+采购决策)      │
         │     └────────────┬────────────┘
         │                  │
         ▼                  ▼
  ┌────────────────────────────────────────┐
  │             runtime_loop               │  ← 总调度器
  │  (daily_topology_builder → 调度)        │
  │  (loop_governance → 门控)              │
  │  (legacy_handoff_adapter → 产物适配)    │
  │  (run_status → 状态聚合)               │
  │  (runtime_reconciler → 对账)           │
  └──────────────────┬─────────────────────┘
                     │
                     ▼
  ┌───────────────────────────────────────────┐
  │        runtime_trigger_compiler            │  ← 编译输出层
  │  Gate YAML + Node YAML → trigger_packet   │
  │       → hermes_launcher → Hermes          │
  └───────────────────────────────────────────┘



共享底层模块（被多模块引用）：
  paths.py           ← auction_monitor, d2_engine, d2_rest_fallback, data_preloader,
                       decision_engine, harness, render, rest_recovery
  node_state_ledger  ← run_status, trigger_runtime_ledger
  runtime_guard      ← render, review_validate
  node_validators    ← agent_harness_acceptance
```

---

## 四、配置/合约文件依赖图

```
合约文件（静态，仓库内）                    运行时产物（动态，handoff/）
─────────────────────────                ──────────────────────────
full_stack.yaml                          data_preload.json         ← 数据预加载产物
goal.yaml                                auction_snapshot.json     ← D1 竞价快照
ignition_prompt.yaml                     filtered_pool.json        ← 三闸过滤后股票池
trigger_dictionary.yaml                  decision_1.json           ← D1 决策
node_contracts.yaml                      d2_decision.json          ← D2 输入
algorithm_data_type_mapping.yaml         decision_2.json           ← D2 终报
llm_io_contracts.yaml                    terminal_packet.json      ← 终报包
run_topology.schema.yaml                 terminal_review.json      ← 终报评审
                                         data_source_acceptance.json ← 数据源验收
runtime_trigger/gates.yaml               data_source_collision.json  ← 数据源碰撞
runtime_trigger/nodes.yaml               data_source_preflight.json  ← 起飞前校验
                                         iwencai_live_trial_gate.json ← i问财门控
                                         llm_io_quality_gate.json     ← LLM IO 质量门
                                         node_state_ledger.json       ← 节点状态账本
                                         run_status.json              ← 运行状态
                                         desync_state.json            ← 前后端同步状态
                                         reconciler_state.json        ← 对账状态
                                         artifact_provenance.json     ← 产物溯源
                                         trigger_dictionary.yaml      ← (既是合约也是产物)
```

---

## 五、外部服务/API 依赖

| # | 服务 | 端点 | 协议 | 认证 | 使用位置 | 依赖级别 |
|---|------|------|------|------|---------|---------|
| 1 | **TickFlow** | `api.tickflow.org/v1/quote` | WebSocket + REST | `TICKFLOW_API_KEY` | `auction_monitor.py`, `d2_engine.py`, `rest_recovery.py`, `data_preloader.py`, `decision_engine.py` | 🔴 P0 主数据源 |
| 2 | **TickFlow** | `api.tickflow.org/v1/kline` | REST | 同上 | `d2_rest_fallback.py` | 🟡 P1 K线补充 |
| 3 | **东方财富** | `data.eastmoney.com` (push.xxx) | HTTP | 无/公开 | `auction_monitor.py`, `data_preloader.py` | 🟡 P2 降级/校验源 |
| 4 | **i问财 (THS)** | `openapi.iwencai.com` | REST | `IWENCAI_API_KEY` | `iwencai_live_probe.py`, `iwencai_gate_check.py`, `loop_governance.py` | 🟡 P1 解释层 |
| 5 | **Hermes Studio** | `127.0.0.1:8647` | HTTP + Socket.io | JWT (HS256) | `hermes_launcher.py`, `dispatch_review.py` | 🔴 P0 Agent 执行平台 |
| 6 | **GPT-5.5 (xixu)** | `api.xi-xu.me/v1` | HTTP (OpenAI compat) | (Hermes 代理) | 由 Hermes agent 调用，非仓库直接依赖 | 🟡 LLM 推理 |

---

## 六、环境变量目录

| 变量名 | 来源文件 | 用途 | 已配置？ |
|--------|---------|------|---------|
| `TICKFLOW_API_KEY` | `paths.py`, `rest_recovery.py` | TickFlow 主 API Key | ✅ `.env` |
| `TICKFLOW_API_KEY_FILE` | `paths.py`, `rest_recovery.py` | API Key 文件路径 | 备选 |
| `IWENCAI_API_KEY` | `iwencai_gate_check.py`, `preflight_check.py` | i问财 API Key | ✅ `.env` |
| `IWENCAI_BASE_URL` | `iwencai_gate_check.py` | i问财 端点 | ✅ `.env` (`openapi.iwencai.com`) |
| `HERMES_API_URL` | `hermes_launcher.py`, `dispatch_review.py` | Hermes 地址 | ✅ `.env` (`127.0.0.1:8647`) |
| `HERMES_API_TOKEN` | `hermes_launcher.py`, `dispatch_review.py` | Hermes 认证 Token | JWT 自动签发 |
| `HERMES_PROFILE` | `hermes_launcher.py` | Hermes 运行 profile | 可选 |
| `AUTH_JWT_SECRET` | `hermes_launcher.py`, `dispatch_review.py` | JWT 签名密钥 | 运行时注入 |
| `OPENCLAW_STOCK_CSV` | `data_preloader.py`, `preflight_check.py` | 股票码表 CSV 路径 | 默认 `data/static/all_stocks_20260306.csv` |
| `OPENCLAW_RUNTIME_MODE` | `.env.example` | 运行模式 (`dry_run`/`live`) | `dry_run` |
| `OPENCLAW_NODE_HANDOFF_DIR` | `paths.py` | 节点产物输出目录 | 由 `master_launcher` 注入 |
| `OPENCLAW_RUN_HANDOFF_DIR` | `paths.py` | Run 级产物输出目录 | 由 `master_launcher` 注入 |
| `OPENCLAW_HISTORY_HANDOFF_ROOT` | `d2_engine.py`, `d2_rest_fallback.py` | 历史 handoff 根 | 运行时注入 |
| `OPENCLAW_CURRENT_TIME` | `master_launcher.py` | 当前模拟时间 | 运行时注入 |
| `OPENCLAW_IS_TRADING_DAY` | `master_launcher.py` | 是否交易日 | 运行时注入 |
| `OPENCLAW_TRADE_DATE` | `master_launcher.py` | 交易日期 | 运行时注入 |
| `OPENCLAW_RUN_ID` | `master_launcher.py` | 运行 ID | 运行时注入 |

---

## 七、关键依赖链（P0 断路 = 系统不可用）

```
TICKFLOW_API_KEY (.env)
    → paths.load_api_key()
        → auction_monitor.py  (WS 实时报价)
            → filtered_pool.json
                → decision_engine.py  (三闸过滤)
                    → decision_1.json
                        → d2_engine.py + d2_rest_fallback.py
                            → decision_2.json
                                → render.py → terminal_packet.json
                                    → runtime_trigger_compiler.py
                                        → hermes_launcher.py
                                            → Hermes (:8647) → LLM 终报


旁路依赖（降级路径）：
  TickFlow WS 断开 → rest_recovery.py → api.tickflow.org/v1/quote (REST)
  TickFlow 全断 → data.eastmoney.com (东方财富公开接口)
  i问财不可用 → 降级标记 degraded_continue → gate 允许降级通过
  Hermes 不可用 → hermes_launcher 报错 → 人类手动注入 prompt
```

---

## 八、Hermes Studio 接线状态（前次调查摘要）

| 维度 | 状态 |
|------|------|
| Hermes 服务 (`:8647`) | 🟢 运行中 |
| Agent 模型 | gpt-5.5 (custom/api.xi-xu.me) |
| 物理拓扑 | 仓库 ↔ Hermes 物理分离，Agent cwd = `hermes-studio/` |
| JWT 认证链路 | 🟢 自动签发 |
| 治理层集成 | 🔴 断路 — governance YAML 未注入 Hermes 运行层 |
| Agent 写回 | 极少 (31 次 write_file / 11 天) |
| 最后活跃 | 2026-07-07 03:30 (测试对话) |
| 插件桥接 | `migrate-hermes` disabled, IPC bridge 在跑 |

---

## 九、CodeGraph 索引状态

```
.codegraph/codegraph.db  — 5.5 MB，最后更新 2026-07-06 20:22
.codegraph/daemon.log    — 20 KB
索引覆盖: 仓库内全部 Python 文件
可用于: codegraph_explore 符号级依赖追踪
```
