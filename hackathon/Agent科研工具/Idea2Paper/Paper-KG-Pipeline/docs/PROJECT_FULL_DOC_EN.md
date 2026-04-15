# Idea2Paper Project Summary

> **Note**: Scripts have been categorized into `scripts/tools/` and `scripts/demos/`. Old paths (e.g., `scripts/build_entity_v3.py`) can still be run via compatibility shims.

## 📋 Project Overview

**Project Name**: Idea2Paper - Knowledge Graph Based Academic Paper Automatic Generation System

**Core Goal**: Automatically convert user research Ideas into paper Stories that meet top conference (ICLR) standards.

**Tech Stack**:
- Knowledge Graph: NetworkX
- Vector Retrieval: Embedding (Qwen3-Embedding-4B)
- Large Language Model: Qwen3-14B, Qwen2.5-7B-Instruct
- Data Source: ICLR 2025 Paper Dataset (8,285 papers)

---

## 1. System Architecture

### 1.1 Overall Flowchart

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        【Idea2Paper Full Process】                       │
└─────────────────────────────────────────────────────────────────────────┘

User Input Idea
    │
    ├──────────────────────────────────────────────────────────────────────┐
    │                  【Phase 1: Knowledge Graph Construction】             │
    │                  (One-time construction, reused later)               │
    ├──────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  1. Load ICLR Paper Data (8,285 papers)                               │
    │      ↓                                                                 │
    │  2. Build 4 Types of Nodes                                            │
    │      ├─ Idea Nodes (8,284)                                            │
    │      ├─ Pattern Nodes (124, LLM Enhanced)                             │
    │      ├─ Domain Nodes (98)                                             │
    │      └─ Paper Nodes (8,285)                                           │
    │      ↓                                                                 │
    │  3. Build Edge Relations (444,872 edges)                              │
    │      ├─ Basic Connection Edges (Paper→Idea/Pattern/Domain)            │
    │      └─ Recall Auxiliary Edges (Idea→Domain, Pattern→Domain)          │
    │      ↓                                                                 │
    │  4. Output Knowledge Graph                                            │
    │                                                                        │
    └──────────────────────────────────────────────────────────────────────┘
    │
    ├──────────────────────────────────────────────────────────────────────┐
    │                      【Phase 2: Three-Way Recall】                     │
    │                      (Per run, approx 27 seconds)                      │
    ├──────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  ┌─────────────┬─────────────┬─────────────┐                        │
    │  │  Path 1     │   Path 2    │   Path 3    │                        │
    │  │ Similar Idea│ Domain Rel. │ Similar Paper│                        │
    │  │ (Weight 0.4)│ (Weight 0.2)│ (Weight 0.4)│                        │
    │  └─────────────┴─────────────┴─────────────┘                        │
    │       │              │              │                                 │
    │       │              │              │                                 │
    │  Coarse: Jaccard Match Domain Coarse: Jaccard                        │
    │  Top-100         Top-5        Top-100                                │
    │       ↓              ↓              ↓                                 │
    │  Fine: Embedding Find Pattern Fine: Embedding                        │
    │  Top-10          works_well   Top-20                                 │
    │       ↓              ↓              ↓                                 │
    │  Get Pattern     Get Pattern   Get Pattern                           │
    │  Score           Score         Score                                 │
    │       │              │              │                                 │
    │       └──────────────┴──────────────┘                                │
    │                      ↓                                                │
    │              Weighted Fusion & Ranking                               │
    │                      ↓                                                │
    │              Top-10 Patterns                                         │
    │                                                                        │
    └──────────────────────────────────────────────────────────────────────┘
    │
    ├──────────────────────────────────────────────────────────────────────┐
    │                【Phase 3: Story Generation & Correction】              │
    │                (3-10 minutes)                                         │
    ├──────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  1. Pattern Multi-dimensional Classification                         │
    │      ├─ Stability                                                    │
    │      ├─ Novelty                                                      │
    │      └─ Cross-Domain                                                 │
    │      ↓                                                                 │
    │  2. Select Initial Pattern → Generate Draft Story                    │
    │      ↓                                                                 │
    │  3. Critic Multi-Role Review (Methodology/Novelty/Storyteller)       │
    │      ↓                                                                 │
    │  4. Judgment: Score >= 7.0?                                          │
    │      ├─【Yes】→ Enter Phase 4                                         │
    │      └─【No】→ Intelligent Correction                                 │
    │                 │                                                      │
    │                 ├─ Novelty Stagnated? → 【Novelty Mode】             │
    │                 │   ├─ Iterate Novelty Patterns                       │
    │                 │   ├─ Idea Fusion                                    │
    │                 │   ├─ Story Reflection                               │
    │                 │   ├─ Regenerate Story                               │
    │                 │   ├─ Critic Review                                  │
    │                 │   ├─ Score Drop? → Rollback                         │
    │                 │   └─ Fallback: Select Highest Score Version         │
    │                 │                                                      │
    │                 └─ Normal Correction → Inject Complementary Tricks    │
    │                     ├─ Lack Novelty → Tail Injection (Rank 5-10)     │
    │                     ├─ Lack Stability → Head Injection (Rank 1-3)    │
    │                     └─ Return to Step 2                               │
    │                                                                        │
    └──────────────────────────────────────────────────────────────────────┘
    │
    ├──────────────────────────────────────────────────────────────────────┐
    │                      【Phase 4: RAG Deduplication】                    │
    │                      (Approx 30 seconds)                              │
    ├──────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  1. Extract Key Methods → Retrieve Recent 3-Year Top Papers           │
    │      ↓                                                                 │
    │  2. Judgment: Similarity > 0.75?                                      │
    │      ├─【No】→ Output Final Story ✅                                  │
    │      └─【Yes】→ Collision! Pivot Avoidance                            │
    │                 ├─ Analyze Collision Points                           │
    │                 ├─ Generate Constraints (Disable Tech/Domain Shift)   │
    │                 └─ Return to Phase 3 Step 2                           │
    │                                                                        │
    └──────────────────────────────────────────────────────────────────────┘
    │
    ▼
Output Final Story (JSON format)
```

**Process Description**:
- **Phase 1**: Offline construction, run only once.
- **Phase 2**: Real-time recall, 13x speedup (27 seconds).
- **Phase 3**: Core generation, intelligent correction mechanism.
- **Phase 4**: Deduplication verification, avoiding collision.

### 1.2 Core Modules

| Level | Module | File/Script | Function |
|-------|--------|-------------|----------|
| **Data Layer** | KG Construction | `build_entity_v3.py`, `build_edges.py` | Build nodes and edges |
| **Recall Layer** | Three-Way Recall | `recall_system.py` | Retrieve relevant Patterns |
| **Generation Layer** | Pattern Selection | `pattern_selector.py` | Multi-dimensional Pattern classification |
| **Generation Layer** | Idea Fusion | `planner.py` | Fuse innovative Ideas |
| **Generation Layer** | Story Generation | `story_generator.py` | Generate Paper Story |
| **Generation Layer** | Story Reflection | `story_reflector.py` | Evaluate fusion quality |
| **Generation Layer** | Critic Review | `critic.py` | Multi-role review |
| **Generation Layer** | Intelligent Correction | `refinement.py` | Iterative optimization |
| **Generation Layer** | RAG Deduplication | `verifier.py` | Deduplication and avoidance |
| **Orchestration Layer** | Pipeline Management | `manager.py`, `idea2story_pipeline.py` | Process orchestration |

---

## 2. Knowledge Graph Construction

### 2.1 Data Scale

```
Knowledge Graph Statistics:
├─ Total Nodes: 16,791
│  ├─ Idea:    8,284 (100% coverage)
│  ├─ Pattern: 124 (Clustering generated)
│  ├─ Domain:  98 (Aggregation generated)
│  └─ Paper:   8,285
└─ Total Edges: 444,872
   ├─ Basic Connection Edges: ~25,000
   └─ Recall Auxiliary Edges: ~420,000
```

### 2.2 Node Definitions

**Idea Node**: Core innovation of the paper
```json
{
  "idea_id": "idea_0",
  "description": "Core idea description...",
  "base_problem": "Base problem...",
  "solution_pattern": "Solution...",
  "pattern_ids": ["pattern_9", ...]
}
```

**Pattern Node**: Writing tropes/Method templates
```json
{
  "pattern_id": "pattern_24",
  "name": "Reframing Graph Learning Scalability",
  "size": 331,
  "llm_enhanced_summary": {
    "representative_ideas": "Inductive summary...",
    "common_tricks": ["Trick1", "Trick2"]
  }
}
```

**Domain Node**: Research Field
```json
{
  "domain_id": "domain_0",
  "name": "Natural Language Processing",
  "paper_count": 1076,
  "sub_domains": ["Text Classification", ...]
}
```

**Paper Node**: Specific Paper
```json
{
  "paper_id": "RUzSobdYy0V",
  "title": "Quantifying and Mitigating...",
  "domain": "Fairness & Accountability",
  "idea": "Core idea...",
  "pattern_id": "pattern_9"
}
```

### 2.3 Edge Definitions

**Basic Connection Edges**:
- `Paper → Idea` (implements): Paper implements the Idea
- `Paper → Pattern` (uses_pattern): Paper uses the Pattern
- `Paper → Domain` (in_domain): Paper belongs to the Domain

**Recall Auxiliary Edges**:
- `Idea → Domain` (belongs_to): Idea belongs to Domain, weight=proportion
- `Pattern → Domain` (works_well_in): Pattern effect in Domain, weight=effectiveness
- `Idea → Paper` (similar_to_paper): Similarity weight (Real-time calculation in Path 3)

### 2.4 Execution

```bash
# 1. Build Nodes
python scripts/build_entity_v3.py
# Output: output/nodes_*.json (4 files)

# 2. Build Edges
python scripts/build_edges.py
# Output: output/edges.json, output/knowledge_graph_v2.gpickle
```

**Execution Time**: Node construction 15 mins (incl. LLM enhancement) + Edge construction 3 mins

---

## 3. Three-Way Recall System

### 3.1 Recall Strategy

| Path | Matching Object | Capture Dimension | Weight | Recall Count |
|------|----------------|-------------------|--------|--------------|
| **Path 1** | Idea Description | Core Idea Similarity | 0.4 | Top-10 Pattern |
| **Path 2** | Domain & Sub-domains | Domain Generalization | 0.2 | Top-5 Pattern |
| **Path 3** | Paper Title | Research Topic Similarity | 0.4 | Top-10 Pattern |

### 3.2 Two-Stage Recall Optimization

**Performance Comparison**:
```
Full Embedding: ~7 mins (8,284 API calls)
Two-Stage Recall: ~27 secs (100 API calls)
Speedup: 13x
```

**Process**:
```
Coarse: Jaccard Fast Filter Top-100 (Milliseconds)
    ↓
Fine: Embedding Precise Sort Top-10/20 (~27 secs)
```

### 3.3 Similarity Calculation

**Jaccard Similarity** (Coarse):
```python
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

**Embedding Similarity** (Fine):
```python
Cosine(A, B) = dot(emb_A, emb_B) / (norm(emb_A) * norm(emb_B))
```

### 3.4 Execution

```bash
# Standalone Run
python scripts/simple_recall_demo.py "Your Research Idea"

# Use as Class
from recall_system import RecallSystem
system = RecallSystem()
results = system.recall(user_idea, verbose=True)
```

**Output**: Top-10 Pattern list, each containing (pattern_id, pattern_info, score)

---

## 4. Idea2Story Pipeline

### 4.1 Core Mechanisms

#### (1) Pattern Multi-dimensional Classification

**Goal**: Ensure Pattern diversity

**Dimensions**:
- **Stability**: Rank Top-3 + Cluster Size ≥ 15
- **Novelty**: Cluster Size < 10
- **Cross-Domain**: From Path 2/3 + Domain different
- 
#### (2) Idea Fusion

**Goal**: Organic fusion at the conceptual level, not technical piling.

**Process**:
```
Original Idea + New Pattern → LLM Generates Fused Idea
    ↓
Fused Idea contains:
  - fused_core_idea: Core idea after fusion
  - conceptual_bridge: Conceptual bridge
  - reframed_problem: Reframed problem
  - innovation_angle: Unique innovation point
```

**Example**:
```
Original Idea: Use LLM for data augmentation
New Pattern: Curriculum Learning
Fused Idea: Difficulty-adaptive curriculum learning framework based on LLM generation
```

#### (3) Story Reflection

**Goal**: Evaluate fusion quality, ensure conceptual unity.

**Scoring**:
```
fusion_quality = 0.4 × Coherence + 0.4 × Fusion Richness + 0.2 × Fusion Idea Bonus
```

**Threshold**: `fusion_quality >= 0.65` considered successful fusion.

#### (4) Critic Multi-Role Review

**Roles**:
- **Reviewer A** (Methodology): Technical Rationality
- **Reviewer B** (Novelty): Innovation
- **Reviewer C** (Storyteller): Narrative Completeness

**Pass Standard**: Average Score >= 7.0

#### (5) Intelligent Correction

**Novelty Mode**:
- **Trigger**: Novelty score stagnation (≤ Last round + 0.5)
- **Process**: Iterate all Novelty Patterns, each goes through Fusion→Reflection→Generation→Critic
- **Fallback**: Select highest score version

**Score Degradation Rollback**:
- **Trigger**: Any dimension score drop > 0.1
- **Process**: Restore Story + Mark Failure + Remove Tricks + Continue Iteration

**Normal Correction**:
- **Tail Injection**: Lack Novelty → Inject Rank 5-10 Tail Patterns
- **Head Injection**: Lack Stability → Inject Rank 1-3 Mature Patterns

#### (6) RAG Deduplication & Avoidance

**Deduplication**: Retrieve recent 3-year top papers, similarity > 0.75 considered collision.

**Avoidance**: Pivot strategy generates constraints (Domain shift, set limits, etc.), regenerate Story.

### 4.2 Execution

```bash
python scripts/idea2story_pipeline.py "Your Research Idea"
```

