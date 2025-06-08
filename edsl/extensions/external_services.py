import requests
import json
import os
from edsl import Survey
from typing import Optional, List, Dict, Any, Callable, Type, Tuple
from collections import UserDict
from .authoring import ServiceDefinition
# Import loaders from the new module
from .service_loaders import ServiceLoader, APIServiceLoader, GithubYamlLoader
import logging

# Attempt to import Survey, but make it optional
from edsl import Survey

logger = logging.getLogger(__name__)

# --- Service Display Function ---

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

    Service configurations are loaded lazily using a configured ServiceLoader.
    Implemented as a singleton to ensure configurations are fetched only once.
    """
    _instance = None
    _initialized = False
    _fetched = False # Track if services have been fetched
    _loader: Optional[ServiceLoader] = None # Store the loader instance

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ExternalServices, cls).__new__(cls)
        return cls._instance

    def __init__(self,
                 loader: Optional[ServiceLoader] = None,
                 base_url: Optional[str] = None, # Keep for API loader default and fallback
                 ep_api_token: Optional[str] = None):
        """
        Initializes the ExternalServices client singleton.

        Args:
            loader (ServiceLoader, optional): The loader instance to use for fetching service definitions.
                                              If None, defaults to APIServiceLoader using base_url.
            base_url (str, optional): The base URL for the API gateway. Required if loader is None or is APIServiceLoader
                                      and wasn't initialized with a URL. Also used to configure services.
            ep_api_token (str, optional): The Expected Parrot API token. Used to configure services.
        """
        # Prevent re-initialization if already done with compatible settings
        if self._initialized:
            update_needed = False
            # Check if loader type/config changed OR base_url/token changed
            if loader and loader != self._loader: # Check if loader instance itself changed
                 update_needed = True
            elif base_url is not None and base_url != getattr(self, 'base_url', None): # Use getattr for safety
                update_needed = True
            elif ep_api_token is not None and ep_api_token != getattr(self, 'ep_api_token', None):
                update_needed = True

            if not update_needed:
                 logger.info("ExternalServices already initialized with compatible configuration.")
                 return # No changes needed
            else:
                # If config changes, we need to refetch services
                self._fetched = False
                self.data.clear() # Clear old prepared services
                logger.info("ExternalServices configuration changed. Services will be re-fetched.")

        # Determine the loader
        if loader:
             self._loader = loader
        else:
            self._loader = GithubYamlLoader()
            

        # Initialize UserDict
        super().__init__()

        # Store base_url and token for configuring ServiceDefinition objects later
        # Update config only if new values are provided or it's the first init
        # Important: These are stored on ExternalServices, not necessarily tied to the loader's source URL
        if base_url is not None:
            self.base_url = base_url.rstrip('/')
        elif not hasattr(self, 'base_url'):
             # Try to infer from loader if it's API based and URL is missing
             if isinstance(self._loader, APIServiceLoader):
                 self.base_url = self._loader.base_url # Use loader's URL as the service base URL
             else:
                 # Cannot infer base_url, needed for service calls even with other loaders
                 raise ValueError("base_url must be provided, even when using non-API loaders, to configure service calls.")


        if ep_api_token is not None:
            self.ep_api_token = ep_api_token
        elif not hasattr(self, 'ep_api_token'):
            self.ep_api_token = None # Default to None if not provided and not set


        # Don't fetch here; fetch lazily on first access or list
        self._initialized = True

    def _ensure_services_fetched(self):
        """Ensures services are fetched and prepared if not already done."""
        if not self._fetched:
            self._fetch_and_prepare_services()
            self._fetched = True

    def _fetch_and_prepare_services(self) -> None:
        """Internal method to fetch service configurations using the loader, prepare callables, and store them."""
        if not self._loader:
             logger.error("No service loader configured. Cannot fetch services.")
             self.data.clear()
             return

        logger.info("Using loader: %s", type(self._loader).__name__)
        services_data_list = self._loader.load_services() # Use the loader

        # Clear existing data before loading new definitions
        self.data.clear()

        if not services_data_list:
             logger.warning("Loader returned no service definitions.")
             return # _fetched remains False if loading failed/returned empty

        # Populate the dictionary with ServiceDefinition objects
        for service_data in services_data_list:
            if not isinstance(service_data, dict):
                 logger.warning("Skipping invalid service data item (not a dictionary): %s", service_data)
                 continue
            try:
                service_def = ServiceDefinition.from_dict(service_data)
                # Set internal config on the definition object using ExternalServices config
                # IMPORTANT: Use the base_url and token stored in ExternalServices,
                #            regardless of the loader type, as this determines where the calls go.
                service_def._base_url = getattr(self, 'base_url', None) # Use stored base_url
                service_def._ep_api_token = getattr(self, 'ep_api_token', None) # Use stored token

                if not service_def._base_url:
                     logger.warning("No base_url configured in ExternalServices. Service '%s' may not be callable.", service_def.name)

                # Store the configured ServiceDefinition object
                self.data[service_def.name] = service_def
            except Exception as e:
                logger.error("Error processing service definition for '%s': %s", service_data.get('name', 'Unknown'), e)
                # print(f"Service data: {service_data}") # Optional: for debugging

        # If loading succeeded (even if zero services were defined), mark as fetched.
        self._fetched = True
        logger.info("Finished processing %d service definitions.", len(self.data))


    def __getitem__(self, key: str) -> ServiceDefinition: # Return type is ServiceDefinition
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
            logger.info("No services available to list.")
            return

        # self.data directly contains ServiceDefinition objects
        service_definitions = list(self.data.values())

        if services_display_func:
            try:
                services_display_func(service_definitions)
            except Exception as e:
                 logger.error("Error in services_display_func: %s", e) # Log error

# Option 3: Default to API Loader via base_url (requires base_url to be set)
API_BASE_URL = os.getenv("EDSL_API_URL", "http://localhost:8000")
EP_API_TOKEN = os.getenv("EXPECTED_PARROT_API_KEY")
extensions = ExternalServices(base_url=API_BASE_URL, ep_api_token=EP_API_TOKEN)


if __name__ == "__main__":
    # Instantiate the client using the global 'extensions' instance
    # The configuration above determines which loader is used
    service_client = extensions

    # List available services (triggers config fetch AND displays them)
    print("\nListing available services:")
    service_client.list()
    print("--- End of service listing ---")

    # Example usage: Call a service (assuming one is defined, e.g., 'generate_survey_external')
    # This part remains the same, relying on the __getitem__ access
    if "generate_survey_external" in service_client:
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

            # Check the response type (same logic as before)
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

            else:
                print("\nService call returned None or empty response.")

         except KeyError as e: # Should not happen if check above passes, but good practice
            print(f"\nError: {e}")
         except requests.exceptions.RequestException as e:
            print(f"\nAPI Request Error: {e}") # Catch request errors from __call__
         except ValueError as e:
             print(f"\nError: Invalid parameters provided - {e}")
         except Exception as e:
            print(f"\nAn unexpected error occurred during service call: {e}")
    else:
         print("\n'generate_survey_external' service not found with the current loader configuration.")

    # Example: Demonstrate fetching a different service if available
    if "another_service_example" in service_client:
         print("\n=== Calling 'another_service_example' Service ===")
         try:
            # Assuming 'another_service_example' takes 'input_text'
            another_service = service_client["another_service_example"]
            result = another_service(input_text="Hello from EDSL!")
            print("Result from 'another_service_example':", result)
         except Exception as e:
            print(f"Error calling 'another_service_example': {e}")


