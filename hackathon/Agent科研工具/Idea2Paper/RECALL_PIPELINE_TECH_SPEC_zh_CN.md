# 召回链路技术说明（输入 Idea → 三路召回 → Pattern 选择 → 首稿 Story 生成）

面向读者：需要开发/调试 Idea2Paper 的开发者与维护者。  
本文只覆盖 **从输入 idea 到“第一篇（首稿）story 生成结束”** 的链路；评审（critic/reviewer）、refinement、查重（RAG verifier）属于后续阶段，仅在文末给出指针，不展开。

---

## 0. 一句话总览

**你输入一段 idea 文本** →（可选）Idea Packaging 把它“结构化+改写成更适合召回的 query” → **三路召回系统**从知识图谱里找 Top-K 个 Pattern →（可选）把 `patterns_structured.json` 的增强字段合并进召回结果 → **PatternSelector** 对候选 Pattern 做三维排序并选出本轮要用的 Pattern → **StoryGenerator** 根据（Idea + Pattern 模板 + 约束/技巧）产出结构化 Story JSON（首稿）。

---

## 1. 入口与调用链（你该从哪里读代码）

### 1.1 CLI 入口（最常用）

- 运行入口：`Paper-KG-Pipeline/scripts/idea2story_pipeline.py`
  - `main()`：读入 `user_idea` → 数据加载 → 召回 → 进入 Pipeline（Pattern 选择 + Story 生成 + 后续阶段）
  - `ensure_required_indexes()`：索引预检（novelty/recall offline index/subdomain taxonomy）

> 说明：`Paper-KG-Pipeline/scripts/pipeline/*` 多为**包装层**，真正实现主要在 `Paper-KG-Pipeline/src/idea2paper/*`（或 `src/idea2paper/application/*`）。

补充说明（很容易踩坑）：
- `Paper-KG-Pipeline/scripts/pipeline/*`：为了让 `scripts/idea2story_pipeline.py` 能 `from pipeline import ...` 直接跑起来的包装层（会把 `Paper-KG-Pipeline/src` 加进 `sys.path` 并转发到 `idea2paper` 包）。
- `Paper-KG-Pipeline/src/idea2paper/pipeline/*`：为了让 `from idea2paper.pipeline import ...` 保持稳定 import 路径的转发层。
- **真正实现**主要在：`Paper-KG-Pipeline/src/idea2paper/application/*`。

### 1.2 召回系统入口

- 包装层：`Paper-KG-Pipeline/scripts/recall_system.py`
- 核心实现：`Paper-KG-Pipeline/src/idea2paper/recall/recall_system.py`
  - `class RecallSystem`
  - `recall(self, user_idea: str, verbose: bool = True)`：三路召回融合的主函数

### 1.3 Pattern 选择与 Story 生成入口

Pipeline 编排（首稿 story 在这里生成）：
- `Paper-KG-Pipeline/src/idea2paper/application/pipeline/manager.py`
  - `Idea2StoryPipeline.run()`：
    - Phase 1：`PatternSelector.select()`
    - Phase 2：`StoryGenerator.generate(...)`（首稿生成点）

PatternSelector：
- `Paper-KG-Pipeline/src/idea2paper/application/pipeline/pattern_selector.py`
  - `PatternSelector.select()`：对 recalled patterns 做三维评分与排序

StoryGenerator：
- `Paper-KG-Pipeline/src/idea2paper/application/pipeline/story_generator.py`
  - `StoryGenerator.generate(...)`：首稿生成（无 previous_story/review_feedback 时为“初次生成模式”）
  - `StoryGenerator._build_generation_prompt(...)`：首稿 prompt 组装

（可选）Idea Packaging：
- `Paper-KG-Pipeline/src/idea2paper/application/idea_packaging/packager.py`
  - `IdeaPackager.parse_raw_idea()`：把 raw idea 结构化成 `IdeaBrief` + `retrieval_query`
  - `IdeaPackager.build_pattern_evidence()`：把召回到的 Pattern 信息 + exemplar papers 组装成 evidence pack
  - `IdeaPackager.package_with_pattern()`：用 Pattern evidence 对 idea 做“pattern-guided 重写”
  - `IdeaPackager.judge_best_candidate()`：在多个候选 brief 里挑最优

---

## 2. 链路总流程图（从输入到首稿结束）

```mermaid
flowchart TD
  A[CLI: idea2story_pipeline.py\n输入 user_idea] --> B[load .env + PipelineConfig\n可选 RunLogger]
  B --> C[ensure_required_indexes\n可选：构建/校验 offline index + taxonomy]
  C --> D[加载 nodes_pattern/nodes_paper\n构建 papers_by_id]
  D --> E{IDEA_PACKAGING_ENABLE?}
  E -- 否 --> F[RecallSystem.recall(raw_user_idea)]
  E -- 是 --> E1[IdeaPackager.parse_raw_idea]
  E1 --> E2[RecallSystem.recall(query_a)\n拿 top patterns]
  E2 --> E3[package_with_pattern 生成候选 brief/query]
  E3 --> E4[judge_best_candidate + 可选 recall_focus_score\n二次选择 query_best]
  E4 --> F[RecallSystem.recall(query_best)]
  F --> G[合并 patterns_structured.json\n(skeleton_examples/common_tricks)]
  G --> H[Idea2StoryPipeline.run]
  H --> I[PatternSelector.select\n三维排序 stability/novelty/domain_distance]
  I --> J[选择首个 Pattern\n优先 stability]
  J --> K[StoryGenerator.generate\n初次生成模式]
  K --> L[首稿 Story JSON\n(内存 current_story)]
```

