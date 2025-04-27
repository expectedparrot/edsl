import requests
import json
import yaml
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

# --- Service Loader Abstraction ---

class ServiceLoader(ABC):
    """Abstract base class for loading service definitions."""

    @abstractmethod
    def load_services(self) -> List[Dict[str, Any]]:
        """
        Loads service definitions and returns them as a list of dictionaries.
        Each dictionary should conform to the structure expected by ServiceDefinition.from_dict.
        """
        pass

# --- Concrete Loader Implementations ---

class APIServiceLoader(ServiceLoader):
    """Loads service definitions from a remote API endpoint."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.url = f"{self.base_url}/services"

    def load_services(self) -> List[Dict[str, Any]]:
        """Fetches service configurations from the API."""
        print(f"Fetching service configurations from {self.url}...") # Notify user
        try:
            response = requests.get(self.url)
            response.raise_for_status()
            data = response.json()
            services_list = data.get("services", [])
            if not services_list:
                print("Warning: No services found at the specified endpoint.")
            return services_list
        except requests.exceptions.RequestException as e:
            print(f"Error fetching service configurations via API: {e}. Services will be unavailable.")
            return []
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from {self.url}: {e}. Services will be unavailable.")
            return []


class GithubYamlLoader(ServiceLoader):
    """Loads service definitions from YAML files in a public GitHub repository directory."""
    # TODO: Implement SSL certificate verification bypass option if needed, or document cert setup.
    GITHUB_API_BASE = "https://api.github.com/repos"

    def __init__(self, repo_owner: str = 'expectedparrot', 
                 repo_name: str = 'extensions', 
                 directory_path: str = 'service_definitions', 
                 github_token: Optional[str] = None):
        """
        Initializes the loader for a specific GitHub directory.

        Defaults to loading from 'expectedparrot/extensions/service_definitions'.

        Args:
            repo_owner (str): The owner of the GitHub repository. Defaults to 'expectedparrot'.
            repo_name (str): The name of the repository. Defaults to 'extensions'.
            directory_path (str): The path to the directory containing YAML service definitions within the repo.
                                 Defaults to 'service_definitions'. Use '' for the root directory.
            github_token (str, optional): A GitHub personal access token for accessing private repos
                                          or avoiding rate limits. Defaults to None (public access only).
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.directory_path = directory_path.strip('/')
        self._headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
             self._headers["Authorization"] = f"token {github_token}"


    def _get_api_url(self) -> str:
        """Constructs the GitHub API URL for the target directory contents."""
        return f"{self.GITHUB_API_BASE}/{self.repo_owner}/{self.repo_name}/contents/{self.directory_path}"

    def _fetch_directory_contents(self, api_url: str) -> Optional[List[Dict[str, Any]]]:
        """Fetches and performs basic validation on the directory contents from GitHub API."""
        try:
            response = requests.get(api_url, headers=self._headers)
            response.raise_for_status()
            contents = response.json()

            if not isinstance(contents, list):
                print(f"Warning: Expected a list of files from GitHub API at {api_url}, but got {type(contents)}. Cannot load services.")
                return None
            return contents
        except requests.exceptions.RequestException as e:
            print(f"Error fetching directory contents from GitHub API ({api_url}): {e}. Services will be unavailable.")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from GitHub API ({api_url}): {e}. Services will be unavailable.")
            return None
        except Exception as e: # Catch other potential errors
             print(f"An unexpected error occurred fetching directory contents from GitHub ({api_url}): {e}")
             return None

    def _fetch_and_parse_yaml_file(self, file_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetches and parses a single YAML file from GitHub, expecting a dictionary."""
        file_url = file_info.get('download_url')
        file_name = file_info.get('name')

        if not file_url:
            print(f"Warning: Could not get download URL for file '{file_name}'. Skipping.")
            return None

        try:
            print(f"  Fetching {file_name}...")
            file_response = requests.get(file_url, headers=self._headers) # Use headers for private repos too
            file_response.raise_for_status()
            yaml_content = file_response.text

            # Parse YAML content - expecting a single dictionary per file
            service_data = yaml.safe_load(yaml_content)

            if isinstance(service_data, dict):
                return service_data
            else:
                print(f"Warning: Could not parse a valid service definition (dictionary) from '{file_name}'. Got {type(service_data)}. Skipping file.")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Error fetching file '{file_name}' from {file_url}: {e}")
            return None
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file '{file_name}': {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred processing file '{file_name}': {e}")
            return None


    def load_services(self) -> List[Dict[str, Any]]:
        """Fetches and parses YAML service definitions from the GitHub directory."""
        api_url = self._get_api_url()
        print(f"Fetching service definitions from GitHub: {self.repo_owner}/{self.repo_name}/{self.directory_path}")

        contents = self._fetch_directory_contents(api_url)
        if contents is None:
            return [] # Error fetching directory contents

        # Filter for YAML files
        yaml_files_info = [
            item for item in contents
            if item.get('type') == 'file' and (item['name'].endswith('.yaml') or item['name'].endswith('.yml'))
        ]

        if not yaml_files_info:
            print(f"No YAML files found in {self.repo_owner}/{self.repo_name}/{self.directory_path}")
            return []

        loaded_services = []
        for file_info in yaml_files_info:
            service_data = self._fetch_and_parse_yaml_file(file_info)
            if service_data:
                 loaded_services.append(service_data)

        print(f"Successfully loaded {len(loaded_services)} service definition(s) from GitHub.")
        return loaded_services 

if __name__ == "__main__":
    print("Testing GithubYamlLoader with default settings...")
    github_loader = GithubYamlLoader() 
    github_services = github_loader.load_services()

    if github_services:
        print(f"\nLoaded {len(github_services)} service(s) from GitHub:")
        # Print names or basic info for verification
        for i, service in enumerate(github_services):
            print(f"  {i+1}. Name: {service.get('name', 'N/A')}") 
    else:
        print("\nNo services loaded from GitHub using default settings.")

    # Example of testing APIServiceLoader (optional, might need a running server)
    # print("\nTesting APIServiceLoader...")
    # api_loader = APIServiceLoader(base_url="http://localhost:8000") # Replace with actual API URL
    # api_services = api_loader.load_services()
    # if api_services:
    #     print(f"Loaded {len(api_services)} service(s) from API:")
    #     for i, service in enumerate(api_services):
    #         print(f"  {i+1}. Name: {service.get('name', 'N/A')}")
    # else:
    #     print("No services loaded from API.") 