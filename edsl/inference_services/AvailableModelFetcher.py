from typing import Any, List, Tuple, Optional, Dict, TYPE_CHECKING, Union
import json
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from edsl.inference_services.ServiceAvailability import ServiceAvailability
from dataclasses import dataclass
from platformdirs import user_cache_dir

if TYPE_CHECKING:
    from edsl.inference_services.InferenceServiceABC import InferenceServiceABC


from edsl.enums import InferenceServiceLiteral


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

    def fetch_service_by_service_name(
        self, service_name: InferenceServiceLiteral
    ) -> "InferenceServiceABC":
        """The service name is the _inference_service_ attribute of the service."""
        if service_name in self._service_map:
            return self._service_map[service_name]
        raise ValueError(f"Service {service_name} not found")

    def get_available_models_by_service(
        self, service: "InferenceServiceABC", warn: bool = False
    ) -> list[str]:
        """Gets the available models for a single service."""
        return self.service_availability.get_service_available(service, warn)

    def get_service_models(
        self, service: "InferenceServiceABC"
    ) -> Tuple[List[List[Any]], str]:
        """Get models for a single service."""
        service_models = self.get_available_models_by_service(service)
        return (
            [[model, service._inference_service_, -1] for model in service_models],
            service._inference_service_,
        )

    def available(self, service: Optional[str] = None) -> List[List[Any]]:
        """
        Get available models from all services, using cached data when available.
        Returns a list of [model, service_name, index] entries.
        """
        # If requesting specific service, bypass cache
        if service:
            service_obj = self.fetch_service_by_service_name(service)
            total_models = self.get_service_models(service=service_obj)[0]
            sorted_models = sorted(total_models)
            for i, model in enumerate(sorted_models):
                model[2] = "NA"
                model = tuple(model)
            return sorted_models

        # Try to get cached data
        cache_data = self._read_cache()
        if cache_data:
            return cache_data["models"]

        total_models = []

        # Use ThreadPoolExecutor to parallel process the services
        with ThreadPoolExecutor(max_workers=min(len(self.services), 10)) as executor:
            future_to_service = {
                executor.submit(self.get_service_models, service): service
                for service in self.services
            }

            for future in as_completed(future_to_service):
                try:
                    models, service_name = future.result()
                    total_models.extend(models)

                    # Add any additional models for this service
                    for model in self.added_models.get(service_name, []):
                        total_models.append([model, service_name, -1])

                except Exception as exc:
                    print(f"Service query failed: {exc}")
                    continue

        sorted_models = sorted(total_models)
        for i, model in enumerate(sorted_models):
            model[2] = i
            model = tuple(model)

        # Cache the results
        self._write_cache(sorted_models)

        return sorted_models


def main():
    from edsl.inference_services.OpenAIService import OpenAIService

    af = AvailableModelFetcher([OpenAIService()], {}, verbose=True)
    print(af.available(service="openai"))


if __name__ == "__main__":
    main()
