"""Convenience factory for models served by OpenAI-compatible endpoints."""

from typing import Any, Optional, TYPE_CHECKING

from .model import Model

if TYPE_CHECKING:
    from .language_model import LanguageModel


def HostedModel(
    model_name: str,
    *,
    base_url: str,
    api_key_env: Optional[str] = None,
    **kwargs: Any,
) -> "LanguageModel":
    """Create a model backed by a hosted OpenAI-compatible endpoint.

    ``HostedModel`` is a convenience factory, not a separate model type. The
    returned object uses EDSL's registered ``openai_compatible`` inference
    service, so it shares that service's execution, error reporting, client
    lifecycle, and serialization behavior.

    Args:
        model_name: Model identifier understood by the hosted endpoint.
        base_url: OpenAI-compatible API root, conventionally ending in ``/v1``.
        api_key_env: Optional name of the environment variable containing the
            endpoint credential. The credential itself is never serialized.
        **kwargs: Ordinary model parameters such as ``temperature`` and
            ``max_tokens``.

    Returns:
        A regular EDSL language model configured for the endpoint.

    Examples:
        >>> model = HostedModel(
        ...     "my-model",
        ...     base_url="https://models.example.com/v1",
        ...     api_key_env="MY_MODEL_API_KEY",
        ...     temperature=0.2,
        ... )
        >>> model._inference_service_
        'openai_compatible'
    """
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("model_name must be a nonempty string")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("base_url must be a nonempty string")
    if api_key_env is not None and (
        not isinstance(api_key_env, str) or not api_key_env.strip()
    ):
        raise ValueError("api_key_env must be a nonempty string when provided")

    connection: dict[str, Any] = {"base_url": base_url.rstrip("/")}
    if api_key_env is not None:
        connection["api_key_env"] = api_key_env

    return Model(
        model_name.strip(),
        service_name="openai_compatible",
        **connection,
        **kwargs,
    )