---

## 3. 配置读取规则（开发者必看）

核心配置类：`Paper-KG-Pipeline/src/idea2paper/config.py`（`PipelineConfig`）

### 3.1 配置优先级

`PipelineConfig._get(...)` 的读取顺序是：

1) 环境变量（含 `.env` 注入后的 env）  
2) 用户配置文件 `i2p_config.json`（默认路径，可用 `I2P_CONFIG_PATH` 指定）  
3) 代码默认值

相关实现：
- `.env` 加载：`Paper-KG-Pipeline/src/idea2paper/infra/dotenv.py`
- 用户配置文件路径：`Paper-KG-Pipeline/src/idea2paper/infra/user_config.py`

### 3.2 与召回链路最相关的配置项（建议先从这几个排查）

#### 召回质量/性能

- `I2P_RECALL_USE_OFFLINE_INDEX`（bool）：是否启用 offline embedding 索引（强烈建议用于提速）
- `I2P_RECALL_INDEX_DIR`（path）：offline index 存放目录
- `I2P_RECALL_EMBED_BATCH_SIZE` / `I2P_RECALL_EMBED_MAX_RETRIES` / `I2P_RECALL_EMBED_SLEEP_SEC`：在线 embedding 批量与重试参数
- `I2P_RECALL_AUDIT_ENABLE`（bool）：是否在结果里保存 `recall_audit`
- `I2P_RECALL_AUDIT_TOPN`：审计里 TopN 的截断长度
- `I2P_RECALL_AUDIT_SNIPPET_CHARS`：审计里 idea/paper 文本 snippet 的截断长度（默认 240）
- `I2P_RECALL_AUDIT_IN_EVENTS`（bool）：是否把 `recall_audit` 也写入 `events.jsonl`（便于复盘）

#### 索引预检/自动构建（强相关：你到底在用哪个 index 目录）

- `I2P_INDEX_DIR_MODE`：`manual` / `auto_profile`
  - `manual`：默认固定目录 `Paper-KG-Pipeline/output/recall_index` / `novelty_index`
  - `auto_profile`：默认目录变成 `Paper-KG-Pipeline/output/recall_index__<profile>`（profile 由 `EMBEDDING_MODEL` 推导）
- `I2P_INDEX_AUTO_PREPARE`（bool）：是否在运行前自动 preflight 必需 index（默认 true）
- `I2P_INDEX_ALLOW_BUILD`（bool）：preflight 失败时是否允许自动构建 index（默认 true）

#### Subdomain taxonomy（Path2 子领域归一化，可选但推荐）

- `I2P_SUBDOMAIN_TAXONOMY_ENABLE`（bool）：是否启用 subdomain taxonomy（canonicalize + stoplist）
- `I2P_SUBDOMAIN_TAXONOMY_PATH`（path）：taxonomy 路径（空则默认 `<RECALL_INDEX_DIR>/subdomain_taxonomy.json`）
- `I2P_SUBDOMAIN_TAXONOMY_STOPLIST_MODE`：`drop` / `keep`
  - `drop`：遇到 stoplist 子领域直接丢弃（默认）
  - `keep`：只做 canonicalize，不丢弃 stoplist

#### Idea Packaging（可选增强）

- `I2P_IDEA_PACKAGING_ENABLE`（bool）：是否启用 idea packaging
- `I2P_IDEA_PACKAGING_TOPN_PATTERNS`：第一次召回取多少个 pattern 作为 evidence
- `I2P_IDEA_PACKAGING_MAX_EXEMPLAR_PAPERS`：每个候选 pattern evidence 里最多带多少篇 exemplar paper（默认 8）
- `I2P_IDEA_PACKAGING_CANDIDATE_K`：生成多少个候选 brief/query
- `I2P_IDEA_PACKAGING_SELECT_MODE`：`llm_then_recall` / `recall_only`
- `I2P_IDEA_PACKAGING_FORCE_EN_QUERY`（bool）：是否强制 retrieval query 以英文关键词开头（默认 true）

#### LLM 温度（影响首稿多样性/稳定性）

- `I2P_LLM_TEMPERATURE_PATTERN_SELECTOR`：PatternSelector 的温度（通常较低）
- `I2P_LLM_TEMPERATURE_STORY_GENERATOR`：StoryGenerator 首稿温度（默认 0.7）
- `I2P_LLM_TEMPERATURE_IDEA_PACKAGING_PARSE` / `I2P_LLM_TEMPERATURE_IDEA_PACKAGING_PATTERN_GUIDED` / `I2P_LLM_TEMPERATURE_IDEA_PACKAGING_JUDGE`：Idea Packaging 各子阶段温度（建议 parse/judge 低温）

#### Embedding/LLM 端点（影响“是否会降级到 Jaccard”）

- Embedding：
  - `EMBEDDING_PROVIDER` / `EMBEDDING_API_URL` / `EMBEDDING_MODEL`
  - `EMBEDDING_API_KEY`（secret；通常放 `.env`；若未设置会 fallback 到 `LLM_API_KEY`）
