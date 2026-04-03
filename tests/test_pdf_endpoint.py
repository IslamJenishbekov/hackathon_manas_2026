import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_pdf_ocr_service
from app.main import app
from app.services.get_info_service import UnsupportedMediaTypeError
from app.services.pdf_ocr_service import PDFOCRService


class FakePDFOCRService:
    def handle(self, *, file_name: str, file_bytes: bytes, content_type: str | None):
        assert file_name == "archive.pdf"
        assert file_bytes.startswith(b"%PDF-")
        assert content_type == "application/pdf"
        return {
            "text": "Байтемиров Асан Жумабекович, 1899 года рождения.",
            "warnings": [],
            "extraction_mode": "vision_ocr",
        }


class FakePDFOCRServiceUnsupported:
    def handle(self, *, file_name: str, file_bytes: bytes, content_type: str | None):
        raise UnsupportedMediaTypeError("file must be a PDF")


class FakeOpenAIClient:
    def extract_text_from_pdf(self, *, model: str, file_name: str, file_bytes: bytes) -> str:
        assert model == "test-pdf-model"
        assert file_name == "scan.pdf"
        assert file_bytes.startswith(b"%PDF-")
        return "Распознанный текст"


def test_extract_pdf_text_endpoint_accepts_multipart_pdf() -> None:
    app.dependency_overrides[get_pdf_ocr_service] = lambda: FakePDFOCRService()
    client = TestClient(app)

    response = client.post(
        "/ai/extract_pdf_text",
        files={"file": ("archive.pdf", b"%PDF-1.7 fake pdf bytes", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "Байтемиров Асан Жумабекович, 1899 года рождения.",
        "warnings": [],
        "extraction_mode": "vision_ocr",
    }

    app.dependency_overrides.clear()


def test_extract_pdf_text_endpoint_returns_415_for_non_pdf() -> None:
    app.dependency_overrides[get_pdf_ocr_service] = lambda: FakePDFOCRServiceUnsupported()
    client = TestClient(app)

    response = client.post(
        "/ai/extract_pdf_text",
        files={"file": ("archive.txt", b"not pdf", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json() == {
        "error": {
            "code": "unsupported_media_type",
            "message": "file must be a PDF",
        }
    }

    app.dependency_overrides.clear()


def test_pdf_ocr_service_extracts_text_from_pdf() -> None:
    service = PDFOCRService(
        openai_client=FakeOpenAIClient(),
        model="test-pdf-model",
    )

    response = service.handle(
        file_name="scan.pdf",
        file_bytes=b"%PDF-1.7 fake pdf bytes",
        content_type="application/pdf",
    )

    assert response.text == "Распознанный текст"
    assert response.warnings == []
    assert response.extraction_mode == "vision_ocr"


def test_pdf_ocr_service_rejects_non_pdf() -> None:
    service = PDFOCRService(
        openai_client=FakeOpenAIClient(),
        model="test-pdf-model",
    )

    with pytest.raises(UnsupportedMediaTypeError):
        service.handle(
            file_name="scan.txt",
            file_bytes=b"plain text",
            content_type="text/plain",
        )
