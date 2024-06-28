from edsl.inference_services.InferenceServiceABC import InferenceServiceABC


class InferenceServicesCollection:
    added_models = {}

    def __init__(self, services: list[InferenceServiceABC] = None):
        self.services = services or []

    @classmethod
    def add_model(cls, service_name, model_name):
        if service_name not in cls.added_models:
            cls.added_models[service_name] = []
        cls.added_models[service_name].append(model_name)

    def available(self):
        total_models = []
        for service in self.services:
            try:
                service_models = service.available()
            except Exception as e:
                print(f"Error getting models for {service._inference_service_}: {e}")
                service_models = []
                continue
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
        for service in self.services:
            if model_name in service.available():
                if service_name is None or service_name == service._inference_service_:
                    return service.create_model(model_name)

        raise Exception(f"Model {model_name} not found in any of the services")
