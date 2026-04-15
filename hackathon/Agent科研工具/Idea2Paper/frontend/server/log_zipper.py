from __future__ import annotations

import zipfile
from pathlib import Path


def make_zip(log_dir: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in log_dir.rglob("*"):
            if p.is_dir():
                continue
            # only include files under log_dir
            rel = p.relative_to(log_dir)
            zf.write(p, arcname=str(rel))
    return out_path
