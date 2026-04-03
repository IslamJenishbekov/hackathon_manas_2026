from dataclasses import dataclass

from app.schemas.api import (
    GetInfoPluralResponse,
    GetInfoRequest,
    GetInfoSingleResponse,
    SaveDocRequest,
    SaveDocResponse,
)
from app.services.chunking import chunk_text
from app.services.get_info_service import (
    GetInfoService,
    ServiceValidationError,
    UpstreamServiceError,
)
from app.services.index_store import (
    IndexChunkRecord,
    IndexDocumentRecord,
    IndexEntityRecord,
    SQLiteIndexStore,
)
from app.services.openai_client import OpenAIParseError, OpenAIStructuredClient


@dataclass
class SaveDocService:
    get_info_service: GetInfoService
    openai_client: OpenAIStructuredClient
    index_store: SQLiteIndexStore
    embedding_model: str
    chunk_size: int
    chunk_overlap: int

    def handle(self, request: SaveDocRequest) -> SaveDocResponse:
        analysis = self.get_info_service.analyze(GetInfoRequest(text=request.text))

        chunks = chunk_text(
            request.text,
            chunk_size=self.chunk_size,
            overlap=self.chunk_overlap,
        )
        if not chunks:
            raise ServiceValidationError("text produced no indexable chunks")

        try:
            embeddings = self.openai_client.embed_texts(
                model=self.embedding_model,
                texts=[chunk.text for chunk in chunks],
            )
        except OpenAIParseError as exc:
            raise UpstreamServiceError("failed to create document embeddings") from exc

        if len(embeddings) != len(chunks):
            raise UpstreamServiceError("embedding count does not match chunk count")

        document_record, entity_records = self._build_document_records(request, analysis)
        chunk_records = [
            IndexChunkRecord(
                document_id=request.document_id,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                embedding=embedding,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        document_record.chunk_count = len(chunk_records)

        self.index_store.reindex_document(document_record, entity_records, chunk_records)
        return SaveDocResponse(status="ok")

    def _build_document_records(
        self,
        request: SaveDocRequest,
        analysis: GetInfoSingleResponse | GetInfoPluralResponse,
    ) -> tuple[IndexDocumentRecord, list[IndexEntityRecord]]:
        if isinstance(analysis, GetInfoSingleResponse):
            ru_card = analysis.result["ru"]
            document = IndexDocumentRecord(
                document_id=request.document_id,
                person_id=request.person_id,
                filename=request.filename,
                source_link=request.link,
                raw_text=request.text,
                doc_type="single",
                primary_full_name=ru_card.full_name,
                primary_normalized_name=ru_card.normalized_name,
                primary_birth_year=ru_card.birth_year,
                primary_region=ru_card.region,
                primary_charge=ru_card.charge,
                embedding_model=self.embedding_model,
                chunk_count=0,
                warnings=analysis.warnings,
            )
            entities = []
            if ru_card.normalized_name:
                entities.append(
                    IndexEntityRecord(
                        document_id=request.document_id,
                        normalized_name=ru_card.normalized_name,
                        raw_name=ru_card.full_name,
                        birth_year=ru_card.birth_year,
                        role="primary",
                    )
                )
            return document, entities

        document = IndexDocumentRecord(
            document_id=request.document_id,
            person_id=request.person_id,
            filename=request.filename,
            source_link=request.link,
            raw_text=request.text,
            doc_type="plural",
            primary_full_name=None,
            primary_normalized_name=None,
            primary_birth_year=None,
            primary_region=None,
            primary_charge=None,
            embedding_model=self.embedding_model,
            chunk_count=0,
            warnings=analysis.warnings,
        )
        entities = [
            IndexEntityRecord(
                document_id=request.document_id,
                normalized_name=name,
                raw_name=None,
                birth_year=None,
                role="mentioned",
            )
            for name in analysis.normalized_names
        ]
        return document, entities
