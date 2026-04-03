from app.schemas.api import GetInfoPluralResponse, GetInfoSingleResponse


def test_single_response_schema_accepts_contract_shape() -> None:
    payload = {
        "type": "single",
        "result": {
            "ky": {},
            "ru": {"full_name": "Байтемиров Асан Жумабекович"},
            "en": {},
            "tr": {},
        },
        "missing_fields": ["death_place"],
        "warnings": [],
    }
    parsed = GetInfoSingleResponse.model_validate(payload)
    assert parsed.type == "single"
    assert parsed.result["ru"].full_name == "Байтемиров Асан Жумабекович"


def test_plural_response_schema_accepts_contract_shape() -> None:
    payload = {
        "type": "plural",
        "normalized_names": ["сыдыкова бурул токтогуловна"],
        "warnings": [],
    }
    parsed = GetInfoPluralResponse.model_validate(payload)
    assert parsed.type == "plural"
    assert parsed.normalized_names == ["сыдыкова бурул токтогуловна"]

