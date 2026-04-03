from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class GetInfoClassification(BaseModel):
    type: Literal["single", "plural"]
    warnings: list[str] = Field(default_factory=list)


class PersonCardLocalized(BaseModel):
    full_name: str | None = None
    normalized_name: str | None = None
    birth_year: int | None = None
    death_year: int | None = None
    birth_date: date | None = None
    death_date: date | None = None
    birth_place: str | None = None
    death_place: str | None = None
    region: str | None = None
    district: str | None = None
    occupation: str | None = None
    charge: str | None = None
    arrest_date: date | None = None
    sentence: str | None = None
    sentence_date: date | None = None
    rehabilitation_date: date | None = None
    biography: str | None = None


class GetInfoSingleLLMOutput(BaseModel):
    ky: PersonCardLocalized
    ru: PersonCardLocalized
    en: PersonCardLocalized
    tr: PersonCardLocalized
    warnings: list[str] = Field(default_factory=list)


class GetInfoPluralLLMOutput(BaseModel):
    names: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
