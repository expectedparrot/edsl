import requests
import json
from typing import Optional, List
from edsl.data.CacheEntry import CacheEntry

class RemoteDict:

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
    
    def values(self) -> List[CacheEntry]:
        response = requests.get(f"{self.base_url}/items/values")
        response.raise_for_status()
        items = response.json()
        return [CacheEntry(**json.loads(item)) for item in items]


if __name__ == "__main__":
    api_dict = APIDict()

    # Add an item
    api_dict["example"] = CacheEntry.example()

    # Retrieve an item
    print(api_dict["example"])

    # Check if an item exists
    print("example" in api_dict)

# Delete an item
#del api_dict["example"]