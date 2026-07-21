# LLM 上下文改写与语义槽位升级方案

> **目标：** 将当前基于规则的多轮上下文改写升级为“规则预判 + LLM 结构化理解 + 元数据校验与澄清兜底”的三层架构。让系统既能理解复杂追问，又能保持企业级数据系统需要的稳定性、可审计性和可测评性。

## 一、当前问题

当前系统已经支持查询历史、多轮上下文和“系统理解”展示，但上下文改写主要依赖规则。

规则版对简单追问有效：

```text
那华东地区呢
换成订单数呢
```

但对复杂追问容易出错：

```text
上一轮：统计 2025 年 3 月各商品品类的销量和销售额
当前轮：那各大区的 GMV 排序呢
```

正确理解应该是：

```text
统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序
```

但规则版可能错误理解为：

```text
统计 2025 年 3 月各商品品类的 GMV 和 GMV
```

根因是当前改写逻辑只能做局部字符串替换，无法稳定识别“继承时间、覆盖维度、覆盖指标、新增排序”这种组合语义。

## 二、设计原则

本方案不建议简单地“把规则全部换成大模型”。更合理的企业级方案是：

```text
大模型负责语义理解
规则负责预判和兜底
系统负责校验和安全控制
```

原因：

1. 大模型更擅长理解复杂追问。
2. 规则更适合做确定性预判和低成本过滤。
3. 元数据校验可以防止大模型编造不存在的表、字段、指标或维度。
4. 结构化输出方便审计、前端展示和自动化测评。

## 三、目标能力

升级完成后，系统应具备以下能力：

1. 能识别用户是否在进行追问。
2. 能从历史问题中抽取并继承语义槽位。
3. 能识别当前问题覆盖了哪些槽位。
4. 能生成结构化的 `resolved_query`。
5. 能输出 `context_trace`，解释系统为什么这样理解。
6. 能对 LLM 输出进行元数据校验。
7. 低置信度或校验失败时不强行执行，而是进入澄清。
8. 能被 RAG/Agent 测评模块单独评估改写准确率。

## 四、总体架构

推荐采用三层上下文理解架构：

```text
用户问题
  |
  v
第一层：规则预判
  |
  |-- 不是追问 --> 正常 RAG/SQL 流程
  |
  |-- 可能是追问
        |
        v
第二层：LLM 结构化改写
        |
        v
第三层：元数据校验与澄清兜底
        |
        |-- 校验通过且高置信度 --> 进入 SQL 生成
        |
        |-- 校验失败或低置信度 --> 返回澄清问题
```

## 五、第一层：规则预判

规则预判不负责最终改写，只判断当前问题是否可能是追问。

### 1. 追问示例

```text
那华东呢
那各大区呢
换成 3 月呢
按会员等级看呢
那 GMV 排序呢
再看销售额
```

### 2. 非追问示例

```text
统计 2025 年 3 月各商品品类的销量和销售额
查询华东地区 2025 年第一季度销售额最高的前 5 个商品
按会员等级统计 2025 年第一季度的订单数和销售额
```

### 3. 规则预判输出

```json
{
  "maybe_follow_up": true,
  "reason": "问题较短，包含追问提示词，并引用上一轮上下文"
}
```

如果 `maybe_follow_up=false`，则不进入 LLM 改写，直接走正常 RAG/SQL 流程。

## 六、第二层：LLM 结构化改写

当规则判断当前问题可能是追问时，调用 LLM 进行结构化上下文理解。

### 1. LLM 输入

LLM 不应该只看到当前问题，还应该看到：

1. 当前用户问题。
2. 最近 N 轮历史问题。
3. 最近 N 轮的 `semantic_slots`。
4. 可用指标列表。
5. 可用维度列表。
6. 可用时间口径说明。
7. 改写约束。

示例输入信息：

```json
{
  "current_query": "那各大区的 GMV 排序呢",
  "recent_turns": [
    {
      "query": "统计 2025 年 3 月各商品品类的销量和销售额",
      "resolved_query": "统计 2025 年 3 月各商品品类的销量和销售额",
      "semantic_slots": {
        "time_range": "2025 年 3 月",
        "dimension": "商品品类",
        "metrics": ["销量", "销售额"],
        "filters": {},
        "sort": null
      }
    }
  ],
  "available_dimensions": ["大区", "商品品类", "商品", "会员等级", "日期"],
  "available_metrics": ["GMV", "销售额", "销量", "订单数"],
  "constraints": [
    "只能输出 JSON",
    "不能编造不存在的维度和指标",
    "如果不确定必须设置 needs_clarification=true"
  ]
}
```

