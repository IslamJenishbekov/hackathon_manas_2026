from app.services.index_store import RetrievedChunkRecord, RetrievedEntityRecord, RetrievedPersonRecord
from app.services.retrieval import resolve_person_candidates, score_chunks, search_person_records


def test_resolve_person_candidates_matches_partial_name() -> None:
    entities = [
        RetrievedEntityRecord(
            document_id=4412,
            normalized_name="байтемиров асан жумабекович",
            raw_name="Байтемиров Асан Жумабекович",
            birth_year=1899,
            role="primary",
        ),
        RetrievedEntityRecord(
            document_id=5581,
            normalized_name="сыдыкова бурул токтогуловна",
            raw_name="Сыдыкова Бурул Токтогуловна",
            birth_year=1905,
            role="primary",
        ),
    ]

    resolved = resolve_person_candidates(
        candidate_names=["Байтемирова"],
        persons=[],
        entities=entities,
    )

    assert resolved is not None
    assert resolved.normalized_name == "байтемиров асан жумабекович"
    assert resolved.person_id is None
    assert resolved.confidence >= 0.82


def test_score_chunks_returns_top_ranked_items() -> None:
    chunks = [
        RetrievedChunkRecord(
            document_id=1,
            chunk_index=0,
            chunk_text="a",
            char_start=0,
            char_end=1,
            embedding=[1.0, 0.0],
            doc_type="single",
            filename="a.txt",
            source_link="https://archive.example/documents/1",
            person_id=1,
        ),
        RetrievedChunkRecord(
            document_id=2,
            chunk_index=0,
            chunk_text="b",
            char_start=0,
            char_end=1,
            embedding=[0.0, 1.0],
            doc_type="single",
            filename="b.txt",
            source_link="https://archive.example/documents/2",
            person_id=2,
        ),
    ]

    scored = score_chunks(
        query_text="a",
        question_embedding=[1.0, 0.0],
        chunks=chunks,
        top_k=1,
    )

    assert len(scored) == 1
    assert scored[0].document_id == 1


def test_search_person_records_finds_late_rehabilitation_pattern() -> None:
    persons = [
        RetrievedPersonRecord(
            person_id=8,
            full_name="Маматов Эсенгул Кадырович",
            normalized_name="маматов эсенгул кадырович",
            birth_year=1888,
            death_year=1937,
            region="Ошская область",
            district="Узген",
            occupation="Мулла, духовный деятель",
            charge="Антисоветская агитация на религиозной почве",
            arrest_date="1937-06-22",
            sentence="Расстрел",
            sentence_date="1937-08-30",
            rehabilitation_date="1989-05-14",
            biography="Духовный лидер общины. Реабилитирован только в 1989 году.",
            source="seed",
            status="verified",
            search_text="Маматов Эсенгул Кадырович. Мулла. Реабилитирован только в 1989 году.",
            raw_payload={},
        ),
        RetrievedPersonRecord(
            person_id=1,
            full_name="Байтемиров Асан Жумабекович",
            normalized_name="байтемиров асан жумабекович",
            birth_year=1899,
            death_year=1937,
            region="Чуйская область",
            district="Кара-Балта",
            occupation="Учитель",
            charge="Контрреволюционная агитация",
            arrest_date="1937-08-12",
            sentence="Расстрел",
            sentence_date="1937-11-03",
            rehabilitation_date="1958-04-15",
            biography="Учитель. Реабилитирован в 1958 году.",
            source="seed",
            status="verified",
            search_text="Байтемиров Асан Жумабекович. Учитель. Реабилитирован в 1958 году.",
            raw_payload={},
        ),
    ]

    scored = search_person_records(
        query_text="Почему некоторых реабилитировали только в 1989 году?",
        persons=persons,
        top_k=1,
    )

    assert len(scored) == 1
    assert scored[0].person_id == 8


def test_resolve_person_candidates_prefers_surname_over_patronymic_similarity() -> None:
    persons = [
        RetrievedPersonRecord(
            person_id=2,
            full_name="Сыдыкова Бурул Токтогуловна",
            normalized_name="сыдыкова бурул токтогуловна",
            birth_year=1905,
            death_year=1943,
            region="Ошская область",
            district="Ош",
            occupation="Врач",
            charge="Шпионаж",
            arrest_date=None,
            sentence=None,
            sentence_date=None,
            rehabilitation_date=None,
            biography=None,
            source="seed",
            status="verified",
            search_text="Сыдыкова Бурул Токтогуловна",
            raw_payload={},
        ),
        RetrievedPersonRecord(
            person_id=3,
            full_name="Токтогулов Качкынбай Асанович",
            normalized_name="токтогулов качкынбай асанович",
            birth_year=1892,
            death_year=1938,
            region="Иссык-Кульская область",
            district="Каракол",
            occupation="Председатель колхоза",
            charge="Контрреволюционная организация",
            arrest_date=None,
            sentence=None,
            sentence_date=None,
            rehabilitation_date=None,
            biography=None,
            source="seed",
            status="verified",
            search_text="Токтогулов Качкынбай Асанович",
            raw_payload={},
        ),
    ]

    resolved = resolve_person_candidates(
        candidate_names=["Токтогулова"],
        persons=persons,
        entities=[],
    )

    assert resolved is not None
    assert resolved.person_id == 3
