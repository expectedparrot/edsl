from typing import Dict, List, Any, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
from collections import UserDict
import datetime
import os

if TYPE_CHECKING:
    from .inference_service_registry import InferenceServiceRegistry
    from .model_info import ModelInfo


class ModelInfoFetcherABC(UserDict, ABC):
    """Registry for all model info fetcher classes."""

    _registry: Dict[str, type] = {}

    def __init_subclass__(cls, **kwargs):
        """Automatically register all subclasses and validate fetcher_name."""
        super().__init_subclass__(**kwargs)

        # Require fetcher_name attribute
        if not hasattr(cls, "fetcher_name"):
            raise AttributeError(
                f"Class {cls.__name__} must define a 'fetcher_name' class attribute"
            )

        if not isinstance(cls.fetcher_name, str):
            raise TypeError(
                f"Class {cls.__name__} fetcher_name must be a string, got {type(cls.fetcher_name)}"
            )

        # Register the class
        if cls.fetcher_name in cls._registry:
            raise ValueError(
                f"Fetcher name '{cls.fetcher_name}' is already registered by {cls._registry[cls.fetcher_name].__name__}"
            )

        cls._registry[cls.fetcher_name] = cls

    @classmethod
    def get_registered_fetchers(cls) -> Dict[str, type]:
        """Get all registered fetcher classes."""
        return cls._registry.copy()

    @classmethod
    def get_fetcher_by_name(cls, fetcher_name: str) -> type:
        """Get a fetcher class by its name."""
        if fetcher_name not in cls._registry:
            raise ValueError(
                f"No fetcher registered with name '{fetcher_name}'. Available: {list(cls._registry.keys())}"
            )
        return cls._registry[fetcher_name]

    """
    Abstract base class for model information fetchers.
    
    This ABC defines the interface that all model fetchers must implement,
    providing a consistent way to fetch model information from different sources.
    
    Inherits from UserDict, so instances can be used as dictionaries where:
    - Keys are service names (str)
    - Values are lists of models (List[Any])
    
    Args:
        verbose: Enable verbose logging output
        data: Optional initial data dictionary with service names as keys and model lists as values
    """

    def __init__(
        self,
        registry: "InferenceServiceRegistry",
        verbose: bool = False,
        data: Optional[Dict[str, List["ModelInfo"]]] = None,
    ):
        self.data: Dict[str, List["ModelInfo"]] = data or {}
        self.verbose = verbose
        self.services_registry = registry

    def fetch(self, **kwargs) -> None:
        """
        Fetch model information and store in self.data.

        Args:
            **kwargs: Additional arguments (ignored for Coop implementation)
        """
        data = self._fetch(**kwargs)
        self.data.update(data)

    @abstractmethod
    def _fetch(self, **kwargs) -> Dict[str, List["ModelInfo"]]:
        """
        Abstract method to fetch model information and populate self.data.

        This method should fetch model information and store it in self.data
        where keys are service names and values are lists of models.

        Args:
            **kwargs: Additional keyword arguments for the specific implementation

        Returns:
            Dict[str, List["ModelInfo"]] - Dictionary mapping service names to lists of ModelInfo objects

        Raises:
            NotImplementedError: If not implemented by concrete class
        """
        pass

    def __repr__(self) -> str:
        """
        Return a string representation showing services, model counts, and sample model names.

        Format like a pandas table with one service per line:
        Service       Models  Sample
        openai        5       gpt-4, gpt-3.5-turbo, text-davinci-003, ...
        anthropic     3       claude-3-opus, claude-3-sonnet, ...

        Truncates sample model names at 82 characters total width if needed.
        """
        if not self.data:
            return f"{self.__class__.__name__}: no data"

        lines = []
        lines.append("Service       Models  Sample")

        for service_name, models in self.data.items():
            model_count = len(models) if models else 0

            if model_count == 0:
                sample_str = ""
            else:
                # Show first few model names
                sample_models = (
                    models[:3] if isinstance(models, list) else list(models)[:3]
                )
                sample_str = ", ".join(str(model) for model in sample_models)
                if model_count > 3:
                    sample_str += ", ..."

            # Format line with proper spacing
            service_col = f"{service_name:<12}"
            models_col = f"{model_count:<6}"

            # Check if line would exceed 82 characters and truncate sample if needed
            line_without_sample = f"{service_col}  {models_col}  "
            available_width = 82 - len(line_without_sample)

            if len(sample_str) > available_width and available_width > 3:
                sample_str = sample_str[: available_width - 3] + "..."

            line = f"{service_col}  {models_col}  {sample_str}"
            lines.append(line)

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the fetcher instance to a dictionary representation.

        Returns:
            Dictionary containing the fetcher's state, including:
            - data: The fetched model data
            - fetcher_name: The fetcher name for reconstruction (preferred)
            - class_name: The name of the concrete class for backward compatibility
        """
        return {
            "data": dict(self.data),
            "fetcher_name": self.fetcher_name,
            "class_name": self.__class__.__name__,
        }

    @classmethod
    def from_dict(cls, data_dict: Dict[str, Any]) -> "ModelInfoFetcherABC":
        """
        Create a fetcher instance from a dictionary representation.

        This method reconstructs the appropriate concrete class based on the
        fetcher_name stored in the dictionary.

        Args:
            data_dict: Dictionary containing the fetcher's state with keys:
                - data: The model data to restore
                - fetcher_name: The name of the fetcher to instantiate (uses registry)
                - class_name: (deprecated) The class name - will be converted to fetcher_name

        Returns:
            An instance of the appropriate concrete fetcher class

        Raises:
            ValueError: If fetcher_name is not recognized or data_dict is invalid
        """
        if not isinstance(data_dict, dict):
            raise ValueError("data_dict must be a dictionary")

        # Support both old class_name format and new fetcher_name format
        fetcher_name = data_dict.get("fetcher_name")
        class_name = data_dict.get("class_name")

        if fetcher_name:
            # New format using fetcher_name
            concrete_class = cls.get_fetcher_by_name(fetcher_name)
        elif class_name:
            # Legacy format using class_name - convert to fetcher_name
            class_to_fetcher_mapping = {
                "ModelInfoCoopRegular": "coop_regular",
                "ModelInfoCoopWorking": "coop_working",
                "ModelInfoServices": "services",
                "ModelInfoArchive": "archive",
            }

            if class_name not in class_to_fetcher_mapping:
                raise ValueError(f"Unknown class name: {class_name}")

            mapped_fetcher_name = class_to_fetcher_mapping[class_name]
            concrete_class = cls.get_fetcher_by_name(mapped_fetcher_name)
        else:
            raise ValueError(
                "data_dict must contain either 'fetcher_name' or 'class_name' key"
            )

        # Create instance of the appropriate class
        instance = concrete_class(
            registry=None,  # Will need to be set by caller if needed
            verbose=False,
            data=data_dict.get("data", {}),
        )

        return instance

    def write_to_archive(self, archive_path: str = ".edsl_model_archive.json") -> None:
        """
        Write the current data to a Python archive file.

        Creates a Python file with the current timestamp and data that can be
        imported and used by the ModelInfoArchive fetcher.

        Args:
            archive_path: Path where to write the archive file (default: ".edsl_model_archive.json")
        """
        import json

        # Get current timestamp
        timestamp = datetime.datetime.now().isoformat()

        # Convert ModelInfo objects to their raw data format for archiving
        serializable_data = {}
        for service_name, models in self.data.items():
            serializable_models = []
            for model in models:
                serializable_models.append(model.to_dict())
            serializable_data[service_name] = serializable_models

        archive_data = {
            "metadata": {
                "title": "Model Information Archive",
                "description": f"This archive contains data about available models. Auto-generated on {timestamp}.",
                "created_at": timestamp,
                "fetcher_name": self.fetcher_name,
            },
            "created_at": timestamp,
            "data": serializable_data,
        }

        # Write to file
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(archive_data, f, indent=4)

        if self.verbose:
            print(
                f"[MODEL_FETCHER] Wrote archive to {archive_path} with {len(self.data)} services"
            )


class ModelInfoCoopRegular(ModelInfoFetcherABC):
    """
    Fetcher for regular model information from the Coop API.

    This class handles the retrieval of model lists from the Coop API,
    providing access to centralized model information.

    Args:
        verbose: Enable verbose logging output
    """

    fetcher_name = "coop"

    def _fetch(self, **kwargs) -> Dict[str, List["ModelInfo"]]:
        """
        Fetch regular model information from the Coop API and store in self.data.

        Args:
            **kwargs: Additional arguments (ignored for Coop implementation)

        Returns:
            Dict[str, List["ModelInfo"]] - Dictionary mapping service names to lists of ModelInfo objects

        Raises:
            Exception: If Coop API call fails
        """
        if self.verbose:
            print(
                "[MODEL_FETCHER_COOP_REGULAR] Fetching regular models from Coop API..."
            )

        from ..coop import Coop
        from .model_info import ModelInfo

        # Get raw data from Coop API
        raw_data = Coop().fetch_models()

        # Convert strings to ModelInfo objects
        data = {}
        for service_name, model_names in raw_data.items():
            data[service_name] = [
                ModelInfo.from_raw({"id": model_name}, service_name, model_name)
                for model_name in model_names
            ]

        return data


class ModelInfoCoopWorking(ModelInfoFetcherABC):
    """
    Fetcher for working model information from the Coop API.

    This class handles the retrieval of working models with pricing and capability
    information from the Coop API.

    Args:
        verbose: Enable verbose logging output
    """

    fetcher_name = "coop_working"

    def _fetch(self, **kwargs) -> Dict[str, List["ModelInfo"]]:
        """
        Fetch working models with pricing and capability information from the Coop API and store in self.data.

        Args:
            return_type: Either "list" for List[dict] or "scenario_list" for ScenarioList
            **kwargs: Additional arguments (ignored for Coop implementation)

        Returns:
            Dict[str, List["ModelInfo"]] - Dictionary mapping service names to lists of ModelInfo objects

        Example:
            fetcher = ModelInfoCoopWorking()
            fetcher.fetch("list")
            working_models = fetcher["working_models"]  # Access via dict interface

        Raises:
            Exception: If Coop API call fails
        """
        if self.verbose:
            print(
                "[MODEL_FETCHER_COOP_WORKING] Fetching working models from Coop API..."
            )

        from ..coop import Coop
        from .model_info import ModelInfo
        from collections import defaultdict

        c = Coop()
        working_models = c.fetch_working_models()

        data = defaultdict(list)
        for model in working_models:
            service_name = model["service"]
            model_id = model["model"]
            # Create ModelInfo object with the rich model data from working models
            model_info = ModelInfo.from_raw(
                {
                    "id": model_id,
                    "works_with_text": model.get("works_with_text", False),
                    "works_with_images": model.get("works_with_images", False),
                    "usd_per_1M_input_tokens": model.get("usd_per_1M_input_tokens", 0),
                    "usd_per_1M_output_tokens": model.get(
                        "usd_per_1M_output_tokens", 0
                    ),
                },
                service_name,
                model_id,
            )
            data[service_name].append(model_info)

        return data


class ModelInfoServices(ModelInfoFetcherABC):
    """
    Fetcher for model information directly from inference service APIs.

    This class handles the retrieval of model lists by querying each registered
    inference service directly through their APIs.

    Args:
        verbose: Enable verbose logging output
    """

    fetcher_name = "local"

    def _fetch(self, **kwargs) -> Dict[str, List["ModelInfo"]]:
        """
        Fetch model information directly from inference service APIs and store in self.data.

        Args:
            **kwargs: Additional arguments:
                - services_registry: Required - Dictionary of registered service classes
                - skip_errors: Whether to skip services that fail to load models (default True)

        Returns:
            Dict[str, List["ModelInfo"]] - Dictionary mapping service names to lists of ModelInfo objects

        Raises:
            ValueError: If services_registry is not provided
        """
        skip_errors = kwargs.get("skip_errors", True)
        data = {}
        for service_name, service_entry in self.services_registry.services.items():
            try:
                model_list = service_entry.get_model_list()
                data[service_name] = model_list
            except Exception as e:
                if skip_errors:
                    if self.verbose:
                        print(f"Error fetching model list for {service_name}: {e}")
                    continue
                else:
                    raise e

        return data


class ModelInfoArchive(ModelInfoFetcherABC):
    """
    Fetcher that loads model information from an archive file.

    This class loads model information from a previously saved archive file,
    without making any external API calls. The archive file should contain
    a 'data' variable with the model information.

    Args:
        verbose: Enable verbose logging output
        archive_path: Path to the archive file (default: ".edsl_model_archive.json")
    """

    fetcher_name = "archive"

    def __init__(
        self,
        registry: "InferenceServiceRegistry",
        verbose: bool = False,
        data: Optional[Dict[str, List["ModelInfo"]]] = None,
        archive_path: str = ".edsl_model_archive.json",
    ):
        super().__init__(registry, verbose, data)
        self.archive_path = archive_path

    def _fetch(self, **kwargs) -> Dict[str, List["ModelInfo"]]:
        """
        Load model information from the archive file.

        Args:
            **kwargs: Additional arguments:
                - archive_path: Override the default archive path

        Returns:
            Dict[str, List["ModelInfo"]] - Dictionary mapping service names to lists of ModelInfo objects loaded from archive

        Raises:
            FileNotFoundError: If archive file doesn't exist
            ImportError: If archive file can't be imported
            AttributeError: If archive file doesn't have required 'data' attribute
        """
        import json
        from .model_info import ModelInfo

        try:
            with open(self.archive_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Archive file not found at {self.archive_path}")
        except json.JSONDecodeError:
            raise json.JSONDecodeError(
                f"Invalid JSON in archive file {self.archive_path}"
            )
        except Exception as e:
            raise Exception(f"Error loading archive file {self.archive_path}: {e}")

        # Convert archived data (which may be strings) to ModelInfo objects
        converted_data = {}
        for service_name, models in data.get("data", {}).items():
            converted_models = []
            for model in models:
                converted_models.append(ModelInfo.from_dict(model))
            converted_data[service_name] = converted_models

        return converted_data


if __name__ == "__main__":
    # Example usage of the archive functionality
    print("=== Testing Archive Functionality ===")

    # Create a fetcher with some sample data
    class TestFetcher(ModelInfoFetcherABC):
        fetcher_name = "test"

        def _fetch(self, **kwargs):
            return {
                "openai": ["gpt-4o", "gpt-4", "gpt-3.5-turbo"],
                "anthropic": ["claude-3-opus", "claude-3-sonnet"],
                "google": ["gemini-pro", "gemini-pro-vision"],
            }

    # Create and populate a test fetcher
    test_fetcher = TestFetcher(registry=None, verbose=True)
    test_fetcher.fetch()

    print("Original data:")
    print(test_fetcher)

    # Write to archive
    print("\n=== Writing to Archive ===")
    test_fetcher.write_to_archive()

    # Load from archive
    print("\n=== Loading from Archive ===")
    archive_fetcher = ModelInfoArchive(registry=None, verbose=True)
    archive_fetcher.fetch()

    print("Archive data:")
    print(archive_fetcher)

    # Clean up test archive file
    if os.path.exists(".edsl_model_archive.json"):
        print("\n=== Cleaning up test archive ===")
        os.remove(".edsl_model_archive.json")
        print("Removed .edsl_model_archive.json")

    # Uncomment these to test other fetchers
    # fetcher_coop = ModelInfoCoopRegular()
    # fetcher_coop.fetch()

    # fetcher_coop_working = ModelInfoCoopWorking()
    # fetcher_coop_working.fetch()

    # fetcher_services = ModelInfoServices()
    # fetcher_services.fetch()
