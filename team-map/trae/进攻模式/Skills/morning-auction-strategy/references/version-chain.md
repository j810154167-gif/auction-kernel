# 版本链架构

## 设计原则

- 包级版本：整个策略包一个版本号，不和单文件绑定
- 日期编码：`vYYYYMMDD`（日级一版，无序号。当日修改用新日期）
- 递归链：每个版本记录 `parent` 指针，形成从 v20260709 到当前的可审计演化链
- 物理层下沉：版本号不仅是 `VERSION` 文件的声明，也体现在目录结构中

## 目录结构

```
core/
  VERSION              ← 纯文本: vYYYYMMDD\nparent: vYYYYMMDD
  __init__.py           ← __version__ + __parent__ 导出
  _legacy/              ← 永久归档的废弃引擎
  v20260710/            ← 0710 不可变快照 (12文件)
  v20260713/            ← 当前 dev, fork 自 v20260710

handoff/<date>/
  *.json               ← 平铺副本 (快速访问)
  vYYYYMMDD/            ← 版本子目录 (完整追溯, 每个JSON带 engine_version + parent_version)
```

## 版本链

```
v20260709  (scoring engine, gate-as-modifier)
    ↓ parent
v20260710  (constraint system, 6-module pipeline, D2→延)
    ↓ parent
v20260713  (version management, behavioral governance, handoff chain linkage)
```

## 三门校验 (preflight P0)

启动时三者必须一致，任一不匹配 → BLOCKED:
1. `core/VERSION` → 引擎版本
2. `run_status.json` → `engine_version` 字段
3. `SKILL.md` → 声明的目标版本

## bump 流程

1. 确定变更内容
2. `mkdir core/v<新日期> && cp core/v<前一天>/*.py core/v<新日期>/`
3. 更新 `core/VERSION`: 新版本号, parent 指向前一版本
4. 更新 `core/__init__.py`: `__version__`, `__parent__`
5. 更新 `scripts/auction_engine.py`: import 路径
6. 更新 SKILL.md 目标版本
7. 改动只在当前版本目录内进行

## 旧版处置

废弃引擎 → `core/_legacy/<name>_v<version>_<reason>.py`

不删除。退回 = 有意识的考古，不是一键降级。

## Agent 行为约束 (编程到 SKILL.md)

7条 P0 + 4条 P1 约束已编程到 `morning-auction-strategy/SKILL.md` 中。Agent 每轮加载该 skill 时接收约束，preflight 时必须逐条验证。违反 P0 → BLOCKED，违反 P1 → 退化警告。
