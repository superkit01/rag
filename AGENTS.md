# Agent Guide

本文件面向在此仓库内继续协作的 AI 代理与开发者，目标是让后续工作在不重新摸索上下文的前提下继续推进。

## 1. 项目目标

本项目是一个企业级 RAG 知识库平台的 Phase 0/1 实现，核心目标是：

- 面向企业内部专家用户提供“带引用的研究问答”。
- 支持文档导入、切块、混合检索、答案引用回链、反馈采集、离线评测。
- 使用 `FastAPI + Next.js + Temporal + PostgreSQL + OpenSearch + MinIO + Redis` 作为目标技术栈。
- 首期不做细粒度 ACL，但数据模型必须预留后续权限和连接器扩展点。

## 2. 目录速览

- `backend/`：后端 API、服务层、数据模型、工作流、测试。
- `web/`：前端控制台，使用 `Next.js 15 + React 19 + pnpm`。
- `infra/postgres/init/`：数据库初始化脚本。
- `docker-compose.yml`：本地一键联调环境。
- `docs/`：本次会话整理出来的详细设计文档。

## 3. 当前关键设计决策

- 文档导入只支持前端弹窗选择文件上传，后端接收 `uploaded_file_name` 和 `uploaded_file_base64`。
- 二进制文档解析走 `Docling` 可选依赖，未安装时给出明确错误。
- 检索采用混合策略：
  - 词法召回：基于 OpenSearch token/term 字段。
  - 语义召回：本地 hash embedding rerank。
- 问答必须返回引用；证据不足时走保守回答，不输出无依据结论。
- 导入、重建索引、评测统一走异步任务模型。
- Docker/标准开发环境使用真实 Temporal；轻量测试可退回 `WORKFLOW_BACKEND=immediate`。
- `completed` 的导入/重建索引任务表示：
  - 数据库写入完成；
  - 检索索引已可查询；
  - 前端可以立刻发起问答而不会出现“状态完成但无引用”的空窗。

## 4. 常用命令

后端本地开发：

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

启动 Temporal worker：

```bash
cd backend
.venv/bin/python -m app.workflows.worker
```

前端开发：

```bash
cd web
pnpm dev
```

Docker 联调：

```bash
docker compose up --build
```

宿主机运行 `api` / `worker` / `web`，容器运行中间件：

```bash
docker compose up -d postgres redis opensearch minio temporal temporal-ui
```

```bash
cd backend
export SEARCH_BACKEND=${SEARCH_BACKEND:-memory}   # 可选: memory | opensearch
DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5432/rag \
WORKFLOW_BACKEND=temporal \
SEARCH_BACKEND=$SEARCH_BACKEND \
OPENSEARCH_URL=http://localhost:9200 \
OBJECT_STORAGE_BACKEND=minio \
OBJECT_STORAGE_ENDPOINT=http://localhost:9000 \
OBJECT_STORAGE_BUCKET=rag-documents \
OBJECT_STORAGE_ACCESS_KEY=minioadmin \
OBJECT_STORAGE_SECRET_KEY=minioadmin \
TEMPORAL_HOST=localhost:7233 \
TEMPORAL_NAMESPACE=default \
TEMPORAL_TASK_QUEUE=rag-jobs \
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

```bash
cd backend
export SEARCH_BACKEND=${SEARCH_BACKEND:-memory}   # 可选: memory | opensearch
DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5432/rag \
WORKFLOW_BACKEND=temporal \
SEARCH_BACKEND=$SEARCH_BACKEND \
OPENSEARCH_URL=http://localhost:9200 \
OBJECT_STORAGE_BACKEND=minio \
OBJECT_STORAGE_ENDPOINT=http://localhost:9000 \
OBJECT_STORAGE_BUCKET=rag-documents \
OBJECT_STORAGE_ACCESS_KEY=minioadmin \
OBJECT_STORAGE_SECRET_KEY=minioadmin \
TEMPORAL_HOST=localhost:7233 \
TEMPORAL_NAMESPACE=default \
TEMPORAL_TASK_QUEUE=rag-jobs \
.venv/bin/python -m app.workflows.worker
```

```bash
cd web
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api \
pnpm dev
```

前端生产构建：

```bash
cd web
pnpm build
```

## 5. 运行时约束

- 后端虚拟环境放在 `backend/.venv`。
- 前端统一使用 `pnpm`，不要切回 `npm`。
- `web/.npmrc` 已固定为国内镜像源 `https://registry.npmmirror.com/`。
- Docker Compose 中 API 和 worker 默认使用：
  - `WORKFLOW_BACKEND=temporal`
- `SEARCH_BACKEND` 当前兼容：
  - `memory`
  - `opensearch`
- 宿主机跑 `api` / `worker` 时，如果要让浏览器上传的原始文件落到 MinIO，必须显式设置：
  - `OBJECT_STORAGE_BACKEND=minio`
  - `OBJECT_STORAGE_ENDPOINT=http://localhost:9000`
- 本地直接跑后端时，若未额外配置，通常会退回轻量的 `memory` 检索。

## 6. 建议优先阅读的文档

1. [`docs/01-architecture-overview.md`](./docs/01-architecture-overview.md)
2. [`docs/03-ingestion-retrieval-and-answering.md`](./docs/03-ingestion-retrieval-and-answering.md)
3. [`docs/04-temporal-async-jobs.md`](./docs/04-temporal-async-jobs.md)
4. [`docs/06-deployment-and-operations.md`](./docs/06-deployment-and-operations.md)
5. [`docs/07-roadmap-and-acceptance.md`](./docs/07-roadmap-and-acceptance.md)

## 7. 后续工作优先级建议

- 补正式的任务历史筛选、失败原因聚合、批量重试。
- 为 Docker 镜像增加 `dev/test` target，支持容器内直接跑 `pytest`。
- 接入真实 OpenAI-compatible embeddings 与 chat model。
- 引入连接器框架、审计日志、观测指标和成本看板。
- 在评测体系里增加黄金集、近义问法和跨文档综合场景。
