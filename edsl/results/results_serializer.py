"""Serialization functionality for Results objects.

This module provides the ResultsSerializer class which handles serialization and
deserialization operations for Results objects, including dictionary conversion
and object reconstruction.
"""

from typing import TYPE_CHECKING, Any, Optional, Dict
from ..utilities import remove_edsl_version

if TYPE_CHECKING:
    from .results import Results

from .exceptions import ResultsDeserializationError


class ResultsSerializer:
    """Handles serialization and deserialization operations for Results objects.
    
    This class encapsulates all the serialization logic for Results objects,
    including conversion to and from dictionary representations for storage
    and transmission.
    
    Attributes:
        results: The Results object to serialize
    """
    
    def __init__(self, results: "Results"):
        """Initialize the serializer with a Results object.
        
        Args:
            results: The Results object to serialize
        """
        self.results = results
    
    def to_dict(
        self,
        sort: bool = False,
        add_edsl_version: bool = True,
        include_cache: bool = True,
        include_task_history: bool = False,
        include_cache_info: bool = True,
        offload_scenarios: bool = True,
    ) -> Dict[str, Any]:
        """Convert the Results object to a dictionary representation.
        
        Args:
            sort: Whether to sort the results data by hash before serialization
            add_edsl_version: Whether to include the EDSL version in the output
            include_cache: Whether to include cache data in the output
            include_task_history: Whether to include task history in the output
            include_cache_info: Whether to include cache information in result data
            offload_scenarios: Whether to optimize scenarios before serialization
            
        Returns:
            Dict[str, Any]: Dictionary representation of the Results object
        """
        from ..caching import Cache

        if offload_scenarios:
            self.results.optimzie_scenarios()
        if sort:
            data = sorted([result for result in self.results.data], key=lambda x: hash(x))
        else:
            data = [result for result in self.results.data]

        d = {
            "data": [
                result.to_dict(
                    add_edsl_version=add_edsl_version,
                    include_cache_info=include_cache_info,
                )
                for result in data
            ],
            "survey": self.results.survey.to_dict(add_edsl_version=add_edsl_version),
            "created_columns": self.results.created_columns,
        }
        if include_cache:
            d.update(
                {
                    "cache": (
                        Cache()
                        if not hasattr(self.results, "cache")
                        else self.results.cache.to_dict(add_edsl_version=add_edsl_version)
                    )
                }
            )
        if self.results.name is not None:
            d["name"] = self.results.name

        if self.results.task_history.has_unfixed_exceptions or include_task_history:
            d.update({"task_history": self.results.task_history.to_dict(offload_content=True)})

        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Results"

        return d
    
    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: Dict[str, Any]) -> "Results":
        """Convert a dictionary to a Results object.

        Args:
            data: A dictionary representation of a Results object.

        Returns:
            Results: A new Results object created from the dictionary data

        Raises:
            ResultsDeserializationError: If there's an error during deserialization

        Examples:
            >>> # This would typically be used internally
            >>> # r = Results.example()
            >>> # d = ResultsSerializer(r).to_dict()
            >>> # r2 = ResultsSerializer.from_dict(d)
            >>> # r == r2
        """
        # Import here to avoid circular imports
        from .results import Results
        from ..surveys import Survey
        from ..caching import Cache
        from .result import Result
        from ..tasks import TaskHistory

        survey = Survey.from_dict(data["survey"])
        # Convert dictionaries to Result objects
        results_data = [Result.from_dict(r) for r in data["data"]]
        created_columns = data.get("created_columns", None)
        cache = Cache.from_dict(data.get("cache")) if "cache" in data else Cache()
        task_history = (
            TaskHistory.from_dict(data.get("task_history"))
            if "task_history" in data
            else TaskHistory(interviews=[])
        )
        name = data.get("name", None)

        # Create a Results object with original order preserved
        # using the empty data list initially
        params = {
            "survey": survey,
            "data": [],  # Start with empty data
            "created_columns": created_columns,
            "cache": cache,
            "task_history": task_history,
            "name": name
        }

        try:
            results = Results(**params)
            # Add each result individually to respect order attributes
            for result in results_data:
                results.append(result)
        except Exception as e:
            raise ResultsDeserializationError(f"Error in Results.from_dict: {e}")
        return results 