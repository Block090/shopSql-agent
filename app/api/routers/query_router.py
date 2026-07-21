"""
问数查询接口路由

负责定义前端访问的 `/api/query` 接口，把 HTTP 请求交给 QueryService，
并把问数智能体执行过程以 SSE 形式持续返回给客户端。
路由层只处理请求体、依赖声明和响应类型，不直接创建 Repository 或执行图节点。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies import get_query_service
from app.api.schemas.query_schema import QuerySchema
from app.services.query_history_service import QueryService

# 当前模块只维护查询相关接口，避免后续所有 API 都挤在 main.py 中
query_router = APIRouter()


@query_router.post("/api/query")
async def query_handler(
    # 请求体参数：FastAPI 会把前端 JSON 自动解析成 QuerySchema
    query: QuerySchema,
    # 服务依赖：FastAPI 会调用 get_query_service，递归组装它所需的仓储和客户端
    query_service: Annotated[QueryService, Depends(get_query_service)],
):
    """接收用户自然语言问题，并流式返回 LangGraph 工作流输出"""

    return StreamingResponse(
        # query.query 是用户问题字符串；QueryService.query 返回异步生成器供响应逐段消费
        query_service.query(
            query.query,
            session_id=query.session_id,
            user_id=query.user_id,
        ),
        media_type="text/event-stream",
    )


@query_router.get("/api/sessions")
async def list_sessions_handler(
    query_service: Annotated[QueryService, Depends(get_query_service)],
):
    """返回最近的问数会话列表。"""

    return {"sessions": await query_service.list_sessions()}


@query_router.get("/api/sessions/{session_id}/history")
async def get_session_history_handler(
    session_id: str,
    query_service: Annotated[QueryService, Depends(get_query_service)],
):
    """返回指定会话的历史问答摘要。"""

    return {"history": await query_service.get_session_history(session_id)}


@query_router.delete("/api/sessions/{session_id}")
async def delete_session_handler(
    session_id: str,
    query_service: Annotated[QueryService, Depends(get_query_service)],
):
    """删除指定历史会话及其全部查询记录。"""

    return await query_service.delete_session(session_id)