**Output**:
```
output/
├── final_story.json          # Final Paper Story
├── pipeline_result.json      # Complete Process Result
└── log.json                  # Detailed Log
```

**Execution Time**: 3-10 minutes (depends on iteration count)

---

## 5. Parameter Configuration Overview

### 5.1 Knowledge Graph Construction

```python
# scripts/build_entity_v3.py

# Data Source Paths
DATA_DIR = PROJECT_ROOT / "data" / "ICLR_25"
ASSIGNMENTS_FILE = DATA_DIR / "assignments.jsonl"
CLUSTER_LIBRARY_FILE = DATA_DIR / "cluster_library_sorted.jsonl"
PATTERN_DETAILS_FILE = DATA_DIR / "iclr_patterns_full.jsonl"

# LLM API Config (legacy KG script example; use unified LLM config)
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_PROVIDER = "openai_compatible_chat"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
```

### 5.2 Recall System

```python
# scripts/recall_system.py

class RecallConfig:
    # Path Weights
    PATH1_WEIGHT = 0.4  # Similar Idea
    PATH2_WEIGHT = 0.2  # Domain Related
    PATH3_WEIGHT = 0.4  # Similar Paper

    # Recall Counts
    PATH1_TOP_K_IDEAS = 10
    PATH1_FINAL_TOP_K = 10
    PATH2_TOP_K_DOMAINS = 5
    PATH2_FINAL_TOP_K = 5
    PATH3_TOP_K_PAPERS = 20
    PATH3_FINAL_TOP_K = 10
    FINAL_TOP_K = 10

    # Two-Stage Recall
    USE_EMBEDDING = True
    TWO_STAGE_RECALL = True
    COARSE_RECALL_SIZE = 100
    FINE_RECALL_SIZE = 20
```

### 5.3 Pipeline

```python
# scripts/pipeline/config.py

class PipelineConfig:
    # Pattern Selection
    SELECT_PATTERN_COUNT = 3
    CONSERVATIVE_RANK_RANGE = (0, 2)
    INNOVATIVE_CLUSTER_SIZE_THRESHOLD = 10

    # Critic Thresholds
    PASS_SCORE = 7.0
    MAX_REFINE_ITERATIONS = 3

    # Novelty Mode
    NOVELTY_MODE_MAX_PATTERNS = 10
    NOVELTY_SCORE_THRESHOLD = 6.0
    NOVELTY_STAGNATION_DELTA = 0.5

    # Reflection
    FUSION_QUALITY_THRESHOLD = 0.65

    # Rollback
    SCORE_DEGRADATION_THRESHOLD = 0.1

    # RAG Deduplication
    COLLISION_THRESHOLD = 0.75

    # Refinement Strategy
    TAIL_INJECTION_RANK_RANGE = (4, 9)
    HEAD_INJECTION_RANK_RANGE = (0, 2)
    HEAD_INJECTION_CLUSTER_THRESHOLD = 15

# LLM Config
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_PROVIDER = "openai_compatible_chat"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
```

---

## 6. Full Run Workflow

### 6.1 Environment Preparation

```bash
# 1. Clone Project
cd /Users/gaoge/code/mycode/Idea2Paper/Paper-KG-Pipeline

# 2. Install Dependencies
pip install -r requirements.txt

# 3. Set Environment Variables
export LLM_API_KEY="your_api_key_here"
export LLM_PROVIDER="openai_compatible_chat"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o-mini"
```

### 6.2 One-Time Construction

```bash
# Build Knowledge Graph (Run only once)
python scripts/build_entity_v3.py   # 15 mins
python scripts/build_edges.py       # 3 mins
```

### 6.3 Use Pipeline

```bash
# Generate Paper Story
python scripts/idea2story_pipeline.py "Your Research Idea Description"

# Example
python scripts/idea2story_pipeline.py "Optimizing LLM inference efficiency using Reinforcement Learning"
```

### 6.4 View Results

```bash
# View Final Story
cat output/final_story.json

# View Full Pipeline Result
cat output/pipeline_result.json

# View Detailed Log
cat output/log.json | jq '.'
```

---

## 7. Core Innovations

### 7.1 Knowledge Graph Level

✅ **LLM Enhanced Pattern**: Generate inductive summaries for each Pattern cluster.
✅ **Dual-Layer Description**: Concrete examples + Global summary, both learnable and understandable.
✅ **Quality-Oriented Edge Weights**: Calculate edge weights based on paper quality and Pattern effectiveness.

### 7.2 Recall Level

✅ **Three-Way Complementary Recall**: Capture relevance from Idea, Domain, and Paper dimensions.
✅ **Two-Stage Optimization**: Jaccard Coarse + Embedding Fine, 13x speedup.
✅ **Real-Time Path 3**: Avoid pre-building redundant edges, ensure complementarity.

### 7.3 Generation Level

✅ **Idea Fusion**: Organic unity at conceptual level, not technical piling.
✅ **Story Reflection**: Reflect on fusion quality, evaluate conceptual unity.
✅ **Novelty Priority Mode**: Auto-upgrade when stagnated, systematically enhance innovation.
✅ **Intelligent Rollback**: Avoid invalid corrections, improve iteration efficiency.
✅ **Fallback Strategy**: Ensure output quality, select highest score version.

---

## 8. System Advantages

### 8.1 High Automation

- ✅ Fully automated process, no human intervention.
- ✅ Intelligent decision mechanisms (Novelty Mode, Rollback, Fallback).
- ✅ Adaptive parameter adjustment.

### 8.2 Multi-Layer Quality Assurance

1. **Pattern Layer**: High-quality Pattern library enhanced by LLM.
2. **Recall Layer**: Three-way complementary recall, comprehensive coverage.
3. **Fusion Layer**: Idea Fusion ensures conceptual unity.
4. **Reflection Layer**: Story Reflection evaluates fusion quality.
5. **Review Layer**: Three-role Critic comprehensive assessment.
6. **Deduplication Layer**: RAG avoids collision.

### 8.3 Fully Optimized Efficiency

- ✅ Two-stage recall speedup 13x (7 mins → 27 secs).
- ✅ Intelligent rollback avoids invalid iterations.
- ✅ Pattern failure marking avoids repeated attempts.
- ✅ LLM response caching reduces API calls.

### 8.4 Strong Scalability

- ✅ Modular design, easy to add new features.
- ✅ Support incremental updates to Knowledge Graph.
- ✅ Adaptable to other conference data sources.
- ✅ Can add new recall paths.

---

## 9. Current Limitations & Improvements

### 9.1 Data Level

**Current Limitations**:
- ⚠️ Domain granularity too coarse, 98 Domains cover 8,285 papers.

**Improvements**:
- 📌 Introduce Domain hierarchy (Main Domain → Sub Domain).
- 📌 Use sub_domains for fine-grained matching.
- 📌 Extend to more conferences' Review data.

### 9.2 Recall Level

**Current Limitations**:
- ⚠️ Path 2 Domain matching based on keywords, may be inaccurate.
- ⚠️ Recall speed still has room for optimization (27 secs).

**Improvements**:
- 📌 Use Embedding to calculate semantic similarity between Idea and Domain.
- 📌 Introduce Vector Database (Faiss/Milvus), speed up to 1-3 secs.
- 📌 Pre-compute and cache all Embeddings.

### 9.3 Generation Level

**Current Limitations**:
- ⚠️ Fusion quality score depends on LLM, may be unstable.
- ⚠️ Novelty Mode traversing 10 Patterns may take long.

**Improvements**:
- 📌 Introduce learnable fusion quality scoring model.
- 📌 Optimize Pattern selection order based on historical data.
- 📌 Parallel generation of multiple Story candidates.

### 9.4 Review Level

**Current Limitations**:
- ⚠️ Critic score depends on LLM, may fluctuate.
- ⚠️ No user feedback mechanism.

**Improvements**:
- 📌 Collect real review data, train dedicated Critic model.
- 📌 Introduce user feedback, online learning to adjust weights.
- 📌 A/B test effects of different strategies.

---

## 10. Document Index

### 10.1 Core Documents

| Document | Path | Content |
|----------|------|---------|
| **Project Summary** | `docs/00_PROJECT_OVERVIEW.md` | This document, overall overview |
| **KG Construction** | `docs/01_KG_CONSTRUCTION.md` | Data sources, nodes, edges, execution |
| **Recall System** | `docs/02_RECALL_SYSTEM.md` | Three-way recall, similarity calc, config |
| **Idea2Story Pipeline** | `docs/03_IDEA2STORY_PIPELINE.md` | Pattern selection, Fusion, Reflection, Critic |

### 10.2 Auxiliary Documents

| Document | Path | Content |
|----------|------|---------|
| **Edge Types** | `docs/EDGE_TYPES.md` | Detailed edge definitions and weight calc |
| **Pattern Scoring** | `docs/PATTERN_SCORING_EXPLAINED.md` | Pattern score calculation logic |
| **Two-Stage Recall** | `docs/TWO_STAGE_RECALL_OPTIMIZATION.md` | Recall performance optimization details |
| **Data Format** | `docs/Data_Format_Comparison.md` | V2 vs V3 data format changes |

### 10.3 Historical Documents (Archived)

Documents recording system evolution history, core content integrated into above 4 main docs:
- `NOVELTY_MODE_FIX.md`
- `REFLECTION_REGENERATION_FIX.md`
- `WORKFLOW_CORRECTION_2025-01-25.md`
- `REFINE_SYSTEM_UPGRADE.md`
- `RECALL_USAGE_V3.md`
- etc.

---

## 11. Code Structure

```
Paper-KG-Pipeline/
├── data/                           # Data Sources
│   └── ICLR_25/
│       ├── assignments.jsonl
│       ├── cluster_library_sorted.jsonl
│       └── iclr_patterns_full.jsonl
│
├── output/                         # Output Files
│   ├── nodes_*.json               # 4 Types of Nodes
│   ├── edges.json                 # Edge Data
│   ├── knowledge_graph_v2.gpickle # NetworkX Graph
│   ├── final_story.json           # Final Story
│   └── pipeline_result.json       # Pipeline Result
│
├── scripts/                        # Core Scripts
│   ├── build_entity_v3.py         # Build Nodes
│   ├── build_edges.py             # Build Edges
│   ├── recall_system.py           # Recall System (Class)
│   ├── simple_recall_demo.py      # Recall Demo
│   ├── idea2story_pipeline.py     # Pipeline Entry
│   │
│   └── pipeline/                   # Pipeline Modules
│       ├── config.py              # Config Params
│       ├── manager.py             # Orchestration
│       ├── pattern_selector.py    # Pattern Classification
│       ├── planner.py             # Idea Fusion
│       ├── story_generator.py     # Story Generation
│       ├── story_reflector.py     # Story Reflection
│       ├── critic.py              # Critic Review
│       ├── refinement.py          # Intelligent Correction
│       ├── verifier.py            # RAG Deduplication
│       └── utils.py               # Utils
│
├── docs/                           # Documentation
│   ├── 00_PROJECT_OVERVIEW.md     # Project Summary (This Doc)
│   ├── 01_KG_CONSTRUCTION.md      # KG Construction
│   ├── 02_RECALL_SYSTEM.md        # Recall System
│   └── 03_IDEA2STORY_PIPELINE.md  # Idea2Story Pipeline
│
└── requirements.txt                # Dependencies
```

---

## 12. Key Metrics

### 12.1 Data Scale

```
Knowledge Graph:
  - Nodes: 16,791
  - Edges: 444,872
  - Patterns: 124 (124 LLM enhanced)
  - Idea Coverage: 100% (8,284/8,285)
```

### 12.2 Performance Metrics

```
Recall Speed:
  - Full Embedding: ~7 mins
  - Two-Stage Recall: ~27 secs
  - Speedup: 13x

Pipeline Execution Time:
  - Fastest: 3 mins (First pass)
  - Typical: 5-7 mins (2-3 rounds correction)
  - Slowest: 10 mins (Novelty Mode)
```

### 12.3 Quality Metrics

```
Critic Review:
  - Pass Standard: Avg Score >= 7.0
  - Dimensions: Methodology, Novelty, Storyteller
  - Novelty Mode Boost: 0.5-1.5 points

Fusion Quality:
  - Threshold: >= 0.65
  - Typical Value: 0.68-0.75
  - Dimensions: Coherence (40%) + Richness (40%) + Bonus (20%)
```

---

## 13. Usage Suggestions

### 13.1 Quick Start

```bash
# 1. First Run (Build KG)
python scripts/build_entity_v3.py
python scripts/build_edges.py

# 2. Generate Paper Story
python scripts/idea2story_pipeline.py "Your Research Idea"

# 3. View Results
cat output/final_story.json
```

### 13.2 Parameter Tuning

**Boost Novelty**:
```python
# Increase Novelty Mode Attempts
PipelineConfig.NOVELTY_MODE_MAX_PATTERNS = 15  # Default 10

# Increase Novelty Weight
RecallConfig.PATH1_WEIGHT = 0.5  # Default 0.4, increase Similar Idea weight
```

**Boost Stability**:
```python
# Lower Fusion Quality Threshold
PipelineConfig.FUSION_QUALITY_THRESHOLD = 0.60  # Default 0.65

# Increase Head Pattern Weight
RecallConfig.PATH3_WEIGHT = 0.5  # Default 0.4, increase High Quality Paper weight
```

**Accelerate Recall**:
```python
# Reduce Recall Count
RecallConfig.PATH1_TOP_K_IDEAS = 5   # Default 10
RecallConfig.PATH3_TOP_K_PAPERS = 10 # Default 20
```

### 13.3 Monitor Key Events

```bash
# Novelty Mode Activation
grep "Activate [Novelty Mode]" output/log.json

# Fusion Quality Score
grep "Fusion Quality Score" output/log.json

# Rollback Event
grep "【ROLLBACK TRIGGERED】" output/log.json

# Final Pass
grep "🎉 Critic Review Passed" output/log.json
```

---

## 14. Troubleshooting

### 14.1 Environment Issues

