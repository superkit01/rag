# Temporal 异步任务设计

## 1. 为什么要引入 Temporal

RAG 系统里的导入、重建索引和评测都不是轻量请求：

- 导入包含读取、解析、切块、数据库写入、检索建索引。
- 评测包含多案例问答和指标汇总。
- 重建索引需要删除旧索引再建立新索引。

因此这些过程不适合一直绑在 API 请求线程内执行。

## 2. 当前工作流类型

定义在 `backend/app/workflows/definitions.py`：

- `ImportWorkflow`
- `ReindexWorkflow`
- `EvalWorkflow`

每个工作流都遵循同一模式：

- 执行主 activity
- 捕获取消异常
- 标记取消状态
- 捕获普通异常
- 标记失败状态

## 3. 工作流与活动分工

### Orchestrator

负责：

- 建立 Temporal client
- 启动工作流
- 取消工作流
- 在 `temporal` 和 `immediate` 两种模式间切换

### Worker

负责：

- 注册 workflow
- 注册 activity
- 长轮询 Temporal task queue

### Executor

负责：

- 在 activity 中复用服务层
- 为工作流运行期创建独立 container 和 session factory

## 4. 当前任务覆盖范围

### 导入

- `POST /api/sources/import`

### 重建索引

- `POST /api/documents/{id}/reindex`

### 评测

- `POST /api/eval/runs`

## 5. 任务 ID 和工作流 ID

当前任务在业务库中保存 `workflow_id`，用于：

- 轮询状态
- 取消任务
- 重试时生成新的 workflow 实例

命名规则：

- 导入：`ingestion-<job_id>-attempt-<n>`
- 重建索引：`reindex-<job_id>-attempt-<n>`
- 评测：`eval-<run_id>-attempt-<n>`

## 6. 状态流转

### 正常完成

`pending -> running -> completed`

### 失败

`pending/running -> failed`

### 取消

`pending/running -> cancelling -> cancelled`

## 7. 重试语义

允许重试的状态：

- `failed`
- `cancelled`

重试会执行：

- `attempt_count + 1`
- 生成新的 `workflow_id`
- 清空 `error_message`
- 将状态恢复为 `pending`

对于重建索引任务，还会重新把文档状态切回 `reindexing`。

## 8. 取消语义

前端调用取消接口后：

1. 业务状态先置为 `cancelling`
2. 再向 Temporal 发出 cancel 请求
3. workflow 捕获 `CancelledError`
4. activity 将任务最终置为 `cancelled`

这保证了：

- UI 能立刻反馈“已请求取消”
- 工作流层仍有机会做收尾和状态修正

## 9. Immediate 模式的作用

`WORKFLOW_BACKEND=immediate` 时：

- 不依赖 Temporal
- 直接在线程里执行服务层逻辑
- 更适合单测和极简本地开发

它保留了和 Temporal 模式接近的接口面，因此业务层不需要分叉实现。

## 10. 本次会话新增的任务治理能力

- 任务状态轮询
- 导入任务重试
- 导入任务取消
- 评测任务重试
- 评测任务取消
- `attempt_count` 展示
- `workflow_id` 暴露给前端
- 失败原因持久化

## 11. 后续建议

- 增加任务筛选和归档
- 增加批量取消/批量重试
- 增加任务超时和告警
- 增加 worker 并发度配置
- 增加 OpenTelemetry trace 与 job 关联
