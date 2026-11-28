"""
会话接口 Schema

集中声明会话列表与历史详情的数据结构，路由层只负责组装和返回。
"""

from datetime import datetime

from pydantic import BaseModel


class SessionSummarySchema(BaseModel):
    """会话列表中的一项"""

    session_id: str
    title: str
    turn_count: int
    updated_at: datetime | None = None


class SessionMessageSchema(BaseModel):
    """历史会话里的一条消息，用户和助手共用"""

    role: str
    content: str
    # 只有助手消息才有下面这几个字段
    sql: str | None = None
    result: list | None = None
    row_count: int | None = None
    clarify: bool = False
    # 超出只读范围的请求（删除、更新、导出等），回放时按拒绝提示展示
    rejected: bool = False
    created_at: datetime | None = None


class SessionDetailSchema(BaseModel):
    """某个会话的完整历史"""

    session_id: str
    title: str
    messages: list[SessionMessageSchema]
