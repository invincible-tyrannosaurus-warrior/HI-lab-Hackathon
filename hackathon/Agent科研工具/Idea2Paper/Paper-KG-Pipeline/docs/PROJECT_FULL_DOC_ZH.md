# Idea2Paper 项目总结文档

> **说明**：脚本已分类整理到 `scripts/tools/` 与 `scripts/demos/`。旧路径（如 `scripts/build_entity_v3.py`）仍可通过兼容薄壳运行。

## 📋 项目概述

**项目名称**: Idea2Paper - 基于知识图谱的学术论文自动生成系统

**核心目标**: 将用户的研究Idea自动转化为符合顶会(ICLR)标准的论文Story

**技术栈**:
- 知识图谱: NetworkX
- 向量检索: Embedding (Qwen3-Embedding-4B)
- 大语言模型: Qwen3-14B, Qwen2.5-7B-Instruct
- 数据源: ICLR 2025论文数据集(8,285篇)

---

## 1. 系统架构

### 1.1 整体流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          【Idea2Paper 完整流程】                          │
└─────────────────────────────────────────────────────────────────────────┘

用户输入Idea
    │
    ├──────────────────────────────────────────────────────────────────────┐
    │                      【第一阶段: 知识图谱构建】                        │
    │                      (一次性构建,后续复用)                            │
    ├──────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  1. 加载ICLR论文数据 (8,285篇)                                        │
    │      ↓                                                                 │
    │  2. 构建4类节点                                                        │
    │      ├─ Idea节点 (8,284个)                                            │
    │      ├─ Pattern节点 (124个, LLM增强)                                  │
    │      ├─ Domain节点 (98个)                                             │
    │      └─ Paper节点 (8,285个)                                           │
    │      ↓                                                                 │
    │  3. 构建边关系 (444,872条)                                            │
    │      ├─ 基础连接边 (Paper→Idea/Pattern/Domain)                       │
    │      └─ 召回辅助边 (Idea→Domain, Pattern→Domain)                     │
    │      ↓                                                                 │
    │  4. 输出知识图谱                                                       │
    │                                                                        │
    └──────────────────────────────────────────────────────────────────────┘
    │
    ├──────────────────────────────────────────────────────────────────────┐
    │                      【第二阶段: 三路召回】                            │
    │                      (每次运行,约27秒)                                │
    ├──────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  ┌─────────────┬─────────────┬─────────────┐                        │
    │  │  路径1      │   路径2     │   路径3     │                        │
    │  │ 相似Idea    │  领域相关   │ 相似Paper   │                        │
    │  │ (权重0.4)   │  (权重0.2)  │ (权重0.4)   │                        │
    │  └─────────────┴─────────────┴─────────────┘                        │
    │       │              │              │                                 │
    │       │              │              │                                 │
    │  粗排: Jaccard   匹配Domain   粗排: Jaccard                          │
    │  Top-100         Top-5        Top-100                                │
    │       ↓              ↓              ↓                                 │
    │  精排: Embedding 查找Pattern  精排: Embedding                        │
    │  Top-10          works_well   Top-20                                 │
    │       ↓              ↓              ↓                                 │
    │  获取Pattern     获取Pattern   获取Pattern                           │
    │  得分            得分           得分                                  │
    │       │              │              │                                 │
    │       └──────────────┴──────────────┘                                │
    │                      ↓                                                │
    │              加权融合 & 精排                                          │
    │                      ↓                                                │
    │              Top-10 Pattern                                           │
    │                                                                        │
    └──────────────────────────────────────────────────────────────────────┘
    │
    ├──────────────────────────────────────────────────────────────────────┐
    │                    【第三阶段: Story生成与修正】                       │
    │                    (3-10分钟)                                         │
    ├──────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  1. Pattern多维度分类                                                 │
    │      ├─ Stability (稳健型)                                            │
    │      ├─ Novelty (新颖型)                                              │
    │      └─ Cross-Domain (跨域型)                                         │
    │      ↓                                                                 │
    │  2. 选择初始Pattern → 生成初稿Story                                   │
    │      ↓                                                                 │
    │  3. Critic多角色评审 (Methodology/Novelty/Storyteller)                │
    │      ↓                                                                 │
    │  4. 判断: 评分 >= 7.0?                                                │
    │      ├─【是】→ 进入第四阶段                                           │
    │      └─【否】→ 智能修正                                               │
    │                 │                                                      │
    │                 ├─ 新颖性停滞? → 【新颖性模式】                       │
    │                 │   ├─ 遍历Novelty Pattern                            │
    │                 │   ├─ Idea Fusion (概念融合)                         │
    │                 │   ├─ Story Reflection (质量评估)                    │
    │                 │   ├─ 重新生成Story                                  │
    │                 │   ├─ Critic评审                                     │
    │                 │   ├─ 分数下降? → 回滚                               │
    │                 │   └─ 兜底: 选最高分版本                             │
    │                 │                                                      │
    │                 └─ 普通修正 → 注入互补Tricks                          │
    │                     ├─ 缺新颖性 → 长尾注入 (Rank 5-10)               │
    │                     ├─ 缺稳定性 → 头部注入 (Rank 1-3)                │
    │                     └─ 返回步骤2                                      │
    │                                                                        │
    └──────────────────────────────────────────────────────────────────────┘
    │
    ├──────────────────────────────────────────────────────────────────────┐
    │                      【第四阶段: RAG查重】                             │
    │                      (约30秒)                                         │
    ├──────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  1. 提取关键方法 → 检索近3年顶会论文                                  │
    │      ↓                                                                 │
    │  2. 判断: 相似度 > 0.75?                                              │
    │      ├─【否】→ 输出Final Story ✅                                     │
    │      └─【是】→ 撞车! Pivot规避                                        │
    │                 ├─ 分析撞车点                                         │
    │                 ├─ 生成约束 (禁用技术/领域迁移)                       │
    │                 └─ 返回第三阶段步骤2                                  │
    │                                                                        │
    └──────────────────────────────────────────────────────────────────────┘
    │
    ▼
输出Final Story (JSON格式)
```

**流程说明**:
- **第一阶段**: 离线构建,只需运行一次
- **第二阶段**: 实时召回,13倍提速(27秒)
- **第三阶段**: 核心生成,智能修正机制
- **第四阶段**: 查重验证,避免撞车

### 1.2 核心模块

| 层级 | 模块 | 文件/脚本 | 作用 |
|------|------|----------|------|
| **数据层** | 知识图谱构建 | `build_entity_v3.py`, `build_edges.py` | 构建节点和边 |
| **召回层** | 三路召回系统 | `recall_system.py` | 检索相关Pattern |
| **生成层** | Pattern选择 | `pattern_selector.py` | 多维度分类Pattern |
| **生成层** | Idea Fusion | `planner.py` | 融合创新Idea |
| **生成层** | Story生成 | `story_generator.py` | 生成论文Story |
| **生成层** | Story反思 | `story_reflector.py` | 评估融合质量 |
| **生成层** | Critic评审 | `critic.py` | 多角色评审 |
| **生成层** | 智能修正 | `refinement.py` | 迭代优化 |
| **生成层** | RAG查重 | `verifier.py` | 查重与规避 |
| **编排层** | Pipeline管理 | `manager.py`, `idea2story_pipeline.py` | 流程编排 |

---

## 2. 知识图谱构建

### 2.1 数据规模

```
知识图谱统计:
├─ 节点总数: 16,791
│  ├─ Idea:    8,284 (100%覆盖)
│  ├─ Pattern: 124 (聚类生成)
│  ├─ Domain:  98 (聚合生成)
│  └─ Paper:   8,285
└─ 边总数:   444,872
   ├─ 基础连接边: ~25,000
   └─ 召回辅助边: ~420,000
```

### 2.2 节点定义

**Idea节点**: 论文的核心创新点
```json
{
  "idea_id": "idea_0",
  "description": "核心想法描述...",
  "base_problem": "基础问题...",
  "solution_pattern": "解决方案...",
  "pattern_ids": ["pattern_9", ...]
}
```

**Pattern节点**: 写作套路/方法模板
```json
{
  "pattern_id": "pattern_24",
  "name": "Reframing Graph Learning Scalability",
  "size": 331,
  "llm_enhanced_summary": {
    "representative_ideas": "归纳性总结...",
    "common_tricks": ["技巧1", "技巧2"]
  }
}
```

**Domain节点**: 研究领域
```json
{
  "domain_id": "domain_0",
  "name": "Natural Language Processing",
  "paper_count": 1076,
  "sub_domains": ["Text Classification", ...]
}
```

**Paper节点**: 具体论文
```json
{
  "paper_id": "RUzSobdYy0V",
  "title": "Quantifying and Mitigating...",
  "domain": "Fairness & Accountability",
  "idea": "核心想法...",
  "pattern_id": "pattern_9"
}
```

### 2.3 边定义

**基础连接边**:
- `Paper → Idea` (implements): 论文实现了该Idea
- `Paper → Pattern` (uses_pattern): 论文使用了该Pattern
- `Paper → Domain` (in_domain): 论文属于该领域

**召回辅助边**:
- `Idea → Domain` (belongs_to): Idea所属领域,权重=占比
- `Pattern → Domain` (works_well_in): Pattern在该领域的效果,权重=effectiveness
- `Idea → Paper` (similar_to_paper): 相似度权重(路径3实时计算)

### 2.4 运行方式

```bash
# 1. 构建节点
python scripts/build_entity_v3.py
# 输出: output/nodes_*.json (4个文件)

# 2. 构建边
python scripts/build_edges.py
# 输出: output/edges.json, output/knowledge_graph_v2.gpickle
```

**执行时间**: 节点构建15分钟(含LLM增强) + 边构建3分钟

---

## 3. 三路召回系统

### 3.1 召回策略

| 路径 | 匹配对象 | 捕捉维度 | 权重 | 召回数量 |
|------|---------|---------|------|---------|
| **路径1** | Idea Description | 核心思想相似性 | 0.4 | Top-10 Pattern |
| **路径2** | Domain & Sub-domains | 领域泛化能力 | 0.2 | Top-5 Pattern |
| **路径3** | Paper Title | 研究主题相似性 | 0.4 | Top-10 Pattern |

### 3.2 两阶段召回优化

**性能对比**:
```
全量Embedding: ~7分钟 (8,284次API调用)
两阶段召回:   ~27秒 (100次API调用)
提速比:        13倍
```

**流程**:
```
粗排: Jaccard快速筛选 Top-100 (毫秒级)
    ↓
精排: Embedding精确排序 Top-10/20 (~27秒)
```

### 3.3 相似度计算

**Jaccard相似度**(粗排):
```python
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

**Embedding相似度**(精排):
```python
Cosine(A, B) = dot(emb_A, emb_B) / (norm(emb_A) * norm(emb_B))
```

### 3.4 运行方式

```bash
# 独立运行
python scripts/simple_recall_demo.py "你的研究Idea"

# 作为类使用
from recall_system import RecallSystem
system = RecallSystem()
results = system.recall(user_idea, verbose=True)
```

**输出**: Top-10 Pattern列表,每个包含(pattern_id, pattern_info, score)

---

## 4. Idea2Story Pipeline

### 4.1 核心机制

#### (1) Pattern多维度分类

**目标**: 确保Pattern多样性

**维度**:
- **Stability** (稳健型): Rank Top-3 + Cluster Size ≥ 15
- **Novelty** (新颖型): Cluster Size < 10
- **Cross-Domain** (跨域型): 来自路径2/3 + Domain不同

#### (2) Idea Fusion

**目标**: 概念层面的有机融合,而非技术堆砌

**流程**:
```
原Idea + 新Pattern → LLM生成融合Idea
    ↓
融合Idea包含:
  - fused_core_idea: 融合后的核心想法
  - conceptual_bridge: 概念桥梁
  - reframed_problem: 重构后的问题
  - innovation_angle: 独特创新点
```

**示例**:
```
原Idea: 使用大模型做数据增强
新Pattern: 课程学习
融合Idea: 基于LLM生成的难度自适应课程学习框架
```

#### (3) Story Reflection

**目标**: 评估融合质量,确保概念统一

**评分**:
```
fusion_quality = 0.4 × 连贯性 + 0.4 × 融合丰富度 + 0.2 × Fusion Idea奖励
```

**阈值**: `fusion_quality >= 0.65` 认为融合成功

#### (4) Critic多角色评审

**角色**:
- **Reviewer A** (Methodology): 技术合理性
- **Reviewer B** (Novelty): 创新性
- **Reviewer C** (Storyteller): 叙事完整性

**通过标准**: 平均分 >= 7.0

#### (5) 智能修正

**新颖性模式**:
- **触发**: 新颖性分数停滞(≤ 上一轮 + 0.5)
- **流程**: 遍历所有Novelty Pattern,每个都经过Fusion→Reflection→生成→Critic
- **兜底**: 选择最高分版本

**分数退化回滚**:
- **触发**: 任一维度分数下降 > 0.1
- **流程**: 恢复Story + 标记失败 + 删除Tricks + 继续迭代

