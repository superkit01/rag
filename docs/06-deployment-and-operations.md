# 部署与运维说明

## 1. 本地开发模式

### 后端

推荐使用 `conda base` 创建 `backend/.venv`。

```bash
cd backend
conda run -n base python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

### 前端

```bash
cd web
pnpm install
pnpm dev
```

### 宿主机运行 API / Worker / Web，容器运行中间件

推荐在需要频繁改动 Python 或 Next.js 代码时使用这种模式：中间件仍然走 Docker，`api`、`worker`、`web` 直接跑在宿主机，重载更快。

先启动中间件：

```bash
docker compose up -d postgres redis opensearch minio temporal temporal-ui
```

宿主机启动 API：

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

宿主机启动 Worker：

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

宿主机启动 Web：

```bash
cd web
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api \
pnpm dev
```

说明：

- 这种模式下，本地文件上传会把原始文件持久化到 MinIO，因此 `OBJECT_STORAGE_BACKEND` 需要设置为 `minio`。
- `SEARCH_BACKEND` 当前兼容 `memory` 和 `opensearch`：
  - `memory`：不依赖 OpenSearch，适合快速本地开发
  - `opensearch`：连接 `localhost:9200`，更接近正式部署
- 如果你已经把这些变量写进仓库根目录 `.env`，可以先执行 `set -a && source .env && set +a`，再运行上面的命令。
- 浏览器侧访问地址：
  - Web：`http://localhost:3000`
  - API Docs：`http://localhost:8000/docs`
  - Temporal UI：`http://localhost:8088`

## 2. Docker Compose 栈

当前 `docker-compose.yml` 启动以下服务：

- `postgres`
- `redis`
- `opensearch`
- `minio`
- `temporal`
- `temporal-ui`

职责划分：

- `temporal`：任务编排
- `opensearch`：混合检索候选召回
- `postgres`：主数据和评测数据
- `minio`：对象存储模拟
- `redis`：预留缓存与限流

## 3. 环境变量

### 数据与基础设施

- `DATABASE_URL`
- `REDIS_URL`
- `OPENSEARCH_URL`
- `OPENSEARCH_INDEX`
- `OBJECT_STORAGE_BACKEND`
- `OBJECT_STORAGE_ENDPOINT`
- `OBJECT_STORAGE_BUCKET`
- `OBJECT_STORAGE_LOCAL_ROOT`

### 工作流

- `WORKFLOW_BACKEND`
- `TEMPORAL_HOST`
- `TEMPORAL_NAMESPACE`
- `TEMPORAL_TASK_QUEUE`
- `TEMPORAL_CONNECT_RETRIES`
- `TEMPORAL_CONNECT_DELAY_SECONDS`

### 模型

- `EMBEDDING_BACKEND`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`
- `OPENAI_EMBEDDING_MODEL`

### 检索/切块

- `RETRIEVAL_TOP_K`
- `RERANK_TOP_K`
- `CHUNK_SIZE`
- `CHUNK_OVERLAP`
- `EMBEDDING_DIMENSIONS`

## 4. 当前默认行为

### 直接本地跑后端

- 更适合轻量开发
- 通常走 SQLite 和内存检索
- embedding 默认使用 `hash`

### 宿主机跑应用，容器跑中间件

- 适合需要热更新的联调开发
- API / worker 会连接 `localhost` 上映射出来的 PostgreSQL、OpenSearch、MinIO、Temporal
- `SEARCH_BACKEND` 支持 `memory` 和 `opensearch` 两档，按环境显式切换
- 要启用原始上传文件持久化，需要设置 `OBJECT_STORAGE_BACKEND=minio`

### Docker 环境

- Compose 默认只启动 PostgreSQL + OpenSearch + MinIO + Temporal 等中间件
- `api`、`worker`、`web` 建议在宿主机运行做本地联调
- `backend` 与 `web` 的 Dockerfile 仍保留，便于后续生产部署继续走镜像方式

如果要启用真实 embedding，可在 `.env` 中增加：

```bash
EMBEDDING_BACKEND=openai
OPENAI_API_KEY=your-key
OPENAI_EMBEDDING_MODEL=your-embedding-model
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
```

## 5. 国内网络适配

当前项目已经做了两层国内环境适配：

- Web 端 `pnpm` 安装走 `npmmirror`
- Docker 基础镜像尽量使用 `docker.m.daocloud.io` 前缀

## 6. 当前运维约束

- 生产级观测还未补齐
- Redis 目前主要是占位，尚未完整接入缓存与限流逻辑
- 镜像中默认未安装 `pytest` 等 dev 依赖
- 当前更偏 MVP/演示环境，而不是正式生产发布形态

## 7. 建议的下一步运维增强

- 增加 `dev/test` Docker target
- 将 `pytest` 与 smoke test 纳入 CI
- 增加 health/readiness 区分
- 引入 OpenTelemetry
- 增加 OpenSearch、Temporal、Postgres 的关键监控项
- 增加备份与恢复脚本
