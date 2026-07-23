# 0714 D1 校准

## 运行时 vs 治理会话

D1 输出经历了从 Gate标记 → chg×3评分 → 断崖 → 移除×3×2 → 自然梯度的演化。

### 关键数据修正

- **close_t1 vs prev_close**: 池里 `prev_close` 是 T-2 收盘。`open_chg_pct` 用 `close_t1`(昨收)。水发燃气从 +19.69% → +8.77%。
- **×3×2 移除**: 评分公式从 `chg×3 - max(0,dev-7)×2` 改为 `chg - max(0,dev-7)`，断崖消失，max_gap=11.8。

### D1 输出形态 v20260714

8 列 markdown 表格:
```
| ★ | symbol | name(标签) | price | chg% vs锚 | 得分 | L0 | 风控 |
```

- name: 挂 risk_labels 标签(一字封板/开盘冲/盘中推/尾盘偷袭)
- chg%: vs 昨VWAP
- 得分: chg - max(0,dev-7) + ... (无乘系数)
- L0: 🟢/🟡/🔴 (VWAP生命线三级)
- 风控: 🟢/🔴 (筹码密集区)

### 六模块管线

- sector/multi_day/vwap/anti_hft/orderbook/risk_odds → 仅存 JSON
- 终端输出静默 (contextlib.redirect_stdout)
- 标记不打印到 D1 面板

### 55轮事故

根因: Agent 跳过仿写直接改 D1 输出格式，每轮自认为"优化"，实际在终端 stdout vs markdown 渲染之间反复。解决: 协议写入 SKILL(先仿写→确认→再改)+渲染机制文档化。

### 盘后风控 (risk_scan)

T-1 产出 risk_labels.json + risk_zones.json。T日 D1 读入联动:
- 标签: 一分半内判断昨日涨停结构
- 密区: [VWAP×0.985, VWAP×1.015]，竞 < 下沿 → 🔴

0714 池结果: 一字5/开盘12/尾拉11/盘中推0。D1 面板 8 列全亮。
