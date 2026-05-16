# OpenAI-compatible 模型调用阶段

本文说明当前项目在哪些阶段会调用 OpenAI-compatible 模型接口，以及每个阶段对应的触发条件、接口类型和配置项。

## 1. 总览

项目里目前有两类 OpenAI-compatible 调用：

- Embedding 调用：`POST /embeddings`
- Chat 调用：`POST /chat/completions`

统一提供商配置：

```bash
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=...
```

模型配置分三类：

- `OPENAI_EMBEDDING_MODEL`：最终 chunk 向量、query 向量、检索/rerank 使用。
- `SEMANTIC_EMBEDDING_MODEL`：仅用于 semantic 切片阶段的语义边界判断。
- `OPENAI_CHAT_MODEL`：用于 query rewrite、答案生成、会话标题生成。

## 2. Embedding 调用阶段

### 2.1 Semantic 切片边界判断

触发条件：

```bash
CHUNKING_STRATEGY=semantic
EMBEDDING_BACKEND=openai
```

接口：

```text
POST {OPENAI_BASE_URL}/embeddings
```

模型配置：

```bash
SEMANTIC_EMBEDDING_MODEL=...
```

调用时机：

- 文档导入。
- 文档重建索引。

用途：

- 将 semantic sliding windows 转成 embedding。
- 计算相邻 window 的 cosine similarity。
- 当 similarity 低于 `SEMANTIC_SIMILARITY_THRESHOLD` 时，作为候选切割边界。

注意：

- 这一步的 embedding 不落库。
- 这一步只服务切片决策。
- 如果 `EMBEDDING_BACKEND=hash`，则使用本地 hash embedding，不调用 OpenAI-compatible 接口，也不需要 `SEMANTIC_EMBEDDING_MODEL`。

### 2.2 最终 chunk embedding 入库和入索引

触发条件：

```bash
EMBEDDING_BACKEND=openai
```

接口：

```text
POST {OPENAI_BASE_URL}/embeddings
```

模型配置：

```bash
OPENAI_EMBEDDING_MODEL=...
```

调用时机：

- 文档导入。
- 文档重建索引。

用途：

- 为最终可检索 chunk 生成 embedding。
- 写入 PostgreSQL 的 `chunks.embedding`。
- 同一份 embedding 会写入当前检索索引：
  - `memory`
  - `opensearch`
  - `milvus`
  - `hybrid`

不同切片策略下的行为：

- `fixed-size`：所有 `fixed` chunk 都会生成 embedding。
- `semantic`：最终输出的 `fixed` chunk 都会生成 embedding。
- `parent-child`：只给 `child` chunk 生成 embedding；`parent` chunk 会落库，但 embedding 为空，也不写入搜索索引。

### 2.3 用户问题 query embedding

触发条件：

```bash
EMBEDDING_BACKEND=openai
```

接口：

```text
POST {OPENAI_BASE_URL}/embeddings
```

模型配置：

```bash
OPENAI_EMBEDDING_MODEL=...
```

调用时机：

- 用户发起问答。
- 评测用例执行问答链路。

用途：

- 将用户问题或改写后的检索 query 转成 embedding。
- 用于向量召回或候选结果语义打分。

不同检索后端下的行为：

- `memory`：query embedding 与内存 chunk embedding 计算相似度。
- `opensearch`：OpenSearch 先做词法候选召回，应用层再用 query embedding 与候选 chunk embedding 做语义打分。
- `milvus`：query embedding 送入 Milvus 做向量召回。
- `hybrid`：OpenSearch 做词法召回，Milvus 做向量召回，应用层融合结果。

## 3. Chat 调用阶段

Chat provider 启用条件：

```bash
OPENAI_API_KEY=...
OPENAI_CHAT_MODEL=...
```

接口：

```text
POST {OPENAI_BASE_URL}/chat/completions
```

模型配置：

```bash
OPENAI_CHAT_MODEL=...
```

如果未配置 `OPENAI_API_KEY` 或 `OPENAI_CHAT_MODEL`，系统会使用本地 `HeuristicAnswerProvider`，不会调用 chat 模型。

### 3.1 多轮 query rewrite

