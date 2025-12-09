import datetime

from .authoring import ServiceDefinition


class RegisteredService:
    service_name: str
    creator_ep_username: str
    last_updated: str
    service_url: str
    service_def_hash: int
    service_definition_uuid: str

    def key(self) -> tuple:
        return self.creator_ep_username, self.service_name

    @classmethod
    def from_service_definition(
        cls, service_definition: ServiceDefinition, service_url: str
    ) -> "RegisteredService":
        info = service_definition.push()
        # breakpoint()
        return cls(
            service_name=service_definition.name,
            creator_ep_username=service_definition.ep_username,
            last_updated=datetime.datetime.now().isoformat(),
            service_url=service_url,
            service_def_hash=service_definition.__hash__(),
            service_definition_uuid=info["uuid"],
        )


class ServiceDirectory:
    def __init__(self):
        self.services = {}

    def add_service(self, service: RegisteredService) -> None:
        self.services[service.service_name] = service

    def get_service(self, service_name: str) -> RegisteredService:
        return self.services[service_name]

    def get_service_definition(self, service_name: str) -> ServiceDefinition:
        service_uuid = self.services[service_name].service_definition_uuid
        return ServiceDefinition.from_uuid(service_uuid)


if __name__ == "__main__":
    service = ServiceDefinition.example()
    rs = RegisteredService.from_service_definition(service, "http://localhost:8001")
    print(rs)
