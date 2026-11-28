"""
SQLAudit 映射器

字段差异（实体里叫 sql，库里是 sql_text）只在这一层处理。
"""

from app.entities.sql_audit import SQLAudit
from app.models.sql_audit import SQLAuditMySQL


class SQLAuditMapper:
    """负责 `SQLAudit` 与 `SQLAuditMySQL` 之间的双向转换"""

    @staticmethod
    def to_entity(model: SQLAuditMySQL) -> SQLAudit:
        """把 ORM 模型转换回审计实体"""

        return SQLAudit(
            session_id=model.session_id,
            seq=model.seq,
            user_query=model.user_query,
            rewritten_query=model.rewritten_query,
            sql=model.sql,
            allowed=bool(model.allowed),
            guard_rule=model.guard_rule,
            guard_reason=model.guard_reason,
            row_count=model.row_count,
            elapsed_ms=model.elapsed_ms,
            created_at=model.created_at,
        )

    @staticmethod
    def to_model(audit: SQLAudit) -> SQLAuditMySQL:
        """把审计实体转换成 ORM 模型用于落库"""

        return SQLAuditMySQL(
            session_id=audit.session_id,
            seq=audit.seq,
            user_query=audit.user_query,
            rewritten_query=audit.rewritten_query,
            sql=audit.sql,
            allowed=audit.allowed,
            guard_rule=audit.guard_rule,
            guard_reason=audit.guard_reason,
            row_count=audit.row_count,
            elapsed_ms=audit.elapsed_ms,
        )
