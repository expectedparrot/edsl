import functools
import json
import requests
from typing import Optional
from edsl.data.CacheEntry import CacheEntry


def handle_request_exceptions(reraise=False):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.ConnectionError as e:
                print(f"Could not connect to remote server: {e}")
            except requests.exceptions.Timeout as e:
                print(f"Request timed out: {e}")
            except requests.exceptions.HTTPError as e:
                print(f"HTTP error occurred: {e}")
            except requests.exceptions.RequestException as e:
                print(f"An error occurred during the request: {e}")
            except ValueError as e:
                print(f"Invalid data format: {e}")

            if reraise:
                raise

        return wrapper

    return decorator


class RemoteDict:
    """
    A dictionary-like object that is an interface for a remote database.
    - You can use RemoteDict as a regular dictionary.
    - TODO: Implement the methods.
    """

    def __init__(self, base_url: str = None):
        self.base_url = base_url or "http://127.0.0.1:8000"

    def __bool__(self):
        return True

    def __setitem__(self, key: str, value: CacheEntry):
        response = requests.post(f"{self.base_url}/items/{key}", json=value.to_dict())
        response.raise_for_status()

    def __getitem__(self, key: str):
        response = requests.get(f"{self.base_url}/items/{key}")
        if response.status_code == 404:
            raise KeyError(f"Key '{key}' not found.")
        response.raise_for_status()
        return CacheEntry.from_dict(response.json())

    def get(self, key: str, default: Optional[CacheEntry] = None):
        try:
            return self[key]
        except KeyError:
            return default

    def __delitem__(self, key: str):
        response = requests.delete(f"{self.base_url}/items/{key}")
        if response.status_code == 404:
            raise KeyError(f"Key '{key}' not found.")
        response.raise_for_status()

    def __contains__(self, key: str):
        keys = self.keys()
        return key in keys

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        response = requests.get(f"{self.base_url}/items/count")
        response.raise_for_status()
        return response.json()["count"]

    def keys(self):
        response = requests.get(f"{self.base_url}/items/")
        response.raise_for_status()
        return response.json()

    def values(self) -> list[CacheEntry]:
        response = requests.get(f"{self.base_url}/items/values")
        response.raise_for_status()
        items = response.json()
        return [CacheEntry(**json.loads(item)) for item in items]


if __name__ == "__main__":
    api_dict = RemoteDict()

    # Add an item
    api_dict["example"] = CacheEntry.example()

    # Retrieve an item
    print(api_dict["example"])

    # Check if an item exists
    print("example" in api_dict)