**普通修正**:
- **长尾注入**: 缺新颖性 → 注入Rank 5-10的冷门Pattern
- **头部注入**: 缺稳定性 → 注入Rank 1-3的成熟Pattern

#### (6) RAG查重与规避

**查重**: 检索近3年顶会论文,相似度 > 0.75 认为撞车

**规避**: Pivot策略生成约束(领域迁移、设定限制等),重新生成Story

### 4.2 运行方式

```bash
python scripts/idea2story_pipeline.py "你的研究Idea"
```

**输出**:
```
output/
├── final_story.json          # 最终论文Story
├── pipeline_result.json      # 完整流程结果
└── log.json                  # 详细日志
```

**执行时间**: 3-10分钟(取决于迭代次数)

---

## 5. 参数配置总览

### 5.1 知识图谱构建

```python
# scripts/build_entity_v3.py

# 数据源路径
DATA_DIR = PROJECT_ROOT / "data" / "ICLR_25"
ASSIGNMENTS_FILE = DATA_DIR / "assignments.jsonl"
CLUSTER_LIBRARY_FILE = DATA_DIR / "cluster_library_sorted.jsonl"
PATTERN_DETAILS_FILE = DATA_DIR / "iclr_patterns_full.jsonl"

# LLM API配置（该构图脚本为 legacy 示例；如需启用 LLM 增强，请按当前 LLM 统一配置）
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_PROVIDER = "openai_compatible_chat"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
```

### 5.2 召回系统

```python
# scripts/recall_system.py

class RecallConfig:
    # 路径权重
    PATH1_WEIGHT = 0.4  # 相似Idea
    PATH2_WEIGHT = 0.2  # 领域相关
    PATH3_WEIGHT = 0.4  # 相似Paper

    # 召回数量
    PATH1_TOP_K_IDEAS = 10
    PATH1_FINAL_TOP_K = 10
    PATH2_TOP_K_DOMAINS = 5
    PATH2_FINAL_TOP_K = 5
    PATH3_TOP_K_PAPERS = 20
    PATH3_FINAL_TOP_K = 10
    FINAL_TOP_K = 10

    # 两阶段召回
    USE_EMBEDDING = True
    TWO_STAGE_RECALL = True
    COARSE_RECALL_SIZE = 100
    FINE_RECALL_SIZE = 20
```

### 5.3 Pipeline

```python
# scripts/pipeline/config.py

class PipelineConfig:
    # Pattern选择
    SELECT_PATTERN_COUNT = 3
    CONSERVATIVE_RANK_RANGE = (0, 2)
    INNOVATIVE_CLUSTER_SIZE_THRESHOLD = 10

    # Critic阈值
    PASS_SCORE = 7.0
    MAX_REFINE_ITERATIONS = 3

    # 新颖性模式
    NOVELTY_MODE_MAX_PATTERNS = 10
    NOVELTY_SCORE_THRESHOLD = 6.0
    NOVELTY_STAGNATION_DELTA = 0.5

    # Reflection
    FUSION_QUALITY_THRESHOLD = 0.65

    # 回滚
    SCORE_DEGRADATION_THRESHOLD = 0.1

    # RAG查重
    COLLISION_THRESHOLD = 0.75

    # Refinement策略
    TAIL_INJECTION_RANK_RANGE = (4, 9)
    HEAD_INJECTION_RANK_RANGE = (0, 2)
    HEAD_INJECTION_CLUSTER_THRESHOLD = 15

# LLM配置
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_PROVIDER = "openai_compatible_chat"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
```

---

## 6. 完整运行流程

### 6.1 环境准备

```bash
# 1. 克隆项目
cd /Users/gaoge/code/mycode/Idea2Paper/Paper-KG-Pipeline

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置环境变量
export LLM_API_KEY="your_api_key_here"
export LLM_PROVIDER="openai_compatible_chat"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o-mini"
```

### 6.2 一次性构建

```bash
# 构建知识图谱(只需运行一次)
python scripts/build_entity_v3.py   # 15分钟
python scripts/build_edges.py       # 3分钟
```

### 6.3 使用Pipeline

```bash
# 生成论文Story
python scripts/idea2story_pipeline.py "你的研究Idea描述"

# 示例
python scripts/idea2story_pipeline.py "使用强化学习优化大模型推理效率"
```

### 6.4 查看结果

```bash
# 查看最终Story
cat output/final_story.json

# 查看完整流程
cat output/pipeline_result.json

# 查看详细日志
cat output/log.json | jq '.'
```

---

## 7. 核心创新点

### 7.1 知识图谱层面

✅ **LLM增强Pattern**: 为每个Pattern cluster生成归纳性总结
✅ **双层描述**: 具体示例 + 全局总结,既可学习又可理解
✅ **质量导向边权重**: 基于论文质量和Pattern效果计算边权重

### 7.2 召回层面

✅ **三路互补召回**: 从思想、领域、论文三个维度捕捉相关性
✅ **两阶段优化**: Jaccard粗排 + Embedding精排,提速13倍
✅ **实时计算路径3**: 避免预构建冗余边,确保互补性

### 7.3 生成层面

✅ **Idea Fusion**: 概念层面的有机融合,而非技术堆砌
✅ **Story Reflection**: 反思融合质量,评估概念统一性
✅ **新颖性优先模式**: 停滞时自动升级,系统性提升创新性
✅ **智能回滚**: 避免无效修正,提高迭代效率
✅ **兜底策略**: 保证输出质量,选择最高分版本

---

## 8. 系统优势

### 8.1 自动化程度高

- ✅ 完全自动化流程,无需人工干预
- ✅ 智能决策机制(新颖性模式、回滚、兜底)
- ✅ 自适应参数调整

### 8.2 质量保障多层

1. **Pattern层**: LLM增强的高质量Pattern库
2. **召回层**: 三路互补召回,覆盖全面
3. **融合层**: Idea Fusion确保概念统一
4. **反思层**: Story Reflection评估融合质量
5. **评审层**: 三角色Critic全面评估
6. **查重层**: RAG避免撞车

### 8.3 效率优化充分

- ✅ 两阶段召回提速13倍(7分钟→27秒)
- ✅ 智能回滚避免无效迭代
- ✅ Pattern失败标记避免重复尝试
- ✅ LLM响应缓存减少API调用

### 8.4 可扩展性强

- ✅ 模块化设计,易于添加新功能
- ✅ 支持增量更新知识图谱
- ✅ 可适配其他会议数据源
- ✅ 可添加新的召回路径

---

## 9. 当前局限与改进方向

### 9.1 数据层面

**当前局限**:
- ⚠️ Domain粒度过粗,98个Domain覆盖8,285篇论文

**改进方向**:
- 📌 引入Domain层级结构(主领域→子领域)
- 📌 使用sub_domains进行精细匹配
- 📌 扩展到更多会议的 Review 数据

### 9.2 召回层面

**当前局限**:
- ⚠️ 路径2 Domain匹配基于关键词,可能不精确
- ⚠️ 召回速度仍有优化空间(27秒)

**改进方向**:
- 📌 使用Embedding计算Idea与Domain的语义相似度
- 📌 引入向量数据库(Faiss/Milvus),提速到1-3秒
- 📌 预计算并缓存所有Embedding

### 9.3 生成层面

**当前局限**:
- ⚠️ Fusion质量评分依赖LLM,可能不够稳定
- ⚠️ 新颖性模式遍历10个Pattern可能耗时较长

**改进方向**:
- 📌 引入可学习的融合质量评分模型
- 📌 根据历史数据优化Pattern选择顺序
- 📌 并行生成多个Story候选

### 9.4 评审层面

**当前局限**:
- ⚠️ Critic评分依赖LLM,可能存在波动
- ⚠️ 无用户反馈机制

**改进方向**:
- 📌 收集真实审稿数据,训练专用Critic模型
- 📌 引入用户反馈,在线学习调整权重
- 📌 A/B测试不同策略的效果

---

## 10. 文档索引

### 10.1 核心文档

| 文档 | 路径 | 内容 |
|------|------|------|
| **项目总结** | `docs/00_PROJECT_OVERVIEW.md` | 本文档,整体概述 |
| **知识图谱构建** | `docs/01_KG_CONSTRUCTION.md` | 数据源、节点、边、运行方式 |
| **召回系统** | `docs/02_RECALL_SYSTEM.md` | 三路召回、相似度计算、参数配置 |
| **Idea2Story Pipeline** | `docs/03_IDEA2STORY_PIPELINE.md` | Pattern选择、Fusion、Reflection、Critic |

### 10.2 辅助文档

| 文档 | 路径 | 内容 |
|------|------|------|
| **边类型说明** | `docs/EDGE_TYPES.md` | 详细的边定义和权重计算 |
| **Pattern评分解释** | `docs/PATTERN_SCORING_EXPLAINED.md` | Pattern得分计算逻辑 |
| **两阶段召回优化** | `docs/TWO_STAGE_RECALL_OPTIMIZATION.md` | 召回性能优化细节 |
| **数据格式对比** | `docs/Data_Format_Comparison.md` | V2 vs V3数据格式变化 |

### 10.3 历史文档(归档)

以下文档记录了系统演进历史,但核心内容已整合到上述4个主文档中:
- `NOVELTY_MODE_FIX.md`
- `REFLECTION_REGENERATION_FIX.md`
- `WORKFLOW_CORRECTION_2025-01-25.md`
- `REFINE_SYSTEM_UPGRADE.md`
- `RECALL_USAGE_V3.md`
- 等

---

## 11. 代码结构

```
Paper-KG-Pipeline/
├── data/                           # 数据源
│   └── ICLR_25/
│       ├── assignments.jsonl
│       ├── cluster_library_sorted.jsonl
│       └── iclr_patterns_full.jsonl
│
├── output/                         # 输出文件
│   ├── nodes_*.json               # 4类节点
│   ├── edges.json                 # 边数据
│   ├── knowledge_graph_v2.gpickle # NetworkX图谱
│   ├── final_story.json           # 最终Story
│   └── pipeline_result.json       # 流程结果
│
├── scripts/                        # 核心脚本
│   ├── build_entity_v3.py         # 构建节点
│   ├── build_edges.py             # 构建边
│   ├── recall_system.py           # 召回系统(类封装)
│   ├── simple_recall_demo.py      # 召回Demo
│   ├── idea2story_pipeline.py     # Pipeline主入口
│   │
│   └── pipeline/                   # Pipeline模块
│       ├── config.py              # 配置参数
│       ├── manager.py             # 流程编排
│       ├── pattern_selector.py    # Pattern分类
│       ├── planner.py             # Idea Fusion
│       ├── story_generator.py     # Story生成
│       ├── story_reflector.py     # Story反思
│       ├── critic.py              # Critic评审
│       ├── refinement.py          # 智能修正
│       ├── verifier.py            # RAG查重
│       └── utils.py               # 工具函数
│
├── docs/                           # 文档
│   ├── 00_PROJECT_OVERVIEW.md     # 项目总结(本文档)
│   ├── 01_KG_CONSTRUCTION.md      # 知识图谱构建
│   ├── 02_RECALL_SYSTEM.md        # 召回系统
│   └── 03_IDEA2STORY_PIPELINE.md  # Idea2Story Pipeline
│
└── requirements.txt                # 依赖
```

---

## 12. 关键指标

### 12.1 数据规模

```
知识图谱:
  - 节点: 16,791 个
  - 边:   444,872 条
  - Pattern: 124 个(124个已LLM增强)
  - Idea覆盖率: 100% (8,284/8,285)
```

### 12.2 性能指标

```
召回速度:
  - 全量Embedding: ~7分钟
  - 两阶段召回:   ~27秒
  - 提速比:        13倍

Pipeline执行时间:
  - 最快: 3分钟 (首次通过)
  - 典型: 5-7分钟 (2-3轮修正)
  - 最慢: 10分钟 (新颖性模式)
```

### 12.3 质量指标

```
Critic评审:
  - 通过标准: 平均分 >= 7.0
  - 维度: Methodology, Novelty, Storyteller
  - 新颖性模式提升: 0.5-1.5分

Fusion质量:
  - 阈值: >= 0.65
  - 典型值: 0.68-0.75
  - 评分维度: 连贯性(40%) + 融合丰富度(40%) + Fusion Idea奖励(20%)
```

---

## 13. 使用建议

### 13.1 快速开始

```bash
# 1. 首次运行(构建知识图谱)
python scripts/build_entity_v3.py
python scripts/build_edges.py

# 2. 生成论文Story
python scripts/idea2story_pipeline.py "你的研究Idea"

# 3. 查看结果
cat output/final_story.json
```

### 13.2 参数调优

**提升新颖性**:
```python
# 增加新颖性模式尝试次数
PipelineConfig.NOVELTY_MODE_MAX_PATTERNS = 15  # 默认10

# 提高新颖性权重
RecallConfig.PATH1_WEIGHT = 0.5  # 默认0.4,提高相似Idea权重
```

