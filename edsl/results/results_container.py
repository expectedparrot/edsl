"""ResultsContainer module for handling list-like container behavior of Results objects.

This module contains the ResultsContainer class which provides all the list-like
container operations for Results objects, including indexing, iteration, modification,
and combination operations.
"""

from typing import TYPE_CHECKING, Union
from bisect import bisect_left

if TYPE_CHECKING:
    from ..results import Results, Result

from .exceptions import ResultsError


class ResultsContainer:
    """Handles all list-like container behavior for Results objects.
    
    This class provides the core container operations including indexing,
    slicing, length, insertion, extension, and combination of Results objects.
    """

    def __init__(self, results: "Results"):
        """Initialize the ResultsContainer with a reference to the Results object.
        
        Args:
            results: The Results object to provide container behavior for
        """
        self._results = results

    def __getitem__(self, i):
        """Get item(s) from the Results container.
        
        Args:
            i: Index (int), slice, or string key for accessing data
            
        Returns:
            Individual Result, new Results object, or dictionary value
            
        Raises:
            ResultsError: If invalid argument type is provided
        """
        if isinstance(i, int):
            return self._results.data[i]
        if isinstance(i, slice):
            return self._results.__class__(survey=self._results.survey, data=self._results.data[i])
        if isinstance(i, str):
            return self._results.to_dict()[i]
        raise ResultsError("Invalid argument type for indexing Results object")

    def __setitem__(self, i, item):
        """Set item in the Results container.
        
        Args:
            i: Index for setting the item
            item: Item to set at the given index
        """
        self._results.data[i] = item
        self._results._cache_manager.invalidate_cache()

    def __delitem__(self, i):
        """Delete item from the Results container.
        
        Args:
            i: Index of item to delete
        """
        del self._results.data[i]
        self._results._cache_manager.invalidate_cache()

    def __len__(self):
        """Return the length of the Results container.
        
        Returns:
            int: Number of Result objects in the container
        """
        return len(self._results.data)

    def insert(self, index, item):
        """Insert item at the specified index.
        
        Args:
            index: Index at which to insert the item
            item: Item to insert
        """
        self._results.data.insert(index, item)
        self._results._cache_manager.invalidate_cache()

    def extend(self, other):
        """Extend the Results list with items from another iterable.
        
        Args:
            other: Iterable of items to extend with
        """
        self._results.data.extend(other)
        self._results._cache_manager.invalidate_cache()

    def extend_sorted(self, other):
        """Extend the Results list with items from another iterable.

        This method preserves ordering based on 'order' attribute if present,
        otherwise falls back to 'iteration' attribute.
        
        Args:
            other: Iterable of items to extend with
        """
        # Collect all items (existing and new)
        all_items = list(self._results.data)
        all_items.extend(other)

        # Sort combined list by order attribute if available, otherwise by iteration
        def get_sort_key(item):
            if hasattr(item, "order"):
                return (0, item.order)  # Order attribute takes precedence
            return (1, item.data["iteration"])  # Iteration is secondary

        all_items.sort(key=get_sort_key)

        # Clear and refill with sorted items
        self._results.data.clear()
        self._results.data.extend(all_items)

    def insert_sorted(self, item: "Result") -> None:
        """Insert a Result object into the Results list while maintaining sort order.

        Uses the 'order' attribute if present, otherwise falls back to 'iteration' attribute.
        Utilizes bisect for efficient insertion point finding.

        Args:
            item: A Result object to insert

        Examples:
            >>> r = Results.example()
            >>> new_result = r[0].copy()
            >>> new_result.order = 1.5  # Insert between items
            >>> r.insert_sorted(new_result)
        """

        def get_sort_key(result):
            if hasattr(result, "order"):
                return (0, result.order)  # Order attribute takes precedence
            return (1, result.data["iteration"])  # Iteration is secondary

        # Get the sort key for the new item
        item_key = get_sort_key(item)

        # Get list of sort keys for existing items
        keys = [get_sort_key(x) for x in self._results.data]

        # Find insertion point
        index = bisect_left(keys, item_key)

        # Insert at the found position
        self._results.data.insert(index, item)

    def __add__(self, other: "Results") -> "Results":
        """Add two Results objects together.

        Combines two Results objects into a new one. Both objects must have the same
        survey and created columns.

        Args:
            other: A Results object to add to this one.

        Returns:
            A new Results object containing data from both objects.

        Raises:
            ResultsError: If the surveys or created columns of the two objects don't match.

        Examples:
            >>> from edsl.results import Results
            >>> r1 = Results.example()
            >>> r2 = Results.example()
            >>> # Combine two Results objects
            >>> r3 = r1 + r2
            >>> len(r3) == len(r1) + len(r2)
            True

            >>> # Attempting to add incompatible Results
            >>> from unittest.mock import Mock
            >>> r4 = Results(survey=Mock())  # Different survey
            >>> try:
            ...     r1 + r4
            ... except ResultsError:
            ...     True
            True
        """
        if self._results.survey != other.survey:
            raise ResultsError(
                "The surveys are not the same so the the results cannot be added together."
            )
        if self._results.created_columns != other.created_columns:
            raise ResultsError(
                "The created columns are not the same so they cannot be added together."
            )

        # Create a new ResultsSQLList with the combined data
        # combined_data = ResultsSQLList()
        combined_data = self._results._data_class()
        combined_data.extend(self._results.data)
        combined_data.extend(other.data)

        # Use the same class as the current Results instance to avoid circular imports
        return self._results.__class__(
            survey=self._results.survey,
            data=combined_data,
            created_columns=self._results.created_columns,
        ) 