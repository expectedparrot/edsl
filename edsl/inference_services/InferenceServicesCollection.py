from functools import lru_cache
from collections import defaultdict
from typing import Optional, Protocol, Dict, List, Tuple

from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.inference_services.AvailableModelFetcher import AvailableModelFetcher
from edsl.exceptions.inference_services import InferenceServiceError


class ModelCreator(Protocol):
    def create_model(self, model_name: str) -> "LanguageModel": ...


class InferenceService(ModelCreator, Protocol):
    _inference_service_: str


class ModelResolver:
    def __init__(
        self,
        services: List[InferenceService],
        models_to_services: Dict[str, InferenceService],
        availability_fetcher: "AvailableModelFetcher",
    ):
        self.services = services
        self._models_to_services = models_to_services
        self.availability_fetcher = availability_fetcher
        self._service_names_to_classes = {
            service._inference_service_: service for service in services
        }

    def resolve_model(
        self, model_name: str, service_name: Optional[str]
    ) -> InferenceService:
        if model_name == "test":
            from edsl.inference_services.TestService import TestService

            return TestService()

        if service_name:
            service = self._service_names_to_classes.get(service_name)
            if not service:
                raise InferenceServiceError(f"Service {service_name} not found")
            return service

        if model_name in self._models_to_services:
            return self._models_to_services[model_name]

        for service in self.services:
            available_models = (
                self.availability_fetcher.get_available_models_by_service(service)
            )
            if model_name in available_models:
                self._models_to_services[model_name] = service
                return service

        raise InferenceServiceError(f"Model {model_name} not found in any services")


class InferenceServicesCollection:
    added_models = defaultdict(list)  # Moved back to class level

    def __init__(self, services: Optional[List[InferenceService]] = None):
        self.services = services or []
        self._models_to_services: Dict[str, InferenceService] = {}

        self.availability_fetcher = AvailableModelFetcher(
            self.services, self.added_models
        )
        self.resolver = ModelResolver(
            self.services, self._models_to_services, self.availability_fetcher
        )

    @classmethod
    def add_model(cls, service_name: str, model_name: str) -> None:
        if service_name not in cls.added_models:
            cls.added_models[service_name].append(model_name)

    @lru_cache(maxsize=128)
    def available(self, service: Optional[str] = None) -> List[Tuple[str, str, int]]:
        return self.availability_fetcher.available(service)

    def reset_cache(self) -> None:
        self.available.cache_clear()

    def register(self, service: InferenceService) -> None:
        self.services.append(service)

    def create_model_factory(
        self, model_name: str, service_name: Optional[str] = None
    ) -> "LanguageModel":
        service = self.resolver.resolve_model(model_name, service_name)
        return service.create_model(model_name)
