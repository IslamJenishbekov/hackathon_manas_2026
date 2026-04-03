from typing import Any


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
