"""
ChatSession 映射器

会话索引表的实体与 ORM 模型转换，沿用元数据模块的 Mapper 分层做法。
"""

from app.entities.chat_session import ChatSession
from app.models.chat_session import ChatSessionMySQL


class ChatSessionMapper:
    """负责 `ChatSession` 与 `ChatSessionMySQL` 之间的双向转换"""

    @staticmethod
    def to_entity(model: ChatSessionMySQL) -> ChatSession:
        """把 ORM 模型转换回会话实体"""

        return ChatSession(
            session_id=model.session_id,
            title=model.title,
            turn_count=model.turn_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(chat_session: ChatSession) -> ChatSessionMySQL:
        """把会话实体转换成 ORM 模型用于落库"""

        return ChatSessionMySQL(
            session_id=chat_session.session_id,
            title=chat_session.title,
            turn_count=chat_session.turn_count,
        )