### 2. LLM 输出

LLM 必须输出结构化 JSON，不允许输出自由文本。

推荐格式：

```json
{
  "is_follow_up": true,
  "resolved_query": "统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序",
  "semantic_slots": {
    "time_range": "2025 年 3 月",
    "dimension": "大区",
    "metrics": ["GMV"],
    "filters": {},
    "sort": {
      "field": "GMV",
      "direction": "desc"
    }
  },
  "inherited_context": {
    "time_range": "2025 年 3 月"
  },
  "overwritten_context": {
    "dimension": "大区",
    "metrics": ["GMV"],
    "sort": "GMV 从高到低"
  },
  "needs_clarification": false,
  "clarification_question": "",
  "confidence": 0.92,
  "rewrite_method": "llm"
}
```

### 3. 低置信度输出

如果 LLM 不确定用户意图，应输出：

```json
{
  "is_follow_up": true,
  "resolved_query": "",
  "semantic_slots": {},
  "inherited_context": {},
  "overwritten_context": {},
  "needs_clarification": true,
  "clarification_question": "你是想按大区统计 2025 年 3 月 GMV，并按 GMV 从高到低排序吗？",
  "confidence": 0.56,
  "rewrite_method": "llm"
}
```

系统看到 `needs_clarification=true` 后，不进入 SQL 生成，而是返回澄清事件。

## 七、第三层：元数据校验与澄清兜底

LLM 输出后，后端不能直接信任，需要做校验。

### 1. 校验内容

| 校验项 | 说明 |
| --- | --- |
| 维度校验 | `dimension` 必须属于可用维度 |
| 指标校验 | `metrics` 必须属于可用指标 |
| 排序校验 | `sort.field` 必须是当前指标或合法字段 |
| 时间校验 | `time_range` 必须能被系统解析 |
| 字段范围校验 | 不允许引入知识库不存在的字段 |
| 置信度校验 | `confidence` 低于阈值时不能直接执行 |
| 安全校验 | 写操作仍然必须走审批计划，不允许直接执行 |

### 2. 置信度策略

建议阈值：

| confidence | 行为 |
| ---: | --- |
| `>= 0.8` | 校验通过后直接执行 |
| `0.5 - 0.8` | 返回澄清确认 |
| `< 0.5` | 不改写，提示用户补充问题 |

### 3. 校验失败示例

如果 LLM 输出：

```json
{
  "dimension": "主播",
  "metrics": ["直播间转化率"]
}
```

但当前电商数据知识库中没有“主播”和“直播间转化率”，系统必须拒绝进入 SQL 生成，返回：

```text
当前数据知识库中没有找到“主播”或“直播间转化率”相关信息，无法可靠回答该问题。
```

## 八、语义槽位设计

为了让上下文继承更稳定，不能只保存自然语言 `resolved_query`，还应保存结构化语义槽位 `semantic_slots`。

### 1. 槽位结构

```json
{
  "time_range": "2025 年 3 月",
  "dimension": "商品品类",
  "metrics": ["销量", "销售额"],
  "filters": {
    "region": "华东"
  },
  "sort": {
    "field": "销售额",
    "direction": "desc"
  },
  "limit": 10
}
```

### 2. 槽位继承示例

上一轮：

```json
{
  "time_range": "2025 年 3 月",
  "dimension": "商品品类",
  "metrics": ["销量", "销售额"],
  "filters": {},
  "sort": null
}
```

当前问题：

```text
那各大区的 GMV 排序呢
```

更新后：

```json
{
  "time_range": "2025 年 3 月",
  "dimension": "大区",
  "metrics": ["GMV"],
  "filters": {},
  "sort": {
    "field": "GMV",
    "direction": "desc"
  }
}
```

## 九、数据表改造

建议在 `query_history` 表中增加字段：

```sql
semantic_slots JSON NULL COMMENT '结构化语义槽位，用于多轮上下文继承',
rewrite_confidence DECIMAL(5,4) NULL COMMENT '上下文改写置信度'
```

已有字段 `context_trace` 继续保留，用于前端展示和审计。

三者关系：

