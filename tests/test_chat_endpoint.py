from fastapi.testclient import TestClient

from app.api.dependencies import get_chat_service
from app.main import app


class FakeChatService:
    def handle(self, request):
        assert request.question == "За что его арестовали?"
        return {
            "answer": "Байтемиров был арестован по обвинению в контрреволюционной агитации...",
            "sources": [
                {
                    "document_id": 18,
                }
            ],
        }


def test_chat_endpoint_returns_full_sources_payload() -> None:
    app.dependency_overrides[get_chat_service] = lambda: FakeChatService()
    client = TestClient(app)

    response = client.post(
        "/ai/chat",
        json={
            "question": "За что его арестовали?",
            "history": [],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Байтемиров был арестован по обвинению в контрреволюционной агитации...",
        "sources": [
            {
                "document_id": 18,
            }
        ],
    }

    app.dependency_overrides.clear()
