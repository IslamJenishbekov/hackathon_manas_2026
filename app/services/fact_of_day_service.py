from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Callable

from app.schemas.api import FactOfDayResponse
from app.services.index_store import RetrievedPersonRecord, SQLiteIndexStore

_MONTH_NAMES_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


@dataclass(frozen=True)
class FactCandidate:
    text: str
    score: float
    person_id: int
    category: str


@dataclass
class FactOfDayService:
    index_store: SQLiteIndexStore
    today_provider: Callable[[], date] = date.today

    def handle(self) -> FactOfDayResponse:
        persons = self.index_store.get_person_records()
        if not persons:
            return FactOfDayResponse(
                text="Факт дня пока недоступен: архив ещё не наполнен данными."
            )

        today = self.today_provider()
        occupation_frequency = Counter(
            _normalize_counter_key(person.occupation)
            for person in persons
            if _normalize_counter_key(person.occupation)
        )
        charge_frequency = Counter(
            _normalize_counter_key(person.charge)
            for person in persons
            if _normalize_counter_key(person.charge)
        )

        anniversary_candidates = self._build_anniversary_candidates(
            persons=persons,
            today=today,
            occupation_frequency=occupation_frequency,
            charge_frequency=charge_frequency,
        )
        if anniversary_candidates:
            selected = sorted(
                anniversary_candidates,
                key=lambda item: (-item.score, item.person_id, item.category, item.text),
            )[0]
            return FactOfDayResponse(text=selected.text)

        fallback_candidates = self._build_fallback_candidates(
            persons=persons,
            occupation_frequency=occupation_frequency,
            charge_frequency=charge_frequency,
        )
        selected = self._pick_rotating_fallback(fallback_candidates, today)
        return FactOfDayResponse(text=selected.text)

    def _build_anniversary_candidates(
        self,
        *,
        persons: list[RetrievedPersonRecord],
        today: date,
        occupation_frequency: Counter[str],
        charge_frequency: Counter[str],
    ) -> list[FactCandidate]:
        candidates: list[FactCandidate] = []
        for person in persons:
            for field_name, base_score in (
                ("rehabilitation_date", 92.0),
                ("sentence_date", 84.0),
                ("arrest_date", 80.0),
            ):
                event_date = _parse_iso_date(getattr(person, field_name))
                if event_date is None or (event_date.month, event_date.day) != (
                    today.month,
                    today.day,
                ):
                    continue

                years_since = today.year - event_date.year
                if years_since < 0:
                    continue

                score = (
                    base_score
                    + min(_richness_score(person), 8)
                    + _rarity_bonus(person, occupation_frequency, charge_frequency)
                    + min(_rehabilitation_gap_years(person) or 0, 25) * 0.35
                )
                candidates.append(
                    FactCandidate(
                        text=self._render_anniversary_text(
                            person=person,
                            field_name=field_name,
                            event_date=event_date,
                            years_since=years_since,
                        ),
                        score=score,
                        person_id=person.person_id,
                        category=field_name,
                    )
                )
        return candidates

    def _build_fallback_candidates(
        self,
        *,
        persons: list[RetrievedPersonRecord],
        occupation_frequency: Counter[str],
        charge_frequency: Counter[str],
    ) -> list[FactCandidate]:
        candidates: list[FactCandidate] = []

        for person in persons:
            richness = _richness_score(person)
            rarity = _rarity_bonus(person, occupation_frequency, charge_frequency)
            gap_years = _rehabilitation_gap_years(person)

            if gap_years is not None and gap_years >= 5 and person.rehabilitation_date:
                candidates.append(
                    FactCandidate(
                        text=self._render_delayed_rehabilitation_text(person, gap_years),
                        score=68.0 + min(gap_years, 35) * 0.8 + richness + rarity,
                        person_id=person.person_id,
                        category="delayed_rehabilitation",
                    )
                )

            if person.occupation:
                occupation_key = _normalize_counter_key(person.occupation)
                occupation_count = occupation_frequency.get(occupation_key, 0)
                candidates.append(
                    FactCandidate(
                        text=self._render_occupation_text(person),
                        score=42.0
                        + richness
                        + rarity
                        + max(0, 4 - min(occupation_count, 4)) * 3,
                        person_id=person.person_id,
                        category="occupation",
                    )
                )

            if person.charge:
                charge_key = _normalize_counter_key(person.charge)
                charge_count = charge_frequency.get(charge_key, 0)
                candidates.append(
                    FactCandidate(
                        text=self._render_charge_text(person),
                        score=40.0
                        + richness
                        + rarity
                        + max(0, 4 - min(charge_count, 4)) * 3,
                        person_id=person.person_id,
                        category="charge",
                    )
                )

            candidates.append(
                FactCandidate(
                    text=self._render_profile_text(person),
                    score=24.0 + richness + rarity,
                    person_id=person.person_id,
                    category="profile",
                )
            )

        return sorted(
            candidates,
            key=lambda item: (-item.score, item.person_id, item.category, item.text),
        )

    def _pick_rotating_fallback(
        self,
        candidates: list[FactCandidate],
        today: date,
    ) -> FactCandidate:
        if not candidates:
            return FactCandidate(
                text="Факт дня пока недоступен: архив ещё не наполнен данными.",
                score=0.0,
                person_id=0,
                category="empty",
            )

        pool_size = min(7, len(candidates))
        selected_index = today.toordinal() % pool_size
        return candidates[selected_index]

    def _render_anniversary_text(
        self,
        *,
        person: RetrievedPersonRecord,
        field_name: str,
        event_date: date,
        years_since: int,
    ) -> str:
        event_date_text = _format_date_ru(event_date)
        subject = person.full_name
        if field_name == "rehabilitation_date":
            lead = (
                f"Факт дня: {years_since} лет назад, {event_date_text}, "
                f"в архиве отмечена реабилитация {subject}."
            )
            details = _build_person_detail_sentences(
                person,
                include_sentence=False,
                include_rehabilitation=False,
            )
            return _join_sentences([lead, *details])

        if field_name == "sentence_date":
            lead = (
                f"Факт дня: {years_since} лет назад, {event_date_text}, "
                f"по делу {subject} был вынесен приговор."
            )
            details = _build_person_detail_sentences(
                person,
                include_sentence=True,
                include_rehabilitation=True,
            )
            return _join_sentences([lead, *details])

        lead = (
            f"Факт дня: {years_since} лет назад, {event_date_text}, "
            f"в архиве зафиксирован арест {subject}."
        )
        details = _build_person_detail_sentences(
            person,
            include_sentence=True,
            include_rehabilitation=True,
        )
        return _join_sentences([lead, *details])

    def _render_delayed_rehabilitation_text(
        self,
        person: RetrievedPersonRecord,
        gap_years: int,
    ) -> str:
        reference_label = "ареста"
        reference_date = _parse_iso_date(person.arrest_date)
        sentence_date = _parse_iso_date(person.sentence_date)
        if sentence_date is not None:
            reference_label = "приговора"
            reference_date = sentence_date

        date_fragment = ""
        if reference_date is not None:
            date_fragment = f" от {_format_date_ru(reference_date)}"

        lead = (
            f"Факт дня: дело {person.full_name} завершилось реабилитацией "
            f"только через {gap_years} лет после {reference_label}{date_fragment}."
        )
        details = _build_person_detail_sentences(
            person,
            include_sentence=False,
            include_rehabilitation=True,
        )
        return _join_sentences([lead, *details])

    def _render_occupation_text(self, person: RetrievedPersonRecord) -> str:
        lead = (
            f"Факт дня: среди архивных дел выделяется история {person.full_name}"
            f" — {person.occupation.strip()}."
        )
        details = _build_person_detail_sentences(
            person,
            include_sentence=True,
            include_rehabilitation=True,
        )
        return _join_sentences([lead, *details])

    def _render_charge_text(self, person: RetrievedPersonRecord) -> str:
        lead = (
            f"Факт дня: среди архивных дел выделяется дело {person.full_name} "
            f"с формулировкой обвинения «{person.charge.strip()}»."
        )
        details = _build_person_detail_sentences(
            person,
            include_sentence=True,
            include_rehabilitation=True,
        )
        return _join_sentences([lead, *details])

    def _render_profile_text(self, person: RetrievedPersonRecord) -> str:
        lead = f"Факт дня: в архиве хранится дело {person.full_name}."
        details = _build_person_detail_sentences(
            person,
            include_sentence=True,
            include_rehabilitation=True,
        )
        biography = _first_sentence(person.biography)
        if biography:
            details.append(f"Краткая справка: {biography}.")
        return _join_sentences([lead, *details])


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _format_date_ru(value: date) -> str:
    return f"{value.day} {_MONTH_NAMES_RU[value.month]} {value.year} года"


