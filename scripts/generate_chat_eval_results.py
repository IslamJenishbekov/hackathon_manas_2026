import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.chat_evaluation import ChatBenchmarkRun, ChatBenchmarkRunCase, load_chat_benchmark_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate chat benchmark answers and save them as JSON."
    )
    parser.add_argument(
        "--queries",
        default="docs/test-seed/queries.md",
        help="Path to the markdown file with benchmark questions.",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000/ai/chat",
        help="Chat endpoint URL.",
    )
    parser.add_argument(
        "--output",
        default="docs/test_seed_chat_results_ollama.json",
        help="Where to save raw benchmark answers.",
    )
    parser.add_argument(
        "--answer-provider",
        default="ollama",
        help="Label stored in the output JSON.",
    )
    parser.add_argument(
        "--provider-model",
        default="llama3.1:8b",
        help="Provider model label stored in the output JSON.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Per-request timeout in seconds.",
    )
    return parser.parse_args()


def call_chat_api(*, api_url: str, question: str, timeout: float) -> tuple[str, list[int]]:
    payload = {
        "question": question,
        "history": [],
    }
    http_request = request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            parsed_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace").strip()
        detail = error_body or str(exc.reason)
        raise RuntimeError(f"chat endpoint returned {exc.code}: {detail}") from exc
    except (error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"failed to call chat endpoint: {exc}") from exc

    answer = parsed_payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("chat endpoint returned an empty answer")

    raw_sources = parsed_payload.get("sources", [])
    source_document_ids = []
    for item in raw_sources:
        if not isinstance(item, dict):
            continue
        document_id = item.get("document_id")
        if isinstance(document_id, int):
            source_document_ids.append(document_id)

    return answer.strip(), source_document_ids


def main() -> None:
    args = parse_args()
    cases = load_chat_benchmark_cases(args.queries)

    results = []
    for case in cases:
        answer, source_document_ids = call_chat_api(
            api_url=args.api_url,
            question=case.question,
            timeout=args.timeout,
        )
        results.append(
            ChatBenchmarkRunCase(
                id=case.id,
                question=case.question,
                expected_answer=case.expected_answer,
                actual_answer=answer,
                source_document_ids=source_document_ids,
            )
        )

    run = ChatBenchmarkRun(
        answer_provider=args.answer_provider,
        provider_model=args.provider_model,
        api_url=args.api_url,
        generated_at=datetime.now(timezone.utc).isoformat(),
        cases=results,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(run.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved {len(results)} chat benchmark results to {output_path}")


if __name__ == "__main__":
    main()
