import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SCRIPTS_DIR.parent
REPO_ROOT = PROJECT_ROOT.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from idea2paper.infra.dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=False)
except Exception:
    pass

from idea2paper.infra.startup_preflight import run_startup_preflight  # noqa: E402


def main() -> int:
    pre = run_startup_preflight()
    if pre.ok:
        print("✅ preflight_check OK")
        return 0
    print("❌ preflight_check FAILED")
    print(f"   error={pre.error}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

