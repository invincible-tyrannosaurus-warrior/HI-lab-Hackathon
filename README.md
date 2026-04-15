# Durham AI Hackathon README

## 本次 Hackathon 的两个主任务

本次 hackathon 包含两条并行任务线：

### 1. Education System Upgrade
围绕 Durham AI Education System Upgrade，完成一个 **MVP 级别** 的 multi-agent educational workflow prototype。

### 2. Idea2Paper 学习与诊断任务
对 Idea2Paper 项目进行系统性学习、试用、评估，并总结它当前的能力边界与后续 upgrade 方向。

---

## Hackathon 的整体节奏

### 第一阶段：先介绍 Education System Upgrade 的整体 workflow
明天开始时，会先用一段时间快速介绍 **Education System Upgrade** 这条主线，帮助大家统一理解：

- 这个系统想解决什么问题
- 为什么当前教育内容生产流程需要升级
- 整体 workflow 是怎么设计的
- 各个模块分别负责什么
- 本次 hackathon 的 scope 和 MVP boundary 在哪里

这一部分的重点是先让所有人清楚理解这条核心主链路：

**source intake → knowledge compilation → approval / governance → content generation → student-agent testing → analytics / adaptation → governed revision**

也就是说，先把整个系统的 **workflow design、module responsibility、core logic、MVP target** 讲清楚，再进入真正的开发。

---

### 第二阶段：进入具体开发工作
在 workflow 和边界讲清楚之后，团队会立即进入具体开发。

核心目标是证明以下几点：

- approved knowledge 可以被系统化整理并提供给下游模块
- generation pipeline 能基于 approved knowledge 产出 grounded teaching content
- student-agent testing 能对生成内容进行基础测试
- analytics / adaptation 能把 learner-side evidence 转成 actionable recommendations
- governance trace 能清楚展示什么内容被采纳、什么内容不能直接进入 canonical flow

开发重点是完成一条清晰的 **end-to-end MVP pipeline**，而不是铺开做一个完整大系统。

---

### 第三阶段：产出一个 MVP 级别产品
本次 sprint 结束时，目标是形成一个小而完整的 prototype，至少能够展示：

- source-to-knowledge 的主链路
- approval-aware Knowledge Bank
- grounded content generation
- student-agent evaluation
- analytics/adaptation handoff
- governance / revision visibility
- demo panel / API flow 的可视化展示

最终交付重点是 **闭环完整度、模块边界清晰度、以及 demo 可解释性**。

---

## 并行任务：科研工具 - Idea2Paper
**学习和诊断 Idea2Paper 项目**。

这部分的重点是：

- 理解 Idea2Paper 的 paper-level design
- 梳理它的 code-level workflow
- 实际跑一次 demo / trial
- 分析它现在能做什么、不能做什么
- 总结最值得继续 upgrade 的方向

预计节奏大致为：

1. 阅读相关 paper 和项目说明  
2. 梳理 repo 结构与主流程  
3. 跑通一次 demo  
4. 记录优点、缺点和 failure points  
5. 形成一份可用于组内/导师汇报的结论

这条任务线更偏向 **understanding + testing + diagnosis + upgrade suggestion** 硬性规定的代码层面开发较少。

---

## 本次 Hackathon 希望得到的最终产出导向

本次 hackathon 最终会形成两类核心结果：

### A. Education System Upgrade
产出一个 **demoable MVP prototype**，证明主链路成立。

### B. Idea2Paper
产出一份 **结构化分析与升级建议总结**，帮助判断它是否值得作为未来 research accelerator / upgrade base。


---

## Repo 阅读顺序
1. hackathon/Agent教育工具/basic info
2. hackathon/Agent教育工具/开发/exec_plan.docx
3. module开发案
4. hackathon/Agent科研工具：项目介绍&任务
---

## 总结
明天的 hackathon 会先介绍 **Education System Upgrade** 的 workflow design、系统结构与 MVP 边界，然后立即进入具体开发，目标是在产出一个可演示的 MVP 级别产品；与此同时，也会并行推进 **Idea2Paper** 的学习、试用、评估与 upgrade direction analysis。
