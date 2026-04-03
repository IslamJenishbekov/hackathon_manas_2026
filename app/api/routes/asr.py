from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_asr_service
from app.schemas.audio import ASRResponse
from app.services.asr_service import ASRService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/asr", response_model=ASRResponse)
async def asr(
    file: UploadFile = File(...),
    service: ASRService = Depends(get_asr_service),
) -> ASRResponse:
    file_bytes = await file.read()
    file_name = file.filename or "audio.bin"
    return service.handle(
        file_name=file_name,
        file_bytes=file_bytes,
        content_type=file.content_type,
    )
