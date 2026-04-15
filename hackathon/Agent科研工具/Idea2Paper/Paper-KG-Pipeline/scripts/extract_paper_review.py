#!/usr/bin/env python3
from pathlib import Path
import runpy

# Compatibility wrapper (scripts/ -> scripts/tools)
runpy.run_path(str(Path(__file__).parent / "tools" / "extract_paper_review.py"), run_name="__main__")
