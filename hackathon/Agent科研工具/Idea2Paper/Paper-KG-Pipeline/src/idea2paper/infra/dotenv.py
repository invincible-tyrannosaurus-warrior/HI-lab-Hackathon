import os
from pathlib import Path


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_dotenv(path: Path, override: bool = False) -> dict:
    """Load .env into os.environ.

    Returns: {"loaded": int, "path": str, "ok": bool, "error": str|None}
    """
    result = {"loaded": 0, "path": str(path), "ok": True, "error": None}
    try:
        if not path.exists():
            return result
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith("#"):
                    continue
                if raw.startswith("export "):
                    raw = raw[len("export "):].lstrip()
                if "=" not in raw:
                    continue
                key, value = raw.split("=", 1)
                key = key.strip()
                value = _strip_quotes(value.strip())
                if not key:
                    continue
                if not override and key in os.environ:
                    continue
                os.environ[key] = value
                result["loaded"] += 1
        return result
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)
        print(f"[dotenv] warning: failed to load {path}: {e}")
        return result
