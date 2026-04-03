import re

from app.schemas.extraction import PersonCardLocalized


LANG_PRIORITY = ("ru", "ky", "en", "tr")
INVARIANT_FIELDS = (
    "normalized_name",
    "birth_year",
    "death_year",
    "birth_date",
    "death_date",
    "arrest_date",
    "sentence_date",
    "rehabilitation_date",
)
LOCALIZED_FIELDS = tuple(PersonCardLocalized.model_fields.keys())


def normalize_person_name(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower().replace("ё", "е")
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"[^\w\s-]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized, flags=re.UNICODE).strip()
    return normalized or None


def coalesce_canonical_name(cards: dict[str, PersonCardLocalized]) -> str | None:
    for language in LANG_PRIORITY:
        full_name = cards[language].full_name
        if full_name:
            return full_name
    return None


def sync_invariant_fields(cards: dict[str, PersonCardLocalized]) -> list[str]:
    warnings: list[str] = []

    for field_name in INVARIANT_FIELDS:
        values: list[tuple[str, str | int]] = []
        for language in LANG_PRIORITY:
            value = getattr(cards[language], field_name)
            if value not in (None, ""):
                values.append((language, value))

        if not values:
            continue

        canonical_language, canonical_value = values[0]
        conflicting_languages = [
            language for language, value in values[1:] if value != canonical_value
        ]
        if conflicting_languages:
            warnings.append(
                f"conflicting `{field_name}` values detected; "
                f"using value from `{canonical_language}`"
            )

        for language in LANG_PRIORITY:
            setattr(cards[language], field_name, canonical_value)

    return warnings


def compute_missing_fields(cards: dict[str, PersonCardLocalized]) -> list[str]:
    missing_fields: list[str] = []
    for field_name in LOCALIZED_FIELDS:
        if field_name == "normalized_name":
            continue
        if all(getattr(cards[language], field_name) in (None, "") for language in LANG_PRIORITY):
            missing_fields.append(field_name)
    return missing_fields


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def merge_warnings(*warning_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in warning_groups:
        for warning in group:
            cleaned = warning.strip()
            if cleaned:
                merged.append(cleaned)
    return dedupe_preserve_order(merged)

