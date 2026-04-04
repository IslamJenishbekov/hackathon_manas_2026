from dataclasses import dataclass

from app.schemas.api import ChatRequest, ChatResponse, ChatSource
from app.schemas.chat import ChatQueryAnalysis
from app.services.chat_answer_generator import ChatAnswerGenerationError, ChatAnswerGenerator
from app.services.get_info_service import UpstreamServiceError
from app.services.index_store import RetrievedPersonRecord, SQLiteIndexStore
from app.services.openai_client import OpenAIParseError, OpenAIStructuredClient
from app.services.prompt_renderer import PromptRenderer
from app.services.retrieval import (
    resolve_person_candidates,
    score_chunks,
    search_person_records,
)


@dataclass
class ChatService:
    prompt_renderer: PromptRenderer
    openai_client: OpenAIStructuredClient
    answer_generator: ChatAnswerGenerator
    index_store: SQLiteIndexStore
    analysis_model: str
    embedding_model: str
    retrieval_top_k: int

    def handle(self, request: ChatRequest) -> ChatResponse:
        analysis = self._analyze_query(request)

        if analysis.mode == "ambiguous":
            return ChatResponse(
                answer=(
                    "Мне недостаточно контекста, чтобы точно понять, о ком или о чём вопрос. "
                    "Уточните имя человека или задайте вопрос подробнее."
                ),
                sources=[],
            )

        entities = self.index_store.get_entity_records()
        persons = self.index_store.get_person_records()

        scoped_document_ids: list[int] | None = None
        preferred_doc_types: list[str] | None = None
        support_profiles: list[RetrievedPersonRecord] = []

        if analysis.mode == "person":
            resolved = resolve_person_candidates(
                candidate_names=analysis.candidate_names,
                persons=persons,
                entities=entities,
            )
            if resolved is None:
                support_profiles = self._search_support_profiles(
                    request.question,
                    persons,
                    top_k=2,
                    minimum_score=0.4,
                )
                if len(support_profiles) == 1:
                    resolved = resolve_person_candidates(
                        candidate_names=[support_profiles[0].full_name],
                        persons=persons,
                        entities=entities,
                    )

            if resolved is None:
                if analysis.candidate_names:
                    return ChatResponse(
                        answer="Я не смог найти такую информацию в архивах.",
                        sources=[],
                    )
                return ChatResponse(
                    answer=(
                        "Я не смог уверенно определить, о каком человеке идёт речь. "
                        "Уточните, пожалуйста, имя."
                    ),
                    sources=[],
                )

            scoped_document_ids = self.index_store.find_related_document_ids(
                person_ids=[resolved.person_id] if resolved.person_id is not None else None,
                normalized_names=[resolved.normalized_name],
            )
            preferred_doc_types = ["single"]
            if resolved.person_id is not None:
                support_profiles = self.index_store.get_person_records(person_ids=[resolved.person_id])

        elif analysis.mode == "global":
            preferred_doc_types = ["plural"]
            if self._should_search_profiles_for_global_question(request.question):
                support_profiles = self._search_support_profiles(
                    request.question,
                    persons,
                    top_k=3,
                    minimum_score=0.28,
                )

        elif analysis.mode == "comparative":
            preferred_doc_types = ["plural"]
            resolved = resolve_person_candidates(
                candidate_names=analysis.candidate_names,
                persons=persons,
                entities=entities,
            )
            if resolved is not None:
                scoped_document_ids = self.index_store.find_related_document_ids(
                    person_ids=[resolved.person_id] if resolved.person_id is not None else None,
                    normalized_names=[resolved.normalized_name],
                )
                if resolved.person_id is not None:
                    support_profiles = self.index_store.get_person_records(person_ids=[resolved.person_id])
            else:
                support_profiles = self._search_support_profiles(
                    request.question,
                    persons,
                    top_k=3,
                    minimum_score=0.28,
                )

        chunks = self.index_store.get_chunks(document_ids=scoped_document_ids)

        if not chunks and not support_profiles:
            return ChatResponse(
                answer="В доступном контексте недостаточно данных, чтобы ответить на этот вопрос.",
                sources=[],
            )

        scored_chunks = []
        if chunks:
            try:
                question_embedding = self.openai_client.embed_texts(
                    model=self.embedding_model,
                    texts=[request.question],
                )[0]
            except OpenAIParseError as exc:
                raise UpstreamServiceError("failed to create question embedding") from exc

            scored_chunks = score_chunks(
                query_text=request.question,
                question_embedding=question_embedding,
                chunks=chunks,
                top_k=self.retrieval_top_k,
                preferred_doc_types=preferred_doc_types,
            )

        prompt_sources = [
            {
                "document_id": chunk.document_id,
                "quote_text": chunk.chunk_text,
                "link": chunk.source_link,
            }
            for chunk in scored_chunks
        ]
        sources = [ChatSource(document_id=chunk.document_id) for chunk in scored_chunks]

        if not sources and not support_profiles:
            return ChatResponse(
                answer="В доступном контексте недостаточно данных, чтобы ответить на этот вопрос.",
                sources=[],
            )

        system_prompt = self.prompt_renderer.render(
            "chat/answer_system.j2",
            {},
        )
        user_prompt = self.prompt_renderer.render(
            "chat/answer_user.j2",
            {
                "question": request.question,
                "history": request.history,
                "sources": prompt_sources,
                "profiles": support_profiles,
                "mode": analysis.mode,
            },
        )

        try:
            answer = self.answer_generator.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except ChatAnswerGenerationError as exc:
            raise UpstreamServiceError("failed to generate chat answer") from exc

        return ChatResponse(answer=answer, sources=sources)

    def _analyze_query(self, request: ChatRequest) -> ChatQueryAnalysis:
        try:
            return self.openai_client.parse(
                model=self.analysis_model,
                messages=[
                    {
                        "role": "system",
                        "content": self.prompt_renderer.render(
                            "chat/router_system.j2",
                            {},
                        ),
                    },
                    {
                        "role": "user",
                        "content": self.prompt_renderer.render(
                            "chat/router_user.j2",
                            {
                                "question": request.question,
                                "history": request.history,
                            },
                        ),
                    },
                ],
                response_model=ChatQueryAnalysis,
            )
        except OpenAIParseError as exc:
            raise UpstreamServiceError("failed to analyze chat question") from exc

    def _search_support_profiles(
        self,
        question: str,
        persons: list[RetrievedPersonRecord],
        *,
        top_k: int,
        minimum_score: float,
    ) -> list[RetrievedPersonRecord]:
        scored_profiles = search_person_records(
            query_text=question,
            persons=persons,
            top_k=top_k,
            minimum_score=minimum_score,
        )
        if not scored_profiles:
            return []

        selected_ids = [profile.person_id for profile in scored_profiles]
        records = self.index_store.get_person_records(person_ids=selected_ids)
        records_by_id = {record.person_id: record for record in records}
        return [records_by_id[profile.person_id] for profile in scored_profiles if profile.person_id in records_by_id]

    def _should_search_profiles_for_global_question(self, question: str) -> bool:
        normalized = question.lower().replace("ё", "е")
        if any(char.isdigit() for char in normalized):
            return True
        return any(
            marker in normalized
            for marker in (
                "реабилит",
                "актал",
                "кто такой",
                "кто такая",
                "ким болгон",
            )
        )
