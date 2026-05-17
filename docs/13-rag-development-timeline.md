# RAG Development Timeline

本文件按时间线梳理 Retrieval-Augmented Generation, RAG 的发展脉络，重点关注架构演进、代表性技术、核心难点和对企业级知识库系统的启发。资料基于 2026-05-17 的联网查询整理。

## 一句话脉络

RAG 的演进不是从一个固定架构走向另一个固定架构，而是从“检索增强问答”逐步发展为“可编排、可评测、可审计的知识系统”：先解决模型不知道的问题，再解决检索不准、证据不稳、多跳综合、权限安全和工程治理问题。

## Timeline

| 时间 | 阶段 | 代表技术/论文 | 架构形态 | 主要解决的问题 | 新暴露的问题 |
| --- | --- | --- | --- | --- | --- |
| 2010s-2020 | 检索式问答前史 | BM25、TF-IDF、Open-domain QA Reader | 稀疏检索 + 阅读器/抽取器 | 从大规模语料中找到相关文档，再抽取答案 | 词面匹配依赖强，语义召回弱，生成能力有限 |
| 2020 | 神经检索兴起 | DPR、REALM | Dense retriever + reader / LM pre-training | 用向量语义检索替代纯关键词匹配，提高开放域问答召回 | 训练和索引成本上升，检索器与生成器协同仍复杂 |
| 2020 | RAG 正式提出 | RAG by Lewis et al. | Retriever + seq2seq generator | 把外部文档作为非参数记忆，减少只依赖模型参数的知识瓶颈 | 检索结果质量直接决定生成质量，引用和忠实度仍需额外约束 |
| 2020-2022 | 检索增强生成探索 | FiD、RETRO、Atlas | 多文档检索 + 融合生成 | 让生成模型同时利用多个 passage，提升开放域 QA 和 few-shot 表现 | 多文档上下文噪声增加，排序、融合和成本问题突出 |
| 2022-2023 | LLM Naive RAG 工程化 | Embedding API、Vector DB、LangChain/LlamaIndex 生态 | 文档切块 + embedding + 向量库 + prompt 拼接 | 让企业/个人知识库快速接入 LLM 问答 | Chunk 策略粗糙，top-k 语义相似不等于证据相关，幻觉和错引常见 |
| 2023-2024 | Advanced RAG | Hybrid search、reranker、query rewrite、HyDE、context compression | 多路召回 + 重排 + 压缩 + 受控生成 | 提升召回率、相关性、上下文利用率和引用质量 | 链路变长，延迟、成本、可观测性和调参复杂度提升 |
| 2023 | Self-reflective RAG | Self-RAG | 检索决策 + 生成 + 自我批判/验证 | 让模型判断何时检索、如何使用证据、答案是否需要修正 | 反思链路依赖模型能力，线上稳定性和评测难度增加 |
| 2024 | Corrective RAG | CRAG | 检索质量评估 + 纠错/补充检索 | 在检索结果不可靠时触发纠偏，降低错误证据带来的错误回答 | 需要可靠的检索质量判断器，也会增加调用次数和响应时间 |
| 2024 | Modular RAG | RAG survey 中的 Naive/Advanced/Modular 分类 | 查询分析、路由、检索、重排、压缩、验证、生成可插拔编排 | 把 RAG 从单链路升级为可组合系统 | 系统边界更复杂，需要模块级评测、日志和失败归因 |
| 2024-2025 | GraphRAG | Microsoft GraphRAG | 文档 -> 实体/关系/社区 -> 图检索/全局摘要 | 改善跨文档、多跳关系、全局主题综合能力 | 图构建成本高，实体消歧、增量更新和答案溯源更难 |
| 2024-2026 | Agentic RAG | Tool use、workflow agents、enterprise connectors | LLM planner + 多工具/多数据源检索 + 验证闭环 | 面向复杂任务自动选择数据源、检索策略和工具 | 可控性、权限、审计、循环失败、成本治理成为核心问题 |
| 2025-2026 | Enterprise RAG / RAGOps | RAG evaluation、observability、ACL、cost dashboard | RAG pipeline + 评测集 + 监控 + 审计 + 权限模型 | 把 demo 级 RAG 推向可运营的企业知识平台 | 数据治理、持续评测、模型漂移、索引一致性和合规风险长期存在 |

