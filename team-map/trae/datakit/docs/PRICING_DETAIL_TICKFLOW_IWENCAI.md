# TickFlow + i问财 SkillHub 定价详情调查报告

> 2026-07-07 | 基于全网 18 轮搜索 + 官网抓取 | 忽略本地已落盘的旧定价信息

---

## 一、执行摘要

| 数据源 | 定价页面 | 公开可查价格 | 结论 |
|--------|----------|-------------|------|
| TickFlow | `/pricing/` JS渲染 | ✅ 4档套餐已获取 | 通过 browser-use 渲染成功，数字确认 |
| i问财 SkillHub OpenAPI | 无公开定价页 | ❌ 完全未公开 | 同花顺B端销售驱动，需人工咨询 |

---

## 二、TickFlow 定价详情

### 2.1 定价来源

通过 browser-use Chrome CDP 成功渲染 tickflow.org/pricing/ 页面并提取 DOM 数据。

### 2.2 套餐对比

| 套餐 | 月付 | 年付（约省17%） | 适用场景 |
|------|------|----------------|---------|
| **Free** | ¥0 | — | A股历史日K，无需注册，无API Key |
| **Starter** | ¥49/月 | ≈¥41/月 | 入门级实时行情，分钟K线 |
| **Pro** 🔥 | ¥99/月 | ≈¥82/月 | 全市场实时行情+WS推送+五档盘口 |
| **Expert** | ¥199/月 | ≈¥165/月 | 最高频控，企业级 |

### 2.3 Free vs 付费 能力差异（从SDK代码和官方文档交叉验证）

| 能力维度 | Free | Starter+ |
|----------|------|----------|
| A股历史日K | ✅ | ✅ |
| A股实时行情 REST | ❌ | ✅ |
| WebSocket 推送 | ❌ | ✅ (Pro+) |
| 分钟K线（1m/5m/15m/30m/60m） | ❌ | ✅ |
| 五档盘口 | ❌ | ✅ (Pro+) |
| 美股/港股/ETF | ❌ | ✅ |
| 批量查询 | ❌ | ✅ |
| 需要注册 | ❌ | ✅ |
| 需要 API Key | ❌ | ✅ |

### 2.4 J先生 当前订阅状态（高危盲区）

⚠️ **J先生 当前使用的是 Expert 版**（Key 前缀 `tk_b35f...10e7`，环境变量 `TICKFLOW_API_KEY`），但：
- **月费 ¥199 是否在正常扣款？** — 未知
- **到期时间？** — 未知
- **是否存在用量配额？** — SDK 代码中未见明确限流参数

> 建议：登录 tickflow.org → 控制台 → 查看 Billing/Subscription 页面确认

### 2.5 信息可信度评估

| 来源 | 类型 | 可信度 |
|------|------|--------|
| browser-use 渲染 tickflow.org/pricing/ | 官方定价页 DOM 数据 | ⭐⭐⭐⭐⭐ |
| Zhihu 作者原文 | 开发者自述（免费/高级两档） | ⭐⭐⭐⭐ |
| GitHub SDK 代码 | `TickFlow.free()` vs `TickFlow(api_key=...)` | ⭐⭐⭐⭐⭐ |
| CSDN 文章 | 第三方评测提到"收费版价格合理" | ⭐⭐⭐ |
| Volcengine 文章 | "基于AKShare开发了TickFlow" | ⭐⭐⭐ |

---

## 三、i问财 SkillHub OpenAPI 定价详情

### 3.1 产品矩阵澄清

i问财有**三个不同产品**，价格体系完全不同：

```
同花顺 i问财 生态
├── i问财 Web (iwencai.com)       → 免费，手动使用，无API
├── 同花顺量化API (quantapi.10jqka.com.cn)  → 有免费额度，有付费版
└── SkillHub OpenAPI (sk-proj-...) → 面向Agent调用，定价未公开 ⚠️
```

J先生 当前使用的是 **SkillHub OpenAPI**（环境变量 `IWENCAI_API_KEY=sk-proj-...`）。

### 3.2 传统量化API 免费额度（参考，非SkillHub）

| 数据类型 | 免费额度/月 |
|----------|-----------|
| 实时行情 | **300万次** |
| 历史行情 | 100万次 |
| 日期序列 | 60万次 |
| 基础数据 | 60万次 |
| 专题报表 | 60万次 |

> 来源：同花顺官方帮助中心 `quantapi.10jqka.com.cn/gwstatic/static/ds_web/quantapi-web/help-center.html`

### 3.3 SkillHub OpenAPI 定价（🔴 完全未公开）

经过 10+ 轮定向搜索，**未找到任何关于 SkillHub OpenAPI (`sk-proj-` 前缀 Key) 的定价信息**：

- 同花顺官网无 SkillHub 定价页
- 无第三方评测文章提到 SkillHub 价格
- 无 CSDN/Zhihu/论坛 讨论 SkillHub 收费
- SkillHub 技能市场本身免费（技能安装和浏览）
- 但 OpenAPI 调用是否计费？调用次数配额？超额是否扣费？——**全部未知**

### 3.4 同花顺整体定价背景（供参考）

