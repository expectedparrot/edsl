"""Parameter validation for language models."""

import warnings
from typing import Any, Optional

# Known parameters for different services
# These are the standard parameters that APIs actually use
KNOWN_PARAMETERS = {
    "openai": {
        "temperature", "max_tokens", "top_p", "frequency_penalty",
        "presence_penalty", "stop", "n", "stream", "logprobs",
        "echo", "seed", "suffix", "user", "functions", "function_call",
        "tools", "tool_choice", "response_format", "logit_bias",
        "top_logprobs", "max_completion_tokens"
    },
    "anthropic": {
        "temperature", "max_tokens", "top_p", "top_k", "stop_sequences",
        "stream", "metadata"
    },
    "google": {
        "temperature", "max_output_tokens", "top_p", "top_k",
        "candidate_count", "stop_sequences"
    },
    "azure": {
        # Azure uses OpenAI parameters
        "temperature", "max_tokens", "top_p", "frequency_penalty",
        "presence_penalty", "stop", "n", "stream", "logprobs",
        "user", "functions", "function_call", "tools", "tool_choice"
    },
    "together": {
        "temperature", "max_tokens", "top_p", "top_k", "stop",
        "repetition_penalty", "stream"
    },
    "groq": {
        "temperature", "max_tokens", "top_p", "stop", "stream",
        "seed", "frequency_penalty", "presence_penalty"
    },
    "mistral": {
        "temperature", "max_tokens", "top_p", "random_seed", "safe_mode"
    },
    "bedrock": {
        "temperature", "max_tokens", "top_p", "top_k", "stop_sequences"
    },
    "replicate": {
        "temperature", "max_tokens", "top_p", "top_k", "repetition_penalty"
    },
    "deep_infra": {
        "temperature", "max_tokens", "top_p", "frequency_penalty",
        "presence_penalty", "stop"
    }
}

# Parameters that EDSL uses internally (not passed to APIs)
INTERNAL_PARAMETERS = {
    "canned_response", "skip_api_key_check", "use_cache", "remote",
    "rpm", "tpm", "omit_system_prompt_if_empty", "omit_system_prompt_if_empty_string"
}

# Common typos and their corrections
COMMON_TYPOS = {
    "temp": "temperature",
    "temprature": "temperature",
    "temperture": "temperature",
    "max_token": "max_tokens",
    "maxtoken": "max_tokens",
    "maxtokens": "max_tokens",
    "top-p": "top_p",
    "top-k": "top_k",
    "frequencypenalty": "frequency_penalty",
    "presencepenalty": "presence_penalty",
}

def validate_parameters(
    kwargs: dict[str, Any],
    service_name: Optional[str] = None,
    standard_parameters: Optional[set[str]] = None,
    strict: bool = False
) -> dict[str, Any]:
    """
    Validate parameters for language model initialization.

    Args:
        kwargs: The keyword arguments passed to the model
        service_name: The name of the service (e.g., 'openai', 'anthropic')
        standard_parameters: Set of parameters already handled by the model
        strict: If True, raise errors for unknown parameters. If False, issue warnings.

    Returns:
        The validated kwargs dictionary

    Raises:
        ValueError: If strict=True and unknown parameters are found
    """
    if standard_parameters is None:
        standard_parameters = set()

    # Get known parameters for this service
    if service_name:
        service_name_lower = service_name.lower()
        known_params = KNOWN_PARAMETERS.get(service_name_lower, set())
    else:
        # If no service specified, use union of all known parameters
        known_params = set()
        for params in KNOWN_PARAMETERS.values():
            known_params.update(params)

    # Add internal parameters and standard parameters
    all_valid_params = known_params | INTERNAL_PARAMETERS | standard_parameters

    # Check for unknown parameters
    unknown_params = []
    suggestions = {}

    for key in kwargs:
        if key not in all_valid_params:
            # Check if it's a common typo
            if key.lower() in COMMON_TYPOS:
                suggestions[key] = COMMON_TYPOS[key.lower()]
            else:
                # Check for close matches (case-insensitive)
                key_lower = key.lower()
                for valid_param in all_valid_params:
                    if key_lower == valid_param.lower():
                        suggestions[key] = valid_param
                        break
                else:
                    unknown_params.append(key)

    # Handle validation results
    if unknown_params or suggestions:
        message_parts = []

        if suggestions:
            for typo, correct in suggestions.items():
                message_parts.append(
                    f"  '{typo}' might be a typo. Did you mean '{correct}'?"
                )

        if unknown_params:
            if service_name:
                message_parts.append(
                    f"  Unknown parameters for {service_name}: {', '.join(unknown_params)}"
                )
            else:
                message_parts.append(
                    f"  Unknown parameters: {', '.join(unknown_params)}"
                )
            message_parts.append(
                "  These parameters will be ignored and have no effect."
            )

        full_message = "Parameter validation issues:\n" + "\n".join(message_parts)

        if strict:
            raise ValueError(full_message)
        warnings.warn(full_message, UserWarning, stacklevel=3)

    return kwargs

def get_valid_parameters(service_name: Optional[str] = None) -> set[str]:
    """
    Get the set of valid parameters for a given service.

    Args:
        service_name: The name of the service (e.g., 'openai', 'anthropic')

    Returns:
        Set of valid parameter names
    """
    if service_name:
        service_name_lower = service_name.lower()
        known_params = KNOWN_PARAMETERS.get(service_name_lower, set())
    else:
        # Return union of all known parameters
        known_params = set()
        for params in KNOWN_PARAMETERS.values():
            known_params.update(params)

    return known_params | INTERNAL_PARAMETERS
