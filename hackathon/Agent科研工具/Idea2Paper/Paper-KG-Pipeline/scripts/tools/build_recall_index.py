"""
Build recall indices offline (idea + paper).

Usage:
  python Paper-KG-Pipeline/scripts/tools/build_recall_index.py
  python Paper-KG-Pipeline/scripts/tools/build_recall_index.py --batch-size 32 --resume
  python Paper-KG-Pipeline/scripts/tools/build_recall_index.py --force-rebuild
"""

import argparse
import json
import hashlib
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

import numpy as np

try:
    from tqdm import tqdm
except Exception:
    tqdm = None

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
    PipelineConfig,
)
from idea2paper.recall.recall_text import (
    build_recall_idea_text,
    build_recall_paper_text,
    truncate_for_embedding,
)
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


def _load_json(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_done_ids(meta_path: Path, id_key: str) -> set:
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
                pid = obj.get(id_key)
                if pid:
                    done.add(pid)
            except Exception:
                continue
    return done


def _next_part_index(index_dir: Path, prefix: str) -> int:
    parts = sorted(index_dir.glob(f"{prefix}_emb.part_*.npy"))
    if not parts:
        return 0
    last = parts[-1].stem
    try:
        return int(last.split("_")[-1]) + 1
    except Exception:
        return len(parts)


def _merge_parts(index_dir: Path, prefix: str, emb_path: Path):
    parts = sorted(index_dir.glob(f"{prefix}_emb.part_*.npy"))
    if not parts:
        return
    mats = [np.load(p) for p in parts]
    mat = np.vstack(mats) if mats else np.zeros((0, 0), dtype=np.float32)
    np.save(emb_path, mat)
    for p in parts:
        try:
            p.unlink()
        except Exception:
            pass


def _build_index(kind: str, items: List[Dict], id_key: str, text_fn, index_dir: Path,
                 batch_size: int, resume: bool, max_retries: int, sleep_sec: float,
                 nodes_hash: str):
    meta_path = index_dir / f"{kind}_meta.jsonl"
    emb_path = index_dir / f"{kind}_emb.npy"
    manifest_path = index_dir / f"{kind}_manifest.json"

    done_ids = _read_done_ids(meta_path, id_key) if resume else set()
    part_idx = _next_part_index(index_dir, kind) if resume else 0

    skipped = 0
    processed = 0
    batch_texts = []
    batch_meta = []
    total_to_process = sum(1 for item in items if item.get(id_key) and item.get(id_key) not in done_ids)

    pbar_context = None
    if tqdm is not None:
        pbar_context = tqdm(
            total=total_to_process,
            desc=f"Recall index ({kind})",
            unit="item",
            dynamic_ncols=True,
            disable=not sys.stderr.isatty(),
        )

    def flush_batch(texts, metas, part_idx):
        nonlocal skipped, processed
        if not texts:
            return part_idx
        embeddings = None
        for attempt in range(max_retries + 1):
            embeddings = get_embeddings_batch(texts, timeout=10)
            if embeddings is not None:
                break
            time.sleep(sleep_sec * (attempt + 1))
        if embeddings is None:
            skipped += len(metas)
            if pbar_context is not None:
                pbar_context.set_postfix(parts=part_idx, skipped=skipped)
            return part_idx
        mat = np.array(embeddings, dtype=np.float32)
        mat = _normalize_matrix(mat)
        part_path = index_dir / f"{kind}_emb.part_{part_idx:04d}.npy"
        np.save(part_path, mat)
        part_idx += 1
        with meta_path.open("a", encoding="utf-8") as f:
            for m in metas:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        processed += len(metas)
        if pbar_context is not None:
            pbar_context.set_postfix(parts=part_idx, skipped=skipped)
        return part_idx

    try:
        for item in items:
            item_id = item.get(id_key)
            if not item_id or item_id in done_ids:
                continue
            text = text_fn(item)
            emb_text = truncate_for_embedding(text)
            meta = {
                id_key: item_id,
                "text_hash": hashlib.sha256(emb_text.encode("utf-8")).hexdigest(),
            }
            if kind == "idea":
                meta["snippet"] = text[:240]
                meta["pattern_count"] = len(item.get("pattern_ids", []) or [])
            else:
                meta["title"] = item.get("title", "")
                meta["pattern_id"] = item.get("pattern_id", "")
                meta["domain"] = item.get("domain", "")
                review_stats = item.get("review_stats") or {}
                meta["review_count"] = int(review_stats.get("review_count", 0) or 0)
            batch_texts.append(emb_text)
            batch_meta.append(meta)
            if pbar_context is not None:
                pbar_context.update(1)

            if len(batch_texts) >= batch_size:
                part_idx = flush_batch(batch_texts, batch_meta, part_idx)
                batch_texts, batch_meta = [], []
                time.sleep(sleep_sec)

        part_idx = flush_batch(batch_texts, batch_meta, part_idx)
    finally:
        if pbar_context is not None:
            pbar_context.close()
    _merge_parts(index_dir, kind, emb_path)

    index_count = 0
    if meta_path.exists():
        with meta_path.open("r", encoding="utf-8") as f:
            index_count = sum(1 for _ in f if _.strip())

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": EMBEDDING_MODEL,
        f"nodes_{kind}_hash": nodes_hash,
        "count": len(items),
        "index_count": index_count,
        "skipped": skipped,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"index_count": index_count, "skipped": skipped, "manifest_path": str(manifest_path)}


