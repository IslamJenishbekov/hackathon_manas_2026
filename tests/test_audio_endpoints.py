from fastapi.testclient import TestClient

from app.api.dependencies import get_asr_service, get_voice_service
from app.main import app
from app.schemas.audio import ASRResponse, VoiceRequest


class FakeVoiceService:
    def handle(self, request: VoiceRequest) -> bytes:
        assert request.text == "Байтемиров был реабилитирован в 1958 году."
        assert request.language == "ru"
        return b"fake-mp3-bytes"


class FakeASRService:
    def handle(self, *, file_name: str, file_bytes: bytes, content_type: str | None) -> ASRResponse:
        assert file_name == "sample.wav"
        assert file_bytes == b"wav-bytes"
        assert content_type == "audio/wav"
        return ASRResponse(text="Ассаламу алейкум")


def override_voice_service() -> FakeVoiceService:
    return FakeVoiceService()


def override_asr_service() -> FakeASRService:
    return FakeASRService()


def test_voice_endpoint_returns_mpeg_audio() -> None:
    app.dependency_overrides[get_voice_service] = override_voice_service
    client = TestClient(app)

    response = client.post(
        "/ai/voice",
        json=VoiceRequest(
            text="Байтемиров был реабилитирован в 1958 году.",
            language="ru",
        ).model_dump(),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"fake-mp3-bytes"

    app.dependency_overrides.clear()


def test_asr_endpoint_accepts_multipart_file() -> None:
    app.dependency_overrides[get_asr_service] = override_asr_service
    client = TestClient(app)

    response = client.post(
        "/ai/asr",
        files={"file": ("sample.wav", b"wav-bytes", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "Ассаламу алейкум"}

    app.dependency_overrides.clear()
