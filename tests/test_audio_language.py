import pytest

from app.schemas.audio import VoiceRequest
from app.services.asr_service import ASRService
from app.services.audio_language import detect_transcript_language
from app.services.get_info_service import ServiceValidationError


class FakeOpenAIClientKazakhASR:
    def transcribe_audio(self, *, model: str, file_name: str, file_bytes: bytes, content_type: str | None) -> str:
        return "Сәлем, менің атым Ислам."


def test_voice_request_rejects_unsupported_language() -> None:
    with pytest.raises(ValueError):
        VoiceRequest(text="Тестовый текст", language="kk")


def test_detect_transcript_language_marks_kazakh_as_unsupported() -> None:
    assert detect_transcript_language("Сәлем, менің атым Ислам.") == "kk"


def test_asr_service_rejects_unsupported_transcript_language() -> None:
    service = ASRService(
        openai_client=FakeOpenAIClientKazakhASR(),
        model="test-asr-model",
    )

    with pytest.raises(ServiceValidationError):
        service.handle(
            file_name="sample.mp3",
            file_bytes=b"audio-bytes",
            content_type="audio/mpeg",
        )