**Q: API key invalid**
```bash
# Check Env Var
echo $LLM_API_KEY

# Set Env Var
export LLM_API_KEY="your_key_here"
```

**Q: Missing Dependencies**
```bash
# Reinstall Dependencies
pip install -r requirements.txt --upgrade
```

### 14.2 Data Issues

**Q: Node files not found**
```bash
# Rebuild KG
python scripts/build_entity_v3.py
python scripts/build_edges.py
```

**Q: Recall result empty**
```bash
# Check if KG built successfully
ls -lh output/nodes_*.json
ls -lh output/knowledge_graph_v2.gpickle
```

### 14.3 Pipeline Issues

**Q: Fusion quality always below threshold**
```python
# Lower threshold or improve Fusion Prompt
PipelineConfig.FUSION_QUALITY_THRESHOLD = 0.60
```

**Q: Novelty Mode traversed all but failed**
```
# Check fallback strategy in log
grep "Fallback Strategy" output/log.json
# System automatically selects highest score version
```

---

## 15. Summary

### 15.1 Core Achievements

✅ **Complete Knowledge Graph System**: 16,791 nodes, 444,872 edges.
✅ **Efficient Recall System**: 13x speedup, second-level response.
✅ **Intelligent Generation Pipeline**: Fusion+Reflection+Critic+Intelligent Correction.
✅ **Quality Assurance Mechanism**: Multi-level check, auto rollback, fallback strategy.
✅ **Complete Documentation System**: 4 core docs covering Construction, Recall, Generation.

### 15.2 Technical Highlights

✅ **Conceptual Fusion**: Idea Fusion achieves organic unity, not technical piling.
✅ **Fusion Quality Reflection**: Story Reflector evaluates fusion effect.
✅ **Novelty Priority**: Auto upgrade to Novelty Mode when stagnated.
✅ **Intelligent Rollback**: Avoid invalid correction, improve efficiency.
✅ **LLM Enhanced Pattern**: Dual-layer description improves usability.

### 15.3 Application Value

✅ **Research Assist**: Help researchers quickly generate paper frameworks.
✅ **Innovation Exploration**: Discover new research directions via Pattern fusion.
✅ **Writing Guidance**: Provide structured paper organization suggestions.
✅ **Literature Survey**: Quickly locate related work based on Knowledge Graph.

### 15.4 Future Outlook

📌 **Data Extension**: Integrate more conference data (CVPR, NeurIPS, ACL, etc.).
📌 **Model Optimization**: Train dedicated Fusion and Critic models.
📌 **User Interaction**: Introduce user feedback, online learning optimization.
📌 **Multi-modal Support**: Integrate charts, formulas, code, etc.

---

## 16. Acknowledgement

Thanks to the ICLR 2025 Paper Dataset support, and all LLM API providers.

---

**Generated**: 2026-01-25
**Version**: V1.0
**Author**: Idea2Paper Team

**Contact**: Refer to core documents for detailed technical support

<br/>
<br/>
<br/>

# Knowledge Graph Construction Document

> **Note**: Scripts have been categorized into `scripts/tools/` and `scripts/demos/`. Old paths (e.g., `scripts/build_entity_v3.py`) can still be run via compatibility shims.

## 📋 Overview

This document details the construction process of the Knowledge Graph in the Idea2Paper project, including data sources, node/edge definitions, construction flow, parameter configuration, and execution methods.

---

## 1. Data Sources

### 1.1 Input Files

| File | Path | Description | Volume |
|------|------|-------------|--------|
| **assignments.jsonl** | `data/ICLR_25/assignments.jsonl` | Paper to Pattern assignments | 8,285 records |
| **cluster_library_sorted.jsonl** | `data/ICLR_25/cluster_library_sorted.jsonl` | Pattern Cluster info | 124 records |
| **iclr_patterns_full.jsonl** | `data/ICLR_25/iclr_patterns_full.jsonl` | Pattern detailed attributes (Full English) | 8,310 records |

### 1.2 Data Structure Examples

**assignments.jsonl**:
```json
{
  "paper_id": "RUzSobdYy0V",
  "paper_title": "Quantifying and Mitigating...",
  "global_pattern_id": "g0",
  "pattern_id": "p0",
  "domain": "Fairness & Accountability",
  "sub_domains": ["Label Noise", "Disparity Metrics"],
  "cluster_id": 9,
  "cluster_prob": 0.384
}
```

**cluster_library_sorted.jsonl**:
```json
{
  "cluster_id": 24,
  "cluster_name": "Reframing Graph Learning Scalability",
  "size": 331,
  "coherence": {
    "centroid_mean": 0.668,
    "pairwise_sample_mean": 0.461
  },
  "exemplars": [...]
}
```

---

## 2. Node Definitions

### 2.1 Node Types Overview

| Node Type | Count | Main Data Source | Function |
|-----------|-------|------------------|----------|
| **Idea** | 8,284 | `iclr_patterns_full.jsonl` | Core innovation of the paper |
| **Pattern** | 124 | `cluster_library_sorted.jsonl` | Writing trope/Method template |
| **Domain** | 98 | `assignments.jsonl`(Aggregated) | Research Field |
| **Paper** | 8,285 | `assignments.jsonl` + pattern details | Specific Paper |

### 2.2 Pattern Node

**Data Source**: `cluster_library_sorted.jsonl` + LLM Enhancement

**Key Fields**:
```json
{
  "pattern_id": "pattern_24",
  "cluster_id": 24,
  "name": "Reframing Graph Learning Scalability",
  "size": 331,
  "domain": "Machine Learning",
  "sub_domains": ["Graph Neural Networks", ...],
  "coherence": {...},

  "summary": {
    "representative_ideas": ["idea1", "idea2", ...],
    "common_problems": ["problem1", ...],
    "solution_approaches": ["solution1", ...],
    "story": ["story1", ...]
  },

  "llm_enhanced_summary": {
    "representative_ideas": "Inductive summary (single sentence)...",
    "common_problems": "Inductive summary (single sentence)...",
    "solution_approaches": "Inductive summary (single sentence)...",
    "story": "Inductive summary (single sentence)..."
  },

  "llm_enhanced": true,
  "exemplar_count": 6
}
```

**Construction Logic**:
```python
def _build_pattern_nodes(clusters):
    for cluster in clusters:
        if cluster_id == -1:
            continue  # Skip unassigned

        pattern_node = {
            'pattern_id': f"pattern_{cluster_id}",
            'name': cluster['cluster_name'],
            'size': cluster['size'],
            'coherence': cluster['coherence'],
            'summary': extract_from_exemplars(cluster)
        }
```

### 2.3 Idea Node

**Data Source**: `iclr_patterns_full.jsonl`

**Key Fields**:
```json
{
  "idea_id": "idea_0",
  "description": "Analyzing the impact of label noise on group disparity metrics...",
  "base_problem": "In group disparity metric evaluation...",
  "solution_pattern": "Propose a method to estimate...",
  "story": "Extending label noise issue from model performance impact to...",
  "application": "Fairness auditing in high-stakes decision systems...",
  "domain": "Fairness & Accountability",
  "sub_domains": ["Label Noise", ...],
  "source_paper_ids": ["RUzSobdYy0V"],
  "pattern_ids": ["pattern_9"]
}
```

**Deduplication Strategy**: First 16 chars of MD5 hash

**Construction Logic**:
```python
def _build_idea_nodes(pattern_details):
    for paper_id, details in pattern_details.items():
        idea_text = details['idea']
        idea_hash = hashlib.md5(idea_text.encode()).hexdigest()[:16]

        if idea_hash not in self.idea_map:
            idea_node = {
                'idea_id': f"idea_{len(self.idea_nodes)}",
                'description': idea_text,
                ...
            }
```

### 2.4 Domain Node

**Data Source**: `assignments.jsonl` (Aggregated)

**Key Fields**:
```json
{
  "domain_id": "domain_0",
  "name": "Fairness & Accountability",
  "paper_count": 69,
  "sub_domains": ["Label Noise", "Bias Mitigation", ...],
  "related_pattern_ids": ["pattern_9", "pattern_15", ...],
  "sample_paper_ids": ["RUzSobdYy0V", ...]
}
```

**Construction Logic**:
```python
def _build_domain_nodes(assignments):
    domain_stats = defaultdict(lambda: {
        'paper_count': 0,
        'sub_domains': set(),
        'related_patterns': set()
    })

    for assignment in assignments:
        domain = assignment['domain']
        domain_stats[domain]['paper_count'] += 1
        domain_stats[domain]['sub_domains'].update(assignment['sub_domains'])
```

### 2.5 Paper Node

**Data Source**: `assignments.jsonl` + `iclr_patterns_full.jsonl`

**Key Fields**:
```json
{
  "paper_id": "RUzSobdYy0V",
  "title": "Quantifying and Mitigating...",
  "global_pattern_id": "g0",
  "cluster_id": 9,
  "cluster_prob": 0.384,
  "domain": "Fairness & Accountability",
  "sub_domains": [...],
  "idea": "Core idea description (string)",
  "pattern_details": {...},
  "pattern_id": "pattern_9",
  "idea_id": "idea_0",
  "domain_id": "domain_0"
}
```

---

## 3. Edge Definitions

### 3.1 Edge Classification

| Edge Type | Usage | Count |
|-----------|-------|-------|
| **Basic Connection Edge** | Establish basic entity relations | ~25,000 |
| **Recall Auxiliary Edge** | Support three-way recall strategy | ~420,000 |

### 3.2 Basic Connection Edges

#### (1) Paper → Idea (`implements`)
```python
G.add_edge(
    paper['paper_id'],
    paper['idea_id'],
    relation='implements'
)
```

#### (2) Paper → Pattern (`uses_pattern`)
```python
G.add_edge(
    paper['paper_id'],
    paper['pattern_id'],
    relation='uses_pattern',
    quality=paper_quality  # [0, 1]
)
```

**Quality Score Calculation**:
```python
def _get_paper_quality(paper):
    reviews = paper.get('reviews', [])
    if reviews:
        scores = [r['overall_score'] for r in reviews]
        avg_score = np.mean(scores)
        return (avg_score - 1) / 9  # Normalize to [0,1]
    return 0.5  # Default value (V3 currently has no review data)
```

#### (3) Paper → Domain (`in_domain`)
```python
G.add_edge(
    paper['paper_id'],
    paper['domain_id'],
    relation='in_domain'
)
```

### 3.3 Recall Auxiliary Edges

#### (1) Idea → Domain (`belongs_to`)

**Weight Definition**: Proportion of Idea-related Papers in that Domain

```python
for idea in ideas:
    domain_counts = defaultdict(int)
    for paper_id in idea['source_paper_ids']:
        paper = paper_id_to_paper[paper_id]
        domain_counts[paper['domain_id']] += 1

    total_papers = len(idea['source_paper_ids'])
    for domain_id, count in domain_counts.items():
        weight = count / total_papers

        G.add_edge(
            idea['idea_id'],
            domain_id,
            relation='belongs_to',
            weight=weight,  # [0, 1]
            paper_count=count
        )
```

#### (2) Pattern → Domain (`works_well_in`)

**Weight Definition**:
- `effectiveness`: Effect gain of Pattern in that Domain (relative to baseline) [-1, 1]
- `confidence`: Confidence based on sample size [0, 1]

```python
for pattern in patterns:
    domain_papers = defaultdict(list)
    for paper_id in pattern['sample_paper_ids']:
        paper = paper_id_to_paper[paper_id]
        domain_papers[paper['domain_id']].append(paper)

    for domain_id, papers in domain_papers.items():
        qualities = [_get_paper_quality(p) for p in papers]
        avg_quality = np.mean(qualities)

        all_domain_papers = get_papers_in_domain(domain_id)
        domain_baseline = np.mean([_get_paper_quality(p) for p in all_domain_papers])

        effectiveness = avg_quality - domain_baseline  # [-1, 1]
        frequency = len(papers)
        confidence = min(frequency / 20, 1.0)  # [0, 1]

        G.add_edge(
            pattern['pattern_id'],
            domain_id,
            relation='works_well_in',
            frequency=frequency,
            effectiveness=effectiveness,
            confidence=confidence
        )
```

#### (3) Idea → Paper (`similar_to_paper`)

**Note**: This edge is **pre-built but not directly used** in V3.1. Recall Path 3 calculates user Idea vs Paper Title similarity **in real-time**.

---

## 4. Construction Process

### 4.1 Overall Process

