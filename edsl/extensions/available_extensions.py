import os
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
    
    The gateway URL should be provided via the EXTENSION_GATEWAY_URL environment variable.
    Example: EXTENSION_GATEWAY_URL=http://localhost:8000
    """
    
    def __init__(self, gateway_url: Optional[str] = None, timeout: float = 10.0):
        """
        Initialize the ServiceFetcher.
        
        Args:
            gateway_url: Optional URL override. If not provided, uses EXTENSION_GATEWAY_URL env var
            timeout: Request timeout in seconds
        """
        self.gateway_url = gateway_url or CONFIG.get("EDSL_EXTENSION_GATEWAY_URL")
        if not self.gateway_url:
            raise ValueError(
                "Gateway URL must be provided either as parameter or via EXTENSION_GATEWAY_URL environment variable"
            )
        
        # Remove trailing slash for consistency
        self.gateway_url = self.gateway_url.rstrip('/')
        self.timeout = timeout
        
        logger.info(f"ServiceFetcher initialized with gateway URL: {self.gateway_url}")
    
    async def fetch_services(self) -> List[ServiceInfo]:
        """
        Fetch all available services from the gateway.
        
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
                        service_endpoint=service_data["service_endpoint"]
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
        Synchronous version of fetch_services.
        
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
                        service_endpoint=service_data["service_endpoint"]
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
        Fetch services grouped by collection.
        
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
        Synchronous version of fetch_service_collections.
        
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
    
    async def fetch_services_by_creator(self, creator_username: str) -> List[ServiceInfo]:
        """
        Fetch services created by a specific user.
        
        Args:
            creator_username: Username of the service creator
            
        Returns:
            List of ServiceInfo objects for services created by the specified user
        """
        all_services = await self.fetch_services()
        return [service for service in all_services if service.creator_ep_username == creator_username]
    
    def fetch_services_by_creator_sync(self, creator_username: str) -> List[ServiceInfo]:
        """
        Synchronous version of fetch_services_by_creator.
        
        Args:
            creator_username: Username of the service creator
            
        Returns:
            List of ServiceInfo objects for services created by the specified user
        """
        all_services = self.fetch_services_sync()
        return [service for service in all_services if service.creator_ep_username == creator_username]
    
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

# Convenience function for quick access
def get_available_services(gateway_url: Optional[str] = None) -> List[ServiceInfo]:
    """
    Convenience function to quickly fetch all available services.
    
    Args:
        gateway_url: Optional gateway URL override
        
    Returns:
        List of ServiceInfo objects
    """
    fetcher = ServiceFetcher(gateway_url)
    return fetcher.fetch_services_sync()

# Example usage
if __name__ == "__main__":
    import asyncio
    
    # Example using environment variable
    # export EXTENSION_GATEWAY_URL=http://localhost:8000
    
    try:
        # Synchronous usage
        print("=== Synchronous Usage ===")
        fetcher = ServiceFetcher()
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
        print("Please set the EXTENSION_GATEWAY_URL environment variable")
    except Exception as e:
        print(f"Error: {e}")
