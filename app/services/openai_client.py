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

