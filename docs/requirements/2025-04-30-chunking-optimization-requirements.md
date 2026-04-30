# 文档切割优化需求文档

## 文档信息

- **项目名称：** RAG 系统文档切割优化
- **版本：** v1.0
- **创建日期：** 2025-04-30
- **负责人：** [待填写]
- **参考设计：** `docs/superpowers/specs/2025-04-30-document-chunking-optimization-design.md`
- **实施计划：** `docs/superpowers/plans/2025-04-30-document-chunking-optimization-plan.md`

---

## 一、背景

### 当前问题

RAG 系统当前使用固定的文档切割策略（HierarchicalChunker），存在以下问题：

1. **检索质量受限** - 固定大小切割不考虑语义边界，可能导致相关内容被切到不同 chunk
2. **上下文完整性不足** - 检索返回的小块可能缺乏足够上下文用于生成高质量答案
3. **扩展性差** - 无法针对不同场景选择最优的切割策略
4. **效率与质量难以平衡** - 想要提高质量需要更大 chunk，但会影响检索精度

### 解决方案概述

实现**可配置的多种文档切割策略系统**，本期重点实现**父子文档策略**：

- **小块用于检索** - 提高检索召回率和准确率
- **大块用于生成** - 提供完整上下文用于生成高质量答案
- **策略可配置** - 支持通过配置切换不同策略
- **预留扩展接口** - 为未来策略（语义切割、文档增强等）预留接口

---

## 二、核心目标

### 必须达成（P0）

1. **建立策略框架** - 创建 ChunkingStrategy 抽象基类和工厂模式
2. **重构现有实现** - 将 HierarchicalChunker 重构为 FixedSizeStrategy，保持向后兼容
3. **实现父子文档策略** - 完整实现 ParentChildStrategy
4. **数据库支持** - 添加 chunk_type 和 parent_id 字段
5. **索引优化** - 只索引 child chunks 和 fixed chunks
6. **检索优化** - 检索时加载父文档内容用于生成答案

### 应该达成（P1）

7. **配置完整性** - 预置所有未来策略的配置项
8. **测试覆盖** - 完整的单元测试和集成测试
9. **性能基准** - 建立性能基准，确保可接受的切割速度
10. **文档完善** - 更新 README 和配置示例

### 可选达成（P2）

11. **前端更新** - 更新引用来源显示（可作为独立任务）
12. **性能监控** - 添加性能监控指标

---

## 三、架构设计

### 3.1 策略架构图

```
ChunkingStrategy (抽象基类)
    │
    ├── FixedSizeStrategy (现有策略重构)
    │   └── 参数: chunk_size=700, chunk_overlap=100
    │
    ├── ParentChildStrategy (本期新增)
    │   ├── 参数: parent_chunk_size=900, parent_overlap=150
    │   │         child_chunk_size=250, child_overlap=50
    │   └── 输出: parent chunks (大块) + child chunks (小块)
    │
    ├── SemanticStrategy (P1 预留)
    ├── SlidingSimilarityStrategy (P2 预留)
    ├── DocumentEnhancedStrategy (P2 预留)
    ├── RecursiveStrategy (P3 预留)
    └── HybridStrategy (P3 预留)
```

### 3.2 数据流程

#### 文档处理流程

```
1. Parser 解析文档 → ParsedSection[]
   ↓
2. ChunkingStrategyFactory 根据配置创建策略
   ↓
3. Strategy.chunk_sections() → PreparedChunk[]
   ├── ParentChildStrategy: parent[] + child[]
   └── FixedSizeStrategy: fixed[]
   ↓
4. 生成嵌入向量（仅 child chunks 和 fixed chunks）
   ↓
5. 存储到数据库（所有 chunks）
   ├── chunk_type: "parent" | "child" | "fixed"
   └── parent_id: child → parent 的关联
   ↓
6. 索引到搜索引擎（仅 child chunks 和 fixed chunks）
```

#### 检索流程

