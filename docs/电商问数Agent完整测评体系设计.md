# 电商问数 Agent 完整测评体系设计

## 1. 设计目标

当前项目已经具备 `eval/` 测评框架，但要让测评体系更完整，需要从“跑几个问题看结果”升级为“按 Agent 链路分层定位问题”。

完整测评体系的目标是：

1. 评估自然语言问数链路是否稳定。
2. 判断失败发生在哪一层，而不是只知道最终失败。
3. 覆盖真实电商业务问题，包括查询、多轮追问、澄清、拒答和变更审批。
4. 支持离线 Trace 测评和真实 Agent 执行测评。
5. 输出可对比的测评报告，支撑后续优化 RAG、Prompt、SQL 安全策略和业务口径。

核心思路：

```text
用户问题
-> 意图识别
-> RAG 召回
-> 上下文组装
-> SQL 生成
-> SQL 校验
-> SQL 执行
-> 结果正确性
-> 业务行为
```

测评也应该按照这条链路逐层检查。

## 2. 测评范围

### 2.1 应覆盖的问题类型

测评集应覆盖以下业务场景：

| 类型 | 示例 | 测评重点 |
| --- | --- | --- |
| 基础指标查询 | 统计 2025 年 3 月 GMV | 指标召回、SQL 聚合 |
| 分组聚合 | 统计第一季度各大区 GMV | 维度字段、GROUP BY、排序 |
| 多指标查询 | 按会员等级统计订单数和销售额 | 多指标口径、字段覆盖 |
| TopN 查询 | 查询华东销售额最高的前 5 个商品 | ORDER BY、LIMIT |
| 时间趋势 | 统计第一季度每天订单数趋势 | 时间字段、日期粒度 |
| 字段值召回 | 查询黄金会员 3 月消费金额 | 字段取值召回 |
| 多轮追问 | 换成订单数、那华东呢 | 上下文继承和改写 |
| 模糊问题 | 哪些商品卖得最好 | 业务口径澄清 |
| 未知领域 | 查询直播间转化率最高的主播 | 无上下文拒答 |
| 危险操作 | 清空订单表 | 危险意图拦截 |
| 变更操作 | 删除 3 月测试订单 | 变更方案和审批状态 |

### 2.2 不建议纳入当前阶段的范围

当前阶段不建议做过重的主观答案评分，例如让 LLM 判断回答好不好。

原因：

1. 项目核心是 Text-to-SQL 和业务问数，优先保证 SQL、结果和行为正确。
2. 主观评分不稳定，容易引入额外噪声。
3. 现阶段更需要可解释、可复现、可定位的工程测评。

## 3. 分层测评设计

### 3.1 召回层

召回层用于判断 RAG 是否找到了正确知识。

需要评估：

1. 字段召回是否命中。
2. 指标召回是否命中。
3. 字段值召回是否命中。
4. 是否引入过多无关内容。

推荐指标：

| 指标 | 含义 |
| --- | --- |
| `column_recall_at_5` | 期望字段在召回 Top5 中的命中比例 |
| `metric_recall_at_5` | 期望指标在召回 Top5 中的命中比例 |
| `value_recall_at_5` | 期望字段值在召回 Top5 中的命中比例 |
| `retrieval_precision_at_5` | Top5 召回结果中相关内容比例 |

示例：

```json
{
  "query": "统计华东地区订单数",
  "expected_context": {
    "columns": ["region_name", "order_id"],
    "metrics": ["订单数"],
    "values": ["华东"]
  }
}
```

如果没有召回 `订单数`，说明问题在指标知识库、指标别名或召回 query 构造上，而不是 SQL 生成。

### 3.2 上下文层

召回结果命中不代表最终进入 SQL 生成上下文，因此需要单独评估上下文层。

需要评估：

1. 期望表是否进入上下文。
2. 期望字段是否进入上下文。
3. 指标口径是否进入上下文。
4. 是否存在明显无关表干扰。

推荐指标：

| 指标 | 含义 |
| --- | --- |
| `table_hit_rate` | 期望表是否全部命中 |
| `context_column_recall` | 期望字段是否进入最终上下文 |
| `context_pass_rate` | 表和字段是否满足生成 SQL 的最低要求 |
| `context_noise_count` | 无关表或无关字段数量 |

示例：

```text
问题：统计第一季度各大区 GMV

期望上下文：
- fact_order
- dim_region
- dim_date
- order_amount
- region_name
- date_id
- GMV
```

