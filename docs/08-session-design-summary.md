# 本次会话设计要点纪要

## 1. 会话内达成的关键结论

### 技术栈固定

- 后端：FastAPI
- 前端：Next.js
- 编排：Temporal
- 元数据：PostgreSQL
- 检索：OpenSearch
- 对象存储：MinIO / S3 兼容
- 缓存与限流预留：Redis

### 交付范围明确

- 首期做企业内部专家研究台
- 重点是带引用问答
- 不做自治 Agent
- 不做细粒度 ACL
- 但为 ACL、连接器、SSO 预留数据扩展位

## 2. 本次会话中新增或修正的实现点

### 前端

- 切换到 `pnpm`
- 配置国内淘宝镜像源
- 控制台支持异步任务轮询
- 控制台支持任务重试/取消
- 暴露 `workflow_id`、`attempt_count`、错误信息
- 单页控制台拆成 `namespace / dashboard / documents / chat / tasks / evaluation / history`
- `chat` 页面支持流式输出
- 文档记录和任务记录支持详情页
- `web` 端上传入口收紧为本地文件上传

### 后端

- 用真实 Temporal 替换 stub
- 导入、重建索引、评测改为异步 job
- 新增任务查询、重试、取消接口
- 导入任务支持前端弹窗文件上传 payload
- OpenSearch 检索从占位实现升级到真实适配器
- embedding provider 支持 `hash` 与真实 OpenAI-compatible embeddings 切换

### 基础设施

- Docker Compose 接入 `worker`
- PostgreSQL、OpenSearch、MinIO、Temporal 联调打通
- 镜像源与 npm 源做国内网络适配

## 3. 本次会话里修掉的关键一致性问题

问题：

- 导入任务过早标记为 `completed`
- 用户立刻发起问答时，索引尚未可查
- 结果会返回“证据不足”

修复后的规则：

- 任务只有在 chunk 已写入检索索引并且可以被查询后，才标记为 `completed`

这是一条很重要的产品语义约束，因为它直接决定了：

- 状态是否可信
- 前端是否能安全自动刷新
- 用户是否会把系统误判为“不稳定”

## 4. 建议把这些文档作为后续开发基线

- 架构看 [`01-architecture-overview.md`](./01-architecture-overview.md)
- 接口看 [`02-data-model-and-api.md`](./02-data-model-and-api.md)
- 检索与问答看 [`03-ingestion-retrieval-and-answering.md`](./03-ingestion-retrieval-and-answering.md)
- 任务治理看 [`04-temporal-async-jobs.md`](./04-temporal-async-jobs.md)
- 前端能力看 [`05-frontend-console.md`](./05-frontend-console.md)
- 运维与部署看 [`06-deployment-and-operations.md`](./06-deployment-and-operations.md)
- 路线图看 [`07-roadmap-and-acceptance.md`](./07-roadmap-and-acceptance.md)