- LLM：
  - `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_API_URL` / `LLM_MODEL`
  - `LLM_API_KEY`（secret；放 `.env`）
  - `LLM_EXTRA_HEADERS_JSON` / `LLM_EXTRA_BODY_JSON`（可选：给代理/网关加 header/body）
  - `LLM_ANTHROPIC_VERSION`（仅 `LLM_PROVIDER=anthropic` 时使用）

### 3.3 Index 目录到底怎么来的？（INDEX_DIR_MODE=auto_profile 时必看）

实现位置：`Paper-KG-Pipeline/src/idea2paper/config.py`（`INDEX_DIR_MODE` 相关逻辑）

当 `I2P_INDEX_DIR_MODE=auto_profile` 时，默认 index 目录会根据 `EMBEDDING_MODEL` 变化：

```python
# Paper-KG-Pipeline/src/idea2paper/config.py (节选)
if INDEX_DIR_MODE == "auto_profile":
    _PROFILE_ID = _compute_profile_id(EMBEDDING_MODEL)  # e.g. Qwen/Qwen3-Embedding-8B -> Qwen_Qwen3-Embedding-8B
    _DEFAULT_RECALL_INDEX_DIR = OUTPUT_DIR / f"recall_index__{_PROFILE_ID}"
else:
    _DEFAULT_RECALL_INDEX_DIR = OUTPUT_DIR / "recall_index"
```

这会导致两个“常见误解”：
- 你以为在用 `output/recall_index__text-embedding-3-small`，但实际 `EMBEDDING_MODEL` 已经改成别的了 → preflight 会认为 mismatch，然后**自动建新目录**或 fallback。
- 你切换 embedding 模型后忘了重建 index → `validate_recall_index()` 会因为 `embedding_model` 不一致而报 mismatch（属于预期行为）。

---

## 4. 数据依赖（召回链路依赖哪些 KG 文件）

召回系统 `RecallSystem.__init__()` 会加载（路径在 `Paper-KG-Pipeline/src/idea2paper/recall/recall_system.py` 顶部常量定义）：

- `Paper-KG-Pipeline/output/nodes_idea.json`
  - 召回用字段（至少）：
    - `idea_id`
    - `description`（用于 embedding/Jaccard）
    - `pattern_ids`（路径1直接用它把 Idea → Pattern）
- `Paper-KG-Pipeline/output/nodes_pattern.json`
  - 用于返回 `pattern_info`，并用于后续 PatternSelector / StoryGenerator
  - 典型字段：
    - `pattern_id`, `name`, `size`, `domain`, `sub_domains`
    - `summary`（dict）：`representative_ideas/common_problems/solution_approaches/story`
    - `exemplar_paper_ids`（Idea Packaging 可能用）
- `Paper-KG-Pipeline/output/nodes_domain.json`
  - 路径2（Domain 相关性）用：`domain_id`, `name`, `paper_count`
- `Paper-KG-Pipeline/output/nodes_paper.json`
  - 路径3（Paper 相似召回）用：
    - `paper_id`, `title`
    - `review_stats.avg_score`（用于 paper quality，若没有则降级到旧 reviews 或默认 0.5）
- `Paper-KG-Pipeline/output/knowledge_graph_v2.gpickle`
  - 召回系统依赖图谱边：
    - Pattern → Domain：`relation == "works_well_in"`（路径2用：`effectiveness/confidence`）
    - Paper → Pattern：`relation == "uses_pattern"`（路径3用：`quality`）
    - Idea → Domain：`relation == "belongs_to"`（路径2兜底）

（可选增强，不是硬依赖）：
- `Paper-KG-Pipeline/output/patterns_structured.json`
  - 在 `idea2story_pipeline.py` 里把它合并进召回结果：
    - `skeleton_examples`：StoryGenerator 首稿 prompt 的“参考论文包装策略”
    - `common_tricks`：后续 refinement 可能用（首稿阶段一般还未注入）

### 4.1 关键中间数据结构（建议开发时重点盯这些对象）

#### A) recalled_patterns（召回输出，进入 pipeline 的主输入）

类型（Python）：
```python
List[Tuple[str, Dict, float]]  # [(pattern_id, pattern_info, final_score), ...]
```

来源：
- `RecallSystem.recall(...)` 的返回值
- 经过 `idea2story_pipeline.py` 合并 `patterns_structured.json` 后，`pattern_info` 会多出 `skeleton_examples/common_tricks`

注意点：
- `pattern_id` 是图谱与 nodes 的唯一键（通常形如 `pattern_123`）
- `pattern_info` 是 `nodes_pattern.json` 对应条目的整条 dict（后续 PatternSelector/StoryGenerator 直接消费它）

#### B) recall_audit（召回审计，用于复盘“为什么召回成这样”）

存放位置：
- 运行结束后的 `Paper-KG-Pipeline/output/pipeline_result.json` → `recall_audit`
- 若启用 run logger：`log/<run_id>/events.jsonl` 中 `type=="event"` 且 `data.event_type=="recall_audit"` 的记录

