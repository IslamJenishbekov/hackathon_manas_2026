import json
import sqlite3

from app.schemas.api import (
    GetInfoPluralResponse,
    GetInfoSingleResponse,
    SaveDocRequest,
)
from app.schemas.extraction import PersonCardLocalized
from app.services.index_store import SQLiteIndexStore
from app.services.save_doc_service import SaveDocService


class FakeGetInfoServiceSingle:
    def analyze(self, _request):
        return GetInfoSingleResponse(
            type="single",
            result={
                "ky": PersonCardLocalized(),
                "ru": PersonCardLocalized(
                    full_name="Байтемиров Асан Жумабекович",
                    normalized_name="байтемиров асан жумабекович",
                    birth_year=1899,
                    region="Чуйская область",
                    charge="Контрреволюционная агитация",
                ),
                "en": PersonCardLocalized(),
                "tr": PersonCardLocalized(),
            },
            missing_fields=[],
            warnings=["single warning"],
        )


class FakeGetInfoServicePlural:
    def analyze(self, _request):
        return GetInfoPluralResponse(
            type="plural",
            normalized_names=[
                "сыдыкова бурул токтогуловна",
                "маматов эсенгул кадырович",
            ],
            warnings=["plural warning"],
        )


class FakeOpenAIClient:
    def embed_texts(self, *, model: str, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), float(index)] for index, text in enumerate(texts)]


class FakeGetInfoServiceAnalyzeOnly:
    def handle(self, _request):
        raise AssertionError("save_doc should not call handle()")

    def analyze(self, _request):
        return GetInfoPluralResponse(
            type="plural",
            normalized_names=["сыдыкова бурул токтогуловна"],
            warnings=[],
        )


def build_service(tmp_path, get_info_service) -> tuple[SaveDocService, str]:
    db_path = str(tmp_path / "index.db")
    service = SaveDocService(
        get_info_service=get_info_service,
        openai_client=FakeOpenAIClient(),
        index_store=SQLiteIndexStore(db_path),
        embedding_model="test-embedding-model",
        chunk_size=80,
        chunk_overlap=10,
    )
    return service, db_path


def fetch_one(db_path: str, query: str, params: tuple = ()) -> tuple:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(query, params).fetchone()
        assert row is not None
        return row


def fetch_all(db_path: str, query: str, params: tuple = ()) -> list[tuple]:
    with sqlite3.connect(db_path) as connection:
        return connection.execute(query, params).fetchall()


def test_save_doc_single_persists_document_entities_and_chunks(tmp_path) -> None:
    service, db_path = build_service(tmp_path, FakeGetInfoServiceSingle())

    response = service.handle(
        SaveDocRequest(
            person_id=12,
            document_id=18,
            filename="delo_baytemirova.txt",
            link="https://archive.example/documents/18",
            text="Байтемиров Асан Жумабекович. Учитель. Арестован по обвинению в антисоветской агитации. Реабилитирован позже.",
        )
    )

    assert response.status == "ok"

    document_row = fetch_one(
        db_path,
        """
        SELECT person_id, filename, source_link, doc_type, primary_full_name, primary_normalized_name,
               primary_birth_year, primary_region, primary_charge, chunk_count, warnings_json
        FROM documents WHERE document_id = ?
        """,
        (18,),
    )
    assert document_row[:9] == (
        12,
        "delo_baytemirova.txt",
        "https://archive.example/documents/18",
        "single",
        "Байтемиров Асан Жумабекович",
        "байтемиров асан жумабекович",
        1899,
        "Чуйская область",
        "Контрреволюционная агитация",
    )
    assert document_row[9] >= 1
    assert json.loads(document_row[10]) == ["single warning"]

    entity_rows = fetch_all(
        db_path,
        """
        SELECT normalized_name, raw_name, birth_year, role
        FROM document_entities WHERE document_id = ?
        """,
        (18,),
    )
    assert entity_rows == [
        (
            "байтемиров асан жумабекович",
            "Байтемиров Асан Жумабекович",
            1899,
            "primary",
        )
    ]

    chunk_rows = fetch_all(
        db_path,
        "SELECT chunk_index, chunk_text, embedding_json FROM chunks WHERE document_id = ?",
        (18,),
    )
    assert len(chunk_rows) >= 1


def test_save_doc_plural_persists_mentioned_entities(tmp_path) -> None:
    service, db_path = build_service(tmp_path, FakeGetInfoServicePlural())

    response = service.handle(
        SaveDocRequest(
            person_id=99,
            document_id=77,
            filename="spisok_oshskaya_1938.txt",
            link="https://archive.example/documents/77",
            text="Сыдыкова Бурул Токтогуловна. Маматов Эсенгул Кадырович. Итого 247 человек.",
        )
    )

    assert response.status == "ok"

    document_row = fetch_one(
        db_path,
        "SELECT doc_type, primary_normalized_name, source_link, chunk_count FROM documents WHERE document_id = ?",
        (77,),
    )
    assert document_row[0] == "plural"
    assert document_row[1] is None
    assert document_row[2] == "https://archive.example/documents/77"
    assert document_row[3] >= 1

    entity_rows = fetch_all(
        db_path,
        """
        SELECT normalized_name, raw_name, birth_year, role
        FROM document_entities WHERE document_id = ?
        ORDER BY id
        """,
        (77,),
    )
    assert entity_rows == [
        ("сыдыкова бурул токтогуловна", None, None, "mentioned"),
        ("маматов эсенгул кадырович", None, None, "mentioned"),
    ]


def test_save_doc_reindex_replaces_previous_entities_and_chunks(tmp_path) -> None:
    service, db_path = build_service(tmp_path, FakeGetInfoServicePlural())

    first_request = SaveDocRequest(
        person_id=7,
        document_id=55,
        filename="list.txt",
        link="https://archive.example/documents/55",
        text="Сыдыкова Бурул Токтогуловна. Маматов Эсенгул Кадырович. " * 3,
    )
    second_request = SaveDocRequest(
        person_id=7,
        document_id=55,
        filename="list_updated.txt",
        link="https://archive.example/documents/55-v2",
        text="Сыдыкова Бурул Токтогуловна.",
    )

    service.handle(first_request)
    service.handle(second_request)

    document_row = fetch_one(
        db_path,
        "SELECT filename, source_link, chunk_count FROM documents WHERE document_id = ?",
        (55,),
    )
    assert document_row[0] == "list_updated.txt"
    assert document_row[1] == "https://archive.example/documents/55-v2"

    entity_count = fetch_one(
        db_path,
        "SELECT COUNT(*) FROM document_entities WHERE document_id = ?",
        (55,),
    )[0]
    chunk_count = fetch_one(
        db_path,
        "SELECT COUNT(*) FROM chunks WHERE document_id = ?",
        (55,),
    )[0]

    assert entity_count == 2
    assert chunk_count == document_row[2]


def test_save_doc_uses_analyze_instead_of_handle(tmp_path) -> None:
    service, db_path = build_service(tmp_path, FakeGetInfoServiceAnalyzeOnly())

    response = service.handle(
        SaveDocRequest(
            person_id=7,
            document_id=56,
            filename="list.txt",
            link="https://archive.example/documents/56",
            text="Сыдыкова Бурул Токтогуловна. Итого 1 человек.",
        )
    )

    assert response.status == "ok"
    document_row = fetch_one(
        db_path,
        "SELECT doc_type FROM documents WHERE document_id = ?",
        (56,),
    )
    assert document_row[0] == "plural"
