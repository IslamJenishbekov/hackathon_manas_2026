import base64
import json
from dataclasses import dataclass
from urllib import error, request


class LayoutParsingError(RuntimeError):
    pass


@dataclass
class LayoutParsingClient:
    base_url: str
    timeout_seconds: float
    file_type: int = 0
    visualize: bool = False

    def extract_text_from_pdf(self, *, file_bytes: bytes) -> str:
        payload = {
            "file": base64.b64encode(file_bytes).decode("ascii"),
            "fileType": self.file_type,
            "visualize": self.visualize,
        }
        endpoint = f"{self.base_url.rstrip('/')}/layout-parsing"
        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                content_type = (response.headers.get("Content-Type") or "").strip().lower()
                raw_payload = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace").strip()
            detail = error_body or str(exc.reason)
            raise LayoutParsingError(
                f"layout parsing request failed with status {exc.code}: {detail}"
            ) from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise LayoutParsingError(f"failed to call layout parsing service: {exc}") from exc

        text = self._extract_text(raw_payload=raw_payload, content_type=content_type)
        if not text:
            raise LayoutParsingError("layout parsing service returned an empty response")
        return text

    def _extract_text(self, *, raw_payload: str, content_type: str) -> str:
        normalized_content_type = content_type.split(";", 1)[0].strip().lower()
        stripped_payload = raw_payload.strip()

        if normalized_content_type == "application/json" or stripped_payload.startswith("{"):
            try:
                parsed_payload = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                raise LayoutParsingError("layout parsing service returned invalid JSON") from exc
            return self._extract_text_from_json(parsed_payload)

        return stripped_payload

    def _extract_text_from_json(self, payload: object) -> str:
        if isinstance(payload, str):
            return payload.strip()

        if not isinstance(payload, dict):
            raise LayoutParsingError("layout parsing service returned an unexpected JSON payload")

        error_code = payload.get("errorCode")
        if error_code not in (None, 0):
            error_message = payload.get("errorMsg") or "unknown error"
            raise LayoutParsingError(
                f"layout parsing service returned error {error_code}: {error_message}"
            )

        result = payload.get("result")
        if isinstance(result, str) and result.strip():
            return result.strip()

        if isinstance(result, dict):
            layout_results = result.get("layoutParsingResults")
            if isinstance(layout_results, list):
                for item in layout_results:
                    if not isinstance(item, dict):
                        continue

                    markdown = item.get("markdown")
                    if isinstance(markdown, dict):
                        text = markdown.get("text")
                        if isinstance(text, str) and text.strip():
                            return text.strip()

                    pruned_result = item.get("prunedResult")
                    if isinstance(pruned_result, dict):
                        blocks = pruned_result.get("parsing_res_list")
                        if isinstance(blocks, list):
                            block_texts = []
                            for block in blocks:
                                if not isinstance(block, dict):
                                    continue
                                block_text = block.get("block_content")
                                if isinstance(block_text, str) and block_text.strip():
                                    block_texts.append(block_text.strip())
                            if block_texts:
                                return "\n\n".join(block_texts)

            text = result.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

        raise LayoutParsingError("layout parsing service returned JSON without extracted text")
