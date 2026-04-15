# MultiAgentReview (Blind + τ-Calibrated + Deterministic Scoring) — Developer Technical Spec

This document is for developers maintaining the **new reviewer/critic system**.  
Core idea: the **LLM only makes blind relative judgments** (better/tie/worse), while the **final 1–10 scores are deterministically inferred** from anchors’ real `score10` using an **offline-calibrated τ**. A separate **Coach Layer** generates field-level edit instructions and does **not** affect scoring.

---

## 0. Quickstart (including τ fitting commands)

### 0.1 Fit τ first (strongly recommended)

The τ fitting script judges sampled paper pairs per role. With default `--pairs=2000`, the three roles require about **6000 LLM calls** total (plus a small amount of retries), so plan for cost/time.

```bash
# Methodology (default 2000 pairs)
python Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py --role Methodology --pairs 2000

# Novelty (default 2000 pairs)
python Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py --role Novelty --pairs 2000

# Storyteller (default 2000 pairs)
python Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py --role Storyteller --pairs 2000
```

Outputs:
- Pair dataset: `Paper-KG-Pipeline/output/judge_pairs.jsonl`
- τ file: `Paper-KG-Pipeline/output/judge_tau.json` (includes `tau_methodology/tau_novelty/tau_storyteller` + metadata like `rubric_version/card_version/judge_model/nodes_paper_hash`)

Script location:
- `Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py`

### 0.2 Run a pipeline smoke test (includes the new critic)

```bash
python Paper-KG-Pipeline/scripts/idea2story_pipeline.py "test idea"
```

Recommended logs:
- `log/<run_id>/llm_calls.jsonl`
- `log/<run_id>/events.jsonl`

---

## 1. Non-negotiable principles (viewer相关.md alignment)

1) **Blind judging**: judge/critic prompts must never expose real-world identifiers or any score-related data (e.g. `paper_id/title/author/url/doi/arxiv/score/score10/pattern_id`).  
2) **LLM outputs relative judgments only**: `better|tie|worse` + `strength(weak|medium|strong)` + short rationale (≤ 25 words).  
3) **Deterministic score inference**: final `S∈[1,10]` is inferred by code from anchors’ real `score10` using a fixed τ (offline-calibrated).  
4) **Two-layer design**:
   - **Score Layer**: blind comparisons → deterministic inference (reproducible)
   - **Coach Layer**: field-level edits after scoring (does not affect scores)

---

## 2. Module map (where the implementation lives)

### 2.1 Entry point: MultiAgentCritic

- Main implementation: `Paper-KG-Pipeline/src/idea2paper/application/review/critic.py`
- Compatibility wrapper (keeps old import paths working): `Paper-KG-Pipeline/src/idea2paper/review/critic.py`

Primary API:
- `MultiAgentCritic.review(story: Dict, context: Optional[Dict]) -> Dict`

### 2.2 Score Layer modules

- Blind Cards: `Paper-KG-Pipeline/src/idea2paper/application/review/cards.py`
  - `build_story_card(...)`
  - `build_paper_card(...)`
  - `CARD_VERSION`
- Rubric: `Paper-KG-Pipeline/src/idea2paper/application/review/rubric.py`
  - `get_rubric(role)`
  - `RUBRIC_VERSION`
- Blind Judge: `Paper-KG-Pipeline/src/idea2paper/application/review/blind_judge.py`
  - `BlindJudge.judge(...)` (prompt building + schema validation + repair/retry)
  - `FORBIDDEN_TERMS` (rationale leak checks)
- Deterministic inference: `Paper-KG-Pipeline/src/idea2paper/application/review/score_inference.py`
  - `infer_score_from_comparisons(...)` (grid search over S)

### 2.3 Anchor index & selection

- `Paper-KG-Pipeline/src/idea2paper/application/review/review_index.py`
  - Builds `score10/weight` from `nodes_paper.json` `review_stats`
  - Initial anchors: `select_initial_anchors(...)` (dense quantiles + exemplars)
  - Densify anchors: `select_bucket_anchors(...)` (bucket cache)

### 2.4 Coach Layer

- `Paper-KG-Pipeline/src/idea2paper/application/review/coach.py`
  - `CoachReviewer.review(...)` (field-level JSON + repair/retry)

### 2.5 Pipeline integration (where critic is called)

- Pipeline orchestrator: `Paper-KG-Pipeline/src/idea2paper/application/pipeline/manager.py`
  - `critic_result = self.critic.review(current_story, context=critic_context)`
- StoryGenerator consumes coach outputs for refinement prompts: `Paper-KG-Pipeline/src/idea2paper/application/pipeline/story_generator.py`

---

## 3. Score Layer: end-to-end flow (Story → per-role scores)

Orchestrated in: `Paper-KG-Pipeline/src/idea2paper/application/review/critic.py`