```
1. 用户提问
   ↓
2. 生成问题嵌入向量
   ↓
3. 搜索引擎检索（仅检索 child chunks）
   ↓
4. 获取 child chunks 的 parent_id
   ↓
5. 从数据库批量加载对应的 parent chunks
   ↓
6. 使用 parent chunks 内容作为上下文生成答案
   ↓
7. 返回答案（引用显示 parent chunk 信息）
```

### 3.3 文件结构

```
backend/app/services/
├── chunking.py                 # 现有，添加向后兼容导出
├── chunking_strategies/        # 新目录
│   ├── __init__.py
│   ├── base.py                 # 抽象基类 PreparedChunk, ChunkingStrategy
│   ├── fixed_size.py           # FixedSizeStrategy
│   └── parent_child.py         # ParentChildStrategy
├── chunking_factory.py         # 工厂类
├── ingestion.py                # 修改：使用工厂，更新嵌入逻辑
├── indexing.py                 # 修改：更新 SearchResult，索引过滤
└── answering.py                # 修改：检索时加载父文档

backend/app/core/
└── config.py                   # 添加所有策略配置项

backend/app/models/
└── entities.py                 # Chunk 模型添加 chunk_type, parent_id

backend/alembic/versions/
└── xxx_add_chunk_type_fields.py # 数据库迁移

tests/
├── test_chunking_strategies.py # 策略单元测试
├── test_models.py              # 模型测试
├── test_ingestion.py           # 集成测试
└── benchmarks/
    └── test_chunking_performance.py # 性能测试
```

---

## 四、技术规格

### 4.1 核心数据结构

#### PreparedChunk

```python
@dataclass(slots=True)
class PreparedChunk:
    fragment_id: str              # 块唯一标识
    section_title: str            # 章节标题
    heading_path: list[str]       # 标题路径
    page_number: int | None       # 页码
    start_offset: int             # 起始位置
    end_offset: int               # 结束位置
    token_count: int              # token 数量
    content: str                  # 内容
    chunk_type: str = "fixed"     # 类型: "fixed", "parent", "child"
    parent_id: str | None = None  # 父文档 ID（仅 child 使用）
```

#### ChunkingStrategy 接口

```python
class ChunkingStrategy(ABC):
    @abstractmethod
    def chunk_sections(self, sections: list[ParsedSection]) -> list[PreparedChunk]:
        """将文档章节切割成 chunks"""
        pass
```

### 4.2 FixedSizeStrategy 规格

**功能：** 基于字符数的固定窗口切割，在句子边界断开

**参数：**
- `chunk_size`: 700（默认）
- `chunk_overlap`: 100（默认）

**行为：**
- 短文本（≤ chunk_size）不切割
- 长文本按窗口切割
- 优先在句号（。）处断开，其次在空格处
- 重叠窗口保持上下文连续性

**输出：**
- 所有 chunks 的 `chunk_type = "fixed"`
- 所有 chunks 的 `parent_id = None`

### 4.3 ParentChildStrategy 规格

**功能：** 创建父子两种文档，小块检索大块生成

**参数：**
- `parent_chunk_size`: 900（默认）
- `parent_chunk_overlap`: 150（默认）
- `child_chunk_size`: 250（默认）
- `child_chunk_overlap`: 50（默认）

**行为：**

1. **第一步：创建父文档**
   - 将 section 内容按 parent_chunk_size 切割
   - 每个父文档获得唯一 fragment_id（格式：parent-0001）
   - chunk_type = "parent", parent_id = None

2. **第二步：为每个父文档创建子文档**
   - 将父文档内容按 child_chunk_size 切割
   - 每个子文档获得唯一 fragment_id（格式：child-0001）
   - chunk_type = "child", parent_id = 父文档 fragment_id

3. **关系维护**
   - 一个父文档 → 多个子文档
   - 每个子文档 → 一个父文档
   - 子文档内容必须在父文档内容范围内

