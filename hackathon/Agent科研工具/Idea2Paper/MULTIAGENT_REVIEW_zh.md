# MultiAgentReview（Blind + τ 校准 + 确定性反推评分）技术说明（面向开发者）

本文档面向仓库开发者，详细说明 **新 Reviewer/Critic 系统** 的工作机制、数据结构、关键配置、调用链路与代码位置。  
核心思想：**LLM 只做盲测相对判断**（better/tie/worse），**分数由程序用锚点真实 score10 + 离线标定的 τ 确定性反推**；另有独立的 **Coach Layer** 产出字段级可执行改稿建议（不影响评分）。

---

## 0. 快速开始（含 τ 标定命令）

### 0.1 先标定 τ（强烈建议）

τ 标定脚本会对每个 role 采样并评判一批论文对。默认 `--pairs=2000`，三角色合计约 **6000 次 LLM 调用**（还可能有少量重试），耗时/费用请提前评估。

```bash
# Methodology（默认 2000 对）
python Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py --role Methodology --pairs 2000

# Novelty（默认 2000 对）
python Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py --role Novelty --pairs 2000

# Storyteller（默认 2000 对）
python Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py --role Storyteller --pairs 2000
```

输出文件：
- 采样对数据：`Paper-KG-Pipeline/output/judge_pairs.jsonl`
- τ 文件：`Paper-KG-Pipeline/output/judge_tau.json`

脚本位置：
- `Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py`

### 0.2 跑一次 pipeline 冒烟（包含新 critic）

```bash
python Paper-KG-Pipeline/scripts/idea2story_pipeline.py "test idea"
```

建议同时查看运行日志：
- `log/<run_id>/llm_calls.jsonl`
- `log/<run_id>/events.jsonl`

---

## 1. 关键原则（与 viewer相关.md 对齐的“契约”）

1) **盲测**：在任何 judge/critic prompt 中，严禁出现能反推出真实论文身份或评分的信息（例如 `paper_id/title/author/url/doi/arxiv/score/score10/pattern_id` 等）。  
2) **LLM 仅输出相对判断**：`better|tie|worse` + `strength(weak|medium|strong)` + `rationale(<=25 words)`。  
3) **分数确定性反推**：最终 `S∈[1,10]` 由程序用 anchors 的真实 `score10` + 固定 τ（离线拟合写入 config）做最大似然/交叉熵拟合得到。  
4) **两层架构**：
   - **Score Layer（计分层）**：盲测相对判断 → 反推分数（严格、可复现）
   - **Coach Layer（改稿层）**：分数确定后 → 字段级改稿建议（不影响评分）

---

## 2. 模块地图（从哪里看代码）

### 2.1 主入口：MultiAgentCritic

- 主实现：`Paper-KG-Pipeline/src/idea2paper/application/review/critic.py`
- 包装导出（兼容旧 import 路径）：`Paper-KG-Pipeline/src/idea2paper/review/critic.py`

核心接口：
- `MultiAgentCritic.review(story: Dict, context: Optional[Dict]) -> Dict`

### 2.2 Score Layer（计分层）模块

- Blind Cards：`Paper-KG-Pipeline/src/idea2paper/application/review/cards.py`
  - `build_story_card(...)`
  - `build_paper_card(...)`
  - `CARD_VERSION`
- Rubric：`Paper-KG-Pipeline/src/idea2paper/application/review/rubric.py`
  - `get_rubric(role)`
  - `RUBRIC_VERSION`
- Blind Judge：`Paper-KG-Pipeline/src/idea2paper/application/review/blind_judge.py`
  - `BlindJudge.judge(...)`（prompt 构造 + JSON 校验 + repair/retry）
  - `FORBIDDEN_TERMS`（对 rationale 的敏感词检查）
- 分数反推：`Paper-KG-Pipeline/src/idea2paper/application/review/score_inference.py`
  - `infer_score_from_comparisons(...)`（网格搜索 S）

### 2.3 Anchor 索引与选择

- `Paper-KG-Pipeline/src/idea2paper/application/review/review_index.py`
  - 构建索引：从 `nodes_paper.json` 的 `review_stats` 计算 `score10/weight`
  - 初始 anchors：`select_initial_anchors(...)`（分位点 q05~q95 + exemplars）
  - densify anchors：`select_bucket_anchors(...)`（bucket 缓存）

### 2.4 Coach Layer（改稿层）模块

- `Paper-KG-Pipeline/src/idea2paper/application/review/coach.py`
  - `CoachReviewer.review(...)`（字段级 JSON + repair/retry）

### 2.5 Pipeline 调用链（critic 在哪里被调用）

- Pipeline 编排：`Paper-KG-Pipeline/src/idea2paper/application/pipeline/manager.py`
  - `critic_result = self.critic.review(current_story, context=critic_context)`
- StoryGenerator 消费 coach 结构（用于 refinement prompt）：`Paper-KG-Pipeline/src/idea2paper/application/pipeline/story_generator.py`

---

## 3. Score Layer：端到端数据流（Story → 三维分数）

