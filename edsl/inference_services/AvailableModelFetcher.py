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


LanguageModelInfo = namedtuple(
    "LanguageModelInfo", ["model_name", "service_name", "index"]
)


@dataclass
class ModelInfo:
    model: str
    service_name: InferenceServiceLiteral
    index: int


@dataclass
class AvailableModels:
    models: List[ModelInfo]

    def __in__(self, model_name: str) -> bool:
        return any(model.model == model_name for model in self.models)


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
        self.use_cache = use_cache
        self.cache_dir = Path(user_cache_dir("edsl", "model_availability"))
        self.cache_file = self.cache_dir / "available_models.json"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _read_cache(self) -> Union[dict, None]:
        """Read the cached model availability data if it exists and is valid."""

        if self.verbose:
            print("Reading from cache at ", self.cache_file)

        if not self.cache_file.exists():
            if self.verbose:
                print("No cache file found")
            return None

        try:
            with open(self.cache_file, "r") as f:
                cache_data = json.load(f)

            # Check cache validity
            cache_time = datetime.fromisoformat(str(cache_data["timestamp"]))
            if self.verbose:
                print("Cache time: ", cache_time)

            if datetime.now() - cache_time > timedelta(hours=self.CACHE_VALIDITY_HOURS):
                return None

            return cache_data
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _write_cache(self, models_data: List[List[Any]]):
        """Write the model availability data to cache."""
        cache_data = {"timestamp": datetime.now().isoformat(), "models": models_data}

        if self.verbose:
            print("Writing to cache at ", self.cache_file)
        with open(self.cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)

    def available(
        self, service: Optional[InferenceServiceABC] = None
    ) -> List[LanguageModelInfo]:
        """
        Get available models from all services, using cached data when available.

        :param service: Optional[InferenceServiceABC] - If specified, only fetch models for this service.

        Returns a list of [model, service_name, index] entries.
        """

        if service:  # they passed a specific service
            matching_models, _ = self._get_service_models(service=service)
            return list(self._adjust_index(matching_models, include_index=False))

        # They want them all!

        # Try to get cached data
        if self.use_cache:
            cache_data = self._read_cache()
            if cache_data is not None:
                return cache_data["models"]

        all_models = self._get_all_models()
        if self.use_cache:
            self._write_cache(all_models)

        return all_models

    @staticmethod
    def _adjust_index(sorted_models, include_index=False) -> Generator:
        """Adjust the index of the models."""
        for index, model in enumerate(sorted_models):
            model_name, service, _ = model
            if include_index:
                yield LanguageModelInfo(model_name, service, index)
            else:
                yield LanguageModelInfo(model_name, service, "NA")

    def _get_service_models(
        self, service: Union["InferenceServiceABC", InferenceServiceLiteral]
    ) -> Tuple[List[LanguageModelInfo], InferenceServiceLiteral]:
        """Get models for a single service.

        :param service: InferenceServiceABC - e.g., OpenAIService
        :return: Tuple[List[LanguageModelInfo], InferenceServiceLiteral]
        """
        if isinstance(service, str):
            service = self._fetch_service_by_service_name(service)

        service_models: ModelNamesList = (
            self.service_availability.get_service_available(service, warn=False)
        )
        service_name = service._inference_service_

        models_list = [
            LanguageModelInfo(
                model_name=model_name,
                service_name=service_name,
                index=-1,
            )
            for model_name in service_models
        ]
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

        return list(self._adjust_index(all_models, include_index=True))


def main():
    from edsl.inference_services.OpenAIService import OpenAIService

    af = AvailableModelFetcher([OpenAIService()], {}, verbose=True)
    print(af.available(service="openai"))


if __name__ == "__main__":
    # main()
    pass
