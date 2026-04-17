#!/usr/bin/env python3
"""
Analytics & Adaptation — 入口脚本
用法:
    python main.py                          # LLM 模式 (自动检测 API key)
    python main.py --model qwen-turbo       # 指定模型
    python main.py --rule-based             # 纯规则引擎, 不调 LLM
    python main.py --dry-run                # 只验证结构, 不调 LLM
    python main.py --output result.json     # 输出到指定文件
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from pipeline import (
    SignalSummary, DeckMetadata, KnowledgeEntry,
    LLMPipeline, RuleBasedEngine,
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  Mock Data (模拟 Student Agent Testing 输出)                 ║
# ╚══════════════════════════════════════════════════════════════╝

def get_mock_signal() -> SignalSummary:
    return SignalSummary(
        tested_deck_id="deck_ml_week3_v1",
        weak_topics=[
            "entropy intuition",
            "information gain calculation",
            "Gini impurity vs entropy",
        ],
        repeated_confusion_points=[
            "why lower entropy is better — students keep saying 'lower entropy = less information'",
            "difference between impurity measure and classification error rate",
            "when to stop splitting a decision tree",
            "log base 2 vs natural log in entropy formula",
        ],
        misconception_clusters=[
            "entropy equals randomness only — ignoring its role as uncertainty measure",
            "information gain is always positive — students don't consider edge cases",
            "Gini and entropy always rank features identically",
        ],
        missing_prerequisite_patterns=[
            "logarithm intuition missing — many students can't explain why log appears",
            "probability distribution basics weak — confusion about P(x) summing to 1",
        ],
        recommended_revision_targets=[
            "slide 4 — entropy formula introduction",
            "slide 7 — information gain worked example",
            "slide 11 — Gini vs entropy comparison table",
        ],
        evidence_refs=["run_001", "run_002", "run_003", "run_005", "run_008"],
    )


def get_mock_deck() -> DeckMetadata:
    return DeckMetadata(
        deck_id="deck_ml_week3_v1",
        slide_refs=[
            "slide_01_overview", "slide_02_what_is_decision_tree",
            "slide_03_splitting_criteria", "slide_04_entropy_formula",
            "slide_05_entropy_example", "slide_06_information_gain_def",
            "slide_07_ig_worked_example", "slide_08_gini_impurity_def",
            "slide_09_gini_example", "slide_10_entropy_vs_gini_theory",
            "slide_11_comparison_table", "slide_12_pruning_intro",
            "slide_13_summary",
        ],
        topic_scope=[
            "decision trees", "entropy", "information gain",
            "Gini impurity", "tree pruning basics",
        ],
        source_knowledge_ids=["kb_010", "kb_011", "kb_014", "kb_019", "kb_022"],
    )


def get_mock_knowledge() -> list[KnowledgeEntry]:
    return [
        KnowledgeEntry("kb_010", ["decision tree", "splitting"], "core concept", "Mitchell Ch.3"),
        KnowledgeEntry("kb_011", ["entropy", "information theory"], "core concept", "Mitchell Ch.3 + Shannon 1948"),
        KnowledgeEntry("kb_014", ["information gain"], "derived concept", "Mitchell Ch.3"),
        KnowledgeEntry("kb_019", ["Gini impurity"], "alternative measure", "Breiman et al. CART"),
        KnowledgeEntry("kb_022", ["pruning", "overfitting"], "extension concept", "Mitchell Ch.3"),
    ]


# ╔══════════════════════════════════════════════════════════════╗
# ║  Output Helpers                                              ║
# ╚══════════════════════════════════════════════════════════════╝

def print_section(title: str, data: dict):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")
    text = json.dumps(data, indent=2, ensure_ascii=False)
    lines = text.split("\n")
    print("\n".join(lines[:80]))
    if len(lines) > 80:
        print(f"  ... ({len(lines) - 80} more lines, see output file)")


def print_summary(results: dict, mode: str):
    print("\n" + "=" * 60)
    print(f"  PIPELINE EXECUTION SUMMARY  ({mode})")
    print("=" * 60)

    trace = results.get("trace", [])
    if trace:
        total_time = sum(t["elapsed_sec"] for t in trace)
        total_pt = sum(t["tokens"]["prompt"] for t in trace)
        total_ct = sum(t["tokens"]["completion"] for t in trace)
        print(f"\n  Model: {trace[0]['model']}")
        print(f"  Total time: {total_time:.1f}s across {len(trace)} steps")
        print(f"  Total tokens: {total_pt} prompt + {total_ct} completion")

    ranked = results.get("step4_score", results).get("ranked_issues",
             results.get("issues", []))
    if ranked:
        print(f"\n  Top Issues:")
        for i, iss in enumerate(ranked[:5]):
            sev = iss.get("severity", "?")
            score = iss.get("score", 0)
            desc = iss.get("description", iss.get("rationale", iss.get("topic", "")))[:80]
            print(f"    {i+1}. [{sev.upper():>8}] (score={score}) {desc}")

    recs = results.get("step5_recommend", results).get("recommendations", [])
    if recs:
        print(f"\n  Recommendations ({len(recs)} total):")
        for r in recs[:5]:
            action = r.get("action_type", r.get("action", "?"))
            slides = r.get("target_slides", r.get("target_slide_refs", []))
            print(f"    • {action} → {', '.join(slides[:3])}")

    proposals = results.get("step6_proposal", results).get("proposal_candidates", [])
    if proposals:
        print(f"\n  Proposal Candidates ({len(proposals)} total):")
        for p in proposals:
            pid = p.get("proposal_candidate_id", "?")
            action = p.get("recommended_action", "?")
            pri = p.get("suggested_priority", "?")
            print(f"    • {pid}: {action} (priority={pri})")

    hints = results.get("step6_proposal", {}).get("regenerate_hints", [])
    if hints:
        print(f"\n  Regenerate Hints ({len(hints)} total):")
        for h in hints[:3]:
            print(f"    • {h.get('target_slide', '?')}: {h.get('hint', '')[:80]}")

    print(f"\n{'='*60}\n")


# ╔══════════════════════════════════════════════════════════════╗
# ║  Main                                                        ║
# ╚══════════════════════════════════════════════════════════════╝

def main():
    parser = argparse.ArgumentParser(description="Analytics & Adaptation Pipeline")
    parser.add_argument("--model", default=None, help="LLM model name (auto-detect if omitted)")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    parser.add_argument("--rule-based", action="store_true", help="Use rule-based engine (no LLM)")
    parser.add_argument("--dry-run", action="store_true", help="Validate structure only")
    parser.add_argument("--quiet", action="store_true", help="Suppress step-by-step output")
    args = parser.parse_args()

    signal = get_mock_signal()
    deck = get_mock_deck()
    knowledge = get_mock_knowledge()

    mode = "rule-based" if args.rule_based else "LLM"

    print("╔══════════════════════════════════════════════════════════╗")
    print("║   Analytics & Adaptation — Agent Reasoning Pipeline     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Mode:    {mode}")
    print(f"  Deck:    {deck.deck_id}")
    print(f"  Topics:  {', '.join(deck.topic_scope)}")
    print(f"  Signals: {len(signal.evidence_refs)} evidence runs")
    print(f"  Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.dry_run:
        print("\n[DRY RUN] Structure OK. Skipping execution.")
        return

    # ── Run ──

    if args.rule_based:
        engine = RuleBasedEngine()
        results = engine.run(signal, deck)
    else:
        has_key = any(os.environ.get(k) for k in ("DASHSCOPE_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"))
        if not has_key:
            print("\nERROR: No API key found. Set one of:")
            print("  export DASHSCOPE_API_KEY='sk-...'   (阿里云百炼)")
            print("  export OPENAI_API_KEY='sk-...'      (OpenAI)")
            print("  export GEMINI_API_KEY='AIza...'     (Google Gemini)")
            print("\nOr use --rule-based for offline mode.")
            sys.exit(1)

        pipe = LLMPipeline(model=args.model, verbose=not args.quiet)
        print(f"  Provider: {pipe.provider}")
        print(f"  Model:    {pipe.model}")
        results = pipe.run(signal, deck, knowledge)

    # ── Print ──

    if not args.quiet and not args.rule_based:
        step_names = {
            "step1_ingest": "Step 1: Signal Ingestion",
            "step2_normalize": "Step 2: Issue Normalization",
            "step3_cluster": "Step 3: Issue Clustering",
            "step4_score": "Step 4: Severity Scoring",
            "step5_recommend": "Step 5: Adaptation Recommendations",
            "step6_proposal": "Step 6: Proposal Candidates",
        }
        for key, title in step_names.items():
            if key in results:
                print_section(title, results[key])

    print_summary(results, mode)

    # ── Save ──

    output_path = args.output or f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  Full output saved to: {output_path}")


if __name__ == "__main__":
    main()
