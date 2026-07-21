"""
电商问数 Agent 状态定义

State 是 LangGraph 各节点之间传递和更新的共享数据
本章在用户原始问题之外，新增关键词列表和三路召回结果
并把召回到的实体整理成后续提示词更容易消费的表信息和指标信息
SQL 生成闭环会继续写入候选 SQL 以及校验错误信息，用于控制校正或执行分支
"""

from typing import NotRequired, TypedDict

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo


class MetricInfoState(TypedDict):
    """面向 SQL 生成提示词的指标信息"""

    name: str
    description: str
    # 指标依赖的字段 id，用来提示模型不要脱离业务口径随意计算
    relevant_columns: list[str]
    alias: list[str]


class ColumnInfoState(TypedDict):
    """表上下文中的字段信息"""

    name: str
    type: str
    role: str
    # 字段真实样例值，尤其用于辅助 where 条件里的枚举值选择
    examples: list
    description: str
    alias: list[str]


class TableInfoState(TypedDict):
    """SQL 生成阶段真正传给模型的表结构上下文"""

    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


class DateInfoState(TypedDict):
    """SQL 生成阶段使用的当前日期上下文"""

    date: str
    weekday: str
    quarter: str


class DBInfoState(TypedDict):
    """SQL 生成阶段使用的数据库环境信息"""

    dialect: str
    version: str


class DataAgentState(TypedDict):
    """一次问数链路中的核心状态"""

    query: str  # 用户输入的查询
    is_unsafe_intent: bool  # 是否命中删除 修改 写入等危险操作意图
    operation_intent: bool  # 是否进入数据变更审批链路
    operation_type: str  # DELETE UPDATE INSERT 等变更类型
    operation_plan: dict  # AI 生成的变更方案，仅用于审批展示
    impact_count: int  # 只读预览 SQL 评估出的影响行数
    impact_preview_rows: list[dict]  # 只读预览 SQL 返回的影响样例数据
    risk_level: str  # 变更风险等级
    approval_required: bool  # 是否需要提交审批
    clarification_required: bool  # 是否需要先追问确认业务口径
    clarification_question: str  # 返回给用户的业务口径追问问题
    clarification_options: list[str]  # 用户可选择的业务口径选项
    clarification_type: str  # 追问类型，用于前端展示和测评归因
    clarification_missing_slots: list[str]  # 需要用户补充的业务槽位
    keywords: list[str]  # 抽取的关键词
    semantic_slots: dict  # 上下文改写后的语义槽位，用于增强 RAG 召回和重排
    retrieved_column_infos: list[ColumnInfo]  # 检索到的字段信息
    retrieved_metric_infos: list[MetricInfo]  # 检索到的指标信息
    retrieved_value_infos: list[ValueInfo]  # 检索到的取值信息
    similar_query_cases: list[dict]  # 召回到的历史成功 Query Case 压缩结果
    recall_decision: dict  # 领域覆盖检查结果，决定是否允许进入 SQL 生成

    table_infos: list[TableInfoState]  # 合并和补齐后的表结构上下文
    metric_infos: list[MetricInfoState]  # 合并后的指标上下文
    date_info: DateInfoState  # 当前日期 星期和季度信息
    db_info: DBInfoState  # 数据库方言和版本信息

    sql: str  # 生成或校正后的SQL

    error: str  # 校验SQL时出现的错误信息
    retry_count: int  # SQL 校正重试次数，用于防止修正闭环无限循环
    permission_context: NotRequired[dict]
    permission_error: NotRequired[str | None]