## 架构演进主线

### 1. Sparse Retrieval QA

早期开放域问答通常采用“检索器 + 阅读器”架构。检索器多使用 BM25、TF-IDF 等稀疏检索方法，阅读器负责从候选文档中抽取答案。这一阶段的核心优势是可解释、成本低、工程成熟；核心短板是依赖词面匹配，面对同义表达、隐含关系、跨语言问题时召回有限。

### 2. Neural Retriever

2020 年前后，DPR 和 REALM 代表了神经检索的重要跃迁。DPR 使用 dense passage retrieval，把问题和段落编码到同一向量空间；REALM 则把检索增强引入语言模型预训练，使模型在训练和推理中都能访问外部语料。

这一阶段把重点从“关键词是否匹配”推进到“语义是否相关”，但也带来了新的系统问题：向量索引维护、embedding 更新、训练数据构造、检索器与生成器之间的目标不一致。

### 3. Original RAG

Meta 在 2020 年提出的 RAG 将外部文档视为非参数记忆，与参数化的 seq2seq 模型结合。它明确了后来 RAG 系统的基本范式：

- 检索器负责从外部知识源中找证据。
- 生成器负责基于输入问题和检索证据生成答案。
- 知识更新可以通过更新外部索引完成，而不必每次重新训练模型。

RAG 的关键价值是降低模型参数记忆的压力，但它并没有天然解决“证据是否正确支持答案”的问题。

### 4. LLM Naive RAG

大模型普及后，RAG 迅速工程化为一种简单模式：文档解析、切块、embedding、向量库检索、top-k 上下文拼接、LLM 生成。这一阶段让 RAG 的使用门槛大幅降低，也推动了企业知识库、客服问答、内部文档助手等产品形态。

但 Naive RAG 的缺陷非常典型：

- Chunk 太大导致噪声多，太小导致语义断裂。
- 向量相似不等于答案相关。
- top-k 容易遗漏关键证据。
- LLM 可能无证据回答，或者引用不能真正支撑结论。
- 数据更新、权限过滤、引用回链在 demo 中常被低估。

### 5. Advanced RAG

Advanced RAG 的重点是增强检索链路和上下文质量，常见手段包括：

- Hybrid search：结合 BM25/term 检索和 dense vector 检索。
- Reranker：用 cross-encoder 或 LLM 对候选证据重新排序。
- Query rewrite：把用户问题改写为更适合检索的查询。
- Multi-query retrieval：从多个角度召回候选文档。
- Context compression：压缩、过滤或摘要检索结果，减少噪声。
- Citation grounding：要求答案与引用片段建立更严格的对应关系。

这一阶段的核心目标是“让进入上下文窗口的材料更少、更准、更可用”。

### 6. Modular RAG

Modular RAG 把 RAG 看成可编排系统，而不是固定流水线。典型模块包括：

- Query understanding：识别意图、实体、时间、约束条件。
- Router：决定查哪个知识库、连接器、索引或工具。
- Retriever：词法、向量、图、结构化数据库等多种检索。
- Reranker：对候选证据做精排。
- Compressor：压缩上下文。
- Verifier：验证证据是否支持答案。
- Generator：生成最终回答。
- Feedback/Eval：采集反馈并进行离线/在线评测。

这一阶段最重要的变化是：RAG 从“单次检索后回答”变成“带判断、路由、重试和验证的任务系统”。

### 7. GraphRAG

GraphRAG 面向传统 chunk RAG 难以处理的全局综合和多跳关系问题。它通常会从文档中抽取实体、关系和社区结构，再基于图进行局部或全局查询。

适合 GraphRAG 的问题包括：

- 跨多篇文档总结某个主题。
- 分析实体之间的关系网络。
- 追踪政策、产品、人员、项目之间的依赖。
- 回答需要多跳推理的问题。

GraphRAG 的代价也明显：图构建、实体消歧、关系抽取、增量更新、图证据回链都比普通向量 RAG 更复杂。

