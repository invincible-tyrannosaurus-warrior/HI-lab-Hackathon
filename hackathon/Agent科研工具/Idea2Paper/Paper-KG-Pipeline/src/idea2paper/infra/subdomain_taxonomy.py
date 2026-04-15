import json
import time
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
try:
    from tqdm import tqdm
except Exception:
    tqdm = None

from idea2paper.config import OUTPUT_DIR, PipelineConfig, EMBEDDING_PROVIDER, EMBEDDING_API_URL, EMBEDDING_MODEL
from idea2paper.infra.embeddings import get_embeddings_batch
from idea2paper.infra.index_preflight import sha256_file


GENERIC_KEYWORDS = [
    "neural",
    "deep learning",
    "representation learning",
    "optimization",
    "benchmark",
    "machine learning",
    "artificial intelligence",
]


def resolve_subdomain_taxonomy_paths() -> Tuple[Path, Path]:
    path_cfg = getattr(PipelineConfig, "SUBDOMAIN_TAXONOMY_PATH", "") or ""
    if path_cfg:
        tax_path = Path(path_cfg)
    else:
        tax_path = Path(PipelineConfig.RECALL_INDEX_DIR) / "subdomain_taxonomy.json"
    patterns_path = Path(OUTPUT_DIR) / "nodes_pattern.json"
    return tax_path, patterns_path


def validate_subdomain_taxonomy(tax_path: Path, patterns_path: Path) -> Dict:
    tax_path = Path(tax_path)
    patterns_path = Path(patterns_path)
    result = {
        "ok": False,
        "reason": "missing",
        "details": {},
        "paths": {
            "taxonomy_path": str(tax_path),
            "patterns_path": str(patterns_path),
        },
    }

    if not tax_path.exists():
        return result

    try:
        data = json.loads(tax_path.read_text(encoding="utf-8"))
    except Exception:
        result["reason"] = "load_failed"
        return result

    mapping = data.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        result["reason"] = "mismatch"
        return result

    manifest = data.get("manifest") or {}
    result["details"]["embedding_model"] = EMBEDDING_MODEL
    result["details"]["manifest_model"] = manifest.get("embedding_model")
    result["details"]["embedding_used"] = manifest.get("embedding_used")
    result["details"]["manifest_nodes_pattern_sha256"] = manifest.get("nodes_pattern_sha256")
    result["details"]["manifest_sha256"] = sha256_file(tax_path)

    if manifest.get("embedding_model") != EMBEDDING_MODEL:
        result["reason"] = "mismatch"
        return result

    if not bool(manifest.get("embedding_used")):
        result["reason"] = "mismatch"
        return result

    if not patterns_path.exists():
        result["reason"] = "mismatch"
        return result

    current_hash = sha256_file(patterns_path)
    result["details"]["nodes_pattern_sha256"] = current_hash
    if manifest.get("nodes_pattern_sha256") != current_hash:
        result["reason"] = "mismatch"
        return result

    if manifest.get("embedding_api_url") != EMBEDDING_API_URL:
        result["details"]["embedding_api_url_mismatch"] = True
        result["details"]["embedding_api_url"] = EMBEDDING_API_URL
        result["details"]["manifest_api_url"] = manifest.get("embedding_api_url")

    result["ok"] = True
    result["reason"] = "ok"
    return result


def embed_cards_in_batches(
    cards: List[str],
    *,
    batch_size: int,
    max_retries: int,
    sleep_sec: float,
    timeout: int,
    logger=None,
):
    if not cards:
        return [], {"batch_count": 0, "failed_batch_idx": None, "error": None}

    if batch_size <= 0:
        batch_size = len(cards)

    total = len(cards)
    batches = [cards[i:i + batch_size] for i in range(0, total, batch_size)]
    all_embeddings = []
    meta = {"batch_count": len(batches), "failed_batch_idx": None, "error": None}

    pbar_context = None
    if tqdm is not None:
        pbar_context = tqdm(
            total=len(batches),
            desc="Taxonomy embedding",
            unit="batch",
            dynamic_ncols=True,
            disable=not sys.stderr.isatty(),
        )

    try:
        for idx, batch in enumerate(batches):
            last_ok = None
            for attempt in range(max_retries + 1):
                if pbar_context is not None:
                    pbar_context.set_postfix(batch_size=len(batch), attempt=attempt + 1)
                last_ok = get_embeddings_batch(batch, logger=logger, timeout=timeout)
                if last_ok is not None:
                    break
                if attempt < max_retries:
                    time.sleep(sleep_sec * (attempt + 1))
            if last_ok is None:
                meta["failed_batch_idx"] = idx
                meta["error"] = f"embedding batch failed after {max_retries + 1} attempts"
                return None, meta
            all_embeddings.extend(last_ok)
            if pbar_context is not None:
                pbar_context.update(1)
    finally:
        if pbar_context is not None:
            pbar_context.close()

    return all_embeddings, meta