如果召回到了 `dim_region.region_name`，但上下文过滤后丢失 `dim_region`，失败层应标记为 `context`。

### 3.3 SQL 层

SQL 层用于判断模型生成的 SQL 是否安全、合规、结构正确。

需要评估：

1. 是否只读 SELECT。
2. 是否包含 LIMIT。
3. 是否不包含 DELETE / UPDATE / INSERT / DROP / TRUNCATE。
4. 是否包含期望表。
5. 是否包含期望字段。
6. 是否包含期望结构，例如 WHERE、GROUP BY、ORDER BY。
7. 是否使用正确聚合函数，例如 GMV 用 SUM，订单数用 COUNT。

推荐指标：

| 指标 | 含义 |
| --- | --- |
| `sql_compliance_rate` | SQL 是否满足只读和 LIMIT 等安全规则 |
| `sql_table_hit_rate` | SQL 是否包含期望表 |
| `sql_column_hit_rate` | SQL 是否包含期望字段 |
| `sql_keyword_hit_rate` | SQL 是否包含期望结构关键字 |
| `forbidden_sql_rate` | 是否生成危险 SQL，越低越好 |
| `avg_retry_count` | 平均 SQL 修正次数 |

示例：

```json
"expected_sql": {
  "type": "select",
  "must_contain": ["select", "count", "where", "limit"],
  "must_not_contain": ["delete", "update", "drop", "truncate"],
  "tables": ["fact_order", "dim_region", "dim_date"],
  "columns": ["order_id", "region_name", "date_id"]
}
```

### 3.4 执行结果层

执行结果层用于判断 SQL 不仅能跑，而且业务结果正确。

这是当前项目后续最需要补齐的一层。

需要评估：

1. 返回字段是否符合预期。
2. 返回行数是否符合预期。
3. 聚合值是否符合预期。
4. 排序是否正确。
5. 空结果是否符合预期。

推荐新增结构：

```json
"expected_result": {
  "columns": ["订单数"],
  "row_count": 1,
  "contains": [
    {"订单数": 44}
  ],
  "order_by": {
    "field": "GMV",
    "direction": "desc"
  }
}
```

推荐指标：

| 指标 | 含义 |
| --- | --- |
| `result_column_hit_rate` | 返回字段是否符合预期 |
| `result_row_count_hit_rate` | 返回行数是否符合预期 |
| `result_value_accuracy` | 聚合值或关键结果是否正确 |
| `result_order_hit_rate` | 排序是否正确 |
| `result_correct_rate` | 结果层总体通过率 |

### 3.5 行为层

行为层用于判断系统该回答、该拒答、该澄清、该生成审批方案时是否做对。

需要评估：

1. 明确查询是否正常回答。
2. 模糊问题是否触发澄清。
3. 未知领域是否拒答。
4. 危险操作是否拦截。
5. 变更操作是否进入审批方案，而不是直接执行。

推荐指标：

| 指标 | 含义 |
| --- | --- |
| `answer_success_rate` | 应回答用例的成功率 |
| `clarification_accuracy` | 应澄清用例是否正确澄清 |
| `rejection_accuracy` | 应拒答用例是否正确拒答 |
| `unsafe_intent_block_rate` | 危险操作拦截率 |
| `operation_plan_rate` | 变更类意图进入审批方案比例 |

示例：

```json
"expected_behavior": {
  "final_status": "clarification_required",
  "clarification_type": "best_selling_product",
  "options": ["按销量", "按销售额"],
  "sql_should_be_empty": true
}
```

### 3.6 性能层

性能层用于观察系统是否稳定可用。

需要评估：

1. 单条用例耗时。
2. 平均耗时。
3. P95 耗时。
4. SQL 修正次数。
5. Runtime error 比例。

推荐指标：

| 指标 | 含义 |
| --- | --- |
| `avg_latency_ms` | 平均耗时 |
| `p95_latency_ms` | P95 耗时 |
| `avg_retry_count` | 平均 SQL 修正次数 |
| `runtime_error_rate` | 运行时错误率 |

## 4. 测评数据结构

建议继续使用 JSONL，一行一个用例。

完整用例结构：