触发条件：

- Chat provider 已启用。
- 当前问答请求带有 `session_id`。
- 该 session 已有历史问答记录。

用途：

- 将多轮追问改写成更适合检索的独立 query。
- 改写结果用于后续检索，不直接作为最终答案。

如果没有历史对话，系统直接使用用户原始问题，不调用 query rewrite。

### 3.2 答案生成

触发条件：

- Chat provider 已启用。
- 检索后证据充足，即 `insufficient_evidence=False`。

用途：

- 基于当前检索证据生成 grounded answer。
- 普通回答和流式回答都会走这一阶段。

注意：

- 如果没有召回结果，或 confidence 低于阈值，系统直接返回保守回答，不调用 chat 模型生成答案。
- 模型提示要求只能依据本轮证据回答，不能编造。

### 3.3 会话标题生成

触发条件：

- Chat provider 已启用。
- 当前 session 是首轮问答完成后。
- 当前标题仍是空标题、新对话、新会话或临时问题标题。

用途：

- 基于首轮问题和答案摘要生成短中文标题。

注意：

- 用户自定义过的 session 标题不会被覆盖。
- 如果模型调用失败，会 fallback 到本地临时标题逻辑。

## 4. 评测任务中的模型调用

评测服务本身没有单独模型调用器，但它会复用问答链路。

因此每条 eval case 可能间接触发：

- query embedding
- 多轮 query rewrite
- 答案生成
- 会话标题生成

是否触发取决于评测请求、会话上下文和模型配置。

## 5. 不会触发 OpenAI 调用的配置

以下配置目前属于预留或实验性配置，主流程中尚未真正接入 OpenAI 调用：

```bash
QUESTION_GENERATION_MODEL=gpt-4o-mini
HYPOTHETICAL_QUESTIONS_PER_CHUNK=3
HYBRID_PRIMARY_STRATEGY=parent-child
HYBRID_SECONDARY_STRATEGY=semantic
```

其中 `hybrid` 检索后端已经存在，但它使用的是 `OPENAI_EMBEDDING_MODEL` 生成的 query/chunk embedding，不使用 `HYBRID_PRIMARY_STRATEGY` 或 `HYBRID_SECONDARY_STRATEGY` 选择切片策略。

## 6. 成本与运维注意事项

- `semantic + openai` 会在导入/重建索引阶段多一轮 embedding 调用：先对 semantic windows 做边界判断，再对最终 chunks 生成检索向量。
- 从 `hash` 切换到 `openai` 后，建议对历史文档执行重建索引，否则旧 chunk embedding 与新 query embedding 不在同一向量空间。
- 切换 `OPENAI_EMBEDDING_MODEL` 或 embedding 维度后，也建议重建索引；如果使用 Milvus，还要确保 collection 维度与新 embedding 维度一致。
- API 和 worker 必须使用一致的模型配置。Temporal 模式下，导入和重建索引实际在 worker 进程中执行。

## 7. 快速配置示例

### 7.1 本地无模型依赖

```bash
EMBEDDING_BACKEND=hash
CHUNKING_STRATEGY=semantic
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=
```

效果：

- semantic 切片使用本地 hash embedding 判断边界。
- 检索向量使用本地 hash embedding。
- 回答生成使用本地启发式 provider。
- 不调用 OpenAI-compatible 接口。

### 7.2 真实 embedding + 本地回答

```bash
EMBEDDING_BACKEND=openai
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=
```

效果：

- chunk embedding 和 query embedding 调用 `/embeddings`。
- 回答生成仍使用本地启发式 provider。

### 7.3 Semantic 切片和问答都使用模型

```bash
CHUNKING_STRATEGY=semantic
EMBEDDING_BACKEND=openai
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=...
SEMANTIC_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
```

效果：

- semantic 边界判断调用 `/embeddings`，模型为 `SEMANTIC_EMBEDDING_MODEL`。
- 最终 chunk/query embedding 调用 `/embeddings`，模型为 `OPENAI_EMBEDDING_MODEL`。
- query rewrite、答案生成、标题生成调用 `/chat/completions`，模型为 `OPENAI_CHAT_MODEL`。
