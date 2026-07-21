# RAG 召回与上下文记忆融合优化方案

## 1. 背景

当前项目已经具备两类能力：

1. RAG 召回能力：根据用户问题召回表信息、字段信息、指标信息和字段取值。
2. 会话级上下文记忆：通过 `session_id` 保存多轮查询历史，并在追问时结合最近历史改写问题。

目前这两部分能力相对独立：

```text
RAG 负责找表、字段、指标
上下文 memory 负责理解多轮追问
```

后续可以把它们融合起来，让系统不仅能从元数据中找知识，还能从历史成功查询中复用经验。

目标不是做泛化的长期聊天记忆，而是做更适合问数业务的：

```text
会话上下文 + 语义槽位 + 元数据召回 + 历史成功 Query Case 召回
```

## 2. 现状分析

### 2.1 当前上下文记忆

相关文件：

```text
app/services/query_history_service.py
app/repositories/mysql/meta/query_history_repository.py
app/core/query_rewriter.py
app/core/context_rewrite/llm_rewriter.py
```

当前流程：

```text
前端携带 session_id
-> 后端查询最近 3 轮历史
-> 规则或 LLM 改写当前追问
-> 得到 resolved_query
-> 进入 LangGraph 问数流程
-> 保存 query_history
```

历史记录中已经保存：

```text
query
resolved_query
sql_text
result_summary
result_data
context_trace
semantic_slots
rewrite_confidence
status
```

### 2.2 当前 RAG 召回

相关文件：

```text
app/agent/nodes/recall_metric.py
app/agent/nodes/recall_column.py
app/agent/nodes/recall_value.py
app/agent/nodes/merge_retrieved_info.py
app/repositories/qdrant/
app/repositories/es/
```

当前 RAG 主要召回：

```text
指标信息
字段信息
字段取值
表结构信息
```

当前不足：

- RAG 召回只依赖用户问题文本，对 `semantic_slots` 利用不充分。
- 历史成功 SQL 没有沉淀成可复用经验。
- 向量召回结果缺少结合业务槽位的二次重排。
- SQL 生成 prompt 中缺少相似成功案例的结构化参考。

## 3. 优化目标

本次优化目标分为四个方向：

1. 把历史成功查询沉淀为 Query Case。
2. 用 `semantic_slots` 增强 RAG 检索 query。
3. 对召回结果做业务相关性重排。
4. 将相似 Query Case 压缩后注入 SQL 生成上下文。

整体目标：

```text
提升 NL2SQL 的稳定性
降低无关召回上下文噪声
增强多轮追问下的业务理解能力
让系统具备可解释的历史经验复用能力
```

## 4. 核心设计

### 4.1 Query Case Memory

Query Case 表示一次成功问数案例。

每次查询成功后，将本次查询沉淀为结构化案例：

```json
{
  "question": "统计 2025 年第一季度各大区 GMV",
  "resolved_query": "统计 2025 年第一季度各大区 GMV，并按 GMV 从高到低排序",
  "semantic_slots": {
    "time_range": "2025 年第一季度",
    "dimension": "大区",
    "metrics": ["GMV"],
    "filters": {},
    "sort": {
      "field": "GMV",
      "direction": "desc"
    }
  },
  "sql": "SELECT ...",
  "used_tables": ["fact_order", "dim_region", "dim_date"],
  "used_fields": ["order_amount", "region_id", "date_id"],
  "sql_pattern": "按大区维度分组，汇总订单金额，并按 GMV 降序排序",
  "result_summary": "返回 5 行，字段：大区、GMV"
}
```

它的作用不是直接复用旧 SQL，而是给新问题提供：

```text
相似业务问法
常用表组合
常用字段组合
SQL 结构模式
指标与维度搭配经验
```

### 4.2 Semantic Slots 增强检索

当前追问改写后已经有 `semantic_slots`。

后续召回时不只用用户原始问题，而是构造更稳定的检索文本：

```text
resolved_query
+ metrics
+ dimension
+ filters
+ time_range
+ sort
```

示例：

```json
{
  "resolved_query": "统计 2025 年第一季度华东地区 GMV",
  "semantic_slots": {
    "time_range": "2025 年第一季度",
    "dimension": "大区",
    "metrics": ["GMV"],
    "filters": {
      "region": "华东"
    }
  }
}
```

构造后的检索 query：

```text
统计 2025 年第一季度华东地区 GMV 指标 GMV 维度 大区 过滤条件 region=华东 时间 2025 年第一季度
```

这样可以降低自然语言省略、口语化表达对召回质量的影响。

### 4.3 召回结果重排

向量召回的 topK 不一定都适合进入 SQL prompt。

需要结合 `semantic_slots` 做二次打分：

```text
命中指标名：+3
命中维度字段：+2
命中过滤字段：+2
命中时间字段：+1
候选字段属于候选主表：+2
指标和字段绑定关系匹配：+3
和当前问题无关：-2
```

重排后只保留高相关上下文，避免 prompt 噪声。

