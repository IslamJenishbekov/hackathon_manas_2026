from dataclasses import dataclass

from app.schemas.api import GetInfoPluralResponse, GetInfoRequest, GetInfoSingleResponse
from app.schemas.extraction import (
    GetInfoClassification,
    GetInfoPluralLLMOutput,
    GetInfoSingleLLMOutput,
    PersonCardLocalized,
)
from app.services.normalization import (
    coalesce_canonical_name,
    compute_missing_fields,
    dedupe_preserve_order,
    merge_warnings,
    normalize_person_name,
    sync_invariant_fields,
)
from app.services.openai_client import OpenAIParseError, OpenAIStructuredClient
from app.services.prompt_renderer import PromptRenderer


class ServiceValidationError(ValueError):
    pass


class UpstreamServiceError(RuntimeError):
    pass


@dataclass
class GetInfoService:
    prompt_renderer: PromptRenderer
    openai_client: OpenAIStructuredClient
    model: str

    def handle(self, request: GetInfoRequest) -> GetInfoSingleResponse | GetInfoPluralResponse:
        text = request.text.strip()
        if len(text.split()) < 2 and len(text) < 20:
            raise ServiceValidationError("text is too short to analyze")

        classification = self._classify(text)
        if classification.type == "single":
            return self._handle_single(text, classification)
        return self._handle_plural(text, classification)

    def _classify(self, text: str) -> GetInfoClassification:
        try:
            return self.openai_client.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.prompt_renderer.render(
                            "get_info/classify_system.j2",
                            {},
                        ),
                    },
                    {
                        "role": "user",
                        "content": self.prompt_renderer.render(
                            "get_info/classify_user.j2",
                            {"text": text},
                        ),
                    },
                ],
                response_model=GetInfoClassification,
            )
        except OpenAIParseError as exc:
            raise UpstreamServiceError("failed to classify document type") from exc

    def _handle_single(
        self,
        text: str,
        classification: GetInfoClassification,
    ) -> GetInfoSingleResponse:
        try:
            parsed: GetInfoSingleLLMOutput = self.openai_client.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.prompt_renderer.render(
                            "get_info/single_system.j2",
                            {},
                        ),
                    },
                    {
                        "role": "user",
                        "content": self.prompt_renderer.render(
                            "get_info/single_user.j2",
                            {"text": text},
                        ),
                    },
                ],
                response_model=GetInfoSingleLLMOutput,
            )
        except OpenAIParseError as exc:
            raise UpstreamServiceError("failed to extract single-person document info") from exc

        cards: dict[str, PersonCardLocalized] = {
            "ky": parsed.ky,
            "ru": parsed.ru,
            "en": parsed.en,
            "tr": parsed.tr,
        }

        canonical_name = coalesce_canonical_name(cards)
        normalized_name = normalize_person_name(canonical_name)
        for card in cards.values():
            card.normalized_name = normalized_name

        service_warnings = sync_invariant_fields(cards)
        missing_fields = compute_missing_fields(cards)
        warnings = merge_warnings(classification.warnings, parsed.warnings, service_warnings)

        return GetInfoSingleResponse(
            type="single",
            result=cards,
            missing_fields=missing_fields,
            warnings=warnings,
        )

    def _handle_plural(
        self,
        text: str,
        classification: GetInfoClassification,
    ) -> GetInfoPluralResponse:
        try:
            parsed: GetInfoPluralLLMOutput = self.openai_client.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.prompt_renderer.render(
                            "get_info/plural_system.j2",
                            {},
                        ),
                    },
                    {
                        "role": "user",
                        "content": self.prompt_renderer.render(
                            "get_info/plural_user.j2",
                            {"text": text},
                        ),
                    },
                ],
                response_model=GetInfoPluralLLMOutput,
            )
        except OpenAIParseError as exc:
            raise UpstreamServiceError("failed to extract plural document names") from exc

        normalized_names = dedupe_preserve_order(
            [
                normalized_name
                for raw_name in parsed.names
                if (normalized_name := normalize_person_name(raw_name)) is not None
            ]
        )
        warnings = merge_warnings(classification.warnings, parsed.warnings)

        return GetInfoPluralResponse(
            type="plural",
            normalized_names=normalized_names,
            warnings=warnings,
        )

