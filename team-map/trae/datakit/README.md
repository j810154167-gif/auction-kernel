# datakit — 统一数据流工具包

多源金融数据统一访问层，CLI + Python API 双模，自动降级路由，即插即用。

## 快速开始

```bash
pip install pyarrow aiohttp

# 检查 API Key 配置状态
python -m datakit inject status

# 查看 Key 注入指引
python -m datakit inject guide

# 设置 Key（推荐：外挂 ~/.openclaw/keys.env）
export TICKFLOW_API_KEY=tk_xxx
export IWENCAI_API_KEY=sk-proj-xxx

python -m datakit registry list
python -m datakit ops check
python -m datakit quote --symbols 000001.SZ
```

## 架构

```
datakit/
├── core/          # 路由器、注册表、类型、SQLite
├── adapters/      # TickFlow / 东方财富 / i问财
├── services/      # 健康探活、Parquet 缓存、配额账本
├── ops/           # 运维原语（无调度）
├── cli/           # 命令树
├── guard.py       # 未来函数风险门控
├── inject.py      # API Key 注入器
└── config.yaml    # 降级链、TTL、端点
```

## Python API

```python
from datakit import Datakit
dk = Datakit()
quotes = dk.quote(["000001.SZ", "000002.SZ"])
klines = dk.klines(["000001.SZ"], days=2)
blocks = dk.blocks("concept", mode="realtime")
```

## 数据通道（v1 → v2 路线图）

| 版本 | 通道 | 状态 |
|------|------|------|
| v1 (当前) | Normalized（Quote/Kline/BlockInfo） | ✅ 稳定 |
| v2 (设计中) | + RawRecord（原始数据）+ Provenance（溯源链）+ ConsumptionRouter（意图路由）+ AnchorCalendar（时间锚点） | 📋 [设计文档](docs/design/three-channel-protocol.md) |

v2 向后兼容——现有 `dk.quote()` 调用无需任何修改。新通道通过可选 `intent=` 参数激活。

## 适配器

| Adapter | 数据源 | 协议 | Key |
|---------|--------|------|-----|
| tickflow | TickFlow API | REST + WebSocket | `TICKFLOW_API_KEY` |
| iwencai | i问财 SkillHub | HTTP + 离线缓存 | `IWENCAI_API_KEY` |
| eastmoney | 东方财富 | HTTP | 无（免费） |

## 降级链（config.yaml）

```yaml
fallback:
  quote:  [tickflow, eastmoney]
  kline:  [tickflow, eastmoney]
  block:  [iwencai, eastmoney]
  reason: [iwencai]
```

## 适用场景

- 多源金融数据统一访问
- Agent（Hermes/Claude Code）终端调用
- 多源数据健康监控
- 量化策略数据获取

## 参考文档

| 文档 | 内容 |
|------|------|
| `CLAUDE.md` | datakit Agent 行为规范 |
| `pickup.md` | 会话交接文件 |
| `docs/design/three-channel-protocol.md` | 三通道协议架构设计 |
| `docs/INJECTION_STACK.md` | API Key 注入栈 |
| `docs/DATA_SOURCE_FINAL_SELECTION_V2.md` | 数据源选型最终报告 |
| `docs/NODE_API_FIELD_MATRIX.md` | API 字段矩阵 |
| `docs/DEPENDENCY_MANIFEST.md` | 依赖递归识别 |