### 3.1 Anchor selection (program-only; never shown to LLM)

If `context["anchors"]` is not provided, anchors are chosen deterministically by `pattern_id`:
1) Quantile anchors (default q05–q95)  
2) Exemplar anchors (up to 2)  
3) Truncate to `I2P_ANCHOR_MAX_INITIAL` (default 11)

Implementation:
- `ReviewIndex.select_initial_anchors(...)`

Anchor summary fields (program-only):
- `paper_id` (lookup key)
- `score10` (real anchor score on 1–10 scale)
- `weight` (anchor reliability weight)

### 3.2 Blind card construction (anonymization)

StoryCard and PaperCard share identical fields (treat this as the *only* information surface the LLM is allowed to see):
- `problem`
- `method`
- `contrib`
- `card_version`

Design choices:
- Only stable, widely available fields are shown to the judge to avoid “unknown” becoming a decisive negative signal.
- Fields like `experiments_plan`, `domain/sub_domains/application`, and `notes` are **not** rendered into judge prompts.
- Length caps are enforced on all three fields to prevent “longer = better” bias:
  - `problem` ≤ 220 chars
  - `method` ≤ 280 chars
  - `contrib` ≤ 320 chars

Implementation:
- `cards.py:build_story_card(...)`
- `cards.py:build_paper_card(...)`
Current `CARD_VERSION`: `blind_card_v2_minimal` (changing it requires re-fitting τ).

Crucially, cards do **not** include `paper_id/title/url/score/score10/pattern_id`.

### 3.3 Blind Judge: one LLM call per role

For each role (Methodology / Novelty / Storyteller), we ask the LLM to compare the StoryCard against all AnchorCards:

Output schema (JSON-only):
```json
{
  "rubric_version": "rubric_v1",
  "comparisons": [
    {"anchor_id":"A1","judgement":"better|tie|worse","strength":"weak|medium|strong","rationale":"..."}
  ]
}
```

Implementation:
- Prompt: `blind_judge.py:_build_prompt(...)`
- Validation: `blind_judge.py:_validate(...)` (strict schema + forbidden rationale terms)
- Retry: `blind_judge.py:judge(...)` (repair prompt up to `I2P_CRITIC_JSON_RETRIES`)

### 3.4 Map LLM judgments to observations

Mapping (viewer-related contract):
- better → `y=1`
- worse → `y=0`
- tie → `y=0.5` (soft label)

Strength as weight multiplier (not numeric “confidence”):
- weak=1, medium=2, strong=3

Implementation:
- `score_inference.py`

### 3.5 Deterministic inference of S via grid search

Given anchors’ real `score10_i` (program-only) and τ:
- `p_i = sigmoid((S - score10_i) / tau)`
- minimize: `NLL(S) = Σ w_i * CE(y_i, p_i)`
  - `w_i = anchor_weight * strength_weight`
  - `anchor_weight = log(1+review_count)/(1+dispersion10)` from `review_stats`

Implementation:
- `score_inference.py:infer_score_from_comparisons(...)`
  - grid `S ∈ [1,10]`, step `I2P_GRID_STEP` (default 0.01)
  - outputs diagnostics (`loss/avg_strength/monotonic_violations/ci_low/ci_high`)

---

## 4. τ: where it comes from and when to refit

### 4.1 τ loading priority

Implementation: `critic.py:_get_tau(...)`

Priority:
1) `I2P_JUDGE_TAU_PATH` JSON file keys `tau_methodology/tau_novelty/tau_storyteller`
2) Env/config fallbacks: `I2P_TAU_METHODOLOGY/I2P_TAU_NOVELTY/I2P_TAU_STORYTELLER`
3) Final fallback: `I2P_JUDGE_TAU_DEFAULT`

### 4.2 When you MUST refit τ

Refit τ if any of the following changes:
- `RUBRIC_VERSION` changes (rubric text or criteria)
- `CARD_VERSION` changes (card fields/mapping)
- Judge model changes
- Large changes in `nodes_paper.json` distribution

The fitter writes `rubric_version/card_version/judge_model/nodes_paper_hash` into `judge_tau.json` to make mismatches detectable.

---

## 5. Densify (second round with extra anchors)

If the first round looks unstable/inconsistent, densify adds a few anchors and re-runs all roles (still blind).

Triggers (in `critic.py`):
- `loss > I2P_DENSIFY_LOSS_THRESHOLD`, or
- `monotonic_violations >= 1`, or
- `avg_strength < I2P_DENSIFY_MIN_AVG_CONF`

Extra anchor strategy:
- bucketed selection around `S_hint`: `review_index.py:select_bucket_anchors(...)`
- cached via `_bucket_cache` to avoid repeated slow selection

