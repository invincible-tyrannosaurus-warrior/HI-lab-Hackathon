"""
Build novelty index offline (batch + resume).

Usage:
  python Paper-KG-Pipeline/scripts/tools/build_novelty_index.py
  python Paper-KG-Pipeline/scripts/tools/build_novelty_index.py --batch-size 32 --resume
  python Paper-KG-Pipeline/scripts/tools/build_novelty_index.py --force-rebuild
"""

import argparse
import json
import os
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

import numpy as np
from tqdm import tqdm

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

from idea2paper.config import (
    OUTPUT_DIR,
    NOVELTY_INDEX_DIR,
    NOVELTY_INDEX_BUILD_BATCH_SIZE,
    NOVELTY_INDEX_BUILD_RESUME,
    NOVELTY_INDEX_BUILD_MAX_RETRIES,
    NOVELTY_INDEX_BUILD_SLEEP_SEC,
)
from idea2paper.novelty.novelty_index import build_paper_text
from idea2paper.infra.embeddings import get_embeddings_batch, EMBEDDING_MODEL


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_matrix(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _load_nodes_paper(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_done_ids(meta_path: Path) -> set:
    done = set()
    if not meta_path.exists():
        return done
    with meta_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                pid = obj.get("paper_id")
                if pid:
                    done.add(pid)
            except Exception:
                continue
    return done


def _next_part_index(index_dir: Path) -> int:
    parts = sorted(index_dir.glob("paper_emb.part_*.npy"))
    if not parts:
        return 0
    last = parts[-1].stem  # paper_emb.part_XXXX
    try:
        return int(last.split("_")[-1]) + 1
    except Exception:
        return len(parts)


def _merge_parts(index_dir: Path, emb_path: Path):
    parts = sorted(index_dir.glob("paper_emb.part_*.npy"))
    if not parts:
        return
    mats = []
    for p in parts:
        mats.append(np.load(p))
    mat = np.vstack(mats) if mats else np.zeros((0, 0), dtype=np.float32)
    np.save(emb_path, mat)
    # cleanup part files after successful merge
    for p in parts:
        try:
            p.unlink()
        except Exception:
            pass


def build_novelty_index(
    index_dir: Path,
    batch_size: int,
    resume: bool,
    max_retries: int,
    sleep_sec: float,
    force_rebuild: bool,
    logger=None,
):
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    meta_path = index_dir / "paper_meta.jsonl"
    emb_path = index_dir / "paper_emb.npy"
    manifest_path = index_dir / "index_manifest.json"

    nodes_paper_path = OUTPUT_DIR / "nodes_paper.json"
    if not nodes_paper_path.exists():
        raise FileNotFoundError(f"nodes_paper.json not found: {nodes_paper_path}")

    current_hash = _file_hash(nodes_paper_path)

    if force_rebuild:
        for p in index_dir.glob("*"):
            if p.is_file():
                try:
                    p.unlink()
                except Exception:
                    pass

    if emb_path.exists() and meta_path.exists() and manifest_path.exists() and not force_rebuild:
        return {"ok": True, "skipped": 0, "index_dir": str(index_dir), "already_exists": True}

    papers = _load_nodes_paper(nodes_paper_path)
    done_ids = _read_done_ids(meta_path) if resume else set()
    part_idx = _next_part_index(index_dir) if resume else 0

    if done_ids:
        print(f"↩️  Resume enabled: {len(done_ids)} already processed")

    skipped = 0
    batch_texts = []
    batch_meta = []

    def flush_batch(batch_texts, batch_meta, part_idx):
        nonlocal skipped
        if not batch_texts:
            return part_idx

        embeddings = None
        for attempt in range(max_retries + 1):
            embeddings = get_embeddings_batch(batch_texts, logger=logger)
            if embeddings is not None:
                break
            time.sleep(sleep_sec * (attempt + 1))

        if embeddings is None:
            skipped += len(batch_meta)
            return part_idx

        mat = np.array(embeddings, dtype=np.float32)
        mat = _normalize_matrix(mat)

        part_path = index_dir / f"paper_emb.part_{part_idx:04d}.npy"
        np.save(part_path, mat)
        part_idx += 1

        with meta_path.open("a", encoding="utf-8") as f:
            for m in batch_meta:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

        return part_idx

    for paper in tqdm(papers, desc="Processing papers"):
        pid = paper.get("paper_id")
        if pid in done_ids:
            continue
        text = build_paper_text(paper)
        meta = {
            "paper_id": pid or "",
            "title": paper.get("title", ""),
            "pattern_id": paper.get("pattern_id", ""),
            "domain": paper.get("domain", ""),
            "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()
        }
        batch_texts.append(text)
        batch_meta.append(meta)

        if len(batch_texts) >= batch_size:
            part_idx = flush_batch(batch_texts, batch_meta, part_idx)
            batch_texts, batch_meta = [], []
            time.sleep(sleep_sec)

    part_idx = flush_batch(batch_texts, batch_meta, part_idx)
    _merge_parts(index_dir, emb_path)

    index_count = 0
    if meta_path.exists():
        with meta_path.open("r", encoding="utf-8") as f:
            index_count = sum(1 for _ in f if _.strip())

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": EMBEDDING_MODEL,
        "paper_count": len(papers),
        "index_count": index_count,
        "skipped": skipped,
        "nodes_paper_hash": current_hash,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True, "skipped": skipped, "index_dir": str(index_dir), "index_count": index_count}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-dir", default=str(NOVELTY_INDEX_DIR))
    parser.add_argument("--batch-size", type=int, default=NOVELTY_INDEX_BUILD_BATCH_SIZE)
    parser.add_argument("--resume", action="store_true", default=NOVELTY_INDEX_BUILD_RESUME)
    parser.add_argument("--no-resume", action="store_true", default=False)
    parser.add_argument("--force-rebuild", action="store_true", default=False)
    parser.add_argument("--max-retries", type=int, default=NOVELTY_INDEX_BUILD_MAX_RETRIES)
    parser.add_argument("--sleep-sec", type=float, default=NOVELTY_INDEX_BUILD_SLEEP_SEC)
    args = parser.parse_args()

    if args.no_resume:
        args.resume = False

    result = build_novelty_index(
        index_dir=Path(args.index_dir),
        batch_size=args.batch_size,
        resume=args.resume,
        max_retries=args.max_retries,
        sleep_sec=args.sleep_sec,
        force_rebuild=args.force_rebuild,
    )
    if result.get("already_exists"):
        print("✅ Index already exists. Use --force-rebuild to rebuild.")
    else:
        print("✅ Build done.")
        print(f"   index_count={result.get('index_count')}, skipped={result.get('skipped')}")
        print(f"   index_dir={result.get('index_dir')}")


if __name__ == "__main__":
    main()
