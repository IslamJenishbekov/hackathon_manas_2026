from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr = Field(alias="OPENAI_API_KEY")
    openai_model_get_info: str = Field(default="gpt-5.4", alias="OPENAI_MODEL_GET_INFO")
    openai_model_pdf_ocr: str = Field(default="gpt-5.4", alias="OPENAI_MODEL_PDF_OCR")
    openai_model_chat: str = Field(default="gpt-5.4", alias="OPENAI_MODEL_CHAT")
    openai_model_voice_rewrite: str = Field(
        default="gpt-5.4",
        alias="OPENAI_MODEL_VOICE_REWRITE",
    )
    chat_answer_provider: Literal["openai", "ollama"] = Field(
        default="openai",
        alias="CHAT_ANSWER_PROVIDER",
    )
    ollama_base_url: str = Field(default="http://127.0.0.1:11435", alias="OLLAMA_BASE_URL")
    ollama_model_chat: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL_CHAT")
    openai_embedding_model: str = Field(
        default="text-embedding-3-large",
        alias="OPENAI_EMBEDDING_MODEL",
    )
    openai_tts_model: str = Field(default="tts-1-hd", alias="OPENAI_TTS_MODEL")
    openai_tts_voice: str = Field(default="alloy", alias="OPENAI_TTS_VOICE")
    openai_asr_model: str = Field(default="gpt-4o-transcribe", alias="OPENAI_ASR_MODEL")
    request_timeout_seconds: float = Field(default=90.0, alias="REQUEST_TIMEOUT_SECONDS")
    sqlite_db_path: str = Field(default="data/ai_index.db", alias="SQLITE_DB_PATH")
    chunk_size_chars: int = Field(default=800, alias="CHUNK_SIZE_CHARS")
    chunk_overlap_chars: int = Field(default=120, alias="CHUNK_OVERLAP_CHARS")
    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
