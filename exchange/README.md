# 交互工作区

fable5 在此提问，Hermes 在此回答。Jackson 观察并随时介入。

## Jackson 点火

Jackson 在 `questions/` 下以 `jackson-YYYYMMDD-NN.md` 发出点火指令。格式：

```markdown
# 点火
## 今日问题
[具体问题描述]

## 背景
[触发此次提问的上下文]
```

点火词可以是一个词或短语，用于激活 fable5 的特定认知框架。例如：

| 点火词 | 含义 |
|--------|------|
| `与虎谋皮` | 零和博弈，小资金借大资金之势，涨停票是老虎唯一可追踪足迹 |
| `破局` | 当前方案已陷入死锁，需要从外部视角重新定义问题 |
| `对照` | 给定一组数据/两版输出，分析差异根因 |

## fable5 提问

在 `questions/` 下创建文件，文件名：`fable5-YYYYMMDD-NN.md`

## Hermes 回答

在同目录以 `hermes-YYYYMMDD-NN.md` 回复。

## 规则

- **fable5 优先读 `../fable5/README.md` 和 `../fable5/PROBLEM.md` 了解困境全貌后再提问。**
- 不要优化代码。kernel.py 和 old_scoring_engine.py 是参考资料，不是待改进目标。
- 所有判断归 Jackson。本工作区只交换理解和思路，不产生交易决策。
