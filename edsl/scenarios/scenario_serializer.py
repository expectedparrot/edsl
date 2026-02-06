"""
Scenario serialization functionality.

This module contains the ScenarioSerializer class which handles all serialization
and deserialization operations for Scenario objects. This includes converting to/from
dictionaries, datasets, and hash computation.

The ScenarioSerializer provides:
- Dictionary serialization/deserialization with version handling
- Dataset conversion functionality
- Hash computation for scenario instances
- Special handling for FileStore and Prompt objects
- Base64 offloading capabilities for memory optimization
"""

from __future__ import annotations
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scenario import Scenario
    from ..dataset import Dataset


class ScenarioSerializer:
    """
    Handles serialization and deserialization operations for Scenario objects.

    This class provides methods for converting Scenario objects to and from various
    formats including dictionaries and datasets. It also handles hash computation
    and special serialization requirements for embedded objects like FileStore.
    """

    def __init__(self, scenario: "Scenario"):
        """
        Initialize the serializer with a Scenario instance.

        Args:
            scenario: The Scenario instance to serialize.
        """
        self.scenario = scenario

    def to_dict(
        self, add_edsl_version: bool = True, offload_base64: bool = False
    ) -> dict:
        """Convert a scenario to a dictionary.

        Args:
            add_edsl_version: If True, adds the EDSL version to the returned dictionary.
            offload_base64: If True, replaces any base64_string fields with 'offloaded'
                           to reduce memory usage.

        Returns:
            A dictionary representation of the scenario.

        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"food": "wood chips"})
            >>> serializer = ScenarioSerializer(s)
            >>> result = serializer.to_dict()  # doctest: +ELLIPSIS
            >>> 'food' in result and 'edsl_version' in result
            True

            >>> serializer.to_dict(add_edsl_version=False)
            {'food': 'wood chips'}
        """
        from edsl.scenarios import FileStore
        from edsl.scenarios.dimension import Dimension
        from edsl.prompts import Prompt

        d = self.scenario.data.copy()
        for key, value in d.items():
            # Check for NaN values and replace with None for JSON serialization
            if isinstance(value, float) and math.isnan(value):
                d[key] = None
            elif isinstance(value, Dimension):
                d[key] = value.to_dict()
            elif isinstance(value, FileStore) or isinstance(value, Prompt):
                value_dict = value.to_dict(add_edsl_version=add_edsl_version)
                if isinstance(value_dict, dict) and "base64_string" in value_dict:
                    # Auto-offload if already uploaded to GCS (has file_uuid)
                    gcs_info = value_dict.get("external_locations", {}).get("gcs", {})
                    if gcs_info.get("uploaded") and gcs_info.get("file_uuid"):
                        value_dict["base64_string"] = "offloaded"
                    # Also offload if explicitly requested
                    elif offload_base64:
                        value_dict["base64_string"] = "offloaded"
                d[key] = value_dict

        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Scenario"

        return d

    def compute_hash(self) -> int:
        """Return a hash of the scenario.

        Returns:
            A hash integer representing the scenario's content.

        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"food": "wood chips"})
            >>> serializer = ScenarioSerializer(s)
            >>> serializer.compute_hash()
            1153210385458344214
        """
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    def to_dataset(self) -> "Dataset":
        """Convert a scenario to a dataset.

        Returns:
            A Dataset object containing the scenario's key-value pairs.

        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"food": "wood chips"})
            >>> serializer = ScenarioSerializer(s)
            >>> serializer.to_dataset()  # doctest: +SKIP
            Dataset([{'key': ['food']}, {'value': ['wood chips']}])
        """
        try:
            from ..dataset import Dataset
        except ImportError:
            from edsl.dataset import Dataset

        keys = list(self.scenario.keys())
        values = list(self.scenario.values())
        return Dataset([{"key": keys}, {"value": values}])

    @classmethod
    def from_dict(cls, d: dict) -> "Scenario":
        """
        Creates a Scenario from a dictionary, with special handling for FileStore and Dimension objects.

        This method creates a Scenario using the provided dictionary. It has special handling
        for dictionary values that represent serialized FileStore or Dimension objects, which it will
        deserialize back into proper instances.

        Args:
            d: A dictionary to convert to a Scenario.

        Returns:
            A new Scenario containing the provided dictionary data.

        Examples:
            >>> result = ScenarioSerializer.from_dict({"food": "wood chips"})  # doctest: +SKIP
            >>> result  # doctest: +SKIP
            Scenario({'food': 'wood chips'})

        Notes:
            - Any dictionary values that match the FileStore format will be converted to FileStore objects
            - Any dictionary values that match the Dimension format will be converted to Dimension objects
            - The method detects FileStore objects by looking for "base64_string" and "path" keys
            - The method detects Dimension objects by looking for "name", "description", and "values" keys
            - EDSL version information is automatically removed
            - This method is commonly used when deserializing scenarios from JSON or other formats
        """
        from edsl.scenarios import FileStore
        from edsl.scenarios.dimension import Dimension

        # Remove EDSL version information manually
        data_copy = dict(d)
        data_copy.pop("edsl_version", None)
        data_copy.pop("edsl_class_name", None)

        for key, value in data_copy.items():
            # Check if it's a Dimension object
            if (
                isinstance(value, dict)
                and "name" in value
                and "description" in value
                and "values" in value
                and len(value) == 3  # Ensure it only has these 3 keys
            ):
                data_copy[key] = Dimension.from_dict(value)
            # TODO: we should check this better if its a FileStore + add remote security check against path traversal
            elif (
                isinstance(value, dict) and "base64_string" in value and "path" in value
            ) or isinstance(value, FileStore):
                data_copy[key] = FileStore.from_dict(value)

        # Import here to avoid circular imports
        try:
            from .scenario import Scenario
        except ImportError:
            from edsl.scenarios import Scenario
        return Scenario(data_copy)