**输出示例：**
```
输入: 2000 字的 section

父文档:
- parent-0001: 内容 [0-900]
- parent-0002: 内容 [750-1650]
- parent-0003: 内容 [1500-2000]

子文档（从 parent-0001 切割）:
- child-0001: 内容 [0-250], parent_id=parent-0001
- child-0002: 内容 [200-450], parent_id=parent-0001
- child-0003: 内容 [400-650], parent_id=parent-0001
- child-0004: 内容 [600-900], parent_id=parent-0001
...（其他父文档的子文档）
```

### 4.4 数据库变更

#### Chunk 表新增字段

```sql
ALTER TABLE chunks ADD COLUMN chunk_type VARCHAR(16) NOT NULL DEFAULT 'fixed';
ALTER TABLE chunks ADD COLUMN parent_id VARCHAR(36);
CREATE INDEX ix_chunks_parent_id ON chunks(parent_id);
```

#### 现有数据迁移

```sql
-- 将现有 chunks 标记为 fixed 类型
UPDATE chunks SET chunk_type = 'fixed' WHERE chunk_type IS NULL OR chunk_type = '';
```

### 4.5 嵌入和索引规则

**嵌入向量生成：**
- ✅ child chunks - 生成嵌入
- ✅ fixed chunks - 生成嵌入
- ❌ parent chunks - 不生成嵌入（空数组）

**搜索引擎索引：**
- ✅ child chunks - 索引
- ✅ fixed chunks - 索引
- ❌ parent chunks - 不索引

**原因：** 父文档不直接参与检索，通过子文档关联后加载

### 4.6 配置规格

#### 环境变量

```bash
# ========== 文档切割配置 ==========
CHUNKING_STRATEGY=fixed-size  # 或 parent-child

# Fixed-size 策略
CHUNK_SIZE=700
CHUNK_OVERLAP=100

# Parent-child 策略
PARENT_CHUNK_SIZE=900
PARENT_CHUNK_OVERLAP=150
CHILD_CHUNK_SIZE=250
CHILD_CHUNK_OVERLAP=50

# 预置未来策略配置（本期不实现，但需预置）
# Semantic (P1)
SEMANTIC_CHUNK_MAX_SIZE=500
SEMANTIC_SIMILARITY_THRESHOLD=0.75
SEMANTIC_EMBEDDING_MODEL=text-embedding-3-small

# Sliding-similarity (P2)
SLIDING_WINDOW_SIZE=300
SLIDING_OVERLAP_RATIO=0.3
SLIDING_MERGE_THRESHOLD=0.8

# Document-enhanced (P2)
HYPOTHETICAL_QUESTIONS_PER_CHUNK=3
QUESTION_GENERATION_MODEL=gpt-4o-mini

# Recursive (P3)
RECURSIVE_SEPARATORS=\n\n,\n,., 
RECURSIVE_MAX_CHUNK_SIZE=800

# Hybrid (P3)
HYBRID_PRIMARY_STRATEGY=parent-child
HYBRID_SECONDARY_STRATEGY=semantic
```

#### Settings 类

```python
class Settings(BaseSettings):
    # 基础配置
    chunking_strategy: str = os.getenv("CHUNKING_STRATEGY", "fixed-size")

    # Fixed-size
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "700"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "100"))

    # Parent-child
    parent_chunk_size: int = int(os.getenv("PARENT_CHUNK_SIZE", "900"))
    parent_chunk_overlap: int = int(os.getenv("PARENT_CHUNK_OVERLAP", "150"))
    child_chunk_size: int = int(os.getenv("CHILD_CHUNK_SIZE", "250"))
    child_chunk_overlap: int = int(os.getenv("CHILD_CHUNK_OVERLAP", "50"))

    # ... 未来策略配置
```

### 4.7 工厂类规格

