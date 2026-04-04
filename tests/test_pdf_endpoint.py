import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_pdf_ocr_service
from app.main import app
from app.services.get_info_service import UnsupportedMediaTypeError
from app.services.layout_parsing_client import LayoutParsingClient, LayoutParsingError
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


class UnexpectedOpenAIClient:
    def extract_text_from_pdf(self, *, model: str, file_name: str, file_bytes: bytes) -> str:
        raise AssertionError("OpenAI fallback should not be called")


class FakeLayoutParsingClient:
    def extract_text_from_pdf(self, *, file_bytes: bytes) -> str:
        assert file_bytes.startswith(b"%PDF-")
        return "Текст из layout parsing"


class FailingLayoutParsingClient:
    def extract_text_from_pdf(self, *, file_bytes: bytes) -> str:
        raise LayoutParsingError("boom")


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
        layout_parsing_client=None,
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
        layout_parsing_client=None,
        model="test-pdf-model",
    )

    with pytest.raises(UnsupportedMediaTypeError):
        service.handle(
            file_name="scan.txt",
            file_bytes=b"plain text",
            content_type="text/plain",
        )


def test_pdf_ocr_service_prefers_layout_parsing_when_available() -> None:
    service = PDFOCRService(
        openai_client=UnexpectedOpenAIClient(),
        layout_parsing_client=FakeLayoutParsingClient(),
        model="test-pdf-model",
    )

    response = service.handle(
        file_name="scan.pdf",
        file_bytes=b"%PDF-1.7 fake pdf bytes",
        content_type="application/pdf",
    )

    assert response.text == "Текст из layout parsing"
    assert response.warnings == []
    assert response.extraction_mode == "vision_ocr"


def test_pdf_ocr_service_falls_back_to_openai_when_layout_parsing_fails() -> None:
    service = PDFOCRService(
        openai_client=FakeOpenAIClient(),
        layout_parsing_client=FailingLayoutParsingClient(),
        model="test-pdf-model",
    )

    response = service.handle(
        file_name="scan.pdf",
        file_bytes=b"%PDF-1.7 fake pdf bytes",
        content_type="application/pdf",
    )

    assert response.text == "Распознанный текст"
    assert response.warnings == ["layout parsing failed; fell back to OpenAI OCR"]
    assert response.extraction_mode == "vision_ocr"


class FakeHTTPResponse:
    def __init__(self, *, body: str, content_type: str) -> None:
        self._body = body.encode("utf-8")
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_layout_parsing_client_accepts_plain_text_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LayoutParsingClient(
        base_url="http://layout.example",
        timeout_seconds=5.0,
    )

    monkeypatch.setattr(
        "app.services.layout_parsing_client.request.urlopen",
        lambda req, timeout: FakeHTTPResponse(body="plain extracted text", content_type="text/plain; charset=utf-8"),
    )

    response = client.extract_text_from_pdf(file_bytes=b"%PDF-1.7 fake pdf bytes")

    assert response == "plain extracted text"


def test_layout_parsing_client_extracts_markdown_text_from_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LayoutParsingClient(
        base_url="http://layout.example",
        timeout_seconds=5.0,
    )

    payload = {
        "errorCode": 0,
        "errorMsg": "Success",
        "result": {
            "layoutParsingResults": [
                {
                    "markdown": {
                        "text": "json extracted text",
                    }
                }
            ]
        },
    }
    monkeypatch.setattr(
        "app.services.layout_parsing_client.request.urlopen",
        lambda req, timeout: FakeHTTPResponse(body=__import__("json").dumps(payload), content_type="application/json"),
    )

    response = client.extract_text_from_pdf(file_bytes=b"%PDF-1.7 fake pdf bytes")

    assert response == "json extracted text"
