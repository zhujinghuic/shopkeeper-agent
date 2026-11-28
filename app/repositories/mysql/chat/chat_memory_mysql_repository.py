"""
会话记忆 MySQL 仓储

负责把一次问答记录落库、按会话读出最近若干轮、以及按关键词回捞更早的轮次。
同时维护左侧会话列表需要的 chat_session 索引行。

这些表放在独立的 chat 库而不是 meta 库：元数据可以由脚本随时重建，
会话记录丢了就找不回来，两者不该共用同一个库的清理和备份边界。
它只管“怎么查怎么写”，上下文压缩和 token 预算由 app/agent/memory.py 负责。
"""

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.chat_session import ChatSession
from app.entities.chat_turn import ChatTurn
from app.models.chat_session import ChatSessionMySQL
from app.models.chat_turn import ChatTurnMySQL
from app.repositories.mysql.chat.mappers.chat_session_mapper import ChatSessionMapper
from app.repositories.mysql.chat.mappers.chat_turn_mapper import ChatTurnMapper


class ChatMemoryMySQLRepository:
    """负责多轮会话记录的持久化与读取"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_turns(self, session_id: str, limit: int) -> list[ChatTurn]:
        """按轮次倒序取最近 limit 轮，再翻回正序返回，方便拼历史上下文"""

        stmt = (
            select(ChatTurnMySQL)
            .where(ChatTurnMySQL.session_id == session_id)
            .order_by(ChatTurnMySQL.seq.desc())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        # 数据库里按 seq 倒序取的是“最近几轮”，返回前反转成从早到晚
        return [ChatTurnMapper.to_entity(model) for model in reversed(result.all())]

    async def list_all_turns(self, session_id: str) -> list[ChatTurn]:
        """按正序取出某个会话的全部轮次，用于前端回放历史对话"""

        stmt = (
            select(ChatTurnMySQL)
            .where(ChatTurnMySQL.session_id == session_id)
            .order_by(ChatTurnMySQL.seq.asc())
        )
        result = await self.session.scalars(stmt)
        return [ChatTurnMapper.to_entity(model) for model in result.all()]

    async def search_turns(
        self, session_id: str, keyword: str, limit: int = 2
    ) -> list[ChatTurn]:
        """按关键词回捞历史轮次，用于“回到刚才那个口径”这类强指代"""

        # 原话和改写结果都参与匹配：用户说的可能是“华北那个”，改写结果是完整问题
        stmt = (
            select(ChatTurnMySQL)
            .where(
                ChatTurnMySQL.session_id == session_id,
                or_(
                    ChatTurnMySQL.user_query.contains(keyword),
                    ChatTurnMySQL.rewritten_query.contains(keyword),
                ),
            )
            .order_by(ChatTurnMySQL.seq.desc())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return [ChatTurnMapper.to_entity(model) for model in result.all()]

    async def next_seq(self, session_id: str) -> int:
        """取该会话下一个轮次编号，没有历史时从 1 开始"""

        stmt = select(func.max(ChatTurnMySQL.seq)).where(
            ChatTurnMySQL.session_id == session_id
        )
        max_seq = await self.session.scalar(stmt)
        return (max_seq or 0) + 1

    async def append_turn(self, turn: ChatTurn, session_title: str) -> None:
        """追加一条问答记录，同时维护会话索引行

        两件事在同一个事务里：只有写入成功了，左侧列表才会出现这个会话；
        已存在的会话不会被 title 覆盖，标题永远是最早那一轮的问题。
        """

        self.session.add(ChatTurnMapper.to_model(turn))

        # MySQL 的 upsert：没有就插入，有就只递增轮数和刷新时间
        stmt = insert(ChatSessionMySQL).values(
            session_id=turn.session_id,
            title=session_title,
            turn_count=1,
        )
        stmt = stmt.on_duplicate_key_update(
            turn_count=ChatSessionMySQL.turn_count + 1,
            updated_at=func.now(),
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def list_sessions(self, limit: int = 50) -> list[ChatSession]:
        """按最后更新时间倒序取会话列表，供左侧栏展示"""

        stmt = (
            select(ChatSessionMySQL)
            .order_by(ChatSessionMySQL.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return [ChatSessionMapper.to_entity(model) for model in result.all()]

    async def get_session(self, session_id: str) -> ChatSession | None:
        """按会话编号取概要信息"""

        model = await self.session.get(ChatSessionMySQL, session_id)
        return ChatSessionMapper.to_entity(model) if model else None

    async def delete_session(self, session_id: str) -> None:
        """删除会话及其全部轮次：先删子记录再删索引行"""

        await self.session.execute(
            delete(ChatTurnMySQL).where(ChatTurnMySQL.session_id == session_id)
        )
        await self.session.execute(
            delete(ChatSessionMySQL).where(ChatSessionMySQL.session_id == session_id)
        )
        await self.session.commit()