**提升稳定性**:
```python
# 降低融合质量阈值
PipelineConfig.FUSION_QUALITY_THRESHOLD = 0.60  # 默认0.65

# 增加头部Pattern权重
RecallConfig.PATH3_WEIGHT = 0.5  # 默认0.4,提高高质量Paper权重
```

**加速召回**:
```python
# 减少召回数量
RecallConfig.PATH1_TOP_K_IDEAS = 5   # 默认10
RecallConfig.PATH3_TOP_K_PAPERS = 10 # 默认20
```

### 13.3 监控关键事件

```bash
# 新颖性模式激活
grep "激活【新颖性模式】" output/log.json

# 融合质量评分
grep "融合质量评分" output/log.json

# 回滚事件
grep "【ROLLBACK TRIGGERED】" output/log.json

# 最终通过
grep "🎉 Critic 评审通过" output/log.json
```

---

## 14. 故障排查

### 14.1 环境问题

**Q: API key无效**
```bash
# 检查环境变量
echo $LLM_API_KEY

# 设置环境变量
export LLM_API_KEY="your_key_here"
```

**Q: 依赖缺失**
```bash
# 重新安装依赖
pip install -r requirements.txt --upgrade
```

### 14.2 数据问题

**Q: 节点文件不存在**
```bash
# 重新构建知识图谱
python scripts/build_entity_v3.py
python scripts/build_edges.py
```

**Q: 召回结果为空**
```bash
# 检查知识图谱是否构建成功
ls -lh output/nodes_*.json
ls -lh output/knowledge_graph_v2.gpickle
```

### 14.3 Pipeline问题

**Q: Fusion质量总是低于阈值**
```python
# 降低阈值或改进Fusion Prompt
PipelineConfig.FUSION_QUALITY_THRESHOLD = 0.60
```

**Q: 新颖性模式遍历完仍未通过**
```
# 检查log中的兜底策略
grep "兜底策略" output/log.json
# 系统会自动选择最高分版本输出
```

---

## 15. 总结

### 15.1 核心成果

✅ **完整的知识图谱系统**: 16,791节点,444,872条边
✅ **高效的召回系统**: 13倍提速,秒级响应
✅ **智能的生成Pipeline**: Fusion+Reflection+Critic+智能修正
✅ **质量保障机制**: 多层次检查,自动回滚,兜底策略
✅ **完整的文档体系**: 4个核心文档,覆盖构建、召回、生成

### 15.2 技术亮点

✅ **概念层面融合**: Idea Fusion实现有机统一而非技术堆砌
✅ **融合质量反思**: Story Reflector评估融合效果
✅ **新颖性优先**: 停滞时自动升级为新颖性模式
✅ **智能回滚**: 避免无效修正,提高效率
✅ **LLM增强Pattern**: 双层描述提升可用性

### 15.3 应用价值

✅ **科研辅助**: 帮助研究人员快速生成论文框架
✅ **创新探索**: 通过Pattern融合发现新研究方向
✅ **写作指导**: 提供结构化的论文组织建议
✅ **文献调研**: 基于知识图谱快速定位相关工作

### 15.4 未来展望

📌 **数据扩展**: 整合更多会议数据(CVPR, NeurIPS, ACL等)
📌 **模型优化**: 训练专用的Fusion和Critic模型
📌 **用户交互**: 引入用户反馈,在线学习优化
📌 **多模态支持**: 整合图表、公式、代码等多模态信息

---

## 16. 致谢

感谢 ICLR 2025 论文数据集的支持，以及所有 LLM API 服务提供方的支持。

---

**生成时间**: 2026-01-25
**版本**: V1.0
**作者**: Idea2Paper Team

**联系方式**: 参考各核心文档获取详细技术支持

<br/>
<br/>
<br/>

# 知识图谱构建文档

> **说明**：脚本已分类整理到 `scripts/tools/` 与 `scripts/demos/`。旧路径（如 `scripts/build_entity_v3.py`）仍可通过兼容薄壳运行。

## 📋 概述

本文档详细说明了 Idea2Paper 项目中知识图谱的构建过程,包括数据源、节点、边的定义、构建流程、参数配置和运行方式。

---

## 1. 数据源

### 1.1 输入文件

| 文件 | 路径 | 说明 | 数据量 |
|------|------|------|--------|
| **assignments.jsonl** | `data/ICLR_25/assignments.jsonl` | Paper到Pattern的分配关系 | 8,285条 |
| **cluster_library_sorted.jsonl** | `data/ICLR_25/cluster_library_sorted.jsonl` | Pattern Cluster信息 | 124条 |
| **iclr_patterns_full.jsonl** | `data/ICLR_25/iclr_patterns_full.jsonl` | Pattern详细属性(英文完整版) | 8,310条 |

### 1.2 数据结构示例

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

## 2. 节点定义

### 2.1 节点类型概览

| 节点类型 | 数量 | 主要数据源 | 作用 |
|---------|------|-----------|------|
| **Idea** | 8,284 | `iclr_patterns_full.jsonl` | 论文的核心创新点 |
| **Pattern** | 124 | `cluster_library_sorted.jsonl` | 写作套路/方法模板 |
| **Domain** | 98 | `assignments.jsonl`(聚合) | 研究领域 |
| **Paper** | 8,285 | `assignments.jsonl` + pattern details | 具体论文 |

### 2.2 Pattern节点

**数据源**: `cluster_library_sorted.jsonl` + LLM增强

**关键字段**:
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
    "representative_ideas": "归纳性总结(单句)...",
    "common_problems": "归纳性总结(单句)...",
    "solution_approaches": "归纳性总结(单句)...",
    "story": "归纳性总结(单句)..."
  },

  "llm_enhanced": true,
  "exemplar_count": 6
}
```

**构建逻辑**:
```python
def _build_pattern_nodes(clusters):
    for cluster in clusters:
        if cluster_id == -1:
            continue  # 跳过未分配

        pattern_node = {
            'pattern_id': f"pattern_{cluster_id}",
            'name': cluster['cluster_name'],
            'size': cluster['size'],
            'coherence': cluster['coherence'],
            'summary': extract_from_exemplars(cluster)
        }
```

### 2.3 Idea节点

**数据源**: `iclr_patterns_full.jsonl`

**关键字段**:
```json
{
  "idea_id": "idea_0",
  "description": "通过分析标签错误对群体差异指标的影响...",
  "base_problem": "在群体差异指标评估中...",
  "solution_pattern": "提出一种方法估计...",
  "story": "将标签错误问题从模型性能影响扩展到...",
  "application": "高风险决策系统的公平性审计...",
  "domain": "Fairness & Accountability",
  "sub_domains": ["Label Noise", ...],
  "source_paper_ids": ["RUzSobdYy0V"],
  "pattern_ids": ["pattern_9"]
}
```

**去重策略**: MD5 hash前16位

**构建逻辑**:
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

### 2.4 Domain节点

**数据源**: `assignments.jsonl`(聚合)

**关键字段**:
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

**构建逻辑**:
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

### 2.5 Paper节点

**数据源**: `assignments.jsonl` + `iclr_patterns_full.jsonl`

**关键字段**:
```json
{
  "paper_id": "RUzSobdYy0V",
  "title": "Quantifying and Mitigating...",
  "global_pattern_id": "g0",
  "cluster_id": 9,
  "cluster_prob": 0.384,
  "domain": "Fairness & Accountability",
  "sub_domains": [...],
  "idea": "核心想法描述(字符串)",
  "pattern_details": {...},
  "pattern_id": "pattern_9",
  "idea_id": "idea_0",
  "domain_id": "domain_0"
}
```

---

## 3. 边定义

### 3.1 边分类

| 边类型 | 用途 | 数量 |
|--------|------|------|
| **基础连接边** | 建立实体间基本关系 | ~25,000 |
| **召回辅助边** | 支持三路召回策略 | ~420,000 |

### 3.2 基础连接边

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

**质量评分计算**:
```python
def _get_paper_quality(paper):
    reviews = paper.get('reviews', [])
    if reviews:
        scores = [r['overall_score'] for r in reviews]
        avg_score = np.mean(scores)
        return (avg_score - 1) / 9  # 归一化到[0,1]
    return 0.5  # 默认值(V3当前无review数据)
```

#### (3) Paper → Domain (`in_domain`)
```python
G.add_edge(
    paper['paper_id'],
    paper['domain_id'],
    relation='in_domain'
)
```

### 3.3 召回辅助边

#### (1) Idea → Domain (`belongs_to`)

**权重定义**: Idea相关Paper在该Domain的占比

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

**权重定义**:
- `effectiveness`: Pattern在该Domain的效果增益(相对基线) [-1, 1]
- `confidence`: 基于样本数的置信度 [0, 1]

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

**注意**: 此边在V3.1版本中**已预构建但未直接使用**。路径3召回改为**实时计算**用户Idea与Paper Title的相似度。

---

## 4. 构建流程

### 4.1 整体流程

```
┌─────────────────────────────────────────────────────────────┐
│               【知识图谱构建完整流程】                        │
└─────────────────────────────────────────────────────────────┘

【阶段1: 数据加载】(约1秒)
    │
    ├─ 加载 assignments.jsonl (8,285篇论文)
    ├─ 加载 cluster_library_sorted.jsonl (124个Pattern Cluster)
    └─ 加载 iclr_patterns_full.jsonl (8,310条Pattern详情)
    │
    ▼

【阶段2: 节点构建】(约2分钟)
    │
    ├─ 1. Pattern节点 (124个)
    │     ├─ 从cluster_library提取基础信息
    │     ├─ 提取exemplars的ideas/problems/solutions/stories
    │     └─ 生成初步Pattern节点
    │     ↓
    ├─ 2. LLM增强Pattern (124个,约10分钟)
    │     ├─ 为每个Pattern调用LLM
    │     ├─ 生成归纳性总结(4个维度)
    │     │   ├─ representative_ideas
    │     │   ├─ common_problems
    │     │   ├─ solution_approaches
    │     │   └─ story
    │     └─ 添加llm_enhanced_summary字段
    │     ↓
    ├─ 3. Idea节点 (8,284个)
    │     ├─ 从pattern_details提取idea字段
    │     ├─ MD5 hash去重
    │     └─ 提取base_problem/solution_pattern/story/application
    │     ↓
    ├─ 4. Domain节点 (98个)
    │     ├─ 从assignments聚合domain信息
    │     ├─ 收集sub_domains
    │     ├─ 统计paper_count
    │     └─ 关联related_pattern_ids
    │     ↓
    └─ 5. Paper节点 (8,285个)
          ├─ 合并assignments和pattern_details
          ├─ 提取title/domain/sub_domains/idea
          └─ 保留cluster_id/global_pattern_id
    │
    ▼

【阶段3: 建立关联】(约1秒)
    │
    ├─ Paper → Pattern关联
    │    └─ 通过cluster_id映射到pattern_id
    │        覆盖率: 5,981/8,285 (72.2%)
    │
    ├─ Paper → Idea关联
    │    └─ 通过idea文本的MD5 hash映射
    │        覆盖率: 8,284/8,285 (100%)
    │
    ├─ Paper → Domain关联
    │    └─ 通过domain名称映射到domain_id
    │        覆盖率: 8,285/8,285 (100%)
    │
    └─ Idea → Pattern关联
         └─ 通过Paper中转建立连接
             ├─ 收集每个Idea关联的所有Paper
             ├─ 提取这些Paper的pattern_id
             └─ 填充Idea.pattern_ids字段
             平均每个Idea关联0.7个Pattern
    │
    ▼

【阶段4: 保存节点】(约1秒)
    │
    ├─ 输出 nodes_idea.json (8,284个)
    ├─ 输出 nodes_pattern.json (124个)
    ├─ 输出 nodes_domain.json (98个)
    ├─ 输出 nodes_paper.json (8,285个)
    └─ 输出 knowledge_graph_stats.json
    │
    ▼

【阶段5: 构建边】(约2-3分钟)
    │
    ├─ 基础连接边
    │    ├─ Paper → Idea (implements) 8,284条
    │    ├─ Paper → Pattern (uses_pattern) 5,981条
    │    └─ Paper → Domain (in_domain) 8,285条
    │
    ├─ 召回辅助边 - 路径2
    │    ├─ Idea → Domain (belongs_to)
    │    │   └─ 权重: Idea相关Paper在该Domain的占比
    │    │
    │    └─ Pattern → Domain (works_well_in)
    │        ├─ effectiveness: Pattern在Domain的效果增益
    │        └─ confidence: 基于样本数的置信度
    │
    └─ 召回辅助边 - 路径3
         └─ (实时计算,不预构建)
    │
    ▼

【阶段6: 保存图谱】(约1秒)
    │
    ├─ 输出 edges.json
    └─ 输出 knowledge_graph_v2.gpickle
    │
    ▼

✅ 构建完成
   ├─ 总节点: 16,791个
   ├─ 总边数: 444,872条
   └─ 总耗时: 约15-18分钟
