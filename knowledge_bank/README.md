# Knowledge Bank Module

Durham AI Education System Upgrade hackathon MVP 的 Knowledge Bank 核心模块。

这个模块不是内容生成器，也不是简单文件仓库。它的职责是把原始教学资料注册进系统，整理成结构化 knowledge units，做最小审批闸门，然后把和某个 topic 相关的已批准内容打包成统一 JSON bundle 交给下游模块。

## 1. 模块定位

Knowledge Bank 是当前系统里的知识底座，负责四件事：

1. 接收和登记原始 source
2. 将预处理后的内容写入 canonical knowledge store
3. 用 `draft / approved` 作为最小治理边界
4. 按 topic/module/week 打包下游可消费的 context bundle

当前 hackathon MVP 的设计重点是：

- 可运行
- 可调试
- 字段稳定
- 接口稳定
- 方便其他模块今晚接入

## 2. 当前业务边界

Knowledge Bank 负责：

- `source registry`
- `knowledge unit store`
- `draft / approved` 状态管理
- metadata-first retrieval
- generation-ready context bundle
- cohort signal write-in
- graph / summary / detail inspection

Knowledge Bank 不负责：

- 直接生成 PPT / lecture / worksheet
- 完整权限系统
- 复杂工作流审批
- 自动修改 canonical knowledge 以响应 cohort signal
- 必须依赖向量检索才能工作

补充说明：

- 当前 MVP 主链以 `metadata-first retrieval` 为主
- embedding / Chroma 可以作为增强层存在，但不是本次最小交付的必需条件

## 3. 数据对象

### 3.1 Source

表示进入系统的原始资料。

字段：

- `source_id`
- `filename`
- `source_type`
- `module_tag`
- `week_tag`
- `uploader`
- `hash`
- `storage_path`
- `created_at`

### 3.2 Knowledge Unit

表示可检索、可审批、可打包给下游的知识单元。

字段：

- `knowledge_id`
- `title`
- `summary`
- `body_text`
- `module_tag`
- `week_tag`
- `topic_tags`
- `difficulty_level`
- `pedagogical_role`
- `source_type`
- `source_ref`
- `approval_status`
- `prerequisite_links`
- `learning_outcome_links`
- `version_number`
- `created_at`
- `updated_at`

### 3.3 Cohort Signal

表示测试/分析模块写回的班级级别信号。

字段：

- `signal_id`
- `tested_deck_id`
- `related_knowledge_ids`
- `weak_topics`
- `repeated_confusion_points`
- `misconception_clusters`
- `evidence_refs`
- `created_at`

## 4. 核心业务规则

这些规则是其他模块接入时必须遵守的：

1. 下游生成只读取 `approved` knowledge units
2. `draft` 可以被检索和人工查看，但不能作为正式 generation input
3. `cohort_signals` 不会自动修改 `knowledge_units`
4. source 上传成功不依赖完美解析
5. `context-bundle` 是下游消费 Knowledge Bank 的核心合同
6. 当前最小 MVP 以 metadata-first 为主，不把语义向量召回当成唯一依赖

## 5. 模块输入与输出

### 5.1 输入

Knowledge Bank 接收三类输入：

1. 原始 source 文件
2. 预处理后的 `compiled_units`
3. 下游测试/分析模块写回的 `cohort signal`

### 5.2 输出

Knowledge Bank 输出四类结果：

1. source metadata
2. knowledge unit detail / search result
3. approved-only context bundle
4. graph / summary / inspection data

## 6. API 总览

### Sources

- `POST /sources/upload`
- `GET /sources`
- `GET /sources/{source_id}`

### Knowledge

- `POST /knowledge/compile`
- `GET /knowledge/search`
- `GET /knowledge/{knowledge_id}`
- `GET /knowledge/context-bundle`
- `GET /knowledge/summary`
- `GET /knowledge/graph`

### Approvals

- `POST /approvals/{knowledge_id}`
- `POST /approvals/bulk`

### Signals