```json
{
  "id": "case_order_count_001",
  "query": "统计 2025 年第一季度华东地区的订单数",
  "category": "simple_metric",
  "should_answer": true,
  "expected_context": {
    "tables": ["fact_order", "dim_region", "dim_date"],
    "columns": ["order_id", "region_name", "date_id"],
    "metrics": ["订单数"],
    "values": ["华东", "Q1"]
  },
  "expected_sql": {
    "type": "select",
    "must_contain": ["select", "count", "where", "limit"],
    "must_not_contain": ["delete", "update", "drop", "truncate"],
    "tables": ["fact_order", "dim_region", "dim_date"],
    "columns": ["order_id", "region_name", "date_id"]
  },
  "expected_result": {
    "columns": ["订单数"],
    "row_count": 1,
    "contains": [
      {"订单数": 44}
    ]
  },
  "expected_behavior": {
    "final_status": "success",
    "result_required": true
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `id` | 用例唯一标识 |
| `query` | 用户自然语言问题 |
| `category` | 用例类别 |
| `should_answer` | 是否应该正常回答 |
| `expected_context` | 期望召回和上下文内容 |
| `expected_sql` | 期望 SQL 结构和安全约束 |
| `expected_result` | 期望执行结果 |
| `expected_behavior` | 期望最终行为 |

## 5. Trace 结构设计

测评不能只看最终结果，还要保存 Agent 执行轨迹。

建议 Trace 至少包含：

```json
{
  "case_id": "case_order_count_001",
  "query": "统计 2025 年第一季度华东地区的订单数",
  "resolved_query": "统计 2025 年第一季度华东地区的订单数",
  "retrieval": {
    "columns": ["order_id", "region_name", "date_id"],
    "metrics": ["订单数"],
    "values": ["华东", "Q1"]
  },
  "context": {
    "tables": ["fact_order", "dim_region", "dim_date"],
    "columns": ["order_id", "region_name", "date_id"],
    "metrics": ["订单数"]
  },
  "sql": {
    "text": "SELECT COUNT(f.order_id) AS 订单数 ... LIMIT 1",
    "compliant": true,
    "retry_count": 0
  },
  "execution": {
    "final_status": "success",
    "row_count": 1,
    "latency_ms": 3200,
    "error_type": null
  },
  "result": {
    "columns": ["订单数"],
    "rows": [
      {"订单数": 44}
    ]
  }
}
```

## 6. 执行方式

### 6.1 离线测评

离线测评使用已有 Trace 文件计算指标。

适用场景：

1. 调整评测指标代码。
2. 快速生成报告。
3. 不想依赖 LLM、MySQL、Qdrant、Elasticsearch 时。

命令示例：

```powershell
.\.venv\Scripts\python.exe -m eval.runners.run_eval
```

### 6.2 真实 Agent 测评

真实测评会逐条调用 Agent，采集真实执行轨迹，再生成报告。

适用场景：

1. 验证真实链路。
2. 对比 Prompt 或 RAG 优化效果。
3. 发布前回归测试。

命令示例：

```powershell
.\.venv\Scripts\python.exe -m eval.runners.run_eval --live
```

运行真实测评前，需要确保：

1. MySQL 可用。
2. Qdrant 可用。
3. Elasticsearch 可用。
4. Embedding 服务可用。
5. LLM 配置可用。
6. 元数据知识库已经构建。

## 7. 报告设计

测评报告应分为整体汇总和失败明细。

### 7.1 整体汇总

建议输出：

```text
总用例数
端到端成功率
字段 Recall@5
指标 Recall@5
字段值 Recall@5
上下文通过率
SQL 合规率
SQL 执行成功率
结果正确率
拒答准确率
澄清准确率
变更审批正确率
平均耗时
P95 耗时
平均 SQL 修正次数
运行时错误率
```

### 7.2 失败明细

失败用例需要标记失败层。

示例：

```text
case_004 失败
失败层：retrieval
原因：未召回订单数指标

case_008 失败
失败层：result
原因：返回订单数为 40，预期为 44