```
┌─────────────────────────────────────────────────────────────┐
│               【Knowledge Graph Construction Process】         │
└─────────────────────────────────────────────────────────────┘

【Phase 1: Load Data】 (Approx 1 sec)
    │
    ├─ Load assignments.jsonl (8,285 papers)
    ├─ Load cluster_library_sorted.jsonl (124 Pattern Clusters)
    └─ Load iclr_patterns_full.jsonl (8,310 Pattern details)
    │
    ▼

【Phase 2: Build Nodes】 (Approx 2 mins)
    │
    ├─ 1. Pattern Nodes (124)
    │     ├─ Extract basic info from cluster_library
    │     ├─ Extract ideas/problems/solutions/stories from exemplars
    │     └─ Generate preliminary Pattern nodes
    │     ↓
    ├─ 2. LLM Enhanced Pattern (124, approx 10 mins)
    │     ├─ Call LLM for each Pattern
    │     ├─ Generate inductive summary (4 dimensions)
    │     │   ├─ representative_ideas
    │     │   ├─ common_problems
    │     │   ├─ solution_approaches
    │     │   └─ story
    │     └─ Add llm_enhanced_summary field
    │     ↓
    ├─ 3. Idea Nodes (8,284)
    │     ├─ Extract idea fields from pattern_details
    │     ├─ MD5 hash deduplication
    │     └─ Extract base_problem/solution_pattern/story/application
    │     ↓
    ├─ 4. Domain Nodes (98)
    │     ├─ Aggregate domain info from assignments
    │     ├─ Collect sub_domains
    │     ├─ Count paper_count
    │     └─ Associate related_pattern_ids
    │     ↓
    └─ 5. Paper Nodes (8,285)
          ├─ Merge assignments and pattern_details
          ├─ Extract title/domain/sub_domains/idea
          └─ Keep cluster_id/global_pattern_id
    │
    ▼

【Phase 3: Establish Links】 (Approx 1 sec)
    │
    ├─ Paper → Pattern Link
    │    └─ Map cluster_id to pattern_id
    │        Coverage: 5,981/8,285 (72.2%)
    │
    ├─ Paper → Idea Link
    │    └─ Map via idea text MD5 hash
    │        Coverage: 8,284/8,285 (100%)
    │
    ├─ Paper → Domain Link
    │    └─ Map domain name to domain_id
    │        Coverage: 8,285/8,285 (100%)
    │
    └─ Idea → Pattern Link
         └─ Link via Paper intermediary
             ├─ Collect all Papers related to each Idea
             ├─ Extract pattern_id of these Papers
             └─ Fill Idea.pattern_ids field
             Avg 0.7 Patterns per Idea
    │
    ▼

【Phase 4: Save Nodes】 (Approx 1 sec)
    │
    ├─ Output nodes_idea.json (8,284)
    ├─ Output nodes_pattern.json (124)
    ├─ Output nodes_domain.json (98)
    ├─ Output nodes_paper.json (8,285)
    └─ Output knowledge_graph_stats.json
    │
    ▼

【Phase 5: Build Edges】 (Approx 2-3 mins)
    │
    ├─ Basic Connection Edges
    │    ├─ Paper → Idea (implements) 8,284
    │    ├─ Paper → Pattern (uses_pattern) 5,981
    │    └─ Paper → Domain (in_domain) 8,285
    │
    ├─ Recall Auxiliary Edges - Path 2
    │    ├─ Idea → Domain (belongs_to)
    │    │   └─ Weight: Proportion of Idea-related Papers in Domain
    │    │
    │    └─ Pattern → Domain (works_well_in)
    │        ├─ effectiveness: Pattern effect gain in Domain
    │        └─ confidence: Confidence based on sample size
    │
    └─ Recall Auxiliary Edges - Path 3
         └─ (Real-time calculation, no pre-built edges)
    │
    ▼

【Phase 6: Save Graph】 (Approx 1 sec)
    │
    ├─ Output edges.json
    └─ Output knowledge_graph_v2.gpickle
    │
    ▼

✅ Construction Complete
   ├─ Total Nodes: 16,791
   ├─ Total Edges: 444,872
   └─ Total Time: Approx 15-18 mins
```

### 4.2 Key Steps

#### Step 1: Load Data
```python
assignments = _load_assignments()      # 8,285
clusters = _load_clusters()            # 124
pattern_details = _load_pattern_details()  # 8,310
```

#### Step 2: Build Nodes
```python
_build_pattern_nodes(clusters)         # 124 Patterns
_enhance_patterns_with_llm(clusters)   # LLM Enhancement
_build_idea_nodes(pattern_details)     # 8,284 Ideas
_build_domain_nodes(assignments)       # 98 Domains
_build_paper_nodes(assignments, pattern_details)  # 8,285 Papers
```

#### Step 3: Establish Links
```python
_link_paper_to_pattern(assignments)    # Paper → Pattern
_link_paper_to_idea()                  # Paper → Idea
_link_paper_to_domain()                # Paper → Domain
_link_idea_to_pattern()                # Idea → Pattern (via Paper)
```

#### Step 4: Build Edges
```python
_build_paper_edges()                   # Basic Connection Edges
_build_idea_belongs_to_domain_edges()  # Recall Edge - Path 2
_build_pattern_works_well_in_domain_edges()
_build_idea_similar_to_paper_edges()   # Recall Edge - Path 3
```

#### Step 5: Save Results
```python
_save_nodes()  # Save 4 node JSONs
_save_edges()  # Save edges.json
_save_graph()  # Save knowledge_graph_v2.gpickle
```

---

## 5. LLM Enhancement Mechanism

### 5.1 Enhancement Goal

Generate inductive summaries for each Pattern cluster, preserving concrete examples while providing a global overview.

### 5.2 Prompt Design

```python
def _build_llm_prompt_for_pattern(pattern_node, exemplars):
    prompt = f"""
You are an academic research expert. Based on the Pattern information from the following {len(exemplars)} papers,
generate an inductive summary for Pattern Cluster "{pattern_node['name']}".

【Paper Pattern Info】
{format_exemplars(exemplars)}

【Task】
Generate inductive summaries for 4 dimensions (1 sentence each, 80-120 chars):
1. representative_ideas: Representative research ideas
2. common_problems: Common problems solved
3. solution_approaches: Solution characteristics
4. story: Research narrative framework

Return in JSON format.
"""
    return prompt
```

### 5.3 API Config

```python
# Legacy KG script example; use unified LLM config
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_PROVIDER = "openai_compatible_chat"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
```

---

## 6. Parameter Configuration

### 6.1 Path Config

```python
# Data Input Paths
DATA_DIR = PROJECT_ROOT / "data" / "ICLR_25"
ASSIGNMENTS_FILE = DATA_DIR / "assignments.jsonl"
CLUSTER_LIBRARY_FILE = DATA_DIR / "cluster_library_sorted.jsonl"
PATTERN_DETAILS_FILE = DATA_DIR / "iclr_patterns_full.jsonl"

# Output Paths
OUTPUT_DIR = PROJECT_ROOT / "output"
NODES_IDEA = OUTPUT_DIR / "nodes_idea.json"
NODES_PATTERN = OUTPUT_DIR / "nodes_pattern.json"
NODES_DOMAIN = OUTPUT_DIR / "nodes_domain.json"
NODES_PAPER = OUTPUT_DIR / "nodes_paper.json"
EDGES_FILE = OUTPUT_DIR / "edges.json"
GRAPH_FILE = OUTPUT_DIR / "knowledge_graph_v2.gpickle"
```

### 6.2 LLM Config

```python
# API Key (Env Var)
LLM_API_KEY = os.getenv("LLM_API_KEY")

# Provider
LLM_PROVIDER = "openai_compatible_chat"

# Base URL (or use LLM_API_URL override)
LLM_BASE_URL = "https://api.openai.com/v1"

# Model Selection
LLM_MODEL = "gpt-4o-mini"
```

### 6.3 Edge Build Config

```python
# Pattern-Domain Edge Weight Calculation
BASELINE_SAMPLE_SIZE = 20  # Sample size threshold for confidence 1.0

# Paper Quality Score
# Prefer review_stats.avg_score (based on multi-dimensional Review scores)
# Default 0.5 when no review data
```

---

## 7. Execution Methods

### 7.1 Environment Preparation

**Install Dependencies**:
```bash
cd /Users/gaoge/code/mycode/Idea2Paper/Paper-KG-Pipeline
pip install -r requirements.txt
```

**Set Environment Variables**:
```bash
export LLM_API_KEY="your_api_key_here"
```

### 7.2 Build Nodes

**Command**:
```bash
python scripts/build_entity_v3.py
```

**Output**:
```
output/
├── nodes_idea.json           # 8,284 Idea nodes
├── nodes_pattern.json        # 124 Pattern nodes
├── nodes_domain.json         # 98 Domain nodes
├── nodes_paper.json          # 8,285 Paper nodes
└── knowledge_graph_stats.json # Stats info
```

**Execution Time**: Approx 10-15 mins (incl. LLM enhancement)

### 7.3 Build Edges

**Command**:
```bash
python scripts/build_edges.py
```

**Output**:
```
output/
├── edges.json                # Edge data (JSON format)
└── knowledge_graph_v2.gpickle # Full graph (NetworkX format)
```

**Execution Time**: Approx 2-3 mins

### 7.4 Verify Graph

**Python Interactive Verification**:
```python
import json
import pickle

# Load Nodes
with open('output/nodes_pattern.json') as f:
    patterns = json.load(f)
print(f"Pattern Count: {len(patterns)}")

# Load Graph
with open('output/knowledge_graph_v2.gpickle', 'rb') as f:
    G = pickle.load(f)
print(f"Nodes: {G.number_of_nodes()}")
print(f"Edges: {G.number_of_edges()}")
```

---

## 8. Output Statistics

### 8.1 Node Statistics

```
Total Nodes:  9,411
  - Idea:      8,284 (100% coverage)
  - Pattern:   124
  - Domain:    98
  - Paper:     8,285
```

### 8.2 Edge Statistics

```
【Basic Connection Edges】
  Paper→Idea:      8,284 (100%)
  Paper→Pattern:   5,981 (72.2% coverage)
  Paper→Domain:    8,285 (100%)

【Recall Edges - Path 2】
  Idea→Domain:     ~15,000
  Pattern→Domain:  ~3,500

【Recall Edges - Path 3】
  (Real-time calculation, no pre-built edges)

Total Edges: 444,872
```

### 8.3 Data Quality

```
✅ Idea Coverage: 100% (8,284/8,285)
✅ Pattern Coverage: 72.2% (Based on cluster assignment)
✅ LLM Enhancement: 124/124 Pattern nodes
✅ Clustering Quality: Quantifiable (coherence metric)
```

---

## 9. Troubleshooting

### 9.1 Common Issues

**Q: LLM API Call Failed**
```
Error: Connection timeout / API key invalid
Solution:
1. Check network connection
2. Verify LLM_API_KEY env var
3. Check API quota
```

**Q: Memory Error**
```
Error: MemoryError
Solution:
1. Reduce exemplar count for LLM enhancement (Default 20→10)
2. Process Pattern nodes in batches
```

**Q: Output File Exists**
```
Behavior: Auto overwrite
Suggestion: Backup important output/ files before running
```

### 9.2 Log Viewing

Construction process outputs detailed logs:
```
🚀 Start Building Knowledge Graph V3 (ICLR Data Source)
【Step 1】Load Data
  ✅ Loaded 8285 paper assignments
【Step 2】Build Nodes
  ✓ Created 124 Pattern nodes
  ✓ LLM Enhancement: 124/124 Complete
【Step 3】Establish Node Links
  ✓ Established 8284 Idea->Pattern links
【Step 4】Save Nodes
【Step 5】Statistics
✅ Knowledge Graph Construction Complete!
```

---

## 10. Extensions & Optimizations

### 10.1 Data Source Extension

**Add New Conference Data**:
1. Prepare JSONL files consistent with ICLR format
2. Modify `DATA_DIR` path
3. Re-run `build_entity_v3.py`

### 10.2 Review Data Extension

**Current Status**: Paper nodes integrated ICLR 2025 review data, containing multi-dimensional scores.

**Data Structure**:
```json
{
  "paper_id": "xxx",
  "review_ids": ["review_1", "review_2", ...],
  "review_stats": {
    "review_count": 4,
    "avg_score": 0.656,
    "highest_score": 0.790,
    "lowest_score": 0.575
  }
}
```

**Extension Plan**: Add more conferences' review data to enrich Knowledge Graph.

### 10.3 Performance Optimization

**LLM Enhancement Acceleration**:
```python
# Parallel Process Patterns
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(_enhance_single_pattern, p)
               for p in pattern_nodes]
```

---

## 11. Summary

### Core Achievements

✅ Successfully built Knowledge Graph based on ICLR data source
✅ Achieved 100% Idea coverage
✅ Introduced LLM enhancement, generating inductive summaries for each Pattern
✅ Retained clustering quality metric (coherence)
✅ Modular code, easy to extend

### Technical Features

✅ **LLM Integration**: Use a unified LLM provider to enhance Pattern descriptions
✅ **Prompt Engineering**: Structured Prompt design
✅ **Fault Tolerance**: Automatic JSON parsing and repair
✅ **Dual-Layer Description**: Concrete examples + Global summary

### Scalability

✅ Support incremental updates
✅ Adaptable to other conference data sources
✅ Provide complete node foundation for Recall System

---

**Generated**: 2026-01-25
**Version**: V3.1
**Author**: Idea2Paper Team

<br/>
<br/>
<br/>

# Three-Way Recall System Document

> **Note**: Scripts have been categorized into `scripts/tools/` and `scripts/demos/`. Old paths (e.g., `scripts/simple_recall_demo.py`) can still be run via compatibility shims.

## 📋 Overview

This document details the three-way recall system based on Knowledge Graph, including recall strategies, similarity calculation, multi-way fusion, parameter configuration, and execution methods.

---

## 1. System Architecture

### 1.1 Core Goal

**Input**: User Research Idea Description (Text)
**Output**: Top-10 Most Relevant Research Patterns (Writing tropes/Method templates)

### 1.2 Technical Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                  【Three-Way Recall System Architecture】          │
└──────────────────────────────────────────────────────────────────┘

