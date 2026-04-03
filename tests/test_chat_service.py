from pathlib import Path

from app.schemas.api import ChatRequest
from app.schemas.chat import ChatAnswerDraft, ChatQueryAnalysis
from app.services.chat_service import ChatService
from app.services.index_store import SQLiteIndexStore
from app.services.save_doc_service import SaveDocService


class FakePromptRenderer:
    def render(self, template_name: str, context: dict[str, object]) -> str:
        return f"{template_name}:{context}"


class FakeGetInfoServiceSingle:
    def analyze(self, _request):
        from app.schemas.api import GetInfoSingleResponse
        from app.schemas.extraction import PersonCardLocalized

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
            warnings=[],
        )


class FakeOpenAIClient:
    def parse(self, *, model: str, messages: list[dict[str, object]], response_model: type[object]) -> object:
        name = response_model.__name__
        if name == "ChatQueryAnalysis":
            return ChatQueryAnalysis(mode="person", candidate_names=["Байтемиров"], warnings=[])
        if name == "ChatAnswerDraft":
            return ChatAnswerDraft(answer="Байтемиров был арестован по обвинению в контрреволюционной агитации.")
        raise AssertionError(f"unexpected structured parse for {name}")

    def embed_texts(self, *, model: str, texts: list[str]) -> list[list[float]]:
        if len(texts) == 1:
            return [[1.0, 0.0]]
        return [[1.0, 0.0] if "контрреволюционной агитации" in text else [0.0, 1.0] for text in texts]


class FakeOpenAIClientUnknownPerson(FakeOpenAIClient):
    def parse(self, *, model: str, messages: list[dict[str, object]], response_model: type[object]) -> object:
        name = response_model.__name__
        if name == "ChatQueryAnalysis":
            return ChatQueryAnalysis(mode="person", candidate_names=["Месси"], warnings=[])
        return super().parse(model=model, messages=messages, response_model=response_model)


def build_index(tmp_path) -> SQLiteIndexStore:
    db_path = str(tmp_path / "chat_index.db")
    store = SQLiteIndexStore(db_path)
    save_doc_service = SaveDocService(
        get_info_service=FakeGetInfoServiceSingle(),
        openai_client=FakeOpenAIClient(),
        index_store=store,
        embedding_model="test-embedding-model",
        chunk_size=120,
        chunk_overlap=20,
    )
    text = Path("docs/test-seed/test_data/test_data/documents/delo_baytemirova.txt").read_text(
        encoding="utf-8"
    )
    save_doc_service.handle(
        request=__import__("app.schemas.api", fromlist=["SaveDocRequest"]).SaveDocRequest(
            person_id=1,
            document_id=4412,
            filename="delo_baytemirova.txt",
            link="https://archive.example/documents/4412",
            text=text,
        )
    )
    return store


def test_chat_service_returns_answer_with_sources(tmp_path) -> None:
    store = build_index(tmp_path)
    service = ChatService(
        prompt_renderer=FakePromptRenderer(),
        openai_client=FakeOpenAIClient(),
        index_store=store,
        model="test-chat-model",
        embedding_model="test-embedding-model",
        retrieval_top_k=2,
    )

    response = service.handle(ChatRequest(question="За что арестовали Байтемирова?"))

    assert "контрреволюционной агитации" in response.answer
    assert len(response.sources) == 2
    assert all(source.document_id == 4412 for source in response.sources)


def test_chat_service_returns_archive_not_found_for_unknown_person(tmp_path) -> None:
    store = build_index(tmp_path)
    service = ChatService(
        prompt_renderer=FakePromptRenderer(),
        openai_client=FakeOpenAIClientUnknownPerson(),
        index_store=store,
        model="test-chat-model",
        embedding_model="test-embedding-model",
        retrieval_top_k=2,
    )

    response = service.handle(ChatRequest(question="Кто такой Месси?"))

    assert response.answer == "Я не смог найти такую информацию в архивах."
    assert response.sources == []
