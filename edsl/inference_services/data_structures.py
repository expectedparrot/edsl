from collections import UserDict, defaultdict, UserList
from typing import Union
from edsl.enums import InferenceServiceLiteral
from dataclasses import dataclass


@dataclass
class LanguageModelInfo:
    model_name: str
    service_name: str

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
            raise IndexError("Index out of range")


class ModelNamesList(UserList):
    pass


class AvailableModels(UserList):
    def __init__(self, data: list) -> None:
        super().__init__(data)

    def __contains__(self, model_name: str) -> bool:
        for model_entry in self:
            if model_entry.model_name == model_name:
                return True
        return False


class ServiceToModelsMapping(UserDict):
    def __init__(self, data: dict) -> None:
        super().__init__(data)

    @property
    def service_names(self) -> list[str]:
        return list(self.data.keys())

    def _validate_service_names(self):
        for service in self.service_names:
            if service not in InferenceServiceLiteral:
                raise ValueError(f"Invalid service name: {service}")

    def model_to_services(self) -> dict:
        self._model_to_service = defaultdict(list)
        for service, models in self.data.items():
            for model in models:
                self._model_to_service[model].append(service)
