# 文档切割优化设计

## 概述

本设计旨在优化 RAG 系统的文档切割策略，通过支持可配置的多种切割策略来提升检索质量、保持上下文完整性，同时保持良好的切割效率。

## 目标

1. **检索质量** - 提高检索召回率和准确率
2. **上下文完整性** - 确保每个 chunk 保持语义完整
3. **切割效率** - 保持合理的文档处理速度
4. **可扩展性** - 支持未来添加更多切割策略

## 架构设计

### 策略架构

```
ChunkingStrategy (抽象基类/接口)
    ↓
    ├── FixedSizeStrategy (现有策略)
    ├── ParentChildStrategy (父子文档策略)
    ├── SemanticStrategy (语义切分策略 - P1)
    ├── SlidingSimilarityStrategy (滑动窗口相似度 - P2)
    ├── DocumentEnhancedStrategy (文档增强策略 - P2)
    ├── RecursiveStrategy (递归结构切割 - P3)
    └── HybridStrategy (混合策略 - P3)
```

### 核心组件

1. **ChunkingStrategy (抽象基类)** - 定义策略接口
2. **ChunkingStrategyFactory** - 根据配置创建对应策略
3. **各策略实现类** - 独立实现各自的切分逻辑
4. **ChildIndexer** - 只索引子文档到搜索引擎
5. **ParentRetriever** - 检索后加载父文档内容

### 数据流

**文档处理流程：**

```
Parser 解析文档
    ↓
根据配置创建 ChunkingStrategy
    ↓
Strategy.chunk_sections() 生成 chunks
    ↓
生成嵌入向量（child chunks 和 fixed chunks）
    ↓
存储到数据库（所有 chunks）
    ↓
索引到搜索引擎（仅 child chunks 和 fixed chunks）
```

**检索流程：**

```
用户提问
    ↓
生成问题嵌入向量
    ↓
搜索引擎检索（仅检索 child chunks）
    ↓
获取 child chunks 的 parent_id
    ↓
从数据库加载对应的 parent chunks 内容
    ↓
使用 parent chunks 作为上下文生成答案
    ↓
返回答案（引用来源显示 parent chunk 信息）
```

## 各策略详细设计

### 1. FixedSizeStrategy（已实现）

基于字符数的固定窗口切割，在句子边界处断开。

**参数：**
- `chunk_size`: 700 (默认)
- `chunk_overlap`: 100 (默认)

**特点：**
- 实现简单，效率高
- 适合通用场景
- 缺乏语义理解

### 2. ParentChildStrategy（本期实现）

父子文档策略：小块用于检索，大块用于生成。

**参数：**
- `parent_chunk_size`: 900 (默认)
- `parent_chunk_overlap`: 150 (默认)
- `child_chunk_size`: 250 (默认)
- `child_chunk_overlap`: 50 (默认)

**特点：**
- 检索精度高（小块更精准）
- 生成质量好（大块提供完整上下文）
- 适合问答系统

**存储成本：** 约 +50%

### 3. SemanticStrategy（P1 优先级）

基于句子嵌入的语义边界切割。

**参数：**
- `semantic_chunk_max_size`: 500 (默认)
- `semantic_similarity_threshold`: 0.75 (默认)
- `semantic_embedding_model`: text-embedding-3-small (默认)

**特点：**
- 保持语义完整性
- 需要额外的嵌入模型调用
- 检索质量更高

### 4. SlidingSimilarityStrategy（P2 优先级）

滑动窗口 + 相似度合并策略。

**参数：**
- `sliding_window_size`: 300 (默认)
- `sliding_overlap_ratio`: 0.3 (默认)
- `sliding_merge_threshold`: 0.8 (默认)

**特点：**
- 平衡效率和语义
- 相似度合并减少碎片

### 5. DocumentEnhancedStrategy（P2 优先级）

基于文档生成假设性问题进行增强。

