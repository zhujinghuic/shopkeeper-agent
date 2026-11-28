"""
`chat_session` ORM 模型

一条记录代表左侧会话列表里的一个会话：标题、轮次数和最后更新时间。
标题取首轮改写后的完整问题，不为它单独调一次大模型，省一次调用也更稳定。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatSessionMySQL(Base):
    """会话索引表对应的 ORM 模型"""

    __tablename__ = "chat_session"

    # 会话编号由前端生成（uuid），这里直接做主键
    session_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="会话编号"
    )
    # 左侧列表展示的标题，取首轮改写后的完整问题，超长截断
    title: Mapped[str] = mapped_column(String(120), comment="会话标题")
    turn_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="问答轮数"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    # 列表按它倒序，每问一轮更新一次
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
        comment="最后更新时间",
    )
    # 预留给后续的重命名/备注，先不参与列表展示
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")
