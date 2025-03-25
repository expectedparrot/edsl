from collections import defaultdict
from typing import Optional, Protocol, Dict, List, Tuple, TYPE_CHECKING

from ..enums import InferenceServiceLiteral
from .inference_service_abc import InferenceServiceABC
from .available_model_fetcher import AvailableModelFetcher
from .exceptions import InferenceServiceError

if TYPE_CHECKING:
    from ..language_models import LanguageModel
    from .inference_service_abc import InferenceServiceABC


class ModelCreator(Protocol):
    def create_model(self, model_name: str) -> "LanguageModel":
        ...


class ModelResolver:
    def __init__(
        self,
        services: List[InferenceServiceLiteral],
        models_to_services: Dict[InferenceServiceLiteral, InferenceServiceABC],
        availability_fetcher: "AvailableModelFetcher",
    ):
        """
        Class for determining which service to use for a given model.
        """
        self.services = services
        self._models_to_services = models_to_services
        self.availability_fetcher = availability_fetcher
        self._service_names_to_classes = {
            service._inference_service_: service for service in services
        }

    def resolve_model(
        self, model_name: str, service_name: Optional[InferenceServiceLiteral] = None
    ) -> InferenceServiceABC:
        """Returns an InferenceServiceABC object for the given model name.

        :param model_name: The name of the model to resolve. E.g., 'gpt-4o'
        :param service_name: The name of the service to use. E.g., 'openai'
        :return: An InferenceServiceABC object

        """
        if model_name == "test":
            from .services.test_service import TestService

            return TestService()

        if service_name is not None:
            service: InferenceServiceABC = self._service_names_to_classes.get(
                service_name
            )
            if not service:
                raise InferenceServiceError(f"Service {service_name} not found")
            return service

        if model_name in self._models_to_services:  # maybe we've seen it before!
            return self._models_to_services[model_name]

        for service in self.services:
            (
                available_models,
                service_name,
            ) = self.availability_fetcher.get_available_models_by_service(service)
            if model_name in available_models:
                self._models_to_services[model_name] = service
                return service

        raise InferenceServiceError(
            f"""Model {model_name} not found in any services. 
                                    If you know the service that has this model, use the service_name parameter directly.
                                    E.g., Model("gpt-4o", service_name="openai")
                                    """
        )


class InferenceServicesCollection:
    added_models = defaultdict(list)  # Moved back to class level

    def __init__(self, services: Optional[List[InferenceServiceABC]] = None):
        self.services = services or []
        self._models_to_services: Dict[str, InferenceServiceABC] = {}

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

    def service_names_to_classes(self) -> Dict[str, InferenceServiceABC]:
        return {service._inference_service_: service for service in self.services}

    def available(
        self,
        service: Optional[str] = None,
        force_refresh: bool = False,
    ) -> List[Tuple[str, str, int]]:
        return self.availability_fetcher.available(service, force_refresh=force_refresh)

    def reset_cache(self) -> None:
        self.availability_fetcher.reset_cache()

    @property
    def num_cache_entries(self) -> int:
        return self.availability_fetcher.num_cache_entries

    def register(self, service: InferenceServiceABC) -> None:
        self.services.append(service)

    def create_model_factory(
        self, model_name: str, service_name: Optional[InferenceServiceLiteral] = None
    ) -> "LanguageModel":
        if service_name is None:  # we try to find the right service
            service = self.resolver.resolve_model(model_name, service_name)
        else:  # if they passed a service, we'll use that
            service = self.service_names_to_classes().get(service_name)

        if not service:  # but if we can't find it, we'll raise an error
            raise InferenceServiceError(f"Service {service_name} not found")

        return service.create_model(model_name)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
