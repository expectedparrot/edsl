"""
Module for handling base64 content offloading in Scenario objects.

This module provides the ScenarioOffloader class which handles the logic for 
offloading base64-encoded content from scenarios by replacing 'base64_string'
fields with 'offloaded' to reduce memory usage.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .scenario import Scenario


class ScenarioOffloader:
    """
    Handles offloading of base64-encoded content from Scenario objects.
    
    This class provides functionality to replace base64-encoded content in scenarios
    with placeholder text to reduce memory usage while preserving the scenario structure.
    """
    
    def __init__(self, scenario: "Scenario"):
        """
        Initialize the offloader with a scenario.
        
        Args:
            scenario: The Scenario object to process for offloading.
        """
        self.scenario = scenario
    
    def offload(self, inplace: bool = False) -> "Scenario":
        """
        Offload base64-encoded content from the scenario.
        
        This method replaces 'base64_string' fields with 'offloaded' to reduce 
        memory usage. It handles three types of base64 content:
        1. Direct base64_string in the scenario (from FileStore.to_dict())
        2. FileStore objects containing base64 content
        3. Dictionary values containing base64_string fields
        
        Args:
            inplace: If True, modify the current scenario. If False, return a new one.
            
        Returns:
            The modified scenario (either the original or a new instance).
            
        Examples:
            >>> from edsl.scenarios import Scenario, FileStore
            >>> s = Scenario({"base64_string": "SGVsbG8gV29ybGQ=", "name": "test"})
            >>> offloader = ScenarioOffloader(s)
            >>> offloaded = offloader.offload()
            >>> offloaded["base64_string"]
            'offloaded'
            >>> offloaded["name"]
            'test'
        """
        # Import here to avoid circular imports
        try:
            from .scenario import Scenario
        except ImportError:
            # For doctest execution
            from edsl.scenarios.scenario import Scenario
            
        try:
            from edsl.scenarios import FileStore
        except ImportError:
            # For doctest execution  
            from edsl.scenarios.file_store import FileStore

        target = self.scenario if inplace else Scenario()

        # Process all key-value pairs in the scenario
        for key, value in self.scenario.items():
            if key == "base64_string" and isinstance(value, str):
                # Handle direct base64_string content
                target[key] = "offloaded"
            else:
                # Handle other values (FileStore, dicts with base64, etc.)
                modified_value = self._process_value(value, FileStore)
                target[key] = modified_value

        return target
    

    
    def _process_value(self, value: Any, FileStore: type) -> Any:
        """
        Process a single value for base64 offloading.
        
        Args:
            value: The value to process.
            FileStore: The FileStore class for type checking.
            
        Returns:
            The processed value with base64 content offloaded.
        """
        if isinstance(value, FileStore):
            return self._offload_filestore_value(value, FileStore)
        elif isinstance(value, dict) and "base64_string" in value:
            return self._offload_dict_value(value)
        else:
            return value
    
    def _offload_filestore_value(self, file_store: Any, FileStore: type) -> Any:
        """
        Offload base64 content from a FileStore object.
        
        Args:
            file_store: The FileStore object to process.
            FileStore: The FileStore class for reconstruction.
            
        Returns:
            A new FileStore object with base64 content offloaded.
        """
        file_store_dict = file_store.to_dict()
        if "base64_string" in file_store_dict:
            file_store_dict["base64_string"] = "offloaded"
        return FileStore.from_dict(file_store_dict)
    
    def _offload_dict_value(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """
        Offload base64 content from a dictionary value.
        
        Args:
            value: The dictionary to process.
            
        Returns:
            A copy of the dictionary with base64_string replaced.
        """
        value_copy = value.copy()
        value_copy["base64_string"] = "offloaded"
        return value_copy
    
    def requires_offloading(self) -> bool:
        """
        Check if the scenario contains any base64 content that can be offloaded.
        
        Returns:
            True if the scenario contains base64 content, False otherwise.
            
        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"base64_string": "SGVsbG8=", "name": "test"})
            >>> ScenarioOffloader(s).requires_offloading()
            True
            >>> s2 = Scenario({"name": "test", "value": 42})
            >>> ScenarioOffloader(s2).requires_offloading()
            False
        """
        # Check for direct base64_string (but not if already offloaded)
        if ("base64_string" in self.scenario and 
            isinstance(self.scenario.get("base64_string"), str) and
            self.scenario.get("base64_string") != "offloaded"):
            return True
            
        # Check for base64 content in values
        try:
            from edsl.scenarios import FileStore
        except ImportError:
            from edsl.scenarios.file_store import FileStore
            
        for key, value in self.scenario.items():
            if isinstance(value, FileStore):
                file_store_dict = value.to_dict()
                if "base64_string" in file_store_dict and file_store_dict["base64_string"] != "offloaded":
                    return True
            elif isinstance(value, dict) and "base64_string" in value and value["base64_string"] != "offloaded":
                return True
                
        return False
    
    def get_offload_summary(self) -> Dict[str, Any]:
        """
        Get a summary of base64 content that can be offloaded.
        
        Returns:
            A dictionary containing information about offloadable content.
            
        Examples:
            >>> from edsl.scenarios import Scenario
            >>> s = Scenario({"base64_string": "SGVsbG8=", "name": "test"})
            >>> summary = ScenarioOffloader(s).get_offload_summary()
            >>> summary["has_offloadable_content"]
            True
            >>> summary["total_items"]
            1
        """
        summary = {
            "has_offloadable_content": False,
            "total_items": 0,
            "direct_base64": False,
            "filestore_items": 0,
            "dict_items": 0,
            "offloadable_keys": []
        }
        
        # Check for direct base64_string (but not if already offloaded)
        if ("base64_string" in self.scenario and 
            isinstance(self.scenario.get("base64_string"), str) and
            self.scenario.get("base64_string") != "offloaded"):
            summary["has_offloadable_content"] = True
            summary["direct_base64"] = True
            summary["total_items"] += 1
            summary["offloadable_keys"].append("base64_string")
            
        # Check for base64 content in values
        try:
            from edsl.scenarios import FileStore
        except ImportError:
            from edsl.scenarios.file_store import FileStore
            
        for key, value in self.scenario.items():
            if isinstance(value, FileStore):
                file_store_dict = value.to_dict()
                if "base64_string" in file_store_dict and file_store_dict["base64_string"] != "offloaded":
                    summary["has_offloadable_content"] = True
                    summary["filestore_items"] += 1
                    summary["total_items"] += 1
                    summary["offloadable_keys"].append(key)
            elif isinstance(value, dict) and "base64_string" in value and value["base64_string"] != "offloaded":
                summary["has_offloadable_content"] = True
                summary["dict_items"] += 1
                summary["total_items"] += 1
                summary["offloadable_keys"].append(key)
                
        return summary


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS) 