User Input Idea (Text Description)
    │
    ├────────────────────────────────────────────────────────────┐
    │                  Three-Way Parallel Recall (~27s)          │
    ├────────────────────────────────────────────────────────────┤
    │                                                              │
    │  ┌──────────────┬──────────────┬──────────────┐           │
    │  │   Path 1     │    Path 2    │    Path 3    │           │
    │  │ Similar Idea │ Domain Rel.  │ Similar Paper│           │
    │  │ (Weight 0.4) │ (Weight 0.2) │ (Weight 0.4) │           │
    │  └──────────────┴──────────────┴──────────────┘           │
    │        │              │              │                      │
    │        │              │              │                      │
    │  ┌─────▼──────┐  ┌───▼────┐  ┌──────▼─────┐              │
    │  │【Coarse】  │  │【Domain】│  │【Coarse】  │              │
    │  │ Jaccard    │  │ Match    │  │ Jaccard    │              │
    │  └────────────┘  └──────────┘  └────────────┘              │
    │        │              │              │                      │
    │  Traverse 8,284  Use Top-1      Traverse 8,285             │
    │  Idea Descs      Idea's Domain  Paper Titles               │
    │  BoW Model       Keyword Match  BoW Model                  │
    │  Fast Filter     Check Graph    Fast Filter                │
    │        │              │              │                      │
    │  Top-100         Top-5          Top-100                    │
    │  Candidate Ideas Domain         Candidate Papers           │
    │        │              │              │                      │
    │  ┌─────▼──────┐  ┌───▼────┐  ┌──────▼─────┐              │
    │  │【Fine】    │  │【Pattern】│  │【Fine】    │              │
    │  │ Embedding  │  │ Recall   │  │ Embedding  │              │
    │  └────────────┘  └──────────┘  └────────────┘              │
    │        │              │              │                      │
    │  100 API Calls   Check works_   100 API Calls              │
    │  Semantic Sim    well_in Edge   Semantic Sim               │
    │  Precise Rank    Effect Weight  × Paper Quality            │
    │        │              │              │                      │
    │  Top-10          Top-K          Top-20                     │
    │  Similar Ideas   Patterns       Similar Papers             │
    │        │              │              │                      │
    │  ┌─────▼──────┐  ┌───▼────┐  ┌──────▼─────┐              │
    │  │【Pattern】 │  │【Pattern】│  │【Pattern】 │              │
    │  │  Extract   │  │  Score   │  │  Extract   │              │
    │  └────────────┘  └──────────┘  └────────────┘              │
    │        │              │              │                      │
    │  Direct Get Idea Domain Rel.    Check Paper→Pattern         │
    │  .pattern_ids    × effectiveness uses_pattern Edge          │
    │  Weight by Sim   × confidence   Sim × Quality Weight        │
    │        │              │              │                      │
    │  Pattern Score   Pattern Score  Pattern Score               │
    │  Dict            Dict           Dict                        │
    │        │              │              │                      │
    │    ┌───┴──────────────┼──────────────┼────────────────────┐
    │    │                  │              │
    │    └──────────────────┴──────────────┘
    │                       │
    │                       ▼
    │            ┌──────────────────────┐
    │            │   【Multi-Way Fusion】│
    │            └──────────────────────┘
    │                       │
    │             score = path1 × 0.4
    │                   + path2 × 0.2
    │                   + path3 × 0.4
    │                       │
    │                       ▼
    │               Sort by Fused Score
    │                       │
    │                       ▼
    │            ┌──────────────────────┐
    │            │   Top-10 Patterns    │
    │            │   Return to User     │
    │            └──────────────────────┘
```

**Architecture Description**:
- **Horizontal**: Three-way parallel execution, independent.
- **Vertical**: Two-stage optimization (Coarse → Fine) within each path.
- **Fusion**: Weighted sum, ensuring diversity.

### 1.3 Data Scale

```
Knowledge Graph Statistics:
  - Idea Nodes:    8,284
  - Pattern Nodes: 124
  - Domain Nodes:  98
  - Paper Nodes:   8,285
  - Total Edges:   444,872
```

---

## 2. Three-Way Recall Strategy

### 2.1 Design Philosophy

Three-way recall captures user needs from different dimensions, avoiding duplication and information redundancy:

| Path | Matching Object | Capture Dimension | Weight | Typical Scenario |
|------|-----------------|-------------------|--------|------------------|
| **Path 1** | Idea Description | Core Idea/Concept Similarity | 0.4 | User description aligns with historical success core ideas |
| **Path 2** | Domain & Sub-domains | Domain Generalization | 0.2 | User Idea belongs to a domain, recalling valid patterns in that domain |
| **Path 3** | Paper Title | Research Topic/Specific Problem Similarity | 0.4 | User wants to solve a specific problem similar to some paper titles |

**Complementarity**:
- **Path 1 vs Path 3**: Path 1 focuses on "Idea Essence", Path 3 focuses on "Research Direction".
- **Path 2 Generalization**: Even if User Idea is novel, as long as it belongs to a mature domain, it can recall effective Patterns in that domain.

---

## 3. Path 1: Similar Idea Recall

### 3.1 Recall Process

```
User Idea (Text)
    ↓ [Coarse] Jaccard Fast Filter
Candidate Ideas (Top-100)
    ↓ [Fine] Embedding Re-rank
Similar Ideas (Top-10)
    ↓ Direct Get idea.pattern_ids
Pattern Set
    ↓ Weighted Accumulation by Similarity
Top-10 Patterns (Score Dict)
```

### 3.2 Two-Stage Recall Optimization

**Why Two-Stage?**
- Full Embedding Retrieval: 8,284 API calls, takes **~7 mins** ❌
- Two-Stage Recall: 100 API calls, takes **~10 secs** ✅ (40x speedup)

**Coarse Stage (Jaccard)**:
```python
def compute_jaccard_similarity(text1, text2):
    """Calculate Jaccard Similarity (BoW Model)"""
    # Tokenize
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())

    # Jaccard = Intersection / Union
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0

# Coarse: Fast Filter Top-100
coarse_similarities = []
for idea in ideas:  # 8,284
    sim = compute_jaccard_similarity(user_idea, idea['description'])
    if sim > 0:
        coarse_similarities.append((idea_id, sim))

coarse_similarities.sort(reverse=True)
candidates = coarse_similarities[:100]  # Coarse Top-100
```

**Fine Stage (Embedding)**:
```python
def compute_embedding_similarity(text1, text2):
    """Use Qwen3-Embedding-4B for semantic similarity"""
    # Get Embedding
    emb1 = get_embedding(text1)  # API Call
    emb2 = get_embedding(text2)  # API Call

    # Cosine Similarity
    return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

# Fine: Re-rank candidates using Embedding
fine_similarities = []
for idea_id, _ in candidates:  # 100
    idea = idea_id_to_idea[idea_id]
    sim = compute_embedding_similarity(user_idea, idea['description'])
    if sim > 0:
        fine_similarities.append((idea_id, sim))

fine_similarities.sort(reverse=True)
top_ideas = fine_similarities[:10]  # Fine Top-10
```

### 3.3 Pattern Score Calculation

```python
pattern_scores = defaultdict(float)

for idea_id, similarity in top_10_ideas:
    idea = idea_id_to_idea[idea_id]

    # V3: Directly get pattern_ids from Idea node
    for pattern_id in idea['pattern_ids']:
        # Score = Similarity (Accumulate if multiple Ideas use same Pattern)
        pattern_scores[pattern_id] += similarity

# Sort and keep Top-10
sorted_patterns = sorted(pattern_scores.items(), reverse=True)
top_patterns = dict(sorted_patterns[:10])
```

**Example**:
```
User Idea: "Text classification using Transformer"

Similar Idea_1 (Sim 0.8) → [pattern_5, pattern_10]
Similar Idea_2 (Sim 0.7) → [pattern_5, pattern_20]
Similar Idea_3 (Sim 0.6) → [pattern_10]

Path 1 Scores:
  pattern_5:  0.8 + 0.7 = 1.5
  pattern_10: 0.8 + 0.6 = 1.4
  pattern_20: 0.7 = 0.7
```

---

## 4. Path 2: Domain Related Recall

### 4.1 Recall Process

```
User Idea (Text)
    ↓ Keyword Match Domain name
Relevant Domains (Top-5)
    ↓ Reverse Lookup Pattern→Domain Edges
Patterns working well in Domain
    ↓ Weighted by effectiveness & confidence
Top-5 Patterns (Score Dict)
```

### 4.2 Domain Matching Logic

**Method 1: Keyword Match** (Priority):
```python
def match_domains(user_idea, domains):
    domain_scores = []
    user_tokens = set(user_idea.lower().split())

    for domain in domains:
        domain_name = domain['name']
        domain_tokens = set(domain_name.lower().split())

        # Vocabulary Overlap
        match_score = len(user_tokens & domain_tokens) / max(len(user_tokens), 1)

        if match_score > 0:
            domain_scores.append((domain['domain_id'], match_score))

    domain_scores.sort(reverse=True)
    return domain_scores[:5]  # Top-5
```

**Method 2: Via Similar Idea's Domain** (Fallback):
```python
if not domain_scores:
    # Find most similar Idea
    similarities = [(idea, compute_similarity(user_idea, idea['description']))
                    for idea in ideas]
    top_idea = max(similarities, key=lambda x: x[1])[0]

    # Get Idea's Domain (via belongs_to edge)
    for successor in G.successors(top_idea['idea_id']):
        edge_data = G[top_idea['idea_id']][successor]
        if edge_data['relation'] == 'belongs_to':
            domain_id = successor
            weight = edge_data['weight']
            domain_scores.append((domain_id, weight))
```

### 4.3 Pattern Score Calculation

```python
pattern_scores = defaultdict(float)

for domain_id, domain_weight in top_5_domains:
    # Reverse Lookup: Which Patterns work well in this Domain?
    for predecessor in G.predecessors(domain_id):
        edge_data = G[predecessor][domain_id]

        if edge_data['relation'] == 'works_well_in':
            pattern_id = predecessor
            effectiveness = edge_data['effectiveness']  # [-1, 1]
            confidence = edge_data['confidence']  # [0, 1]

            # Score = Domain Relevance × Effect × Confidence
            # max(effectiveness, 0.1) prevents negative
            score = domain_weight * max(effectiveness, 0.1) * confidence
            pattern_scores[pattern_id] += score

# Sort and keep Top-5 (Auxiliary Channel)
sorted_patterns = sorted(pattern_scores.items(), reverse=True)
top_patterns = dict(sorted_patterns[:5])
```

**Edge Weight Explanation**:
- `effectiveness`: Pattern effect gain in Domain (relative to baseline) [-1, 1]
  - Positive: Pattern works better than average in Domain
  - Negative: Pattern works worse than average in Domain
- `confidence`: Confidence based on sample size [0, 1]
  - Sample size ≥ 20 reaches 1.0 confidence

---

## 5. Path 3: Similar Paper Recall

### 5.1 Recall Process

```
User Idea (Text)
    ↓ [Coarse] Jaccard Filter (Based on Paper Title)
Candidate Papers (Top-100)
    ↓ [Fine] Embedding Re-rank (Based on Paper Title)
Similar Papers (Top-20)
    ↓ Find Paper→Pattern Edge
Pattern Set
    ↓ Weighted by similarity × quality
Top-10 Patterns (Score Dict)
```

### 5.2 Design Philosophy

**Complementarity of Path 1 vs Path 3**:
- **Path 1**: Use Idea Description for similarity → Capture **Core Idea/Concept** similarity
- **Path 3**: Use Paper Title for similarity → Capture **Research Topic/Specific Problem** similarity

### 5.3 Two-Stage Recall Optimization

**Coarse Stage (Jaccard)**:
```python
coarse_similarities = []
for paper in papers:  # 8,285
    paper_title = paper['title']  # Use Paper Title
    sim = compute_jaccard_similarity(user_idea, paper_title)

    if sim > 0.05:  # Lower threshold to keep more candidates
        coarse_similarities.append((paper_id, sim))

coarse_similarities.sort(reverse=True)
candidates = coarse_similarities[:100]  # Coarse Top-100
```

**Fine Stage (Embedding)**:
```python
fine_similarities = []
for paper_id, _ in candidates:  # 100
    paper = paper_id_to_paper[paper_id]
    paper_title = paper['title']  # Use Paper Title

    sim = compute_embedding_similarity(user_idea, paper_title)

    if sim > 0.1:  # Filter low similarity
        # Get Paper Quality (Prefer review_stats.avg_score)
        quality = _get_paper_quality(paper)  # [0, 1]
        combined_weight = sim * quality  # Combine Sim and Quality
        fine_similarities.append((paper_id, sim, quality, combined_weight))

fine_similarities.sort(key=lambda x: x[3], reverse=True)
top_papers = fine_similarities[:20]  # Fine Top-20
```

### 5.4 Pattern Score Calculation

```python
pattern_scores = defaultdict(float)

for paper_id, similarity, paper_quality, combined_weight in top_20_papers:
    # Find Pattern used by Paper from Graph
    for successor in G.successors(paper_id):
        edge_data = G[paper_id][successor]

        if edge_data['relation'] == 'uses_pattern':
            pattern_id = successor
            pattern_quality = edge_data['quality']  # Paper Review Quality

            # Score = (Sim × Paper Quality) × Pattern Quality
            # paper_quality comes from review_stats.avg_score
            score = combined_weight * pattern_quality
            pattern_scores[pattern_id] += score

# Sort and keep Top-10
sorted_patterns = sorted(pattern_scores.items(), reverse=True)
top_patterns = dict(sorted_patterns[:10])
```

---

## 6. Multi-Way Fusion & Fine Ranking

### 6.1 Fusion Strategy

```python
# Path Weight Config
PATH1_WEIGHT = 0.4  # Similar Idea Recall (Important)
PATH2_WEIGHT = 0.2  # Domain Related Recall (Auxiliary)
PATH3_WEIGHT = 0.4  # Similar Paper Recall (Important)
```

**Weight Rationale**:
- **Path 1 (0.4)**: Directly use historical success experience, most reliable.
- **Path 2 (0.2)**: Strong domain generalization, but coarser granularity, serves as auxiliary.
- **Path 3 (0.4)**: Fine-grained matching, quality-oriented, equally important as Path 1.

### 6.2 Aggregate Scores by Pattern

```python
# Collect all Patterns from three paths
all_patterns = set(path1_scores.keys()) | set(path2_scores.keys()) | set(path3_scores.keys())

# Calculate Final Score for each Pattern
final_scores = {}
for pattern_id in all_patterns:
    score1 = path1_scores.get(pattern_id, 0.0) * PATH1_WEIGHT
    score2 = path2_scores.get(pattern_id, 0.0) * PATH2_WEIGHT
    score3 = path3_scores.get(pattern_id, 0.0) * PATH3_WEIGHT

    final_scores[pattern_id] = score1 + score2 + score3

# Sort and Return Top-10
ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
top_10 = ranked[:10]
```

### 6.3 Result Example

```
================================================================================
📊 Recall Results Top-10
================================================================================

【Rank 1】 pattern_111
  Name: Reframing Zero-Shot Generalization
  Final Score: 0.6571
  - Path 1 (Similar Idea):   0.5257 (80.0%)
  - Path 2 (Domain Rel.):    0.0000 (0.0%)
  - Path 3 (Similar Paper):  0.1314 (20.0%)
  Cluster Size: 22 papers

