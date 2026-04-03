from dataclasses import dataclass


@dataclass
class TextChunk:
    chunk_index: int
    text: str
    char_start: int
    char_end: int


def chunk_text(
    text: str,
    *,
    chunk_size: int,
    overlap: int,
) -> list[TextChunk]:
    cleaned = text.strip()
    if not cleaned:
        return []

    source = cleaned
    chunks: list[TextChunk] = []
    start = 0
    length = len(source)
    chunk_index = 0

    while start < length:
        hard_end = min(start + chunk_size, length)
        end = hard_end

        if hard_end < length:
            candidate = _find_breakpoint(source, start, hard_end)
            if candidate is not None and candidate > start:
                end = candidate

        segment = source[start:end]
        left_trim = len(segment) - len(segment.lstrip())
        right_trim = len(segment) - len(segment.rstrip())
        actual_start = start + left_trim
        actual_end = end - right_trim
        chunk_body = source[actual_start:actual_end]

        if chunk_body:
            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    text=chunk_body,
                    char_start=actual_start,
                    char_end=actual_end,
                )
            )
            chunk_index += 1

        if end >= length:
            break

        next_start = max(end - overlap, start + 1)
        start = next_start

    return chunks


def _find_breakpoint(text: str, start: int, end: int) -> int | None:
    minimum = start + max((end - start) // 2, 1)
    breakpoint_patterns = ("\n\n", "\n", ". ", "! ", "? ", "; ", ": ", " | ")

    best_position: int | None = None
    for pattern in breakpoint_patterns:
        position = text.rfind(pattern, minimum, end)
        if position != -1:
            candidate = position + len(pattern.rstrip())
            if best_position is None or candidate > best_position:
                best_position = candidate

    return best_position