def build_recall_index(
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

    nodes_idea_path = OUTPUT_DIR / "nodes_idea.json"
    nodes_paper_path = OUTPUT_DIR / "nodes_paper.json"
    if not nodes_idea_path.exists() or not nodes_paper_path.exists():
        raise FileNotFoundError("nodes_idea.json or nodes_paper.json not found in output/")

    if force_rebuild:
        for p in index_dir.glob("*"):
            if p.is_file():
                try:
                    p.unlink()
                except Exception:
                    pass

    idea_manifest = index_dir / "idea_manifest.json"
    paper_manifest = index_dir / "paper_manifest.json"
    if idea_manifest.exists() and paper_manifest.exists() and not force_rebuild:
        return {"ok": True, "already_exists": True, "index_dir": str(index_dir)}

    ideas = _load_json(nodes_idea_path)
    papers = _load_json(nodes_paper_path)

    idea_hash = _file_hash(nodes_idea_path)
    paper_hash = _file_hash(nodes_paper_path)

    idea_stats = _build_index(
        "idea",
        ideas,
        "idea_id",
        build_recall_idea_text,
        index_dir,
        batch_size,
        resume,
        max_retries,
        sleep_sec,
        idea_hash
    )
    paper_stats = _build_index(
        "paper",
        papers,
        "paper_id",
        build_recall_paper_text,
        index_dir,
        batch_size,
        resume,
        max_retries,
        sleep_sec,
        paper_hash
    )

    return {
        "ok": True,
        "idea_index_count": idea_stats.get("index_count"),
        "paper_index_count": paper_stats.get("index_count"),
        "idea_skipped": idea_stats.get("skipped"),
        "paper_skipped": paper_stats.get("skipped"),
        "index_dir": str(index_dir),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-dir", default=str(PipelineConfig.RECALL_INDEX_DIR))
    parser.add_argument("--batch-size", type=int, default=PipelineConfig.RECALL_EMBED_BATCH_SIZE)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_true", default=False)
    parser.add_argument("--force-rebuild", action="store_true", default=False)
    parser.add_argument("--max-retries", type=int, default=PipelineConfig.RECALL_EMBED_MAX_RETRIES)
    parser.add_argument("--sleep-sec", type=float, default=PipelineConfig.RECALL_EMBED_SLEEP_SEC)
    args = parser.parse_args()

    if args.no_resume:
        args.resume = False

    result = build_recall_index(
        index_dir=Path(args.index_dir),
        batch_size=args.batch_size,
        resume=args.resume,
        max_retries=args.max_retries,
        sleep_sec=args.sleep_sec,
        force_rebuild=args.force_rebuild,
    )
    if result.get("already_exists"):
        print("✅ Recall index already exists. Use --force-rebuild to rebuild.")
    else:
        print("✅ Build done.")
        print(f"   idea_index_count={result.get('idea_index_count')}, skipped={result.get('idea_skipped')}")
        print(f"   paper_index_count={result.get('paper_index_count')}, skipped={result.get('paper_skipped')}")
        print(f"   index_dir={result.get('index_dir')}")


if __name__ == "__main__":
    main()
