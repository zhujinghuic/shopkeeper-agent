"""
会话管理服务

左侧会话列表和“点回历史对话”都由它提供，逻辑很薄：
读会话索引拿标题，读某一轮的记录还原成一条条消息。
真正的问答链路在 QueryService 里，两者共用同一个会话仓储。
"""

from app.entities.chat_session import ChatSession
from app.entities.chat_turn import ChatTurn
from app.repositories.mysql.chat.chat_memory_mysql_repository import (
    ChatMemoryMySQLRepository,
)


class ChatSessionService:
    """封装会话列表、历史详情和删除"""

    def __init__(self, chat_memory_repository: ChatMemoryMySQLRepository):
        self.chat_memory_repository = chat_memory_repository

    async def list_sessions(self, limit: int = 50) -> list[ChatSession]:
        """左侧列表：只读会话索引，不碰具体轮次"""

        return await self.chat_memory_repository.list_sessions(limit)

    async def get_detail(
        self, session_id: str
    ) -> tuple[ChatSession, list[dict]] | None:
        """把某个会话的全部轮次还原成前端可直接渲染的消息列表"""

        chat_session = await self.chat_memory_repository.get_session(session_id)
        if not chat_session:
            return None

        turns = await self.chat_memory_repository.list_all_turns(session_id)
        messages: list[dict] = []
        for turn in turns:
            messages.append(self._user_message(turn))
            messages.append(self._assistant_message(turn))

        return chat_session, messages

    async def delete_session(self, session_id: str) -> bool:
        """删除会话，返回是否真的存在过"""

        chat_session = await self.chat_memory_repository.get_session(session_id)
        if not chat_session:
            return False
        await self.chat_memory_repository.delete_session(session_id)
        return True

    @staticmethod
    def _user_message(turn: ChatTurn) -> dict:
        """用户消息回放的是原话，不是改写后的完整问题"""

        return {
            "role": "user",
            "content": turn.user_query,
            "created_at": turn.created_at,
        }

    @staticmethod
    def _assistant_message(turn: ChatTurn) -> dict:
        """助手消息按落库时的结果类型还原：拒绝 / 澄清 / 有数据 / 无数据 / 没结果"""

        missing = (turn.slots or {}).get("missing") or []
        rejected = (turn.slots or {}).get("rejected") or ""
        if rejected:
            # 只读边界之外的请求：回放时要还原成拒绝提示，不能显示成“查询成功”
            content = str(rejected)
            clarify = False
        elif missing:
            content = "；".join(str(item) for item in missing)
            clarify = True
        elif turn.row_count is None:
            content = "流程已结束，但没有拿到查询结果。"
            clarify = False
        elif turn.row_count > 0:
            content = f"已经查好了，共 {turn.row_count} 条结果。"
            clarify = False
        else:
            content = "已经查好了，本次没有匹配的数据。"
            clarify = False

        return {
            "role": "assistant",
            "content": content,
            # 没有数据时不要回传空数组，否则前端会画出一个空表格
            "result": turn.result or None,
            "sql": turn.sql,
            "row_count": turn.row_count,
            "clarify": clarify,
            "rejected": bool(rejected),
            "created_at": turn.created_at,
        }
