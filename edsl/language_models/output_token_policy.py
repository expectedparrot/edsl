"""Offline, provider-independent output-budget policy.

Names identify known reasoning families; unrecognized model IDs remain unknown.
This deliberately does not query a remote catalog while constructing models.
"""

import re
import warnings

REASONING_OUTPUT_TOKENS = 16_000
DEFAULT_OUTPUT_TOKENS = 2_000
LOW_REASONING_OUTPUT_TOKENS = 4_000
TOKEN_LIMIT_PARAMETERS = ("max_tokens", "maxOutputTokens", "max_output_tokens")
_UNSET = object()


def reasoning_capability(model: str, parameters=None) -> bool | None:
    """Recognize reasoning families, including provider-prefixed model IDs."""
    name = (model or "").lower().rsplit("/", 1)[-1].removeprefix("azure:")
    parameters = parameters or {}
    thinking = parameters.get("thinking")
    if isinstance(thinking, dict) and thinking.get("type") in ("enabled", "adaptive"):
        return True
    budget = parameters.get("thinking_budget")
    if isinstance(budget, (int, float)) and budget > 0:
        return True
    if re.match(r"(?:o[134](?:-|$)|gpt-(?:[5-9]|[1-9]\d)(?:[.-]|$))", name):
        return True
    if re.search(
        r"(?:deepseek-r1|deepseek-reasoner|qwq|magistral|(?:^|-)reasoning(?:-|$)|(?:^|-)thinking(?:-|$)|sonar-reasoning)",
        name,
    ):
        return True
    if re.match(r"gemini-(?:2\.5|3(?:\.\d+)?)(?:-|$)", name):
        return True
    if re.match(r"(?:gpt-[34](?:[.-]|o)|gemini-[12]\.0(?:-|$))", name):
        return False
    return None


def resolve_output_token_limit(model: str, user_value=_UNSET, *, parameters=None):
    """An explicit value wins; otherwise use the central capability default."""
    if user_value is not _UNSET:
        return user_value
    return (
        REASONING_OUTPUT_TOKENS
        if reasoning_capability(model, parameters)
        else DEFAULT_OUTPUT_TOKENS
    )


def model_token_policy(model) -> dict:
    """Describe the effective value, including unknown reasoning capability."""
    parameters = model.parameters
    parameter = next((key for key in TOKEN_LIMIT_PARAMETERS if key in parameters), None)
    return {
        "model": model.model,
        "inference_service": model._inference_service_,
        "reasoning": reasoning_capability(model.model, parameters),
        "parameter": parameter,
        "effective_max_tokens": parameters.get(parameter),
    }


def token_limit_warnings(models, *, emit=False) -> list[str]:
    messages = []
    for model in models or []:
        policy = model_token_policy(model)
        limit = policy["effective_max_tokens"]
        if (
            policy["reasoning"]
            and isinstance(limit, (int, float))
            and limit < LOW_REASONING_OUTPUT_TOKENS
        ):
            message = (
                f"Reasoning model {model.model!r} ({model._inference_service_}) has "
                f"{policy['parameter']}={limit}. Reasoning tokens share the output "
                "budget and may leave no room for an answer. Increase the limit "
                "explicitly if needed; EDSL will not increase it automatically."
            )
            if message not in messages:
                messages.append(message)
                if emit:
                    warnings.warn(message, UserWarning, stacklevel=2)
    return messages