【Rank 2】 pattern_110
  Name: Reframing Few Shot Learning Robustness
  Final Score: 0.4990
  - Path 1 (Similar Idea):   0.3036 (60.8%)
  - Path 2 (Domain Rel.):    0.0000 (0.0%)
  - Path 3 (Similar Paper):  0.1954 (39.2%)
  Cluster Size: 24 papers
```

---

## 7. Parameter Configuration

### 7.1 Recall Parameters

```python
class RecallConfig:
    """Recall System Config"""
    # Path 1: Similar Idea Recall
    PATH1_TOP_K_IDEAS = 10         # Recall Top-K most similar Ideas
    PATH1_FINAL_TOP_K = 10         # Final keep Top-K Patterns

    # Path 2: Domain Related Recall
    PATH2_TOP_K_DOMAINS = 5        # Recall Top-K most relevant Domains
    PATH2_FINAL_TOP_K = 5          # Final keep Top-K Patterns

    # Path 3: Similar Paper Recall
    PATH3_TOP_K_PAPERS = 20        # Recall Top-K most similar Papers
    PATH3_FINAL_TOP_K = 10         # Final keep Top-K Patterns

    # Path Weights
    PATH1_WEIGHT = 0.4             # Path 1 Weight (Similar Idea - Important)
    PATH2_WEIGHT = 0.2             # Path 2 Weight (Domain Related - Auxiliary)
    PATH3_WEIGHT = 0.4             # Path 3 Weight (Similar Paper - Important)

    # Final Recall Top-K
    FINAL_TOP_K = 10

    # Similarity Calculation Method
    USE_EMBEDDING = True           # Use embedding (Recommended)

    # Two-Stage Recall Optimization
    TWO_STAGE_RECALL = True        # Enable two-stage recall (Significant speedup)
    COARSE_RECALL_SIZE = 100       # Coarse recall size (Jaccard)
    FINE_RECALL_SIZE = 20          # Fine rank size (Embedding)
```

### 7.2 Embedding API Config

```python
# API Endpoint
EMBEDDING_API_URL = "https://api.openai.com/v1/embeddings"

# Model Selection
EMBEDDING_MODEL = "text-embedding-3-large"

# API Key
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
```

---

## 8. Execution Methods

### 8.1 Standalone Run

**Command**:
```bash
cd /Users/gaoge/code/mycode/Idea2Paper/Paper-KG-Pipeline
python scripts/simple_recall_demo.py "Your Research Idea Description"
```

**Example**:
```bash
python scripts/simple_recall_demo.py "Task completion using distillation for Transformer cross-domain text classification"
```

**Output**:
```
🎯 Three-Way Recall System Demo
================================================================================
【User Idea】
Task completion using distillation for Transformer cross-domain text classification

🔍 [Path 1] Similar Idea Recall...
  [Coarse] Using Jaccard fast filter Top-100...
  [Fine] Using Embedding re-rank Top-10...
  ✓ Coarse 8284 -> Fine 100 -> Final 10

🌍 [Path 2] Domain Relevance Recall...
  Found 3 relevant Domains
  ✓ Recalled 34 Patterns, kept Top-5

📄 [Path 3] Similar Paper Recall...
  [Coarse] Using Jaccard fast filter Top-100...
  [Fine] Using Embedding re-rank Top-20...
  ✓ Coarse 171 -> Fine 100 -> Final 20

🔗 Fusing Three-Way Recall Results...

📊 Recall Results Top-10
【Rank 1】 pattern_11 - Model Compression and Knowledge Distillation
  Final Score: 0.1312
  ...
```

### 8.2 Use as Class

```python
from recall_system import RecallSystem

# Initialize Recall System
system = RecallSystem()

# Execute Recall
user_idea = "Your Research Idea"
results = system.recall(user_idea, verbose=True)

# Process Results
for pattern_id, pattern_info, score in results:
    print(f"Pattern: {pattern_info['name']}, Score: {score:.4f}")
```

### 8.3 Integrate into Pipeline

```python
# Use in idea2story_pipeline.py
from recall_system import RecallSystem

recall_system = RecallSystem()
recall_results = recall_system.recall(user_idea, verbose=True)

# recall_results format: [(pattern_id, pattern_info, score), ...]
```

---

## 9. Performance Optimization

### 9.1 Recall Speed Comparison

| Mode | Description | Time | API Calls |
|------|-------------|------|-----------|
| **Full Embedding** | Embedding calc for all 8,284 Ideas | ~7 mins | 8,284 |
| **Two-Stage Recall** | Jaccard Coarse 100 → Embedding Fine 10 | ~27 secs | 100 |
| **Speedup** | - | **13x** | - |

### 9.2 Further Optimization Plans

**Plan 1: Embedding Cache**:
```python
# Precompute all Idea and Paper Embeddings
idea_embeddings = precompute_all_embeddings(ideas)
paper_embeddings = precompute_all_embeddings(papers)

# Use cache during recall
user_embedding = get_embedding(user_idea)
similarities = [cosine_similarity(user_embedding, idea_emb)
                for idea_emb in idea_embeddings]
```

**Plan 2: Vector Database**:
```python
# Use Faiss/Milvus Vector DB
import faiss

# Build Index
index = faiss.IndexFlatIP(embedding_dim)
index.add(idea_embeddings)

# ANN Search
D, I = index.search(user_embedding, k=10)  # Top-10
```
Expected Speedup: **~1-3 secs**

**Plan 3: GPU Acceleration**:
```python
# Batch calculate Embedding similarity on GPU
import torch

user_emb = torch.tensor(user_embedding).cuda()
all_embs = torch.tensor(idea_embeddings).cuda()

similarities = torch.matmul(user_emb, all_embs.T)
```

---

## 10. Troubleshooting

### 10.1 Common Issues

**Q: Recall results are all high-score Patterns**
```
Cause: Path 2 weight too high, causing popular Patterns to have inflated scores
Solution: Reduce PATH2_WEIGHT (0.2 → 0.1)
```

**Q: Embedding API Timeout**
```
Cause: Network issue or API rate limit
Solution:
1. Add retry mechanism
2. Add request delay (time.sleep(0.1))
3. Use cache to avoid repeated requests
```

**Q: Slow Recall Speed**
```
Cause: TWO_STAGE_RECALL=False or USE_EMBEDDING=False
Solution: Ensure two-stage recall and Embedding are enabled in config
```

**Q: Path 1 Score is 0**
```
Cause: User Idea has extremely low similarity with all historical Ideas
Check: Print similarity distribution, confirm if there are matching Ideas
```

### 10.2 Debug Mode

```python
# Enable verbose log
results = system.recall(user_idea, verbose=True)

# View intermediate results
print(f"Path 1 Pattern Count: {len(path1_scores)}")
print(f"Path 2 Pattern Count: {len(path2_scores)}")
print(f"Path 3 Pattern Count: {len(path3_scores)}")

# View similarity distribution
for idea_id, sim in top_ideas:
    print(f"Idea {idea_id}: {sim:.3f}")
```

---

## 11. Evaluation Metrics

### 11.1 Recall Quality Evaluation

**Relevance Evaluation**:
```python
# Manually annotate Top-10 results relevance (0-1)
relevance_scores = []
for pattern in top_10:
    score = manual_annotation(pattern, user_idea)
    relevance_scores.append(score)

avg_relevance = np.mean(relevance_scores)
print(f"Average Relevance: {avg_relevance:.2f}")
```

**Diversity Evaluation**:
```python
# Calculate cluster size distribution of Top-10 Patterns
cluster_sizes = [p['size'] for p in top_10_patterns]
diversity_score = np.std(cluster_sizes) / np.mean(cluster_sizes)
print(f"Diversity Score (CV): {diversity_score:.2f}")
```

### 11.2 Performance Monitoring

```python
import time

start = time.time()
results = system.recall(user_idea)
elapsed = time.time() - start

print(f"Recall Time: {elapsed:.2f}s")
print(f"API Call Count: {api_call_count}")
```

---

## 12. Extensions & Customization

### 12.1 Custom Weights

```python
# Modify in recall_system.py
class RecallConfig:
    PATH1_WEIGHT = 0.5  # Increase Path 1 weight
    PATH2_WEIGHT = 0.1  # Decrease Path 2 weight
    PATH3_WEIGHT = 0.4
```

### 12.2 Add New Recall Path

**Example: Path 4 - Similar Tech Stack Recall**:
```python
def _recall_path4_similar_techniques(self, user_idea):
    """Path 4: Recall via Tech Stack Similarity"""
    # Extract tech keywords
    techniques = extract_techniques(user_idea)

    # Match Pattern's common_tricks
    pattern_scores = defaultdict(float)
    for pattern in self.patterns:
        tricks = pattern.get('common_tricks', [])
        overlap = len(set(techniques) & set(tricks))
        pattern_scores[pattern['pattern_id']] = overlap

    return pattern_scores
```

### 12.3 Domain Specialization

```python
# Adjust params for specific domain (e.g., NLP)
if domain == "Natural Language Processing":
    RecallConfig.PATH1_WEIGHT = 0.5  # NLP relies more on historical experience
    RecallConfig.PATH2_WEIGHT = 0.1
```

---

## 13. Summary

### System Highlights

✅ **Three-Way Complementary Recall**: Balance similarity, domain, and quality
✅ **Two-Stage Optimization**: 13x speedup, second-level recall
✅ **Quality-Oriented Recall**: Path 3 incorporates Review quality score, improving accuracy
✅ **LLM Enhanced Pattern**: 124 Patterns summarized by LLM
✅ **Scalable Architecture**: Easy to add new recall paths
✅ **Complete Monitoring**: Detailed logs and metrics

### Technical Features

✅ **Embedding + Jaccard Hybrid**: Balance precision and speed
✅ **Graph Structured Recall**: Precise scoring using edge weights
✅ **Multi-Dimensional Quality Score**: Integrate overall_score, confidence, contribution, correctness
✅ **Real-Time Calculation**: Path 3 avoids pre-building redundant edges

### Improvements Needed

⚠️ **Optimize Domain Matching**: Introduce hierarchical structure or Embedding match
⚠️ **Vector Database**: Further boost recall efficiency to 1-3s
⚠️ **Online Learning**: Adjust weights based on user feedback
⚠️ **Extend Review Data**: Integrate review data from more conferences

---

**Generated**: 2026-01-25
**Version**: V3.1
**Author**: Idea2Paper Team

<br/>
<br/>
<br/>

# Idea2Story Pipeline Document

> **Note**: Scripts have been categorized into `scripts/tools/` and `scripts/demos/`. Old paths (e.g., `scripts/idea2story_pipeline.py`) can still be run via compatibility shims.

## 📋 Overview

This document details the complete generation link from User Idea to Publishable Paper Story, including Pattern Selection, Idea Fusion, Story Generation, Critic Review, Intelligent Correction Mechanism, Parameter Configuration, and Execution Methods.

---

## 1. System Architecture

### 1.1 Overall Process

```
┌─────────────────────────────────────────────────────────────────┐
│                  【Idea2Story Pipeline Full Process】             │
└─────────────────────────────────────────────────────────────────┘

User Input Idea
    │
    ▼
【Phase 1: Pattern Selection & Classification】 (Approx 1 sec)
    │
    ├─ Recall Top-10 Patterns (From Recall System)
    │   └─ Path 1 (Similar Idea) + Path 2 (Domain) + Path 3 (Similar Paper)
    │
    ├─ Pattern Multi-dimensional Classification
    │   ├─ Stability: Rank Top-3 + Cluster Size ≥ 15
    │   ├─ Novelty: Cluster Size < 10
    │   └─ Cross-Domain: Different Domain Source
    │
    └─ Select Initial Pattern (Prioritize Stability)
    │
    ▼
【Phase 2: Story Generation】 (Approx 1-2 mins)
    │
    └─ Generate Draft Story based on Pattern
        ├─ Use skeleton_examples as template
        ├─ Inject common_tricks
        └─ Structured Output (7 fields)
    │
    ▼
【Phase 3: Critic Review】 (Approx 30 secs)
    │
    └─ Multi-Role Review (Parallel)
        ├─ Methodology Critic: Tech Feasibility/Rigor
        ├─ Novelty Critic: Innovation/Problem Novelty
        └─ Storyteller Critic: Narrative Coherence/Readability
        │
        └─ Calculate Average Score (avg_score)
    │
    ▼