def _normalize_counter_key(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.lower().replace("ё", "е").split())


def _richness_score(person: RetrievedPersonRecord) -> int:
    return sum(
        1
        for value in (
            person.birth_year,
            person.death_year,
            person.region,
            person.district,
            person.occupation,
            person.charge,
            person.arrest_date,
            person.sentence,
            person.sentence_date,
            person.rehabilitation_date,
            person.biography,
        )
        if value
    )


def _rarity_bonus(
    person: RetrievedPersonRecord,
    occupation_frequency: Counter[str],
    charge_frequency: Counter[str],
) -> float:
    bonus = 0.0
    occupation_key = _normalize_counter_key(person.occupation)
    charge_key = _normalize_counter_key(person.charge)

    occupation_count = occupation_frequency.get(occupation_key)
    if occupation_count:
        bonus += max(0.0, 3.5 - min(float(occupation_count), 3.5))

    charge_count = charge_frequency.get(charge_key)
    if charge_count:
        bonus += max(0.0, 3.5 - min(float(charge_count), 3.5))

    return bonus


def _rehabilitation_gap_years(person: RetrievedPersonRecord) -> int | None:
    rehabilitation_date = _parse_iso_date(person.rehabilitation_date)
    if rehabilitation_date is None:
        return None

    reference_date = _parse_iso_date(person.sentence_date) or _parse_iso_date(person.arrest_date)
    if reference_date is None:
        return None

    gap = rehabilitation_date.year - reference_date.year
    if gap < 0:
        return None
    return gap