def _load_json(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_matrix(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    return text[:max_chars]


def _tokenize(text: str) -> frozenset:
    if not text:
        return frozenset()
    tokens = []
    current = []
    for ch in text.lower():
        if ch.isalnum():
            current.append(ch)
        else:
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))
    return frozenset(tokens)


def _jaccard(t1: frozenset, t2: frozenset) -> float:
    if not t1 or not t2:
        return 0.0
    inter = t1 & t2
    union = t1 | t2
    return len(inter) / len(union)


class _DSU:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


def _cluster_by_threshold(sim: np.ndarray, threshold: float) -> List[List[int]]:
    n = sim.shape[0]
    dsu = _DSU(n)
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= threshold:
                dsu.union(i, j)
    groups = defaultdict(list)
    for i in range(n):
        groups[dsu.find(i)].append(i)
    return list(groups.values())


def _cluster_count(sim: np.ndarray, threshold: float) -> int:
    return len(_cluster_by_threshold(sim, threshold))


def _choose_threshold(sim: np.ndarray, k_min: int, k_max: int, t_min: float, t_max: float) -> float:
    if sim.shape[0] == 0:
        return t_min
    thresholds = np.linspace(t_max, t_min, int(round((t_max - t_min) / 0.01)) + 1)
    best = None
    k_mid = (k_min + k_max) / 2.0
    for th in thresholds:
        count = _cluster_count(sim, float(th))
        in_range = k_min <= count <= k_max
        if in_range:
            score = abs(count - k_mid)
        else:
            if count < k_min:
                score = k_min - count
            else:
                score = count - k_max
        if best is None or score < best[0] or (score == best[0] and th > best[1]):
            best = (score, float(th), count)
    return best[1] if best else t_min


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def build_subdomain_taxonomy(
    patterns_path: Path,
    papers_path: Path | None,
    output_path: Path,
    target_k_min: int = 40,
    target_k_max: int = 80,
    sim_min: float = 0.70,
    sim_max: float = 0.95,
    min_papers: int = 30,
    merge_min_sim: float = 0.75,
    stoplist_ratio_max_median: float = 10.0,
    stoplist_domain_ratio: float = 0.30,
    max_exemplar_papers: int = 5,
    max_cooccur: int = 5,
    max_domains: int = 3,
    embed_batch_size: int | None = None,
    embed_max_retries: int | None = None,
    embed_sleep_sec: float | None = None,
    embed_timeout: int = 120,
    logger=None,
) -> Dict:
    patterns = _load_json(patterns_path)
    papers_by_id = {}
    if papers_path and papers_path.exists():
        papers = _load_json(papers_path)
        papers_by_id = {p.get("paper_id"): p for p in papers if p.get("paper_id")}

    raw_stats = {}
    co_counts = defaultdict(Counter)
    domain_counts = defaultdict(Counter)
    paper_ids_by_sd = defaultdict(set)
    all_domains = set()

    for pattern in patterns:
        sub_domains = pattern.get("sub_domains", []) or []
        if not sub_domains:
            continue
        pattern_id = pattern.get("pattern_id")
        domain = pattern.get("domain") or pattern.get("domain_id")
        if domain:
            all_domains.add(domain)
        size = pattern.get("size")
        if size is None:
            size = pattern.get("cluster_size")
        if size is None:
            size = len(pattern.get("exemplar_paper_ids", []) or [])
        size = _safe_float(size, 0.0)
        exemplar_ids = pattern.get("exemplar_paper_ids", []) or []

        for sd in sub_domains:
            if not sd:
                continue
            stats = raw_stats.setdefault(sd, {"pattern_ids": set(), "domain_ids": set(), "paper_count_est": 0.0})
            if pattern_id:
                stats["pattern_ids"].add(pattern_id)
            if domain:
                stats["domain_ids"].add(domain)
                domain_counts[sd][domain] += 1
            stats["paper_count_est"] += size
            for other in sub_domains:
                if other and other != sd:
                    co_counts[sd][other] += 1
            for pid in exemplar_ids:
                if pid:
                    paper_ids_by_sd[sd].add(pid)

    raw_subdomains = sorted(raw_stats.keys())

    def build_card(sd: str) -> str:
        parts = [f"Subdomain: {sd}"]
        co = [x for x, _ in co_counts[sd].most_common(max_cooccur)]
        if co:
            parts.append("Co-occurring: " + ", ".join(co))
        doms = [x for x, _ in domain_counts[sd].most_common(max_domains)]
        if doms:
            parts.append("Domains: " + ", ".join(doms))
        if papers_by_id:
            paper_ids = sorted(paper_ids_by_sd.get(sd, []))[:max_exemplar_papers]
            snippets = []
            for pid in paper_ids:
                paper = papers_by_id.get(pid) or {}
                title = paper.get("title", "")
                abstract = paper.get("abstract", "") or ""
                snippet = title
                if abstract:
                    snippet = f"{title} - {abstract}"
                snippets.append(_truncate(snippet, 200))
            if snippets:
                parts.append("Exemplars: " + " | ".join(snippets))
        return "\n".join(parts)

    cards = [build_card(sd) for sd in raw_subdomains]

    if embed_batch_size is None:
        embed_batch_size = PipelineConfig.RECALL_EMBED_BATCH_SIZE
    if embed_max_retries is None:
        embed_max_retries = PipelineConfig.RECALL_EMBED_MAX_RETRIES
    if embed_sleep_sec is None:
        embed_sleep_sec = PipelineConfig.RECALL_EMBED_SLEEP_SEC

    embeddings = None
    embed_meta = {"batch_count": 0, "failed_batch_idx": None, "error": None}
    if raw_subdomains:
        embeddings, embed_meta = embed_cards_in_batches(
            cards,
            batch_size=embed_batch_size,
            max_retries=embed_max_retries,
            sleep_sec=embed_sleep_sec,
            timeout=embed_timeout,
            logger=logger,
        )

    if embeddings is not None:
        emb = np.array(embeddings, dtype=np.float32)
        emb = _normalize_matrix(emb)
        sim = emb @ emb.T
        embedding_used = True
    else:
        tokens = [_tokenize(card) for card in cards]
        n = len(tokens)
        sim = np.eye(n, dtype=np.float32)
        for i in range(n):
            for j in range(i + 1, n):
                s = _jaccard(tokens[i], tokens[j])
                sim[i, j] = s
                sim[j, i] = s
        emb = None
        embedding_used = False

    threshold = _choose_threshold(sim, target_k_min, target_k_max, sim_min, sim_max)
    clusters = _cluster_by_threshold(sim, threshold)

    mapping = {}
    canonical_groups = {}
    canonical_vectors = {}
    canonical_stats = {}

    for group in clusters:
        group_sds = [raw_subdomains[i] for i in group]
        if emb is not None:
            centroid = np.mean(emb[group], axis=0)
            centroid = centroid / (np.linalg.norm(centroid) or 1.0)
            best_idx = max(group, key=lambda i: float(np.dot(emb[i], centroid)))
            canonical = raw_subdomains[best_idx]
            canonical_vectors[canonical] = centroid
        else:
            canonical = max(group_sds, key=lambda sd: raw_stats[sd]["paper_count_est"])
        canonical_groups[canonical] = group_sds
        for sd in group_sds:
            mapping[sd] = canonical

    for canonical, group_sds in canonical_groups.items():
        paper_count = sum(raw_stats[sd]["paper_count_est"] for sd in group_sds)
        domain_ids = set()
        for sd in group_sds:
            domain_ids.update(raw_stats[sd]["domain_ids"])
        canonical_stats[canonical] = {
            "paper_count_est": paper_count,
            "domain_count": len(domain_ids),
        }

    counts = [v["paper_count_est"] for k, v in canonical_stats.items() if v["paper_count_est"] > 0]
    median = float(np.median(counts)) if counts else 0.0
    total_domains = max(1, len(all_domains))
    stoplist = set()
    for canonical, stats in canonical_stats.items():
        count = stats["paper_count_est"]
        domain_ratio = stats["domain_count"] / total_domains
        name_lower = canonical.lower()
        if median > 0 and count > median * stoplist_ratio_max_median:
            stoplist.add(canonical)
            continue
        if domain_ratio >= stoplist_domain_ratio and count >= median:
            stoplist.add(canonical)
            continue
        if any(key in name_lower for key in GENERIC_KEYWORDS):
            stoplist.add(canonical)

    if emb is not None:
        canon_list = list(canonical_groups.keys())
        canon_vecs = {}
        for canon in canon_list:
            idxs = [raw_subdomains.index(sd) for sd in canonical_groups[canon]]
            centroid = np.mean(emb[idxs], axis=0)
            centroid = centroid / (np.linalg.norm(centroid) or 1.0)
            canon_vecs[canon] = centroid
    else:
        canon_vecs = {canon: _tokenize(canon) for canon in canonical_groups}

    for canonical, stats in list(canonical_stats.items()):
        if canonical in stoplist:
            continue
        if stats["paper_count_est"] >= min_papers:
            continue
        best_target = None
        best_sim = -1.0
        for target, tstats in canonical_stats.items():
            if target == canonical or target in stoplist:
                continue
            if tstats["paper_count_est"] < min_papers:
                continue
            if emb is not None:
                sim_val = float(np.dot(canon_vecs[canonical], canon_vecs[target]))
            else:
                sim_val = _jaccard(canon_vecs[canonical], canon_vecs[target])
            if sim_val > best_sim:
                best_sim = sim_val
                best_target = target
        if best_target and best_sim >= merge_min_sim:
            for sd, canon in list(mapping.items()):
                if canon == canonical:
                    mapping[sd] = best_target
            canonical_groups.pop(canonical, None)

    canonical_groups = defaultdict(list)
    for sd, canon in mapping.items():
        canonical_groups[canon].append(sd)

    canonical_stats = {}
    for canonical, group_sds in canonical_groups.items():
        paper_count = sum(raw_stats[sd]["paper_count_est"] for sd in group_sds)
        domain_ids = set()
        for sd in group_sds:
            domain_ids.update(raw_stats[sd]["domain_ids"])
        canonical_stats[canonical] = {
            "paper_count_est": paper_count,
            "domain_count": len(domain_ids),
        }

    active_counts = [v["paper_count_est"] for k, v in canonical_stats.items() if k not in stoplist and v["paper_count_est"] > 0]
    if active_counts:
        summary = {
            "min": int(min(active_counts)),
            "median": float(np.median(active_counts)),
            "max": int(max(active_counts)),
        }
    else:
        summary = {"min": 0, "median": 0, "max": 0}

    output = {
        "manifest": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "embedding_provider": EMBEDDING_PROVIDER,
            "embedding_api_url": EMBEDDING_API_URL,
            "embedding_model": EMBEDDING_MODEL,
            "nodes_pattern_sha256": sha256_file(patterns_path),
            "embedding_used": bool(embedding_used),
            "embedding_batches": int(embed_meta.get("batch_count") or 0),
            "embedding_failed": bool(embed_meta.get("failed_batch_idx") is not None),
            "embedding_error": embed_meta.get("error") or "",
            "algorithm": {
                "target_k_min": int(target_k_min),
                "target_k_max": int(target_k_max),
                "sim_threshold": float(threshold),
                "min_papers": int(min_papers),
                "merge_min_sim": float(merge_min_sim),
                "stoplist_ratio_max_median": float(stoplist_ratio_max_median),
            },
        },
        "canonical_subdomains": sorted(canonical_groups.keys()),
        "mapping": dict(sorted(mapping.items(), key=lambda x: x[0])),
        "stoplist": sorted(stoplist),
        "stats": {
            "raw_count": len(raw_subdomains),
            "canonical_count": len(canonical_groups),
            "stoplist_count": len(stoplist),
            "paper_count_summary": summary,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"taxonomy written: {output_path}")
    print(f"  raw={output['stats']['raw_count']} canonical={output['stats']['canonical_count']} stoplist={output['stats']['stoplist_count']}")
    print(f"  paper_count_summary={output['stats']['paper_count_summary']}")
    return output
