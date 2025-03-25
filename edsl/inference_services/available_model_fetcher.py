from typing import List, Tuple, Optional, Dict, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from .service_availability import ServiceAvailability
from .inference_service_abc import InferenceServiceABC
from ..enums import InferenceServiceLiteral

from .data_structures import ModelNamesList, LanguageModelInfo, AvailableModels

from .available_model_cache_handler import AvailableModelCacheHandler

class AvailableModelFetcher:
    """Fetches available models from the various services with JSON caching."""

    service_availability = ServiceAvailability()
    CACHE_VALIDITY_HOURS = 48  # Cache validity period in hours

    def __init__(
        self,
        services: List["InferenceServiceABC"],
        added_models: Dict[str, List[str]],
        verbose: bool = False,
        use_cache: bool = True,
    ):
        self.services = services
        self.added_models = added_models
        self._service_map = {
            service._inference_service_: service for service in services
        }
        self.verbose = verbose
        if use_cache:
            self.cache_handler = AvailableModelCacheHandler()
        else:
            self.cache_handler = None

    @property
    def num_cache_entries(self):
        return self.cache_handler.num_cache_entries

    @property
    def path_to_db(self):
        return self.cache_handler.path_to_db

    def reset_cache(self):
        if self.cache_handler:
            self.cache_handler.reset_cache()

    def available(
        self,
        service: Optional[InferenceServiceABC] = None,
        force_refresh: bool = False,
    ) -> List[LanguageModelInfo]:
        """
        Get available models from all services, using cached data when available.

        :param service: Optional[InferenceServiceABC] - If specified, only fetch models for this service.

        >>> from .services.open_ai_service import OpenAIService
        >>> af = AvailableModelFetcher([OpenAIService()], {})
        >>> af.available(service="openai")
        [LanguageModelInfo(model_name='...', service_name='openai'), ...]

        Returns a list of [model, service_name, index] entries.
        """
        if service == "azure" or service == "bedrock":
            force_refresh = True  # Azure models are listed inside the .env AZURE_ENDPOINT_URL_AND_KEY variable

        if service:  # they passed a specific service
            matching_models, _ = self.get_available_models_by_service(
                service=service, force_refresh=force_refresh
            )
            return matching_models

        # Nope, we need to fetch them all
        all_models = self._get_all_models()

        # if self.cache_handler:
        #    self.cache_handler.add_models_to_cache(all_models)

        return all_models

    def get_available_models_by_service(
        self,
        service: Union["InferenceServiceABC", InferenceServiceLiteral],
        force_refresh: bool = False,
    ) -> Tuple[AvailableModels, InferenceServiceLiteral]:
        """Get models for a single service.

        :param service: InferenceServiceABC - e.g., OpenAIService or "openai"
        :return: Tuple[List[LanguageModelInfo], InferenceServiceLiteral]
        """
        if isinstance(service, str):
            service = self._fetch_service_by_service_name(service)

        if not force_refresh:
            models_from_cache = self.cache_handler.models(
                service=service._inference_service_
            )
            if self.verbose:
                print(
                    "Searching cache for models with service name:",
                    service._inference_service_,
                )
                print("Got models from cache:", models_from_cache)
        else:
            models_from_cache = None

        if models_from_cache:
            # print(f"Models from cache for {service}: {models_from_cache}")
            # print(hasattr(models_from_cache[0], "service_name"))
            return models_from_cache, service._inference_service_
        else:
            return self.get_available_models_by_service_fresh(service)

    def get_available_models_by_service_fresh(
        self, service: Union["InferenceServiceABC", InferenceServiceLiteral]
    ) -> Tuple[AvailableModels, InferenceServiceLiteral]:
        """Get models for a single service. This method always fetches fresh data.

        :param service: InferenceServiceABC - e.g., OpenAIService or "openai"
        :return: Tuple[List[LanguageModelInfo], InferenceServiceLiteral]
        """
        if isinstance(service, str):
            service = self._fetch_service_by_service_name(service)

        service_models: ModelNamesList = (
            self.service_availability.get_service_available(service, warn=False)
        )
        service_name = service._inference_service_

        if not service_models:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # Ignores the warning
                warnings.warn(f"No models found for service {service_name}")

            return [], service_name

        models_list = AvailableModels(
            [
                LanguageModelInfo(
                    model_name=model_name,
                    service_name=service_name,
                )
                for model_name in service_models
            ]
        )
        self.cache_handler.add_models_to_cache(models_list)  # update the cache
        return models_list, service_name

    def _fetch_service_by_service_name(
        self, service_name: InferenceServiceLiteral
    ) -> "InferenceServiceABC":
        """The service name is the _inference_service_ attribute of the service."""
        if service_name in self._service_map:
            return self._service_map[service_name]
        from .exceptions import InferenceServiceValueError
        raise InferenceServiceValueError(f"Service {service_name} not found")

    def _get_all_models(self, force_refresh=False) -> List[LanguageModelInfo]:
        all_models = []
        with ThreadPoolExecutor(max_workers=min(len(self.services), 10)) as executor:
            future_to_service = {
                executor.submit(
                    self.get_available_models_by_service, service, force_refresh
                ): service
                for service in self.services
            }

            for future in as_completed(future_to_service):
                try:
                    models, service_name = future.result()
                    all_models.extend(models)

                    # Add any additional models for this service
                    for model in self.added_models.get(service_name, []):
                        all_models.append(
                            LanguageModelInfo(
                                model_name=model, service_name=service_name
                            )
                        )

                except Exception as exc:
                    print(f"Service query failed for service {service_name}: {exc}")
                    continue

        return AvailableModels(all_models)


def main():
    from .services.open_ai_service import OpenAIService

    # Create fetcher without assigning to unused variable
    all_models = AvailableModelFetcher([OpenAIService()], {})._get_all_models(
        force_refresh=True
    )
    print(all_models)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
    # main()

    # from .services.open_ai_service import OpenAIService

    # af = AvailableModelFetcher([OpenAIService()], {}, verbose=True)
    # # print(af.available(service="openai"))

    # all_models = AvailableModelFetcher([OpenAIService()], {})._get_all_models()
    # print(all_models)
