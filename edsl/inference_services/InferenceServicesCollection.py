from edsl.inference_services.InferenceServiceABC import InferenceServiceABC


class InferenceServicesCollection:
    def __init__(self, services: list[InferenceServiceABC] = None):
        self.services = services or []

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