```

### 4.2 关键步骤

#### Step 1: 加载数据
```python
assignments = _load_assignments()      # 8,285条
clusters = _load_clusters()            # 124个
pattern_details = _load_pattern_details()  # 8,310条
```

#### Step 2: 构建节点
```python
_build_pattern_nodes(clusters)         # 124个Pattern
_enhance_patterns_with_llm(clusters)   # LLM增强
_build_idea_nodes(pattern_details)     # 8,284个Idea
_build_domain_nodes(assignments)       # 98个Domain
_build_paper_nodes(assignments, pattern_details)  # 8,285个Paper
```

#### Step 3: 建立关联
```python
_link_paper_to_pattern(assignments)    # Paper → Pattern
_link_paper_to_idea()                  # Paper → Idea
_link_paper_to_domain()                # Paper → Domain
_link_idea_to_pattern()                # Idea → Pattern(通过Paper中转)
```

#### Step 4: 构建边
```python
_build_paper_edges()                   # 基础连接边
_build_idea_belongs_to_domain_edges()  # 召回边-路径2
_build_pattern_works_well_in_domain_edges()
_build_idea_similar_to_paper_edges()   # 召回边-路径3
```

#### Step 5: 保存结果
```python
_save_nodes()  # 保存4类节点JSON
_save_edges()  # 保存edges.json
_save_graph()  # 保存knowledge_graph_v2.gpickle
```

---

## 5. LLM增强机制

### 5.1 增强目标

为每个Pattern cluster生成归纳性总结,既保留具体示例,也提供全局概述。

### 5.2 Prompt设计

```python
def _build_llm_prompt_for_pattern(pattern_node, exemplars):
    prompt = f"""
你是一个学术研究专家。请基于以下{len(exemplars)}篇论文的Pattern信息，
为Pattern Cluster "{pattern_node['name']}" 生成归纳性总结。

【论文Pattern信息】
{format_exemplars(exemplars)}

【任务】
请生成4个维度的归纳性总结(每个1句话，80-120字)：
1. representative_ideas: 代表性研究想法
2. common_problems: 共同解决的问题
3. solution_approaches: 解决方法特点
4. story: 研究叙事框架

返回JSON格式。
"""
    return prompt
```

### 5.3 API配置

```python
# 构图脚本为 legacy 示例；此处展示统一 LLM 配置方式
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_PROVIDER = "openai_compatible_chat"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
```

---

## 6. 参数配置

### 6.1 路径配置

```python
# 数据输入路径
DATA_DIR = PROJECT_ROOT / "data" / "ICLR_25"
ASSIGNMENTS_FILE = DATA_DIR / "assignments.jsonl"
CLUSTER_LIBRARY_FILE = DATA_DIR / "cluster_library_sorted.jsonl"
PATTERN_DETAILS_FILE = DATA_DIR / "iclr_patterns_full.jsonl"

# 输出路径
OUTPUT_DIR = PROJECT_ROOT / "output"
NODES_IDEA = OUTPUT_DIR / "nodes_idea.json"
NODES_PATTERN = OUTPUT_DIR / "nodes_pattern.json"
NODES_DOMAIN = OUTPUT_DIR / "nodes_domain.json"
NODES_PAPER = OUTPUT_DIR / "nodes_paper.json"
EDGES_FILE = OUTPUT_DIR / "edges.json"
GRAPH_FILE = OUTPUT_DIR / "knowledge_graph_v2.gpickle"
```

### 6.2 LLM配置

```python
# API密钥(环境变量)
LLM_API_KEY = os.getenv("LLM_API_KEY")

# Provider 选择
LLM_PROVIDER = "openai_compatible_chat"

# Base URL（或直接使用 LLM_API_URL 覆盖）
LLM_BASE_URL = "https://api.openai.com/v1"

# 模型选择
LLM_MODEL = "gpt-4o-mini"
```

### 6.3 边构建配置

```python
# Pattern-Domain边权重计算
BASELINE_SAMPLE_SIZE = 20  # confidence达到1.0的样本数阈值

# Paper质量评分
# 优先使用 review_stats.avg_score (基于多维度Review评分)
# 无review数据时使用默认值 0.5
```

---

## 7. 运行方式

### 7.1 环境准备

**依赖安装**:
```bash
cd /Users/gaoge/code/mycode/Idea2Paper/Paper-KG-Pipeline
pip install -r requirements.txt
```

**环境变量设置**:
```bash
export LLM_API_KEY="your_api_key_here"
```

### 7.2 构建节点

**命令**:
```bash
python scripts/build_entity_v3.py
```

**输出**:
```
output/
├── nodes_idea.json           # 8,284个Idea节点
├── nodes_pattern.json        # 124个Pattern节点
├── nodes_domain.json         # 98个Domain节点
├── nodes_paper.json          # 8,285个Paper节点
└── knowledge_graph_stats.json # 统计信息
```

**执行时间**: 约10-15分钟(含LLM增强)

### 7.3 构建边

**命令**:
```bash
python scripts/build_edges.py
```

**输出**:
```
output/
├── edges.json                # 边数据(JSON格式)
└── knowledge_graph_v2.gpickle # 完整图谱(NetworkX格式)
```

**执行时间**: 约2-3分钟

### 7.4 验证图谱

**Python交互式验证**:
```python
import json
import pickle

# 加载节点
with open('output/nodes_pattern.json') as f:
    patterns = json.load(f)
print(f"Pattern数量: {len(patterns)}")

# 加载图谱
with open('output/knowledge_graph_v2.gpickle', 'rb') as f:
    G = pickle.load(f)
print(f"节点数: {G.number_of_nodes()}")
print(f"边数: {G.number_of_edges()}")
```

---

## 8. 输出统计

### 8.1 节点统计

```
总节点数:  9,411
  - Idea:      8,284 (100%覆盖率)
  - Pattern:   124
  - Domain:    98
  - Paper:     8,285
```

### 8.2 边统计

```
【基础连接边】
  Paper→Idea:      8,284 条
  Paper→Pattern:   5,981 条 (72.2%覆盖率)
  Paper→Domain:    8,285 条

【召回边 - 路径2】
  Idea→Domain:     ~15,000 条
  Pattern→Domain:  ~3,500 条

【召回边 - 路径3】
  (实时计算，无预构建边)

总边数: 444,872 条
```

### 8.3 数据质量

```
✅ Idea覆盖率: 100% (8,284/8,285)
✅ Pattern覆盖率: 72.2% (基于cluster分配)
✅ LLM增强: 124/124 Pattern节点
✅ 聚类质量: 可量化评估(coherence指标)
```

---

## 9. 故障排查

### 9.1 常见问题

**Q: LLM API调用失败**
```
错误: Connection timeout / API key invalid
解决:
1. 检查网络连接
2. 验证 LLM_API_KEY 环境变量
3. 检查API额度
```

**Q: 内存不足**
```
错误: MemoryError
解决:
1. 减少LLM增强的exemplar数量(默认20→10)
2. 分批处理Pattern节点
```

**Q: 输出文件已存在**
```
行为: 自动覆盖
建议: 备份重要的output/文件后再运行
```

### 9.2 日志查看

构建过程会输出详细日志:
```
🚀 开始构建知识图谱 V3 (ICLR数据源)
【Step 1】加载数据
  ✅ 加载 8285 篇论文分配
【Step 2】构建节点
  ✓ 创建 124 个 Pattern 节点
  ✓ LLM增强: 124/124 完成
【Step 3】建立节点关联
  ✓ 共建立 8284 个 Idea->Pattern 连接
【Step 4】保存节点
【Step 5】统计信息
✅ 知识图谱构建完成!
```

---

## 10. 扩展与优化

### 10.1 数据源扩展

**添加新会议数据**:
1. 准备与ICLR格式一致的JSONL文件
2. 修改`DATA_DIR`路径
3. 重新运行`build_entity_v3.py`

### 10.2 Review数据扩展

**当前状态**: Paper节点已集成ICLR 2025的review数据，包含多维度评分

**数据结构**:
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

**扩展方案**: 可添加更多会议的review数据以丰富知识图谱

### 10.3 性能优化

**LLM增强加速**:
```python
# 并行处理Pattern
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(_enhance_single_pattern, p)
               for p in pattern_nodes]
```

---

## 11. 总结

### 核心成果

✅ 成功基于ICLR数据源构建知识图谱
✅ 实现100% Idea覆盖率
✅ 引入LLM增强,为每个Pattern生成归纳性总结
✅ 保留聚类质量指标(coherence)
✅ 代码模块化,易于扩展

### 技术特性

✅ **LLM集成**: 使用通用 LLM Provider 增强 Pattern 描述
✅ **Prompt工程**: 结构化Prompt设计
✅ **容错机制**: 自动JSON解析和修复
✅ **双层描述**: 具体示例+全局总结

### 扩展性

✅ 支持增量更新
✅ 可适配其他会议数据源
✅ 为召回系统提供完整节点基础

---

**生成时间**: 2026-01-25
**版本**: V3.1
**作者**: Idea2Paper Team

<br/>
<br/>
<br/>

# 三路召回系统文档

> **说明**：脚本已分类整理到 `scripts/tools/` 与 `scripts/demos/`。旧路径（如 `scripts/simple_recall_demo.py`）仍可通过兼容薄壳运行。

## 📋 概述

本文档详细说明了基于知识图谱的三路召回系统,包括召回策略、相似度计算、多路融合、参数配置和运行方式。

---

## 1. 系统架构

### 1.1 核心目标

**输入**: 用户的研究Idea描述(文本)
**输出**: Top-10最相关的研究Pattern(写作套路/方法模板)

### 1.2 技术架构

```
┌──────────────────────────────────────────────────────────────────┐
│                    【三路召回系统架构】                            │
└──────────────────────────────────────────────────────────────────┘

用户输入Idea (文本描述)
    │
    ├────────────────────────────────────────────────────────────┐
    │                  三路并行召回 (约27秒)                      │
    ├────────────────────────────────────────────────────────────┤
    │                                                              │
    │  ┌──────────────┬──────────────┬──────────────┐           │
    │  │   路径1      │    路径2     │    路径3     │           │
    │  │ 相似Idea召回 │ 领域相关召回 │ 相似Paper召回│           │
    │  │  (权重0.4)   │  (权重0.2)   │  (权重0.4)   │           │
    │  └──────────────┴──────────────┴──────────────┘           │
    │        │              │              │                      │
    │        │              │              │                      │
    │  ┌─────▼──────┐  ┌───▼────┐  ┌──────▼─────┐              │
    │  │【粗排阶段】│  │【Domain】│  │【粗排阶段】│              │
    │  │ Jaccard   │  │ 匹配    │  │ Jaccard   │              │
    │  └───────────┘  └────────┘  └────────────┘              │
    │        │              │              │                      │
    │  遍历8,284个    使用Top-1      遍历8,285个                │
    │  Idea描述       Idea的Domain    Paper标题                 │
    │  词袋模型       关键词匹配      词袋模型                   │
    │  快速过滤       查图谱边        快速过滤                   │
    │        │              │              │                      │
    │  Top-100个      Top-5个        Top-100个                  │
    │  候选Idea       Domain         候选Paper                  │
    │        │              │              │                      │
    │  ┌─────▼──────┐  ┌───▼────┐  ┌──────▼─────┐              │
    │  │【精排阶段】│  │【Pattern】│  │【精排阶段】│              │
    │  │ Embedding │  │ 召回    │  │ Embedding │              │
    │  └───────────┘  └────────┘  └────────────┘              │
    │        │              │              │                      │
    │  100次API调用   查works_well  100次API调用                │
    │  语义相似度     _in边        语义相似度                    │
    │  精确重排       效果加权      × Paper质量                  │
    │        │              │              │                      │
    │  Top-10个       Top-K个       Top-20个                    │
    │  相似Idea       Pattern       相似Paper                   │
    │        │              │              │                      │
    │  ┌─────▼──────┐  ┌───▼────┐  ┌──────▼─────┐              │
    │  │【Pattern】 │  │【Pattern】│  │【Pattern】 │              │
    │  │  提取     │  │  得分   │  │  提取     │              │
    │  └───────────┘  └────────┘  └────────────┘              │
    │        │              │              │                      │
    │  直接获取Idea   Domain相关度   查Paper→Pattern             │
    │  .pattern_ids   × effectiveness  uses_pattern边            │
    │  按相似度加权   × confidence   相似度×质量加权              │
    │        │              │              │                      │
    │  Pattern得分    Pattern得分    Pattern得分                 │
    │  字典           字典           字典                         │
    │        │              │              │                      │
    └────────┼──────────────┼──────────────┼────────────────────┘
             │              │              │
             └──────────────┴──────────────┘
                          │
                          ▼
               ┌──────────────────────┐
               │   【多路融合】        │
               └──────────────────────┘
                          │
                score = path1 × 0.4
                      + path2 × 0.2
                      + path3 × 0.4
                          │
                          ▼
                  按融合得分排序
                          │
                          ▼
               ┌──────────────────────┐
               │   Top-10 Pattern     │
               │   返回给用户         │
               └──────────────────────┘