【Phase 4: Judgment Branch】
    │
    ├─【Check 1】Score >= 7.0?
    │   ├─【Yes】→ Enter Phase 5: RAG Deduplication
    │   └─【No】→ Enter Phase 4.1 or 4.2
    │
    ├─【Check 2】Novelty Stagnated? (novelty_score <= last + 0.5)
    │   ├─【Yes】→ Phase 4.1: Novelty Mode
    │   └─【No】→ Phase 4.2: Normal Correction
    │
    ├─────────────────────────────────────────────────────────────┐
    │              【Phase 4.1: Novelty Mode】 (3-10 mins)          │
    ├─────────────────────────────────────────────────────────────┤
    │                                                               │
    │  Iterate Novelty Dimension Patterns (Max 10)                  │
    │      │                                                        │
    │      ├─ For each novelty_pattern:                           │
    │      │                                                        │
    │      ├─ 1. Idea Fusion                                      │
    │      │     ├─ Input: user_idea + current_story + pattern    │
    │      │     ├─ LLM Analysis: Concept A, Concept B, Fusion    │
    │      │     └─ Output: fused_idea (New Idea)                 │
    │      │                                                        │
    │      ├─ 2. Story Reflection                                 │
    │      │     ├─ Input: fused_idea + current_story             │
    │      │     ├─ Evaluate 4 dimensions                         │
    │      │     │   ├─ concept_unity [0-10]                      │
    │      │     │   ├─ technical_soundness [0-10]                │
    │      │     │   ├─ novelty_level [0-10]                      │
    │      │     │   └─ narrative_clarity [0-10]                  │
    │      │     └─ Output: fusion_score + suggestions            │
    │      │                                                        │
    │      ├─ 3. Regenerate Story                                 │
    │      │     └─ Based on fused_idea + reflection_guidance     │
    │      │                                                        │
    │      ├─ 4. Critic Review                                    │
    │      │     └─ Get new avg_score                             │
    │      │                                                        │
    │      ├─ 5. Score Degradation Check                          │
    │      │     └─ If avg_score < last_score - 0.1:              │
    │      │         ├─ Rollback to previous version              │
    │      │         ├─ Mark Pattern Failed                       │
    │      │         └─ Skip this Pattern                         │
    │      │                                                        │
    │      ├─ 6. Record Best Result                               │
    │      │     └─ If avg_score > best_score:                    │
    │      │         └─ Update best_score and best_story          │
    │      │                                                        │
    │      ├─ 7. Pass Check                                       │
    │      │     └─ If avg_score >= 7.0:                          │
    │      │         └─ Early exit, enter Phase 5                 │
    │      │                                                        │
    │      └─ Loop End                                            │
    │           │                                                   │
    │           └─ Fallback: Return best_story (Highest Score)    │
    │                                                               │
    └─────────────────────────────────────────────────────────────┘
    │
    ├─────────────────────────────────────────────────────────────┐
    │              【Phase 4.2: Normal Correction】 (1-2 mins)      │
    ├─────────────────────────────────────────────────────────────┤
    │                                                               │
    │  Intelligent Injection of Complementary Tricks                │
    │      │                                                        │
    │      ├─ Analyze Critic Feedback                             │
    │      │   ├─ novelty_score < 6.0 → Lack Novelty              │
    │      │   ├─ methodology_score < 6.0 → Lack Stability        │
    │      │   └─ storyteller_score < 6.0 → Lack Narrative        │
    │      │                                                        │
    │      ├─ Select Complementary Pattern                        │
    │      │   ├─ Lack Novelty → Tail Injection (Rank 5-10, Novelty)│
    │      │   ├─ Lack Stability → Head Injection (Rank 1-3, Stability)│
    │      │   └─ Lack Narrative → Cross-Domain Injection         │
    │      │                                                        │
    │      └─ Return to Phase 2 (Regenerate Story)                │
    │                                                               │
    └─────────────────────────────────────────────────────────────┘
    │
    ▼
【Phase 5: RAG Deduplication】 (Approx 30 secs)
    │
    ├─ Extract Key Methods (techniques)
    │
    ├─ Retrieve Recent 3-Year Top Papers (Embedding Recall)
    │
    ├─ Calculate Similarity
    │
    └─ Judgment: Similarity > 0.75?
        ├─【No】→ Output Final Story ✅
        └─【Yes】→ Pivot Avoidance
                  ├─ Analyze Collision Points
                  ├─ Generate Constraints (Disable Tech/Domain Shift)
                  └─ Return to Phase 2
    │
    ▼
Output Final Story (JSON Format)
```

**Process Description**:
- **Phase 1-2**: Basic generation link.
- **Phase 3**: Quality assessment.
- **Phase 4**: Core correction mechanism (Two modes).
  - **Novelty Mode**: Deep exploration, Fusion+Reflection.
  - **Normal Correction**: Fast injection, complementary enhancement.
- **Phase 5**: Deduplication verification.

### 1.2 Core Modules

| Module | File | Function |
|--------|------|----------|
| **Pattern Selector** | `pattern_selector.py` | Multi-dimensional Pattern classification & ranking |
| **Story Generator** | `story_generator.py` | Structured Story generation |
| **Idea Fusion** | `planner.py` | Fuse new Pattern to generate innovative Idea |
| **Story Reflector** | `story_reflector.py` | Reflect on fusion quality |
| **Multi-Agent Critic** | `critic.py` | Three-role review |
| **Refinement Engine** | `refinement.py` | Intelligent correction & injection |
| **RAG Verifier** | `verifier.py` | Deduplication & avoidance |
| **Pipeline Manager** | `manager.py` | Process orchestration |

---

## 2. Pattern Selection & Classification

### 2.1 Multi-dimensional Classification

**Goal**: Classify recalled Top-10 Patterns into 3 dimensions to ensure diversity.

**Dimension Definitions**:

| Dimension | Definition | Selection Criteria | Role |
|-----------|------------|--------------------|------|
| **Stability** | Robust | Rank Top-3 + Cluster Size ≥ 15 | Ensure basic quality, reduce risk |
| **Novelty** | Innovative | Cluster Size < 10 | Enhance innovation |
| **Cross-Domain** | Cross-field | From Path 2/3 + Domain diff from Top-1 | Introduce cross-domain perspective |

**Algorithm**:

```python
def classify_patterns(recalled_patterns, user_idea):
    """Multi-dimensional Pattern Classification"""
    classified = {
        'stability': [],
        'novelty': [],
        'cross_domain': []
    }

    for rank, (pattern_id, pattern_info, score) in enumerate(recalled_patterns):
        metadata = {
            'rank': rank,
            'recall_score': score,
            'cluster_size': pattern_info.get('size', 0)
        }

        # Dim 1: Stability
        if rank <= 2 and metadata['cluster_size'] >= 15:
            classified['stability'].append((pattern_id, pattern_info, metadata))

        # Dim 2: Novelty
        if metadata['cluster_size'] < 10:
            classified['novelty'].append((pattern_id, pattern_info, metadata))

        # Dim 3: Cross-Domain
        if rank >= 3:  # From Path 2/3
            user_domain = extract_domain(user_idea)
            pattern_domain = pattern_info.get('domain', '')
            if pattern_domain != user_domain:
                classified['cross_domain'].append((pattern_id, pattern_info, metadata))

    return classified
```

### 2.2 Pattern Selection Strategy

```python
# Priority Order
1. Stability Dimension First (Ensure basic quality)
2. Novelty Dimension First (If stability empty)
3. Cross-Domain Dimension First (Fallback)
```

---

## 3. Story Generation Mechanism

### 3.1 Story Data Structure

```json
{
  "title": "Paper Title",
  "abstract": "Abstract (150-200 words)",
  "problem_definition": "Clear problem definition",
  "gap_pattern": "Research gap description",
  "method_skeleton": {
    "overview": "Method overview",
    "core_components": ["Component 1", "Component 2", "Component 3"],
    "technical_details": "Technical details"
  },
  "innovation_claims": [
    "Contribution 1",
    "Contribution 2",
    "Contribution 3"
  ],
  "experiments_plan": {
    "datasets": ["Dataset 1", "Dataset 2"],
    "baselines": ["Baseline 1", "Baseline 2"],
    "metrics": ["Metric 1", "Metric 2"],
    "ablation_studies": "Ablation study design"
  }
}
```

### 3.2 Generation Prompt Construction

**Initial Draft Prompt**:
```python
def _build_initial_prompt(user_idea, pattern_info):
    prompt = f"""
You are a top AI researcher. Based on the following information, generate an ICLR-level paper Story.

【User Idea】
{user_idea}

【Pattern Guidance】
Name: {pattern_info['name']}
Representative Ideas: {pattern_info['llm_enhanced_summary']['representative_ideas']}
Common Problems: {pattern_info['llm_enhanced_summary']['common_problems']}
Solution Approaches: {pattern_info['llm_enhanced_summary']['solution_approaches']}
Story Framework: {pattern_info['llm_enhanced_summary']['story']}

【Task】
Generate a complete paper Story (JSON format), containing:
- title: Attractive title
- abstract: 150-200 words abstract
- problem_definition: Clear problem definition
- gap_pattern: Research gap
- method_skeleton: Method skeleton (overview + core_components + technical_details)
- innovation_claims: 3 core contributions
- experiments_plan: Experiment design (datasets/baselines/metrics/ablation_studies)
"""
    return prompt
```

**Refinement Prompt**:
```python
def _build_refinement_prompt(story, critic_result, fused_idea, reflection_guidance):
    prompt = f"""
【Current Story】
{json.dumps(story, indent=2)}

【Critic Review Result】
Methodology: {critic_result['methodology']['score']}/10
  Issues: {critic_result['methodology']['issues']}

Novelty: {critic_result['novelty']['score']}/10
  Issues: {critic_result['novelty']['issues']}

【Fusion Innovation Guidance】
{format_fused_idea(fused_idea)}

【Reflection Suggestions】
{format_reflection_guidance(reflection_guidance)}

⚠️ 【HOW TO USE Fused Idea Guidance】
- **Title & Abstract**: Must reflect fused concept innovation, not tech piling
- **Problem Framing**: Adopt new problem perspective from fused idea
- **Gap Pattern**: Explain why existing methods lack this conceptual unity
- **Innovation Claims**: Frame as "transforming/reframing X from Y to Z"
- **Method**: Show how technologies CO-EVOLVE rather than CO-EXIST

【Task】
Revise the Story, focus on solving above issues, generate improved JSON.
"""
    return prompt
```

---

## 4. Idea Fusion Mechanism

### 4.1 Fusion Goal

**Problem**: Directly splicing Patterns leads to "tech piling", lacking conceptual unity.

**Goal**: Generate an **organically fused** new Idea, unifying the new Pattern with the original Idea at the **conceptual level**.

### 4.2 Fusion Prompt

```python
def plan_idea_fusion(user_idea, current_story, new_pattern_info, critic_issues):
    prompt = f"""
You are an innovation research planner. Analyze how to fuse the new Pattern into existing research.

【Current Research】
Idea: {user_idea}
Story: {extract_key_points(current_story)}

【New Pattern】
{format_pattern(new_pattern_info)}

【Critic Issues】
{critic_issues}

【Fusion Task】
Generate a fused Idea, requirements:

1. **Conceptual Unity**: Find conceptual connection point between new Pattern and original Idea
2. **Problem Reframing**: Reframe the problem so the new Pattern becomes a natural solution
3. **Innovation**: Clarify unique contribution after fusion

Return JSON:
{
  "fused_core_idea": "Fused core idea (single sentence)",
  "conceptual_bridge": "Conceptual bridge: how to connect original Idea and new Pattern",
  "reframed_problem": "Reframed problem definition",
  "innovation_angle": "Unique innovation point",
  "implementation_hints": ["Hint 1", "Hint 2"]
}
"""
    return prompt
```

### 4.3 Example

**Original Idea**:
```
Use LLM for data augmentation
```

**New Pattern**: Curriculum Learning

**Fusion Result**:
```json
{
  "fused_core_idea": "Difficulty-adaptive curriculum learning framework based on LLM generation",
  "conceptual_bridge": "LLM not only generates data but importantly can evaluate sample difficulty, thus building personalized learning paths",
  "reframed_problem": "How to make models learn LLM-generated pseudo-labels from easy to hard like humans",
  "innovation_angle": "Unifying LLM generation capability and difficulty evaluation capability in a curriculum learning framework for the first time",
  "implementation_hints": [
    "LLM tags difficulty for each generated sample",
    "Design difficulty-aware sample scheduler",
    "Progressive training strategy"
  ]
}
```

---

## 5. Story Reflection Mechanism

### 5.1 Reflection Goal

**Problem**: Fusion generates a fused Idea, but Story generator might:
- Not fully understand fusion intent
- Generate "rigid splicing" instead of "organic fusion"

**Goal**: After Story generation, reflect on fusion quality, evaluate if conceptual unity is truly achieved.

### 5.2 Reflection Process

```python
def reflect_on_fusion(fused_idea, generated_story):
    """Reflect on fusion quality"""
    # 1. Analyze fusion points
    fusion_points = analyze_fusion_points(fused_idea, generated_story)

    # 2. Check coherence
    coherence = check_conceptual_coherence(fusion_points)

    # 3. Evaluate fusion richness
    richness = evaluate_fusion_richness(fused_idea, generated_story)

    # 4. Calculate quality score
    quality = 0.4 * coherence + 0.4 * richness + 0.2 * has_fusion_idea_bonus

    # 5. Generate improvement suggestions
    suggestions = generate_improvement_suggestions(quality, fusion_points)

    return {
        'fusion_quality': quality,
        'fusion_points': fusion_points,
        'coherence_score': coherence,
        'fusion_richness': richness,
        'fusion_suggestions': suggestions
    }
```

### 5.3 Quality Scoring

```python
fusion_quality = 0.4 × Coherence + 0.4 × Fusion Richness + 0.2 × Fusion Idea Bonus

# Coherence: Are fusion points coherent across Story parts?
coherence_score = len(Coherent Fusion Points) / len(All Fusion Points)

# Fusion Richness: How many parts of Story reflect fusion?
richness_score = len(Story Parts reflecting fusion) / len(Total Story Parts)

# Fusion Idea Bonus: Did it use fused_idea guidance?
fusion_idea_bonus = 1.0 if fused_idea else 0.5
```

**Threshold**: `fusion_quality >= 0.65` considered successful fusion.

---

## 6. Critic Review Mechanism

### 6.1 Three-Role Review

| Role | Focus | Scoring Criteria |
|------|-------|------------------|
| **Reviewer A** (Methodology) | Technical Rationality, Experiment Completeness | Method Feasibility, Experiment Design |
| **Reviewer B** (Novelty) | Innovation, Unique Contribution | Problem Novelty, Method Innovation |
| **Reviewer C** (Storyteller) | Narrative Completeness, Logical Coherence | Structure Integrity, Logic Clarity |

### 6.2 Critic Prompt

```python
def build_critic_prompt(story, role):
    if role == "methodology":
        focus = """
Focus:
1. Is the method technically rational?
2. Is experiment design complete?
3. Any technical risks?
"""
    elif role == "novelty":
        focus = """
Focus:
1. Is problem definition novel?
2. Is method uniquely innovative?
3. Is it just tech piling?
"""
    elif role == "storyteller":
        focus = """
Focus:
1. Is logic coherent?
2. Is narrative complete?
3. Can readers understand?
"""

    prompt = f"""
You are an ICLR reviewer focusing on {role}.

【Paper Story】
{json.dumps(story, indent=2)}

{focus}

【Task】
Return JSON review result:
{{
  "score": 7,  # 1-10
  "issues": ["Issue 1", "Issue 2"],
  "suggestions": ["Suggestion 1", "Suggestion 2"]
}}
"""
    return prompt
