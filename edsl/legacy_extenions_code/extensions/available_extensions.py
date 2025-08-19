import httpx
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from edsl.config import CONFIG


@dataclass
class ServiceInfo:
    """Data class to represent service information"""

    service_name: str
    description: str
    service_collection_name: str
    creator_ep_username: str
    service_endpoint: str

    def __str__(self):
        return f"{self.service_name} ({self.service_collection_name}) by {self.creator_ep_username}"


class ServiceFetcher:
    """
    A class to fetch available services from the extension gateway.

    The gateway URL is dynamically determined based on EXPECTED_PARROT_URL.
    Example: EXPECTED_PARROT_URL=http://localhost:8000 -> gateway URL will be http://localhost:8008
    """

    def __init__(self, gateway_url: Optional[str] = None, timeout: float = 10.0):
        """
        Initialize the ServiceFetcher.

        Args:
            gateway_url: Optional URL override. If not provided, uses dynamic config based on EXPECTED_PARROT_URL
            timeout: Request timeout in seconds
        """
        self.gateway_url = gateway_url or CONFIG.get_extension_gateway_url()
        if not self.gateway_url:
            raise ValueError(
                "Gateway URL must be provided either as parameter or via dynamic config based on EXPECTED_PARROT_URL"
            )

        # Remove trailing slash for consistency
        self.gateway_url = self.gateway_url.rstrip("/")
        self.timeout = timeout

        logger.info(f"ServiceFetcher initialized with gateway URL: {self.gateway_url}")

    def fetch_service_definitions(self) -> List["ServiceDefinition"]:
        """
        Fetch all ServiceDefinition objects from the gateway.

        This method uses the ServiceDefinition.pull_all_from_gateway() method
        to get complete service definitions with all parameters, cost info, etc.

        Returns:
            List of ServiceDefinition objects

        Raises:
            Various exceptions from ServiceDefinition gateway methods
        """
        from .authoring.authoring import ServiceDefinition

        logger.info("Fetching all service definitions from gateway")
        return ServiceDefinition.pull_all_from_gateway(
            gateway_url=self.gateway_url, timeout=int(self.timeout)
        )

    def fetch_service_definition(self, service_id: int) -> "ServiceDefinition":
        """
        Fetch a specific ServiceDefinition by ID from the gateway.

        Args:
            service_id: The database ID of the service definition

        Returns:
            ServiceDefinition object

        Raises:
            Various exceptions from ServiceDefinition gateway methods
        """
        from .authoring.authoring import ServiceDefinition

        logger.info(f"Fetching service definition ID {service_id} from gateway")
        return ServiceDefinition.pull_from_gateway(
            service_id=service_id,
            gateway_url=self.gateway_url,
            timeout=int(self.timeout),
        )

    def fetch_service_definition_by_name(
        self, service_name: str
    ) -> Optional["ServiceDefinition"]:
        """
        Fetch a ServiceDefinition by name from the gateway.

        Args:
            service_name: The name of the service to find

        Returns:
            ServiceDefinition object if found, None otherwise
        """
        service_definitions = self.fetch_service_definitions()

        for service_def in service_definitions:
            if service_def.service_name == service_name:
                return service_def

        return None

    def fetch_service_definitions_by_collection(
        self, collection_name: str
    ) -> List["ServiceDefinition"]:
        """
        Fetch ServiceDefinitions from a specific collection.

        Args:
            collection_name: The name of the collection to filter by

        Returns:
            List of ServiceDefinition objects from the specified collection
        """
        service_definitions = self.fetch_service_definitions()

        return [
            service_def
            for service_def in service_definitions
            if service_def.service_collection_name == collection_name
        ]

    def fetch_service_definitions_by_creator(
        self, creator_username: str
    ) -> List["ServiceDefinition"]:
        """
        Fetch ServiceDefinitions created by a specific user.

        Args:
            creator_username: Username of the service creator

        Returns:
            List of ServiceDefinition objects created by the specified user
        """
        service_definitions = self.fetch_service_definitions()

        return [
            service_def
            for service_def in service_definitions
            if service_def.creator_ep_username == creator_username
        ]

    def list_service_summaries(self) -> List[Dict[str, Any]]:
        """
        Get basic service summaries from the gateway (faster than full definitions).

        Returns:
            List of service summary dictionaries
        """
        from .authoring.authoring import ServiceDefinition

        logger.info("Listing service summaries from gateway")
        return ServiceDefinition.list_from_gateway(
            gateway_url=self.gateway_url, timeout=int(self.timeout)
        )

    async def fetch_services(self) -> List[ServiceInfo]:
        """
        Fetch all available services from the gateway (basic info only).

        Returns:
            List of ServiceInfo objects representing available services

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response format is unexpected
        """
        url = f"{self.gateway_url}/services"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(f"Fetching services from: {url}")
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()

                if "services" not in data:
                    raise ValueError("Response does not contain 'services' key")

                services = []
                for service_data in data["services"]:
                    service_info = ServiceInfo(
                        service_name=service_data["service_name"],
                        description=service_data["description"],
                        service_collection_name=service_data["service_collection_name"],
                        creator_ep_username=service_data["creator_ep_username"],
                        service_endpoint=service_data["service_endpoint"],
                    )
                    services.append(service_info)

                logger.info(f"Successfully fetched {len(services)} services")
                return services

        except httpx.HTTPError as e:
            logger.error(f"HTTP error while fetching services: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching services: {e}")
            raise

    def fetch_services_sync(self) -> List[ServiceInfo]:
        """
        Synchronous version of fetch_services (basic info only).

        Returns:
            List of ServiceInfo objects representing available services

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If the response format is unexpected
        """
        url = f"{self.gateway_url}/services"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                logger.debug(f"Fetching services from: {url}")
                response = client.get(url)
                response.raise_for_status()

                data = response.json()

                if "services" not in data:
                    raise ValueError("Response does not contain 'services' key")

                services = []
                for service_data in data["services"]:
                    service_info = ServiceInfo(
                        service_name=service_data["service_name"],
                        description=service_data["description"],
                        service_collection_name=service_data["service_collection_name"],
                        creator_ep_username=service_data["creator_ep_username"],
                        service_endpoint=service_data["service_endpoint"],
                    )
                    services.append(service_info)

                logger.info(f"Successfully fetched {len(services)} services")
                return services

        except httpx.HTTPError as e:
            logger.error(f"HTTP error while fetching services: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching services: {e}")
            raise

    async def fetch_service_collections(self) -> Dict[str, List[ServiceInfo]]:
        """
        Fetch services grouped by collection (basic info only).

        Returns:
            Dictionary mapping collection names to lists of ServiceInfo objects
        """
        services = await self.fetch_services()
        collections = {}

        for service in services:
            collection_name = service.service_collection_name
            if collection_name not in collections:
                collections[collection_name] = []
            collections[collection_name].append(service)

        return collections

    def fetch_service_collections_sync(self) -> Dict[str, List[ServiceInfo]]:
        """
        Synchronous version of fetch_service_collections (basic info only).

        Returns:
            Dictionary mapping collection names to lists of ServiceInfo objects
        """
        services = self.fetch_services_sync()
        collections = {}

        for service in services:
            collection_name = service.service_collection_name
            if collection_name not in collections:
                collections[collection_name] = []
            collections[collection_name].append(service)

        return collections

    async def fetch_services_by_creator(
        self, creator_username: str
    ) -> List[ServiceInfo]:
        """
        Fetch services created by a specific user (basic info only).

        Args:
            creator_username: Username of the service creator

        Returns:
            List of ServiceInfo objects for services created by the specified user
        """
        all_services = await self.fetch_services()
        return [
            service
            for service in all_services
            if service.creator_ep_username == creator_username
        ]

    def fetch_services_by_creator_sync(
        self, creator_username: str
    ) -> List[ServiceInfo]:
        """
        Synchronous version of fetch_services_by_creator (basic info only).

        Args:
            creator_username: Username of the service creator

        Returns:
            List of ServiceInfo objects for services created by the specified user
        """
        all_services = self.fetch_services_sync()
        return [
            service
            for service in all_services
            if service.creator_ep_username == creator_username
        ]

    def list_services(self, services: Optional[List[ServiceInfo]] = None) -> None:
        """
        Print a formatted list of services.

        Args:
            services: Optional list of services to display. If None, fetches all services.
        """
        if services is None:
            services = self.fetch_services_sync()

        if not services:
            print("No services available.")
            return

        print(f"\nAvailable Services ({len(services)} total):")
        print("-" * 80)

        # Group by collection for better display
        collections = {}
        for service in services:
            collection = service.service_collection_name
            if collection not in collections:
                collections[collection] = []
            collections[collection].append(service)

        for collection_name, collection_services in collections.items():
            print(f"\n{collection_name.upper()} Collection:")
            for service in collection_services:
                print(f"  • {service.service_name}")
                print(f"    Description: {service.description}")
                print(f"    Creator: {service.creator_ep_username}")
                print()

    def list_service_definitions(
        self, service_definitions: Optional[List["ServiceDefinition"]] = None
    ) -> None:
        """
        Print a formatted list of ServiceDefinition objects with detailed information.

        Args:
            service_definitions: Optional list of ServiceDefinition objects to display.
                                If None, fetches all service definitions.
        """
        if service_definitions is None:
            service_definitions = self.fetch_service_definitions()

        if not service_definitions:
            print("No service definitions available.")
            return

        print(f"\nAvailable Service Definitions ({len(service_definitions)} total):")
        print("=" * 100)

        # Group by collection for better display
        collections = {}
        for service_def in service_definitions:
            collection = service_def.service_collection_name
            if collection not in collections:
                collections[collection] = []
            collections[collection].append(service_def)

        for collection_name, collection_services in collections.items():
            print(f"\n{collection_name.upper()} Collection:")
            print("-" * 50)

            for service_def in collection_services:
                print(f"\n  📋 {service_def.service_name}")
                print(f"     Description: {service_def.description}")
                print(f"     Creator: {service_def.creator_ep_username}")
                print(f"     Endpoint: {service_def.service_endpoint or 'Not set'}")

                # Show parameters
                if service_def.parameters:
                    print(f"     Parameters ({len(service_def.parameters)}):")
                    for param_name, param_def in service_def.parameters.items():
                        required_str = "required" if param_def.required else "optional"
                        default_str = (
                            f", default={param_def.default_value}"
                            if param_def.default_value is not None
                            else ""
                        )
                        print(
                            f"       • {param_name} ({param_def.type}, {required_str}{default_str})"
                        )
                        print(f"         {param_def.description}")

                # Show cost info
                if service_def.cost:
                    cost_info = (
                        f"{service_def.cost.per_call_cost} {service_def.cost.unit}"
                    )
                    if service_def.cost.variable_pricing_cost_formula:
                        cost_info += (
                            f" + {service_def.cost.variable_pricing_cost_formula}"
                        )
                    print(f"     Cost: {cost_info}")

                # Show returns
                if service_def.service_returns:
                    print(f"     Returns ({len(service_def.service_returns)}):")
                    for return_name, return_def in service_def.service_returns.items():
                        print(
                            f"       • {return_name} ({return_def.type}): {return_def.description}"
                        )

                print()


