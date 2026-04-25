# 文档导入、检索与有引用问答

## 1. 文档导入入口

后端当前支持三种输入方式：

- `inline_content`
- `source_path`
- `storage_uri`

其中 `storage_uri` 在开发环境支持：

- `file://`
- `s3://bucket/key`
- `minio://bucket/key`

`s3://` 和 `minio://` 会映射到 `OBJECT_STORAGE_LOCAL_ROOT/<bucket>/<key>`。

其中前端 `web` 控制台当前只暴露：

- `inline_content`
- 本地文件上传（落到 `uploaded_file_base64`）

## 2. 解析策略

解析器使用 `CompositeDocumentParser`，逻辑如下：

- Markdown：按标题层级切分 section。
- HTML：先去标签再进入 section 逻辑。
- Text：归一化空白后作为单 section。
- PDF/DOCX/PPTX：
  - 走 `Docling`。
  - 将结果导出为 Markdown。
  - 再复用 Markdown 解析链路。

当前实现优先保证统一格式和快速演示，后续可继续补：

- OCR
- 表格结构保留
- 图片锚点
- 页码精确回链

## 3. 切块策略

当前 chunk 参数通过环境变量配置：

- `CHUNK_SIZE` 默认 `700`
- `CHUNK_OVERLAP` 默认 `100`

切块目标与最初规划一致：

- 保留层级标题路径
- 为中文问答控制 chunk 粒度
- 为 rerank 和引用展示提供稳定片段边界

当前 chunk 实体会保存：

- `fragment_id`
- `section_title`
- `heading_path`
- `page_number`
- `start_offset`
- `end_offset`
- `token_count`
- `content`
- `embedding`

## 4. 索引策略

### Embedding Provider

当前 embedding provider 已支持两种模式：

- `hash`：本地伪向量器，不依赖外部模型。
- `openai`：真实 OpenAI-compatible embeddings，通过 `/embeddings` 接口取向量。

切换方式：

- `EMBEDDING_BACKEND=hash`
- `EMBEDDING_BACKEND=openai`

启用真实 embeddings 时还需要：

- `OPENAI_API_KEY`
- `OPENAI_EMBEDDING_MODEL`
- `OPENAI_BASE_URL`

### Memory Hybrid

适用于无外部依赖的轻量开发。

- 词法得分：query token 与内容 token 的交集比例。
- 语义得分：hash embedding 余弦相似度。
- 标题增强：命中 `heading_path` 时增加小幅加权。

### OpenSearch Hybrid

适用于 Docker 和标准联调环境。

- 候选召回：OpenSearch `multi_match` 查询
- 候选字段：
  - `content_terms`
  - `section_title_terms`
  - `heading_path_terms`
  - `document_title_terms`
- 本地 rerank：继续用 hash embedding 和标题命中做二次排序

这样的好处是：

- 不依赖供应商向量数据库
- 能兼顾中文关键词召回
- 在无 embeddings API 的情况下仍然可运行

当启用真实 embeddings 后，语义 rerank 的稳定性通常会比 `hash` 模式更好。

## 5. 问答生成策略

问答入口是 `POST /api/queries/answer`。

执行顺序：

1. 在知识空间内做混合召回
2. 取 `retrieval_top_k`
3. 做本地 rerank
4. 裁剪到 `rerank_top_k`
5. 组装 citations 与 source documents
6. 估算 confidence
7. 调用回答生成器

默认配置：

- `RETRIEVAL_TOP_K=50`
- `RERANK_TOP_K=8`
- `max_citations` 请求默认 `4`

## 6. Grounded 回答约束

系统遵循“证据优先”原则：

- 没有足够证据时，不输出确定性结论。
- 返回保守回答，并建议用户缩小问题或补充文档。
- 始终保存 `AnswerTrace`，便于复盘和评测。

当前保守回退触发条件：

- 没有召回结果
- 或估算置信度小于 `0.1`

## 7. 回答生成器

### HeuristicAnswerProvider

默认回答器，不依赖外部模型。

- 从 top 证据中抽取短片段
- 生成“可验证要点包括……”式回答
- 更适合离线开发与演示

### OpenAICompatibleAnswerProvider

在配置了以下环境变量后启用：

- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`

系统提示明确要求：

- 只能依据给定证据回答
- 不能编造
- 证据不足必须说明不足

## 8. 一致性规则

本次会话里修复了一条关键规则：

- 导入或重建索引任务只有在索引可查询后才会置为 `completed`。

这条规则直接解决了以下问题：

- 前端看到任务完成后立刻发问
- 检索层却还查不到 chunk
- 最终导致回答返回“证据不足”

现在 `completed` 的定义已经与用户感知保持一致。

## 9. embeddings 切换注意事项

- 从 `hash` 切换到 `openai` 后，建议对已有文档执行一次 `reindex`。
- 原因是旧 chunk 的向量可能仍然是 `hash` 结果，而新查询会变成真实 embedding。
- 当前系统在向量维度不一致时会把语义相似度视为 `0`，避免出现错误的部分维度比对。
