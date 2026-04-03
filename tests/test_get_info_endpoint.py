from fastapi.testclient import TestClient

from app.api.dependencies import get_get_info_service
from app.main import app
from app.schemas.api import GetInfoRequest
from app.schemas.extraction import GetInfoClassification, GetInfoPluralLLMOutput
from app.services.get_info_service import GetInfoService


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
