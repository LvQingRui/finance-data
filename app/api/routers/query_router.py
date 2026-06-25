from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies import get_query_service
from app.api.schemas.query_schema import QuerySchema
from app.query_service import QueryService

query_router = APIRouter()


@query_router.post("/api/query", summary="金融问数 SSE 查询")
async def query_nl2sql(
    query: QuerySchema, service: QueryService = Depends(get_query_service)
):
    return StreamingResponse(
        service.query(query.query), media_type="text/event-stream"
    )