```

**架构说明**:
- **横向**: 三路并行执行,互不干扰
- **纵向**: 每路内部两阶段优化(粗排→精排)
- **融合**: 加权求和,确保多样性

### 1.3 数据规模

```
知识图谱统计:
  - Idea节点:    8,284 个
  - Pattern节点: 124 个
  - Domain节点:  98 个
  - Paper节点:   8,285 个
  - 总边数:      444,872 条
```

---

## 2. 三路召回策略

### 2.1 设计理念

三路召回从不同维度捕捉用户需求,避免重复和信息冗余:

| 路径 | 匹配对象 | 捕捉维度 | 权重 | 典型场景 |
|------|---------|---------|------|---------|
| **路径1** | Idea Description | 核心思想/概念相似性 | 0.4 | 用户描述与历史成功案例的核心思路一致 |
| **路径2** | Domain & Sub-domains | 领域泛化能力 | 0.2 | 用户Idea属于某领域,该领域有验证有效的Pattern |
| **路径3** | Paper Title | 研究主题/具体问题相似性 | 0.4 | 用户想解决的具体问题与某些论文标题表述类似 |

**互补性说明**:
- **路径1 vs 路径3**: 路径1关注"想法本质",路径3关注"研究方向"
- **路径2的泛化作用**: 即使用户Idea是全新的,只要属于某个成熟领域,也能召回该领域通用的有效Pattern

---

## 3. 路径1: 相似Idea召回

### 3.1 召回流程

```
用户Idea (文本)
    ↓ [粗排] Jaccard快速筛选
候选Idea (Top-100)
    ↓ [精排] Embedding重排
相似Idea (Top-10)
    ↓ 直接获取 idea.pattern_ids
Pattern集合
    ↓ 按相似度加权累加
Top-10 Pattern (得分字典)
```

### 3.2 两阶段召回优化

**为什么需要两阶段?**
- 全量Embedding检索: 8,284次API调用,耗时**~7分钟** ❌
- 两阶段召回: 100次API调用,耗时**~10秒** ✅ (提速40倍)

**粗排阶段(Jaccard)**:
```python
def compute_jaccard_similarity(text1, text2):
    """计算Jaccard相似度(词袋模型)"""
    # 分词
    tokens1 = set(text1.lower().split())
    tokens2 = set(text2.lower().split())

    # Jaccard = 交集/并集
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0

# 粗排: 快速筛选Top-100
coarse_similarities = []
for idea in ideas:  # 8,284个
    sim = compute_jaccard_similarity(user_idea, idea['description'])
    if sim > 0:
        coarse_similarities.append((idea_id, sim))

coarse_similarities.sort(reverse=True)
candidates = coarse_similarities[:100]  # 粗排Top-100
```

**精排阶段(Embedding)**:
```python
def compute_embedding_similarity(text1, text2):
    """使用Qwen3-Embedding-4B计算语义相似度"""
    # 获取Embedding
    emb1 = get_embedding(text1)  # API调用
    emb2 = get_embedding(text2)  # API调用

    # 余弦相似度
    return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

# 精排: 对候选使用Embedding重排
fine_similarities = []
for idea_id, _ in candidates:  # 100个
    idea = idea_id_to_idea[idea_id]
    sim = compute_embedding_similarity(user_idea, idea['description'])
    if sim > 0:
        fine_similarities.append((idea_id, sim))

fine_similarities.sort(reverse=True)
top_ideas = fine_similarities[:10]  # 精排Top-10
```

### 3.3 Pattern得分计算

```python
pattern_scores = defaultdict(float)

for idea_id, similarity in top_10_ideas:
    idea = idea_id_to_idea[idea_id]

    # V3版本: 直接从Idea节点获取pattern_ids
    for pattern_id in idea['pattern_ids']:
        # 得分 = 相似度 (多个Idea使用同一Pattern时会累加)
        pattern_scores[pattern_id] += similarity

# 排序并只保留Top-10
sorted_patterns = sorted(pattern_scores.items(), reverse=True)
top_patterns = dict(sorted_patterns[:10])
```

**示例**:
```
用户Idea: "使用Transformer进行文本分类"

相似Idea_1 (相似度0.8) → [pattern_5, pattern_10]
相似Idea_2 (相似度0.7) → [pattern_5, pattern_20]
相似Idea_3 (相似度0.6) → [pattern_10]

路径1得分:
  pattern_5:  0.8 + 0.7 = 1.5
  pattern_10: 0.8 + 0.6 = 1.4
  pattern_20: 0.7 = 0.7
```

---

## 4. 路径2: 领域相关召回

### 4.1 召回流程

```
用户Idea (文本)
    ↓ 关键词匹配Domain name
相关Domain (Top-5)
    ↓ 反向查找Pattern→Domain边
在Domain中表现好的Pattern
    ↓ 按effectiveness & confidence加权
Top-5 Pattern (得分字典)
```

### 4.2 Domain匹配逻辑

**方法1: 关键词匹配**(优先):
```python
def match_domains(user_idea, domains):
    domain_scores = []
    user_tokens = set(user_idea.lower().split())

    for domain in domains:
        domain_name = domain['name']
        domain_tokens = set(domain_name.lower().split())

        # 词汇重叠
        match_score = len(user_tokens & domain_tokens) / max(len(user_tokens), 1)

        if match_score > 0:
            domain_scores.append((domain['domain_id'], match_score))

    domain_scores.sort(reverse=True)
    return domain_scores[:5]  # Top-5
```

**方法2: 通过相似Idea的Domain**(备选):
```python
if not domain_scores:
    # 找到最相似的Idea
    similarities = [(idea, compute_similarity(user_idea, idea['description']))
                    for idea in ideas]
    top_idea = max(similarities, key=lambda x: x[1])[0]

    # 获取该Idea的Domain (通过belongs_to边)
    for successor in G.successors(top_idea['idea_id']):
        edge_data = G[top_idea['idea_id']][successor]
        if edge_data['relation'] == 'belongs_to':
            domain_id = successor
            weight = edge_data['weight']
            domain_scores.append((domain_id, weight))
```

### 4.3 Pattern得分计算

```python
pattern_scores = defaultdict(float)

for domain_id, domain_weight in top_5_domains:
    # 反向查找: 哪些Pattern在该Domain中表现好?
    for predecessor in G.predecessors(domain_id):
        edge_data = G[predecessor][domain_id]

        if edge_data['relation'] == 'works_well_in':
            pattern_id = predecessor
            effectiveness = edge_data['effectiveness']  # [-1, 1]
            confidence = edge_data['confidence']  # [0, 1]

            # 得分 = Domain相关度 × 效果 × 置信度
            # max(effectiveness, 0.1) 避免负值
            score = domain_weight * max(effectiveness, 0.1) * confidence
            pattern_scores[pattern_id] += score

# 排序并只保留Top-5 (辅助通道)
sorted_patterns = sorted(pattern_scores.items(), reverse=True)
top_patterns = dict(sorted_patterns[:5])
```

**边权重说明**:
- `effectiveness`: Pattern在该Domain的效果增益(相对基线) [-1, 1]
  - 正值: Pattern在该Domain效果好于平均水平
  - 负值: Pattern在该Domain效果低于平均水平
- `confidence`: 基于样本数的置信度 [0, 1]
  - 样本数≥20时,置信度达到1.0

---

## 5. 路径3: 相似Paper召回

### 5.1 召回流程

```
用户Idea (文本)
    ↓ [粗排] Jaccard筛选(基于Paper Title)
候选Paper (Top-100)
    ↓ [精排] Embedding重排(基于Paper Title)
相似Paper (Top-20)
    ↓ 查找Paper→Pattern边
Pattern集合
    ↓ 按similarity × quality加权
Top-10 Pattern (得分字典)
```

### 5.2 设计理念

**路径1 vs 路径3的互补性**:
- **路径1**: 使用Idea Description计算相似度 → 捕捉**核心思想/概念**的相似性
- **路径3**: 使用Paper Title计算相似度 → 捕捉**研究主题/具体问题**的相似性

### 5.3 两阶段召回优化

**粗排阶段(Jaccard)**:
```python
coarse_similarities = []
for paper in papers:  # 8,285个
    paper_title = paper['title']  # 使用论文标题
    sim = compute_jaccard_similarity(user_idea, paper_title)

    if sim > 0.05:  # 降低阈值保留更多候选
        coarse_similarities.append((paper_id, sim))

coarse_similarities.sort(reverse=True)
candidates = coarse_similarities[:100]  # 粗排Top-100
```

**精排阶段(Embedding)**:
```python
fine_similarities = []
for paper_id, _ in candidates:  # 100个
    paper = paper_id_to_paper[paper_id]
    paper_title = paper['title']  # 使用论文标题

    sim = compute_embedding_similarity(user_idea, paper_title)

    if sim > 0.1:  # 过滤低相似度
        # 获取Paper质量 (优先使用 review_stats.avg_score)
        quality = _get_paper_quality(paper)  # [0, 1]
        combined_weight = sim * quality  # 结合相似度和质量
        fine_similarities.append((paper_id, sim, quality, combined_weight))

fine_similarities.sort(key=lambda x: x[3], reverse=True)
top_papers = fine_similarities[:20]  # 精排Top-20
```

### 5.4 Pattern得分计算

```python
pattern_scores = defaultdict(float)

for paper_id, similarity, paper_quality, combined_weight in top_20_papers:
    # 从图谱中查找Paper使用的Pattern
    for successor in G.successors(paper_id):
        edge_data = G[paper_id][successor]

        if edge_data['relation'] == 'uses_pattern':
            pattern_id = successor
            pattern_quality = edge_data['quality']  # Paper的Review质量

            # 得分 = (相似度 × Paper质量) × Pattern质量
            # paper_quality 来自 review_stats.avg_score
            score = combined_weight * pattern_quality
            pattern_scores[pattern_id] += score

# 排序并只保留Top-10
sorted_patterns = sorted(pattern_scores.items(), reverse=True)
top_patterns = dict(sorted_patterns[:10])
```

---

## 6. 多路融合与精排

### 6.1 融合策略

```python
# 路径权重配置
PATH1_WEIGHT = 0.4  # 相似Idea召回 (重要)
PATH2_WEIGHT = 0.2  # 领域相关召回 (辅助)
PATH3_WEIGHT = 0.4  # 相似Paper召回 (重要)
```

**权重设计理由**:
- **路径1 (0.4)**: 直接利用历史成功经验,最可靠
- **路径2 (0.2)**: 领域泛化能力强,但较粗粒度,作为辅助
- **路径3 (0.4)**: 细粒度匹配,质量导向,与路径1同等重要

### 6.2 按Pattern聚合得分

```python
# 收集三路召回的所有Pattern
all_patterns = set(path1_scores.keys()) | set(path2_scores.keys()) | set(path3_scores.keys())

# 计算每个Pattern的最终得分
final_scores = {}
for pattern_id in all_patterns:
    score1 = path1_scores.get(pattern_id, 0.0) * PATH1_WEIGHT
    score2 = path2_scores.get(pattern_id, 0.0) * PATH2_WEIGHT
    score3 = path3_scores.get(pattern_id, 0.0) * PATH3_WEIGHT

    final_scores[pattern_id] = score1 + score2 + score3

# 排序并返回Top-10
ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
top_10 = ranked[:10]
```

### 6.3 结果示例

```
================================================================================
📊 召回结果 Top-10
================================================================================

【Rank 1】 pattern_111
  名称: Reframing Zero-Shot Generalization
  最终得分: 0.6571
  - 路径1 (相似Idea):   0.5257 (占比 80.0%)
  - 路径2 (领域相关):   0.0000 (占比 0.0%)
  - 路径3 (相似Paper):  0.1314 (占比 20.0%)
  聚类大小: 22 篇论文

【Rank 2】 pattern_110
  名称: Reframing Few Shot Learning Robustness
  最终得分: 0.4990
  - 路径1 (相似Idea):   0.3036 (占比 60.8%)
  - 路径2 (领域相关):   0.0000 (占比 0.0%)
  - 路径3 (相似Paper):  0.1954 (占比 39.2%)
  聚类大小: 24 篇论文
