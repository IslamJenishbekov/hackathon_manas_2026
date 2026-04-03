from pydantic import BaseModel, Field, field_validator

from app.services.audio_language import validate_supported_audio_language


class VoiceRequest(BaseModel):
    text: str
    language: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text must not be empty")
        if len(cleaned) < 3:
            raise ValueError("text is too short for voice synthesis")
        return cleaned

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("language must not be empty")
        return validate_supported_audio_language(cleaned)


class ASRResponse(BaseModel):
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("transcription text must not be empty")
        return cleaned


class VoiceRewriteDraft(BaseModel):
    spoken_text: str

    @field_validator("spoken_text")
    @classmethod
    def validate_spoken_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("spoken_text must not be empty")
        return cleaned
