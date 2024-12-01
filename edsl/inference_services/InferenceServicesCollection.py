from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.inference_services.AvailableModelFetcher import AvailableModelFetcher


class InferenceServicesCollection:
    added_models = {}

    def __init__(self, services: list[InferenceServiceABC] = None):
        self.services = services or []
        self.availability_fetcher = AvailableModelFetcher(
            self.services, self.added_models
        )

    @classmethod
    def add_model(cls, service_name, model_name):
        if service_name not in cls.added_models:
            cls.added_models[service_name] = []
        cls.added_models[service_name].append(model_name)

    def available(self):
        return self.availability_fetcher.available()

    def register(self, service):
        self.services.append(service)

    def create_model_factory(self, model_name: str, service_name=None, index=None):

        # if they are testing, return the test model
        if model_name == "test":
            from edsl.inference_services.TestService import TestService

            return TestService.create_model(model_name)

        if service_name:  # they passed a service name
            for service in self.services:
                if (
                    service_name == service._inference_service_
                ):  # find the right inference service; short list so ok to loop
                    return service.create_model(model_name)

        for service in self.services:  # this didn't pass a service name
            if model_name in self.availability_fetcher._get_service_available(
                service
            ):  # self._get_service_available(service):
                if service_name is None or service_name == service._inference_service_:
                    return service.create_model(model_name)

        raise Exception(f"Model {model_name} not found in any of the services")
