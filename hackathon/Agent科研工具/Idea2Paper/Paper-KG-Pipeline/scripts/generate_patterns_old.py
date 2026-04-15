#!/usr/bin/env python3
from pathlib import Path
import runpy

# Compatibility wrapper (scripts/ -> scripts/legacy)
runpy.run_path(str(Path(__file__).parent / "legacy" / "generate_patterns_old.py"), run_name="__main__")
