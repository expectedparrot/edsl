from typing import Dict, Any, Optional, Type, Generator, Tuple
from .authoring import ServiceDefinition
from ..scenarios import Scenario
import os 
from collections import UserDict 

from .authoring import ServiceDefinition

# refactor to use EDSL config
API_BASE_URL = os.getenv("EDSL_API_URL", "http://localhost:8000")
EP_API_TOKEN = os.getenv("EXPECTED_PARROT_API_KEY")

class Services(UserDict):
    def __init__(self, services: Optional[Dict[str, ServiceDefinition]] = None):
        self.data = services or {}
        super().__init__(self.data)

    def view(self) -> None:
        """Default function to display a list of services (name and description)."""
        for service_name, service in self.data.items():
            try:
                # Using print for direct user output here as requested for the display func
                print(f"- {service_name}: {service.description}") # Access attributes directly
            except Exception as e:
                # print(f"Error displaying service '{getattr(service, "name", "Unknown")}': {e}")
                pass

from ..config import CONFIG

class ServicesRegistry(UserDict):
    
    registry_url = CONFIG.get("EDSL_EXTENSION_SERVICES")
    registry_uuid = '82dba30d-9939-4408-88b5-002bb65736e1' #TODO: temporary work-around
    
    _info: Optional[Dict[str, Any]] = None

    def __init__(self, service_to_ep_info: Optional[Dict[str, Any]] = None, ep_api_token: Optional[str] = None, gateway_url: Optional[str] = None):
        self._ep_api_token = ep_api_token or EP_API_TOKEN
        self._gateway_url = gateway_url or API_BASE_URL
        self._services = None
        #super().__init__(service_to_ep_info or {})
        self.data = service_to_ep_info or {}


    @classmethod
    def from_config(cls):
        return cls.pull(cls.registry_url)
    
    @property
    def services(self) -> Generator[Tuple[str, ServiceDefinition], None, None]:
        if self._services is None:
            print("Pulling services")
            self._services = Services(self._to_services())
        return self._services
    
    def _to_services(self) -> Generator[Tuple[str, ServiceDefinition], None, None]:
        for service_name, service_info in self.data.items():
            service_definition = ServiceDefinition.pull(service_info['uuid'])
            service_definition._ep_api_token = self._ep_api_token
            yield (service_name, service_definition)

    @classmethod
    def pull(cls, *args, **kwargs):
        pulled_scenario = Scenario.pull(*args, **kwargs)
        return cls.from_dict(pulled_scenario.to_dict())

    # def __init__(self, service_to_ep_info: Optional[Dict[str, str]] = None):
    #     self.data = service_to_ep_info or {}

    def get_service(self, service_name: str) -> ServiceDefinition:
        return ServiceDefinition.pull(self.data[service_name]['uuid'])

    def __repr__(self):
        return f"Services(service_to_ep_info={self.data})"

    def add_service(self, service: ServiceDefinition):
        print(f"Adding service {service.name} to {self.registry_url}")
        print("Current data:", self.data)
        self.data[service.name] = service.push()
        print("Updated data:", self.data)
        print("Updating registry")
        self.update()
        print("Registry updated")

    def update(self):
        print(f"Updating {self.registry_url}")
        scenario = Scenario.from_dict(self.to_dict())
        if hasattr(self, 'registry_uuid'):
            import warnings 
            warnings.warn("Using registry_uuid to update registry; this is a temporary work-around")
            scenario.patch(self.registry_uuid, value = scenario)
        else:
            scenario.patch(self.registry_url, value = scenario)
        print(f"Updated {self.registry_url}")

    def to_dict(self) -> Dict[str, Any]:
        return {'service_to_ep_info': self.data}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServicesRegistry':
        return cls(data['service_to_ep_info'])
    
    def push(self, *args, **kwargs):
        s = Scenario(self.to_dict())
        return s.push(*args, **kwargs)
    
    def update_service(self, service: ServiceDefinition):
        """This does not change the Services object itself, it just updates the service in the registry"""
        if service.name in self.service_to_ep_info:
            print(f"Updating service {service.name}")
            service_uuid = self.service_to_ep_info[service.name]['uuid']
            service.update(service_uuid)            # self.service_to_ep_info[service.name] = service.push()
        else:
            print("Service not found, adding it")
            self.add_service(service)


if __name__ == "__main__":
    if False:
        services_registry = ServicesRegistry()
        services_registry.add_service(ServiceDefinition.example())
        print(services_registry.services)

        info = services_registry.push(alias = 'ep-services-experimental', description = 'EP-Services Experimental', visibility = 'public')
        print(info)
    else:
        services_registry = ServicesRegistry.from_config()
        print(services_registry.services)