```

---

## 7. 参数配置

### 7.1 召回参数

```python
class RecallConfig:
    """召回系统配置"""
    # 路径1: 相似Idea召回
    PATH1_TOP_K_IDEAS = 10         # 召回前K个最相似的Idea
    PATH1_FINAL_TOP_K = 10         # 最终只保留Top-K个Pattern

    # 路径2: 领域相关召回
    PATH2_TOP_K_DOMAINS = 5        # 召回前K个最相关的Domain
    PATH2_FINAL_TOP_K = 5          # 最终只保留Top-K个Pattern

    # 路径3: 相似Paper召回
    PATH3_TOP_K_PAPERS = 20        # 召回前K个最相似的Paper
    PATH3_FINAL_TOP_K = 10         # 最终只保留Top-K个Pattern

    # 各路召回的权重
    PATH1_WEIGHT = 0.4             # 路径1权重(相似Idea - 重要)
    PATH2_WEIGHT = 0.2             # 路径2权重(领域相关 - 辅助)
    PATH3_WEIGHT = 0.4             # 路径3权重(相似Paper - 重要)

    # 最终召回的Top-K
    FINAL_TOP_K = 10

    # 相似度计算方式
    USE_EMBEDDING = True           # 使用embedding(推荐)

    # 两阶段召回优化
    TWO_STAGE_RECALL = True        # 启用两阶段召回(大幅提速)
    COARSE_RECALL_SIZE = 100       # 粗召回数量(Jaccard)
    FINE_RECALL_SIZE = 20          # 精排数量(Embedding)
```

### 7.2 Embedding API配置

```python
# API端点
EMBEDDING_API_URL = "https://api.openai.com/v1/embeddings"

# 模型选择
EMBEDDING_MODEL = "text-embedding-3-large"

# API密钥
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
```

---

## 8. 运行方式

### 8.1 独立运行召回系统

**命令**:
```bash
cd /Users/gaoge/code/mycode/Idea2Paper/Paper-KG-Pipeline
python scripts/simple_recall_demo.py "你的研究Idea描述"
```

**示例**:
```bash
python scripts/simple_recall_demo.py "使用蒸馏技术完成Transformer跨领域文本分类任务"
```

**输出**:
```
🎯 三路召回系统 Demo
================================================================================
【用户Idea】
使用蒸馏技术完成Transformer跨领域文本分类任务

🔍 [路径1] 相似Idea召回...
  [粗排] 使用Jaccard快速筛选Top-100...
  [精排] 使用Embedding重排Top-10...
  ✓ 粗排8284个 → 精排100个 → 最终10个

🌍 [路径2] 领域相关性召回...
  找到 3 个相关Domain
  ✓ 召回 34 个Pattern，保留Top-5

📄 [路径3] 相似Paper召回...
  [粗排] 使用Jaccard快速筛选Top-100...
  [精排] 使用Embedding重排Top-20...
  ✓ 粗排171个 → 精排100个 → 最终20个

🔗 融合三路召回结果...

📊 召回结果 Top-10
【Rank 1】 pattern_11 - 模型压缩与知识蒸馏
  最终得分: 0.1312
  ...
```

### 8.2 作为类使用

```python
from recall_system import RecallSystem

# 初始化召回系统
system = RecallSystem()

# 执行召回
user_idea = "你的研究Idea"
results = system.recall(user_idea, verbose=True)

# 处理结果
for pattern_id, pattern_info, score in results:
    print(f"Pattern: {pattern_info['name']}, Score: {score:.4f}")
```

### 8.3 集成到Pipeline

```python
# 在idea2story_pipeline.py中使用
from recall_system import RecallSystem

recall_system = RecallSystem()
recall_results = recall_system.recall(user_idea, verbose=True)

# recall_results格式: [(pattern_id, pattern_info, score), ...]
```

---

## 9. 性能优化

### 9.1 召回速度对比

| 模式 | 描述 | 时间 | API调用次数 |
|------|------|------|-----------|
| **全量Embedding** | 对所有8,284个Idea用Embedding计算 | ~7分钟 | 8,284次 |
| **两阶段召回** | Jaccard粗排100→Embedding精排10 | ~27秒 | 100次 |
| **提速比** | - | **13倍** | - |

### 9.2 进一步优化方案

**方案1: Embedding缓存**:
```python
# 预计算所有Idea和Paper的Embedding
idea_embeddings = precompute_all_embeddings(ideas)
paper_embeddings = precompute_all_embeddings(papers)

# 召回时直接使用缓存
user_embedding = get_embedding(user_idea)
similarities = [cosine_similarity(user_embedding, idea_emb)
                for idea_emb in idea_embeddings]
```

**方案2: 向量数据库**:
```python
# 使用Faiss/Milvus等向量数据库
import faiss

# 构建索引
index = faiss.IndexFlatIP(embedding_dim)
index.add(idea_embeddings)

# ANN检索
D, I = index.search(user_embedding, k=10)  # Top-10
```
预期提速: **~1-3秒**

**方案3: GPU加速**:
```python
# 使用GPU批量计算Embedding相似度
import torch

user_emb = torch.tensor(user_embedding).cuda()
all_embs = torch.tensor(idea_embeddings).cuda()

similarities = torch.matmul(user_emb, all_embs.T)
```

---

## 10. 故障排查

### 10.1 常见问题

**Q: 召回结果全是高分Pattern**
```
原因: 路径2权重过高,导致热门Pattern得分虚高
解决: 降低PATH2_WEIGHT (0.2 → 0.1)
```

**Q: Embedding API超时**
```
原因: 网络问题或API限流
解决:
1. 增加重试机制
2. 添加请求延迟(time.sleep(0.1))
3. 使用缓存避免重复请求
```

**Q: 召回速度慢**
```
原因: TWO_STAGE_RECALL=False或USE_EMBEDDING=False
解决: 确保config中启用两阶段召回和Embedding
```

**Q: 路径1得分为0**
```
原因: 用户Idea与所有历史Idea相似度极低
检查: 打印相似度分布,确认是否有匹配的Idea
```

### 10.2 调试模式

```python
# 启用详细日志
results = system.recall(user_idea, verbose=True)

# 查看中间结果
print(f"路径1召回Pattern数: {len(path1_scores)}")
print(f"路径2召回Pattern数: {len(path2_scores)}")
print(f"路径3召回Pattern数: {len(path3_scores)}")

# 查看相似度分布
for idea_id, sim in top_ideas:
    print(f"Idea {idea_id}: {sim:.3f}")
```

---

## 11. 评估指标

### 11.1 召回质量评估

**相关性评估**:
```python
# 人工标注Top-10结果的相关性(0-1)
relevance_scores = []
for pattern in top_10:
    score = manual_annotation(pattern, user_idea)
    relevance_scores.append(score)

avg_relevance = np.mean(relevance_scores)
print(f"平均相关性: {avg_relevance:.2f}")
```

**多样性评估**:
```python
# 计算Top-10 Pattern的cluster size分布
cluster_sizes = [p['size'] for p in top_10_patterns]
diversity_score = np.std(cluster_sizes) / np.mean(cluster_sizes)
print(f"多样性得分(变异系数): {diversity_score:.2f}")
```

### 11.2 性能监控

```python
import time

start = time.time()
results = system.recall(user_idea)
elapsed = time.time() - start

print(f"召回耗时: {elapsed:.2f}秒")
print(f"API调用次数: {api_call_count}")
```

---

## 12. 扩展与定制

### 12.1 自定义权重

```python
# 在recall_system.py中修改
class RecallConfig:
    PATH1_WEIGHT = 0.5  # 提高路径1权重
    PATH2_WEIGHT = 0.1  # 降低路径2权重
    PATH3_WEIGHT = 0.4
```

### 12.2 添加新的召回路径

**示例: 路径4 - 相似技术栈召回**:
```python
def _recall_path4_similar_techniques(self, user_idea):
    """路径4: 通过技术栈相似度召回"""
    # 提取技术关键词
    techniques = extract_techniques(user_idea)

    # 匹配Pattern的common_tricks
    pattern_scores = defaultdict(float)
    for pattern in self.patterns:
        tricks = pattern.get('common_tricks', [])
        overlap = len(set(techniques) & set(tricks))
        pattern_scores[pattern['pattern_id']] = overlap

    return pattern_scores
```

### 12.3 领域特化

```python
# 针对特定领域(如NLP)调整参数
if domain == "Natural Language Processing":
    RecallConfig.PATH1_WEIGHT = 0.5  # NLP领域更依赖历史经验
    RecallConfig.PATH2_WEIGHT = 0.1
```

---

## 13. 总结

### 系统亮点

✅ **三路互补召回**: 兼顾相似度、领域和质量
✅ **两阶段优化**: 提速13倍,实现秒级召回
✅ **质量导向召回**: 路径3结合Review质量评分,提升召回准确性
✅ **LLM增强Pattern**: 124个Pattern经过LLM归纳总结
✅ **可扩展架构**: 易于添加新召回路径
✅ **完整监控**: 详细的日志和评估指标

### 技术特性

✅ **Embedding + Jaccard混合策略**: 平衡精度和速度
✅ **图谱结构化召回**: 利用边权重精确计算得分
✅ **多维度质量评分**: 综合overall_score、confidence、contribution、correctness
✅ **实时计算**: 路径3避免预构建冗余边

### 待改进

⚠️ **优化Domain匹配**: 引入层级结构或Embedding匹配
⚠️ **向量数据库**: 进一步提升召回效率到1-3秒
⚠️ **在线学习**: 根据用户反馈调整权重
⚠️ **扩展Review数据**: 整合更多会议的评审数据

---

**生成时间**: 2026-01-25
**版本**: V3.1
**作者**: Idea2Paper Team

<br/>
<br/>
<br/>

# Idea2Story Pipeline 文档

> **说明**：脚本已分类整理到 `scripts/tools/` 与 `scripts/demos/`。旧路径（如 `scripts/idea2story_pipeline.py`）仍可通过兼容薄壳运行。

## 📋 概述

本文档详细说明了从用户Idea到可发表Paper Story的完整生成链路,包括Pattern选择、Idea Fusion、Story生成、Critic评审、智能修正机制、参数配置和运行方式。

---

## 1. 系统架构

### 1.1 整体流程

```
┌─────────────────────────────────────────────────────────────────┐
│                  【Idea2Story Pipeline 完整流程】                 │
└─────────────────────────────────────────────────────────────────┘

用户输入Idea
    │
    ▼
【阶段1: Pattern选择与分类】(约1秒)
    │
    ├─ 召回Top-10 Pattern (来自召回系统)
    │   └─ 路径1(相似Idea) + 路径2(领域) + 路径3(相似Paper)
    │
    ├─ Pattern多维度分类
    │   ├─ Stability (稳健型): Rank前3 + Cluster Size≥15
    │   ├─ Novelty (新颖型): Cluster Size<10
    │   └─ Cross-Domain (跨域型): 不同Domain来源
    │
    └─ 选择初始Pattern (优先Stability维度)
    │
    ▼
【阶段2: Story生成】(约1-2分钟)
    │
    └─ 基于Pattern生成初稿Story
        ├─ 使用skeleton_examples作为模板
        ├─ 注入common_tricks
        └─ 结构化输出(7个字段)
    │
    ▼
【阶段3: Critic评审】(约30秒)
    │
    └─ 多角色评审 (并行)
        ├─ Methodology Critic: 技术可行性/严谨性
        ├─ Novelty Critic: 创新性/问题新颖性
        └─ Storyteller Critic: 叙事连贯性/可读性
        │
        └─ 计算平均分 (avg_score)
    │
    ▼
【阶段4: 判断分支】
    │
    ├─【判断1】评分 >= 7.0?
    │   ├─【是】→ 进入阶段5: RAG查重
    │   └─【否】→ 进入阶段4.1或4.2
    │
    ├─【判断2】新颖性停滞? (novelty_score <= last + 0.5)
    │   ├─【是】→ 阶段4.1: 新颖性模式
    │   └─【否】→ 阶段4.2: 普通修正
    │
    ├─────────────────────────────────────────────────────────────┐
    │              【阶段4.1: 新颖性模式】(3-10分钟)               │
    ├─────────────────────────────────────────────────────────────┤
    │                                                               │
    │  遍历Novelty维度的Pattern (最多10个)                         │
    │      │                                                        │
    │      ├─ For each novelty_pattern:                           │
    │      │                                                        │
    │      ├─ 1. Idea Fusion (概念融合)                           │
    │      │     ├─ 输入: user_idea + current_story + pattern     │
    │      │     ├─ LLM分析: 概念A, 概念B, 融合方式               │
    │      │     └─ 输出: fused_idea (融合后的新Idea)             │
    │      │                                                        │
    │      ├─ 2. Story Reflection (质量评估)                      │
    │      │     ├─ 输入: fused_idea + current_story              │
    │      │     ├─ 评估4个维度                                   │
    │      │     │   ├─ concept_unity: 概念统一性 [0-10]          │
    │      │     │   ├─ technical_soundness: 技术可行性 [0-10]    │
    │      │     │   ├─ novelty_level: 新颖性 [0-10]              │
    │      │     │   └─ narrative_clarity: 叙事清晰度 [0-10]      │
    │      │     └─ 输出: fusion_score + suggestions              │
    │      │                                                        │
    │      ├─ 3. 重新生成Story                                    │
    │      │     └─ 基于fused_idea + reflection_guidance         │
    │      │                                                        │
    │      ├─ 4. Critic评审                                       │
    │      │     └─ 获取新的avg_score                             │
    │      │                                                        │
    │      ├─ 5. 分数退化检测                                     │
    │      │     └─ 如果 avg_score < last_score - 0.1:           │
    │      │         ├─ 回滚到上一版本                            │
    │      │         ├─ 标记Pattern失败                           │
    │      │         └─ 跳过该Pattern                             │
    │      │                                                        │
    │      ├─ 6. 记录最佳结果                                     │
    │      │     └─ 如果 avg_score > best_score:                 │
    │      │         └─ 更新best_score和best_story                │
    │      │                                                        │
    │      ├─ 7. 通过检查                                         │
    │      │     └─ 如果 avg_score >= 7.0:                       │
    │      │         └─ 提前结束,进入阶段5                        │
    │      │                                                        │
    │      └─ 循环结束                                            │
    │           │                                                   │
    │           └─ 兜底: 返回best_story (最高分版本)              │
    │                                                               │
    └─────────────────────────────────────────────────────────────┘
    │
    ├─────────────────────────────────────────────────────────────┐
    │              【阶段4.2: 普通修正】(1-2分钟)                  │
    ├─────────────────────────────────────────────────────────────┤
    │                                                               │
    │  智能注入互补Tricks                                          │
    │      │                                                        │
    │      ├─ 分析Critic反馈                                      │
    │      │   ├─ novelty_score < 6.0 → 缺新颖性                 │
    │      │   ├─ methodology_score < 6.0 → 缺稳健性              │
    │      │   └─ storyteller_score < 6.0 → 缺叙事性              │
    │      │                                                        │
    │      ├─ 选择互补Pattern                                     │
    │      │   ├─ 缺新颖性 → 长尾注入 (Rank 5-10, Novelty类)     │
    │      │   ├─ 缺稳健性 → 头部注入 (Rank 1-3, Stability类)    │
    │      │   └─ 缺叙事性 → 跨域注入 (Cross-Domain类)            │
    │      │                                                        │
    │      └─ 返回阶段2 (重新生成Story)                           │
    │                                                               │
    └─────────────────────────────────────────────────────────────┘
    │
    ▼
