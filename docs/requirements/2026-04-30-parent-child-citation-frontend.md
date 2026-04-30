# Parent-Child 引用展示前端需求

## 背景

后端新增 `parent-child` 文档切割策略后，检索命中的是 `child` chunk，但问答返回的引用会展示对应 `parent` chunk 的 `fragment_id`、章节路径和 quote。前端现有引用列表可以继续使用现有字段，但应按更长 quote 和父 chunk 定位做展示优化。

## 建议调整

- 引用卡片继续显示 `document_title`、`section_title`、`heading_path`、`page_number`、`score`。
- `fragment_id` 可能是 `parent-0001` 或 `frag-0001`，前端不要假设固定前缀。
- quote 可能比 fixed-size 更长，引用卡片默认展示前 3-5 行，并保留展开/收起。
- 点击引用回链仍调用 `GET /api/documents/{document_id}/fragments/{fragment_id}`；该接口已返回 `chunk_type` 和 `parent_id`。
- 如需调试命中链路，可在开发模式展示 `chunk_type`。正式 UI 不建议把策略术语暴露给普通用户。
