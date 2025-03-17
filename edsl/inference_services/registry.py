from .inference_services_collection import InferenceServicesCollection

# Import services module
from . import services

# Use __all__ from services to get service class names
services = [getattr(services, service_name) for service_name in services.__all__]

default = InferenceServicesCollection(services)
