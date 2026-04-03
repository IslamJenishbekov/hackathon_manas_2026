from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.extraction import PersonCardLocalized


class GetInfoRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text must not be empty")
        if len(cleaned) < 10:
            raise ValueError("text is too short to analyze")
        return cleaned


class GetInfoSingleResponse(BaseModel):
    type: Literal["single"]
    result: dict[str, PersonCardLocalized]
    missing_fields: list[str]
    warnings: list[str]


class GetInfoPluralResponse(BaseModel):
    type: Literal["plural"]
    normalized_names: list[str]
    warnings: list[str]


GetInfoResponse = Annotated[
    GetInfoSingleResponse | GetInfoPluralResponse,
    Field(discriminator="type"),
]


class SaveDocRequest(BaseModel):
    person_id: int
    document_id: int
    filename: str
    text: str

    @field_validator("person_id", "document_id")
    @classmethod
    def validate_positive_ids(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be a positive integer")
        return value

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("filename must not be empty")
        return cleaned

    @field_validator("text")
    @classmethod
    def validate_text_for_save(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text must not be empty")
        if len(cleaned) < 10:
            raise ValueError("text is too short to index")
        return cleaned


class SaveDocResponse(BaseModel):
    status: Literal["ok"]


class ChatHistoryItem(BaseModel):
    question: str
    answer: str

    @field_validator("question", "answer")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("history entries must not be empty")
        return cleaned


class ChatRequest(BaseModel):
    question: str
    history: list[ChatHistoryItem] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question must not be empty")
        if len(cleaned) < 3:
            raise ValueError("question is too short")
        return cleaned


class ChatSource(BaseModel):
    document_id: int
    quote_text: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