def _build_person_detail_sentences(
    person: RetrievedPersonRecord,
    *,
    include_sentence: bool,
    include_rehabilitation: bool,
) -> list[str]:
    details: list[str] = []

    location_parts = [value.strip() for value in (person.region, person.district) if value]
    location_text = ", ".join(location_parts)
    if location_parts and person.occupation:
        details.append(
            f"Человек связан с территорией {location_text} и указан как {person.occupation.strip()}."
        )
    elif location_parts:
        details.append(f"В архивной записи упоминается территория: {location_text}.")
    elif person.occupation:
        details.append(f"В карточке человека указано занятие: {person.occupation.strip()}.")

    if person.charge:
        details.append(f"В материалах фигурирует обвинение: {person.charge.strip()}.")

    if include_sentence and person.sentence:
        details.append(f"В архивной записи указан приговор: {person.sentence.strip()}.")

    if include_rehabilitation:
        rehabilitation_date = _parse_iso_date(person.rehabilitation_date)
        if rehabilitation_date is not None:
            details.append(
                f"Дата реабилитации в архиве: {_format_date_ru(rehabilitation_date)}."
            )

    return details


def _first_sentence(value: str | None) -> str:
    if not value:
        return ""
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return ""
    for separator in (".", "!", "?"):
        if separator in cleaned:
            prefix = cleaned.split(separator, 1)[0].strip()
            if prefix:
                return prefix.rstrip(".!?")
    return cleaned[:160].rstrip(".!?")


def _join_sentences(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())
