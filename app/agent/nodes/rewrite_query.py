"""
追问改写节点

多轮问数的第一个节点，必须排在关键词抽取之前：像“那去年同期呢”“只看华东”
这类输入里没有任何业务名词，一旦先分词，召回会全空，后面生成 SQL 全是猜的。

本节点做三件事：
1. 结合历史把本轮问题补全成一句可独立执行的问题（standalone_query）
2. 抽结构化槽位，落库后供下一轮继承
3. 判断是否存在必须向用户澄清的缺口，有就短路到 clarify 节点，不硬生成 SQL
"""

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


class QuerySlots(BaseModel):
    """一轮问数的结构化槽位，落库后供下一轮继承"""

    tables: list[str] = Field(default_factory=list, description="涉及的表名")
    metrics: list[str] = Field(default_factory=list, description="涉及的指标名称")
    filters: list[str] = Field(default_factory=list, description="过滤条件")
    time_range: str = Field("", description="时间范围，如 2025Q1")
    granularity: str = Field("", description="统计粒度，如 按月")
    # 输出列是“结果集”维度的槽位：追加列时要把历史已有列一起写进来，
    # 否则下一轮继承到的只有新增的那两列，上一轮展示的内容会被整体覆盖
    select_columns: list[str] = Field(
        default_factory=list, description="最终要展示的列清单，追加列时需包含历史已有列"
    )


class MissingSlot(BaseModel):
    """需要向用户澄清的槽位"""

    slot: str = Field(description="缺失的槽位名称，如 time_range")
    question: str = Field(description="面向用户的一句追问")


class RewriteResult(BaseModel):
    """改写节点的结构化输出"""

    standalone_query: str = Field(description="结合上文补全后的完整问题")
    slots: QuerySlots = Field(description="本轮问题涉及的结构化槽位")
    missing_slots: list[MissingSlot] = Field(
        default_factory=list, description="必须澄清才能继续的槽位"
    )
    # 问数只读：要求删改数据、建表、导出文件的请求要在入口挡掉，
    # 否则生成 SQL 的阶段会把“删除”理解成“把这些数据查出来”，出现“看似执行成功”的假象
    intent: str = Field(
        "query",
        description="query 表示只读查询；unsupported 表示要求改数据或与问数无关",
    )
    reject_reason: str = Field(
        "", description="intent 为 unsupported 时给用户看的一句说明"
    )


async def rewrite_query(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """把本轮输入结合历史改写成完整问题，并抽出槽位"""

    writer = runtime.stream_writer
    step = "理解追问"
    writer({"type": "progress", "step": step, "status": "running"})

    query = state["query"]
    # 历史文本已经由服务层按 token 预算裁剪好，节点只负责消费
    history_text = state.get("history_text") or "无（本次会话的第一轮）"

    try:
        prompt = PromptTemplate(
            template=load_prompt("rewrite_query"),
            input_variables=["history", "query"],
        )
        # 这里用 JsonOutputParser 而不是 with_structured_output：
        # 当前接入的深度思考类模型（deepseek）不支持 response_format 和 tool_choice，
        # 走纯文本 JSON 解析兼容性最好，解析结果再用 Pydantic 校验兜底。
        chain = prompt | llm | JsonOutputParser()
        raw = await chain.ainvoke({"history": history_text, "query": query})
        # 强行转换成结构化对象
        result = RewriteResult.model_validate(raw)
    except Exception as e:
        # 改写失败不能让整次查询失败：退回原始问题，按单轮处理
        logger.warning(f"{step} failed, fallback to raw query: {e}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {
            "rewritten_query": query,
            "slots": {},
            "missing_slots": [],
            # 降级时无法判断意图，按查询处理：SQL 白名单仍然守着最后一道
            "intent": "query",
            "reject_reason": "",
        }

    standalone_query = (result.standalone_query or "").strip() or query
    slots = result.slots.model_dump()
    missing_slots = [item.model_dump() for item in result.missing_slots]

    # 只认两种意图，模型偶尔会返回别的词，按正常查询处理，避免误杀
    intent = "unsupported" if result.intent == "unsupported" else "query"
    reject_reason = (result.reject_reason or "").strip()

    logger.info(
        f"改写结果：{query} -> {standalone_query}，意图：{intent}，槽位：{slots}"
    )

    writer({"type": "progress", "step": step, "status": "success"})
    # 前端用这个事件提示“已结合上文理解为……”，避免多轮时答案看起来莫名其妙
    writer(
        {
            "type": "rewrite",
            "query": standalone_query,
            "from_history": standalone_query != query,
        }
    )

    return {
        "rewritten_query": standalone_query,
        "slots": slots,
        "missing_slots": missing_slots,
        "intent": intent,
        "reject_reason": reject_reason,
    }
