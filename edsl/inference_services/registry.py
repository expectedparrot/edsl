from .inference_services_collection import InferenceServicesCollection

from .services import *
from .services import __all__

services = [globals()[service_name] for service_name in __all__ if service_name in globals()]

default = InferenceServicesCollection(services)
