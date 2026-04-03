import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.index_store import PersonShadowRecord, SQLiteIndexStore
from app.services.normalization import normalize_person_name


def build_person_search_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []

    full_name = payload.get("full_name")
    if full_name:
        parts.append(str(full_name))

    occupation = payload.get("occupation")
    if occupation:
        parts.append(f"Род занятий: {occupation}")

    charge = payload.get("charge")
    if charge:
        parts.append(f"Обвинение: {charge}")

    region = payload.get("region")
    district = payload.get("district")
    if region or district:
        region_parts = [value for value in (region, district) if value]
        parts.append(f"Регион: {', '.join(str(value) for value in region_parts)}")

    for key, label in (
        ("birth_year", "Год рождения"),
        ("death_year", "Год смерти"),
        ("arrest_date", "Дата ареста"),
        ("sentence", "Приговор"),
        ("sentence_date", "Дата приговора"),
        ("rehabilitation_date", "Дата реабилитации"),
    ):
        value = payload.get(key)
        if value not in (None, ""):
            parts.append(f"{label}: {value}")

    rehabilitation_date = payload.get("rehabilitation_date")
    if rehabilitation_date:
        year = str(rehabilitation_date)[:4]
        if year.isdigit():
            parts.append(f"Реабилитирован в {year} году.")
            parts.append(f"Реабилитирован только в {year} году.")

    biography = payload.get("biography")
    if biography:
        parts.append(str(biography))

    source = payload.get("source")
    if source:
        parts.append(f"Источник: {source}")

    return "\n".join(parts).strip()


@dataclass
class PersonsShadowImporter:
    index_store: SQLiteIndexStore

    def import_json_file(self, file_path: str | Path) -> int:
        path = Path(file_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("seed payload must be a JSON array")

        records = [self._build_record(item) for item in payload]
        self.index_store.upsert_persons_shadow(records)
        return len(records)

    def _build_record(self, payload: dict[str, Any]) -> PersonShadowRecord:
        if not isinstance(payload, dict):
            raise ValueError("each seed item must be a JSON object")

        person_id = payload["id"]
        full_name = str(payload["full_name"]).strip()
        normalized_name = normalize_person_name(full_name)
        if not normalized_name:
            raise ValueError(f"failed to normalize full_name for person_id={person_id}")

        return PersonShadowRecord(
            person_id=int(person_id),
            full_name=full_name,
            normalized_name=normalized_name,
            birth_year=_as_optional_int(payload.get("birth_year")),
            death_year=_as_optional_int(payload.get("death_year")),
            region=_as_optional_str(payload.get("region")),
            district=_as_optional_str(payload.get("district")),
            occupation=_as_optional_str(payload.get("occupation")),
            charge=_as_optional_str(payload.get("charge")),
            arrest_date=_as_optional_str(payload.get("arrest_date")),
            sentence=_as_optional_str(payload.get("sentence")),
            sentence_date=_as_optional_str(payload.get("sentence_date")),
            rehabilitation_date=_as_optional_str(payload.get("rehabilitation_date")),
            biography=_as_optional_str(payload.get("biography")),
            source=_as_optional_str(payload.get("source")),
            status=_as_optional_str(payload.get("status")),
            search_text=build_person_search_text(payload),
            raw_payload=payload,
        )


def _as_optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _as_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
