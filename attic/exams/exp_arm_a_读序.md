# 臂A·生料读序工单(零历史会话专用)

你是一个刚被唤醒的会话,没有任何历史。你将按下列**严格顺序**阅读仓库
(github.com/j810154167-gif/auction-kernel)中的指定文件,然后作答一张考卷。

## 铁律(先读这四条)
1. 只读本工单列出的文件,按列出的顺序读,读完一份再读下一份。
2. **严禁**打开 exchange/questions/data/ 目录下除考卷外的任何文件——里面含事后结果,碰了实验作废。
3. 严禁联网搜索、严禁查询任何市场数据。你的时刻被冻结在 2026-07-20 09:25。
4. 读的过程中不输出总结;全部读完后只输出考卷要求的JSON。

## 读序
1. `README.md` — 项目是什么
2. `fable5/README.md` → `fable5/PROBLEM.md` — 死锁如何被提出
3. `ROLES.md` — 三方是谁
4. `defense_zone.py` — 已经工作的人机模型(逐行读,含注释)
5. `old_scoring_engine.py` — 死掉的第一个内核(读它为何会死)
6. `kernel.py` — 现行复盘→D1管线
7. `exchange/对话记录/近期 x 上的 Serenity@aleabitoreddit 大热，全球金融市场似乎出现了很多 S (5).md` — 项目主人一个月的沙盘实录(全文,这是最重要的一份)
8. `exchange/对话记录/国新和城通增持的是什么股票和 ETF？有具体信息吗？.md` — 他的资金结构校验实操
9. `exchange/对话记录/月之暗面（Kimi）全维度深度穿透调研报告.md` — 他的事件驱动清单格式
10. `exchange/对话记录/帮我校验传闻：长鑫科技目前外围链上交易目标估值为 5 万亿.md` — 他的信息代谢建模
(大摩研报一份因体积跳过,如实告知你。)

## 考卷
读完以上全部后,读 `exchange/questions/exp_instruction.txt`,
再读 `exchange/questions/exp_exam.json`,按指令作答,只输出JSON。
