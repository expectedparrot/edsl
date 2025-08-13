"""Utility classes and decorators for Results functionality.

This module contains utility classes and decorators that support the Results module,
including database handling, method decorators for remote data fetching, and 
helper classes for managing not-ready states.
"""

import json
from typing import Any, Callable, TYPE_CHECKING
from functools import wraps

if TYPE_CHECKING:
    pass

from ...db_list.sqlite_list import SQLiteList


class ResultsSQLList(SQLiteList):
    """SQLite-backed list implementation for Results data storage.

    This class extends SQLiteList to provide specific serialization and
    deserialization methods for Result objects, enabling efficient storage
    and retrieval of large Results collections.
    """

    def serialize(self, obj):
        """Serialize a Result object to JSON string.

        Args:
            obj: The object to serialize, typically a Result object

        Returns:
            str: JSON string representation of the object
        """
        return json.dumps(obj.to_dict()) if hasattr(obj, "to_dict") else json.dumps(obj)

    def deserialize(self, data):
        """Deserialize JSON string back to a Result object.

        Args:
            data: JSON string to deserialize

        Returns:
            Result: Deserialized Result object or raw data if deserialization fails
        """
        from ..result import Result

        return (
            Result.from_dict(json.loads(data))
            if hasattr(Result, "from_dict")
            else json.loads(data)
        )


def ensure_fetched(method: Callable) -> Callable:
    """A decorator that checks if remote data is loaded, and if not, attempts to fetch it.

    This decorator is used to ensure that methods have access to remote data
    before execution. If the data hasn't been fetched yet, it will attempt
    to fetch it using the object's fetch_remote method.

    Args:
        method: The method to decorate.

    Returns:
        Callable: The wrapped method that will ensure data is fetched before execution.
    """

    def wrapper(self, *args, **kwargs):
        if not self._fetched:
            # If not fetched, try fetching now.
            # (If you know you have job info stored in self.job_info)
            self.fetch_remote(self.job_info)
        return method(self, *args, **kwargs)

    return wrapper


def ensure_ready(method: Callable) -> Callable:
    """Decorator for Results methods to handle not-ready state.

    If the Results object is not ready, for most methods we return a NotReadyObject.
    However, for __repr__ (and other methods that need to return a string), we return
    the string representation of NotReadyObject.

    This decorator handles the common pattern of checking if a Results object is
    ready for use and attempting to fetch remote data if needed.

    Args:
        method: The method to decorate.

    Returns:
        Callable: The wrapped method that will handle not-ready Results objects appropriately.

    Raises:
        Exception: Any exception from fetch_remote will be caught and printed.
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if self.completed:
            return method(self, *args, **kwargs)
        # Attempt to fetch remote data
        try:
            if hasattr(self, "job_info"):
                self.fetch_remote(self.job_info)
        except Exception as e:
            print(f"Error during fetch_remote in {method.__name__}: {e}")
        if not self.completed:
            not_ready = NotReadyObject(name=method.__name__, job_info=self.job_info)
            # For __repr__, ensure we return a string
            if method.__name__ == "__repr__" or method.__name__ == "__str__":
                return not_ready.__repr__()
            return not_ready
        return method(self, *args, **kwargs)

    return wrapper


class NotReadyObject:
    """A placeholder object that indicates results are not ready yet.

    This class returns itself for all attribute accesses and method calls,
    displaying a message about the job's running status when represented as a string.

    This is used by the ensure_ready decorator to provide a consistent interface
    for Results objects that are still waiting for remote data to be available.

    Attributes:
        name: The name of the method that was originally called.
        job_info: Information about the running job.
    """

    def __init__(self, name: str, job_info: Any):
        """Initialize a NotReadyObject.

        Args:
            name: The name of the method that was attempted to be called.
            job_info: Information about the running job.
        """
        self.name = name
        self.job_info = job_info
        # print(f"Not ready to call {name}")

    def __repr__(self):
        """Generate a string representation showing the job is still running.

        Returns:
            str: A message indicating the job is still running, along with job details.
        """
        message = """Results not ready - job still running on server."""
        for key, value in self.job_info.creation_data.items():
            message += f"\n{key}: {value}"
        return message

    def __getattr__(self, _):
        """Return self for any attribute access.

        Args:
            _: The attribute name (ignored).

        Returns:
            NotReadyObject: Returns self for chaining.
        """
        return self

    def __call__(self, *args, **kwargs):
        """Return self when called as a function.

        Args:
            *args: Positional arguments (ignored).
            **kwargs: Keyword arguments (ignored).

        Returns:
            NotReadyObject: Returns self for chaining.
        """
        return self