**参数：**
- `hypothetical_questions_per_chunk`: 3 (默认)
- `question_generation_model`: gpt-4o-mini (默认)

**特点：**
- 为每个 chunk 生成问题
- 问题-答案对一起索引
- 提升问答匹配度

### 6. RecursiveStrategy（P3 优先级）

按文档结构递归切割。

**参数：**
- `recursive_separators`: ["\n\n", "\n", ".", " "] (默认)
- `recursive_max_chunk_size`: 800 (默认)

**特点：**
- 保留文档结构
- 适合结构化文档

### 7. HybridStrategy（P3 优先级）

结合多种策略的混合方案。

## 数据模型变更

### Chunk 表新增字段

```python
chunk_type: Mapped[str] = mapped_column(String(16), default="fixed", nullable=False)
parent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
```

### ChunkType 枚举

```python
class ChunkType(str, Enum):
    FIXED = "fixed"           # 固定大小切割
    PARENT = "parent"         # 父文档
    CHILD = "child"           # 子文档
    SEMANTIC = "semantic"     # 语义切割
    DOCUMENT = "document"     # 文档内容
    QUESTION = "question"     # 生成的假设性问题
```

## 配置

### 环境变量

```bash
# 基础配置
CHUNKING_STRATEGY=fixed-size  # 或 parent-child, semantic 等

# Fixed-size 配置
CHUNK_SIZE=700
CHUNK_OVERLAP=100

# Parent-child 配置
PARENT_CHUNK_SIZE=900
PARENT_CHUNK_OVERLAP=150
CHILD_CHUNK_SIZE=250
CHILD_CHUNK_OVERLAP=50

# Semantic 配置
SEMANTIC_CHUNK_MAX_SIZE=500
SEMANTIC_SIMILARITY_THRESHOLD=0.75
SEMANTIC_EMBEDDING_MODEL=text-embedding-3-small

# Document-enhanced 配置
HYPOTHETICAL_QUESTIONS_PER_CHUNK=3
QUESTION_GENERATION_MODEL=gpt-4o-mini
```

## 实施计划

### 阶段 1：基础架构（1-2天）
1. 创建 `ChunkingStrategy` 抽象基类
2. 重构现有实现为 `FixedSizeStrategy`
3. 创建 `ChunkingStrategyFactory`
4. 添加配置项
5. 更新 `IngestionService`
6. 编写单元测试

### 阶段 2：父子文档策略（2-3天）
1. 实现 `ParentChildStrategy` 类
2. 更新数据库模型
3. 编写数据库迁移脚本
4. 更新嵌入和索引逻辑
5. 更新检索逻辑
6. 编写测试

### 阶段 3：检索优化（1-2天）
1. 更新引用来源显示逻辑
2. 优化父文档加载性能
3. 更新文档抽屉显示逻辑

### 阶段 4：测试和优化（1-2天）
1. 运行完整测试套件
2. 性能基准测试
3. 优化热点代码
4. 文档更新

**总计：5-9天**

## 风险和缓解

| 风险 | 缓解方案 |
|------|----------|
| 现有文档需要重新索引 | 提供批量重新索引功能，支持渐进式迁移 |
| 存储成本增加约 50% | Parent chunks 不索引到搜索引擎 |
| 检索时需要额外查询 | 批量查询父文档，考虑缓存 |
| 配置复杂度增加 | 提供合理的默认值和详细注释 |

## 向后兼容性

- 现有 API 不变
- 现有数据不丢失
- fixed-size 策略保持功能完整
- 新增字段有默认值

## 策略路线图

| 策略 | 状态 | 优先级 |
|------|------|--------|
| fixed-size | ✅ 已实现 | - |
| parent-child | 🚧 本期实现 | - |
| semantic | 📋 计划中 | P1 |
| sliding-similarity | 📋 计划中 | P2 |
| document-enhanced | 📋 计划中 | P2 |
| recursive | 📋 计划中 | P3 |
| hybrid | 📋 计划中 | P3 |
