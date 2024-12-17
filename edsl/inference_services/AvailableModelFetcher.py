from typing import Any, List, Tuple, Optional, Dict, TYPE_CHECKING, Union, Generator
import json
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from platformdirs import user_cache_dir

from edsl.inference_services.ServiceAvailability import ServiceAvailability
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.inference_services.data_structures import ModelNamesList
from edsl.enums import InferenceServiceLiteral

from edsl.inference_services.data_structures import LanguageModelInfo
from edsl.inference_services.AvailableModelCacheHandler import (
    AvailableModelCacheHandler,
)

from collections import UserList


class AvailableModels(UserList):

    def __init__(self, data: list) -> None:
        super().__init__(data)

    def __contains__(self, model_name: str) -> bool:
        for model_entry in self:
            if model_entry.model_name == model_name:
                return True
        return False


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

    def available(
        self, service: Optional[InferenceServiceABC] = None
    ) -> List[LanguageModelInfo]:
        """
        Get available models from all services, using cached data when available.

        :param service: Optional[InferenceServiceABC] - If specified, only fetch models for this service.

        >>> from edsl.inference_services.OpenAIService import OpenAIService
        >>> af = AvailableModelFetcher([OpenAIService()], {})
        >>> af.available(service="openai")
        [LanguageModelInfo(model_name='...', service_name='openai', index=...), ...]

        Returns a list of [model, service_name, index] entries.
        """

        if service:  # they passed a specific service
            matching_models, _ = self.get_available_models_by_service(service=service)
            return list(self._adjust_index(matching_models, include_index=False))

        # They want them all!

        # Try to get cached data
        if self.cache_handler:
            if (all_models := self.cache_handler.models()) is not None:
                return all_models

        # Nope, we need to fetch them all
        all_models = self._get_all_models()

        if self.cache_handler:
            self.cache_handler.write_cache(all_models)

        return all_models

    @staticmethod
    def _adjust_index(sorted_models, include_index=False) -> Generator:
        """Adjust the index of the models."""
        for index, model in enumerate(sorted_models):
            if include_index:
                yield LanguageModelInfo(model.model_name, model.service_name, index)
            else:
                yield LanguageModelInfo(model.model_name, model.service_name, "NA")

    def get_available_models_by_service(
        self, service: Union["InferenceServiceABC", InferenceServiceLiteral]
    ) -> Tuple[List[LanguageModelInfo], InferenceServiceLiteral]:
        """Get models for a single service.

        :param service: InferenceServiceABC - e.g., OpenAIService or "openai"
        :return: Tuple[List[LanguageModelInfo], InferenceServiceLiteral]
        """
        if isinstance(service, str):
            service = self._fetch_service_by_service_name(service)

        service_models: ModelNamesList = (
            self.service_availability.get_service_available(service, warn=False)
        )
        service_name = service._inference_service_

        models_list = AvailableModels(
            [
                LanguageModelInfo(
                    model_name=model_name,
                    service_name=service_name,
                    index=-1,
                )
                for model_name in service_models
            ]
        )
        return models_list, service_name

    def _fetch_service_by_service_name(
        self, service_name: InferenceServiceLiteral
    ) -> "InferenceServiceABC":
        """The service name is the _inference_service_ attribute of the service."""
        if service_name in self._service_map:
            return self._service_map[service_name]
        raise ValueError(f"Service {service_name} not found")

    def _get_all_models(self) -> List[LanguageModelInfo]:
        all_models = []
        with ThreadPoolExecutor(max_workers=min(len(self.services), 10)) as executor:
            future_to_service = {
                executor.submit(self._get_service_models, service): service
                for service in self.services
            }

            for future in as_completed(future_to_service):
                try:
                    models, service_name = future.result()
                    all_models.extend(models)

                    # Add any additional models for this service
                    for model in self.added_models.get(service_name, []):
                        all_models.append([model, service_name, -1])

                except Exception as exc:
                    print(f"Service query failed: {exc}")
                    continue

        return AvailableModels(list(self._adjust_index(all_models, include_index=True)))


def main():
    from edsl.inference_services.OpenAIService import OpenAIService

    af = AvailableModelFetcher([OpenAIService()], {}, verbose=True)
    print(af.available(service="openai"))

    all_models = AvailableModelFetcher([OpenAIService()], {})._get_all_models()
    print(all_models)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    main()
