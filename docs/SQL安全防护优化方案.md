# SQL 安全防护优化方案

> 本文用于说明 shopkeeper-agent 第一阶段推荐优先优化的方向：为模型生成的 SQL 增加安全防护，避免大模型生成的 SQL 被直接执行。

---

## 一、为什么先优化 SQL 安全

当前项目的问数链路是：

```text
用户问题 -> 召回字段/指标/取值 -> 生成 SQL -> 校验 SQL -> 执行 SQL -> 返回结果
```

其中最终执行 SQL 的逻辑位于：

```text
app/agent/nodes/run_sql.py
app/repositories/mysql/dw/dw_mysql_repository.py
```

当前实现中，模型生成的 SQL 会直接交给数仓执行：

```python
result = await dw_mysql_repository.run(sql)
```

这对 Demo 项目来说可以跑通链路，但如果要往工程化或生产化方向优化，就存在明显风险：

- 模型可能生成 `DELETE`、`UPDATE`、`DROP` 等危险语句；
- 模型可能生成没有 `LIMIT` 的大查询，导致全表扫描；
- 缺少 SQL 审计与统一校验入口；
- 如果数据库账号权限过大，代码层漏防护时可能直接影响数据。

所以第一阶段应该先补安全防护，但不能只看最终 SQL。更完整的设计应该分成两层：

1. 在 SQL 生成前识别用户意图，发现删除、修改、写入、建表等危险操作时，直接拒绝或进入人工审查；
2. 在 SQL 执行前增加 SQL Guard，保证所有真正进入数据库的 SQL 都必须通过安全校验。

---

## 二、优化目标

第一版目标不追求复杂 SQL 解析，而是先建立最小可用的安全边界：

1. 在生成 SQL 之前识别危险操作意图；
2. 对删除、修改、写入、建表等请求直接拒绝，不能自动改写成 `SELECT`；
3. 只允许执行单条 `SELECT` 查询；
4. 禁止危险 SQL 关键字；
5. 禁止多语句执行；
6. 要求查询带有 `LIMIT`，避免无限制大查询；
7. 在 `validate()` 和 `run()` 两个入口都做校验；
8. 数据库连接尽量使用只读账号兜底。

---

## 三、补充优化：危险操作意图识别

用户明确要求“删除订单”“修改商品价格”“清空数据”“插入一条记录”时，这类请求本身已经不是问数分析需求。

当前项目定位是电商数据问答，只支持只读分析，所以不能把危险写操作意图转换成一条看似安全的 `SELECT`。正确行为应该是：

```text
用户危险操作请求 -> 命中意图安全检查 -> 直接拒绝回答 -> 不进入生成 SQL 节点
```

建议在 LangGraph 中增加一个前置节点：

```text
START -> check_query_intent -> extract_keywords -> ...
                         |
                         -> reject_unsafe_intent -> END
```

第一版可以先使用关键词规则识别，覆盖常见危险表达：

```python
UNSAFE_INTENT_KEYWORDS = {
    "删除",
    "删掉",
    "清空",
    "修改",
    "更新",
    "插入",
    "新增",
    "写入",
    "delete",
    "update",
    "insert",
    "drop",
    "truncate",
    "alter",
}
```

命中后返回明确提示：

```text
当前系统仅支持只读数据分析，不能执行删除、修改、插入、清空等写操作。
```

如果未来系统真的要支持写操作，也不能让 Agent 直接执行。必须增加权限校验、影响范围预览、二次确认、审计日志，必要时还要接入人工审批。对于当前项目，第一阶段建议直接拒绝危险写操作意图。

---

## 四、建议新增 SQL Guard

建议新增文件：

```text
app/core/sql_guard.py
```

示例实现：

```python
import re


DANGEROUS_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "replace",
    "grant",
    "revoke",
}


def normalize_sql(sql: str) -> str:
    return sql.strip().lower()


def validate_readonly_sql(sql: str) -> None:
    normalized = normalize_sql(sql)

    if not normalized:
        raise ValueError("SQL 不能为空")

    if not normalized.startswith("select"):
        raise ValueError("只允许执行 SELECT 查询语句")

    if ";" in normalized.rstrip(";"):
        raise ValueError("不允许执行多条 SQL")

    for keyword in DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized):
            raise ValueError(f"SQL 包含危险关键字: {keyword}")

    if not re.search(r"\blimit\b", normalized):
        raise ValueError("查询必须包含 LIMIT 限制")
```

这是一版轻量实现，优点是改动小、容易理解、适合第一阶段落地。

---

## 五、接入位置

### 1. 在 SQL 校验前接入

修改：

```text
app/repositories/mysql/dw/dw_mysql_repository.py
```

在文件顶部引入：

```python
from app.core.sql_guard import validate_readonly_sql
```