| 字段 | 作用 |
| --- | --- |
| `resolved_query` | 最终给 Agent 执行的自然语言问题 |
| `semantic_slots` | 结构化上下文状态 |
| `context_trace` | 展示系统如何理解和改写 |

## 十、后端模块设计

建议将当前 `query_rewriter` 拆成更清晰的组件。

```text
app/core/context_rewrite/
  follow_up_detector.py
  llm_rewriter.py
  rewrite_validator.py
  semantic_slots.py
  schemas.py
```

### 1. `follow_up_detector.py`

职责：

1. 判断当前问题是否可能是追问。
2. 对明显完整的问题直接返回 `maybe_follow_up=false`。
3. 降低 LLM 调用成本。

### 2. `llm_rewriter.py`

职责：

1. 组装 LLM prompt。
2. 调用大模型。
3. 解析 JSON。
4. 输出 `RewriteResult`。

### 3. `rewrite_validator.py`

职责：

1. 校验维度、指标、时间、排序是否合法。
2. 校验置信度。
3. 决定是否进入 SQL 生成或澄清。

### 4. `semantic_slots.py`

职责：

1. 定义槽位合并规则。
2. 从历史记录中读取上一轮槽位。
3. 将新槽位保存到历史。

### 5. `schemas.py`

职责：

定义统一数据结构：

```python
@dataclass
class SemanticSlots:
    time_range: str | None
    dimension: str | None
    metrics: list[str]
    filters: dict
    sort: dict | None
    limit: int | None


@dataclass
class RewriteResult:
    is_follow_up: bool
    resolved_query: str
    semantic_slots: SemanticSlots
    inherited_context: dict
    overwritten_context: dict
    needs_clarification: bool
    clarification_question: str
    confidence: float
    rewrite_method: str
```

## 十一、前端展示设计

当前已经有“系统理解”展示卡片，后续需要扩展展示内容。

推荐展示：

```text
系统理解
原问题：那各大区的 GMV 排序呢
实际查询：统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序

继承：时间=2025 年 3 月
变更：维度=大区，指标=GMV，排序=GMV 从高到低
置信度：92%
```

如果需要澄清：

```text
我理解你是想按大区统计 2025 年 3 月 GMV，并按 GMV 从高到低排序，对吗？

[确认] [重新描述]
```

第一版可以先只展示澄清问题，不一定实现确认按钮；用户直接重新输入即可。

## 十二、Prompt 设计

LLM prompt 必须强调结构化输出和约束。

示例：

```text
你是电商数据分析 Agent 的上下文改写模块。

你的任务：
1. 判断当前问题是否是对历史问题的追问。
2. 如果是追问，结合最近历史和语义槽位，生成完整问题。
3. 只允许使用给定的指标和维度。
4. 如果不确定，必须设置 needs_clarification=true。
5. 只能输出 JSON，不能输出解释文字。

可用指标：
- GMV
- 销售额
- 销量
- 订单数

可用维度：
- 大区
- 商品品类
- 商品
- 会员等级
- 日期

最近一轮语义槽位：
{semantic_slots}

当前用户问题：
{current_query}

请输出 JSON：
{
  "is_follow_up": boolean,
  "resolved_query": string,
  "semantic_slots": object,
  "inherited_context": object,
  "overwritten_context": object,
  "needs_clarification": boolean,
  "clarification_question": string,
  "confidence": number,
  "rewrite_method": "llm"
}
```

## 十三、测评设计

需要为上下文改写单独建立测评集。

### 1. 单轮到多轮链路用例

| 轮次 | 用户问题 | 期望 resolved_query |
| --- | --- | --- |
| 1 | 统计 2025 年 3 月各商品品类的销量和销售额 | 统计 2025 年 3 月各商品品类的销量和销售额 |
| 2 | 那各大区的 GMV 排序呢 | 统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序 |
| 3 | 换成华东地区 | 统计 2025 年 3 月华东地区的 GMV，并按 GMV 从高到低排序 |
| 4 | 按商品看 | 统计 2025 年 3 月华东地区各商品的 GMV，并按 GMV 从高到低排序 |

### 2. 测评指标