结构（简化示意，字段可能随版本小幅变化）：
```json
{
  "final_top_k": [
    {
      "pattern_id": "pattern_123",
      "name": "...",
      "final_score": 0.123,
      "path1_score": 0.050,
      "path2_score": 0.020,
      "path3_score": 0.053,
      "cluster_size": 82
    }
  ],
  "path1": {"top_ideas": [...], "pattern_scores_topn": [...]},
  "path2": {
    "top_domains": [...],
    "top_subdomains": [...],
    "candidate_stats": [...],
    "pattern_scores_topn": [...],
    "subdomain_taxonomy_used": true,
    "raw_subdomain_count": 319,
    "canonical_subdomain_count": 60,
    "stoplist_count": 10
  },
  "path3": {"top_papers": [...], "pattern_scores_topn": [...]}
}
```

注意：
- `final_top_k[*].path{1,2,3}_score` **是加权后的贡献**（已经乘上 `PATH{1,2,3}_WEIGHT`），用于直观看“最终得分由哪一路贡献”。

#### C) idea_brief（Idea Packaging 的结构化产物）

来源：`IdeaPackager.parse_raw_idea()` / `package_with_pattern()`

用于：
- PatternSelector / StoryGenerator 的 prompt 中的 `【User Requirements Brief】` 区块（提升“约束一致性”与“可评测性”）

典型 schema：见 `Paper-KG-Pipeline/src/idea2paper/application/idea_packaging/packager.py` 的 prompt 约定。

#### D) current_story（首稿 story，Phase 2 输出）

类型（Python）：
```python
Dict[str, Any]
```

结构：见第 7.3 节（Story JSON schema）。

### 4.2 “相似度到底比的是什么文本？”（决定召回效果的关键）

召回系统在算相似度时，真正进入 Jaccard/Embedding 的文本由以下函数决定：

- `Paper-KG-Pipeline/src/idea2paper/recall/recall_text.py`
  - `build_recall_idea_text(idea)`：当前只用 `idea["description"]`
  - `build_recall_paper_text(paper)`：当前只用 `paper["title"]`
  - `truncate_for_embedding(text, max_len=2000)`：embedding 输入截断
- `Paper-KG-Pipeline/src/idea2paper/recall/tokenize.py`
  - `tokenize()`：非常朴素的 `lower().split()`（粗排 Jaccard 会受它影响）

因此如果你觉得：
- “Paper 相似召回总是很飘”：通常是 `paper.title` 信息不足，可考虑把 abstract/keywords 融入 `build_recall_paper_text`
- “Jaccard 粗排效果差”：通常是 tokenize 过于简单（尤其是混合中英文/符号），可改进分词与归一化

> 备注：目前 `RecallConfig`（TopK、权重、两阶段开关）是写死在 `Paper-KG-Pipeline/src/idea2paper/recall/recall_system.py` 的 `class RecallConfig` 常量里，并非走 env/config；要改召回超参需要改代码。

---

## 5. 详细链路：从输入 idea 到三路召回输出

本节对应代码：`Paper-KG-Pipeline/scripts/idea2story_pipeline.py` + `Paper-KG-Pipeline/src/idea2paper/recall/recall_system.py`

### 5.1 运行前准备：日志与索引预检

在 `idea2story_pipeline.py` 的 `main()` 里：

1) 初始化 `run_id`，可选启用 `RunLogger`：
   - 日志目录：`log/<run_id>/`
   - 文件：
     - `meta.json`：运行元信息
     - `events.jsonl`：结构化事件（比如 recall_audit、idea_packaging）
     - `llm_calls.jsonl`：LLM 调用（prompt 会按 `LOG_MAX_TEXT_CHARS` 截断）
     - `embedding_calls.jsonl`：embedding 调用
   - 实现：`Paper-KG-Pipeline/src/idea2paper/infra/run_logger.py`
   - `events.jsonl` 的 record 结构（便于 grep/解析）：
     - 每行：`{"ts": "...", "run_id": "...", "type": "event", "data": {"event_type": "...", "payload": {...}}}`
     - 其中 `event_type` 在 `data.event_type`（不是顶层字段）

2) `ensure_required_indexes(logger)`（如果 `PipelineConfig.INDEX_AUTO_PREPARE=true`）：
   - novelty index（不属于首稿范围，但会在这里预检）
   - recall offline index（如果 `RECALL_USE_OFFLINE_INDEX=true`）
   - subdomain taxonomy（如果 `SUBDOMAIN_TAXONOMY_ENABLE=true`）
   - 预检/锁机制实现：
     - index 校验 + 锁：`Paper-KG-Pipeline/src/idea2paper/infra/index_preflight.py`
       - `validate_novelty_index(...)` / `validate_recall_index(...)`
       - `acquire_lock(...)`（生成/持有 lock file）
     - taxonomy 校验/构建：`Paper-KG-Pipeline/src/idea2paper/infra/subdomain_taxonomy.py`
       - `validate_subdomain_taxonomy(...)` / `build_subdomain_taxonomy(...)`
   - 自动构建脚本（index）：
     - novelty：`Paper-KG-Pipeline/scripts/tools/build_novelty_index.py`
     - recall：`Paper-KG-Pipeline/scripts/tools/build_recall_index.py`

> 重要：预检阶段会在目录下写锁文件，避免并发构建互相踩踏：
> - novelty/recall index：`<index_dir>/.build.lock`
> - subdomain taxonomy：`<taxonomy_dir>/.subdomain_taxonomy.build.lock`

