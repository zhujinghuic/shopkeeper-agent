"""
会话轮次业务实体

仓储层读到 ORM 模型后先转成实体，上层只面对这个对象：
服务层用它组装历史上下文，仓储层用它写库，两边都不直接依赖数据库列名。
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChatTurn:
    """一次问答记录"""

    session_id: str
    # 会话内轮次，从 1 开始
    seq: int
    # 用户原话，例如“只看华东”
    user_query: str
    # 结合上文补全后的完整问题，历史上下文里优先用它
    rewritten_query: str | None = None
    # 结构化槽位：tables / metrics / filters / time_range / granularity / select_columns
    slots: dict = field(default_factory=dict)
    # 本轮生成的 SQL：用于回放，同时作为下一轮增量修改的基线
    sql: str | None = None
    # 结果行数，同样只用于回放
    row_count: int | None = None
    # 结果集快照，切回历史会话时用来重绘表格
    result: list | None = None
    created_at: datetime | None = None
