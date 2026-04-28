# Enterprise RAG Knowledge Hub

面向企业内部专家用户的 RAG 知识库骨架工程，目标是快速落地“带引用的研究问答”平台，并为后续 ACL、连接器、评测和企业化治理留出清晰扩展点。

## 架构概览

```mermaid
flowchart LR
    U["Web Console (Next.js)"] --> API["API Layer (FastAPI)"]
    API --> DB["PostgreSQL / SQLite fallback"]
    API --> IDX["Hybrid Retrieval (OpenSearch adapter / memory fallback)"]
    API --> OBJ["S3 / MinIO"]
    API --> WF["Workflow Orchestrator (Temporal-ready)"]
    API --> LLM["LLM Provider Adapter (OpenAI-compatible or heuristic fallback)"]
```

## 当前实现范围

- `backend/`：FastAPI API、SQLAlchemy 数据模型、文档导入/切块/索引/问答/评测服务。
- `web/`：Next.js 最小化运营与问答界面。
- `docker-compose.yml`：本地依赖栈，包括 PostgreSQL、Redis、OpenSearch、MinIO、Temporal。
- 轻量本地模式使用 `SQLite + in-memory search + immediate workflow + heuristic answer provider`，便于无外部依赖时跑通。
- 生产目标配置仍然围绕 `PostgreSQL + OpenSearch + MinIO + Temporal + OpenAI-compatible provider`。
- embedding provider 支持 `hash` 与 `openai` 两档，可通过 `EMBEDDING_BACKEND` 切换。

## 详细文档

- 协作指南：[`AGENTS.md`](./AGENTS.md)
- 文档索引：[`docs/README.md`](./docs/README.md)
- 架构总览：[`docs/01-architecture-overview.md`](./docs/01-architecture-overview.md)
- 数据模型与接口：[`docs/02-data-model-and-api.md`](./docs/02-data-model-and-api.md)
- 导入、检索与有引用问答：[`docs/03-ingestion-retrieval-and-answering.md`](./docs/03-ingestion-retrieval-and-answering.md)
- Temporal 异步任务：[`docs/04-temporal-async-jobs.md`](./docs/04-temporal-async-jobs.md)
- 前端控制台：[`docs/05-frontend-console.md`](./docs/05-frontend-console.md)
- 部署与运维：[`docs/06-deployment-and-operations.md`](./docs/06-deployment-and-operations.md)
- 路线图与验收：[`docs/07-roadmap-and-acceptance.md`](./docs/07-roadmap-and-acceptance.md)
- 本次会话设计纪要：[`docs/08-session-design-summary.md`](./docs/08-session-design-summary.md)

## 快速开始

1. 复制环境变量：

   ```bash
   cp .env.example .env
   ```

2. 安装后端依赖：

   ```bash
   cd backend
   conda run -n base python -m venv .venv
   source .venv/bin/activate
   pip install -e '.[dev]'
   ```

3. 运行轻量后端：

   ```bash
   WORKFLOW_BACKEND=immediate \
   SEARCH_BACKEND=memory \
   .venv/bin/python -m uvicorn app.main:app --reload --port 8000
   ```

4. 如果切到 `WORKFLOW_BACKEND=temporal`，另开终端运行 Temporal worker：

   ```bash
   cd backend
   .venv/bin/python -m app.workflows.worker
   ```

5. 运行前端：

   ```bash
   cd web
   pnpm install
   pnpm dev
   ```

6. 打开：

   - API Docs: `http://localhost:8000/docs`
   - Web Console: `http://localhost:3000`

## Docker Compose

```bash
docker compose up -d postgres redis opensearch minio temporal temporal-ui
```

