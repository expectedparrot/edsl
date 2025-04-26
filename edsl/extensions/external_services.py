import requests
import json
import os
from edsl import Survey
from typing import Optional, List, Dict, Any, Callable, Type, Tuple # Added Type, Tuple
from collections import UserDict # Added UserDict
from .authoring import ServiceDefinition # Import ServiceDefinition

# Attempt to import Survey, but make it optional
try:
    from edsl import Survey
except ImportError:
    Survey = None

def default_services_display_func(services: List[ServiceDefinition]) -> None:
    """Default function to display a list of services (name and description)."""
    if not services:
        return
    for service in services:
        try:
             # Using print for direct user output here as requested for the display func
             print(f"- {service.name}: {service.description}") # Access attributes directly
        except Exception as e:
            # print(f"Error displaying service '{getattr(service, "name", "Unknown")}': {e}")
            pass

class ExternalServices(UserDict):
    """
    Client for interacting with the EDSL external services API gateway.
    Acts as a dictionary where keys are service names and values are callable functions
    that execute the corresponding service API call.

    Service configurations are fetched lazily upon first access to a service or listing.
    Implemented as a singleton to ensure configurations are fetched only once.
    """
    _instance = None
    _initialized = False
    _fetched = False # Track if services have been fetched

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ExternalServices, cls).__new__(cls)
        return cls._instance

    def __init__(self, base_url: Optional[str] = None, ep_api_token: Optional[str] = None):
        """
        Initializes the ExternalServices client singleton.
        Subsequent calls will return the existing instance without re-initializing
        unless base_url or ep_api_token is provided and differs.

        Args:
            base_url (str, optional): The base URL of the API gateway. Required on first init.
            ep_api_token (str, optional): The Expected Parrot API token.
        """
        # Prevent re-initialization if already done with compatible settings
        if self._initialized:
            update_needed = False
            if base_url is not None and base_url != self.base_url:
                update_needed = True
            if ep_api_token is not None and ep_api_token != self.ep_api_token:
                 update_needed = True # Corrected logic to check if token differs
            
            if not update_needed:
                return # No changes needed
            else:
                # If config changes, we need to refetch services
                self._fetched = False
                self.data.clear() # Clear old prepared services
                print("ExternalServices re-initialized with new configuration. Services will be re-fetched.")

        if base_url is None and not hasattr(self, 'base_url'):
            raise ValueError("base_url must be provided on first initialization.")

        # Initialize UserDict
        super().__init__()

        # Update config only if new values are provided or it's the first init
        if base_url is not None:
            self.base_url = base_url.rstrip('/')
        if ep_api_token is not None:
            self.ep_api_token = ep_api_token
        elif not hasattr(self, 'ep_api_token'):
            self.ep_api_token = None

        # Don't fetch here; fetch lazily on first access or list
        self._initialized = True

    def _ensure_services_fetched(self):
        """Ensures services are fetched and prepared if not already done."""
        if not self._fetched:
            self._fetch_and_prepare_services()
            self._fetched = True

    def _fetch_and_prepare_services(self) -> None:
        """Internal method to fetch service configurations, prepare callables, and store them."""
        url = f"{self.base_url}/services"
        print(f"Fetching service configurations from {url}...") # Notify user
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            services_list = data.get("services", [])

            if not services_list:
                 print("Warning: No services found at the specified endpoint.")

            # Populate the dictionary with ServiceDefinition objects
            for service_data in services_list:
                try:
                    service_def = ServiceDefinition.from_dict(service_data)
                    # Set internal config on the definition object
                    service_def._base_url = self.base_url
                    service_def._ep_api_token = self.ep_api_token
                    # Store the configured ServiceDefinition object
                    self.data[service_def.name] = service_def
                except Exception as e:
                    print(f"Error processing service definition for '{service_data.get('name', 'Unknown')}': {e}")
                    # print(f"Service data: {service_data}") # Optional: for debugging

        except requests.exceptions.RequestException as e:
            print(f"Error fetching service configurations: {e}. Services will be unavailable.")
            # Ensure data is clear if fetch fails
            self.data.clear()
        except json.JSONDecodeError as e:
             print(f"Error decoding JSON response from {url}: {e}. Services will be unavailable.")
             self.data.clear()

    def __getitem__(self, key: str) -> Callable[..., Any]:
        """Accesses a ServiceDefinition object by name, which is callable."""
        self._ensure_services_fetched() # Fetch on first access
        try:
            service_def = super().__getitem__(key)
            # Return the callable ServiceDefinition object directly
            return service_def
        except KeyError:
            raise KeyError(f"Service '{key}' not found. Available services: {list(self.keys())}") from None

    def list(self, services_display_func: Optional[Callable[[List[ServiceDefinition]], None]] = default_services_display_func) -> None:
        """
        Fetches services (if needed) and calls the display function with ServiceDefinition objects.

        Args:
            services_display_func (Optional[Callable[[List[ServiceDefinition]], None]]): 
                A function to display the list of services. Defaults to printing name/description.
                Set to None to disable display.
        """
        self._ensure_services_fetched() # Ensure services are available
        
        if not self.data: # Check if fetch failed or no services
            print("No services available to list.")
            return

        # self.data directly contains ServiceDefinition objects
        service_definitions = list(self.data.values())

        if services_display_func:
            try:
                services_display_func(service_definitions)
            except Exception as e:
                 print(f"Error in services_display_func: {e}") # Log error

# Configuration at the bottom remains largely the same
API_BASE_URL = os.getenv("EDSL_API_URL", "http://localhost:8000") # Use env var with fallback
EP_API_TOKEN = os.getenv("EXPECTED_PARROT_API_KEY")

# Instantiate the client (gets the singleton instance)
# Provide config on first instantiation or if changes are needed
extensions = ExternalServices(base_url=API_BASE_URL, ep_api_token=EP_API_TOKEN)
     

if __name__ == "__main__":
    # Instantiate the client using the global 'extensions' instance
    service_client = extensions 
    
    # List available services (triggers config fetch AND displays them)
    print("Listing available services:")
    service_client.list()
    print("--- End of service listing ---")
    
    # Example usage: Call the generate_survey_external service using dict access
    print("\n=== Calling 'generate_survey_external' Service ===")
    overall_question = "What is the parrot situation in Aruba?"
    population = "Residents of Aruba"

    try:
        # Access the callable ServiceDefinition object
        generate_survey_service = service_client["generate_survey_external"]
        # Call the object directly with parameters
        survey_response = generate_survey_service(
            overall_question=overall_question,
            population=population
        )

        # Check the response type
        if survey_response:
            print("\nService call successful!")
            if isinstance(survey_response, Survey):
                 print("Response deserialized into Survey object:")
                 print(survey_response) # Relies on Survey.__str__ or __repr__
            elif isinstance(survey_response, dict):
                print("Response received as dictionary:")
                print(json.dumps(survey_response, indent=2))
            else:
                 print("Response received (unknown type):")
                 print(survey_response)
            
            # Example check if it returned a dict (like the simulator)
            if isinstance(survey_response, dict) and survey_response.get("survey_id") == "simulated_survey_123":
                 print("\nSuccessfully received expected response from the simulator.")

        else:
            print("\nService call returned None or empty response.")

    except KeyError as e:
        print(f"\nError: {e}")
    except requests.exceptions.RequestException as e:
        print(f"\nAPI Request Error: {e}") # Catch request errors from __call__
    except ValueError as e:
         print(f"\nError: Invalid parameters provided - {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during service call: {e}")


