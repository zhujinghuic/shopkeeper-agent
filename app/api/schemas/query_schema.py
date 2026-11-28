"""
问数接口请求体定义

集中声明 API 层输入输出的数据结构，让路由函数只处理业务流程，
字段校验和 OpenAPI 文档生成交给 Pydantic 与 FastAPI 完成。
"""

from pydantic import BaseModel, Field


class QuerySchema(BaseModel):
    """`/api/query` 请求体，承载用户输入的自然语言问题"""

    # 前端请求体中的 query 字段，例如 {"query": "统计华北地区销售额"}
    query: str
    # 会话编号：同一会话的多轮追问共用，前端首次可以不带，由后端生成后回传
    # 长度受 chat_turn.session_id 的 VARCHAR(64) 约束，这里提前校验避免落库时报错
    session_id: str | None = Field(default=None, max_length=64)