```

### 6.3 Pass Standard

```python
PASS_SCORE = 7.0

# Average score of all three dimensions >= 7.0
avg_score = (methodology_score + novelty_score + storyteller_score) / 3
if avg_score >= PASS_SCORE:
    return "PASS"
else:
    return "FAIL"
```

---

## 7. Intelligent Correction Mechanism

### 7.1 Novelty Mode

**Trigger Condition**:
```python
# Novelty Score Stagnation
if novelty_score <= last_novelty_score + 0.5:
    activate_novelty_mode()
```

**Workflow**:
```python
def novelty_mode(ranked_patterns):
    """Novelty Mode: Iterate all novelty dimension Patterns"""
    novelty_patterns = ranked_patterns['novelty']
    best_score = 0
    best_story = None

    for pattern in novelty_patterns[:NOVELTY_MODE_MAX_PATTERNS]:
        # 1. Idea Fusion
        fused_idea = plan_idea_fusion(user_idea, current_story, pattern)

        # 2. Story Reflection
        reflection_result = reflect_on_fusion(fused_idea, current_story)

        # 3. Generate Final Story
        new_story = generate_story(
            pattern,
            fused_idea=fused_idea,
            reflection_guidance=reflection_result['fusion_suggestions']
        )

        # 4. Critic Review
        critic_result = critic.review(new_story)

        # 5. Score Degradation Check
        if critic_result['avg_score'] < last_avg_score - 0.1:
            # Rollback
            rollback()
            mark_failure(pattern)
            continue

        # 6. Record Highest Score
        if critic_result['avg_score'] > best_score:
            best_score = critic_result['avg_score']
            best_story = new_story

        # 7. Pass Check
        if critic_result['avg_score'] >= PASS_SCORE:
            return new_story

    # 8. Fallback: Return highest score version
    return best_story
```

### 7.2 Score Degradation Rollback

**Detection Condition**:
```python
# Any dimension score drops > 0.1
if (new_methodology_score < old_methodology_score - 0.1 or
    new_novelty_score < old_novelty_score - 0.1 or
    new_storyteller_score < old_storyteller_score - 0.1):
    trigger_rollback()
```

**Rollback Process**:
```python
def rollback():
    """Rollback to previous version"""
    # 1. Restore Story
    current_story = last_story_before_refinement

    # 2. Mark failed Pattern
    pattern_failure_map[pattern_id].add(issue_type)

    # 3. Remove injected Tricks
    injected_tricks.remove(failed_trick)

    # 4. Continue iteration (Do not increment iterations count)
```

### 7.3 Normal Correction Mode

**Trigger Condition**: Novelty not stagnated, but score not passed.

**Critic Diagnosis & Pattern Dimension Mapping**: System maps Critic roles directly to Pattern dimensions for unified correction strategy.

| Critic Role | Review Focus | Issue Type | Mapped Dimension | Injection Strategy |
|-------------|--------------|------------|------------------|--------------------|
| **Novelty** | Innovation | `novelty` | **Novelty Dim** | Select from Novelty dim, inject innovation |
| **Methodology** | Tech Rationality | `stability` | **Stability Dim** | Select from Stability dim, inject robust methods |
| **Storyteller** | Narrative Completeness | `domain_distance` | **Domain Distance Dim** | Select from Domain Distance dim, introduce cross-domain view |

**Injection Logic**:
```python
def refine_with_idea_fusion(main_issue: str, suggestions: List[str],
                            previous_story: Optional[Dict] = None) -> Tuple[List[str], Optional[Dict]]:
    """Select and fuse from corresponding Pattern dimension based on Critic diagnosis"""

    # Step 1: Dimension Mapping
    dimension_map = {
        'novelty': 'novelty',          # Novelty Critic → Novelty Dim
        'stability': 'stability',      # Methodology Critic → Stability Dim
        'domain_distance': 'domain_distance'  # Storyteller Critic → Domain Distance Dim
    }
    dimension = dimension_map[main_issue]

    # Step 2: Select Pattern from dimension
    patterns = ranked_patterns[dimension]
    idx = dimension_indices[dimension]  # Current index in dimension

    while idx < len(patterns):
        pattern_id, pattern_info, metadata = patterns[idx]

        # Skip failed Pattern
        if is_pattern_failed_for_issue(pattern_id, main_issue):
            idx += 1
            continue

        # Step 3: Idea Fusion
        fused_result = fusion_engine.fuse(
            user_idea=user_idea,
            pattern_id=pattern_id,
            pattern_info=pattern_info,
            previous_story=previous_story
        )

        # Step 4: Return Fusion Result
        return injected_tricks, fused_result
```

---

## 8. RAG Deduplication & Avoidance

### 8.1 Deduplication Process

```python
def verify_collision(story):
    """RAG Deduplication"""
    # 1. Extract Key Methods
    method_keywords = extract_method_keywords(story)

    # 2. Build Query
    query = f"{method_keywords} {story['problem_definition']}"

    # 3. Retrieve Recent 3-Year Top Papers
    similar_papers = retrieve_similar_papers(query, top_k=10)

    # 4. Calculate Similarity
    for paper in similar_papers:
        similarity = compute_similarity(story, paper)
        if similarity > COLLISION_THRESHOLD:
            return {
                'collision': True,
                'collided_paper': paper,
                'similarity': similarity
            }

    return {'collision': False}
```

### 8.2 Pivot Avoidance Strategy

**Trigger Condition**: `similarity > 0.75`

**Avoidance Process**:
```python
def pivot_to_avoid_collision(story, collided_paper):
    """Generate Avoidance Constraints"""
    # 1. Collision Analysis
    collision_analysis = analyze_collision(story, collided_paper)

    # 2. Generate Constraints
    constraints = {
        'forbidden_techniques': collision_analysis['overlapping_techniques'],
        'pivot_direction': "Migrate to unsupervised setting",
        'domain_shift': "Migrate from general domain to legal text",
        'additional_constraint': "Add long text processing module"
    }

    # 3. Regenerate Story
    new_story = generate_story(pattern, constraints=constraints)

    return new_story
```

---

## 9. Parameter Configuration

### 9.1 Pipeline Config

```python
# scripts/pipeline/config.py

class PipelineConfig:
    """Pipeline Config Params"""

    # Pattern Selection
    SELECT_PATTERN_COUNT = 3              # Select 3 Patterns
    CONSERVATIVE_RANK_RANGE = (0, 2)      # Stability: Rank 1-3
    INNOVATIVE_CLUSTER_SIZE_THRESHOLD = 10 # Innovative: Cluster Size < 10

    # Critic Thresholds
    PASS_SCORE = 7.0                      # Score >= 7 to pass
    MAX_REFINE_ITERATIONS = 3             # Max 3 rounds correction (Normal Mode)

    # Novelty Mode Config
    NOVELTY_MODE_MAX_PATTERNS = 10        # Max Patterns to try in Novelty Mode
    NOVELTY_SCORE_THRESHOLD = 6.0         # Novelty Score Threshold
    NOVELTY_STAGNATION_DELTA = 0.5        # Stagnation Delta

    # Reflection Config
    FUSION_QUALITY_THRESHOLD = 0.65       # Fusion Quality Threshold

    # Rollback Config
    SCORE_DEGRADATION_THRESHOLD = 0.1     # Score Drop Threshold

    # RAG Deduplication Threshold
    COLLISION_THRESHOLD = 0.75            # Sim > 0.75 Collision

    # Refinement Strategy
    TAIL_INJECTION_RANK_RANGE = (4, 9)    # Tail Injection: Rank 5-10
    HEAD_INJECTION_RANK_RANGE = (0, 2)    # Head Injection: Rank 1-3
    HEAD_INJECTION_CLUSTER_THRESHOLD = 15 # Head Injection: Cluster Size > 15
```

### 9.2 LLM Config

```python
# scripts/pipeline/config.py

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_PROVIDER = "openai_compatible_chat"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
```

---

## 10. Execution Methods

### 10.1 Full Pipeline Run

**Command**:
```bash
cd /Users/gaoge/code/mycode/Idea2Paper/Paper-KG-Pipeline
python scripts/idea2story_pipeline.py "Your Research Idea Description"
```

**Example**:
```bash
python scripts/idea2story_pipeline.py "Optimizing LLM inference efficiency using Reinforcement Learning"
```

**Output**:
```
output/
├── final_story.json          # Final generated Paper Story
├── pipeline_result.json      # Complete process result
└── log.json                  # Detailed Log
```

### 10.2 Output Structure

**final_story.json**:
```json
{
  "title": "Efficient LLM Reasoning via Reinforcement Learning...",
  "abstract": "We propose...",
  "problem_definition": "...",
  "gap_pattern": "...",
  "method_skeleton": {...},
  "innovation_claims": [...],
  "experiments_plan": {...}
}
```

**pipeline_result.json**:
```json
{
  "success": true,
  "final_story": {...},
  "iterations": 5,
  "selected_patterns": {
    "stability": [...],
    "novelty": [...],
    "cross_domain": [...]
  },
  "review_history": [
    {
      "iteration": 1,
      "methodology": {"score": 6.0, "issues": [...]},
      "novelty": {"score": 5.5, "issues": [...]},
      "storyteller": {"score": 7.0, "issues": []},
      "avg_score": 6.17
    },
    ...
  ],
  "refinement_history": [
    {
      "iteration": 2,
      "action": "idea_fusion",
      "pattern": "pattern_42",
      "fusion_quality": 0.72,
      "result": "success"
    },
    ...
  ]
}
```

### 10.3 Monitor Key Metrics

**Novelty Mode Activation**:
```bash
grep "Activate [Novelty Mode]" output/log.json
```

**Fusion Quality Score**:
```bash
grep "Fusion Quality Score" output/log.json
```

**Rollback Event**:
```bash
grep "【ROLLBACK TRIGGERED】" output/log.json
```

**Final Pass**:
```bash
grep "🎉 Critic Review Passed" output/log.json
```

---

## 11. Detailed Process Examples

### 11.1 Scenario A: Novelty Stagnation Triggers New Mode

**Initial State**:
```
Iteration 1: Novelty Score = 5.5
Iteration 2: Novelty Score = 5.6 (Gain 0.1 < 0.5)
→ Trigger Novelty Mode
```

**Novelty Mode Flow**:
```
1. Activate Novelty Mode
2. Iterate Novelty Pattern List (Max 10)

  Pattern 1 (pattern_42):
    ├─ Idea Fusion: Generate Fused Idea
    ├─ Story Reflection: Fusion Quality 0.72
    ├─ Generate Final Story (Based on reflection suggestions)
    ├─ Critic Review: 6.5/10 (Fail)
    └─ Continue to next Pattern

  Pattern 2 (pattern_55):
    ├─ Idea Fusion: Generate Fused Idea
    ├─ Story Reflection: Fusion Quality 0.68
    ├─ Generate Final Story
    ├─ Critic Review: 7.2/10 (Pass!)
    └─ Enter RAG Deduplication

3. RAG Deduplication: No Collision
4. Output Final Story
```

### 11.2 Scenario B: Score Degradation Triggers Rollback

```
Iteration 3:
  Current Scores: Methodology=7.0, Novelty=6.0, Storyteller=7.5

  Inject Pattern_30:
    ├─ Idea Fusion: ...
    ├─ Generate New Story
    ├─ Critic Review: Methodology=6.2 (Drop 0.8 > 0.1)
    ├─ Detected Score Degradation
    └─ Trigger Rollback

  Rollback Operation:
    ├─ Restore Story to pre-injection version
    ├─ Mark Pattern_30 Failed
    ├─ Remove Injected Tricks
    └─ Continue Iteration (No count increment)

  Select Next Pattern: Pattern_45
    ├─ Idea Fusion: ...
    ├─ Generate New Story
    ├─ Critic Review: Methodology=7.3 (Improved)
    └─ Save Result
```

---

## 12. Final Version Selection Mechanism

### 12.1 Global Best Tracking

**Philosophy**: Throughout iterations, generated Stories may have different qualities. System must track and select the global best version.

**Core Mechanism**:
```python
# Update global best after each Critic review
if current_avg_score > global_best_score:
    global_best_story = current_story
    global_best_score = current_avg_score
    global_best_iteration = iteration_number
    print(f"🏆 Update Global Best: Score {global_best_score:.2f}")
```

### 12.2 Final Output Logic

**Priority Rules**:
1. **Priority**: If there is a version passed Critic Review (avg_score >= 7.0) → Use passed version
2. **Fallback**: If no passed version → Use Global Best Version (Highest score during iterations)

**Implementation**:
```python
# Final Version Selection
final_story = current_story  # Default current
final_is_passed = review_history[-1]['pass']

if not final_is_passed and global_best_story is not None:
    # Not passed but has best version
    if global_best_score > current_score:
        final_story = global_best_story  # Use best version
        print(f"✅ Use Global Best Version (Iteration {global_best_iteration}, Score {global_best_score:.2f})")
```

### 12.3 Typical Scenarios

**Scenario A: Stepwise Improvement, Finally Passed**
```
Iteration 1: Draft → 6.17 → Update Best
Iteration 2: Inject Novelty Pattern → 6.85 → Update Best
Iteration 3: Continue Optimize → 7.20 → Pass! ✅
→ Output: Iteration 3 Passed Version
```

**Scenario B: Fluctuation, Not Passed**
```
Iteration 1: Draft → 6.17 → Update Best
Iteration 2: Inject Pattern → 6.85 → Update Best
Iteration 3: Rollback & Optimize → 6.50 → Not Update
→ Output: Iteration 2 Best Version (6.85)
```

**Scenario C: Novelty Mode Traversal**
```
Novelty Mode:
  Pattern 1 → 6.50 → Update Best
  Pattern 2 → 6.35 → Not Update
  Pattern 3 → 6.80 → Update Best
  ...
→ Output: Pattern 3 Version (6.80)
```

---

**Generated**: 2026-01-25
**Version**: V3.1
**Author**: Idea2Paper Team

<br/>
<br/>
<br/>
