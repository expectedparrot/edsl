from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
import warnings


class InferenceServicesCollection:
    added_models = {}

    def __init__(self, services: list[InferenceServiceABC] = None):
        self.services = services or []

    @classmethod
    def add_model(cls, service_name, model_name):
        if service_name not in cls.added_models:
            cls.added_models[service_name] = []
        cls.added_models[service_name].append(model_name)

    @staticmethod
    def _get_service_available(service, warn: bool = False) -> list[str]:
        from_api = True
        try:
            service_models = service.available()
        except Exception as e:
            if warn:
                warnings.warn(
                    f"""Error getting models for {service._inference_service_}. 
                    Check that you have properly stored your Expected Parrot API key and activated remote inference, or stored your own API keys for the language models that you want to use.
                    See https://docs.expectedparrot.com/en/latest/api_keys.html for instructions on storing API keys.
                    Relying on cache.""",
                    UserWarning,
                )
            from edsl.inference_services.models_available_cache import models_available

            service_models = models_available.get(service._inference_service_, [])
            # cache results
            service._models_list_cache = service_models
            from_api = False
        return service_models  # , from_api

    def available(self):
        total_models = []
        for service in self.services:
            service_models = self._get_service_available(service)
            for model in service_models:
                total_models.append([model, service._inference_service_, -1])

            for model in self.added_models.get(service._inference_service_, []):
                total_models.append([model, service._inference_service_, -1])

        sorted_models = sorted(total_models)
        for i, model in enumerate(sorted_models):
            model[2] = i
            model = tuple(model)
        return sorted_models

    def register(self, service):
        self.services.append(service)

    def create_model_factory(self, model_name: str, service_name=None, index=None):

        if service_name:
            for service in self.services:
                if service_name == service._inference_service_:
                    return service.create_model(model_name)

        for service in self.services:
            if model_name in self._get_service_available(service):
                if service_name is None or service_name == service._inference_service_:
                    return service.create_model(model_name)

        # if model_name == "test":
        #     from edsl.language_models import LanguageModel
        #     return LanguageModel(test = True)

        raise Exception(f"Model {model_name} not found in any of the services")
