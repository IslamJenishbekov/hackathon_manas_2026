from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_pdf_ocr_service
from app.schemas.errors import ErrorResponse
from app.schemas.pdf import PDFTextExtractionResponse
from app.services.pdf_ocr_service import PDFOCRService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/extract_pdf_text",
    response_model=PDFTextExtractionResponse,
    responses={
        415: {
            "model": ErrorResponse,
            "description": "The uploaded file is not a PDF.",
        }
    },
)
async def extract_pdf_text(
    file: UploadFile = File(...),
    service: PDFOCRService = Depends(get_pdf_ocr_service),
) -> PDFTextExtractionResponse:
    file_bytes = await file.read()
    file_name = file.filename or "document.pdf"
    return service.handle(
        file_name=file_name,
        file_bytes=file_bytes,
        content_type=file.content_type,
    )
