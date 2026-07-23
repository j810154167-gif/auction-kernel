# pickup.md — datakit 统一数据流工具包

> 会话关闭时间：2026-07-10
> 读者假设：你一无所知。以下每一条都是为了让你在零上下文下恢复工作。

---

## 一、这是什么

**datakit** 是一个独立、模块化、即插即用的多源金融数据统一访问工具包。它提供 CLI + Python API 双模接口，自动降级路由，结构化日志和配额追踪。

- **独立工作区**：`/Users/fiona/.openclaw/workspace/datakit/`
- **独立 git 仓库**：4 commits
- **CodeGraph 索引**：268 nodes, 562 edges
- **零业务耦合**：不知道"早盘竞价"、"治理层"、"引擎节点"——只提供数据管道原语

## 二、数据源

| Adapter | 类型 | Key | 状态 |
|---------|------|-----|------|
| tickflow | REST + WebSocket | `TICKFLOW_API_KEY` | ✅ |
| eastmoney | HTTP 免费 | 无 | ✅ |
| iwencai | 离线优先 + HTTP 门控 | `IWENCAI_API_KEY` | ⚠️ health 端点不稳定 |

降级链（config.yaml）：quote/kline: tickflow→eastmoney, block: iwencai→eastmoney, reason: iwencai

## 三、当前版本 — v1

```
datakit/
├── core/          # Router, Registry, Types, SQLite
├── adapters/      # tickflow, eastmoney, iwencai
├── services/      # health, cache (Parquet), ledger
├── ops/           # cron (primitives only), logger (JSONL)
├── cli/           # command tree
├── guard.py       # 未来函数风险门控
├── inject.py      # API Key 注入器
└── config.yaml    # 降级链/TTL/端点
```

### CLI 命令树

```bash
python -m datakit ops check --json        # 全源体检
python -m datakit quote --symbols xxx     # 行情 (--mode realtime|cache-ok|auto)
python -m datakit kline --symbols xxx     # K线
python -m datakit block --category xxx    # 板块
python -m datakit registry list           # 适配器目录
python -m datakit inject status           # Key 状态
python -m datakit inject guide            # Key 注入指引
python -m datakit cache status|warm|purge # 缓存管理
python -m datakit ops report              # 日报
python -m datakit ops log --tail 20       # 日志
```

### Python API

```python
from datakit import Datakit
dk = Datakit()
quotes = dk.quote(["000001.SZ"])
klines = dk.klines(["000001.SZ"], days=2)
blocks = dk.blocks("concept", mode="realtime")
```

## 四、下一个 Change — 三通道协议

OpenSpec change `datakit-three-channel-protocol` 已就绪（4/4 artifacts），位于 runtime 工作区的 `openspec/changes/datakit-three-channel-protocol/`。

设计文档同步副本：`docs/design/three-channel-protocol.md`

**升级内容**：
- RawRecord 通道（原始数据保留）
- Provenance 链（完整溯源）
- ConsumptionIntent 路由（按意图返回不同通道组合）
- Forward Anchor Calendar（通用时间锚点工具）

**启动命令**（在 runtime 工作区执行）：
```
/opsx:apply datakit-three-channel-protocol
```

34 tasks in 9 phases，预估 2-3 轮对话。

## 五、关键约束

1. **零业务耦合** — 不预设任何业务场景、时间窗口、策略偏好
2. **向后兼容** — v1 API 永不破坏，新功能通过可选参数激活
3. **适配器插件化** — 新增源只需新增文件 + 实现 BaseAdapter
4. **运维原语无调度** — 所有调度决策由外部 crontab / master_launcher 决定
5. **Key 不进 Git** — `.gitignore` 已排除 `keys.env`、`*_KEY_*.txt`

## 六、共识文件

```bash
~/.datakit_consensus  →  MISSING (需要创建)
```

首次 CLI 调用缺失此文件会 exit 77。Agent 必须暂停请求人类共识。
在新会话开始前：`touch ~/.datakit_consensus`

## 七、会话关闭前检查清单

- [ ] `touch ~/.datakit_consensus`
- [ ] 确认 TickFlow 订阅 Active
- [ ] `cd /Users/fiona/.openclaw/workspace/datakit && codegraph build`
- [x] `CLAUDE.md` — ✅ 已创建
- [x] `docs/design/three-channel-protocol.md` — ✅ 已同步
- [x] `docs/INJECTION_STACK.md` — ✅ 已同步
- [x] `README.md` — ✅ 已更新