| 指标 | 含义 |
| --- | --- |
| `rewrite_success_rate` | `resolved_query` 是否符合预期 |
| `slot_inherit_accuracy` | 应继承槽位是否正确保留 |
| `slot_override_accuracy` | 应覆盖槽位是否正确替换 |
| `clarification_accuracy` | 不确定问题是否正确澄清 |
| `metadata_validation_accuracy` | 非法字段/指标是否被拦截 |
| `unnecessary_rewrite_rate` | 完整问题是否被错误改写 |

## 十四、实施顺序

建议分阶段实现，避免一次改动过大。

### 第一阶段：槽位结构落地

1. 定义 `SemanticSlots` 和 `RewriteResult`。
2. 扩展 `query_history`，保存 `semantic_slots` 和 `rewrite_confidence`。
3. 当前规则版 `query_rewriter` 先输出基础槽位。
4. 前端“系统理解”展示槽位和置信度。

### 第二阶段：LLM 结构化改写

1. 新增 `llm_rewriter.py`。
2. 组装最近历史、槽位、可用指标、可用维度。
3. 调用 LLM 输出 JSON。
4. 增加 JSON 解析和异常兜底。

### 第三阶段：元数据校验

1. 新增 `rewrite_validator.py`。
2. 校验指标、维度、排序、时间。
3. 根据置信度决定执行或澄清。

### 第四阶段：测评升级

1. 增加多轮上下文改写测评集。
2. 增加槽位继承/覆盖指标。
3. 将测评结果写入 RAG 测评报告。

## 十五、验收标准

本方案完成后，需要满足：

1. “那各大区的 GMV 排序呢”能正确理解为按大区统计 GMV 并排序。
2. 系统能继承上一轮时间范围。
3. 系统能覆盖上一轮维度和指标。
4. 系统能保存并展示 `semantic_slots`。
5. LLM 输出必须是结构化 JSON。
6. 不存在的指标或维度不能进入 SQL 生成。
7. 低置信度问题必须进入澄清。
8. 测评报告能单独统计上下文改写准确率。

## 十六、风险与控制

| 风险 | 控制方式 |
| --- | --- |
| LLM 编造字段 | 元数据校验 |
| LLM 输出非 JSON | JSON 解析失败后走规则兜底或澄清 |
| 改写不稳定 | 增加测评集和置信度阈值 |
| 成本增加 | 规则预判过滤完整问题 |
| 用户不信任改写 | 前端展示“系统理解”和置信度 |
| 上下文串会话 | 继续按 `session_id` 隔离历史 |

## 十七、真实 LLM 自动判断接入主流程

当前第一版已经落地了语义槽位、置信度、规则覆盖和 LLM JSON 校验接口。下一步需要把 `llm_rewriter` 从“解析/校验模块”升级为“真实调用大模型的上下文改写器”，并接入 `QueryService` 主流程。

### 1. 新增真实 LLM 改写函数

文件：

```text
app/core/context_rewrite/llm_rewriter.py
```

建议新增异步函数：

```python
async def rewrite_with_llm(
    current_query: str,
    recent_turns: list[dict],
    available_dimensions: list[str],
    available_metrics: list[str],
) -> RewriteResult:
    """调用大模型进行结构化上下文改写。"""
```

职责：

1. 组装上下文改写 prompt。
2. 调用 `app.agent.llm.llm`。
3. 获取模型输出文本。
4. 解析 JSON。
5. 校验 JSON 中的维度、指标、排序、置信度。
6. 返回统一 `RewriteResult`。

### 2. Prompt 必须强制 JSON 输出

大模型不能自由回答，只能输出 JSON。

输出格式：

```json
{
  "is_follow_up": true,
  "resolved_query": "统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序",
  "semantic_slots": {
    "time_range": "2025 年 3 月",
    "dimension": "大区",
    "metrics": ["GMV"],
    "filters": {},
    "sort": {
      "field": "GMV",
      "direction": "desc"
    },
    "limit": null
  },
  "inherited_context": {
    "time_range": "2025 年 3 月"
  },
  "overwritten_context": {
    "dimension": "大区",
    "metrics": ["GMV"],
    "sort": "GMV 从高到低"
  },
  "needs_clarification": false,
  "clarification_question": "",
  "confidence": 0.92,
  "rewrite_method": "llm"
}
```

如果模型无法确定，应输出：

```json
{
  "is_follow_up": true,
  "resolved_query": "",
  "semantic_slots": {},
  "inherited_context": {},
  "overwritten_context": {},
  "needs_clarification": true,
  "clarification_question": "你是想按大区统计 2025 年 3 月 GMV，并按 GMV 从高到低排序吗？",
  "confidence": 0.62,
  "rewrite_method": "llm"
}
```

