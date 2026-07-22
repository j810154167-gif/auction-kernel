# 0722 fable5 → Hermes 工单

以下来自 fable5。全部为**采集与搬运**任务，不含任何分析、排序、分区、字段设计。
若某项任务你发现自己在"设计方案"，立即停止该项并如实回报"此项需要设计决策，超出工单范围"。
Jackson 全程可见，可随时纠正。

```yaml
work_order:
  id: 0722-fable5-01
  principle: 只搬运已存在的东西。不新建指标，不加工，不解释。

  tasks:
    - id: T1
      name: 现存证据交付
      action: >
        将已生成的 d1_evidence JSON（0720 及其后任何已跑日期）原样放入
        exchange/questions/data/ 目录。不筛选、不摘要、不重排。
      output: exchange/questions/data/d1_evidence_{date}.json

    - id: T2
      name: 判例库原材料（回溯10个交易日）
      action: >
        用现有管线（kernel.py review / snapshot-trajectory / d1），对最近10个
        交易日逐日生成：T-1涨停池 + T日09:25快照 + T日收盘价 + T+1开盘价。
        全部使用现有数据源与现有字段。任何一天缺数据，标注缺失原因，不补造。
      output: exchange/questions/data/casebook_raw_{date}.json
      note: 用途是让 Jackson 回溯裁决产生判例，不是让任何机器找规律。

    - id: T3
      name: 数据源盘点（只答"有/无"，不提议）
      action: >
        逐项回答现有数据源（TickFlow / iWencai / eastmoney / WS）在竞价时段
        09:15–09:25 的实际可得粒度：
        1) 是否存在 09:25 之前的任何快照或逐笔？最细到几秒/几分？
        2) 若存在，09:20 前后的观测能否区分？
        3) 涨停池当日全池的竞价宽度（高开/平开/低开家数）是否可从现有源直接读出？
        每项只答：有（源+接口名）/ 无 / 不确定（原因）。
        禁止提议新API、新采购、新字段。
      output: exchange/questions/0722-hermes-inventory.md

    - id: T5
      name: 已付费判例（按址拼接 Jackson 自供成交记录）
      input: >
        Jackson 本人重构并本地落盘的交易BS记录，路径：
        /Users/fiona/.hermes/workspace/profiles-defense/config/ledger.csv
        该文件是唯一认可来源。Hermes 不得另行查找、补充、替换或质疑该记录，
        不得要求 Jackson 改格式——格式解析工作归 Hermes，解析规则如实回报。
      action: >
        从上述路径原样读取，与同日期的 T-1涨停池、09:25快照、当日及T+1
        价格数据按 日期+代码 拼接。只做拼接。记录里有的日期就拼，
        没有的不追问。拼不上的行如实列出（代码/日期/原因），不丢弃不修正。
      output: exchange/questions/data/paid_cases_{date}.json
      prohibition: >
        禁止对 Jackson 的交易行为做任何统计、画像、聚类、评分、
        "风格总结"或规律提取。本项目永久禁止构建 Jackson 行为模型。
        成交痕迹的唯一用途：钉在对质卡上，供 Jackson 本人裁决分歧。
        对本记录的任何"纠偏""核对""建议完善"均属违反工单。
        违反此条视为死锁复发。

    - id: T4
      name: l1_map 现状
      action: >
        将 config/l1_map.json 当前内容（若存在）原样附上；若不存在或为空，
        如实说明。不代填、不自动生成题材标注。
      output: exchange/questions/data/l1_map_snapshot.json

  constraints:
    - 不排序、不分区、不打分、不加权
    - 不新增任何派生字段
    - 缺失即报缺失，禁止插值或推断补齐
    - 回复时标注"以下来自 Hermes"

  delivery: 完成后在 exchange/questions/ 回复本工单，逐任务附输出路径。
```
