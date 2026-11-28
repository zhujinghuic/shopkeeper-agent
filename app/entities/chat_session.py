"""
会话索引业务实体

左侧会话列表只依赖这一层数据：标题、轮数、更新时间，
不需要把每一轮问答都读出来。
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatSession:
    """一个会话的概要信息"""

    session_id: str
    title: str
    # 会话内已有多少轮问答
    turn_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