- `POST /signals/cohort`

## 7. 详细 API 契约

## 7.1 `POST /sources/upload`

用途：

- 上传原始资料
- 注册 source
- 保存原文件
- 生成 hash 和 `source_id`

输入：

- `multipart/form-data`
- 文件字段：`file`
- 表单字段：
  - `module_tag`
  - `week_tag` 可选
  - `uploader`

输出示例：

```json
{
  "source_id": "src_d608f4f6",
  "filename": "ml_book.pdf",
  "source_type": "pdf",
  "module_tag": "Machine Learning",
  "week_tag": "week_08",
  "uploader": "codex",
  "hash": "sha256...",
  "storage_path": "backend/storage/raw/src_d608f4f6_ml_book.pdf",
  "created_at": "2026-04-17T10:30:00"
}
```

## 7.2 `GET /sources`

用途：

- 列出 source
- 支持按元数据过滤

查询参数：

- `module`
- `week`
- `source_type`

输出：

- `Source[]`

## 7.3 `GET /sources/{source_id}`

用途：

- 获取单个 source 详情

输出：

- `Source`

## 7.4 `POST /knowledge/compile`

用途：

- 将 source 对应的预处理结果写成 knowledge units
- 或直接接收上游提供的 `compiled_units`

支持两种模式。

### Mode A: 自动 compile

输入示例：

```json
{
  "source_id": "src_d608f4f6"
}
```

行为：

- 根据当前 source 的预处理数据自动生成 compiled units
- 写入 `knowledge_units`
- 新写入的 units 默认是 `draft`

### Mode B: 显式 compiled_units

输入示例：

```json
{
  "source_id": "src_d608f4f6",
  "compiled_units": [
    {
      "title": "Simple linear regression",
      "summary": "Core idea and intuition.",
      "body_text": "Detailed learning content...",
      "module_tag": "Machine Learning",
      "week_tag": "week_08",
      "topic_tags": ["linear regression", "supervised learning"],
      "difficulty_level": "beginner",
      "pedagogical_role": "concept",
      "source_type": "pdf",
      "source_ref": ["src_d608f4f6"],
      "approval_status": "draft",
      "prerequisite_links": [],
      "learning_outcome_links": ["understand regression basics"],
      "version_number": 1
    }
  ]
}
```

输出示例：

```json
{
  "source_id": "src_d608f4f6",
  "created_knowledge_ids": ["kb_12345678", "kb_23456789"],
  "status": "created"
}
```

## 7.5 `GET /knowledge/search`

用途：

- metadata-first 检索 knowledge units
- 用于列表、调试、运营查看和 topic 搜索

查询参数：

- `module`
- `week`
- `topic`
- `approval_status`
- `pedagogical_role`
- `difficulty_level`
- `q`

行为规则：

1. 先按 module / week / approval_status / role 过滤
2. 再按 topic 过滤
3. 再做轻量文本匹配
4. 返回摘要对象，不返回完整大正文

输出：

- `KnowledgeUnitSummary[]`

## 7.6 `GET /knowledge/{knowledge_id}`

用途：

- 获取单条 knowledge unit 的完整详情

输出：

- `KnowledgeUnitDetail`

## 7.7 `POST /approvals/{knowledge_id}`

用途：

- 单条知识单元审批

输入示例：

```json
{
  "target_status": "approved",
  "reviewer": "Professor Yang Long",
  "decision_reason": "Reviewed for downstream generation"
}
```

行为：

- 仅支持 `draft -> approved`

输出示例：

```json
{
  "knowledge_id": "kb_12345678",
  "old_status": "draft",
  "new_status": "approved",
  "reviewer": "Professor Yang Long",
  "decision_reason": "Reviewed for downstream generation"
}
```

## 7.8 `POST /approvals/bulk`

用途：

- 按 topic/module/week 批量审批

输入示例：

```json
{
  "target_status": "approved",
  "reviewer": "Professor Yang Long",
  "decision_reason": "Approve topic bundle candidates",
  "module": "Machine Learning",
  "week": "week_08",
  "topic": "linear regression"
}
```

