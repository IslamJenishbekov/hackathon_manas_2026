from app.services.normalization import dedupe_preserve_order, normalize_person_name


def test_normalize_person_name_is_deterministic() -> None:
    assert (
        normalize_person_name(" Байтемиров   Асан Жумабекович ")
        == "байтемиров асан жумабекович"
    )


def test_dedupe_preserve_order_keeps_first_occurrence() -> None:
    assert dedupe_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]

