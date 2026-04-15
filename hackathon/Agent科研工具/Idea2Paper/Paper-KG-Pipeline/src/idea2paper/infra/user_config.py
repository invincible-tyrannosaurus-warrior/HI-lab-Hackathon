import json
from pathlib import Path


def get_config_path(repo_root: Path) -> Path:
    env_raw = __import__("os").environ.get("I2P_CONFIG_PATH", "")
    if env_raw:
        return Path(env_raw)
    return repo_root / "i2p_config.json"


def load_user_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        print(f"[config] warning: failed to load {path}: {e}")
        return {}