```python
class ChunkingStrategyFactory:
    @staticmethod
    def create(settings: Settings) -> ChunkingStrategy:
        """根据配置创建策略

        Returns:
            ChunkingStrategy 实例

        Fallback:
            如果创建失败，回退到 FixedSizeStrategy 并记录错误日志
        """
        strategy_type = settings.chunking_strategy

        if strategy_type == "fixed-size":
            return FixedSizeStrategy(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap
            )
        elif strategy_type == "parent-child":
            return ParentChildStrategy(
                parent_size=settings.parent_chunk_size,
                parent_overlap=settings.parent_chunk_overlap,
                child_size=settings.child_chunk_size,
                child_overlap=settings.child_chunk_overlap
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy_type}")
```

---

## 五、实施计划

### 阶段 1：基础架构（1-2 天）

**任务清单：**

- [ ] **Task 1.1:** 创建 `chunking_strategies` 包和抽象基类
  - 文件：`backend/app/services/chunking_strategies/base.py`
  - 内容：定义 `PreparedChunk` 数据类和 `ChunkingStrategy` 抽象类
  - 测试：编写接口测试

- [ ] **Task 1.2:** 重构 `HierarchicalChunker` 为 `FixedSizeStrategy`
  - 文件：`backend/app/services/chunking_strategies/fixed_size.py`
  - 内容：将现有逻辑提取到 `FixedSizeStrategy` 类
  - 兼容：在 `chunking.py` 中保留 `HierarchicalChunker = FixedSizeStrategy` 别名

- [ ] **Task 1.3:** 创建 `ChunkingStrategyFactory`
  - 文件：`backend/app/services/chunking_factory.py`
  - 内容：实现工厂类，支持 fixed-size 和 parent-child
  - 回退：添加异常处理和回退到 fixed-size

- [ ] **Task 1.4:** 添加配置项
  - 文件：`backend/app/core/config.py`
  - 内容：添加所有策略的配置字段（包括未来策略）

**验收标准：**
- 可以通过配置切换 fixed-size 和 parent-child
- 现有功能不受影响
- 单元测试全部通过

### 阶段 2：父子文档策略（2-3 天）

**任务清单：**

- [ ] **Task 2.1:** 更新数据库模型
  - 文件：`backend/app/models/entities.py`
  - 内容：`Chunk` 类添加 `chunk_type` 和 `parent_id` 字段
  - 测试：验证新字段默认值和关系

- [ ] **Task 2.2:** 编写数据库迁移脚本
  - 文件：`backend/alembic/versions/xxx_add_chunk_type_fields.py`
  - 内容：添加字段、创建索引、更新现有数据
  - 测试：本地运行迁移验证

- [ ] **Task 2.3:** 实现 `ParentChildStrategy`
  - 文件：`backend/app/services/chunking_strategies/parent_child.py`
  - 内容：实现父子文档切割逻辑
  - 测试：验证父子关系、内容边界、元数据保留

- [ ] **Task 2.4:** 更新嵌入和索引逻辑
  - 文件：`backend/app/services/ingestion.py`
  - 内容：只对 child chunks 和 fixed chunks 生成嵌入
  - 文件：`backend/app/services/indexing.py`
  - 内容：添加 `chunk_type` 和 `parent_id` 到 `IndexedChunk` 和 `SearchResult`
  - 测试：验证父文档不被索引

- [ ] **Task 2.5:** 更新检索逻辑
  - 文件：`backend/app/services/answering.py`
  - 内容：检索后批量加载父文档，使用父内容生成答案
  - 测试：验证答案使用父文档内容

**验收标准：**
- ParentChildStrategy 正确创建父子关系
- 只索引 child chunks
- 检索时加载父文档内容
- 集成测试通过

### 阶段 3：检索优化（1-2 天）

**任务清单：**

- [ ] **Task 3.1:** 优化父文档批量加载
  - 文件：`backend/app/services/answering.py`
  - 内容：实现 `_load_parent_chunks_batch` 方法
  - 测试：性能测试，确保批量加载 < 100ms

- [ ] **Task 3.2:** 更新引用来源显示（文档化）
  - 说明：前端需要更新引用显示逻辑，显示父文档信息
  - 可交付：前端需求文档（作为独立任务）

**验收标准：**
- 批量加载性能可接受
- 前端需求文档清晰