# Convenience functions for quick access
def get_available_services(gateway_url: Optional[str] = None) -> List[ServiceInfo]:
    """
    Convenience function to quickly fetch all available services (basic info).

    Args:
        gateway_url: Optional gateway URL override

    Returns:
        List of ServiceInfo objects
    """
    fetcher = ServiceFetcher(gateway_url)
    return fetcher.fetch_services_sync()


def get_available_service_definitions(
    gateway_url: Optional[str] = None,
) -> List["ServiceDefinition"]:
    """
    Convenience function to quickly fetch all available ServiceDefinition objects.

    Args:
        gateway_url: Optional gateway URL override

    Returns:
        List of ServiceDefinition objects
    """
    fetcher = ServiceFetcher(gateway_url)
    return fetcher.fetch_service_definitions()


def get_service_definition_by_name(
    service_name: str, gateway_url: Optional[str] = None
) -> Optional["ServiceDefinition"]:
    """
    Convenience function to get a specific ServiceDefinition by name.

    Args:
        service_name: Name of the service to find
        gateway_url: Optional gateway URL override

    Returns:
        ServiceDefinition object if found, None otherwise
    """
    fetcher = ServiceFetcher(gateway_url)
    return fetcher.fetch_service_definition_by_name(service_name)


# Example usage
if __name__ == "__main__":
    import asyncio

    # Example using config setting
    # Gateway URL is dynamically determined from EXPECTED_PARROT_URL

    try:
        print("=== ServiceDefinition Usage ===")
        fetcher = ServiceFetcher()

        # Fetch complete service definitions
        service_definitions = fetcher.fetch_service_definitions()
        print(f"Found {len(service_definitions)} service definitions")

        # Display them nicely
        fetcher.list_service_definitions(service_definitions)

        # Get a specific service by name
        if service_definitions:
            first_service_name = service_definitions[0].service_name
            specific_service = fetcher.fetch_service_definition_by_name(
                first_service_name
            )
            if specific_service:
                print(f"\nFound specific service: {specific_service.service_name}")
                # You can now call the service!
                # result = specific_service(param1="value1", param2="value2")

        print("\n=== Basic Service Info Usage ===")
        # Fetch basic service info (faster)
        services = fetcher.fetch_services_sync()
        fetcher.list_services(services)

        # Asynchronous usage
        print("\n=== Asynchronous Usage ===")

        async def async_example():
            fetcher = ServiceFetcher()
            services = await fetcher.fetch_services()
            collections = await fetcher.fetch_service_collections()

            print(f"Found {len(services)} services in {len(collections)} collections")
            for collection_name, collection_services in collections.items():
                print(f"- {collection_name}: {len(collection_services)} services")

        asyncio.run(async_example())

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please check your EXPECTED_PARROT_URL config setting")
    except Exception as e:
        print(f"Error: {e}")
