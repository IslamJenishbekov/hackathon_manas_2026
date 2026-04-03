from functools import lru_cache

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.asr_service import ASRService
from app.services.chat_service import ChatService
from app.services.fact_of_day_service import FactOfDayService
from app.services.get_info_service import GetInfoService
from app.services.index_store import SQLiteIndexStore
from app.services.openai_client import OpenAIStructuredClient
from app.services.pdf_ocr_service import PDFOCRService
from app.services.prompt_renderer import PromptRenderer
from app.services.save_doc_service import SaveDocService
from app.services.voice_service import VoiceService


@lru_cache
def get_prompt_renderer() -> PromptRenderer:
    return PromptRenderer()


def get_openai_client(settings: Settings = Depends(get_settings)) -> OpenAIStructuredClient:
    return OpenAIStructuredClient(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout_seconds=settings.request_timeout_seconds,
    )


@lru_cache
def get_index_store_cached(db_path: str) -> SQLiteIndexStore:
    return SQLiteIndexStore(db_path)


def get_index_store(settings: Settings = Depends(get_settings)) -> SQLiteIndexStore:
    return get_index_store_cached(settings.sqlite_db_path)


def get_get_info_service(
    settings: Settings = Depends(get_settings),
    prompt_renderer: PromptRenderer = Depends(get_prompt_renderer),
    openai_client: OpenAIStructuredClient = Depends(get_openai_client),
    index_store: SQLiteIndexStore = Depends(get_index_store),
) -> GetInfoService:
    return GetInfoService(
        prompt_renderer=prompt_renderer,
        openai_client=openai_client,
        model=settings.openai_model_get_info,
        index_store=index_store,
    )


def get_save_doc_service(
    settings: Settings = Depends(get_settings),
    get_info_service: GetInfoService = Depends(get_get_info_service),
    openai_client: OpenAIStructuredClient = Depends(get_openai_client),
    index_store: SQLiteIndexStore = Depends(get_index_store),
) -> SaveDocService:
    return SaveDocService(
        get_info_service=get_info_service,
        openai_client=openai_client,
        index_store=index_store,
        embedding_model=settings.openai_embedding_model,
        chunk_size=settings.chunk_size_chars,
        chunk_overlap=settings.chunk_overlap_chars,
    )


def get_pdf_ocr_service(
    settings: Settings = Depends(get_settings),
    openai_client: OpenAIStructuredClient = Depends(get_openai_client),
) -> PDFOCRService:
    return PDFOCRService(
        openai_client=openai_client,
        model=settings.openai_model_pdf_ocr,
    )


def get_chat_service(
    settings: Settings = Depends(get_settings),
    prompt_renderer: PromptRenderer = Depends(get_prompt_renderer),
    openai_client: OpenAIStructuredClient = Depends(get_openai_client),
    index_store: SQLiteIndexStore = Depends(get_index_store),
) -> ChatService:
    return ChatService(
        prompt_renderer=prompt_renderer,
        openai_client=openai_client,
        index_store=index_store,
        model=settings.openai_model_chat,
        embedding_model=settings.openai_embedding_model,
        retrieval_top_k=settings.retrieval_top_k,
    )


def get_fact_of_day_service(
    index_store: SQLiteIndexStore = Depends(get_index_store),
) -> FactOfDayService:
    return FactOfDayService(index_store=index_store)


def get_voice_service(
    settings: Settings = Depends(get_settings),
    prompt_renderer: PromptRenderer = Depends(get_prompt_renderer),
    openai_client: OpenAIStructuredClient = Depends(get_openai_client),
) -> VoiceService:
    return VoiceService(
        prompt_renderer=prompt_renderer,
        openai_client=openai_client,
        rewrite_model=settings.openai_model_voice_rewrite,
        tts_model=settings.openai_tts_model,
        tts_voice=settings.openai_tts_voice,
    )


def get_asr_service(
    settings: Settings = Depends(get_settings),
    openai_client: OpenAIStructuredClient = Depends(get_openai_client),
) -> ASRService:
    return ASRService(
        openai_client=openai_client,
        model=settings.openai_asr_model,
    )