修改 `validate()`：

```python
async def validate(self, sql: str):
    """用 EXPLAIN 让数据库提前解析 SQL，发现语法 表名 字段名等错误"""
    validate_readonly_sql(sql)
    sql = f"explain {sql}"
    await self.session.execute(text(sql))
```

这样危险 SQL 不会进入 `EXPLAIN` 阶段。

### 2. 在 SQL 执行前接入

继续修改 `run()`：

```python
async def run(self, sql: str) -> list[dict]:
    """执行最终 SQL，并把 SQLAlchemy 行对象转换成前端更易消费的字典列表"""
    validate_readonly_sql(sql)
    result = await self.session.execute(text(sql))
    return [dict(row) for row in result.mappings().fetchall()]
```

这样无论未来哪个节点调用 `DWMySQLRepository.run()`，都会统一经过安全校验。

---

## 六、为什么放在 Repository 层

SQL 安全校验可以放在 `run_sql` 节点，也可以放在 `DWMySQLRepository` 层。

更推荐放在 Repository 层，原因是：

- Repository 是真正接触数据库执行的最后入口；
- 可以避免其他地方绕过 `run_sql` 直接调用 `run()`；
- 和数据库访问逻辑放在一起，职责更集中；
- 后续如果增加审计日志、超时控制、只读策略，也更容易统一维护。

`run_sql` 节点仍然可以负责用户提示和流程状态，Repository 负责安全边界。

---

## 七、LIMIT 策略说明

第一版可以选择“没有 `LIMIT` 就拒绝执行”，而不是自动追加。

原因是自动拼接 `LIMIT` 存在边界：

- SQL 可能已经有 `LIMIT`；
- SQL 可能包含子查询；
- SQL 可能包含 CTE；
- SQL 可能是聚合查询；
- 简单字符串拼接容易破坏 SQL 结构。

所以第一阶段建议先保守处理：

```text
没有 LIMIT -> 拒绝执行 -> 让模型重新生成带 LIMIT 的 SQL
```

后续如果要做得更完善，可以引入 SQL parser，再做自动补全或重写。

---

## 八、数据库只读账号兜底

代码层防护不是最后一道防线，数据库权限也要配合。

建议为数仓查询配置只读账号，只授予：

```sql
SELECT
SHOW VIEW
```

不要授予：

```sql
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
```

这样即使代码层出现遗漏，数据库本身也能挡住写操作。

---

## 九、后续可升级方向

第一版 SQL Guard 落地后，可以继续优化：

1. 引入 SQL parser，替代简单字符串判断；
2. 对查询增加最大返回行数；
3. 设置数据库查询超时；
4. 记录 SQL 审计日志；
5. 对不同用户角色增加表级、字段级权限；
6. 对语法错误、缺少 `LIMIT` 等可修正问题进入 `correct_sql` 重新生成；
7. 对用户主动提出的删除、修改、写入等危险意图，不进入 `correct_sql` 改写成 `SELECT`，而是直接拒绝或进入二次审查确认。

---

## 十、面试表达

可以这样讲：

> 这个项目最先需要优化的是 SQL 安全防护。当前模型生成的 SQL 会直接进入数仓执行，作为 Demo 可以接受，但生产化风险很高。我会做两层防护：第一层在 SQL 生成前识别用户意图，如果用户要求删除、修改、写入数据，直接拒绝或进入二次审查，不能把它改写成 SELECT；第二层在 DW Repository 层增加统一 SQL Guard，只允许单条 SELECT 查询，禁止 DDL/DML 危险关键字，并要求 LIMIT 限制。同时数据库账号使用只读权限兜底。这样可以把大模型生成 SQL 的不可控风险控制在执行前。

如果继续追问为什么放在 Repository 层，可以回答：

> 因为 Repository 是最终访问数据库的统一入口。把安全校验放在这里，可以保证无论上层哪个节点触发查询，都必须经过同一套防护逻辑，比只放在某个 Agent 节点里更稳。

---

## 十一、推荐实施顺序

1. 新增危险操作意图识别逻辑，例如 `check_query_intent` 节点；
2. 命中删除、修改、写入等危险意图时，直接返回拒答提示；
3. 新增 `app/core/sql_guard.py`；
4. 为危险意图识别和 `validate_readonly_sql()` 补基础单元测试；
5. 在 `DWMySQLRepository.validate()` 中接入 SQL Guard；
6. 在 `DWMySQLRepository.run()` 中接入 SQL Guard；
7. 手动验证正常 `SELECT ... LIMIT ...` 可以执行；
8. 手动验证 `DELETE`、`UPDATE`、多语句、无 `LIMIT` 查询会被拦截；
9. 再考虑接入 SQL 修正闭环，但只修正可安全修复的问题，不把危险写操作意图改写成查询。
