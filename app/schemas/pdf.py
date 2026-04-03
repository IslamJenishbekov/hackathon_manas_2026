from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PDFTextExtractionResponse(BaseModel):
    text: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
    extraction_mode: Literal["vision_ocr"] = "vision_ocr"

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("pdf extraction text must not be empty")
        return cleaned
