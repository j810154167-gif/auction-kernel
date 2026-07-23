"""datakit 未来函数风险门控。

在首次调用时向 LLM/Agent 呈现四项高危风险，
要求 Agent 暂停并向人类用户请求数据使用共识。
共识建立后（~/.datakit_consensus 文件存在），不再警告。
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

CONSENSUS_FILE = Path.home() / ".datakit_consensus"

RISK_BANNER = """
╔══════════════════════════════════════════════════════╗
║  🔴  DATAKIT 未来函数 — 四项数据时间高危风险          ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  1. 信息时间 ≠ 信号时间 ≠ 决策时间                     ║
║     数据到达顺序一旦紊乱，决策引擎即被污染。            ║
║     datakit 的 Quote/Kline 均带 _ingest_ts 字段，     ║
║     可审计不可盲信。                                   ║
║                                                      ║
║  2. T 日 partial bar 污染                             ║
║     K 线未收市前含盘中临时数据，                       ║
║     消费 partial bar 做决策 = 未来函数。               ║
║     调用方必须检查 Kline.date 字段，                   ║
║     拒绝当日未收盘数据。                               ║
║                                                      ║
║  3. 回放数据静默混入                                   ║
║     replay / backtest 模式的数据无显式标记，           ║
║     混入生产决策链后无法追溯。                         ║
║     datakit 不自动区分实时/回放 —                      ║
║     调用方必须自行标记数据来源。                       ║
║                                                      ║
║  4. 数据静默运行的危害                                  ║
║     Agent 在数据源不完整 / 降级 / 过期时               ║
║     继续产出决策，比不决策更危险。                      ║
║     每次摄入后检查 source 和 _ingest_ts，              ║
║     异常即阻断，不要静默降级。                          ║
║                                                      ║
╠══════════════════════════════════════════════════════╣
║  共识文件: ~/.datakit_consensus                       ║
║  建立方式: touch ~/.datakit_consensus                 ║
╚══════════════════════════════════════════════════════╝
"""

AGENT_INSTRUCTIONS = """
📋 Agent / LLM 操作指引（看到此提示后必须执行）:
   1. 暂停当前所有数据操作
   2. 向人类用户呈现上述四项风险
   3. 与人类用户就以下问题达成共识:
      a. 数据时间窗口硬约束 (info_time < signal_time < decision_time)
      b. 降级策略 (哪个源挂掉后走哪个，是否允许跨源降级)
      c. 回放数据隔离 (replay 专用输出路径，禁止写入生产路径)
      d. 数据静默运行的上报机制 (异常时阻断 vs 降级 vs 告警)
   4. 共识达成后执行: touch ~/.datakit_consensus
"""


def check_consensus() -> bool:
    """检查共识文件是否存在。"""
    return CONSENSUS_FILE.exists()


def _write_consensus_file():
    """创建共识文件，记录确认时间戳。"""
    CONSENSUS_FILE.write_text(
        f"# datakit data usage consensus established\n"
        f"# timestamp: {datetime.now(timezone.utc).isoformat()}\n"
        f"# This file suppresses future-function risk warnings.\n"
        f"# Delete it to re-enable warnings (e.g. when changing data sources).\n"
    )


def print_warning(file=None):
    """打印四项风险警告 banner + Agent 操作指引。"""
    out = file or sys.stderr
    print(RISK_BANNER, file=out)
    print(AGENT_INSTRUCTIONS, file=out)


def require_consensus():
    """CLI 入口门控: 无共识 → 打印警告并退出 77。

    退出码 77 是 BSD EX_NOPERM 的语义化复用，
    表示 "操作被阻塞：需人类确认后才能继续"。
    """
    if not check_consensus():
        print_warning()
        sys.exit(77)
