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
    # Github API base URL
    GITHUB_API_BASE = "https://api.github.com/repos"

    def __init__(self, repo_owner: str, repo_name: str, directory_path: str = '', github_token: Optional[str] = None):
        """
        Initializes the loader for a specific GitHub directory.

        Args:
            repo_owner (str): The owner of the GitHub repository (e.g., 'expectedparrot').
            repo_name (str): The name of the repository (e.g., 'edsl').
            directory_path (str): The path to the directory containing YAML service definitions within the repo.
                                 Use '' for the root directory.
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

    def load_services(self) -> List[Dict[str, Any]]:
        """Fetches and parses YAML service definitions from the GitHub directory."""
        api_url = self._get_api_url()
        print(f"Fetching service definitions from GitHub: {self.repo_owner}/{self.repo_name}/{self.directory_path}")

        loaded_services = []
        try:
            # Get directory contents
            response = requests.get(api_url, headers=self._headers)
            response.raise_for_status()
            contents = response.json()

            if not isinstance(contents, list):
                print(f"Warning: Expected a list of files from GitHub API at {api_url}, but got {type(contents)}. No services loaded.")
                return []

            # Filter for YAML files and fetch content
            yaml_files = [item for item in contents if item.get('type') == 'file' and (item['name'].endswith('.yaml') or item['name'].endswith('.yml'))]

            if not yaml_files:
                print(f"No YAML files found in {self.repo_owner}/{self.repo_name}/{self.directory_path}")
                return []

            for file_info in yaml_files:
                file_url = file_info.get('download_url')
                file_name = file_info.get('name')
                if not file_url:
                    print(f"Warning: Could not get download URL for file '{file_name}'. Skipping.")
                    continue

                try:
                    print(f"  Fetching {file_name}...")
                    file_response = requests.get(file_url, headers=self._headers) # Use headers for private repos too
                    file_response.raise_for_status()
                    yaml_content = file_response.text

                    # Parse YAML content
                    # Use safe_load to prevent arbitrary code execution
                    service_data_list = yaml.safe_load(yaml_content)

                    # Handle cases where YAML might contain a list of services or a single service
                    if isinstance(service_data_list, dict): # Single service definition in the file
                        loaded_services.append(service_data_list)
                    elif isinstance(service_data_list, list): # List of services in the file
                         for service_data in service_data_list:
                             if isinstance(service_data, dict):
                                 loaded_services.append(service_data)
                             else:
                                 print(f"Warning: Found non-dictionary item in list within '{file_name}'. Skipping item.")
                    else:
                        print(f"Warning: Could not parse valid service definition(s) from '{file_name}'. Expected dict or list, got {type(service_data_list)}. Skipping file.")

                except requests.exceptions.RequestException as e:
                    print(f"Error fetching file '{file_name}' from {file_url}: {e}")
                except yaml.YAMLError as e:
                    print(f"Error parsing YAML file '{file_name}': {e}")
                except Exception as e:
                    print(f"An unexpected error occurred processing file '{file_name}': {e}")


        except requests.exceptions.RequestException as e:
            print(f"Error fetching directory contents from GitHub API ({api_url}): {e}. Services will be unavailable.")
            return [] # Return empty list on directory fetch error
        except Exception as e: # Catch other potential errors like JSON decoding of directory listing
             print(f"An unexpected error occurred fetching from GitHub ({api_url}): {e}")
             return []

        print(f"Successfully loaded {len(loaded_services)} service definition(s) from GitHub.")
        return loaded_services 