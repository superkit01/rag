# 数据模型与 API 设计

## 1. 核心实体

### KnowledgeSpace

知识空间是逻辑隔离单元，用于承载一组文档、问答轨迹和评测结果。

关键字段：

- `id`
- `name`
- `description`
- `language`

### IngestionJob

导入与重建索引统一走任务模型。

关键字段：

- `job_kind`：`import` 或 `reindex`
- `source_uri`
- `workflow_id`
- `status`
- `request_payload`
- `attempt_count`
- `error_message`
- `imported_document_id`

状态集合：

- `pending`
- `running`
- `cancelling`
- `completed`
- `failed`
- `cancelled`

### Document

文档是知识库中的标准归档单元。

关键字段：

- `title`
- `source_type`
- `source_uri`
- `storage_uri`
- `visibility_scope`
- `source_acl_refs`
- `connector_id`
- `ingestion_job_id`
- `status`
- `checksum`
- `source_metadata`

状态集合：

- `indexing`
- `reindexing`
- `ready`
- `error`

### Chunk

检索和引用的最小业务单元。

关键字段：

- `fragment_id`
- `section_title`
- `heading_path`
- `page_number`
- `start_offset`
- `end_offset`
- `token_count`
- `content`
- `embedding`

### AnswerTrace

记录一次完整问答的业务快照。

关键字段：

- `question`
- `answer`
- `confidence`
- `citations`
- `source_documents`
- `followup_queries`
- `evidence_snapshot`

### EvalRun

离线评测运行记录。

关键字段：

- `workflow_id`
- `status`
- `request_payload`
- `attempt_count`
- `error_message`
- `total_cases`
- `completed_cases`
- `summary`
- `completed_at`

## 2. 预留扩展位

以下字段已经按企业化目标预留：

- `Document.visibility_scope`
- `Document.source_acl_refs`
- `Document.connector_id`
- `Document.ingestion_job_id`
- `IngestionJob.request_payload`
- `EvalRun.request_payload`

这使得 Phase 2 以后接 SSO、ACL、连接器时不用重做主数据结构。

## 3. 关键 API

### 知识空间

- `GET /api/knowledge-spaces`
- `POST /api/knowledge-spaces`

### 导入与任务

- `POST /api/sources/import`
- `POST /api/sources/import/batch`
- `GET /api/sources/jobs`
- `GET /api/sources/jobs/{job_id}`
- `POST /api/sources/jobs/{job_id}/retry`
- `POST /api/sources/jobs/{job_id}/cancel`

### 文档

- `GET /api/documents`
- `GET /api/documents/{id}`
- `GET /api/documents/{id}/fragments/{fragment_id}`
- `POST /api/documents/{id}/reindex`

### 问答与反馈

- `POST /api/queries/answer`
- `GET /api/answer-traces`
- `POST /api/feedback`

### 评测

- `POST /api/eval/runs`
- `GET /api/eval/runs`
- `GET /api/eval/runs/{id}`
- `POST /api/eval/runs/{id}/retry`
- `POST /api/eval/runs/{id}/cancel`

### 控制台汇总

- `GET /api/dashboard/summary`
- `GET /api/health`

## 4. API 设计约束

- 导入和评测接口默认返回 `202 Accepted`，因为它们是异步 job。
- 任务详情接口返回的是“当前状态快照”，前端负责轮询。
- 重试只允许对 `failed` 或 `cancelled` 的任务执行。
- 取消只允许对 `pending` 或 `running` 的任务执行。
- 问答接口不暴露模型内部细节，只返回业务可消费结构：
  - `answer`
  - `citations`
  - `confidence`
  - `source_documents`
  - `followup_queries`

## 5. 当前状态机语义

### 导入任务

`pending -> running -> completed`

失败路径：

`pending/running -> failed`

取消路径：

`pending/running -> cancelling -> cancelled`

注意：

- `completed` 的语义不是“数据库写完了”，而是“数据库和索引都准备好了”。
- 这是本次会话中特意修过的一条一致性规则。

### 评测任务

`pending -> running -> completed`

失败与取消路径与导入任务一致。
