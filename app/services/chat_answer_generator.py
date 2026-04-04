import json
from dataclasses import dataclass
from urllib import error, request

from app.schemas.chat import ChatAnswerDraft
from app.services.openai_client import OpenAIParseError, OpenAIStructuredClient


class ChatAnswerGenerationError(RuntimeError):
    pass


class ChatAnswerGenerator:
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


@dataclass
class OpenAIChatAnswerGenerator(ChatAnswerGenerator):
    openai_client: OpenAIStructuredClient
    model: str

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        try:
            draft: ChatAnswerDraft = self.openai_client.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                response_model=ChatAnswerDraft,
            )
        except OpenAIParseError as exc:
            raise ChatAnswerGenerationError("failed to generate chat answer via OpenAI") from exc

        answer = draft.answer.strip()
        if not answer:
            raise ChatAnswerGenerationError("OpenAI returned an empty chat answer")
        return answer


@dataclass
class OllamaChatAnswerGenerator(ChatAnswerGenerator):
    base_url: str
    model: str
    timeout_seconds: float

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
        }
        endpoint = f"{self.base_url.rstrip('/')}/api/generate"
        request_body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw_payload = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace").strip()
            detail = error_body or str(exc.reason)
            raise ChatAnswerGenerationError(
                f"Ollama request failed with status {exc.code}: {detail}"
            ) from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise ChatAnswerGenerationError(f"failed to call Ollama: {exc}") from exc

        try:
            parsed_payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ChatAnswerGenerationError("Ollama returned invalid JSON") from exc

        answer = parsed_payload.get("response")
        if not isinstance(answer, str) or not answer.strip():
            raise ChatAnswerGenerationError("Ollama returned an empty chat answer")
        return answer.strip()