预检/校验规则速记（为什么会提示 mismatch/incomplete）：
- novelty：校验 `embedding_model` + `nodes_paper_hash` + `paper_meta.jsonl` 行数与 `paper_emb.npy` 行数一致。
- recall：校验 `embedding_model` + `nodes_idea_hash/nodes_paper_hash` + meta/emb 行数一致。

### 5.2 RecallSystem 初始化（数据加载、缓存与可选 offline index）

入口：`RecallSystem()`（在 `idea2story_pipeline.py` 中实例化）

初始化阶段做的事（见 `RecallSystem.__init__()`）：

1) 读入 nodes JSON 与图谱：
   - ideas/patterns/domains/papers
   - `knowledge_graph_v2.gpickle`
2) 构建关键映射表：
   - `idea_id_to_idea`, `pattern_id_to_pattern`, `domain_id_to_domain`, `paper_id_to_paper`
3) 为路径2准备 Domain→Pattern 边索引与子领域压缩池：
   - 从图谱里找 `relation=="works_well_in"` 的 Pattern→Domain 边
   - 统计 Pattern 的 `sub_domains` 形成“候选子领域池”（默认最多 50 个）
4) 可选加载 Subdomain taxonomy（用于把同义子领域归一）：
   - 由 `PipelineConfig.SUBDOMAIN_TAXONOMY_ENABLE` 控制
   - 默认路径：`<RECALL_INDEX_DIR>/subdomain_taxonomy.json`
   - stoplist 行为：由 `PipelineConfig.SUBDOMAIN_TAXONOMY_STOPLIST_MODE` 控制（`drop/keep`）
   - 实现位置：
     - taxonomy 校验：`Paper-KG-Pipeline/src/idea2paper/infra/subdomain_taxonomy.py` → `validate_subdomain_taxonomy(...)`
     - taxonomy 应用：`Paper-KG-Pipeline/src/idea2paper/recall/recall_system.py` → `_map_subdomains(...)`
5) Token cache（用于两阶段粗排 Jaccard）：
   - `to_token_set(build_recall_idea_text(...))`
   - `to_token_set(build_recall_paper_text(...))`
6) 可选 offline index：
   - 由 `PipelineConfig.RECALL_USE_OFFLINE_INDEX` 控制
   - 加载逻辑在 `_load_offline_index()` 与 `_load_index_kind()`
   - 期望文件（位于 `RECALL_INDEX_DIR`）：
     - `idea_emb.npy` / `idea_meta.jsonl` / `idea_manifest.json`
     - `paper_emb.npy` / `paper_meta.jsonl` / `paper_manifest.json`
   - 关键校验（否则会 fallback）：
     - `manifest.embedding_model == EMBEDDING_MODEL`
     - `manifest.nodes_{kind}_hash == sha256(nodes_{kind}.json)`

> 两阶段召回的粗排（Jaccard）成本主要是 CPU + 遍历候选；精排（embedding）成本主要是 embedding API/模型。

#### （可选）Idea Packaging：两次召回 + 选择 query_best（不改 KG）

Idea Packaging 的编排当前在 `Paper-KG-Pipeline/scripts/idea2story_pipeline.py`（`main()`）中完成，目标是：
- 把 `raw_user_idea` 解析成更“可召回”的 `retrieval_query`（通常更结构化、英文关键词更明确）
- 用第一次召回到的 Pattern evidence 引导 query/brief 的改写
- 选出 `query_best/brief_best` 供最终召回 + 后续生成使用

核心流程（代码位置：`Paper-KG-Pipeline/scripts/idea2story_pipeline.py`）：
1) `brief_a, query_a = packager.parse_raw_idea(raw_user_idea)`
2) `first_recall = recall_system.recall(query_a)`
3) 对 `first_recall[:TOPN]` 的前 `CANDIDATE_K` 个 Pattern：
   - `evidence = packager.build_pattern_evidence(...)`（会带 `summary` + exemplar papers）
   - `brief_c, query_c = packager.package_with_pattern(raw_user_idea, brief_a, evidence)`
4) 先用 `judge_best_candidate()` 按“忠实/完整/可操作”选 `best_index`
5) （可选）再用 `_recall_focus_score(recall_audit)` 对每个 `query_c` 再跑一次召回做二次选择：
   - `I2P_IDEA_PACKAGING_SELECT_MODE=recall_only`：完全按 recall_focus_score 选
   - `I2P_IDEA_PACKAGING_SELECT_MODE=llm_then_recall`：只有 recall_focus_score 明显更好（默认阈值 +0.05）才覆盖 LLM judge 的选择

`recall_focus_score` 的定义（节选，实际实现见 `Paper-KG-Pipeline/scripts/idea2story_pipeline.py`）：
```python
def _recall_focus_score(recall_audit: dict | None) -> float:
    # 基于 path2 的 candidate_stats: candidates_before/after 的平均收敛比例
    ratios = []
    for stat in (recall_audit or {}).get("path2", {}).get("candidate_stats", []) or []:
        if not stat:
            continue
        before = int(stat.get("candidates_before", 0) or 0)
        after = int(stat.get("candidates_after", 0) or 0)
        if before > 0:
            ratios.append((before - after) / float(before))
    return sum(ratios) / len(ratios) if ratios else 0.0
```

