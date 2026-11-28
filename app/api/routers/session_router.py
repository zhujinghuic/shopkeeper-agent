"""
会话接口路由

提供左侧会话列表、某个会话的历史消息和删除会话三个接口。
这些接口都是普通 JSON 响应，不涉及流式输出。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_chat_session_service
from app.api.schemas.session_schema import (
    SessionDetailSchema,
    SessionMessageSchema,
    SessionSummarySchema,
)
from app.services.chat_session_service import ChatSessionService

session_router = APIRouter()


@session_router.get("/api/sessions", response_model=list[SessionSummarySchema])
async def list_sessions(
    chat_session_service: Annotated[
        ChatSessionService, Depends(get_chat_session_service)
    ],
):
    """按最后更新时间倒序返回会话列表，供左侧栏展示"""

    sessions = await chat_session_service.list_sessions()
    return [
        SessionSummarySchema(
            session_id=session.session_id,
            title=session.title,
            turn_count=session.turn_count,
            updated_at=session.updated_at,
        )
        for session in sessions
    ]


@session_router.get("/api/sessions/{session_id}", response_model=SessionDetailSchema)
async def get_session_detail(
    session_id: str,
    chat_session_service: Annotated[
        ChatSessionService, Depends(get_chat_session_service)
    ],
):
    """返回某个会话的全部历史消息，前端点击左侧列表时调用"""

    detail = await chat_session_service.get_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="会话不存在")

    chat_session, messages = detail
    return SessionDetailSchema(
        session_id=chat_session.session_id,
        title=chat_session.title,
        messages=[SessionMessageSchema(**message) for message in messages],
    )


@session_router.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    chat_session_service: Annotated[
        ChatSessionService, Depends(get_chat_session_service)
    ],
):
    """删除会话及其全部轮次"""

    deleted = await chat_session_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {"session_id": session_id, "deleted": True}
