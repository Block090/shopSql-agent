# SQL 修正闭环优化方案

> 本文用于说明 shopkeeper-agent 第二阶段推荐优化方向：把当前「校验失败 -> 修正一次 -> 直接执行」改造成「校验 -> 修正 -> 再校验」的 SQL 反思闭环，并设置最大重试次数为 3。

---

## 一、为什么要做这个优化

第一阶段已经增加了 SQL 安全防护：

```text
模型生成 SQL -> SQL Guard 校验 -> 安全才允许进入数据库
```

现在系统已经可以拦截无 `LIMIT` 查询、危险 SQL、多语句 SQL 等问题。例如：

```text
生成 SQL：SELECT ... ORDER BY GMV DESC
校验 SQL：查询必须包含 LIMIT 限制
校正 SQL：SELECT ... ORDER BY GMV DESC LIMIT 10000
执行 SQL：返回结果
```

但是当前流程仍然有一个缺口：

```text
validate_sql -> correct_sql -> run_sql
```

也就是说，`correct_sql` 修正后的 SQL **没有再次经过 `validate_sql`**，而是直接进入 `run_sql`。

虽然 `run_sql` 中的 Repository 层仍然有 SQL Guard 兜底，但从 Agent 流程设计上看，这还不是完整闭环。更理想的流程应该是：

```text
生成 SQL -> 校验 SQL -> 修正 SQL -> 再校验 SQL -> 执行 SQL
```

这样才能保证每一次修正后的 SQL 都重新接受安全规则和数据库语法检查。

---

## 二、当前流程现状

当前图编排位于：

```text
app/agent/graph.py
```

核心逻辑如下：

```python
graph_builder.add_conditional_edges(
    source="validate_sql",
    path=lambda state: "run_sql" if state["error"] is None else "correct_sql",
    path_map={"run_sql": "run_sql", "correct_sql": "correct_sql"},
)
graph_builder.add_edge("correct_sql", "run_sql")
graph_builder.add_edge("run_sql", END)
```

当前流程可以表示为：

```text
generate_sql
  -> validate_sql
      -> 通过：run_sql
      -> 失败：correct_sql
  -> run_sql
```

问题点是：

- 第一次生成的 SQL 会校验；
- 修正后的 SQL 不会再次校验；
- 如果修正后的 SQL 仍然有问题，只能依赖 `run_sql` 阶段兜底；
- 前端流程图无法体现「修正后再校验」的 Agent 反思过程。

---

## 三、优化目标

本次优化目标：

1. 将 `correct_sql` 的出边从 `run_sql` 改为 `validate_sql`；
2. 在 `DataAgentState` 中增加 `retry_count` 字段；
3. 每次进入 `correct_sql` 时，让 `retry_count + 1`；
4. 最大重试次数设置为 **3 次**；
5. 超过 3 次后不再继续修正，进入失败结束节点；
6. 失败时给前端返回友好提示，而不是继续硬执行 SQL。

优化后的流程：

```text
generate_sql
  -> validate_sql
      -> 通过：run_sql
      -> 失败且 retry_count < 3：correct_sql
  -> validate_sql
      -> 通过：run_sql
      -> 失败且 retry_count < 3：correct_sql
  -> validate_sql
      -> 通过：run_sql
      -> 失败且 retry_count >= 3：fail_sql
  -> END
```

---

## 四、建议新增状态字段

修改：

```text
app/agent/state.py
```

在 `DataAgentState` 中新增：

```python
retry_count: int  # SQL 校正重试次数，用于防止修正闭环无限循环
```

含义：

- 初始值默认为 0；
- 每经过一次 `correct_sql`，加 1；
- 达到 3 后不再继续修正；
- 避免模型一直修不对导致 LangGraph 无限循环。

如果担心部分节点没有初始化该字段，可以在读取时使用：

```python
retry_count = state.get("retry_count", 0)
```

---

## 五、建议调整 correct_sql 节点

修改：

```text
app/agent/nodes/correct_sql.py
```

当前 `correct_sql` 只返回：

```python
return {"sql": result}
```

建议改为：

```python
retry_count = state.get("retry_count", 0) + 1

return {
    "sql": result,
    "retry_count": retry_count,
}
```

同时日志可以补充当前重试次数：

```python
logger.info(f"第 {retry_count} 次校正后的SQL：{result}")
```

这样后续 `validate_sql` 的条件边可以根据 `retry_count` 判断是否继续修正。

---

## 六、建议新增失败节点

建议新增文件：

```text
app/agent/nodes/fail_sql.py
```

职责：

- 当 SQL 修正超过 3 次仍然失败时，停止继续调用模型；
- 给前端写出失败状态；
- 返回友好的失败消息；
- 技术错误只留在日志中。

示例逻辑：

```python
async def fail_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    step = "SQL校正失败"
    writer({"type": "progress", "step": step, "status": "error"})
    writer({
        "type": "error",
        "message": "SQL 多次校正后仍未通过校验，请换一种问法或联系管理员。",
    })
```

