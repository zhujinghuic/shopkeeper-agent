"""
SQL 审计业务实体

服务层只面对这个对象：写入时不需要知道库表列名，读取时也不依赖 ORM。
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SQLAudit:
    """一次 SQL 安全校验 + 执行的审计记录"""

    session_id: str
    seq: int | None = None
    user_query: str | None = None
    rewritten_query: str | None = None
    sql: str | None = None
    # 是否放行：被拦截的记录同样要落库，那是排查越权尝试的主要线索
    allowed: bool = True
    guard_rule: str | None = None
    guard_reason: str | None = None
    row_count: int | None = None
    elapsed_ms: int | None = None
    created_at: datetime | None = None
