from typing import Any, List, Tuple
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from edsl.inference_services.ServiceAvailability import ServiceAvailability


class AvailableModelFetcher:

    service_availability = ServiceAvailability()

    def __init__(self, services, added_models):
        self.services = services
        self.added_models = added_models

    @classmethod
    def _get_service_available(cls, service, warn: bool = False) -> list[str]:
        return cls.service_availability.get_service_available(service, warn)

        # try:
        #     service_models = service.available()
        # except Exception:
        #     if warn:
        #         warnings.warn(
        #             f"""Error getting models for {service._inference_service_}.
        #             Check that you have properly stored your Expected Parrot API key and activated remote inference, or stored your own API keys for the language models that you want to use.
        #             See https://docs.expectedparrot.com/en/latest/api_keys.html for instructions on storing API keys.
        #             Relying on Coop.""",
        #             UserWarning,
        #         )
        #     # Use the list of models on Coop as a fallback
        #     try:
        #         models_from_coop = cls.models_from_coop()
        #         service_models = models_from_coop.get(service._inference_service_, [])

        #         # cache results
        #         service._models_list_cache = service_models

        #     # Finally, use the available models cache from the Python file
        #     except Exception:
        #         if warn:
        #             warnings.warn(
        #                 f"""Error getting models for {service._inference_service_}.
        #                 Relying on EDSL cache.""",
        #                 UserWarning,
        #             )

        #         from edsl.inference_services.models_available_cache import (
        #             models_available,
        #         )

        #         service_models = models_available.get(service._inference_service_, [])

        #         # cache results
        #         service._models_list_cache = service_models

        # return service_models

    def available(self) -> List[List[Any]]:
        """
        Get available models from all services using parallel execution.
        Returns a list of [model, service_name, -1] entries.
        """
        total_models = []

        def get_service_models(service) -> Tuple[List[List[Any]], str]:
            """Helper function to get models for a single service."""
            service_models = self._get_service_available(service)
            return (
                [[model, service._inference_service_, -1] for model in service_models],
                service._inference_service_,
            )

        # Use a ThreadPoolExecutor to parallel process the services
        with ThreadPoolExecutor(max_workers=min(len(self.services), 10)) as executor:
            # Submit all service queries to the thread pool
            future_to_service = {
                executor.submit(get_service_models, service): service
                for service in self.services
            }

            # Collect results as they complete
            for future in as_completed(future_to_service):
                try:
                    models, service_name = future.result()
                    total_models.extend(models)

                    # Add any additional models for this service
                    for model in self.added_models.get(service_name, []):
                        total_models.append([model, service_name, -1])

                except Exception as exc:
                    print(f"Service query failed: {exc}")
                    # Optionally handle the error more gracefully
                    continue

        sorted_models = sorted(total_models)
        for i, model in enumerate(sorted_models):
            model[2] = i
            model = tuple(model)
        return sorted_models