【阶段5: RAG查重】(约30秒)
    │
    ├─ 提取关键方法 (techniques)
    │
    ├─ 检索近3年顶会论文 (Embedding召回)
    │
    ├─ 计算相似度
    │
    └─ 判断: 相似度 > 0.75?
        ├─【否】→ 输出Final Story ✅
        └─【是】→ Pivot规避
                  ├─ 分析撞车点
                  ├─ 生成约束 (禁用技术/领域迁移)
                  └─ 返回阶段2
    │
    ▼
输出Final Story (JSON格式)
```

**流程说明**:
- **阶段1-2**: 基础生成链路
- **阶段3**: 质量评估
- **阶段4**: 核心修正机制(两种模式)
  - **新颖性模式**: 深度探索,Fusion+Reflection
  - **普通修正**: 快速注入,互补增强
- **阶段5**: 查重验证

### 1.2 核心模块

| 模块 | 文件 | 作用 |
|------|------|------|
| **Pattern Selector** | `pattern_selector.py` | 多维度Pattern分类与排序 |
| **Story Generator** | `story_generator.py` | 结构化Story生成 |
| **Idea Fusion** | `planner.py` | 融合新Pattern生成创新Idea |
| **Story Reflector** | `story_reflector.py` | 反思融合质量 |
| **Multi-Agent Critic** | `critic.py` | 三角色评审 |
| **Refinement Engine** | `refinement.py` | 智能修正与注入 |
| **RAG Verifier** | `verifier.py` | 查重与规避 |
| **Pipeline Manager** | `manager.py` | 流程编排 |

---

## 2. Pattern选择与分类

### 2.1 多维度分类

**目标**: 将召回的Top-10 Pattern按3个维度分类,确保多样性。

**维度定义**:

| 维度 | 定义 | 选择标准 | 作用 |
|------|------|---------|------|
| **Stability** | 稳健型 | Rank Top-3 + Cluster Size ≥ 15 | 保证基础质量,降低风险 |
| **Novelty** | 新颖型 | Cluster Size < 10 | 提升创新性 |
| **Cross-Domain** | 跨域型 | 来自路径2/3 + Domain不同于Top-1 | 引入跨领域视角 |

**算法**:

```python
def classify_patterns(recalled_patterns, user_idea):
    """多维度分类Pattern"""
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

        # 维度1: Stability (稳健型)
        if rank <= 2 and metadata['cluster_size'] >= 15:
            classified['stability'].append((pattern_id, pattern_info, metadata))

        # 维度2: Novelty (新颖型)
        if metadata['cluster_size'] < 10:
            classified['novelty'].append((pattern_id, pattern_info, metadata))

        # 维度3: Cross-Domain (跨域型)
        if rank >= 3:  # 来自路径2/3
            user_domain = extract_domain(user_idea)
            pattern_domain = pattern_info.get('domain', '')
            if pattern_domain != user_domain:
                classified['cross_domain'].append((pattern_id, pattern_info, metadata))

    return classified
```

### 2.2 Pattern选择策略

```python
# 优先级顺序
1. Stability 维度第一个 (保证基础质量)
2. Novelty 维度第一个 (如果stability为空)
3. Cross-Domain 维度第一个 (兜底)
```

---

## 3. Story生成机制

### 3.1 Story数据结构

```json
{
  "title": "论文标题",
  "abstract": "摘要(150-200词)",
  "problem_definition": "明确的问题定义",
  "gap_pattern": "研究缺口描述",
  "method_skeleton": {
    "overview": "方法概述",
    "core_components": ["组件1", "组件2", "组件3"],
    "technical_details": "技术细节"
  },
  "innovation_claims": [
    "贡献点1",
    "贡献点2",
    "贡献点3"
  ],
  "experiments_plan": {
    "datasets": ["数据集1", "数据集2"],
    "baselines": ["基线方法1", "基线方法2"],
    "metrics": ["评估指标1", "指标2"],
    "ablation_studies": "消融实验设计"
  }
}
```

### 3.2 生成Prompt构建

**初稿生成Prompt**:
```python
def _build_initial_prompt(user_idea, pattern_info):
    prompt = f"""
你是一个顶级AI研究员。请基于以下信息生成一篇ICLR水平的论文Story。

【用户Idea】
{user_idea}

【Pattern指导】
名称: {pattern_info['name']}
代表性想法: {pattern_info['llm_enhanced_summary']['representative_ideas']}
常见问题: {pattern_info['llm_enhanced_summary']['common_problems']}
解决方法: {pattern_info['llm_enhanced_summary']['solution_approaches']}
故事框架: {pattern_info['llm_enhanced_summary']['story']}

【任务】
生成完整的论文Story(JSON格式),包含:
- title: 吸引人的标题
- abstract: 150-200词摘要
- problem_definition: 明确问题定义
- gap_pattern: 研究缺口
- method_skeleton: 方法骨架(overview + core_components + technical_details)
- innovation_claims: 3个核心贡献
- experiments_plan: 实验设计(datasets/baselines/metrics/ablation_studies)
"""
    return prompt
```

**Refinement Prompt**:
```python
def _build_refinement_prompt(story, critic_result, fused_idea, reflection_guidance):
    prompt = f"""
【当前Story】
{json.dumps(story, indent=2)}

【Critic评审结果】
Methodology: {critic_result['methodology']['score']}/10
  问题: {critic_result['methodology']['issues']}

Novelty: {critic_result['novelty']['score']}/10
  问题: {critic_result['novelty']['issues']}

【融合创新指导】
{format_fused_idea(fused_idea)}

【Reflection建议】
{format_reflection_guidance(reflection_guidance)}

⚠️ 【HOW TO USE Fused Idea Guidance】
- **Title & Abstract**: 必须反映融合后的概念创新,而非技术堆砌
- **Problem Framing**: 采用融合idea中的新问题视角
- **Gap Pattern**: 解释为什么现有方法缺乏这种概念统一性
- **Innovation Claims**: 框架为"transforming/reframing X from Y to Z"
- **Method**: 展示技术如何共同演化(CO-EVOLVE)而非共存(CO-EXIST)

【任务】
修正Story,重点解决上述问题,生成改进版JSON。
"""
    return prompt
```

---

## 4. Idea Fusion机制

### 4.1 融合目标

**问题**: 直接拼接Pattern会导致"技术堆砌",缺乏概念统一性。

**目标**: 生成一个**有机融合**的新Idea,使新Pattern与原Idea在**概念层面**统一。

### 4.2 Fusion Prompt

```python
def plan_idea_fusion(user_idea, current_story, new_pattern_info, critic_issues):
    prompt = f"""
你是一个创新研究规划师。请分析如何将新Pattern融合到现有研究中。

【当前研究】
Idea: {user_idea}
Story: {extract_key_points(current_story)}

【新Pattern】
{format_pattern(new_pattern_info)}

【Critic指出的问题】
{critic_issues}

【融合任务】
生成一个融合后的Idea,要求:

1. **概念统一**: 找到新Pattern与原Idea的概念连接点
2. **问题重构**: 重新框架问题,使新Pattern成为自然解决方案
3. **创新点**: 明确融合后的独特贡献

返回JSON:
{
  "fused_core_idea": "融合后的核心想法(单句话)",
  "conceptual_bridge": "概念桥梁:如何连接原Idea和新Pattern",
  "reframed_problem": "重构后的问题定义",
  "innovation_angle": "独特创新点",
  "implementation_hints": ["实现提示1", "提示2"]
}
"""
    return prompt
```

### 4.3 示例

**原Idea**:
```
使用大模型做数据增强
```

**新Pattern**: 课程学习(Curriculum Learning)

**Fusion结果**:
```json
{
  "fused_core_idea": "基于LLM生成的难度自适应课程学习框架",
  "conceptual_bridge": "LLM不仅生成数据,更重要的是可以评估样本难度,从而构建个性化学习路径",
  "reframed_problem": "如何让模型像人类一样从易到难地学习LLM生成的伪标签数据",
  "innovation_angle": "首次将LLM的生成能力和难度评估能力统一在课程学习框架中",
  "implementation_hints": [
    "LLM为每个生成样本打上难度标签",
    "设计难度感知的样本调度器",
    "渐进式训练策略"
  ]
}
```

---

## 5. Story Reflection机制

### 5.1 反思目标

**问题**: Fusion生成了融合Idea,但Story生成器可能:
- 未充分理解融合意图
- 生成了"生硬拼接"而非"有机融合"

**目标**: 在Story生成后,反思融合质量,评估是否真正实现了概念统一。

### 5.2 Reflection流程

```python
def reflect_on_fusion(fused_idea, generated_story):
    """反思融合质量"""
    # 1. 分析融合点
    fusion_points = analyze_fusion_points(fused_idea, generated_story)

    # 2. 检查连贯性
    coherence = check_conceptual_coherence(fusion_points)

    # 3. 评估融合丰富度
    richness = evaluate_fusion_richness(fused_idea, generated_story)

    # 4. 计算质量分数
    quality = 0.4 * coherence + 0.4 * richness + 0.2 * has_fusion_idea_bonus

    # 5. 生成改善建议
    suggestions = generate_improvement_suggestions(quality, fusion_points)

    return {
        'fusion_quality': quality,
        'fusion_points': fusion_points,
        'coherence_score': coherence,
        'fusion_richness': richness,
        'fusion_suggestions': suggestions
    }
```

### 5.3 质量评分

```python
fusion_quality = 0.4 × 连贯性 + 0.4 × 融合丰富度 + 0.2 × Fusion Idea奖励

# 连贯性: 融合点在Story各部分是否连贯出现
coherence_score = len(连贯的融合点) / len(所有融合点)

# 融合丰富度: Story中多少部分体现了融合
richness_score = len(体现融合的Story部分) / len(Story总部分)

# Fusion Idea奖励: 是否使用了fused_idea指导
fusion_idea_bonus = 1.0 if fused_idea else 0.5
```

**阈值**: `fusion_quality >= 0.65` 认为融合成功

---

## 6. Critic评审机制

### 6.1 三角色评审

| 角色 | 关注点 | 评分标准 |
|------|--------|---------|
| **Reviewer A** (Methodology) | 技术合理性、实验完整性 | 方法可行性、实验设计 |
| **Reviewer B** (Novelty) | 创新性、贡献独特性 | 问题新颖度、方法创新度 |
| **Reviewer C** (Storyteller) | 叙事完整性、逻辑连贯性 | 结构完整、逻辑清晰 |

### 6.2 Critic Prompt

```python
def build_critic_prompt(story, role):
    if role == "methodology":
        focus = """
评审重点:
1. 方法是否技术合理?
2. 实验设计是否完整?
3. 是否存在技术风险?
"""
    elif role == "novelty":
        focus = """
评审重点:
1. 问题定义是否新颖?
2. 方法是否有独特创新?
3. 是否仅是技术堆砌?
"""
    elif role == "storyteller":
        focus = """
评审重点:
1. 逻辑是否连贯?
2. 叙事是否完整?
3. 读者能否理解?
"""

    prompt = f"""
你是一个ICLR审稿人,专注于{role}。

【论文Story】
{json.dumps(story, indent=2)}

{focus}

【任务】
返回JSON评审结果:
{{
  "score": 7,  # 1-10分
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"]
}}
"""
    return prompt