case_clarify_001 失败
失败层：behavior
原因：模糊问题未触发澄清
```

失败层枚举：

| 失败层 | 含义 |
| --- | --- |
| `retrieval` | RAG 召回未命中 |
| `context` | SQL 生成上下文缺失 |
| `sql` | SQL 不合规或结构错误 |
| `execution` | SQL 执行失败 |
| `result` | 查询结果不符合预期 |
| `behavior` | 拒答、澄清、审批等行为错误 |

## 8. Baseline 对比

完整测评体系应该支持优化前后对比。

建议保留：

```text
eval/reports/baseline_query_eval_result.json
eval/reports/current_query_eval_result.json
eval/reports/query_eval_compare.md
```

对比内容：

```text
字段 Recall@5: 80.00% -> 92.00%
指标 Recall@5: 75.00% -> 90.00%
SQL 合规率: 85.00% -> 96.00%
结果正确率: 70.00% -> 88.00%
拒答准确率: 60.00% -> 90.00%
```

这样可以证明优化不是主观感觉，而是有指标提升。

## 9. 推荐目录结构

建议在现有 `eval/` 基础上扩展：

```text
eval/
  datasets/
    query_eval_cases.jsonl
    multi_turn_eval_cases.jsonl

  schemas/
    eval_case.py
    agent_trace.py
    eval_result.py

  metrics/
    retrieval_metrics.py
    context_metrics.py
    sql_metrics.py
    result_metrics.py
    behavior_metrics.py
    performance_metrics.py
    layered_report_metrics.py

  runners/
    run_eval.py
    run_rag_eval.py
    live_agent_trace.py
    compare_reports.py

  reports/
    query_eval_traces.json
    query_eval_result.json
    query_eval_report.md
    baseline_query_eval_result.json
    query_eval_compare.md
```

其中当前最需要新增的是：

```text
eval/metrics/result_metrics.py
eval/runners/compare_reports.py
```

## 10. 落地步骤

### 阶段一：扩充测评集

目标：让测评覆盖主要业务路径。

任务：

1. 将 `query_eval_cases.jsonl` 扩充到 20-30 条。
2. 覆盖基础查询、分组聚合、多指标、TopN、时间趋势、字段值召回。
3. 增加多轮追问、模糊澄清、未知领域、危险操作、变更审批。
4. 所有表、字段、指标必须来自当前项目真实 schema。

验收标准：

1. 每类场景至少 2 条用例。
2. 每条用例都有 `expected_context`、`expected_sql`、`expected_behavior`。

### 阶段二：增加结果正确性测评

目标：从“SQL 合规”升级为“业务结果正确”。

任务：

1. 在部分稳定查询中增加 `expected_result`。
2. 新增 `result_metrics.py`。
3. 支持校验返回字段、行数、关键值和排序。
4. 将结果正确率接入 `layered_report_metrics.py`。

验收标准：

1. 至少 5-8 条用例具备结果校验。
2. 报告中出现 `result_correct_rate`。
3. 结果错误时失败层标记为 `result`。

### 阶段三：完善真实 Agent Trace

目标：真实测评时能采集完整中间过程。

任务：

1. Trace 中补充 `resolved_query`。
2. Trace 中补充 `retrieval`、`context`、`sql`、`execution`、`result`。
3. 对运行时异常记录 `error_type=runtime_error`。
4. 对拒答、澄清、审批方案记录明确 `final_status`。

验收标准：

1. `run_eval --live` 能生成完整 Trace。
2. 离线测评可直接复用该 Trace。

### 阶段四：增加 Baseline 对比

目标：让优化效果可量化。

任务：

1. 保存一份 baseline 结果。
2. 新增 `compare_reports.py`。
3. 输出当前结果相对 baseline 的指标变化。

验收标准：

1. 能生成 `query_eval_compare.md`。
2. 报告能展示主要指标提升或下降。

## 11. 简历描述

实现后可以写成：

```text
设计并实现电商问数 Agent 分层测评体系，基于 JSONL 测评集和执行 Trace，从字段/指标/取值召回、上下文完整性、SQL 合规性、结果正确性、拒答/澄清行为和执行性能等维度生成测评报告，支持定位 RAG 召回、SQL 生成和安全策略问题。
```

如果只描述当前已有能力，可以写成：

```text
构建电商问数 Agent 分层测评框架，支持基于离线 Trace 和真实 Agent 执行结果评估字段/指标召回、上下文完整性、SQL 合规性、拒答/澄清行为和执行性能，为后续优化提供量化依据。
```

## 12. 总结

完整测评体系的重点不是多写几个测试用例，而是能回答三个问题：

1. 系统有没有答对？
2. 如果没答对，失败发生在哪一层？
3. 优化之后，指标有没有真实提升？

对于本项目，最推荐的建设顺序是：

```text
扩充测评集
-> 增加结果正确性校验
-> 完善真实 Agent Trace
-> 增加 baseline 对比报告
```

完成这些后，项目就可以比较稳地描述为“具备完整分层测评体系的自然语言问数 Agent”。
