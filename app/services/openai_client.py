import base64
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError


class OpenAIParseError(RuntimeError):
    pass


class OpenAIStructuredClient:
    def __init__(self, api_key: str, timeout_seconds: float) -> None:
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)

    def parse(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        response_model: type[Any],
    ) -> Any:
        try:
            if hasattr(self._client.responses, "parse"):
                response = self._client.responses.parse(
                    model=model,
                    input=messages,
                    text_format=response_model,
                )
                parsed = getattr(response, "output_parsed", None)
                if parsed is None:
                    raise OpenAIParseError("OpenAI returned an empty parsed response")
                return parsed

            completion = self._client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=response_model,
            )
            message = completion.choices[0].message
            if getattr(message, "refusal", None):
                raise OpenAIParseError(f"OpenAI refusal: {message.refusal}")
            if message.parsed is None:
                raise OpenAIParseError("OpenAI returned an empty parsed response")
            return message.parsed
        except (APIConnectionError, APIStatusError, APITimeoutError, RateLimitError) as exc:
            raise OpenAIParseError(str(exc)) from exc

    def embed_texts(self, *, model: str, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            response = self._client.embeddings.create(model=model, input=texts)
        except (APIConnectionError, APIStatusError, APITimeoutError, RateLimitError) as exc:
            raise OpenAIParseError(str(exc)) from exc

        return [item.embedding for item in response.data]

    def synthesize_speech(
        self,
        *,
        model: str,
        voice: str,
        text: str,
        response_format: str = "mp3",
    ) -> bytes:
        try:
            response = self._client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format=response_format,
            )
        except (APIConnectionError, APIStatusError, APITimeoutError, RateLimitError) as exc:
            raise OpenAIParseError(str(exc)) from exc

        return response.content

    def transcribe_audio(
        self,
        *,
        model: str,
        file_name: str,
        file_bytes: bytes,
        content_type: str | None = None,
    ) -> str:
        try:
            response = self._client.audio.transcriptions.create(
                model=model,
                file=(file_name, file_bytes, content_type or "application/octet-stream"),
                response_format="json",
            )
        except (APIConnectionError, APIStatusError, APITimeoutError, RateLimitError) as exc:
            raise OpenAIParseError(str(exc)) from exc

        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise OpenAIParseError("OpenAI returned an empty transcription")
        return text.strip()

    def extract_text_from_pdf(
        self,
        *,
        model: str,
        file_name: str,
        file_bytes: bytes,
    ) -> str:
        encoded_bytes = base64.b64encode(file_bytes).decode("ascii")
        file_data = f"data:application/pdf;base64,{encoded_bytes}"

        try:
            response = self._client.responses.create(
                model=model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_file",
                                "filename": file_name,
                                "file_data": file_data,
                            },
                            {
                                "type": "input_text",
                                "text": (
                                    "Extract all readable text from this PDF in page order. "
                                    "Return only the extracted text. Do not summarize, "
                                    "translate, explain, normalize, or add markdown."
                                ),
                            },
                        ],
                    }
                ],
                store=False,
            )
        except (APIConnectionError, APIStatusError, APITimeoutError, RateLimitError) as exc:
            raise OpenAIParseError(str(exc)) from exc

        text = getattr(response, "output_text", None)
        if not isinstance(text, str) or not text.strip():
            raise OpenAIParseError("OpenAI returned an empty PDF extraction")
        return text.strip()