```

### 6.3 通过标准

```python
PASS_SCORE = 7.0

# 所有三个维度的平均分 >= 7.0
avg_score = (methodology_score + novelty_score + storyteller_score) / 3
if avg_score >= PASS_SCORE:
    return "PASS"
else:
    return "FAIL"
```

---

## 7. 智能修正机制

### 7.1 新颖性模式

**触发条件**:
```python
# 新颖性分数停滞
if novelty_score <= last_novelty_score + 0.5:
    activate_novelty_mode()
```

**工作流程**:
```python
def novelty_mode(ranked_patterns):
    """新颖性模式: 遍历所有novelty维度的Pattern"""
    novelty_patterns = ranked_patterns['novelty']
    best_score = 0
    best_story = None

    for pattern in novelty_patterns[:NOVELTY_MODE_MAX_PATTERNS]:
        # 1. Idea Fusion
        fused_idea = plan_idea_fusion(user_idea, current_story, pattern)

        # 2. Story Reflection
        reflection_result = reflect_on_fusion(fused_idea, current_story)

        # 3. 生成终稿Story
        new_story = generate_story(
            pattern,
            fused_idea=fused_idea,
            reflection_guidance=reflection_result['fusion_suggestions']
        )

        # 4. Critic评审
        critic_result = critic.review(new_story)

        # 5. 分数退化检测
        if critic_result['avg_score'] < last_avg_score - 0.1:
            # 回滚
            rollback()
            mark_failure(pattern)
            continue

        # 6. 记录最高分
        if critic_result['avg_score'] > best_score:
            best_score = critic_result['avg_score']
            best_story = new_story

        # 7. 通过检查
        if critic_result['avg_score'] >= PASS_SCORE:
            return new_story

    # 8. 兜底: 返回最高分版本
    return best_story
```

### 7.2 分数退化回滚

**检测条件**:
```python
# 任一维度分数下降超过0.1
if (new_methodology_score < old_methodology_score - 0.1 or
    new_novelty_score < old_novelty_score - 0.1 or
    new_storyteller_score < old_storyteller_score - 0.1):
    trigger_rollback()
```

**回滚流程**:
```python
def rollback():
    """回滚到上一个版本"""
    # 1. 恢复Story
    current_story = last_story_before_refinement

    # 2. 标记失败Pattern
    pattern_failure_map[pattern_id].add(issue_type)

    # 3. 删除注入的Tricks
    injected_tricks.remove(failed_trick)

    # 4. 继续迭代(不增加iterations计数)
```

### 7.3 普通修正模式

**触发条件**: 新颖性未停滞,但评分未通过

**Critic诊断与Pattern维度映射**: 系统将Critic的三个评审角色直接映射到Pattern的三个分类维度,实现统一的修正策略。

| Critic角色 | 评审焦点 | 诊断问题类型 | 映射Pattern维度 | 注入策略 |
|-----------|---------|------------|----------------|---------|
| **Novelty** | 创新性 | `novelty` | **Novelty维度** | 从novelty维度按序选择Pattern,注入创新方法 |
| **Methodology** | 技术合理性 | `stability` | **Stability维度** | 从stability维度按序选择Pattern,注入稳健方法 |
| **Storyteller** | 叙事完整性 | `domain_distance` | **Domain Distance维度** | 从domain_distance维度选择Pattern,引入跨域视角 |

**核心设计理念**:
- **统一映射**: Critic的诊断结果直接映射到Pattern的三个分类维度,避免额外的启发式规则
- **维度一致**: Pattern Selector已按三个维度(稳健度、新颖度、跨域度)对所有Pattern排序,Refinement Engine直接复用这些排序结果
- **策略简化**: 不再需要"解释性注入"、"领域适配注入"等额外策略,所有修正统一通过Pattern维度选择实现

**注入逻辑**:
```python
def refine_with_idea_fusion(main_issue: str, suggestions: List[str],
                            previous_story: Optional[Dict] = None) -> Tuple[List[str], Optional[Dict]]:
    """基于Critic诊断,从对应Pattern维度选择并融合"""

    # Step 1: 维度映射
    dimension_map = {
        'novelty': 'novelty',          # Novelty Critic → Novelty维度
        'stability': 'stability',      # Methodology Critic → Stability维度
        'domain_distance': 'domain_distance'  # Storyteller Critic → Domain Distance维度
    }
    dimension = dimension_map[main_issue]

    # Step 2: 从对应维度选择Pattern
    patterns = ranked_patterns[dimension]
    idx = dimension_indices[dimension]  # 维度内的当前索引

    while idx < len(patterns):
        pattern_id, pattern_info, metadata = patterns[idx]

        # 跳过已失败的Pattern
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

        # Step 4: 返回融合结果
        return injected_tricks, fused_result
```

**示例场景**:
```
场景: Storyteller Critic给出低分(叙事不连贯)
→ 诊断: domain_distance
→ 选择: 从domain_distance维度(按领域距离升序排列)选择Pattern
→ 效果: 引入不同领域的叙事视角,丰富Story结构
```

---

## 8. RAG查重与规避

### 8.1 查重流程

```python
def verify_collision(story):
    """RAG查重"""
    # 1. 提取关键方法
    method_keywords = extract_method_keywords(story)

    # 2. 构建Query
    query = f"{method_keywords} {story['problem_definition']}"

    # 3. 检索近3年顶会论文
    similar_papers = retrieve_similar_papers(query, top_k=10)

    # 4. 计算相似度
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

### 8.2 Pivot规避策略

**触发条件**: `similarity > 0.75`

**规避流程**:
```python
def pivot_to_avoid_collision(story, collided_paper):
    """生成规避约束"""
    # 1. 撞车分析
    collision_analysis = analyze_collision(story, collided_paper)

    # 2. 生成约束
    constraints = {
        'forbidden_techniques': collision_analysis['overlapping_techniques'],
        'pivot_direction': "迁移到无监督设定",
        'domain_shift': "从通用领域迁移到法律文本",
        'additional_constraint': "增加长文本处理模块"
    }

    # 3. 重新生成Story
    new_story = generate_story(pattern, constraints=constraints)

    return new_story
```

---

## 9. 参数配置

### 9.1 Pipeline配置

```python
# scripts/pipeline/config.py

class PipelineConfig:
    """Pipeline配置参数"""

    # Pattern选择
    SELECT_PATTERN_COUNT = 3              # 选择3个不同策略的Pattern
    CONSERVATIVE_RANK_RANGE = (0, 2)      # 稳健型: Rank 1-3
    INNOVATIVE_CLUSTER_SIZE_THRESHOLD = 10 # 创新型: Cluster Size < 10

    # Critic阈值
    PASS_SCORE = 7.0                      # 评分 >= 7 为通过
    MAX_REFINE_ITERATIONS = 3             # 最多修正3轮(普通模式)

    # 新颖性模式配置
    NOVELTY_MODE_MAX_PATTERNS = 10        # 新颖性模式最多尝试的Pattern数
    NOVELTY_SCORE_THRESHOLD = 6.0         # 新颖性得分阈值
    NOVELTY_STAGNATION_DELTA = 0.5        # 停滞判定阈值

    # Reflection配置
    FUSION_QUALITY_THRESHOLD = 0.65       # 融合质量阈值

    # 回滚配置
    SCORE_DEGRADATION_THRESHOLD = 0.1     # 分数下降阈值

    # RAG查重阈值
    COLLISION_THRESHOLD = 0.75            # 相似度 > 0.75 认为撞车

    # Refinement策略
    TAIL_INJECTION_RANK_RANGE = (4, 9)    # 长尾注入: Rank 5-10
    HEAD_INJECTION_RANK_RANGE = (0, 2)    # 头部注入: Rank 1-3
    HEAD_INJECTION_CLUSTER_THRESHOLD = 15 # 头部注入: Cluster Size > 15
```

### 9.2 LLM配置

```python
# scripts/pipeline/config.py

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_PROVIDER = "openai_compatible_chat"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
```

---

## 10. 运行方式

### 10.1 完整Pipeline运行

**命令**:
```bash
cd /Users/gaoge/code/mycode/Idea2Paper/Paper-KG-Pipeline
python scripts/idea2story_pipeline.py "你的研究Idea描述"
```

**示例**:
```bash
python scripts/idea2story_pipeline.py "使用强化学习优化大模型的推理效率"
```

**输出**:
```
output/
├── final_story.json          # 最终生成的论文Story
├── pipeline_result.json      # 完整流程结果
└── log.json                  # 详细日志
```

### 10.2 输出结构

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

### 10.3 监控关键指标

**新颖性模式激活**:
```bash
grep "激活【新颖性模式】" output/log.json
```

**融合质量评分**:
```bash
grep "融合质量评分" output/log.json
```

**回滚事件**:
```bash
grep "【ROLLBACK TRIGGERED】" output/log.json
```

**最终通过情况**:
```bash
grep "🎉 Critic 评审通过" output/log.json
```

---

## 11. 流程详细示例

### 11.1 场景A: 新颖性停滞触发新模式

**初始状态**:
```
Iteration 1: Novelty Score = 5.5
Iteration 2: Novelty Score = 5.6 (仅提升0.1 < 0.5)
→ 触发新颖性模式
```

**新颖性模式流程**:
```
1. 激活新颖性模式
2. 遍历Novelty Pattern列表 (最多10个)

  Pattern 1 (pattern_42):
    ├─ Idea Fusion: 生成融合Idea
    ├─ Story Reflection: 融合质量评分0.72
    ├─ 生成终稿Story (基于reflection建议)
    ├─ Critic评审: 6.5/10 (未通过)
    └─ 继续下一个Pattern

  Pattern 2 (pattern_55):
    ├─ Idea Fusion: 生成融合Idea
    ├─ Story Reflection: 融合质量评分0.68
    ├─ 生成终稿Story
    ├─ Critic评审: 7.2/10 (通过!)
    └─ 进入RAG查重

3. RAG查重: 未撞车
4. 输出Final Story
```

### 11.2 场景B: 分数退化触发回滚

```
Iteration 3:
  当前分数: Methodology=7.0, Novelty=6.0, Storyteller=7.5

  注入Pattern_30:
    ├─ Idea Fusion: ...
    ├─ 生成新Story
    ├─ Critic评审: Methodology=6.2 (下降0.8 > 0.1)
    ├─ 检测到分数退化
    └─ 触发回滚

  回滚操作:
    ├─ 恢复Story到注入前版本
    ├─ 标记Pattern_30失败
    ├─ 删除注入的Tricks
    └─ 继续迭代(不增加计数)

  选择下一个Pattern: Pattern_45
    ├─ Idea Fusion: ...
    ├─ 生成新Story
    ├─ Critic评审: Methodology=7.3 (提升)
    └─ 保存结果
```

---

## 12. 最终版本选择机制

### 12.1 全局最优追踪

**设计理念**: 在整个迭代过程中,每一轮生成的Story可能有不同的优劣,系统需要记录并最终选择最优版本。

**核心机制**:
```python
# 每轮Critic评审后更新全局最佳版本
if current_avg_score > global_best_score:
    global_best_story = current_story
    global_best_score = current_avg_score
    global_best_iteration = iteration_number
    print(f"🏆 更新全局最佳版本: 得分 {global_best_score:.2f}")
```

### 12.2 最终输出逻辑

**优先级规则**:
1. **优先**: 如果有通过Critic评审的版本(avg_score >= 7.0) → 使用通过版本
2. **兜底**: 如果没有通过版本 → 使用全局最佳版本(迭代中得分最高)

**实现流程**:
```python
# 最终版本选择
final_story = current_story  # 默认当前版本
final_is_passed = review_history[-1]['pass']

if not final_is_passed and global_best_story is not None:
    # 未通过但有最佳版本
    if global_best_score > current_score:
        final_story = global_best_story  # 使用最佳版本
        print(f"✅ 使用全局最佳版本(迭代 {global_best_iteration}, 得分 {global_best_score:.2f})")
```

### 12.3 典型场景

**场景A: 逐步提升,最终通过**
```
迭代1: 初稿 → 6.17分 → 更新最佳版本
迭代2: 注入Novelty Pattern → 6.85分 → 更新最佳版本
迭代3: 继续优化 → 7.20分 → 通过! ✅
→ 输出: 迭代3的通过版本
```

**场景B: 起伏波动,未通过**
```
迭代1: 初稿 → 6.17分 → 更新最佳版本
迭代2: 注入Pattern → 6.85分 → 更新最佳版本
迭代3: 回滚后优化 → 6.50分 → 未更新
→ 输出: 迭代2的最佳版本(6.85分)
```

**场景C: 新颖性模式遍历**
```
新颖性模式:
  Pattern 1 → 6.50分 → 更新最佳版本
  Pattern 2 → 6.35分 → 未更新
  Pattern 3 → 6.80分 → 更新最佳版本
