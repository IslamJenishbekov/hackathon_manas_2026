from dataclasses import dataclass

from app.schemas.audio import VoiceRequest, VoiceRewriteDraft
from app.services.get_info_service import ServiceValidationError, UpstreamServiceError
from app.services.openai_client import OpenAIParseError, OpenAIStructuredClient
from app.services.prompt_renderer import PromptRenderer


@dataclass
class VoiceService:
    prompt_renderer: PromptRenderer
    openai_client: OpenAIStructuredClient
    rewrite_model: str
    tts_model: str
    tts_voice: str

    def handle(self, request: VoiceRequest) -> bytes:
        rewritten_text = self._rewrite_text(request)
        if len(rewritten_text) > 4096:
            raise ServiceValidationError("rewritten text is too long for TTS synthesis")

        try:
            return self.openai_client.synthesize_speech(
                model=self.tts_model,
                voice=self.tts_voice,
                text=rewritten_text,
                response_format="mp3",
            )
        except OpenAIParseError as exc:
            raise UpstreamServiceError("failed to synthesize speech") from exc

    def _rewrite_text(self, request: VoiceRequest) -> str:
        try:
            draft: VoiceRewriteDraft = self.openai_client.parse(
                model=self.rewrite_model,
                messages=[
                    {
                        "role": "system",
                        "content": self.prompt_renderer.render(
                            "voice/rewrite_system.j2",
                            {},
                        ),
                    },
                    {
                        "role": "user",
                        "content": self.prompt_renderer.render(
                            "voice/rewrite_user.j2",
                            {
                                "text": request.text,
                                "language": request.language,
                            },
                        ),
                    },
                ],
                response_model=VoiceRewriteDraft,
            )
        except OpenAIParseError as exc:
            raise UpstreamServiceError("failed to prepare text for speech synthesis") from exc

        return draft.spoken_text.strip()
