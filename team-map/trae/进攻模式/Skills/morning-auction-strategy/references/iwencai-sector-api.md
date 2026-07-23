# iWencai OpenAPI — Sector Data Pipeline

## 背景

防御管线第一层「题材前置筛选」(`core/sector_filter.py`) 使用 Eastmoney `fetch_blocks()` + `fs=b:block_name` 查询板块成分股。实测 0/51 候选匹配到活跃板块 — Eastmoney 该 API 格式对概念板块不适用。

同花顺问财 OpenAPI (`hithink-sector-selector`) 提供了可用的板块查询能力。

## 安装

```bash
# 1. 安装 SkillHub CLI
curl -sS -L "https://www.iwencai.com/skillhub/static/0.0.4/download_and_install.sh" | bash

# 2. 安装技能
iwencai-skillhub-cli install hithink-sector-selector
```

安装路径: `/Users/fiona/.openclaw/workspace/skills/hithink-sector-selector/`

## 环境变量

必须设置在 shell profile (`~/.zshrc`, `~/.zprofile`):

```bash
export IWENCAI_BASE_URL="https://openapi.iwencai.com"
export IWENCAI_API_KEY="sk-proj-00-..."
```

## API 端点

```
POST https://openapi.iwencai.com/v1/query2data
```

### 必填 Headers

| Header | Value |
|--------|-------|
| `Authorization` | `Bearer <IWENCAI_API_KEY>` |
| `Content-Type` | `application/json` |
| `X-Claw-Call-Type` | `normal` (或 `retry` 重试) |
| `X-Claw-Skill-Id` | `hithink-sector-selector` |
| `X-Claw-Skill-Version` | `1.0.0` |
| `X-Claw-Plugin-Id` | `none` |
| `X-Claw-Plugin-Version` | `none` |
| `X-Claw-Trace-Id` | `secrets.token_hex(32)` (64字符) |

### 请求体

```json
{
  "query": "涨幅前五的概念板块",
  "page": "1",
  "limit": "10",
  "is_cache": "1",
  "expand_index": "true"
}
```

### 响应结构

```json
{
  "columns": [{"key": "指数简称", "label": "name"}, ...],
  "datas": [
    {"指数代码": "885893.TI", "指数简称": "国家大基金持股", "涨跌幅[20260709]": 7.76},
    ...
  ],
  "code_count": 5
}
```

关键字段:
- `指数简称` — 板块名称
- `涨跌幅[YYYYMMDD]` — 指定日涨跌幅
- `指数代码` — 同花顺指数代码 (`.TI` 后缀)
- `指数类型` — `同花顺概念指数` | `同花顺行业指数`

## CLI 使用

```bash
cd /Users/fiona/.openclaw/workspace/skills/hithink-sector-selector
python3 scripts/cli.py --query "涨幅前五的概念板块" --limit 5
python3 scripts/cli.py --query "资金净流入的板块" --page 1 --limit 20
```

## curl 等效

```bash
TRACE=$(python3 -c "import secrets; print(secrets.token_hex(32))")
curl -sS -X POST "${IWENCAI_BASE_URL}/v1/query2data" \
  -H "Authorization: Bearer ${IWENCAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "X-Claw-Call-Type: normal" \
  -H "X-Claw-Skill-Id: hithink-sector-selector" \
  -H "X-Claw-Skill-Version: 1.0.0" \
  -H "X-Claw-Plugin-Id: none" \
  -H "X-Claw-Plugin-Version: none" \
  -H "X-Claw-Trace-Id: ${TRACE}" \
  -d '{"query":"涨幅前五的概念板块","page":"1","limit":"5","is_cache":"1","expand_index":"true"}'
```

## 已验证数据 (2026-07-10 查询 0709 数据)

| 板块 | 涨跌幅 |
|------|--------|
| 国家大基金持股 | +7.76% |
| 科创次新股 | +6.23% |
| 中芯国际概念 | +6.12% |
| 存储芯片 | +6.10% |
| 先进封装 | +5.52% |

## 与 datakit iwencai 适配器的关系

datakit 的 iwencai 适配器使用旧的 scraping 端点, 与 OpenAPI 不同。`datakit ops check` 对 iwencai 会超时 — 这是预期行为, 旧适配器未适配 OpenAPI。防御管线应直接使用 hithink-sector-selector CLI 或构造 HTTP 请求, 不经过 datakit iwencai 适配器。

## 0710 进一步验证

**sector_filter 连续失败**: 0709(0/51) + 0710(0/37) 两次实盘 Eastmoney block API 均返回 0 匹配。防御管线第一层持续降级 — 所有候选标记 `sector: unknown`。

**iWencai 成分股查询成功**: `"贵金属板块成分股 涨幅排名"` → 14 只成分股; `"人形机器人板块成分股 涨幅排名"` → 30 只; `"CPO板块成分股 涨幅排名"` → 30 只; `"商业航天板块成分股 涨幅排名"` → 35 只。附带 `股票代码` + `股票简称` + `最新价` + `最新涨跌幅`。

## 穿透识别模式 (0710)

用户指令 `XX板块，做一次穿透识别` → Agent 执行三步穿透：

1. **iWencai 拉取板块所有成分股** (含代码+涨幅+现价)
2. **Gate⓪ 交叉**: 成分股 ∩ 昨日涨停池 → 筛选入池标的
3. **Gate① 竞价闸**: 对Gate⓪通过标的应用 `价格∈[VWAP底, 天花板]` 判定 → 确定可行域

0710 穿透结果:
```
人形机器人 30→4→2  中京电子/东山精密
CPO        30→7→3  中京电子/东山精密/通富微电
商业航天    35→4→2  中京电子/星网宇达
贵金属      14→0    Gate⓪全部排除(板块连调无涨停)
兴业银锡    —→✗    不在0709涨停池(Gate⓪ FAIL)
```

**中京电子 002579.SZ** 是三板块唯一交叉标的。