### 阶段 4：测试和文档（1-2 天）

**任务清单：**

- [ ] **Task 4.1:** 运行完整测试套件
  - 命令：`pytest tests/ -v`
  - 要求：所有测试通过

- [ ] **Task 4.2:** 性能基准测试
  - 文件：`tests/benchmarks/test_chunking_performance.py`
  - 内容：对比 fixed-size 和 parent-child 的性能
  - 指标：切割速度、嵌入成本、存储成本

- [ ] **Task 4.3:** 更新文档
  - 文件：`README.md`
  - 内容：添加文档切割策略章节
  - 文件：`.env.example`
  - 内容：添加所有策略配置示例

**验收标准：**
- 所有测试通过
- 性能基准文档化
- 用户文档完整

---

## 六、并行实施指南

### 6.1 任务分配建议

为了支持并行开发，建议按以下方式分配任务：

**后端开发 A（架构基础）：**
- Task 1.1: 抽象基类
- Task 1.2: FixedSizeStrategy 重构
- Task 1.3: 工厂类

**后端开发 B（数据库和策略）：**
- Task 2.1: 数据库模型
- Task 2.2: 迁移脚本
- Task 2.3: ParentChildStrategy 实现

**后端开发 C（集成和优化）：**
- Task 2.4: 嵌入和索引
- Task 2.5: 检索逻辑
- Task 3.1: 批量加载优化

**测试工程师：**
- Task 1.x: 单元测试
- Task 2.x: 集成测试
- Task 4.2: 性能测试

**文档工程师：**
- Task 4.3: 文档更新
- Task 3.2: 前端需求文档

### 6.2 依赖关系

```
Task 1.1 (抽象基类)
    ↓
Task 1.2 (FixedSizeStrategy) → Task 1.3 (工厂类)
                                  ↓
                            Task 1.4 (配置)

Task 2.1 (模型) → Task 2.2 (迁移)
Task 2.3 (ParentChildStrategy) → Task 2.4 (嵌入索引)
Task 1.3 + Task 2.2 → Task 2.5 (检索逻辑)
Task 2.5 → Task 3.1 (批量加载)

Task 4.1 (测试) 需要 Task 1-3 完成
Task 4.2 (性能) 需要 Task 2.3 完成
Task 4.3 (文档) 可独立进行
```

### 6.3 集成点

**关键集成点 1：策略工厂完成**
- 标志：`ChunkingStrategyFactory` 可以创建 `FixedSizeStrategy`
- 后续任务：Task 2.3 可开始实现 `ParentChildStrategy`

**关键集成点 2：数据库迁移完成**
- 标志：`chunks` 表有 `chunk_type` 和 `parent_id` 字段
- 后续任务：Task 2.4 可更新嵌入和索引逻辑

**关键集成点 3：ParentChildStrategy 完成**
- 标志：单元测试验证父子关系正确
- 后续任务：Task 2.4 和 2.5 可开始集成

### 6.4 代码规范

**命名规范：**
- 策略类：`{Name}Strategy`（如 `FixedSizeStrategy`）
- 配置项：`{strategy}_{param}`（如 `parent_chunk_size`）
- Chunk 类型：小写（`fixed`, `parent`, `child`）

**Git 提交规范：**
- feat: 新功能
- refactor: 重构
- perf: 性能优化
- test: 测试
- docs: 文档

**代码审查要点：**
- [ ] 所有公共方法有 docstring
- [ ] 错误处理完善（有日志和回退）
- [ ] 向后兼容（现有 API 不变）
- [ ] 测试覆盖充分

---

## 七、验收标准

### 功能验收

- [ ] **F1:** 可以通过配置切换 `fixed-size` 和 `parent-child` 策略
- [ ] **F2:** `fixed-size` 策略与原有 `HierarchicalChunker` 行为一致
- [ ] **F3:** `parent-child` 策略创建的父子关系正确
  - 每个子文档有且只有一个父文档
  - 子文档内容在父文档内容范围内
