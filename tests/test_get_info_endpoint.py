from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_get_info_service
from app.main import app
from app.schemas.api import GetInfoRequest
from app.schemas.extraction import (
    GetInfoClassification,
    GetInfoPluralLLMOutput,
    GetInfoSingleLLMOutput,
    PersonCardLocalized,
)
from app.services.get_info_service import GetInfoService
from app.services.index_store import (
    IndexChunkRecord,
    IndexDocumentRecord,
    IndexEntityRecord,
    PersonShadowRecord,
    SQLiteIndexStore,
)
from app.services.person_profile import build_person_search_text


class FakePromptRenderer:
    def render(self, template_name: str, context: dict[str, object]) -> str:
        return f"{template_name}:{context.get('text', '')}"


class FakeOpenAIClient:
    def parse(self, *, model: str, messages: list[dict[str, object]], response_model: type[object]) -> object:
        if response_model is GetInfoClassification:
            return GetInfoClassification(type="plural", warnings=[])
        if response_model is GetInfoPluralLLMOutput:
            return GetInfoPluralLLMOutput(
                names=[
                    "Сыдыкова Бурул Токтогуловна",
                    " Сыдыкова Бурул Токтогуловна ",
                    "Маматов Эсенгул Кадырович",
                ],
                warnings=[],
            )
        raise AssertionError(f"unexpected response model {response_model}")


def override_service() -> GetInfoService:
    return GetInfoService(
        prompt_renderer=FakePromptRenderer(),
        openai_client=FakeOpenAIClient(),
        model="test-model",
    )


def test_get_info_plural_response_is_normalized() -> None:
    app.dependency_overrides[get_get_info_service] = override_service
    client = TestClient(app)

    response = client.post(
        "/ai/get_info",
        json=GetInfoRequest(text="СПИСОК лиц, арестованных в 1938 году").model_dump(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "type": "plural",
        "normalized_names": [
            "сыдыкова бурул токтогуловна",
            "маматов эсенгул кадырович",
        ],
        "warnings": [],
    }

    app.dependency_overrides.clear()


class FakeOpenAIClientSingle:
    def __init__(self, ru_card: PersonCardLocalized) -> None:
        self.ru_card = ru_card

    def parse(self, *, model: str, messages: list[dict[str, object]], response_model: type[object]) -> object:
        if response_model is GetInfoClassification:
            return GetInfoClassification(type="single", warnings=[])
        if response_model is GetInfoSingleLLMOutput:
            return GetInfoSingleLLMOutput(
                ky=PersonCardLocalized(),
                ru=self.ru_card,
                en=PersonCardLocalized(),
                tr=PersonCardLocalized(),
                warnings=[],
            )
        raise AssertionError(f"unexpected response model {response_model}")


def build_service_with_store(
    tmp_path,
    *,
    ru_card: PersonCardLocalized,
    persons: list[dict[str, object]],
    documents: list[dict[str, object]] | None = None,
) -> GetInfoService:
    store = SQLiteIndexStore(str(tmp_path / "index.db"))
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
                source="seed",
                status="verified",
                search_text=build_person_search_text(person),
                raw_payload=person,
            )
            for person in persons
        ]
    )

    for document in documents or []:
        raw_text = str(document["raw_text"])
        store.reindex_document(
            IndexDocumentRecord(
                document_id=int(document["document_id"]),
                person_id=int(document["person_id"]),
                filename=str(document["filename"]),
                source_link=document.get("source_link"),
                raw_text=raw_text,
                doc_type="single",
                primary_full_name=document.get("primary_full_name"),
                primary_normalized_name=document.get("primary_normalized_name"),
                primary_birth_year=document.get("primary_birth_year"),
                primary_region=document.get("primary_region"),
                primary_charge=document.get("primary_charge"),
                embedding_model="test-embedding-model",
                chunk_count=0,
                warnings=[],
            ),
            [
                IndexEntityRecord(
                    document_id=int(document["document_id"]),
                    normalized_name=str(document["primary_normalized_name"]),
                    raw_name=document.get("primary_full_name"),
                    birth_year=document.get("primary_birth_year"),
                    role="primary",
                )
            ],
            [
                IndexChunkRecord(
                    document_id=int(document["document_id"]),
                    chunk_index=0,
                    chunk_text=raw_text,
                    char_start=0,
                    char_end=len(raw_text),
                    embedding=[0.0, 1.0],
                )
            ],
        )

    return GetInfoService(
        prompt_renderer=FakePromptRenderer(),
        openai_client=FakeOpenAIClientSingle(ru_card),
        model="test-model",
        index_store=store,
    )