这个节点不负责修 SQL，只负责优雅终止。

---

## 七、建议调整 graph.py

修改：

```text
app/agent/graph.py
```

新增节点：

```python
from app.agent.nodes.fail_sql import fail_sql

graph_builder.add_node("fail_sql", fail_sql)
```

新增路由函数：

```python
MAX_SQL_RETRY_COUNT = 3


def route_after_validate_sql(state: DataAgentState):
    if state["error"] is None:
        return "run_sql"

    retry_count = state.get("retry_count", 0)
    if retry_count >= MAX_SQL_RETRY_COUNT:
        return "fail_sql"

    return "correct_sql"
```

调整条件边：

```python
graph_builder.add_conditional_edges(
    source="validate_sql",
    path=route_after_validate_sql,
    path_map={
        "run_sql": "run_sql",
        "correct_sql": "correct_sql",
        "fail_sql": "fail_sql",
    },
)
```

关键调整：

```python
graph_builder.add_edge("correct_sql", "validate_sql")
graph_builder.add_edge("run_sql", END)
graph_builder.add_edge("fail_sql", END)
```

这样 `correct_sql` 修正后不会直接执行，而是必须再次进入 `validate_sql`。

---

## 八、为什么最大重试次数设为 3

最大重试次数设置为 3 是一个比较平衡的选择：

- 1 次太少：模型可能只是漏了 `LIMIT` 或写错一个字段，给一次修正机会不够稳；
- 3 次足够覆盖大多数简单修正；
- 超过 3 次还失败，通常说明问题不只是语法错误，可能是召回上下文不够、表结构理解错误或用户问题超出能力边界；
- 控制 LLM 调用成本，避免无限修正浪费 token；
- 防止 LangGraph 进入循环。

所以本项目建议：

```text
MAX_SQL_RETRY_COUNT = 3
```

---

## 九、前端效果预期

优化前：

```text
生成SQL -> 校验SQL -> 校正SQL -> 执行SQL
```

优化后：

```text
生成SQL -> 校验SQL -> 校正SQL -> 校验SQL -> 执行SQL
```

如果连续失败：

```text
生成SQL
-> 校验SQL
-> 校正SQL 第 1 次
-> 校验SQL
-> 校正SQL 第 2 次
-> 校验SQL
-> 校正SQL 第 3 次
-> 校验SQL
-> SQL校正失败
```

这样前端流程图会更符合 Agent 的反思闭环逻辑。

---

## 十、验证方式

### 1. 正常 SQL 一次通过

输入普通问题：

```text
统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序
```

如果模型生成的 SQL 已经带 `LIMIT`，预期：

```text
生成SQL -> 校验SQL -> 执行SQL
```

### 2. SQL 第一次失败后修正成功

如果模型第一次生成 SQL 没有 `LIMIT`，预期：

```text
生成SQL -> 校验SQL -> 校正SQL -> 校验SQL -> 执行SQL
```

日志中应该能看到：

```text
SQL语法错误：查询必须包含 LIMIT 限制
第 1 次校正后的SQL：...
SQL语法正确
SQL执行结果：...
```

### 3. 超过 3 次后失败终止

可以通过构造一个很难修正的问题，或临时让 `correct_sql` 返回固定错误 SQL 来验证。

预期：

```text
retry_count = 3
进入 fail_sql
不再执行 run_sql
前端收到友好错误提示
```

---

## 十一、面试表达

可以这样讲：

> 第一阶段我加了 SQL Guard，保证模型生成的 SQL 在执行前必须满足只读、安全、带 LIMIT 等规则。第二阶段我会继续把 SQL 修正流程改成闭环：校验失败后进入 correct_sql，但修正后的 SQL 不直接执行，而是重新进入 validate_sql。整个过程最多重试 3 次，超过上限就返回友好错误。这样既能体现 Agent 的反思重试能力，也能避免无限循环和不安全 SQL 被直接执行。

如果追问为什么要设置最大次数，可以回答：

> 因为 SQL 修正依赖大模型，如果没有上限，模型可能在错误上下文里反复生成不合法 SQL，导致 token 浪费和流程卡死。3 次是比较均衡的选择，能覆盖常见的字段名、LIMIT、语法修复，又能控制成本和风险。

---

## 十二、推荐实施顺序

1. 在 `DataAgentState` 中新增 `retry_count`；
2. 修改 `correct_sql`，每次修正后返回新的 `retry_count`；
3. 新增 `fail_sql` 节点；
4. 在 `graph.py` 中新增 `MAX_SQL_RETRY_COUNT = 3`；
5. 将 `correct_sql -> run_sql` 改为 `correct_sql -> validate_sql`；
6. 调整 `validate_sql` 的条件路由，失败时根据重试次数决定进入 `correct_sql` 或 `fail_sql`；
7. 用前端页面验证流程图是否出现「校正SQL -> 校验SQL」；
8. 用日志验证最多只修正 3 次。

