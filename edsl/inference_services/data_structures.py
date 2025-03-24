from collections import UserDict, defaultdict, UserList
from typing import Optional, List
from dataclasses import dataclass

from ..enums import InferenceServiceLiteral

@dataclass
class LanguageModelInfo:
    """A dataclass for storing information about a language model.


    >>> LanguageModelInfo("gpt-4-1106-preview", "openai")
    LanguageModelInfo(model_name='gpt-4-1106-preview', service_name='openai')

    >>> model_name, service = LanguageModelInfo.example()
    >>> model_name
    'gpt-4-1106-preview'

    >>> LanguageModelInfo.example().service_name
    'openai'

    """

    model_name: str
    service_name: str

    def __iter__(self):
        yield self.model_name
        yield self.service_name

    def __getitem__(self, key: int) -> str:
        import warnings

        warnings.warn(
            "Accessing LanguageModelInfo via index is deprecated. "
            "Please use .model_name, .service_name, or .index attributes instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if key == 0:
            return self.model_name
        elif key == 1:
            return self.service_name
        else:
            from .exceptions import InferenceServiceIndexError
            raise InferenceServiceIndexError("Index out of range")

    @classmethod
    def example(cls) -> "LanguageModelInfo":
        return cls("gpt-4-1106-preview", "openai")


class ModelNamesList(UserList):
    pass


class AvailableModels(UserList):

    def __init__(self, data: List[LanguageModelInfo]) -> None:
        super().__init__(data)

    def __contains__(self, model_name: str) -> bool:
        for model_entry in self:
            if model_entry.model_name == model_name:
                return True
        return False

    def print(self):
        return self.to_dataset().print()

    def to_dataset(self):
        from ..scenarios.scenario_list import ScenarioList

        models, services = zip(
            *[(model.model_name, model.service_name) for model in self]
        )
        return (
            ScenarioList.from_list("model", models)
            .add_list("service", services)
            .to_dataset()
        )

    def to_model_list(self):
        from ..language_models import ModelList

        return ModelList.from_available_models(self)

    def search(
        self, pattern: str, service_name: Optional[str] = None, regex: bool = False
    ) -> "AvailableModels":
        import re

        if not regex:
            # Escape special regex characters except *
            pattern = re.escape(pattern).replace(r"\*", ".*")

        try:
            regex = re.compile(pattern)
            avm = AvailableModels(
                [
                    entry
                    for entry in self
                    if regex.search(entry.model_name)
                    and (service_name is None or entry.service_name == service_name)
                ]
            )
            if len(avm) == 0:
                from .exceptions import InferenceServiceValueError
                raise InferenceServiceValueError(
                    "No models found matching the search pattern: " + pattern
                )
            else:
                return avm
        except re.error as e:
            from .exceptions import InferenceServiceValueError
            raise InferenceServiceValueError(f"Invalid regular expression pattern: {e}")


class ServiceToModelsMapping(UserDict):
    def __init__(self, data: dict) -> None:
        super().__init__(data)

    @property
    def service_names(self) -> list[str]:
        return list(self.data.keys())

    def _validate_service_names(self):
        for service in self.service_names:
            if service not in InferenceServiceLiteral:
                from .exceptions import InferenceServiceValueError
                raise InferenceServiceValueError(f"Invalid service name: {service}")

    def model_to_services(self) -> dict:
        self._model_to_service = defaultdict(list)
        for service, models in self.data.items():
            for model in models:
                self._model_to_service[model].append(service)