- [ ] **F4:** 只索引 `child` chunks 和 `fixed` chunks
- [ ] **F5:** 检索时正确加载父文档内容用于生成答案
- [ ] **F6:** 现有文档数据不丢失，功能不受影响

### 性能验收

- [ ] **P1:** 切割 50,000 字文档 < 2 秒（parent-child 策略）
- [ ] **P2:** 批量加载 100 个父文档 < 100ms
- [ ] **P3:** 存储成本增加 ≤ 50%（相比 fixed-size）

### 质量验收

- [ ] **Q1:** 所有单元测试通过
- [ ] **Q2:** 所有集成测试通过
- [ ] **Q3:** 代码审查通过（遵循代码规范）
- [ ] **Q4:** 数据库迁移可逆（downgrade 可用）

### 文档验收

- [ ] **D1:** README 有文档切割策略章节
- [ ] **D2:** .env.example 包含所有策略配置
- [ ] **D3:** 代码注释清晰，关键逻辑有说明
- [ ] **D4:** 性能基准结果记录在案

---

## 八、风险和应对

### 风险 1：现有文档需要重新索引

**影响：** 切换到 `parent-child` 策略后，现有文档的 chunks 类型为 `fixed`，没有父子关系

**应对：**
- 提供 API 触发重新索引
- 支持按文档或按知识空间渐进式迁移
- 保留 `fixed-size` 策略作为备选

### 风险 2：存储成本增加

**影响：** `parent-child` 策略会增加约 50% 的 chunk 数量

**应对：**
- Parent chunks 不生成嵌入向量
- Parent chunks 不索引到搜索引擎
- 监控存储使用情况

### 风险 3：检索性能下降

**影响：** 需要额外的数据库查询加载父文档

**应对：**
- 批量查询父文档（一次查询加载多个）
- 考虑添加父文档缓存（可选）
- 性能测试验证影响

### 风险 4：配置复杂度增加

**影响：** 多个配置项可能造成用户困惑

**应对：**
- 提供合理的默认值
- 配置文件添加详细注释
- 考虑提供预设配置文件

---

## 九、支持资源

### 参考文档

- **设计文档：** `docs/superpowers/specs/2025-04-30-document-chunking-optimization-design.md`
- **实施计划：** `docs/superpowers/plans/2025-04-30-document-chunking-optimization-plan.md`

### 关键代码文件

**现有实现：**
- `backend/app/services/chunking.py` - 当前切割逻辑
- `backend/app/services/ingestion.py` - 文档导入流程
- `backend/app/services/indexing.py` - 搜索服务
- `backend/app/services/answering.py` - 答案生成
- `backend/app/models/entities.py` - 数据模型
- `backend/app/core/config.py` - 配置管理

**需要创建：**
- `backend/app/services/chunking_strategies/` - 策略包
- `backend/app/services/chunking_factory.py` - 工厂类
- `tests/test_chunking_strategies.py` - 策略测试

### 技术栈

- **语言：** Python 3.13
- **框架：** FastAPI, SQLAlchemy
- **数据库：** SQLite (开发), PostgreSQL (生产)
- **测试：** Pytest
- **迁移：** Alembic

---

## 十、联系方式

**技术问题咨询：** [待填写]

**进度汇报：** 每日 EOD 提供进度更新

**问题升级：** 遇到阻塞问题立即上报

---

## 附录：快速检查清单

### 开始前检查

- [ ] 已阅读完整需求文档
- [ ] 已阅读设计文档
- [ ] 已阅读实施计划
- [ ] 开发环境已配置
- [ ] 数据库已备份

### 完成后检查

- [ ] 所有 P0 任务已完成
- [ ] 功能验收全部通过
- [ ] 性能验收全部通过
- [ ] 质量验收全部通过
- [ ] 文档验收全部通过
- [ ] 代码已提交到 Git
- [ ] 数据库迁移已验证可逆

---

**文档版本历史：**

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2025-04-30 | 初始版本 |
