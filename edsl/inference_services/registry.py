from .inference_services_collection import InferenceServicesCollection

# Import services module
from . import services

# This gets all the classes 
services = [getattr(services, service_name) for service_name in services.__all__]

default = InferenceServicesCollection(services)
