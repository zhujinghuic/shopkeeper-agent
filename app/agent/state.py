"""
电商问数 Agent 状态定义

State 是 LangGraph 各节点之间传递和更新的共享数据
本章在用户原始问题之外，新增关键词列表和三路召回结果
并把召回到的实体整理成后续提示词更容易消费的表信息和指标信息
SQL 生成闭环会继续写入候选 SQL 以及校验错误信息，用于控制校正或执行分支
"""

from typing import TypedDict

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

    query: str  # 用户本轮输入的原话，例如“只看华东”
    # ===== 多轮会话相关 =====
    session_id: str  # 会话编号，一次会话内多轮共用
    history_text: str  # 服务层裁剪好的历史上下文，只有槽位不含结果集
    sql_baseline: str  # 最近一次产出 SQL 的轮次，作为增量修改的基线
    column_history: str  # 最近几轮展示过的列清单，用于跨轮引用
    rewritten_query: str  # 结合上文补全后的完整问题，后续节点都以它为准
    # 只读意图：unsupported 表示用户要删改数据或做与问数无关的事，走 reject 节点直接结束
    intent: str
    reject_reason: str  # intent 为 unsupported 时给用户看的说明
    slots: dict  # 本轮结构化槽位，落库后供下一轮继承
    missing_slots: list[dict]  # 必须澄清才能继续的槽位，非空则走澄清节点
    # ===== 单轮召回与生成 =====
    keywords: list[str]  # 抽取的关键词
    retrieved_column_infos: list[ColumnInfo]  # 检索到的字段信息
    retrieved_metric_infos: list[MetricInfo]  # 检索到的指标信息
    retrieved_value_infos: list[ValueInfo]  # 检索到的取值信息

    table_infos: list[TableInfoState]  # 合并和补齐后的表结构上下文
    metric_infos: list[MetricInfoState]  # 合并后的指标上下文
    date_info: DateInfoState  # 当前日期 星期和季度信息
    db_info: DBInfoState  # 数据库方言和版本信息

    sql: str  # 生成或校正后的SQL
    # 安全校验结论（allowed / rule / reason），通过和拦截都会写，审计表要用
    sql_guard: dict
    sql_elapsed_ms: int  # SQL 执行耗时，写入审计

    error: str  # 校验SQL时出现的错误信息


def get_effective_query(state: DataAgentState) -> str:
    """取本轮真正要用的完整问题

    多轮追问时 state["query"] 可能只有“那华东呢”，不能直接拿去分词或喂模型；
    改写节点填好 rewritten_query 之后，后续节点统一从它取值。
    """

    return state.get("rewritten_query") or state["query"]
