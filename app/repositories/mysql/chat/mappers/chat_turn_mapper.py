"""
ChatTurn 映射器

延续元数据模块统一的分层做法：实体负责业务语义，ORM 模型负责存储，
两者之间的字段差异（例如 sql 在库里叫 sql_text）只在这一层处理。
"""

from app.entities.chat_turn import ChatTurn
from app.models.chat_turn import ChatTurnMySQL


class ChatTurnMapper:
    """负责 `ChatTurn` 与 `ChatTurnMySQL` 之间的双向转换"""

    @staticmethod
    def to_entity(model: ChatTurnMySQL) -> ChatTurn:
        """把 ORM 模型转换回会话轮次实体"""

        return ChatTurn(
            session_id=model.session_id,
            seq=model.seq,
            user_query=model.user_query,
            rewritten_query=model.rewritten_query,
            slots=model.slots or {},
            sql=model.sql,
            row_count=model.row_count,
            result=model.result or [],
            created_at=model.created_at,
        )

    @staticmethod
    def to_model(turn: ChatTurn) -> ChatTurnMySQL:
        """把会话轮次实体转换成 ORM 模型用于落库"""

        return ChatTurnMySQL(
            session_id=turn.session_id,
            seq=turn.seq,
            user_query=turn.user_query,
            rewritten_query=turn.rewritten_query,
            slots=turn.slots,
            sql=turn.sql,
            row_count=turn.row_count,
            result=turn.result,
        )
