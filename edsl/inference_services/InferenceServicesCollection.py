from functools import lru_cache
from typing import Optional
from collections import defaultdict
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.inference_services.AvailableModelFetcher import AvailableModelFetcher

from edsl.exceptions.inference_services import InferenceServiceError


class InferenceServicesCollection:
    added_models = defaultdict(list)

    def __init__(self, services: list[InferenceServiceABC] = None):
        self.services = services or []
        self.availability_fetcher = AvailableModelFetcher(
            self.services, self.added_models
        )
        self._service_names_to_classes = {
            service._inference_service_: service for service in self.services
        }

        self._models_to_services = {}

    @classmethod
    def add_model(cls, service_name: str, model_name: str) -> None:
        if service_name not in cls.added_models:
            cls.added_models[service_name].append(model_name)

    @lru_cache(maxsize=128)
    def available(self, service: Optional[str] = None) -> list[tuple[str, str, int]]:
        print("Fetching available models")
        return self.availability_fetcher.available(service)

    def reset_cache(self):
        """Reset the LRU cache for the available() method."""
        self.available.cache_clear()

    def register(self, service: str) -> None:
        self.services.append(service)

    def create_model_factory(self, model_name: str, service_name: Optional[str] = None):

        # if they are testing, return the test model
        if model_name == "test":
            from edsl.inference_services.TestService import TestService

            return TestService.create_model(model_name)

        # they passed a service name
        if service_name:
            service = self._service_names_to_classes.get(service_name)
            return service.create_model(model_name)

        # they didn't pass a service name but maybe we know which service to use
        if model_name in self._models_to_services:
            service = self._models_to_services[model_name]
            return service.create_model(model_name)

        # they didn't pass a service name and we don't know which service to use
        for service in self.services:
            available_models = (
                self.availability_fetcher.get_available_models_by_service(service)
            )
            if model_name in available_models:
                self._models_to_services[model_name] = service
            if service_name is None or service_name == service._inference_service_:
                return service.create_model(model_name)

        raise InferenceServiceError(
            f"Model {model_name} not found in any of the services"
        )
