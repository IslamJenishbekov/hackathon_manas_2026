from app.services.chat_evaluation import (
    ChatBenchmarkMetricsCase,
    build_metrics_summary,
    load_chat_benchmark_cases,
    map_accuracy_label_to_score,
)


def test_load_chat_benchmark_cases_reads_seed_queries() -> None:
    cases = load_chat_benchmark_cases("docs/test-seed/queries.md")

    assert len(cases) == 15
    assert cases[0].id == 1
    assert cases[0].question == "За что арестовали Байтемирова?"
    assert "контрреволюционной агитации" in cases[0].expected_answer
    assert cases[-1].id == 15
    assert cases[-1].question == "Сыдыкова Бурул ким болгон?"


def test_build_metrics_summary_averages_scores() -> None:
    cases = [
        ChatBenchmarkMetricsCase(
            id=1,
            question="Q1",
            expected_answer="E1",
            actual_answer="A1",
            source_document_ids=[1],
            accuracy_label="correct",
            accuracy_score=map_accuracy_label_to_score("correct"),
            accuracy_reason="full match",
            human_likeness_score=5,
            human_likeness_reason="natural",
        ),
        ChatBenchmarkMetricsCase(
            id=2,
            question="Q2",
            expected_answer="E2",
            actual_answer="A2",
            source_document_ids=[2],
            accuracy_label="partial",
            accuracy_score=map_accuracy_label_to_score("partial"),
            accuracy_reason="some omissions",
            human_likeness_score=3,
            human_likeness_reason="acceptable",
        ),
    ]

    summary = build_metrics_summary(cases)

    assert summary.total_cases == 2
    assert summary.accuracy_avg == 0.75
    assert summary.human_likeness_avg == 4.0
