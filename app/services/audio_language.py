SUPPORTED_AUDIO_LANGUAGES = {"ky", "ru", "tr", "en"}
KAZAKH_MARKERS = {"ә", "ғ", "қ", "һ", "і", "ұ"}
KYRGYZ_MARKERS = {"ң", "ө", "ү"}
TURKISH_MARKERS = {"ç", "ğ", "ı", "ö", "ş", "ü"}


def normalize_audio_language(value: str) -> str:
    return value.strip().lower()


def validate_supported_audio_language(value: str) -> str:
    normalized = normalize_audio_language(value)
    if normalized not in SUPPORTED_AUDIO_LANGUAGES:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_LANGUAGES))
        raise ValueError(f"unsupported language; supported languages: {supported}")
    return normalized


def detect_transcript_language(text: str) -> str:
    lowered = text.lower()

    if any(marker in lowered for marker in KAZAKH_MARKERS):
        return "kk"

    if any(marker in lowered for marker in TURKISH_MARKERS):
        return "tr"

    if _contains_latin(lowered):
        return "en"

    if _contains_cyrillic(lowered):
        if any(marker in lowered for marker in KYRGYZ_MARKERS):
            return "ky"
        return "ru"

    return "unknown"


def is_supported_transcript_language(text: str) -> bool:
    return detect_transcript_language(text) in SUPPORTED_AUDIO_LANGUAGES


def _contains_latin(text: str) -> bool:
    return any("a" <= char <= "z" for char in text)


def _contains_cyrillic(text: str) -> bool:
    return any("\u0400" <= char <= "\u04ff" for char in text)
