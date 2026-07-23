"""TickFlow 凭据加载。密钥不写入提示词、路由或代码。"""
import os
from pathlib import Path


DEFAULT_KEY_FILE = Path(
    "/Users/fiona/.openclaw/workspace/skills/"
    "tickflow-expert-governance/tickflow expert api.txt"
)


def load_tickflow_api_key() -> str:
    """环境变量优先；其次读取指定文件；最后读取本机既有安全文件。"""
    key = os.environ.get("TICKFLOW_API_KEY", "").strip()
    if key:
        return key

    configured = os.environ.get("TICKFLOW_API_KEY_FILE", "").strip()
    key_file = Path(configured).expanduser() if configured else DEFAULT_KEY_FILE
    try:
        key = key_file.read_text().strip()
    except OSError as exc:
        raise RuntimeError(
            "TickFlow API key missing: set TICKFLOW_API_KEY or "
            "TICKFLOW_API_KEY_FILE"
        ) from exc

    if not key:
        raise RuntimeError(f"TickFlow API key file is empty: {key_file}")
    return key