落盘/可观测性：
- `Paper-KG-Pipeline/output/pipeline_result.json` 会包含 `idea_packaging`（完整 meta，包括 `query_best/brief_best`、候选列表、judge 信息、recall_scores）
- 若启用 RunLogger：`log/<run_id>/events.jsonl` 会有 `data.event_type=="idea_packaging"`（失败则 `idea_packaging_failed`）

### 5.3 三路召回（Path1/Path2/Path3）

主函数：`RecallSystem.recall(user_idea, verbose=True)`

#### Path1：Idea → Idea → Pattern（相似 Idea 召回）

实现：`_recall_path1_similar_ideas(user_idea)`

核心逻辑：

1) 粗排：对全量 idea 做 Jaccard，取 `COARSE_RECALL_SIZE`（默认 100）
2) 精排：对粗排候选用 embedding 重排，取 `PATH1_TOP_K_IDEAS`（默认 20）
3) 直接从这些 idea 的 `pattern_ids` 累加 Pattern 分数（按相似度加权）
4) 输出 `PATH1_FINAL_TOP_K`（默认 10）个 Pattern

实现细节（关键阈值/降级）：
- 粗排阶段只收集 `sim > 0` 的候选。
- 精排阶段会优先用 offline index（如果可用）批量计算 cosine；若 query embedding 获取失败，会降级为对候选逐个 Jaccard。

#### Path2：Idea → Domain → Pattern（领域相关性召回）

实现：`_recall_path2_domain_patterns(user_idea, top_ideas=...)`

核心逻辑：

1) 一级 Domain 匹配：
   - Domain 表达文本 = `domain.name` + 压缩后的 `Sub-domains pool`
   - embedding 可用则用 embedding 相似度，否则用 Jaccard
2) 子领域（sub_domain）精匹配：
   - 对每个 top domain，计算 query 与候选子领域的相似度，取 top-k
3) Pattern 候选收敛：
   - 若命中子领域：只在该子领域对应的 Pattern 集合里打分（减少候选）
   - 否则：使用该 domain 下的全量 Pattern
4) 打分（按边属性）：
   - `score = domain_weight * max(effectiveness,0.1) * confidence * (1 + boost * max_sd_sim)`
5) 输出 `PATH2_FINAL_TOP_K`（默认 5）个 Pattern

实现细节（fallback 很重要）：
- 如果一级 Domain 完全没有命中（top_domains 为空）且 path1 有 top_ideas：会用 top-1 idea 在图谱里的 `Idea -> Domain`（`relation=="belongs_to"`）做兜底 domain（权重来自边上 `weight`）。
- 子领域命中使用的是 canonicalized subdomain（见 `_map_subdomains(...)`），并可能受 stoplist 影响（`STOPLIST_MODE=drop` 时会过滤掉过泛子领域）。

#### Path3：Idea → Paper → Pattern（相似 Paper 召回）

实现：`_recall_path3_similar_papers(user_idea)`

核心逻辑：

1) 粗排：用 Jaccard 计算 `user_idea` 与 `paper.title`
2) 精排：embedding 重排，取 top papers（默认 20）
3) Paper 质量：
   - 优先 `paper.review_stats.avg_score`（0~1）
   - 否则尝试旧结构 `paper.reviews[*].overall_score`
   - 再否则默认 0.5
4) 在图谱里找 `Paper -> Pattern` 的 `relation=="uses_pattern"`，并用边上 `quality` 加权

实现细节（两个阈值直接决定“这一路有没有信号”）：

```python
# Paper-KG-Pipeline/src/idea2paper/recall/recall_system.py (节选)
# 粗排：只保留 Jaccard > 0.05 的 paper 进入候选池
if sim > 0.05:
    coarse_similarities.append((paper_id, sim))

# 精排：embedding 相似度过滤掉 sim <= 0.1 的 paper
if sim > 0.1:
    fine_similarities.append((paper_id, sim, quality, sim * quality))
```

> 提示：当 user_idea/query 很长、tokenize 又简单时，`Jaccard > 0.05` 往往会让候选池极小，导致 path3 基本“失声”。调试时优先看 `recall_audit.path3.top_papers` 的数量。

### 5.4 三路融合与审计（Recall Audit）

融合发生在 `RecallSystem.recall()`：

- 三路分数按权重线性融合（默认）：
  - `PATH1_WEIGHT=0.4`
  - `PATH2_WEIGHT=0.2`
  - `PATH3_WEIGHT=0.4`
- 输出 `FINAL_TOP_K`（默认 10）个 Pattern，返回结构：
  - `[(pattern_id, pattern_info, final_score), ...]`

审计信息：

- `RecallSystem.last_audit` 会记录：
  - 各路 top candidates（top ideas / top domains+subdomains / top papers）
  - final_top_k 的拆分贡献（path1/path2/path3）
- `idea2story_pipeline.py` 会把 `last_audit` 放到：
  - `pipeline_result.json` 的 `recall_audit` 字段
  - 可选写入 `RunLogger.events.jsonl`（由 `PipelineConfig.RECALL_AUDIT_IN_EVENTS` 控制）

---

## 6. 从召回结果到 Pattern 选择（Phase 1）

本节对应代码：
- 召回结果传入 pipeline：`Paper-KG-Pipeline/scripts/idea2story_pipeline.py`
- 选择逻辑：`Paper-KG-Pipeline/src/idea2paper/application/pipeline/pattern_selector.py`

