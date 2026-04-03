from dataclasses import dataclass

from app.schemas.audio import ASRResponse
from app.services.audio_language import is_supported_transcript_language
from app.services.get_info_service import ServiceValidationError, UpstreamServiceError
from app.services.openai_client import OpenAIParseError, OpenAIStructuredClient


@dataclass
class ASRService:
    openai_client: OpenAIStructuredClient
    model: str

    def handle(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        content_type: str | None,
    ) -> ASRResponse:
        if not file_bytes:
            raise ServiceValidationError("audio file must not be empty")

        try:
            text = self.openai_client.transcribe_audio(
                model=self.model,
                file_name=file_name,
                file_bytes=file_bytes,
                content_type=content_type,
            )
        except OpenAIParseError as exc:
            raise UpstreamServiceError("failed to transcribe audio") from exc

        if not is_supported_transcript_language(text):
            raise ServiceValidationError(
                "audio language is not supported; supported languages: en, ky, ru, tr"
            )

        return ASRResponse(text=text)
