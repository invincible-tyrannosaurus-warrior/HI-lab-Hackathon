import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from idea2paper.config import LLM_PROVIDER, LLM_MODEL, LLM_API_URL, LLM_BASE_URL  # noqa: E402
from idea2paper.infra.llm import call_llm  # noqa: E402


def main():
    endpoint = LLM_API_URL or LLM_BASE_URL
    print(f"[llm_smoke_test] provider={LLM_PROVIDER} model={LLM_MODEL} endpoint={endpoint}")
    text = call_llm("ping", temperature=0.0, max_tokens=32, timeout=30)
    preview = text[:200] if isinstance(text, str) else str(text)[:200]
    print(f"[llm_smoke_test] output: {preview}")


if __name__ == "__main__":
    main()