### 6.1 patterns_structured.json 合并（增强 Pattern 信息）

发生在 `idea2story_pipeline.py`：

- 如果存在 `Paper-KG-Pipeline/output/patterns_structured.json`：
  - 以 `pattern_<id>` 的方式构造映射
  - 对每个召回 Pattern，合并：
    - `skeleton_examples`
    - `common_tricks`

关键实现（pattern_id 的拼接规则）：

```python
# Paper-KG-Pipeline/scripts/idea2story_pipeline.py (节选)
for p in patterns_structured:
    pattern_id = f"pattern_{p.get('pattern_id')}"  # 注意：这里的 p['pattern_id'] 通常是数字 id
    structured_map[pattern_id] = p
```

这一步的目的：
- 让首稿 Story prompt 能引用更具体的“参考论文包装策略”（`skeleton_examples`）
- 为后续 refinement 提供可注入技巧池（`common_tricks`）

### 6.2 PatternSelector 三维排序

主函数：`PatternSelector.select()`

输入：
- `recalled_patterns: [(pattern_id, pattern_info, recall_score), ...]`
- `user_idea`（用于 LLM 判断 domain_distance）
- 可选 `idea_brief`

输出：
```python
{
  "stability": [(pid, pinfo, meta), ...],        # stability_score 降序
  "novelty": [(pid, pinfo, meta), ...],          # novelty_score 降序
  "domain_distance": [(pid, pinfo, meta), ...],  # domain_distance 升序（越小越贴近用户 idea）
}
```

评分方式：
- 对 Top-20 patterns 调 LLM 产出 `stability_score/novelty_score/domain_distance`（0~1）
  - 组 prompt 的位置：`_call_llm_for_multidim_scoring(...)`
  - idea_brief 注入位置：`_build_idea_brief_block()`（把 constraints/keywords 等放进 prompt）
- LLM 不可用时 fallback 到规则：`_fallback_multidim_scoring(pattern_size)`

Pipeline 首个 Pattern 的选择策略（见 `application/pipeline/manager.py`）：
- 优先使用 `ranked_patterns["stability"][0]`
- 若 stability 为空，fallback 到 novelty，再 fallback 到其他维度

---

## 7. 首稿 Story 生成（Phase 2：第一篇 story 生成结束点）

本节对应代码：`Paper-KG-Pipeline/src/idea2paper/application/pipeline/story_generator.py`

首稿生成发生在：
- `Paper-KG-Pipeline/src/idea2paper/application/pipeline/manager.py`
  - `Idea2StoryPipeline.run()` 中的：
    - `current_story = self.story_generator.generate(pattern_id, pattern_info, constraints, injected_tricks)`

### 7.1 初次生成模式 vs 修正模式

`StoryGenerator.generate(...)` 会根据参数决定模式：

- 初次生成模式（首稿）：`previous_story is None` 且 `review_feedback is None`
  - 走 `_build_generation_prompt(pattern_info, constraints, injected_tricks)`
  - 使用 `PipelineConfig.LLM_TEMPERATURE_STORY_GENERATOR`

- 增量修正模式（后续阶段）：同时提供 `previous_story` 与 `review_feedback`
  - 走 `_build_refinement_prompt(...)`
  - 本文不展开

### 7.2 首稿 Prompt 组装要点（你想改“首稿质量”主要改这里）

`_build_generation_prompt(...)` 主要从 `pattern_info` 提取：

- `pattern_info["summary"]`（dict）：
  - `representative_ideas`（用于给模型“这个 pattern 常见想法是什么”）
  - `common_problems`（用于给模型“这个 pattern 常见问题是什么”）
  - `solution_approaches`（用于构造方法骨架）
  - `story`（用于“包装策略/叙事模板”）
- `pattern_info["skeleton_examples"]`（若存在）：
  - 用于“参考论文的包装策略”（problem_framing/gap/method_story 等截断摘要）
- `constraints` / `injected_tricks`（首稿阶段通常为空，但接口已支持）
- `idea_brief`（若启用了 idea packaging，会提供更结构化的用户约束块）

实现细节（截断数量会影响“信息密度”与 prompt 长度）：
- 见 `Paper-KG-Pipeline/src/idea2paper/application/pipeline/story_generator.py` → `StoryGenerator._build_generation_prompt(...)`：
  - `representative_ideas[:3]`
  - `common_problems[:3]`
  - `solution_approaches[:3]`
  - `story[:2]`
  - `skeleton_examples[:2]`

### 7.3 首稿输出结构（Story JSON schema）

StoryGenerator 期望 LLM 返回纯 JSON，并解析为：

```json
{
  "title": "...",
  "abstract": "...",
  "problem_framing": "...",
  "gap_pattern": "...",
  "solution": "...",
  "method_skeleton": "Step 1; Step 2; Step 3",
  "innovation_claims": ["Claim 1", "Claim 2", "Claim 3"],
  "experiments_plan": "..."
}
```

解析逻辑：
- `_parse_story_response(response)`（会做 JSON 提取与字段清洗）
- `_print_story(story)`（会把首稿打印到控制台）

因此，“第一篇 story 生成结束”在 runtime 上的可观测结果是：
- 控制台输出完整 story 字段
- 若启用 RunLogger：`log/<run_id>/llm_calls.jsonl` 里可以看到该次调用的 prompt 与返回（可能截断）

