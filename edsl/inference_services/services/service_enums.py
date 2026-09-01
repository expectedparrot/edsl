import re

OPENAI_REASONING_MODELS = [
    "o1",
    "o1-mini",
    "o3",
    "o3-mini",
    "o1-pro",
    "o4-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5.1",
    "gpt-5.5",
    "gpt-5.6",
]


def openai_requires_temperature_one(model_name: str) -> bool:
    """Return whether an OpenAI model only accepts ``temperature=1``.

    The o-series reasoning models (o1, o3, o4-mini, ...) and the GPT-5 and later
    generation (gpt-5, gpt-5.6, gpt-6, ...) reject any temperature other than 1,
    so we pin it regardless of the exact model id (dates/suffixes included).
    """
    name = model_name.lower()
    # o-series reasoning models: an "o" followed immediately by a digit.
    if re.match(r"o\d", name):
        return True
    # gpt-5 and later.
    gpt_match = re.match(r"gpt-(\d+)", name)
    if gpt_match and int(gpt_match.group(1)) >= 5:
        return True
    return False