### 4.4 Query Case 压缩注入

不能把完整历史聊天记录直接塞进 prompt。

召回相似 Query Case 后，需要压缩成结构化参考：

```json
{
  "similar_cases": [
    {
      "question": "统计 2025 年第一季度各大区 GMV",
      "used_tables": ["fact_order", "dim_region", "dim_date"],
      "used_fields": ["order_amount", "region_id", "date_id"],
      "sql_pattern": "按大区维度 group by，sum(order_amount)，按 GMV 降序"
    }
  ]
}
```

SQL 生成阶段只参考这些结构化信息，不直接照抄旧 SQL。

## 5. 推荐架构

优化后的链路：

```text
用户问题
  ↓
session_id 获取最近历史
  ↓
上下文改写，生成 resolved_query 和 semantic_slots
  ↓
用 resolved_query + semantic_slots 构造 RAG 检索 query
  ↓
召回指标、字段、取值、Query Case
  ↓
结合 semantic_slots 对召回结果 rerank
  ↓
合并元数据上下文和相似 Query Case
  ↓
生成 SQL
  ↓
执行查询
  ↓
保存 query_history
  ↓
成功查询沉淀为新的 Query Case
```

## 6. 后端改造点

### 6.1 新增 Query Case 构建模块

建议新增：

```text
app/core/query_case_memory.py
```

职责：

```text
从成功查询中提取 Query Case
从 SQL 中解析使用到的表和字段
生成 sql_pattern
构造用于向量化的 case_text
压缩相似 Query Case
```

建议函数：

```python
def build_query_case(
    query: str,
    resolved_query: str,
    sql: str,
    semantic_slots: dict,
    result_summary: str | None,
) -> dict:
    ...


def build_query_case_text(query_case: dict) -> str:
    ...


def compress_similar_cases(cases: list[dict]) -> list[dict]:
    ...
```

### 6.2 新增 Query Case 向量仓储

建议新增：

```text
app/repositories/qdrant/query_case_qdrant_repository.py
```

职责：

```text
保存成功 Query Case embedding
根据当前问题召回相似 Query Case
返回结构化 payload
```

建议接口：

```python
async def upsert_query_case(self, query_case: dict, vector: list[float]) -> None:
    ...


async def search_query_cases(self, vector: list[float], limit: int = 3) -> list[dict]:
    ...
```

### 6.3 改造 QueryService

涉及文件：

```text
app/services/query_history_service.py
```

改造点：

1. 上下文改写后，将 `semantic_slots` 放入后续召回上下文。
2. 查询成功后，构建 Query Case。
3. 将 Query Case 写入 Qdrant。
4. Query Case 写入失败时不能影响主查询链路。

伪流程：

```python
rewrite_result = await self.context_rewriter(query, recent_turns)

state = DataAgentState(
    query=rewrite_result.resolved_query,
    semantic_slots=rewrite_result.semantic_slots,
)

...

if final_status == "success" and sql:
    query_case = build_query_case(...)
    await query_case_memory_repository.upsert_query_case(...)
```

### 6.4 改造召回节点

涉及文件：

```text
app/agent/nodes/recall_metric.py
app/agent/nodes/recall_column.py
app/agent/nodes/merge_retrieved_info.py
```

改造点：

1. 使用增强后的检索 query。
2. 读取 `semantic_slots`。
3. 对召回结果做 rerank。
4. 合并相似 Query Case。

建议新增：

```text
app/core/rag_reranker.py
```

职责：

```text
根据 semantic_slots 对指标、字段、表、Query Case 进行业务相关性打分
```

建议函数：

```python
def build_retrieval_query(resolved_query: str, semantic_slots: dict) -> str:
    ...


def rerank_recalled_context(candidates: list[dict], semantic_slots: dict) -> list[dict]:
    ...
```

### 6.5 改造 SQL Prompt 上下文

涉及文件：

```text
app/agent/nodes/merge_retrieved_info.py
prompts/generate_sql.prompt
```

在 SQL prompt 中新增：

```text
相似成功查询案例：
- 问题：...
- 使用表：...
- 使用字段：...
- SQL 模式：...

注意：
1. 相似案例只作为结构参考。
2. 不允许直接复制案例 SQL。
3. 当前问题的指标、时间、过滤条件优先级更高。
```

## 7. 数据结构设计

### 7.1 Query Case Payload

```json
{
  "case_id": "qc_20260705_xxxx",
  "question": "",
  "resolved_query": "",
  "semantic_slots": {},
  "sql": "",
  "used_tables": [],
  "used_fields": [],
  "sql_pattern": "",
  "result_summary": "",
  "created_at": ""
}
```

### 7.2 Query Case 向量文本

建议向量化文本：

```text
问题：统计 2025 年第一季度各大区 GMV
完整问题：统计 2025 年第一季度各大区 GMV，并按 GMV 从高到低排序
指标：GMV
维度：大区
过滤条件：无
时间范围：2025 年第一季度
使用表：fact_order, dim_region, dim_date
使用字段：order_amount, region_id, date_id
SQL模式：按大区分组，汇总订单金额，按 GMV 降序
```

