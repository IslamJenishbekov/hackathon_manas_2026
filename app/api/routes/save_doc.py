from fastapi import APIRouter, Depends

from app.api.dependencies import get_save_doc_service
from app.schemas.api import SaveDocRequest, SaveDocResponse
from app.services.save_doc_service import SaveDocService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/save_doc", response_model=SaveDocResponse)
def save_doc(
    request: SaveDocRequest,
    service: SaveDocService = Depends(get_save_doc_service),
) -> SaveDocResponse:
    return service.handle(request)

