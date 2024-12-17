from typing import List, Any, Union, Dict, Optional, Generator
from pathlib import Path

from datetime import datetime, timedelta
import json
from platformdirs import user_cache_dir
from dataclasses import asdict

from edsl.inference_services.data_structures import LanguageModelInfo


class AvailableModelCacheHandler:

    CACHE_VALIDITY_HOURS = 48  # Cache validity period in hours

    def __init__(
        self,
        cache_validity_hours: int = 48,
        verbose: bool = False,
        testing_file_name: str = None,
    ):
        self.cache_validity_hours = cache_validity_hours
        self.verbose = verbose

        if testing_file_name:  # for testing purposes
            import tempfile

            self.cache_dir = Path(tempfile.mkdtemp())
            self.cache_file = self.cache_dir / testing_file_name
        else:
            self.cache_dir = Path(user_cache_dir("edsl", "model_availability"))
            self.cache_file = self.cache_dir / "available_models.json"
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def example_models(cls) -> List[LanguageModelInfo]:
        return [
            LanguageModelInfo(
                "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "deep_infra", 111
            ),
            LanguageModelInfo("openai/gpt-4o", "openai", 3),
        ]

    def add_models_to_cache(self, models_data: List[LanguageModelInfo]):
        """Add new models to the cache."""
        cache_data = self.read_cache()
        if not cache_data:
            cache_data = {"timestamp": datetime.now().isoformat(), "models": []}

        cache_data["models"].extend([asdict(entry) for entry in models_data])
        self.write_cache([LanguageModelInfo(**entry) for entry in cache_data["models"]])

    def write_cache(self, models_data: List[LanguageModelInfo]):
        """Write the model availability data to cache."""
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "models": [asdict(entry) for entry in models_data],
        }

        if self.verbose:
            print("Writing to cache at ", self.cache_file)
        with open(self.cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)

    def clear_cache(self):
        """Clear the cache file."""
        if self.cache_file.exists():
            self.cache_file.unlink()

    def models(self) -> List[LanguageModelInfo]:
        """Return the available models."""
        cache_data = self.read_cache()
        if not cache_data:
            return
        else:
            return [LanguageModelInfo(**entry) for entry in cache_data["models"]]

    def read_cache(self) -> Union[dict, None]:
        """Read the cached model availability data if it exists and is valid."""
        if self.verbose:
            print("Reading from cache at ", self.cache_file)

        if not self.cache_file.exists():
            if self.verbose:
                print("No cache file found")
            return None

        try:
            with open(self.cache_file, "r") as f:
                cache_data = json.load(f)

            # Check cache validity
            cache_time = datetime.fromisoformat(str(cache_data["timestamp"]))
            if self.verbose:
                print("Cache time: ", cache_time)

            if datetime.now() - cache_time > timedelta(hours=self.CACHE_VALIDITY_HOURS):
                return None

            return cache_data
        except (json.JSONDecodeError, KeyError, ValueError):
            return None


if __name__ == "__main__":
    pass
    # cache_handler = AvailableModelCacheHandler()
    # models_data = cache_handler.example_models()
    # cache_handler.write_cache(models_data)
    # print(cache_handler.models())
    # cache_handler.clear_cache()
    # print(cache_handler.models())
    # cache_handler.clear_cache()
    # print(cache_handler.models())