Key configs:
- `I2P_ANCHOR_DENSIFY_ENABLE`
- `I2P_ANCHOR_BUCKET_SIZE` / `I2P_ANCHOR_BUCKET_COUNT`

---

## 6. Coach Layer (field-level actionable edits; does not affect scoring)

After Score Layer completes, a separate LLM call produces structured rewrite guidance:

```json
{
  "field_feedback": {
    "title": {"issue":"...", "edit_instruction":"...", "expected_effect":"..."},
    "abstract": {...},
    "problem_framing": {...},
    "method_skeleton": {...},
    "innovation_claims": {...},
    "experiments_plan": {...}
  },
  "suggested_edits":[{"field":"innovation_claims","action":"rewrite|add|delete|expand","content":"..."}],
  "priority":["innovation_claims","method_skeleton","abstract"]
}
```

Implementation:
- `coach.py:CoachReviewer.review(...)` (includes JSON repair/retries)

Configs:
- `I2P_CRITIC_COACH_ENABLE`
- `I2P_CRITIC_COACH_TEMPERATURE`
- `I2P_CRITIC_COACH_MAX_TOKENS`

---

## 7. Public API & pipeline compatibility

`MultiAgentCritic.review(...)` returns (core fields):

```python
{
  "pass": bool,
  "avg_score": float,
  "reviews": [{"reviewer": "...", "role": "...", "score": float, "feedback": str}],
  "main_issue": str,
  "suggestions": [str, ...],
  "audit": dict,

  # Added for precise rewriting:
  "field_feedback": dict,
  "suggested_edits": list,
  "priority": list,
  "review_coach": dict,
}
```

Compatibility:
- Legacy code can still concatenate `reviews[*].feedback`
- New code can prefer `field_feedback/suggested_edits/priority`

---

## 8. Logging, audit, and common phenomena (e.g., “why S becomes 10”)

### 8.1 Audit is for reproducibility (and is allowed to include score10)

`audit` is used to reproduce and debug results. It may contain `paper_id/score10/weight`, but those must never enter judge prompts.

Key fields:
- `audit.anchors[*]`: `paper_id/score10/weight`
- `audit.role_details[role]`:
  - `comparisons` (LLM relative judgments)
  - `loss/avg_strength/monotonic_violations/ci_low/ci_high/tau`

### 8.2 Interpreting “S=10”

If the LLM outputs near-all `better` across anchors (y≈1), the likelihood objective can push `S` to the grid upper bound 10.  
This is **not** “LLM directly outputting a 10”, but an inference saturation effect typically caused by low-score anchor ranges or weak anchor cards.

### 8.3 Run logs

With run logging enabled:
- `log/<run_id>/llm_calls.jsonl`: prompt/response/latency (prompt/response may be truncated by `I2P_LOG_MAX_TEXT_CHARS`)
- `log/<run_id>/events.jsonl`: structured events (e.g., pass threshold computed)

Implementation:
- `Paper-KG-Pipeline/src/idea2paper/infra/run_logger.py`

---

## 9. Configuration checklist (common)

Config precedence: env/.env > `i2p_config.json` > defaults (implemented in `Paper-KG-Pipeline/src/idea2paper/config.py`).

### 9.1 τ
- `I2P_JUDGE_TAU_PATH`
- `I2P_TAU_METHODOLOGY` / `I2P_TAU_NOVELTY` / `I2P_TAU_STORYTELLER`
- `I2P_JUDGE_TAU_DEFAULT`

### 9.2 Anchors / densify
- `I2P_ANCHOR_QUANTILES`
- `I2P_ANCHOR_MAX_INITIAL` / `I2P_ANCHOR_MAX_TOTAL` / `I2P_ANCHOR_MAX_EXEMPLARS`
- `I2P_ANCHOR_DENSIFY_ENABLE`
- `I2P_DENSIFY_LOSS_THRESHOLD` / `I2P_DENSIFY_MIN_AVG_CONF`
- `I2P_ANCHOR_BUCKET_SIZE` / `I2P_ANCHOR_BUCKET_COUNT`
- `I2P_GRID_STEP`

### 9.3 JSON strictness / safety
- `I2P_CRITIC_STRICT_JSON`
- `I2P_CRITIC_JSON_RETRIES`

### 9.4 Coach
- `I2P_CRITIC_COACH_ENABLE`
- `I2P_CRITIC_COACH_TEMPERATURE`
- `I2P_CRITIC_COACH_MAX_TOKENS`

---

## 10. Why the old system was removed

Typical issues with the old path:
- LLM saw `score10`/titles → anchoring bias and leakage risk
- LLM produced 1–10 scores directly → non-reproducible, hard to calibrate/audit
- Unstructured feedback → hard to do precise rewrite loops

Benefits of the new system:
- Blind + τ-calibrated inference → controlled, reproducible, debuggable
- Coach outputs are field-level → refinement can be “execute edits per field”