## 8. 实施步骤

### 第一阶段：构造 Query Case

目标：

```text
先不接 Qdrant，只把成功查询转成 Query Case，并用单元测试覆盖。
```

任务：

1. 新增 `app/core/query_case_memory.py`。
2. 实现 `build_query_case()`。
3. 实现简单 SQL 表名和字段提取。
4. 实现 `sql_pattern` 生成。
5. 新增 `tests/test_query_case_memory.py`。

验收：

```text
成功查询可以生成包含 question、resolved_query、semantic_slots、used_tables、used_fields、sql_pattern 的 Query Case。
```

### 第二阶段：semantic_slots 增强检索 query

目标：

```text
让 RAG 检索不只依赖自然语言问题，而是结合结构化槽位。
```

任务：

1. 新增 `app/core/rag_reranker.py`。
2. 实现 `build_retrieval_query()`。
3. 在召回节点中使用增强 query。
4. 增加单元测试。

验收：

```text
输入 resolved_query 和 semantic_slots 后，可以生成包含指标、维度、过滤条件、时间范围的检索文本。
```

### 第三阶段：召回结果重排

目标：

```text
减少无关字段和无关表进入 SQL prompt。
```

任务：

1. 实现候选召回结果打分。
2. 指标、维度、过滤条件命中加权。
3. 保留 topN 高相关候选。
4. 增加 rerank 单元测试。

验收：

```text
当用户问题包含 GMV 和大区时，GMV 指标、大区字段、订单事实表优先级更高。
```

### 第四阶段：Query Case RAG

目标：

```text
让历史成功查询成为可召回经验。
```

任务：

1. 新增 Query Case Qdrant repository。
2. 查询成功后写入 Query Case。
3. 下一次查询时召回相似 Query Case。
4. 将相似案例压缩后注入 SQL prompt。

验收：

```text
相似历史问题可以被召回，并以 sql_pattern 的形式辅助当前 SQL 生成。
```

## 9. 测试建议

### 9.1 单元测试

建议新增：

```text
tests/test_query_case_memory.py
tests/test_rag_reranker.py
```

覆盖：

```text
Query Case 构造
SQL 表名提取
SQL 字段提取
sql_pattern 生成
semantic_slots 检索 query 构造
召回候选重排
相似 Query Case 压缩
```

### 9.2 集成测试

覆盖场景：

```text
第一轮：统计 2025 年第一季度各大区 GMV
第二轮：那华东地区呢
第三轮：换成订单数
```

验证：

```text
第二轮和第三轮能够继承时间范围
召回 query 中包含继承后的 semantic_slots
SQL 生成上下文中包含正确指标、维度和过滤条件
```

## 10. 风险与边界

### 10.1 不直接复用旧 SQL

历史 Query Case 只能作为参考，不能直接复制旧 SQL。

原因：

```text
当前问题的时间、过滤条件、指标可能不同
旧 SQL 可能不适合当前业务口径
直接复用会带来错误查询风险
```

### 10.2 Query Case 只保存成功查询

失败、澄清、拒答、数据变更审批类请求不应沉淀为 Query Case。

建议只保存：

```text
status = success
sql 不为空
result_data 有效
```

### 10.3 召回失败不影响主流程

Query Case 写入或召回失败时，主查询链路仍然可以继续使用原有元数据 RAG。

## 11. 面试表达

可以这样讲：

```text
我在项目中把上下文 memory 和 RAG 召回做了融合。系统不只是保存聊天记录，而是把每轮成功查询抽象成 semantic_slots 和 Query Case，包括问题、SQL、使用表字段和 SQL 模式。下一轮查询时，系统会先基于 session_id 取最近历史完成上下文改写，再用 resolved_query 和 semantic_slots 构造检索 query，召回指标、字段和值，同时召回相似历史 Query Case。召回结果会经过业务相关性重排，最后以压缩后的结构化上下文进入 SQL 生成 prompt，从而降低无关上下文噪声，提升 NL2SQL 稳定性。
```

简历表达：

```text
优化问数 Agent 的 RAG 与上下文记忆链路：基于 session_id 持久化多轮查询历史和 semantic_slots，将成功查询沉淀为 Query Case，通过向量召回相似历史案例，并结合语义槽位对指标、字段、表召回结果进行业务重排，降低上下文噪声，提升复杂追问场景下的 SQL 生成稳定性。
```

## 12. 总结

这个优化的核心不是增加泛化聊天记忆，而是让问数系统拥有可复用的业务经验：

```text
历史上下文用于理解追问
semantic_slots 用于结构化表达业务意图
RAG 用于召回元数据和历史成功案例
rerank 用于降低上下文噪声
Query Case 用于复用成功 SQL 模式
```

推荐优先实现：

```text
Query Case 构造
semantic_slots 增强检索 query
召回结果 rerank
```

这三项最容易落地，也最能体现项目的业务和工程深度。
