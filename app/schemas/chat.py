from typing import Literal

from pydantic import BaseModel, Field


class ChatQueryAnalysis(BaseModel):
    mode: Literal["person", "global", "comparative", "ambiguous"]
    candidate_names: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ChatAnswerDraft(BaseModel):
    answer: str

