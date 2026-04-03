import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.services.index_store import RetrievedChunkRecord, RetrievedEntityRecord, RetrievedPersonRecord
from app.services.normalization import normalize_person_name


TOKEN_RE = re.compile(r"\w+", re.UNICODE)
STOPWORDS = {
    "а",
    "в",
    "во",
    "и",
    "из",
    "к",
    "как",
    "кем",
    "ким",
    "кто",
    "на",
    "о",
    "об",
    "он",
    "она",
    "они",
    "по",
    "про",
    "с",
    "со",
    "что",
    "эмне",
    "үчүн",
}


@dataclass
class ResolvedPerson:
    person_id: int | None
    normalized_name: str
    full_name: str | None
    confidence: float


@dataclass
class ScoredChunk:
    document_id: int
    chunk_index: int
    chunk_text: str
    source_link: str | None
    score: float


@dataclass
class ScoredPersonRecord:
    person_id: int
    full_name: str
    normalized_name: str
    search_text: str
    score: float


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def resolve_person_candidates(
    *,
    candidate_names: list[str],
    persons: list[RetrievedPersonRecord],
    entities: list[RetrievedEntityRecord],
) -> ResolvedPerson | None:
    normalized_candidates = [
        normalized for candidate in candidate_names if (normalized := normalize_person_name(candidate))
    ]
    if not normalized_candidates:
        return None

    best_person: RetrievedPersonRecord | None = None
    best_person_score = 0.0

    for candidate in normalized_candidates:
        for person in persons:
            score = _person_name_match_score(candidate, person.normalized_name)
            if score > best_person_score:
                best_person_score = score
                best_person = person

    if best_person is not None and best_person_score >= 0.82:
        return ResolvedPerson(
            person_id=best_person.person_id,
            normalized_name=best_person.normalized_name,
            full_name=best_person.full_name,
            confidence=best_person_score,
        )

    best_name: str | None = None
    best_score = 0.0
    unique_entity_names = sorted({entity.normalized_name for entity in entities})
    for candidate in normalized_candidates:
        for entity_name in unique_entity_names:
            score = _person_name_match_score(candidate, entity_name)
            if score > best_score:
                best_score = score
                best_name = entity_name

    if best_name is None or best_score < 0.82:
        return None

    return ResolvedPerson(
        person_id=None,
        normalized_name=best_name,
        full_name=None,
        confidence=best_score,
    )


def search_person_records(
    *,
    query_text: str,
    persons: list[RetrievedPersonRecord],
    top_k: int,
    minimum_score: float = 0.18,
) -> list[ScoredPersonRecord]:
    query_normalized = normalize_person_name(query_text) or query_text.lower()
    scored: list[ScoredPersonRecord] = []

    for person in persons:
        text_score = lexical_similarity(query_text, person.search_text)
        name_score = _name_similarity(query_normalized, person.normalized_name)
        exact_name_bonus = 0.0
        if person.normalized_name and person.normalized_name in query_normalized:
            exact_name_bonus = 0.2

        score = min(1.0, 0.55 * text_score + 0.35 * name_score + exact_name_bonus)
        if score < minimum_score:
            continue

        scored.append(
            ScoredPersonRecord(
                person_id=person.person_id,
                full_name=person.full_name,
                normalized_name=person.normalized_name,
                search_text=person.search_text,
                score=score,
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:top_k]


def score_chunks(
    *,
    query_text: str,
    question_embedding: list[float],
    chunks: list[RetrievedChunkRecord],
    top_k: int,
    preferred_doc_types: list[str] | None = None,
) -> list[ScoredChunk]:
    preferred = set(preferred_doc_types or [])
    scored = []
    for chunk in chunks:
        semantic = cosine_similarity(question_embedding, chunk.embedding)
        lexical = lexical_similarity(query_text, chunk.chunk_text)
        score = 0.72 * semantic + 0.28 * lexical
        if preferred and chunk.doc_type in preferred:
            score += 0.05
        scored.append(
            ScoredChunk(
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.chunk_text,
                source_link=chunk.source_link,
                score=score,
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:top_k]


def lexical_similarity(query_text: str, target_text: str) -> float:
    query_tokens = _tokenize_for_search(query_text)
    target_tokens = _tokenize_for_search(target_text)
    if not query_tokens or not target_tokens:
        return 0.0

    query_token_set = set(query_tokens)
    target_token_set = set(target_tokens)

    exact_overlap = len(query_token_set & target_token_set) / len(query_token_set)

    query_prefixes = {_token_prefix(token) for token in query_token_set}
    target_prefixes = {_token_prefix(token) for token in target_token_set}
    prefix_overlap = len(query_prefixes & target_prefixes) / len(query_prefixes)

    query_numbers = {token for token in query_token_set if token.isdigit()}
    target_numbers = {token for token in target_token_set if token.isdigit()}
    number_overlap = (
        len(query_numbers & target_numbers) / len(query_numbers) if query_numbers else 0.0
    )

    return min(1.0, 0.55 * prefix_overlap + 0.25 * exact_overlap + 0.20 * number_overlap)


def _name_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0

    left_tokens = left.split()
    right_tokens = right.split()
    if not left_tokens or not right_tokens:
        return 0.0

    token_scores: list[float] = []
    for left_token in left_tokens:
        best_token_score = max(
            SequenceMatcher(None, left_token, right_token).ratio()
            for right_token in right_tokens
        )
        token_scores.append(best_token_score)

    coverage = sum(token_scores) / len(token_scores)
    phrase_ratio = SequenceMatcher(None, left, right).ratio()
    return max(coverage, phrase_ratio)


def _person_name_match_score(candidate: str, full_name: str) -> float:
    candidate_tokens = candidate.split()
    full_name_tokens = full_name.split()
    if not candidate_tokens or not full_name_tokens:
        return 0.0

    if len(candidate_tokens) == 1:
        candidate_token = candidate_tokens[0]
        surname_score = SequenceMatcher(None, candidate_token, full_name_tokens[0]).ratio()
        exact_token_match = 1.0 if candidate_token in full_name_tokens else 0.0
        non_surname_score = 0.0
        if len(full_name_tokens) > 1:
            non_surname_score = max(
                SequenceMatcher(None, candidate_token, token).ratio()
                for token in full_name_tokens[1:]
            )

        return max(surname_score, exact_token_match, 0.65 * non_surname_score)

    base_score = _name_similarity(candidate, full_name)
    first_token_score = SequenceMatcher(None, candidate_tokens[0], full_name_tokens[0]).ratio()
    return max(base_score, 0.7 * base_score + 0.3 * first_token_score)


def _tokenize_for_search(text: str) -> list[str]:
    normalized = normalize_person_name(text) or ""
    tokens = TOKEN_RE.findall(normalized)
    return [token for token in tokens if len(token) > 1 and token not in STOPWORDS]


def _token_prefix(token: str) -> str:
    return token if len(token) <= 4 else token[:4]