| 产品线 | 价格 | 目标用户 |
|--------|------|---------|
| 同花顺 App（C端） | 增值服务订阅制 | 散户 |
| iFinD 终端（B端） | **年费数万~数十万元** | 机构 |
| 量化API 免费版 | ¥0（有限额） | 个人开发者 |
| 量化API 付费版 | "价格较高，非普通个人首选" | 专业开发者 |
| SkillHub OpenAPI | **未公开** | AI Agent 开发者 |

> 来源：知乎专栏《从免费到稳定：A股实时数据源深度对比》2026年；火山引擎开发者文章

### 3.5 雪球社区传闻

> "同花顺以后i问财收费，一年按照200块钱算" — 雪球用户讨论

⚠️ 这是用户猜测，非官方信息，不可作为决策依据。

### 3.6 J先生 当前订阅状态（🔴 高危盲区）

- **SkillHub OpenAPI Key**：`sk-proj-...` 格式
- **已安装6个Skills**：通过 SkillHub CLI 0.0.4 安装
- **月调用次数**：未知
- **是否在免费额度内**：未知
- **超额是否自动扣费**：未知
- **如何查看用量**：未知（无公开控制台入口）

### 3.7 信息可信度评估

| 来源 | 类型 | 可信度 |
|------|------|--------|
| 同花顺官方帮助中心 | 传统量化API免费额度 | ⭐⭐⭐⭐⭐ |
| Zhihu 专栏 2026 | 第三方横向评测 | ⭐⭐⭐⭐ |
| 火山引擎开发者文章 | 行业分析 | ⭐⭐⭐ |
| 雪球用户讨论 | 猜测传闻 | ⭐⭐ |
| SkillHub OpenAPI 定价 | **无任何来源** | 🔴 盲区 |

---

## 四、两源定价透明度对比

| 维度 | TickFlow | i问财 SkillHub |
|------|----------|---------------|
| 定价页面存在 | ✅ `/pricing/` | ❌ 不存在 |
| 价格数字公开 | ✅ (JS渲染，需浏览器) | ❌ |
| 免费版明确 | ✅ Free tier | ❌ (SkillHub 技能安装免费，API调用未知) |
| 套餐分层 | ✅ 4档 | ❌ |
| 价格可见性 | 🟡 需登录后可见 | 🔴 完全不透明 |
| 个人开发者可承受 | ✅ ¥49-199/月 | ❓ 未知 |

---

## 五、行动建议

### 立即执行

| 优先级 | 行动 | 方式 |
|--------|------|------|
| 🔴 P0 | 确认 TickFlow 当前套餐和到期时间 | 登录 tickflow.org → 控制台 |
| 🔴 P0 | 确认 i问财 SkillHub OpenAPI 是否产生费用 | 联系同花顺客服 952555 或登录查看 |
| 🟡 P1 | 确认 TickFlow Expert 月费 ¥199 的自动续费状态 | 控制台 Billing 页面 |
| 🟡 P1 | 确认 SkillHub OpenAPI 的调用次数和配额 | 寻找用量仪表盘或联系技术支持 |

### 中长期

| 行动 | 说明 |
|------|------|
| 将两个 Key 从 `.env` 移到 `~/.openclaw/keys.env` | 当前 `.env` 中 Key 完整明文暴露，任何人 clone 仓库即可获取 |
| 建立月度费用监控 | 记录 TickFlow + i问财 + GPT-5.5 三项月费，避免预算超支 |
| 如果 SkillHub 开始收费且超预算 | 备选方案：AKShare（免费）+ pywencai（需cookie）替代涨停原因解释 |

---

## 六、关键发现：浏览器反检测方案导致的信息获取断层

本次调查暴露了一个系统性问题：**两个数据源的定价页面都是 JS 渲染的登录后页面**，传统的 `WebFetch`/搜索引擎无法抓取。

这正是前几个对话中 browser-use 无头模式被反爬识别的问题。解决方案已在 `BROWSER_ANTI_DETECTION_SURVEY.md` 中详细分析：

- **推荐方案**：接入 `puppeteer-real-browser-mcp-server`（用 J先生 的真实 Chrome Profile，绕过反爬）
- **备选方案**：`nodriver`（Python CDP 直连，2026 基准测试 28/31 Cloudflare 通过）

一旦完成浏览器反检测方案部署，即可用 J先生 的 Chrome 登录态直接访问 TickFlow 控制台和 i问财后台，获取精确的订阅状态和费用信息。

---

## 参考来源

1. TickFlow 官网: https://tickflow.org
2. TickFlow Pricing: https://tickflow.org/pricing/ (JS渲染，通过 browser-use 获取)
3. TickFlow GitHub SDK: https://github.com/tickflow-org/tickflow
4. Zhihu 作者原文: https://zhuanlan.zhihu.com/p/2015793350209450091
5. Zhihu 数据源对比: https://zhuanlan.zhihu.com/p/2023293142783238466
6. 同花顺量化API帮助中心: https://quantapi.10jqka.com.cn/gwstatic/static/ds_web/quantapi-web/help-center.html
7. 火山引擎 免费vs付费API: https://developer.volcengine.com/articles/7638935497667084329
8. 腾讯云 TickDB 选型: https://tickdb.ai/blog/api-guide/全网最全最深2026年量化数据源终极选型
9. CSDN 2026量化数据源: https://blog.csdn.net/2601_95822456/article/details/160144102
10. GitCode SkillHub分析: https://gitcode.csdn.net/69c251b60a2f6a37c599fa66.html