输出示例：

```json
{
  "approved_count": 24,
  "knowledge_ids": ["kb_1", "kb_2", "kb_3"]
}
```

## 7.9 `GET /knowledge/context-bundle`

这是当前最重要的下游合同接口。

用途：

- 接收一个 topic scope
- 从当前数据库中筛出相关的、已 `approved` 的知识单元
- 打包成 generation-ready JSON bundle

查询参数：

- `module`
- `week`
- `topic`
- `generation_target`
- `difficulty_level`

输出示例：

```json
{
  "module_tag": "Machine Learning",
  "week_tag": "week_08",
  "topic_scope": ["linear regression"],
  "generation_target": "pptx",
  "approved_context_bundle": [
    {
      "knowledge_id": "kb_12345678",
      "title": "Simple linear regression",
      "summary": "Core idea and intuition.",
      "body_text": "Detailed learning content...",
      "module_tag": "Machine Learning",
      "week_tag": "week_08",
      "topic_tags": ["linear regression", "supervised learning"],
      "difficulty_level": "beginner",
      "pedagogical_role": "concept",
      "source_type": "pdf",
      "source_ref": ["src_d608f4f6"],
      "approval_status": "approved",
      "prerequisite_links": [],
      "learning_outcome_links": ["understand regression basics"],
      "version_number": 1,
      "created_at": "2026-04-17T10:30:00",
      "updated_at": "2026-04-17T10:45:00"
    }
  ],
  "supporting_source_chunks": [],
  "source_registry_refs": [
    {
      "source_id": "src_d608f4f6",
      "filename": "ml_book.pdf",
      "source_type": "pdf",
      "module_tag": "Machine Learning",
      "week_tag": "week_08",
      "uploader": "codex",
      "hash": "sha256...",
      "storage_path": "backend/storage/raw/src_d608f4f6_ml_book.pdf",
      "created_at": "2026-04-17T10:30:00"
    }
  ],
  "retrieval_trace": {
    "vector_search_used": false
  }
}
```

关键规则：

- `approved_context_bundle` 只允许出现 `approved`
- 这是 content generation agent 读取的核心部分
- 下游应以这个字段为正式输入，不要绕过它直接扫数据库

## 7.10 `POST /signals/cohort`

用途：

- 接收测试/分析模块写回的 cohort-level signal

输入示例：

```json
{
  "tested_deck_id": "deck_week08_linear_regression",
  "related_knowledge_ids": ["kb_12345678", "kb_23456789"],
  "weak_topics": ["linear regression", "gradient descent"],
  "repeated_confusion_points": [
    "difference between cost function and loss",
    "interpretation of slope coefficient"
  ],
  "misconception_clusters": [
    "students mix up correlation and causation"
  ],
  "evidence_refs": [
    "quiz_2026_04_17",
    "assessment_batch_3"
  ]
}
```

输出示例：

```json
{
  "signal_id": "sig_12345678",
  "status": "created"
}
```

关键规则：

- signal 写入不会自动修改 `knowledge_units`
- 如果需要基于 signal 调整知识内容，应走新的 compile / review 流程

## 7.11 `GET /knowledge/summary`

用途：

- 返回 dashboard 计数

输出示例：

```json
{
  "registered_sources": 1,
  "draft_units": 76,
  "approved_units": 25,
  "latest_update_at": "2026-04-17T11:07:26"
}
```

## 7.12 `GET /knowledge/graph`

用途：

- 返回图谱渲染所需的 node-edge 数据

输出示例：

```json
{
  "nodes": [
    {
      "id": "src_d608f4f6",
      "label": "ml_book.pdf",
      "type": "source"
    },
    {
      "id": "kb_12345678",
      "label": "Simple linear regression",
      "type": "knowledge_unit",
      "status": "approved"
    }
  ],
  "edges": [
    {
      "source": "src_d608f4f6",
      "target": "kb_12345678",
      "type": "derived_from"
    },
    {
      "source": "kb_00000001",
      "target": "kb_12345678",
      "type": "prerequisite"
    }
  ]
}
```

