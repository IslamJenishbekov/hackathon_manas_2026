from dataclasses import dataclass

from app.schemas.pdf import PDFTextExtractionResponse
from app.services.get_info_service import (
    ServiceValidationError,
    UnsupportedMediaTypeError,
    UpstreamServiceError,
)
from app.services.layout_parsing_client import LayoutParsingClient, LayoutParsingError
from app.services.openai_client import OpenAIParseError, OpenAIStructuredClient


MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024


@dataclass
class PDFOCRService:
    openai_client: OpenAIStructuredClient
    layout_parsing_client: LayoutParsingClient | None
    model: str

    def handle(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        content_type: str | None,
    ) -> PDFTextExtractionResponse:
        if not file_bytes:
            raise ServiceValidationError("pdf file must not be empty")

        if len(file_bytes) > MAX_PDF_SIZE_BYTES:
            raise ServiceValidationError("pdf file is too large")

        if not self._looks_like_pdf(file_name=file_name, file_bytes=file_bytes, content_type=content_type):
            raise UnsupportedMediaTypeError("file must be a PDF")

        warnings: list[str] = []

        if self.layout_parsing_client is not None:
            try:
                text = self.layout_parsing_client.extract_text_from_pdf(file_bytes=file_bytes)
            except LayoutParsingError:
                warnings.append("layout parsing failed; fell back to OpenAI OCR")
            else:
                return PDFTextExtractionResponse(
                    text=text,
                    warnings=warnings,
                    extraction_mode="vision_ocr",
                )

        try:
            text = self.openai_client.extract_text_from_pdf(
                model=self.model,
                file_name=file_name,
                file_bytes=file_bytes,
            )
        except OpenAIParseError as exc:
            raise UpstreamServiceError("failed to extract text from pdf") from exc

        return PDFTextExtractionResponse(
            text=text,
            warnings=warnings,
            extraction_mode="vision_ocr",
        )

    def _looks_like_pdf(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        content_type: str | None,
    ) -> bool:
        lowered_name = file_name.strip().lower()
        normalized_content_type = (content_type or "").strip().lower()

        if file_bytes.startswith(b"%PDF-"):
            return True
        if normalized_content_type == "application/pdf":
            return True
        return lowered_name.endswith(".pdf")
