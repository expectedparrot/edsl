"""
SQLite-backed list implementation with memory usage limits.

This module provides a list-like class that offloads data to SQLite when memory
usage exceeds a specified threshold. It implements the standard list interface,
making it a drop-in replacement for Python's built-in list.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from typing import Any, Callable, Generator, Iterator, List, Optional, TypeVar, Union, overload

from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import Session, sessionmaker

from ..base.base_class import Base as BaseClass
from .exceptions import SQLListError, SQLListIndexError, SQLListValueError
from .orm import Base, ListItem, ListMetadata

T = TypeVar('T')


class SQLList(BaseClass):
    """
    A list-like class that uses SQLite storage when memory usage exceeds a specified threshold.
    
    This class provides a complete implementation of Python's list interface, automatically
    offloading data to SQLite when the in-memory size of the list exceeds the configured
    threshold. It transparently handles the transition between memory and disk storage,
    making it a seamless replacement for standard lists when working with large datasets.
    
    Attributes:
        memory_threshold (int): Size threshold in bytes before offloading to SQLite
        memory_list (list): In-memory portion of the list
        db_path (str): Path to SQLite database file
        engine: SQLAlchemy engine for database access
        Session: SQLAlchemy sessionmaker for creating database sessions
        is_memory_only (bool): Flag indicating if all data is in memory
        
    Example:
        >>> lst = SQLList(memory_threshold=10000)  # 10KB threshold
        >>> lst.append("item 1")
        >>> lst.extend(["item 2", "item 3"])
        >>> len(lst)
        3
        >>> lst[1] = "modified item 2"
        >>> lst[1]
        'modified item 2'
    """

    def __init__(
        self, 
        iterable: Optional[List[T]] = None, 
        memory_threshold: Optional[int] = None,
        db_path: Optional[str] = None
    ):
        """
        Initialize a new SQLList instance.
        
        Args:
            iterable: Optional iterable to initialize the list with
            memory_threshold: Size in bytes before offloading to SQLite
                (default: 10MB or CONFIG.get("EDSL_SQLLIST_MEMORY_THRESHOLD"))
            db_path: Path to SQLite database file
                (default: temporary file or CONFIG.get("EDSL_SQLLIST_DB_PATH"))
                
        Raises:
            SQLListError: If there is an error initializing the database
        """
        super().__init__()
        
        # Initialize parameters with defaults
        # Check if EDSL_SQLLIST_MEMORY_THRESHOLD is defined in environment variables
        try:
            env_threshold = os.environ.get("EDSL_SQLLIST_MEMORY_THRESHOLD")
            if env_threshold:
                default_memory_threshold = int(env_threshold)
            else:
                default_memory_threshold = None
        except Exception:
            default_memory_threshold = None
            
        self.memory_threshold = memory_threshold or default_memory_threshold or 10 * 1024 * 1024  # 10MB default
        
        # Initialize in-memory list
        self.memory_list = list(iterable) if iterable else []
        self.is_memory_only = True
        
        # Initialize database connection
        self._initialize_db(db_path)
        
        # Check if initial data exceeds memory threshold and offload if needed
        if sys.getsizeof(self.memory_list) > self.memory_threshold:
            self._offload_to_db()
    
    def _initialize_db(self, db_path: Optional[str] = None):
        """
        Initialize SQLite database connection.
        
        Args:
            db_path: Path to SQLite database file
            
        Raises:
            SQLListError: If there is an error initializing the database
        """
        try:
            if db_path:
                self.db_path = db_path
            else:
                # Use environment variable path if set, otherwise create a temporary file
                try:
                    env_path = os.environ.get("EDSL_SQLLIST_DB_PATH")
                    if env_path and not env_path.startswith("sqlite:///"):
                        config_path = f"sqlite:///{env_path}"
                    else:
                        config_path = env_path
                except Exception:
                    config_path = None
                
                if config_path:
                    self.db_path = config_path
                else:
                    # Create a unique temporary path
                    temp_dir = tempfile.gettempdir()
                    unique_id = str(uuid.uuid4())
                    self.db_path = os.path.join(temp_dir, f"sqllist_{unique_id}.db")
            
            # Format path for SQLAlchemy
            if not self.db_path.startswith("sqlite:///"):
                self.db_path = f"sqlite:///{self.db_path}"
                
            # Create engine and initialize tables
            self.engine = create_engine(self.db_path, echo=False, future=True)
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
            
            # Initialize list metadata
            with self.Session() as session:
                metadata = session.query(ListMetadata).filter_by(key="length").first()
                if not metadata:
                    session.add(ListMetadata(key="length", value="0"))
                    session.commit()
                
        except Exception as e:
            raise SQLListError(f"Database initialization error: {e}") from e
    
    def _check_memory_threshold(self):
        """
        Check if memory list exceeds threshold and offload to database if needed.
        """
        if self.is_memory_only and sys.getsizeof(self.memory_list) > self.memory_threshold:
            self._offload_to_db()
    
    def _offload_to_db(self):
        """
        Offload data from memory list to SQLite database.
        
        This method moves all data from the in-memory list to the SQLite database
        when the memory threshold is exceeded.
        """
        with self.Session() as session:
            # Clear existing data
            session.query(ListItem).delete()
            
            # Add all items to database
            for i, item in enumerate(self.memory_list):
                # Serialize the item appropriately
                try:
                    serialized_value = json.dumps(item)
                except TypeError:
                    # Handle Scenario and other EDSL objects
                    if hasattr(item, 'to_dict'):
                        # Use to_dict method if available
                        serialized_value = json.dumps(item.to_dict(add_edsl_version=True))
                    # Handle objects that can be converted to dict but don't have to_dict
                    elif hasattr(item, '__dict__'):
                        # Use __dict__ as a fallback
                        serialized_value = json.dumps(item.__dict__)
                    else:
                        # Fallback for other types
                        raise SQLListValueError(f"Item of type {type(item).__name__} is not JSON serializable and has no to_dict method")
                
                session.add(ListItem(index=i, value=serialized_value))
            
            # Update metadata
            length_meta = session.query(ListMetadata).filter_by(key="length").first()
            if length_meta:
                length_meta.value = str(len(self.memory_list))
            else:
                session.add(ListMetadata(key="length", value=str(len(self.memory_list))))
                
            session.commit()
        
        # Clear memory list and update state
        self.memory_list = []
        self.is_memory_only = False
    
    def _get_db_length(self) -> int:
        """
        Get the length of the list from the database.
        
        Returns:
            int: Length of the list
        """
        with self.Session() as session:
            length_meta = session.query(ListMetadata).filter_by(key="length").first()
            return int(length_meta.value) if length_meta else 0
    
    def _get_item(self, index: int) -> Any:
        """
        Get an item from either memory or database.
        
        Args:
            index: The index of the item to retrieve
            
        Returns:
            The item at the specified index
            
        Raises:
            SQLListIndexError: If the index is out of range
        """
        if self.is_memory_only:
            try:
                return self.memory_list[index]
            except IndexError:
                raise SQLListIndexError(f"List index {index} out of range") from None
        else:
            # Normalize negative indices
            if index < 0:
                index = self._get_db_length() + index
                
            if index < 0:  # Still negative after normalization
                raise SQLListIndexError(f"List index {index} out of range")
                
            with self.Session() as session:
                item = session.query(ListItem).filter_by(index=index).first()
                if item:
                    # Load the serialized data
                    data = json.loads(item.value)
                    
                    # Check if this is a serialized object with edsl_class_name
                    if isinstance(data, dict) and 'edsl_class_name' in data:
                        # Try to reconstruct the object
                        from importlib import import_module
                        try:
                            # For Result objects and others from the EDSL package
                            if data['edsl_class_name'] == 'Result':
                                from ..results import Result
                                return Result.from_dict(data)
                            elif data['edsl_class_name'] == 'Scenario':
                                from ..scenarios import Scenario
                                return Scenario.from_dict(data)
                            else:
                                # Generic approach for other EDSL classes
                                class_name = data['edsl_class_name']
                                # Try to import from appropriate module
                                for module_path in ['edsl', 'edsl.results', 'edsl.agents', 'edsl.models', 'edsl.scenarios']:
                                    try:
                                        module = import_module(module_path)
                                        if hasattr(module, class_name):
                                            cls = getattr(module, class_name)
                                            if hasattr(cls, 'from_dict'):
                                                return cls.from_dict(data)
                                    except (ImportError, AttributeError):
                                        pass
                        except Exception:
                            # If reconstruction fails, fall back to the dictionary
                            pass
                    
                    # Return the data as-is if not reconstructed
                    return data
                else:
                    raise SQLListIndexError(f"List index {index} out of range")
    
    def _set_item(self, index: int, value: Any):
        """
        Set an item value at the specified index.
        
        Args:
            index: The index to set
            value: The value to set
            
        Raises:
            SQLListIndexError: If the index is out of range
        """
        if self.is_memory_only:
            try:
                self.memory_list[index] = value
                self._check_memory_threshold()
            except IndexError:
                raise SQLListIndexError(f"List index {index} out of range") from None
        else:
            # Normalize negative indices
            length = self._get_db_length()
            if index < 0:
                index = length + index
                
            if index < 0 or index >= length:
                raise SQLListIndexError(f"List index {index} out of range")
                
            with self.Session() as session:
                item = session.query(ListItem).filter_by(index=index).first()
                if item:
                    # Serialize the value if it's not directly JSON serializable
                    try:
                        serialized_value = json.dumps(value)
                    except TypeError:
                        # Handle Scenario and other EDSL objects
                        if hasattr(value, 'to_dict'):
                            # Use to_dict method if available
                            serialized_value = json.dumps(value.to_dict(add_edsl_version=True))
                        # Handle objects that can be converted to dict but don't have to_dict
                        elif hasattr(value, '__dict__'):
                            # Use __dict__ as a fallback
                            serialized_value = json.dumps(value.__dict__)
                        else:
                            # Fallback for other types
                            raise SQLListValueError(f"Value of type {type(value).__name__} is not JSON serializable and has no to_dict method")
                    
                    item.value = serialized_value
                    session.commit()
                else:
                    raise SQLListIndexError(f"List index {index} out of range")
    
    def _del_item(self, index: int):
        """
        Delete an item at the specified index.
        
        Args:
            index: The index to delete
            
        Raises:
            SQLListIndexError: If the index is out of range
        """
        if self.is_memory_only:
            try:
                del self.memory_list[index]
            except IndexError:
                raise SQLListIndexError(f"List index {index} out of range") from None
        else:
            # Normalize negative indices
            length = self._get_db_length()
            if index < 0:
                index = length + index
                
            if index < 0 or index >= length:
                raise SQLListIndexError(f"List index {index} out of range")
                
            with self.Session() as session:
                # Delete the item
                session.query(ListItem).filter_by(index=index).delete()
                
                # Shift all subsequent items down by one
                session.execute(
                    text(f"UPDATE list_items SET index = index - 1 WHERE index > {index}")
                )
                
                # Update length metadata
                length_meta = session.query(ListMetadata).filter_by(key="length").first()
                if length_meta:
                    length_meta.value = str(int(length_meta.value) - 1)
                    
                session.commit()
    
    def append(self, item: T) -> None:
        """
        Add an item to the end of the list.
        
        Args:
            item: The item to append
        """
        if self.is_memory_only:
            self.memory_list.append(item)
            self._check_memory_threshold()
        else:
            with self.Session() as session:
                # Get current length
                length_meta = session.query(ListMetadata).filter_by(key="length").first()
                current_length = int(length_meta.value) if length_meta else 0
                
                # Serialize the item if it's not directly JSON serializable
                try:
                    serialized_value = json.dumps(item)
                except TypeError:
                    # Handle Scenario and other EDSL objects
                    if hasattr(item, 'to_dict'):
                        # Use to_dict method if available
                        serialized_value = json.dumps(item.to_dict(add_edsl_version=True))
                    # Handle objects that can be converted to dict but don't have to_dict
                    elif hasattr(item, '__dict__'):
                        # Use __dict__ as a fallback
                        serialized_value = json.dumps(item.__dict__)
                    else:
                        # Fallback for other types
                        raise SQLListValueError(f"Item of type {type(item).__name__} is not JSON serializable and has no to_dict method")
                
                # Add the item at the end
                session.add(ListItem(index=current_length, value=serialized_value))
                
                # Update length
                if length_meta:
                    length_meta.value = str(current_length + 1)
                else:
                    session.add(ListMetadata(key="length", value=str(current_length + 1)))
                    
                session.commit()
    
    def extend(self, iterable: List[T]) -> None:
        """
        Extend the list by appending items from the iterable.
        
        Args:
            iterable: The iterable containing items to append
        """
        items_list = list(iterable)  # Convert to list to handle all iterables
        
        if self.is_memory_only:
            self.memory_list.extend(items_list)
            self._check_memory_threshold()
        else:
            with self.Session() as session:
                # Get current length
                length_meta = session.query(ListMetadata).filter_by(key="length").first()
                current_length = int(length_meta.value) if length_meta else 0
                
                # Add all items
                for i, item in enumerate(items_list):
                    # Serialize the item if it's not directly JSON serializable
                    try:
                        serialized_value = json.dumps(item)
                    except TypeError:
                        # Handle Scenario and other EDSL objects
                        if hasattr(item, 'to_dict'):
                            # Use to_dict method if available
                            serialized_value = json.dumps(item.to_dict(add_edsl_version=True))
                        # Handle objects that can be converted to dict but don't have to_dict
                        elif hasattr(item, '__dict__'):
                            # Use __dict__ as a fallback
                            serialized_value = json.dumps(item.__dict__)
                        else:
                            # Fallback for other types
                            raise SQLListValueError(f"Item of type {type(item).__name__} is not JSON serializable and has no to_dict method")
                    
                    session.add(ListItem(index=current_length + i, value=serialized_value))
                
                # Update length
                new_length = current_length + len(items_list)
                if length_meta:
                    length_meta.value = str(new_length)
                else:
                    session.add(ListMetadata(key="length", value=str(new_length)))
                    
                session.commit()
    
    def insert(self, index: int, item: T) -> None:
        """
        Insert an item at the specified position.
        
        Args:
            index: The index where the item should be inserted
            item: The item to insert
            
        Raises:
            SQLListIndexError: If the index is out of range
        """
        if self.is_memory_only:
            try:
                self.memory_list.insert(index, item)
                self._check_memory_threshold()
            except IndexError:
                raise SQLListIndexError(f"List index {index} out of range") from None
        else:
            # Normalize negative indices
            length = self._get_db_length()
            if index < 0:
                index = length + index
                
            # For insert, we allow index == length (append to the end)
            if index < 0 or index > length:
                raise SQLListIndexError(f"List index {index} out of range")
                
            with self.Session() as session:
                # Shift items to make room
                session.execute(
                    text(f"UPDATE list_items SET index = index + 1 WHERE index >= {index}")
                )
                
                # Serialize the item if it's not directly JSON serializable
                try:
                    serialized_value = json.dumps(item)
                except TypeError:
                    if hasattr(item, 'to_dict'):
                        # Use to_dict method if available
                        serialized_value = json.dumps(item.to_dict(add_edsl_version=True))
                    else:
                        # Fallback for other types
                        raise SQLListValueError(f"Item of type {type(item).__name__} is not JSON serializable and has no to_dict method")
                
                # Insert the new item
                session.add(ListItem(index=index, value=serialized_value))
                
                # Update length
                length_meta = session.query(ListMetadata).filter_by(key="length").first()
                if length_meta:
                    length_meta.value = str(int(length_meta.value) + 1)
                    
                session.commit()
    
    def pop(self, index: int = -1) -> T:
        """
        Remove and return item at index (default last).
        
        Args:
            index: The index of the item to remove (default: -1, the last item)
            
        Returns:
            The item at the specified index
            
        Raises:
            SQLListIndexError: If the list is empty or index is out of range
        """
        # Get the item first to handle possible index errors
        item = self[index]
        
        # Then delete it
        self._del_item(index)
        
        return item
    
    def remove(self, value: T) -> None:
        """
        Remove first occurrence of value.
        
        Args:
            value: The value to remove
            
        Raises:
            SQLListValueError: If the value is not present
        """
        if self.is_memory_only:
            try:
                self.memory_list.remove(value)
            except ValueError:
                raise SQLListValueError(f"Value {value} not in list") from None
        else:
            found = False
            index_to_remove = -1
            
            with self.Session() as session:
                items = session.query(ListItem).order_by(ListItem.index).all()
                
                for item in items:
                    if json.loads(item.value) == value:
                        found = True
                        index_to_remove = item.index
                        break
            
            if found:
                self._del_item(index_to_remove)
            else:
                raise SQLListValueError(f"Value {value} not in list")
    
    def clear(self) -> None:
        """
        Remove all items from the list.
        """
        if self.is_memory_only:
            self.memory_list.clear()
        else:
            with self.Session() as session:
                # Delete all items
                session.query(ListItem).delete()
                
                # Reset length to 0
                length_meta = session.query(ListMetadata).filter_by(key="length").first()
                if length_meta:
                    length_meta.value = "0"
                else:
                    session.add(ListMetadata(key="length", value="0"))
                    
                session.commit()
                
            # Return to memory-only mode since the list is now empty
            self.is_memory_only = True
            self.memory_list = []
    
    def index(self, value: T, start: int = 0, end: Optional[int] = None) -> int:
        """
        Return first index of value.
        
        Args:
            value: The value to find
            start: The starting index to search from
            end: The ending index to search to
            
        Returns:
            The index of the first occurrence of the value
            
        Raises:
            SQLListValueError: If the value is not present
        """
        if self.is_memory_only:
            try:
                if end is None:
                    return self.memory_list.index(value, start)
                else:
                    return self.memory_list.index(value, start, end)
            except ValueError:
                raise SQLListValueError(f"Value {value} not in list") from None
        else:
            # Normalize indices
            length = self._get_db_length()
            
            if start < 0:
                start = length + start
                if start < 0:
                    start = 0
                    
            if end is None:
                end = length
            elif end < 0:
                end = length + end
                
            # Clamp indices
            start = max(0, start)
            end = min(length, end)
            
            value_json = json.dumps(value)
            
            with self.Session() as session:
                items = session.query(ListItem).filter(
                    ListItem.index >= start, 
                    ListItem.index < end
                ).order_by(ListItem.index).all()
                
                for item in items:
                    if item.value == value_json or json.loads(item.value) == value:
                        return item.index
            
            raise SQLListValueError(f"Value {value} not in list")
    
    def count(self, value: T) -> int:
        """
        Return number of occurrences of value.
        
        Args:
            value: The value to count
            
        Returns:
            The number of occurrences
        """
        if self.is_memory_only:
            return self.memory_list.count(value)
        else:
            count = 0
            value_json = json.dumps(value)
            
            with self.Session() as session:
                items = session.query(ListItem).all()
                
                for item in items:
                    if item.value == value_json or json.loads(item.value) == value:
                        count += 1
            
            return count
    
    def reverse(self) -> None:
        """
        Reverse the items of the list in place.
        """
        if self.is_memory_only:
            self.memory_list.reverse()
        else:
            length = self._get_db_length()
            
            with self.Session() as session:
                # We'll use a temporary table for the swap
                session.execute(text("CREATE TEMPORARY TABLE temp_items AS SELECT * FROM list_items"))
                
                # Update indices in the main table
                for i in range(length):
                    session.execute(
                        text(f"UPDATE list_items SET index = {length - 1 - i} "
                        f"WHERE index = (SELECT index FROM temp_items WHERE index = {i})")
                    )
                
                # Drop the temporary table
                session.execute(text("DROP TABLE temp_items"))
                session.commit()
    
    def sort(self, *, key: Optional[Callable[[T], Any]] = None, reverse: bool = False) -> None:
        """
        Sort the items of the list in place.
        
        Args:
            key: A function that extracts a comparison key from each element
            reverse: If True, sort in descending order
        """
        # For sort, we need to bring everything into memory
        items = list(self)
        
        # Sort the items
        items.sort(key=key, reverse=reverse)
        
        # Clear and replace with sorted items
        self.clear()
        
        # Add the sorted items back
        if items:
            self.extend(items)
    
    def copy(self) -> SQLList:
        """
        Return a shallow copy of the list.
        
        Returns:
            A new SQLList with the same items
        """
        return SQLList(list(self), memory_threshold=self.memory_threshold)
    
    def __getitem__(self, key):
        """
        Get item or slice.
        
        Args:
            key: An index or slice object
            
        Returns:
            The item at the specified index or a list of items for a slice
            
        Raises:
            SQLListIndexError: If the index is out of range
        """
        if isinstance(key, slice):
            # Handle slice
            return self._get_slice(key)
        else:
            # Handle single item
            return self._get_item(key)
    
    def _get_slice(self, slice_obj: slice) -> List[T]:
        """
        Get a slice of the list.
        
        Args:
            slice_obj: The slice object
            
        Returns:
            A list of items in the slice
        """
        # Get start, stop, step from slice
        start, stop, step = slice_obj.indices(len(self))
        
        # Build result list
        result = []
        for i in range(start, stop, step):
            result.append(self._get_item(i))
        
        return result
    
    def __setitem__(self, key, value):
        """
        Set item or slice.
        
        Args:
            key: An index or slice object
            value: The value to set
            
        Raises:
            SQLListIndexError: If the index is out of range
            SQLListValueError: If the slice replacement doesn't match in length
        """
        if isinstance(key, slice):
            # Handle slice
            self._set_slice(key, value)
        else:
            # Handle single item
            self._set_item(key, value)
    
    def _set_slice(self, slice_obj: slice, values):
        """
        Set a slice of the list.
        
        Args:
            slice_obj: The slice object
            values: The values to set
            
        Raises:
            SQLListValueError: If extended slice is used with value of different length
        """
        # Get start, stop, step from slice
        start, stop, step = slice_obj.indices(len(self))
        
        # For step=1, we can replace with a sequence of any length
        if step == 1:
            # Create a new version of the list
            full_list = list(self)
            full_list[slice_obj] = values
            
            # Clear and repopulate
            self.clear()
            self.extend(full_list)
        else:
            # For extended slices, lengths must match
            indices = range(start, stop, step)
            values_list = list(values)
            
            if len(indices) != len(values_list):
                raise SQLListValueError(
                    f"Attempt to assign sequence of size {len(values_list)} "
                    f"to extended slice of size {len(indices)}"
                )
            
            # Set each item individually
            for i, value in zip(indices, values_list):
                self._set_item(i, value)
    
    def __delitem__(self, key):
        """
        Delete item or slice.
        
        Args:
            key: An index or slice object
            
        Raises:
            SQLListIndexError: If the index is out of range
        """
        if isinstance(key, slice):
            # Handle slice
            self._del_slice(key)
        else:
            # Handle single item
            self._del_item(key)
    
    def _del_slice(self, slice_obj: slice):
        """
        Delete a slice of the list.
        
        Args:
            slice_obj: The slice object
        """
        # For slices, we need to recreate the list without the sliced items
        full_list = list(self)
        del full_list[slice_obj]
        
        # Clear and repopulate
        self.clear()
        self.extend(full_list)
    
    def __len__(self) -> int:
        """
        Return the length of the list.
        
        Returns:
            The number of items in the list
        """
        if self.is_memory_only:
            return len(self.memory_list)
        else:
            return self._get_db_length()
    
    def __iter__(self) -> Iterator[T]:
        """
        Return an iterator over the list.
        
        Returns:
            An iterator yielding all items
        """
        if self.is_memory_only:
            yield from self.memory_list
        else:
            with self.Session() as session:
                items = session.query(ListItem).order_by(ListItem.index).all()
                for item in items:
                    yield json.loads(item.value)
    
    def __contains__(self, item) -> bool:
        """
        Check if the list contains an item.
        
        Args:
            item: The item to check for
            
        Returns:
            True if the item is in the list, False otherwise
        """
        if self.is_memory_only:
            return item in self.memory_list
        else:
            try:
                self.index(item)
                return True
            except SQLListValueError:
                return False
    
    def __add__(self, other) -> SQLList:
        """
        Return a new list containing the concatenation of self and other.
        
        Args:
            other: Another list or list-like object
            
        Returns:
            A new SQLList with concatenated items
        """
        result = self.copy()
        result.extend(other)
        return result
    
    def __iadd__(self, other) -> SQLList:
        """
        Implement += operator (in-place concatenation).
        
        Args:
            other: Another list or list-like object
            
        Returns:
            Self, after extending with other
        """
        self.extend(other)
        return self
    
    def __mul__(self, n: int) -> SQLList:
        """
        Return a new list containing n copies of self.
        
        Args:
            n: The number of copies
            
        Returns:
            A new SQLList with repeated items
        """
        if not isinstance(n, int):
            raise SQLListValueError(f"Can't multiply list by non-int of type {type(n)}")
        
        result = SQLList(memory_threshold=self.memory_threshold)
        for _ in range(n):
            result.extend(self)
        return result
    
    def __rmul__(self, n: int) -> SQLList:
        """
        Return a new list containing n copies of self (right multiplication).
        
        Args:
            n: The number of copies
            
        Returns:
            A new SQLList with repeated items
        """
        return self.__mul__(n)
    
    def __imul__(self, n: int) -> SQLList:
        """
        Implement *= operator (in-place repeat).
        
        Args:
            n: The number of copies
            
        Returns:
            Self, after repetition
        """
        if not isinstance(n, int):
            raise SQLListValueError(f"Can't multiply list by non-int of type {type(n)}")
        
        # Special case for n <= 0
        if n <= 0:
            self.clear()
            return self
        
        # Special case for n == 1 (no change)
        if n == 1:
            return self
        
        # For n > 1, multiply the list
        original = list(self)
        self.clear()
        for _ in range(n):
            self.extend(original)
        
        return self
    
    def __repr__(self) -> str:
        """
        Return a string representation of the list.
        
        Returns:
            A string representation
        """
        if self.is_memory_only:
            items_repr = repr(self.memory_list)
        else:
            items_repr = repr(list(self))
            
        return f"SQLList({items_repr}, memory_threshold={self.memory_threshold})"
    
    def __str__(self) -> str:
        """
        Return a string representation of the list.
        
        Returns:
            A string representation
        """
        if self.is_memory_only:
            return str(self.memory_list)
        else:
            return str(list(self))
    
    def __eq__(self, other) -> bool:
        """
        Compare for equality with another list.
        
        Args:
            other: Another list or list-like object
            
        Returns:
            True if the lists are equal, False otherwise
        """
        if not hasattr(other, '__iter__') or not hasattr(other, '__len__'):
            return False
        
        if len(self) != len(other):
            return False
        
        return all(a == b for a, b in zip(self, other))
    
    def __cleanup(self):
        """
        Clean up resources when the object is garbage collected.
        Removes temporary database file if one was created.
        """
        # Close database connections
        if hasattr(self, 'engine'):
            self.engine.dispose()
            
        # Delete temporary file if we created one
        if hasattr(self, 'db_path') and self.db_path.startswith('sqlite:///'):
            file_path = self.db_path[10:]  # Remove 'sqlite:///'
            
            # Only delete if it's a temporary file (in temp directory)
            if os.path.exists(file_path) and file_path.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(file_path)
                except (OSError, IOError):
                    pass
    
    def __del__(self):
        """
        Destructor to clean up resources.
        """
        try:
            self.__cleanup()
        except:
            pass  # Suppress any errors during cleanup
    
    # Implementation of abstract methods from BaseClass
    
    @classmethod
    def example(cls) -> SQLList:
        """
        Create an example SQLList for demonstration purposes.
        
        Returns:
            A new SQLList with some example data
        """
        return cls(
            ["example1", "example2", "example3"], 
            memory_threshold=1024  # 1KB, small threshold for demo purposes
        )
    
    def to_dict(self, add_edsl_version=False) -> dict:
        """
        Serialize this object to a dictionary.
        
        Args:
            add_edsl_version: Whether to include EDSL version information
            
        Returns:
            A dictionary representation of the object
        """
        result = {
            "items": list(self),
            "memory_threshold": self.memory_threshold,
            "is_memory_only": self.is_memory_only
        }
        
        if add_edsl_version:
            from .. import __version__
            result["edsl_version"] = __version__
            result["edsl_class_name"] = self.__class__.__name__
            
        return result
    
    @classmethod
    def from_dict(cls, d: dict) -> SQLList:
        """
        Create an instance from a dictionary.
        
        Args:
            d: Dictionary containing the object data
            
        Returns:
            A new SQLList instance
        """
        memory_threshold = d.get("memory_threshold", None)
        items = d.get("items", [])
        
        return cls(items, memory_threshold=memory_threshold)
    
    def code(self) -> str:
        """
        Generate Python code that recreates this object.
        
        Returns:
            Python code that, when executed, creates an equivalent object
        """
        items_repr = repr(list(self))
        code = f"SQLList({items_repr}, memory_threshold={self.memory_threshold})"
        
        return code


def main():
    """
    Demonstrate SQLList functionality for interactive testing.
    """
    # Create a SQLList with a small memory threshold
    lst = SQLList(memory_threshold=1024)  # 1KB threshold for quick offloading
    
    print("Creating a SQLList with memory_threshold=1KB...")
    
    # Adding items
    print("Adding items...")
    for i in range(100):
        lst.append(f"Item {i}")
        if i % 10 == 0:
            print(f"Added {i+1} items")
    
    # Check if data was offloaded
    print(f"Is memory only: {lst.is_memory_only}")
    
    # Accessing items
    print(f"First item: {lst[0]}")
    print(f"Last item: {lst[-1]}")
    print(f"Slice [10:15]: {lst[10:15]}")
    
    # Modification
    print("Modifying items...")
    lst[5] = "Modified Item 5"
    print(f"Modified item: {lst[5]}")
    
    # Length
    print(f"Length: {len(lst)}")
    
    # Contains
    print(f"Contains 'Item 50': {'Item 50' in lst}")
    print(f"Contains 'Nonexistent': {'Nonexistent' in lst}")
    
    # Iteration
    print("Iterating over first 5 items...")
    for i, item in enumerate(lst):
        if i >= 5:
            break
        print(f"  {i}: {item}")
    
    # Methods
    print(f"Index of 'Modified Item 5': {lst.index('Modified Item 5')}")
    print(f"Count of 'Item 20': {lst.count('Item 20')}")
    
    # Operations
    print("Testing operations...")
    lst.insert(10, "Inserted Item")
    print(f"After insert: {lst[9:12]}")
    
    popped = lst.pop(10)
    print(f"Popped item: {popped}")
    print(f"After pop: {lst[9:12]}")
    
    # Cleanup
    print("Clearing list...")
    lst.clear()
    print(f"Length after clear: {len(lst)}")
    print(f"Is memory only after clear: {lst.is_memory_only}")


if __name__ == "__main__":
    import doctest
    doctest.testmod()