## 8. 统一对接方式

## 8.1 上游资料接入模块

适用对象：

- 文件采集模块
- OCR / parser / preprocessing 模块
- 人工整理脚本

接入方式：

1. 调 `POST /sources/upload` 注册原始资料
2. 将预处理结果整理成 `compiled_units`
3. 调 `POST /knowledge/compile`

建议：

- 不要让上游直接写数据库
- 统一通过 API 写入，避免字段漂移

## 8.2 内容生成模块

适用对象：

- content generation agent
- slide generator
- lecture planner

唯一推荐接入点：

- `GET /knowledge/context-bundle`

推荐调用方式：

```http
GET /knowledge/context-bundle?module=Machine%20Learning&week=week_08&topic=linear%20regression&generation_target=pptx
```

接入原则：

1. 只读取 `approved_context_bundle`
2. 不直接从数据库表里抓原始记录
3. 不把 `draft` 内容当成正式生成依据
4. `source_registry_refs` 只作为追踪和引用来源，不是主生成内容

## 8.3 测试 / 分析模块

适用对象：

- assessment engine
- analytics service
- cohort diagnosis module

接入方式：

1. 下游完成测试分析
2. 聚合成班级级别信号
3. 调 `POST /signals/cohort`

规则：

- 不要直接改 `knowledge_units`
- 不要把 signal 当审批结果
- signal 是反馈输入，不是 canonical knowledge 本身

## 8.4 前端 / 运维 / Demo 面板

推荐接口：

- `GET /knowledge/summary`
- `GET /knowledge/graph`
- `GET /knowledge/search`
- `GET /knowledge/{knowledge_id}`
- `GET /sources/{source_id}`

用途：

- 图谱展示
- 列表检索
- 状态监控
- 节点详情查看

## 9. 当前推荐 API Flow

### Flow A: 原始资料进入系统

1. 上传 source
2. 注册 source metadata
3. 保存原文件

### Flow B: 预处理内容进入 canonical knowledge store

1. source 预处理
2. 生成 `compiled_units`
3. `POST /knowledge/compile`
4. knowledge units 进入 `draft`

### Flow C: 进入下游生成主链

1. review / approval
2. `draft -> approved`
3. 下游传入 topic
4. `GET /knowledge/context-bundle`
5. 下游读取 `approved_context_bundle`

### Flow D: 测试反馈写回

1. assessment module 生成分析结果
2. 调 `POST /signals/cohort`
3. Knowledge Bank 存档 signal
4. 后续人工或新流程决定是否触发知识更新

## 10. 对其他模块的设计约束

Knowledge Bank 现在已经是接口基线，因此其他模块在设计时应遵守：

1. 不要绕过 Knowledge Bank 直接读写核心知识表
2. 不要擅自改 `knowledge unit` 字段名
3. 不要擅自把 `draft` 当作正式内容输入
4. topic 驱动的下游消费，统一走 `context-bundle`
5. feedback 统一走 `signals/cohort`

如果其他模块未来需要扩展字段，应优先：

1. 先在 Knowledge Bank schema 里扩展
2. 再统一更新接口文档
3. 最后通知下游同步调整

## 11. 启动方式

后端：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问：

- 前端：`http://localhost:9999`
- 后端文档：`http://localhost:8000/docs`

## 12. 当前 MVP 结论

当前 Knowledge Bank 已经完成的核心主链是：

`source -> compile -> draft -> approved -> context-bundle -> downstream`

这意味着：

- 它已经不是文件堆
- 它已经可以作为其他模块的对接核心
- 它已经可以稳定输出下游需要的 topic bundle

如果后续继续增强，优先顺序建议是：

1. 审批工作台和人工 review 体验
2. compile 质量提升
3. 可选语义检索增强
4. 与更多下游模块的 bundle 契约细化
