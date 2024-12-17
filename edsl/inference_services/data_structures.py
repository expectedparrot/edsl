from collections import UserDict, defaultdict, UserList
from edsl.enums import InferenceServiceLiteral


class ModelNamesList(UserList):
    pass


class AvailableModels(UserDict):
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
