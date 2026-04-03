from fastapi import APIRouter, Depends, Response

from app.api.dependencies import get_voice_service
from app.schemas.audio import VoiceRequest
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/voice")
def voice(
    request: VoiceRequest,
    service: VoiceService = Depends(get_voice_service),
) -> Response:
    audio_bytes = service.handle(request)
    return Response(content=audio_bytes, media_type="audio/mpeg")
