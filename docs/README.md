# Documentation Index

本目录收敛了本次会话设计与实现过程中沉淀下来的详细文档，建议按下面顺序阅读。

## 建议阅读顺序

1. [`01-architecture-overview.md`](./01-architecture-overview.md)
2. [`02-data-model-and-api.md`](./02-data-model-and-api.md)
3. [`03-ingestion-retrieval-and-answering.md`](./03-ingestion-retrieval-and-answering.md)
4. [`04-temporal-async-jobs.md`](./04-temporal-async-jobs.md)
5. [`05-frontend-console.md`](./05-frontend-console.md)
6. [`06-deployment-and-operations.md`](./06-deployment-and-operations.md)
7. [`07-roadmap-and-acceptance.md`](./07-roadmap-and-acceptance.md)
8. [`08-session-design-summary.md`](./08-session-design-summary.md)
9. [`09-data-flow.md`](./09-data-flow.md)
10. [`10-openai-model-call-stages.md`](./10-openai-model-call-stages.md)
11. [`11-document-versioning-and-expiration.md`](./11-document-versioning-and-expiration.md)
12. [`12-connector-framework.md`](./12-connector-framework.md)
13. [`13-rag-development-timeline.md`](./13-rag-development-timeline.md)
14. [`14-graphrag-and-agentic-rag.md`](./14-graphrag-and-agentic-rag.md)

## 文档说明

- `01`：系统边界、核心组件、运行模式、非目标。
- `02`：实体模型、关键状态机、API 合同。
- `03`：文档解析、切块、混合检索、保守回答。
- `04`：Temporal 工作流、重试/取消、任务治理。
- `05`：前端控制台功能区、轮询机制、交互约束。
- `06`：本地开发、Docker、环境变量、运维建议。
- `07`：阶段性路线图、验收指标、下一步待办。
- `08`：本次会话已经达成的设计决策摘要。
- `09`：端到端数据流、导入、索引、问答、评测链路。
- `10`：OpenAI-compatible embedding/chat 模型调用阶段、触发条件和配置项。
- `11`：文档增量更新、版本切换、索引一致性和过期失效设计。
- `12`：连接器体系、数据源同步、变化检测、ImportedSource 合同和落地路径。
- `13`：RAG 发展时间线、架构演进、重难点问题和企业级 RAG 启发。
- `14`：GraphRAG 与 Agentic RAG 的概念、架构实现、最佳实践和本项目落地路线。
