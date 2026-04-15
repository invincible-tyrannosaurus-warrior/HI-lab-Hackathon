"""
Build a canonical subdomain taxonomy for Path2 recall.

Usage:
  python Paper-KG-Pipeline/scripts/tools/build_subdomain_taxonomy.py
  python Paper-KG-Pipeline/scripts/tools/build_subdomain_taxonomy.py --patterns Paper-KG-Pipeline/output/nodes_pattern.json --output /tmp/subdomain_taxonomy.json
  python Paper-KG-Pipeline/scripts/tools/build_subdomain_taxonomy.py --target-k-min 40 --target-k-max 80
"""

import argparse
import sys
from pathlib import Path

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

from idea2paper.config import OUTPUT_DIR, PipelineConfig
from idea2paper.infra.subdomain_taxonomy import build_subdomain_taxonomy


def main():
    parser = argparse.ArgumentParser(description="Build canonical subdomain taxonomy (offline).")
    parser.add_argument("--patterns", type=str, default=str(OUTPUT_DIR / "nodes_pattern.json"))
    parser.add_argument("--papers", type=str, default=str(OUTPUT_DIR / "nodes_paper.json"))
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--target-k-min", type=int, default=40)
    parser.add_argument("--target-k-max", type=int, default=80)
    parser.add_argument("--sim-min", type=float, default=0.70)
    parser.add_argument("--sim-max", type=float, default=0.95)
    parser.add_argument("--min-papers", type=int, default=30)
    parser.add_argument("--merge-min-sim", type=float, default=0.75)
    parser.add_argument("--stoplist-ratio-max-median", type=float, default=10.0)
    parser.add_argument("--stoplist-domain-ratio", type=float, default=0.30)
    parser.add_argument("--max-exemplar-papers", type=int, default=5)
    parser.add_argument("--max-cooccur", type=int, default=5)
    parser.add_argument("--max-domains", type=int, default=3)
    args = parser.parse_args()

    patterns_path = Path(args.patterns)
    papers_path = Path(args.papers) if args.papers else None
    if not patterns_path.exists():
        raise FileNotFoundError(f"patterns not found: {patterns_path}")

    if args.output:
        output_path = Path(args.output)
    else:
        recall_dir = Path(PipelineConfig.RECALL_INDEX_DIR)
        output_path = recall_dir / "subdomain_taxonomy.json"

    build_subdomain_taxonomy(
        patterns_path=patterns_path,
        papers_path=papers_path,
        output_path=output_path,
        target_k_min=args.target_k_min,
        target_k_max=args.target_k_max,
        sim_min=args.sim_min,
        sim_max=args.sim_max,
        min_papers=args.min_papers,
        merge_min_sim=args.merge_min_sim,
        stoplist_ratio_max_median=args.stoplist_ratio_max_median,
        stoplist_domain_ratio=args.stoplist_domain_ratio,
        max_exemplar_papers=args.max_exemplar_papers,
        max_cooccur=args.max_cooccur,
        max_domains=args.max_domains,
    )


if __name__ == "__main__":
    main()
