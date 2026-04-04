import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.chat_evaluation import (
    ChatBenchmarkMetrics,
    ChatBenchmarkMetricsCase,
    ChatBenchmarkRun,
    ChatJudgeEvaluation,
    build_metrics_summary,
    map_accuracy_label_to_score,
)
from app.services.openai_client import OpenAIStructuredClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Judge chat benchmark results and compute accuracy + human-likeness metrics."
    )
    parser.add_argument(
        "--input",
        default="docs/test_seed_chat_results_ollama.json",
        help="Path to the raw benchmark JSON file.",
    )
    parser.add_argument(
        "--output",
        default="docs/test_seed_chat_metrics_ollama.json",
        help="Where to save judge metrics.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="OpenAI model used as judge. Defaults to OPENAI_MODEL_CHAT.",
    )
    return parser.parse_args()


def judge_case(
    *,
    client: OpenAIStructuredClient,
    judge_model: str,
    question: str,
    expected_answer: str,
    actual_answer: str,
) -> ChatJudgeEvaluation:
    system_prompt = """
You evaluate archive question-answering outputs.

Return two judgments:
1. accuracy:
- correct: the answer captures the material facts from the expected answer and does not contradict them.
- partial: the answer gets some core facts right but omits important facts, is too vague, or has minor inaccuracies.
- incorrect: the answer is wrong, hallucinates, contradicts the expected answer, or misses most key facts.

2. human_likeness:
- score from 1 to 5.
- 1 means robotic, awkward, confusing, or badly phrased.
- 5 means natural, direct, concise, and appropriate for a human assistant.

Rules:
- Be strict about factual contradictions and hallucinations.
- Do not penalize wording differences when the meaning is preserved.
- Evaluate human_likeness only on the actual answer text, but accuracy must compare question + expected + actual.
""".strip()
    user_prompt = f"""
Question:
{question}

Expected answer:
{expected_answer}

Actual answer:
{actual_answer}
""".strip()
    return client.parse(
        model=judge_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=ChatJudgeEvaluation,
    )


def main() -> None:
    args = parse_args()
    settings = get_settings()
    judge_model = args.judge_model or settings.openai_model_chat

    raw_results = Path(args.input).read_text(encoding="utf-8")
    benchmark_run = ChatBenchmarkRun.model_validate_json(raw_results)

    client = OpenAIStructuredClient(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout_seconds=settings.request_timeout_seconds,
    )

    metric_cases = []
    for case in benchmark_run.cases:
        evaluation = judge_case(
            client=client,
            judge_model=judge_model,
            question=case.question,
            expected_answer=case.expected_answer,
            actual_answer=case.actual_answer,
        )
        metric_cases.append(
            ChatBenchmarkMetricsCase(
                id=case.id,
                question=case.question,
                expected_answer=case.expected_answer,
                actual_answer=case.actual_answer,
                source_document_ids=case.source_document_ids,
                accuracy_label=evaluation.accuracy.label,
                accuracy_score=map_accuracy_label_to_score(evaluation.accuracy.label),
                accuracy_reason=evaluation.accuracy.reason.strip(),
                human_likeness_score=evaluation.human_likeness.score,
                human_likeness_reason=evaluation.human_likeness.reason.strip(),
            )
        )

    metrics = ChatBenchmarkMetrics(
        judge_provider="openai",
        judge_model=judge_model,
        judged_at=datetime.now(timezone.utc).isoformat(),
        input_file=args.input,
        summary=build_metrics_summary(metric_cases),
        cases=metric_cases,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(metrics.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved judge metrics for {len(metric_cases)} cases to {output_path}")


if __name__ == "__main__":
    main()
