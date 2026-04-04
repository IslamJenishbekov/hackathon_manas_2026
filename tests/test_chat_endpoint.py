from app.api.routes.chat import chat
from app.schemas.api import ChatRequest, ChatResponse, ChatSource


class FakeChatService:
    def handle(self, request):
        assert request.question == "За что его арестовали?"
        return ChatResponse(
            answer="Байтемиров был арестован по обвинению в контрреволюционной агитации...",
            sources=[ChatSource(document_id=18)],
        )


def test_chat_endpoint_returns_full_sources_payload() -> None:
    response = chat(
        request=ChatRequest(
            question="За что его арестовали?",
            history=[],
        ),
        service=FakeChatService(),
    )

    assert response.model_dump() == {
        "answer": "Байтемиров был арестован по обвинению в контрреволюционной агитации...",
        "sources": [
            {
                "document_id": 18,
            }
        ],
    }