主调度位置：`Paper-KG-Pipeline/src/idea2paper/application/review/critic.py`

### 3.1 选 anchors（程序内部，绝不进 LLM）

当 `context["anchors"]` 未提供时，按 `pattern_id` 自动选择：
1) 分位点 anchors（默认 q05~q95）  
2) exemplar anchors（最多 2 个）  
3) 截断到 `I2P_ANCHOR_MAX_INITIAL`（默认 11）

实现：
- `ReviewIndex.select_initial_anchors(...)`

Anchor summary 的关键字段（仅程序内部可见）：
- `paper_id`（用于回查 paper node）
- `score10`（真实锚点分）
- `weight`（锚点可靠度权重）

### 3.2 构造 Blind Cards（匿名化）

StoryCard 与 PaperCard 同构字段（建议视为“公开给 LLM 的唯一信息面”）：
- `problem`
- `method`
- `contrib`
- `card_version`

设计说明：
- 仅展示稳定且普遍可得的字段，避免 “unknown/缺失” 变成决定性负面证据。
- `experiments_plan`、`domain/sub_domains/application`、`notes` 不进入 judge prompt。
- 对三字段强制长度裁剪，避免“写得更长就赢”：
  - `problem` ≤ 220 字符
  - `method` ≤ 280 字符
  - `contrib` ≤ 320 字符

实现：
- `cards.py:build_story_card(...)`
- `cards.py:build_paper_card(...)`
当前 `CARD_VERSION`：`blind_card_v2_minimal`（更改后必须重新拟合 τ）。

重要：Card **不包含** `paper_id/title/url/score/score10/pattern_id`，从源头避免泄露。

### 3.3 Blind Judge（每个维度一次 LLM 调用）

对每个 role（Methodology / Novelty / Storyteller）分别调用：
- 输入：StoryCard + AnchorCards(A1..AK) + 该 role rubric
- 输出 schema（JSON only）：

```json
{
  "rubric_version": "rubric_v1",
  "comparisons": [
    {"anchor_id":"A1","judgement":"better|tie|worse","strength":"weak|medium|strong","rationale":"..."}
  ]
}
```

实现：
- `blind_judge.py:_build_prompt(...)`
- `blind_judge.py:_validate(...)`（强 schema 校验 + rationale 禁止敏感词）
- `blind_judge.py:judge(...)`（不合规就 repair/retry，按 `I2P_CRITIC_JSON_RETRIES`）

### 3.4 将 judge 输出映射为观测量 y

映射规则（对齐 viewer相关.md）：
- better → `y=1`
- worse → `y=0`
- tie → `y=0.5`（软标签）

strength 仅做权重（不做数值置信度）：
- weak=1, medium=2, strong=3

实现：
- `score_inference.py` 内部映射

### 3.5 确定性反推分数 S（网格搜索）

给定每个 anchor 的真实 `score10_i`（只在程序里）与 τ：
- `p_i = sigmoid((S - score10_i) / tau)`
- 最小化：`NLL(S) = Σ w_i * CE(y_i, p_i)`
  - `w_i = anchor_weight * strength_weight`
  - `anchor_weight = log(1+review_count)/(1+dispersion10)`（来自 `review_stats`）

实现：
- `score_inference.py:infer_score_from_comparisons(...)`
  - 网格 `S ∈ [1,10]`，步长 `I2P_GRID_STEP`（默认 0.01）
  - 输出同时给出 `loss/avg_strength/monotonic_violations/ci_low/ci_high`

---

## 4. τ：怎么来的、什么时候需要重拟合

### 4.1 τ 的来源与读取优先级

实现：`critic.py:_get_tau(...)`

优先级：
1) `I2P_JUDGE_TAU_PATH` 指向的 `judge_tau.json` 中的 `tau_methodology/tau_novelty/tau_storyteller`
2) env/config 回退：`I2P_TAU_METHODOLOGY/I2P_TAU_NOVELTY/I2P_TAU_STORYTELLER`
3) 最终回退：`I2P_JUDGE_TAU_DEFAULT`

### 4.2 什么时候必须重拟合

以下任何一项变化，都应重跑 τ 标定：
- `RUBRIC_VERSION` 变化（rubric 文字/标准变化）
- `CARD_VERSION` 变化（card 字段或映射变化）
- judge 模型变化（不同模型“判别曲线”会不同）
- `nodes_paper.json` 大规模更新（分布变化明显）

脚本 `fit_judge_tau.py` 会把 `rubric_version/card_version/judge_model/nodes_paper_hash` 写入 τ 文件，便于人工核对。

---

## 5. Densify（补锚点第二轮）为何会触发

当第一轮推断显示“不稳定/不一致”时，会触发 densify：追加少量 anchors 再跑一轮三角色盲测（仍然盲测，不泄露）。

触发条件（实现：`critic.py`）：
- `loss > I2P_DENSIFY_LOSS_THRESHOLD`，或
- `monotonic_violations >= 1`，或
- `avg_strength < I2P_DENSIFY_MIN_AVG_CONF`

