from fastapi import APIRouter, Depends

from app.api.dependencies import get_get_info_service
from app.schemas.api import GetInfoRequest, GetInfoResponse
from app.services.get_info_service import GetInfoService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/get_info", response_model=GetInfoResponse)
def get_info(
    request: GetInfoRequest,
    service: GetInfoService = Depends(get_get_info_service),
) -> GetInfoResponse:
    return service.handle(request)
