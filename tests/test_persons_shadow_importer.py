import json

from app.services.index_store import SQLiteIndexStore
from app.services.persons_shadow_importer import PersonsShadowImporter


def test_importer_persists_person_cards_with_search_text(tmp_path) -> None:
    db_path = str(tmp_path / "shadow.db")
    store = SQLiteIndexStore(db_path)
    importer = PersonsShadowImporter(store)

    payload = [
        {
            "id": 11,
            "full_name": "Алымкулов Курман Сатыбалдиевич",
            "birth_year": 1896,
            "death_year": 1938,
            "region": "Джалал-Абадская область",
            "district": "Токтогул",
            "occupation": "Сказитель (манасчи)",
            "charge": "Националистическая пропаганда (ст. 58-10)",
            "arrest_date": "1937-09-14",
            "sentence": "Расстрел",
            "sentence_date": "1938-01-07",
            "rehabilitation_date": "1957-12-19",
            "biography": "Известный манасчи. Обвинён за исполнение эпоса Манас.",
            "source": "seed",
            "status": "verified",
        }
    ]
    json_path = tmp_path / "seed.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    imported = importer.import_json_file(json_path)

    assert imported == 1
    persons = store.get_person_records()
    assert len(persons) == 1
    assert persons[0].normalized_name == "алымкулов курман сатыбалдиевич"
    assert "манасчи" in persons[0].search_text.lower()
