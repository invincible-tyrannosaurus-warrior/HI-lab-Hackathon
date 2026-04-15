#!/usr/bin/env python3
from pathlib import Path
import runpy

# Compatibility wrapper (scripts/ -> scripts/demos)
runpy.run_path(str(Path(__file__).parent / "demos" / "demo_pipeline.py"), run_name="__main__")