补锚点策略：
- 以 `S_hint` 为中心选 bucket anchors：`review_index.py:select_bucket_anchors(...)`
- bucket 有缓存 `_bucket_cache`，避免重复选择造成额外开销

配置：
- `I2P_ANCHOR_DENSIFY_ENABLE`
- `I2P_ANCHOR_BUCKET_SIZE` / `I2P_ANCHOR_BUCKET_COUNT`

---

## 6. Coach Layer：字段级可执行改稿建议（不影响评分）

Score Layer 完成后再调用一次 LLM，输出结构化改稿建议：

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

实现：
- `coach.py:CoachReviewer.review(...)`（含 JSON 修复重试）

配置：
- `I2P_CRITIC_COACH_ENABLE`
- `I2P_CRITIC_COACH_TEMPERATURE`
- `I2P_CRITIC_COACH_MAX_TOKENS`

---

## 7. 对外接口与 pipeline 兼容性

`MultiAgentCritic.review(...)` 返回结构（核心字段）：

```python
{
  "pass": bool,
  "avg_score": float,
  "reviews": [{"reviewer": "...", "role": "...", "score": float, "feedback": str}],
  "main_issue": str,
  "suggestions": [str, ...],
  "audit": dict,

  # 新增：供 story_generator 精准改写
  "field_feedback": dict,
  "suggested_edits": list,
  "priority": list,
  "review_coach": dict,
}
```

兼容策略：
- 旧链路仍可只使用 `reviews[*].feedback` 拼接 prompt
- 新链路可优先使用 `field_feedback/suggested_edits/priority` 做字段级改写

---

## 8. 日志、审计与常见现象（例如 “为什么会出现 10 分”）

### 8.1 审计（audit）是什么、为什么允许包含 paper_id/score10

`audit` 用于复盘与复现，允许包含 `paper_id/score10/weight`，但必须保证：
- 这些字段只在程序内部与日志/结果 JSON 中出现
- **不会进入任何 judge prompt**

关键字段：
- `audit.anchors[*]`：`paper_id/score10/weight`
- `audit.role_details[role]`：
  - `comparisons`（LLM 相对判断）
  - `loss/avg_strength/monotonic_violations/ci_low/ci_high/tau`

### 8.2 “S=10” 的解释（不是 LLM 直出）

当某个 role 对当前 anchors 给出近乎全 `better`（y≈1）时，在我们的模型下最优 S 会被推到网格上界 10。  
这通常意味着 anchors 的 `score10` 分布偏低，或 anchor cards 内容过于概括（缺少可区分的细节），导致 judge 更容易判 “Story 更好”。

### 8.3 结构化运行日志

启用 run logger 后：
- `log/<run_id>/llm_calls.jsonl`：每次 LLM 调用的 prompt/响应/耗时（可能按 `I2P_LOG_MAX_TEXT_CHARS` 截断）
- `log/<run_id>/events.jsonl`：结构化事件（例如 `pass_threshold_computed`）

实现：
- `Paper-KG-Pipeline/src/idea2paper/infra/run_logger.py`

---

## 9. 常用配置清单（开发者）

配置读取优先级：env/.env > `i2p_config.json` > 默认值（实现：`Paper-KG-Pipeline/src/idea2paper/config.py`）。

### 9.1 τ 相关

- `I2P_JUDGE_TAU_PATH`
- `I2P_TAU_METHODOLOGY` / `I2P_TAU_NOVELTY` / `I2P_TAU_STORYTELLER`
- `I2P_JUDGE_TAU_DEFAULT`

### 9.2 anchors / densify 相关

- `I2P_ANCHOR_QUANTILES`
- `I2P_ANCHOR_MAX_INITIAL` / `I2P_ANCHOR_MAX_TOTAL` / `I2P_ANCHOR_MAX_EXEMPLARS`
- `I2P_ANCHOR_DENSIFY_ENABLE`
- `I2P_DENSIFY_LOSS_THRESHOLD` / `I2P_DENSIFY_MIN_AVG_CONF`
- `I2P_ANCHOR_BUCKET_SIZE` / `I2P_ANCHOR_BUCKET_COUNT`
- `I2P_GRID_STEP`

### 9.3 JSON 可靠性 / 安全

- `I2P_CRITIC_STRICT_JSON`
- `I2P_CRITIC_JSON_RETRIES`

### 9.4 Coach 相关

- `I2P_CRITIC_COACH_ENABLE`
- `I2P_CRITIC_COACH_TEMPERATURE`
- `I2P_CRITIC_COACH_MAX_TOKENS`

---

## 10. 与旧系统的差异（为什么必须重置）

旧系统的典型问题：
- LLM 看到 `score10`/标题等 → 锚定偏差与泄露风险
- LLM 直出 1~10 分 → 不可复现、难校准、难审计
- 反馈不可结构化落地 → 难以精准改写

新系统的收益：
- 盲测 + τ 校准 → 可控、可复现、可解释
- Coach 字段级建议 → refinement 可“按字段执行”
