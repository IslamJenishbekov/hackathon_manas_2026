from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_fact_of_day_service
from app.main import app
from app.services.fact_of_day_service import FactOfDayService
from app.services.index_store import PersonShadowRecord, SQLiteIndexStore
from app.services.person_profile import build_person_search_text


class FakeFactOfDayService:
    def handle(self):
        return {"text": "Факт дня: тестовый ответ."}


def _build_store(tmp_path, persons: list[dict[str, object]]) -> SQLiteIndexStore:
    store = SQLiteIndexStore(str(tmp_path / "fact_of_day.db"))
    store.upsert_persons_shadow(
        [
            PersonShadowRecord(
                person_id=int(person["person_id"]),
                full_name=str(person["full_name"]),
                normalized_name=str(person["normalized_name"]),
                birth_year=person.get("birth_year"),
                death_year=person.get("death_year"),
                region=person.get("region"),
                district=person.get("district"),
                occupation=person.get("occupation"),
                charge=person.get("charge"),
                arrest_date=person.get("arrest_date"),
                sentence=person.get("sentence"),
                sentence_date=person.get("sentence_date"),
                rehabilitation_date=person.get("rehabilitation_date"),
                biography=person.get("biography"),
                source=person.get("source"),
                status="verified",
                search_text=build_person_search_text(person),
                raw_payload=person,
            )
            for person in persons
        ]
    )
    return store


def test_fact_of_day_service_prefers_today_anniversary(tmp_path) -> None:
    store = _build_store(
        tmp_path,
        persons=[
            {
                "person_id": 1,
                "full_name": "Байтемиров Асан Жумабекович",
                "normalized_name": "байтемиров асан жумабекович",
                "birth_year": 1899,
                "region": "Чуйская область",
                "district": "Кара-Балта",
                "occupation": "Учитель начальной школы",
                "charge": "Контрреволюционная агитация",
                "arrest_date": "1937-08-12",
                "sentence": "Расстрел",
                "sentence_date": "1937-11-03",
                "rehabilitation_date": "1958-04-04",
                "biography": "Родился в селе Ак-Башат и преподавал в школе.",
                "source": "seed",
            },
            {
                "person_id": 2,
                "full_name": "Сыдыкова Бурул Токтогуловна",
                "normalized_name": "сыдыкова бурул токтогуловна",
                "birth_year": 1905,
                "region": "Ошская область",
                "occupation": "Учительница",
                "charge": "Антисоветская деятельность",
                "arrest_date": "1938-03-20",
                "sentence_date": "1938-07-14",
                "rehabilitation_date": "1956-09-22",
                "biography": "Работала в школе и была репрессирована.",
                "source": "seed",
            },
        ],
    )
    service = FactOfDayService(
        index_store=store,
        today_provider=lambda: date(2026, 4, 4),
    )

    response = service.handle()

    assert "Факт дня:" in response.text
    assert "Байтемиров Асан Жумабекович" in response.text
    assert "4 апреля 1958 года" in response.text
    assert "реабилитация" in response.text.lower()


def test_fact_of_day_service_uses_fallback_when_no_anniversary(tmp_path) -> None:
    store = _build_store(
        tmp_path,
        persons=[
            {
                "person_id": 3,
                "full_name": "Касымов Ибраим",
                "normalized_name": "касымов ибраим",
                "birth_year": 1901,
                "region": "Нарынская область",
                "district": "Ат-Башы",
                "occupation": "Ветеринарный фельдшер",
                "charge": "Контрреволюционная агитация",
                "arrest_date": "1937-02-01",
                "sentence_date": "1937-06-12",
                "rehabilitation_date": "1989-05-14",
                "biography": "Работал в районе и был арестован в 1937 году.",
                "source": "seed",
            }
        ],
    )
    service = FactOfDayService(
        index_store=store,
        today_provider=lambda: date(2026, 1, 8),
    )

    response = service.handle()

    assert "Факт дня:" in response.text
    assert "Касымов Ибраим" in response.text
    assert "реабилитацией" in response.text or "Ветеринарный фельдшер" in response.text


def test_fact_of_day_service_returns_placeholder_for_empty_archive(tmp_path) -> None:
    store = SQLiteIndexStore(str(tmp_path / "empty_fact_of_day.db"))
    service = FactOfDayService(index_store=store, today_provider=lambda: date(2026, 4, 4))

    response = service.handle()

    assert response.text == "Факт дня пока недоступен: архив ещё не наполнен данными."


def test_fact_of_day_endpoint_returns_text_payload() -> None:
    app.dependency_overrides[get_fact_of_day_service] = lambda: FakeFactOfDayService()
    client = TestClient(app)

    response = client.post("/ai/fact_of_day")

    assert response.status_code == 200
    assert response.json() == {"text": "Факт дня: тестовый ответ."}

    app.dependency_overrides.clear()
