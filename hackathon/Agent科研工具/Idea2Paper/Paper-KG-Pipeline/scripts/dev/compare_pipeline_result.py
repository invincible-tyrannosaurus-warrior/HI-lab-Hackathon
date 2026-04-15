#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, List, Tuple

IGNORE_KEYS = {
    "run_id",
    "results_dir",
    "log_dir",
    "run_log_dir",
    "report_path",
    "output_path",
    "created_at",
    "started_at",
    "ended_at",
    "duration",
    "duration_ms",
    "elapsed",
    "elapsed_ms",
    "timestamp",
    "ts",
    "time",
}


def _normalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in IGNORE_KEYS:
                continue
            out[k] = _normalize(v)
        return out
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    return obj


def _diff(a: Any, b: Any, path: str = "") -> List[str]:
    diffs: List[str] = []
    if type(a) != type(b):
        diffs.append(f"{path}: type {type(a).__name__} != {type(b).__name__}")
        return diffs
    if isinstance(a, dict):
        a_keys = set(a.keys())
        b_keys = set(b.keys())
        for k in sorted(a_keys - b_keys):
            diffs.append(f"{path}/{k}: missing in B")
        for k in sorted(b_keys - a_keys):
            diffs.append(f"{path}/{k}: extra in B")
        for k in sorted(a_keys & b_keys):
            diffs.extend(_diff(a[k], b[k], f"{path}/{k}"))
        return diffs
    if isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path}: len {len(a)} != {len(b)}")
        for i, (va, vb) in enumerate(zip(a, b)):
            diffs.extend(_diff(va, vb, f"{path}[{i}]"))
        return diffs
    if a != b:
        diffs.append(f"{path}: {a!r} != {b!r}")
    return diffs


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", required=True, help="baseline pipeline_result.json")
    parser.add_argument("--b", required=True, help="after pipeline_result.json")
    args = parser.parse_args()

    a = _normalize(load_json(Path(args.a)))
    b = _normalize(load_json(Path(args.b)))
    diffs = _diff(a, b, "")
    if diffs:
        print("DIFF FOUND:")
        for d in diffs[:200]:
            print("-", d)
        print(f"Total diffs: {len(diffs)}")
        raise SystemExit(1)
    print("OK: normalized results match")


if __name__ == "__main__":
    main()
