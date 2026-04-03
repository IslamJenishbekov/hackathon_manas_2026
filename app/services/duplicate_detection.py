from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from app.schemas.extraction import PersonCardLocalized
from app.services.index_store import RetrievedDocumentRecord, RetrievedPersonRecord
from app.services.normalization import normalize_person_name
from app.services.person_profile import build_person_search_text
from app.services.retrieval import lexical_similarity


STRONG_FIELDS = {
    "birth_year",
    "death_year",
    "arrest_date",
    "sentence_date",
    "rehabilitation_date",
}


@dataclass
class DuplicatePersonMatch:
    person_id: int
    full_name: str
    normalized_name: str
    birth_year: int | None
    confidence: float
    name_score: float
    profile_score: float
    document_score: float
    matched_fields: list[str]
    exact_name: bool
    strong_match_count: int
    soft_match_count: int


def find_duplicate_person(
    *,
    person_card: PersonCardLocalized,
    raw_text: str,
    persons: list[RetrievedPersonRecord],
    documents: list[RetrievedDocumentRecord],
) -> DuplicatePersonMatch | None:
    incoming_name = normalize_person_name(person_card.normalized_name or person_card.full_name)
    if not incoming_name:
        return None

    incoming_payload = _build_person_payload(person_card)
    incoming_search_text = build_person_search_text(incoming_payload)
    documents_by_person = defaultdict(list)
    for document in documents:
        if document.doc_type == "single" and document.raw_text.strip():
            documents_by_person[document.person_id].append(document.raw_text)

    matches = [
        _score_candidate(
            incoming_name=incoming_name,
            incoming_payload=incoming_payload,
            incoming_search_text=incoming_search_text,
            raw_text=raw_text,
            person=person,
            document_texts=documents_by_person.get(person.person_id, []),
        )
        for person in persons
    ]
    matches = [
        match
        for match in matches
        if match.name_score >= 0.72 or match.profile_score >= 0.35 or match.strong_match_count >= 1
    ]
    if not matches:
        return None

    matches.sort(key=lambda item: item.confidence, reverse=True)
    best_match = matches[0]
    if not _passes_duplicate_gate(best_match):
        return None
    return best_match


def _score_candidate(
    *,
    incoming_name: str,
    incoming_payload: dict[str, Any],
    incoming_search_text: str,
    raw_text: str,
    person: RetrievedPersonRecord,
    document_texts: list[str],
) -> DuplicatePersonMatch:
    name_score = _strict_name_similarity(incoming_name, person.normalized_name)
    profile_score = lexical_similarity(incoming_search_text, person.search_text)
    document_score = max(
        (lexical_similarity(raw_text, document_text) for document_text in document_texts),
        default=0.0,
    )

    matched_fields: list[str] = []
    if incoming_name == person.normalized_name:
        matched_fields.append("normalized_name")

    if incoming_payload["birth_year"] is not None and incoming_payload["birth_year"] == person.birth_year:
        matched_fields.append("birth_year")
    if incoming_payload["death_year"] is not None and incoming_payload["death_year"] == person.death_year:
        matched_fields.append("death_year")

    for field_name in ("arrest_date", "sentence_date", "rehabilitation_date"):
        if incoming_payload[field_name] and incoming_payload[field_name] == getattr(person, field_name):
            matched_fields.append(field_name)

    if _exact_text_match(incoming_payload["region"], person.region):
        matched_fields.append("region")
    if _exact_text_match(incoming_payload["district"], person.district):
        matched_fields.append("district")

    for field_name in ("occupation", "charge", "sentence"):
        if _fuzzy_text_match(incoming_payload[field_name], getattr(person, field_name)):
            matched_fields.append(field_name)

    strong_match_count = sum(field_name in STRONG_FIELDS for field_name in matched_fields)
    soft_match_count = len(matched_fields) - strong_match_count
    confidence = min(
        0.99,
        0.46 * name_score
        + 0.24 * profile_score
        + 0.18 * document_score
        + min(0.14, 0.07 * strong_match_count)
        + min(0.08, 0.02 * soft_match_count),
    )

    return DuplicatePersonMatch(
        person_id=person.person_id,
        full_name=person.full_name,
        normalized_name=person.normalized_name,
        birth_year=person.birth_year,
        confidence=confidence,
        name_score=name_score,
        profile_score=profile_score,
        document_score=document_score,
        matched_fields=matched_fields,
        exact_name=incoming_name == person.normalized_name,
        strong_match_count=strong_match_count,
        soft_match_count=soft_match_count,
    )


def _passes_duplicate_gate(match: DuplicatePersonMatch) -> bool:
    if match.exact_name and match.strong_match_count >= 1:
        return True
    if match.exact_name and match.profile_score >= 0.78 and (
        match.strong_match_count + match.soft_match_count
    ) >= 2:
        return True
    if match.name_score >= 0.93 and match.profile_score >= 0.82 and match.strong_match_count >= 1:
        return True
    if match.name_score >= 0.93 and match.profile_score >= 0.88 and (
        match.strong_match_count + match.soft_match_count
    ) >= 4:
        return True
    if match.name_score >= 0.93 and match.document_score >= 0.96:
        return True
    return False


def _build_person_payload(card: PersonCardLocalized) -> dict[str, Any]:
    return {
        "full_name": card.full_name,
        "birth_year": card.birth_year,
        "death_year": card.death_year,
        "region": card.region,
        "district": card.district,
        "occupation": card.occupation,
        "charge": card.charge,
        "arrest_date": _serialize_date(card.arrest_date),
        "sentence": card.sentence,
        "sentence_date": _serialize_date(card.sentence_date),
        "rehabilitation_date": _serialize_date(card.rehabilitation_date),
        "biography": card.biography,
    }


def _serialize_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _strict_name_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0

    left_tokens = left.split()
    right_tokens = right.split()
    if not left_tokens or not right_tokens:
        return 0.0

    first_token_score = SequenceMatcher(None, left_tokens[0], right_tokens[0]).ratio()
    if len(left_tokens) == len(right_tokens):
        ordered_score = sum(
            SequenceMatcher(None, left_token, right_token).ratio()
            for left_token, right_token in zip(left_tokens, right_tokens, strict=True)
        ) / len(left_tokens)
        return 0.7 * ordered_score + 0.3 * first_token_score

    phrase_score = SequenceMatcher(None, left, right).ratio()
    return 0.75 * phrase_score + 0.25 * first_token_score


def _exact_text_match(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    normalized_left = normalize_person_name(left)
    normalized_right = normalize_person_name(right)
    return bool(normalized_left and normalized_left == normalized_right)


def _fuzzy_text_match(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False

    normalized_left = normalize_person_name(left)
    normalized_right = normalize_person_name(right)
    if normalized_left and normalized_left == normalized_right:
        return True

    return lexical_similarity(left, right) >= 0.88
