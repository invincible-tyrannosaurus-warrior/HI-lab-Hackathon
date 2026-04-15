import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from idea2paper.recall.recall_system import RecallSystem


def _as_id_score_list(items, score_idx=1):
    out = []
    for item in items:
        if isinstance(item, (list, tuple)) and len(item) > score_idx:
            out.append((item[0], float(item[score_idx])))
    return out


def _compare_lists(name, a, b, tol=1e-6):
    if len(a) != len(b):
        raise AssertionError(f"{name} length mismatch: {len(a)} vs {len(b)}")
    for i, (xa, xb) in enumerate(zip(a, b)):
        if xa[0] != xb[0]:
            raise AssertionError(f"{name} id mismatch at {i}: {xa[0]} vs {xb[0]}")
        if abs(xa[1] - xb[1]) > tol:
            raise AssertionError(f"{name} score mismatch at {i}: {xa[1]} vs {xb[1]}")


def run_once(rs: RecallSystem, user_idea: str):
    results = rs.recall(user_idea, verbose=False)
    path1_coarse = _as_id_score_list(getattr(rs, "_last_path1_candidates", []), score_idx=1)
    path1_fine = _as_id_score_list(getattr(rs, "_last_path1_top_ideas", []), score_idx=1)

    path3_coarse_raw = getattr(rs, "_last_path3_candidates", [])
    path3_coarse = _as_id_score_list(path3_coarse_raw, score_idx=1)

    path3_fine_raw = getattr(rs, "_last_path3_top_papers", [])
    path3_fine = []
    for item in path3_fine_raw:
        if isinstance(item, (list, tuple)) and len(item) >= 4:
            path3_fine.append((item[0], float(item[1]), float(item[2]), float(item[3])))

    final_top = [(pid, float(score)) for pid, _info, score in results]

    return {
        "path1_coarse": path1_coarse,
        "path1_fine": path1_fine,
        "path3_coarse": path3_coarse,
        "path3_fine": path3_fine,
        "final_top": final_top,
    }


def compare(baseline, optimized, tol=1e-6):
    _compare_lists("path1_coarse", baseline["path1_coarse"], optimized["path1_coarse"], tol)
    _compare_lists("path1_fine", baseline["path1_fine"], optimized["path1_fine"], tol)
    _compare_lists("path3_coarse", baseline["path3_coarse"], optimized["path3_coarse"], tol)
    if len(baseline["path3_fine"]) != len(optimized["path3_fine"]):
        raise AssertionError("path3_fine length mismatch")
    for i, (a, b) in enumerate(zip(baseline["path3_fine"], optimized["path3_fine"])):
        if a[0] != b[0]:
            raise AssertionError(f"path3_fine id mismatch at {i}: {a[0]} vs {b[0]}")
        for j in range(1, 4):
            if abs(a[j] - b[j]) > tol:
                raise AssertionError(f"path3_fine value mismatch at {i}:{j} {a[j]} vs {b[j]}")
    _compare_lists("final_top", baseline["final_top"], optimized["final_top"], tol)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--idea", default="test idea")
    parser.add_argument("--use-offline-index", action="store_true", default=False)
    parser.add_argument("--tol", type=float, default=1e-6)
    args = parser.parse_args()

    base = RecallSystem()
    base._use_embed_batch = False
    base._use_token_cache = False
    base._use_offline_index = False

    opt = RecallSystem()
    opt._use_embed_batch = True
    opt._use_token_cache = True
    opt._use_offline_index = bool(args.use_offline_index)

    baseline = run_once(base, args.idea)
    optimized = run_once(opt, args.idea)

    compare(baseline, optimized, args.tol)
    print("PASS: recall outputs are equivalent")


if __name__ == "__main__":
    main()