def test_get_info_returns_409_for_exact_duplicate(tmp_path) -> None:
    person = {
        "person_id": 1,
        "full_name": "Байтемиров Асан Жумабекович",
        "normalized_name": "байтемиров асан жумабекович",
        "birth_year": 1899,
        "death_year": 1937,
        "region": "Чуйская область",
        "district": "Кара-Балта",
        "occupation": "Учитель начальной школы",
        "charge": "Контрреволюционная агитация",
        "arrest_date": "1937-08-12",
        "sentence": "Расстрел",
        "sentence_date": "1937-11-03",
        "rehabilitation_date": "1958-04-15",
        "biography": "Родился в селе Ак-Башат и преподавал в школе.",
    }
    service = build_service_with_store(
        tmp_path,
        ru_card=PersonCardLocalized(
            full_name="Байтемиров Асан Жумабекович",
            birth_year=1899,
            death_year=1937,
            region="Чуйская область",
            district="Кара-Балта",
            occupation="Учитель начальной школы",
            charge="Контрреволюционная агитация",
            arrest_date=date(1937, 8, 12),
            sentence="Расстрел",
            sentence_date=date(1937, 11, 3),
            rehabilitation_date=date(1958, 4, 15),
            biography="Родился в селе Ак-Башат и преподавал в школе.",
        ),
        persons=[person],
    )

    app.dependency_overrides[get_get_info_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/ai/get_info",
        json=GetInfoRequest(
            text="Байтемиров Асан Жумабекович, 1899 года рождения, учитель из Кара-Балты. Арестован в 1937 году.",
        ).model_dump(),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_person_detected"
    assert response.json()["error"]["details"]["person_id"] == 1
    assert "birth_year" in response.json()["error"]["details"]["matched_fields"]

    app.dependency_overrides.clear()


def test_get_info_returns_409_for_fuzzy_duplicate_with_variant_surname(tmp_path) -> None:
    stored_text = """
АРХИВНОЕ ДЕЛО № 5581
Сыдыкова Бурул Токтогуловна, 1905 года рождения, врач из Оша.
Арестована 20 марта 1938 года по обвинению в шпионаже.
14 июля 1938 года приговорена к 10 годам ИТЛ.
Реабилитирована 22 сентября 1956 года.
""".strip()
    incoming_text = stored_text.replace("Сыдыкова", "Садыкова")
    person = {
        "person_id": 2,
        "full_name": "Сыдыкова Бурул Токтогуловна",
        "normalized_name": "сыдыкова бурул токтогуловна",
        "birth_year": 1905,
        "death_year": 1943,
        "region": "Ошская область",
        "district": "Ош",
        "occupation": "Врач, заведующая фельдшерским пунктом",
        "charge": "Шпионаж в пользу иностранного государства (ст. 58-6)",
        "arrest_date": "1938-03-20",
        "sentence": "10 лет ИТЛ",
        "sentence_date": "1938-07-14",
        "rehabilitation_date": "1956-09-22",
        "biography": "Одна из первых кыргызских женщин-врачей.",
    }
    service = build_service_with_store(
        tmp_path,
        ru_card=PersonCardLocalized(
            full_name="Садыкова Бурул Токтогуловна",
            birth_year=1905,
            death_year=1943,
            region="Ошская область",
            district="Ош",
            occupation="Врач, заведующая фельдшерским пунктом",
            charge="Шпионаж в пользу иностранного государства (ст. 58-6)",
            arrest_date=date(1938, 3, 20),
            sentence="10 лет ИТЛ",
            sentence_date=date(1938, 7, 14),
            rehabilitation_date=date(1956, 9, 22),
            biography="Одна из первых кыргызских женщин-врачей.",
        ),
        persons=[person],
        documents=[
            {
                "document_id": 5581,
                "person_id": 2,
                "filename": "delo_sydykova.txt",
                "raw_text": stored_text,
                "primary_full_name": "Сыдыкова Бурул Токтогуловна",
                "primary_normalized_name": "сыдыкова бурул токтогуловна",
                "primary_birth_year": 1905,
                "primary_region": "Ошская область",
                "primary_charge": "Шпионаж в пользу иностранного государства (ст. 58-6)",
            }
        ],
    )

    app.dependency_overrides[get_get_info_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/ai/get_info",
        json=GetInfoRequest(text=incoming_text).model_dump(),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_person_detected"
    assert response.json()["error"]["details"]["person_id"] == 2
    assert response.json()["error"]["details"]["confidence"] >= 0.9

    app.dependency_overrides.clear()
