import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


ACCURACY_SCORES = {
    "incorrect": 0.0,
    "partial": 0.5,
    "correct": 1.0,
}

QUESTION_BLOCK_PATTERN = re.compile(
    r"^###\s+(?P<id>\d+)\.\s+(?P<question>.+?)\n(?P<body>.*?)(?=^###\s+\d+\.|\Z)",
    re.MULTILINE | re.DOTALL,
)
EXPECTED_PATTERNS = (
    re.compile(r"\*\*Ожидаемый ответ:\*\*\s*(?P<answer>.+)", re.DOTALL),
    re.compile(r"\*\*Күтүлгөн жооп:\*\*\s*(?P<answer>.+)", re.DOTALL),
)


class ChatBenchmarkCase(BaseModel):
    id: int
    question: str
    expected_answer: str


class ChatBenchmarkRunCase(BaseModel):
    id: int
    question: str
    expected_answer: str
    actual_answer: str
    source_document_ids: list[int] = Field(default_factory=list)


class ChatBenchmarkRun(BaseModel):
    answer_provider: str
    provider_model: str | None = None
    api_url: str
    generated_at: str
    cases: list[ChatBenchmarkRunCase]


class AccuracyEvaluation(BaseModel):
    label: Literal["incorrect", "partial", "correct"]
    reason: str


class HumanLikenessEvaluation(BaseModel):
    score: int = Field(ge=1, le=5)
    reason: str


class ChatJudgeEvaluation(BaseModel):
    accuracy: AccuracyEvaluation
    human_likeness: HumanLikenessEvaluation


class ChatBenchmarkMetricsCase(BaseModel):
    id: int
    question: str
    expected_answer: str
    actual_answer: str
    source_document_ids: list[int] = Field(default_factory=list)
    accuracy_label: Literal["incorrect", "partial", "correct"]
    accuracy_score: float
    accuracy_reason: str
    human_likeness_score: int = Field(ge=1, le=5)
    human_likeness_reason: str


class ChatBenchmarkMetricsSummary(BaseModel):
    total_cases: int
    accuracy_avg: float
    human_likeness_avg: float


class ChatBenchmarkMetrics(BaseModel):
    judge_provider: str
    judge_model: str
    judged_at: str
    input_file: str
    summary: ChatBenchmarkMetricsSummary
    cases: list[ChatBenchmarkMetricsCase]


def load_chat_benchmark_cases(markdown_path: str | Path) -> list[ChatBenchmarkCase]:
    content = Path(markdown_path).read_text(encoding="utf-8")
    cases: list[ChatBenchmarkCase] = []

    for match in QUESTION_BLOCK_PATTERN.finditer(content):
        case_id = int(match.group("id"))
        question = match.group("question").strip()
        body = match.group("body").strip()

        expected_answer = _extract_expected_answer(body)
        cases.append(
            ChatBenchmarkCase(
                id=case_id,
                question=question,
                expected_answer=expected_answer,
            )
        )

    if not cases:
        raise ValueError(f"no benchmark cases found in {markdown_path}")
    return cases


def build_metrics_summary(cases: list[ChatBenchmarkMetricsCase]) -> ChatBenchmarkMetricsSummary:
    if not cases:
        return ChatBenchmarkMetricsSummary(
            total_cases=0,
            accuracy_avg=0.0,
            human_likeness_avg=0.0,
        )

    accuracy_avg = sum(case.accuracy_score for case in cases) / len(cases)
    human_likeness_avg = sum(case.human_likeness_score for case in cases) / len(cases)
    return ChatBenchmarkMetricsSummary(
        total_cases=len(cases),
        accuracy_avg=round(accuracy_avg, 4),
        human_likeness_avg=round(human_likeness_avg, 4),
    )


def map_accuracy_label_to_score(label: Literal["incorrect", "partial", "correct"]) -> float:
    return ACCURACY_SCORES[label]


def _extract_expected_answer(block_body: str) -> str:
    for pattern in EXPECTED_PATTERNS:
        match = pattern.search(block_body)
        if match is None:
            continue
        answer = match.group("answer").strip()
        if answer:
            return answer

    raise ValueError("benchmark case is missing an expected answer")
