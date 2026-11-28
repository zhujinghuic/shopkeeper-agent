"""
`sql_audit` ORM 模型

保存每次走到执行的 SQL 的安全判定结果。与 chat_turn 分开的理由：
turn 是"用户看到的一轮问答"，audit 是"系统做过的一次安全决策"，
一次问答可能因为纠正重试留下多条 audit，两者的生命周期和查询场景都不同。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SQLAuditMySQL(Base):
    """一次 SQL 安全校验与执行结果"""

    __tablename__ = "sql_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, comment="会话编号")
    seq: Mapped[int | None] = mapped_column(Integer, comment="会话内轮次")
    # 同一条 SQL 可能先被拦、改好后再放行，两条记录靠 stage 区分
    stage: Mapped[str | None] = mapped_column(
        String(16), comment="判定阶段：intent/validate/run"
    )

    user_query: Mapped[str | None] = mapped_column(Text, comment="用户原话")
    rewritten_query: Mapped[str | None] = mapped_column(
        Text, comment="改写后的完整问题"
    )

    # 记录的是真正要执行的语句：可能已经被白名单补过 LIMIT
    sql: Mapped[str | None] = mapped_column(
        "sql_text", Text, comment="待执行或实际执行的SQL"
    )
    # 放行与否是这张表的核心字段，被拦下的行即使没有结果也有排查价值
    allowed: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否放行")
    guard_rule: Mapped[str | None] = mapped_column(String(64), comment="命中的安全规则")
    guard_reason: Mapped[str | None] = mapped_column(String(500), comment="规则说明")

    row_count: Mapped[int | None] = mapped_column(Integer, comment="结果行数")
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, comment="执行耗时毫秒")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