---

## 8. 常见调试点（只针对首稿阶段）

### 8.1 “召回看起来不对 / 总是召回很偏的 pattern”

优先排查：

1) embedding 是否可用（不可用会降级到 Jaccard，质量会明显下降）
   - embedding 相关实现：`Paper-KG-Pipeline/src/idea2paper/infra/embeddings.py`
   - 召回系统降级提示：`Paper-KG-Pipeline/src/idea2paper/recall/recall_system.py` 内 `_get_embedding/_batch_embeddings` 相关打印
2) 是否启用了 offline index（大幅减少实时 embedding 计算）
   - 开关：`I2P_RECALL_USE_OFFLINE_INDEX=1`
   - 构建：`python Paper-KG-Pipeline/scripts/tools/build_recall_index.py --resume`
   - 是否真的“用上了”：看 `log/<run_id>/events.jsonl` 里是否出现 `data.event_type=="recall_offline_index_used"`；若出现 `recall_offline_index_fallback`，说明发生了 mismatch/缺文件/缺 candidate 等回退
   - 注意：offline index 只覆盖 Path1/Path3 的候选 idea/paper 向量；Path2 的 domain/subdomain 向量仍会走在线 embedding（或降级到 Jaccard）
3) 查看 `recall_audit`：
   - `Paper-KG-Pipeline/output/pipeline_result.json` 的 `recall_audit`
   - 或 `log/<run_id>/events.jsonl` 中 `type=="event"` 且 `data.event_type=="recall_audit"` 的记录
4) Path3 “失声”排查（非常常见）：
   - 看 `recall_audit.path3.top_papers` 数量：若极少/为 0，多半是被粗排阈值 `Jaccard > 0.05` 过滤（见 `Paper-KG-Pipeline/src/idea2paper/recall/recall_system.py` 的 Path3 粗排）
   - 长 query + 朴素 tokenize 往往会把 Jaccard 拉得很低（候选池过小导致 path3 没贡献）
5) Subdomain taxonomy 是否生效（Path2 子领域映射）：
   - 看 `recall_audit.path2.subdomain_taxonomy_used` 与 raw/canonical/stoplist 统计
   - 看 `log/<run_id>/events.jsonl` 是否有 `subdomain_taxonomy_preflight_*`（预检/构建）以及 RecallSystem 初始化阶段的 `subdomain_taxonomy_missing/subdomain_taxonomy_mismatch`
6) index 目录/模型 profile 是否一致（auto_profile 容易踩坑）：
   - 看 `log/<run_id>/events.jsonl` 中 `index_preflight_start` 的 `index_dir_mode/recall_index_dir/embedding_model`
   - 典型现象：你以为在用某个 `output/recall_index__...`，但实际上 `EMBEDDING_MODEL` 变了，程序会切到另一个目录并可能触发自动构建

### 8.2 “卡住很久 / 很慢”

首稿阶段最常见的慢点：

- 在线 embedding：召回 path1/path2/path3 的精排（取决于是否成功批量、网络是否稳定）
- PatternSelector：对 Top-20 patterns 的 LLM 评分（一次一个 pattern）
- StoryGenerator：首稿 prompt 很长（特别是有 `skeleton_examples` 时），LLM 响应慢

提速建议（不改代码的前提下）：

- 启用 offline recall index：`I2P_RECALL_USE_OFFLINE_INDEX=1`
- 减少在线 embedding 重试/睡眠：调小 `I2P_RECALL_EMBED_MAX_RETRIES` 与 `I2P_RECALL_EMBED_SLEEP_SEC`
- 关闭自动 preflight（开发期快速迭代）：`I2P_INDEX_AUTO_PREPARE=0`（需要你自己保证 index/taxonomy 已就绪）
- 关闭 Idea Packaging（它会额外引入多次召回 + 多次 LLM 调用）：`I2P_IDEA_PACKAGING_ENABLE=0`
- 需要更激进提速时（开发期）：在本地将 `PatternSelector` 的 Top-20 调整为更小（需要改代码）

---

## 9. 如何“只跑到首稿结束”（开发者定位问题时很有用）

目前默认入口 `idea2story_pipeline.py` 会跑完整 pipeline（包含后续 critic/refinement/verifier）。如果你只想验证“召回 + 选 pattern + 首稿生成”：

1) 最简单方式：直接在控制台观察 `Phase 2: Initial Story Generation` 之后打印出来的 story（首稿已生成）
2) 更工程化方式（需要少量改动）：在 `application/pipeline/manager.py` 的 `Phase 2` 后 `return`（开发分支用，不建议提交到主分支）

---

## 10. 后续阶段指针（不在本文范围）

从首稿进入后续阶段的入口在：

- `Paper-KG-Pipeline/src/idea2paper/application/pipeline/manager.py`
  - Phase 3：`self.critic.review(current_story, context=...)`
  - Phase 3.x：`self.refinement_engine.refine_with_idea_fusion(...)`
  - Phase 4：`self.verifier.verify(...)` / novelty checker

如需理解新 reviewer/critic 机制，请看：
- `MULTIAGENT_REVIEW_zh.md`
- `REVIEWER_SYSTEM_QUALITY_MODE.md`
