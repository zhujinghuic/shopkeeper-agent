"""
`chat_turn` ORM 模型

保存多轮问数的一次问答记录。落库存的是“全量档案”：
用户原话、改写后的完整问题、结构化槽位、生成过的 SQL 和结果行数都会留下，
目的是回放和检索式回捞。

注意：落库 ≠ 全量进提示词。常规历史上下文只喂 `slots` 这一层小对象，
结果集不进上下文；唯一例外是最近一次产出 SQL 的那一轮，
它的 SQL 会作为“本轮增量修改的基线”单独注入生成节点，避免追问加列时被重写成全新查询。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base


class ChatTurnMySQL(Base):
    """一次问答记录对应的 ORM 模型"""

    __tablename__ = "chat_turn"

    # 自增主键只做数据库层面的唯一标识，业务上真正区分轮次用的是 session_id + seq
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, comment="会话编号")
    # seq 是会话内的轮次，从 1 开始，历史上下文按它排序
    seq: Mapped[int] = mapped_column(Integer, comment="会话内轮次")

    user_query: Mapped[str] = mapped_column(Text, comment="用户原话")
    # 结合上文补全后的完整问题，例如“只看华东” -> “统计2025Q1华东各大区GMV”
    rewritten_query: Mapped[str | None] = mapped_column(
        Text, comment="改写后的完整问题"
    )
    # 结构化槽位：表、指标、过滤条件、时间范围、统计粒度、展示列
    slots: Mapped[dict | None] = mapped_column(JSON, comment="结构化槽位")

    # 列名用 sql_text，避免和关键字混淆；实体里仍然叫 sql
    sql: Mapped[str | None] = mapped_column("sql_text", Text, comment="本轮生成的SQL")
    row_count: Mapped[int | None] = mapped_column(Integer, comment="结果行数")
    # 结果集快照：切回某个会话时要能重新把表格画出来，所以落一份（有上限）
    result: Mapped[list | None] = mapped_column(JSON, comment="结果集快照")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
