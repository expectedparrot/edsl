"""Spoken languages for LiveKit voice interviews (stored on humanize_schema).

Mirrors the server-side list so EDSL can validate
``humanize_schema.questions[...].voice_interview_config.language`` before a
survey is humanized. Keep this set in sync with the Coopr backend's
``voice_interview_languages`` module.
"""

from __future__ import annotations

DEFAULT_VOICE_INTERVIEW_LANGUAGE = "english"

# Lowercase language ids stored in humanize_schema.voice_interview_config.language.
VOICE_INTERVIEW_LANGUAGES: frozenset[str] = frozenset(
    {
        "english",
        "french",
        "german",
        "spanish",
        "portuguese",
        "chinese",
        "japanese",
        "hindi",
        "italian",
        "korean",
        "dutch",
        "polish",
        "russian",
        "swedish",
        "turkish",
        "tagalog",
        "bulgarian",
        "romanian",
        "arabic",
        "czech",
        "greek",
        "finnish",
        "croatian",
        "malay",
        "slovak",
        "danish",
        "tamil",
        "ukrainian",
        "hungarian",
        "norwegian",
        "vietnamese",
        "bengali",
        "thai",
        "hebrew",
        "georgian",
        "indonesian",
        "telugu",
        "gujarati",
        "kannada",
        "malayalam",
        "marathi",
        "punjabi",
        "multilingual",
    }
)


def normalize_voice_interview_language(raw: object) -> str:
    """Normalize a stored language value to its canonical lowercase id.

    None or blank falls back to the default; any other value must be a string
    naming a supported language (case- and whitespace-insensitive). Raises
    ``ValueError`` for non-strings or unsupported languages.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return DEFAULT_VOICE_INTERVIEW_LANGUAGE
    if not isinstance(raw, str):
        raise ValueError("voice_interview_config.language must be a string")
    key = raw.strip().lower()
    if key not in VOICE_INTERVIEW_LANGUAGES:
        raise ValueError(f"Unsupported voice interview language: {raw!r}")
    return key