- `infra/postgres/init/01-create-temporal-db.sql` 会在首次初始化 PostgreSQL 数据卷时创建 `temporal` 数据库。
- 当前 Dockerfile 和 Compose 已默认改用国内更友好的镜像前缀，减少 Docker Hub 拉取失败的问题。
- 当前 Compose 只负责中间件：`postgres`、`redis`、`opensearch`、`minio`、`temporal`、`temporal-ui`。
- `api`、`worker`、`web` 默认建议直接在宿主机运行；`backend` 和 `web` 的 Dockerfile 继续保留，方便后续生产部署。

## 宿主机运行 API / Worker / Web，容器运行中间件

如果你希望只把 PostgreSQL、Redis、OpenSearch、MinIO、Temporal 放在容器里，而把 `api`、`worker`、`web` 直接跑在宿主机，可以使用下面这套命令。

1. 先启动中间件容器：

   ```bash
   docker compose up -d postgres redis opensearch minio temporal temporal-ui
   ```

2. 在宿主机启动 API：

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

3. 在另一个终端启动 Worker：

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

4. 在第三个终端启动 Web：

   ```bash
   cd web
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api \
   pnpm dev
   ```

补充说明：

- 这种模式下，浏览器上传的原始文件会持久化到 MinIO，所以宿主机运行 `api` 和 `worker` 时要显式设置 `OBJECT_STORAGE_BACKEND=minio`。
- `SEARCH_BACKEND` 现在兼容 `memory` 和 `opensearch`：
  - `SEARCH_BACKEND=memory`：不依赖 OpenSearch，适合轻量开发
  - `SEARCH_BACKEND=opensearch`：连接 `http://localhost:9200`，更接近正式环境
- 如果 `.env` 已经写好了这些变量，也可以先执行 `set -a && source .env && set +a`，再运行上面的命令。
- 常用访问地址：
  - API Docs: `http://localhost:8000/docs`
  - Web Console: `http://localhost:3000`
  - Temporal UI: `http://localhost:8088`

## 关键接口

- `POST /api/sources/import`
- `GET /api/sources/jobs`
- `GET /api/sources/jobs/{job_id}`
- `POST /api/documents/{id}/reindex`
- `POST /api/queries/answer`
- `GET /api/documents/{id}`
- `GET /api/documents/{id}/fragments/{fragment_id}`
- `POST /api/feedback`
- `POST /api/eval/runs`
- `GET /api/eval/runs`
- `GET /api/eval/runs/{id}`

补充实现：

- `GET/POST /api/knowledge-spaces`
- `GET /api/documents`
- `GET /api/answer-traces`
- `GET /api/dashboard/summary`

`POST /api/sources/import` 当前只支持前端弹窗选择文件上传：

- `uploaded_file_name`
- `uploaded_file_base64`

## 设计说明

- 数据模型预留了 `visibility_scope`, `source_acl_refs`, `connector_id`, `ingestion_job_id`。
- 导入链路优先支持 `Markdown/HTML/Text`，`PDF/DOCX/PPTX` 通过 `Docling` 适配器接入；如果本地未安装 `docling`，会给出明确提示。
- Web 控制台内置了单文档文件导入、问答反馈和单案例评测入口，适合做内部演示与验收。
- 检索采用“词法 + embedding rerank”混合检索，embedding provider 既支持本地 `hash`，也支持真实 OpenAI-compatible embeddings。
- `SEARCH_BACKEND` 当前显式支持 `memory` 和 `opensearch` 两档；本机直接运行后端时默认仍使用 `memory`，需要时可切到 `opensearch`。
- 单元测试默认使用 `WORKFLOW_BACKEND=immediate` 保持轻量回归，而标准开发和 Docker 环境默认使用真实 Temporal 工作流调度。
- 回答默认使用保守的启发式 grounded answerer；配置 `OPENAI_API_KEY` 后可切换到 OpenAI-compatible provider。
- 当 `EMBEDDING_BACKEND=openai` 时，需要同时配置 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_EMBEDDING_MODEL`。
- 从 `hash` 切换到真实 embeddings 后，建议对历史文档执行一次重建索引，否则旧 chunk 向量与新查询向量可能不一致。
