"""Base module for EDSL.

This module provides the foundation for all classes in the EDSL framework.
"""

from edsl.base.item_collection_abc import ItemCollection

from edsl.base.base_class import (
    Base,
    BaseDiff,
    BaseDiffCollection,
    DiffMethodsMixin,
    DisplayJSON,
    DisplayYAML,
    DummyObject,
    HashingMixin,
    PersistenceMixin,
    RegisterSubclassesMeta,
    RepresentationMixin,
    is_iterable,
)
from edsl.base.base_exception import BaseException
from edsl.base.exceptions import (
    BaseValueError,
    BaseNotImplementedError,
    BaseKeyError,
    BaseFileError,
    BaseTypeError,
)

from edsl.base.enums import (
    EnumWithChecks,
    InferenceServiceLiteral,
    InferenceServiceType,
    QuestionType,
    TokenPricing,
    available_models_urls,
    get_token_pricing,
    pricing,
    service_to_api_keyname,
)
from edsl.base.data_transfer_models import (
    AgentResponseDict,
    Answers,
    EDSLOutput,
    EDSLResultObjectInput,
    ImageInfo,
    ModelInputs,
    ModelResponse,
)

__all__ = [
    # Base classes
    "Base",
    "ItemCollection",
    "BaseDiff",
    "BaseDiffCollection",
    "DiffMethodsMixin",
    "DisplayJSON",
    "DisplayYAML",
    "DummyObject",
    "HashingMixin",
    "PersistenceMixin",
    "RegisterSubclassesMeta",
    "RepresentationMixin",
    "is_iterable",
    # Exceptions
    "BaseException",
    "BaseValueError",
    "BaseNotImplementedError",
    "BaseKeyError",
    "BaseFileError",
    "BaseTypeError",
    # Enums
    "EnumWithChecks",
    "InferenceServiceLiteral",
    "InferenceServiceType",
    "QuestionType",
    "TokenPricing",
    "available_models_urls",
    "get_token_pricing",
    "pricing",
    "service_to_api_keyname",
    # Data transfer models
    "AgentResponseDict",
    "Answers",
    "EDSLOutput",
    "EDSLResultObjectInput",
    "ImageInfo",
    "ModelInputs",
    "ModelResponse",
]