### 8. Agentic / Enterprise RAG

Agentic RAG 把 RAG 放进更大的任务执行系统中。系统可以根据问题自动选择工具和数据源，例如文档库、数据库、搜索引擎、工单系统、CRM、代码仓库、BI 报表等。

企业级 RAG 的重点不再只是“回答是否聪明”，而是：

- 用户是否有权限看到被检索内容。
- 答案是否有可审计的证据链。
- 索引是否和源系统保持一致。
- 失败是否可归因、可重试、可监控。
- 成本、延迟和质量是否可持续治理。

## 重难点演进

| 问题 | 早期表现 | 现阶段表现 | 企业级要求 |
| --- | --- | --- | --- |
| 知识获取 | 模型不知道事实 | 检索召回不足或召回噪声大 | 多数据源连接器、增量同步、索引一致性 |
| 文档理解 | 文本段落检索 | PDF、表格、图片、扫描件、网页混合 | 高质量解析、版面结构保留、可追溯 chunk |
| 检索相关性 | 关键词匹配失败 | embedding 相似但答案无关 | 混合检索、rerank、query rewrite、召回评测 |
| 多跳推理 | 单文档问答 | 跨文档综合、主题归纳、因果链分析 | GraphRAG、迭代检索、证据聚合 |
| 幻觉控制 | 模型编造答案 | 检索后仍可能过度推断 | 保守回答、claim verification、引用强约束 |
| 引用可信度 | 无引用或粗粒度引用 | 引用存在但不支撑结论 | 片段级引用、答案-证据对齐、回链可点击 |
| 权限安全 | 通常忽略 | 检索可能泄露不可见内容 | ACL filter、租户隔离、审计日志、脱敏 |
| 评测体系 | 只看最终答案 | 检索、生成、引用、忠实度难拆分 | 黄金集、回归评测、线上反馈、成本质量看板 |
| 工程治理 | demo pipeline | 多模块链路复杂 | 可观测性、任务队列、重试、SLA、成本控制 |

## 对本项目的启发

本项目当前的 Phase 0/1 设计已经覆盖了企业 RAG 的关键骨架：文档导入、切块、混合检索、引用回链、反馈采集、离线评测、异步任务和后续 ACL/连接器扩展点。结合 RAG 发展趋势，后续优先级可以按下面方向推进：

1. 从 Naive/Advanced RAG 继续增强检索质量：真实 embedding、hybrid search、reranker、query rewrite。
2. 强化引用可信度：让回答中的每个关键 claim 都能对应到证据 chunk。
3. 建立 RAGOps：检索召回率、答案忠实度、引用准确率、延迟、成本都要可评测。
4. 为 Enterprise RAG 做准备：连接器、权限过滤、审计日志、增量同步和索引一致性。
5. 谨慎引入 GraphRAG/Agentic RAG：优先在跨文档综合、多跳分析、复杂研究任务中试点，而不是替换所有普通问答链路。

## 参考资料

- Patrick Lewis et al., [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401), 2020.
- Vladimir Karpukhin et al., [Dense Passage Retrieval for Open-Domain Question Answering](https://arxiv.org/abs/2004.04906), 2020.
- Kelvin Guu et al., [REALM: Retrieval-Augmented Language Model Pre-Training](https://arxiv.org/abs/2002.08909), 2020.
- Gautier Izacard and Edouard Grave, [Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering](https://arxiv.org/abs/2007.01282), 2020.
- Yunfan Gao et al., [Retrieval-Augmented Generation for Large Language Models: A Survey](https://arxiv.org/abs/2312.10997), 2023.
- Akari Asai et al., [Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection](https://arxiv.org/abs/2310.11511), 2023.
- Yan et al., [Corrective Retrieval Augmented Generation](https://arxiv.org/abs/2401.15884), 2024.
- Microsoft Research, [GraphRAG](https://www.microsoft.com/en-us/research/project/graphrag/), 2024.
- Zicheng Xu et al., [Retrieval Augmented Generation Evaluation in the Era of Large Language Models](https://arxiv.org/abs/2504.14891), 2025.
