from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from idea2paper.recall.recall_system import RecallSystem

__all__ = ["RecallSystem"]
