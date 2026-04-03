from fastapi import APIRouter, Depends

from app.api.dependencies import get_fact_of_day_service
from app.schemas.api import FactOfDayResponse
from app.services.fact_of_day_service import FactOfDayService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/fact_of_day", response_model=FactOfDayResponse)
def fact_of_day(
    service: FactOfDayService = Depends(get_fact_of_day_service),
) -> FactOfDayResponse:
    return service.handle()
