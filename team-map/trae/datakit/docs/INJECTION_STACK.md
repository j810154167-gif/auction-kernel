# API Key 注入栈 — datakit

> 描述 datakit 工具包如何发现、加载和使用 API Key。
> 面向对象：datakit 开发者 + 调用 datakit 的 Agent。

## 注入链路

```
Layer 0: OS 环境变量
  export TICKFLOW_API_KEY=tk_xxx
  export IWENCAI_API_KEY=sk-proj-xxx
          │
          ▼
Layer 1: _FILE 备选路径（docker/k8s secret mount）
  export TICKFLOW_API_KEY_FILE=/run/secrets/tickflow_key
          │
          ▼
Layer 2: datakit/adapters/*.py
  每个 adapter 独立读取: os.environ.get("TICKFLOW_API_KEY") or
                       read_file(os.environ.get("TICKFLOW_API_KEY_FILE"))
          │
          ▼
Layer 3: datakit/inject.py
  统一注入检查: python -m datakit inject status
  人类可读指引: python -m datakit inject guide
```

## 各 Adapter Key 需求

| Adapter | Key 环境变量 | _FILE 备选 | 可选? |
|---------|-------------|-----------|------|
| tickflow | `TICKFLOW_API_KEY` | `TICKFLOW_API_KEY_FILE` | 否 |
| eastmoney | 无 | 无 | 是（免费） |
| iwencai | `IWENCAI_API_KEY` | `IWENCAI_API_KEY_FILE` | 否 |

## Key 注入检查

```bash
python -m datakit inject status
# → [
#     {"source": "tickflow", "configured": true,  "found_vars": {"TICKFLOW_API_KEY": "tk_b35f2..."}},
#     {"source": "iwencai", "configured": true,  "found_vars": {"IWENCAI_API_KEY": "sk-proj-..."}}
#   ]

python -m datakit inject guide
# → Markdown 格式的人类可读注入指引
```

## 安全约束

1. **Key 值始终遮蔽** — CLI 输出只显示前 8 位 + `...`
2. **不写回文件** — datakit 只读 `os.environ`，不修改任何文件
3. **不进 Git** — `.gitignore` 已排除 `keys.env`、`*_KEY_*.txt`
4. **_FILE 是备选** — 任一方式配了就算 `configured: true`