### 3. QueryService 主流程接入方式

当前主流程类似：

```python
rewrite_result = rewrite_query_with_trace(query, recent_turns)
```

升级后应改成：

```python
rewrite_result = await rewrite_query_with_llm_or_rule(query, recent_turns)
```

推荐分流逻辑：

```text
1. 规则预判当前问题是否可能是追问。
2. 如果不是追问，不调用 LLM，直接使用原问题。
3. 如果是追问，优先调用 LLM 结构化改写。
4. LLM 输出合法且 confidence >= 0.8，使用 LLM 的 resolved_query。
5. LLM 输出非法 JSON，走规则兜底或澄清。
6. LLM 输出非法维度/指标，返回澄清或拒答。
7. LLM 输出 needs_clarification=true，直接返回澄清事件，不进入 SQL 生成。
```

整体流程：

```text
用户问题
  |
  v
读取最近历史 + semantic_slots
  |
  v
规则预判是否追问
  |
  |-- 否 --> 原问题进入 Agent
  |
  |-- 是 --> LLM 结构化改写
               |
               |-- 合法 + 高置信度 --> resolved_query 进入 Agent
               |
               |-- 不确定/非法 --> 返回澄清
```

### 4. 澄清兜底

如果 LLM 输出：

```json
{
  "needs_clarification": true,
  "clarification_question": "你是想按大区统计 2025 年 3 月 GMV，并按 GMV 从高到低排序吗？",
  "confidence": 0.62
}
```

后端不应继续进入 SQL 生成，而应通过 SSE 返回：

```json
{
  "type": "clarification",
  "message": "你是想按大区统计 2025 年 3 月 GMV，并按 GMV 从高到低排序吗？",
  "options": ["是，按这个查询", "不是，我重新描述"],
  "clarification_type": "context_rewrite"
}
```

前端可以复用现有澄清卡片展示。

### 5. LLM 失败时的兜底策略

LLM 调用失败时，不能让整个查询直接失败。

建议策略：

| 场景 | 处理方式 |
| --- | --- |
| LLM 超时 | 使用规则版 `rewrite_query_with_trace()` 兜底 |
| LLM 返回非 JSON | 使用规则版兜底，记录日志 |
| LLM 返回低置信度 | 返回澄清 |
| LLM 编造非法维度/指标 | 拦截并返回澄清或拒答 |
| 规则也无法改写 | 不强行改写，要求用户补充 |

### 6. 需要补充的测试

接入真实 LLM 主流程前后，至少补充以下测试：

1. 完整问题不调用 LLM。
2. 复杂追问会调用 LLM。
3. LLM 返回合法 JSON 时，使用 LLM 的 `resolved_query`。
4. LLM 返回非法 JSON 时，走规则兜底或澄清。
5. LLM 返回低置信度时，返回澄清事件。
6. LLM 编造非法维度/指标时，被元数据校验拦截。
7. LLM 调用异常时，不影响系统返回可理解错误或规则兜底结果。

### 7. 完成标准

真实 LLM 接入完成后，需要满足：

1. `QueryService` 主流程会在追问场景调用 LLM 改写器。
2. LLM 输出必须经过 JSON 解析和元数据校验。
3. 高置信度合法结果才允许进入 SQL 生成。
4. 低置信度或校验失败必须进入澄清。
5. 前端“系统理解”显示 `rewrite_method=llm`、置信度、继承槽位和覆盖槽位。
6. 测试能证明完整问题不会额外调用 LLM，避免不必要成本。

## 十八、最终效果

升级后，系统面对以下连续问题：

```text
统计 2025 年 3 月各商品品类的销量和销售额
那各大区的 GMV 排序呢
```

应展示：

```text
系统理解
原问题：那各大区的 GMV 排序呢
实际查询：统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序
继承：时间=2025 年 3 月
变更：维度=大区，指标=GMV，排序=GMV 从高到低
置信度：92%
```

并返回：

```text
大区 | GMV
华东 | ...
华北 | ...
华南 | ...
```

这时项目会从“规则驱动的多轮问数工具”升级为“LLM 结构化理解 + 规则校验 + 可解释上下文”的企业级数据分析 Agent。
