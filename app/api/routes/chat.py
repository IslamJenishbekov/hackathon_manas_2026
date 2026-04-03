from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_service
from app.schemas.api import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return service.handle(request)

