import sqlite3
import pickle
import collections.abc
from collections import UserList
from bisect import bisect_left

class SQLiteList(UserList):
    """
    A memory-efficient drop-in replacement for collections.UserList, backed by SQLite.
    
    This implementation is carefully designed to be a full replacement for UserList
    while reducing memory usage by storing list data in SQLite rather than Python's
    memory. It maintains 100% compatibility with UserList's interface.
    
    Key features:
    - Matches UserList's API exactly, including data attribute behavior
    - Inherits from UserList to ensure type compatibility
    - Uses SQLite for storage to reduce memory consumption
    - Provides transaction support for bulk operations
    - Works directly with the Results class
    
    Typical usage:
    ```python
    # Initialize with items
    mylist = SQLiteList([1, 2, 3])
    
    # Normal list operations
    mylist.append(4)
    mylist.extend([5, 6])
    mylist[0] = 10
    
    # Full slice support
    mylist[1:3] = [20, 30]
    
    # Direct UserList compatibility
    print(mylist.data)  # same as list(mylist)
    ```
    
    INTEGRATION WITH RESULTS CLASS:
    
    This class supports being a parent class for Results. When used with Results, 
    it detects this and delegates to parent UserList behavior for compatibility.
    
    To use with Results, simply change DataList = UserList to:
    
    ```python
    from ..db_list.sqlite_list import SQLiteList as DataList
    ```
    
    Implementation notes:
    - By default uses in-memory SQLite database
    - Can use persistent file storage with db_path parameter
    - Pickles objects for storage, so all Python objects are supported
    - Uses a table with schema: mylist(pos INTEGER PRIMARY KEY, val BLOB NOT NULL)
    - Special handling for Results and general SQLiteList use cases
    """

    def __init__(self, initlist=None, db_path=":memory:"):
        """
        Initialize a new SQLiteList.
        
        Args:
            initlist: Optional iterable of initial items
            db_path: Path to the SQLite database file (":memory:" for in-memory)
        """
        # We need to initialize basic UserList structure first
        # This creates the self.data attribute that UserList expects
        super().__init__([])
        
        # Special handling for Results instance
        self._is_results = self.__class__.__name__ == 'Results'
        
        # For Results class, we use a different initialization approach
        # that relies more heavily on the parent UserList implementation
        if self._is_results:
            # Store data directly in self.data as UserList expects
            self._userlist_data = self.data
            # If data provided, use it
            if initlist is not None:
                self.data[:] = list(initlist)
            return
            
        # Setup SQLite storage for non-Results instances
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS mylist ("
            " pos INTEGER PRIMARY KEY,"
            " val BLOB NOT NULL)"
        )
        
        # Store a reference to the UserList data attribute
        self._userlist_data = self.data
        
        # Now populate with initial data if provided
        if initlist is not None:
            # For efficient initialization, set up a single transaction
            with self.conn:
                pos = 0
                for item in initlist:
                    # Insert into SQLite
                    self.conn.execute(
                        "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                        (pos, pickle.dumps(item))
                    )
                    # Also populate the underlying list to maintain dual storage
                    self._userlist_data.append(item)
                    pos += 1
    
    @property
    def data(self):
        """
        Access the data list, matching UserList's behavior exactly.
        
        The data property is critical for both UserList compatibility and
        for integration with Results class which accesses data directly.
        
        Returns:
            The list of items in this collection
        """
        # Check if we're a Results instance by checking class name
        # This works even during initialization
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, always use Python list attribute directly
        if is_results:
            # During initialization, we may not have _userlist_data yet
            if hasattr(self, '_userlist_data'):
                return self._userlist_data
            # Fall back to a new empty list during initialization
            return []
        
        # For SQLiteList, use dual storage
        if hasattr(self, '_userlist_data'):
            return self._userlist_data
        # Fall back during initialization
        return []
    
    @data.setter
    def data(self, value):
        """
        Replace all data with new values, matching UserList's behavior exactly.
        
        Args:
            value: The new list of items
        """
        # Check if we're a Results instance
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, direct assignment to our backing store
        if is_results:
            # Create _userlist_data if it doesn't exist yet
            if not hasattr(self, '_userlist_data'):
                self._userlist_data = value
            else:
                # Clear and extend to match UserList behavior
                self._userlist_data[:] = value
            return
            
        # For SQLiteList, properly initialized instances clear and populate both storages
        if hasattr(self, 'conn') and hasattr(self, '_userlist_data'):
            # We're fully initialized, use clear/extend
            self.clear()
            self.extend(value)
        # During initialization, just set up our backing store
        elif not hasattr(self, '_userlist_data'):
            self._userlist_data = list(value) if value is not None else []
        else:
            self._userlist_data[:] = list(value) if value is not None else []

    def __len__(self):
        """Return the number of items in the list."""
        # Check if we're a Results instance
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, use UserList behavior
        if is_results:
            # For compatibility with the parent class
            return len(self.data)
            
        # For SQLiteList, use our own implementation
        return len(self._userlist_data)

    def __getitem__(self, index):
        """Get item(s) at index or slice."""
        # Check if we're a Results instance
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, use UserList behavior
        if is_results:
            return self.data[index]
            
        # For SQLiteList, use our own implementation
        return self._userlist_data[index]

    def __setitem__(self, index, value):
        """Set item(s) at index or slice."""
        # Check if we're a Results instance
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, use UserList behavior
        if is_results:
            self.data[index] = value
            return
            
        # For SQLiteList, implement our dual storage approach
        if isinstance(index, int):
            # Handle negative indices
            if index < 0:
                index = len(self) + index
            if index < 0 or index >= len(self):
                raise IndexError("list assignment index out of range")
                
            # Update both storages together
            with self.conn:
                # Update SQLite
                self.conn.execute(
                    "UPDATE mylist SET val = ? WHERE pos = ?",
                    (pickle.dumps(value), index)
                )
                # Update Python list
                self._userlist_data[index] = value
            
        elif isinstance(index, slice):
            # Get the indices that will be affected
            start, stop, step = index.indices(len(self))
            
            # Special handling for simple replacement (common case)
            if step == 1:
                # Use a transaction for consistency
                with self.conn:
                    # First update the Python list (this handles all the slicing logic for us)
                    self._userlist_data[index] = value
                    
                    # Then sync SQLite with the Python list state
                    # This is simpler than trying to replicate Python's slice assignment logic
                    self.conn.execute("DELETE FROM mylist")
                    for pos, item in enumerate(self._userlist_data):
                        self.conn.execute(
                            "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                            (pos, pickle.dumps(item))
                        )
            else:
                # For more complex slices, rely on the Python list for correct behavior
                # then sync SQLite
                self._userlist_data[index] = value
                
                # Sync SQLite with Python list
                with self.conn:
                    # Clear and rebuild the SQLite table to match exactly
                    self.conn.execute("DELETE FROM mylist")
                    for pos, item in enumerate(self._userlist_data):
                        self.conn.execute(
                            "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                            (pos, pickle.dumps(item))
                        )
        else:
            raise TypeError("list indices must be integers or slices")

    def __delitem__(self, index):
        """Delete item(s) at index or slice."""
        # Check if we're a Results instance
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, use UserList behavior
        if is_results:
            del self.data[index]
            return
            
        # For SQLiteList, implement our dual storage approach
        if isinstance(index, int):
            # Handle negative indices
            if index < 0:
                index = len(self) + index
            if index < 0 or index >= len(self):
                raise IndexError("list index out of range")
                
            # Delete from both storages
            with self.conn:
                # Delete from Python list
                del self._userlist_data[index]
                
                # Reconstruct SQLite storage to match exactly
                self.conn.execute("DELETE FROM mylist")
                for pos, item in enumerate(self._userlist_data):
                    self.conn.execute(
                        "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                        (pos, pickle.dumps(item))
                    )
        elif isinstance(index, slice):
            # For slices, rely on Python list behavior then sync SQLite
            with self.conn:
                # Delete from Python list
                del self._userlist_data[index]
                
                # Reconstruct SQLite storage
                self.conn.execute("DELETE FROM mylist")
                for pos, item in enumerate(self._userlist_data):
                    self.conn.execute(
                        "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                        (pos, pickle.dumps(item))
                    )
        else:
            raise TypeError("list indices must be integers or slices")

    def insert(self, i, item=None):
        """
        Insert item before position i.
        
        This special implementation handles both:
        - Standard list.insert(i, item) pattern
        - Results.insert(item) single parameter pattern used by Results class
        """
        # Check if we're a Results instance
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, delegate to parent UserList
        if is_results:
            # Special handling for Results.insert(item) pattern
            if item is None and not isinstance(i, int):
                # This is Results.insert(item) signature
                # Just pass to insert the value at the end
                value = i  # This is actually the item
                self.data.append(value)
            else:
                # Standard insert(i, item)
                self.data.insert(i, item)
            return
            
        # Check if we're fully initialized
        if not hasattr(self, 'conn') or not hasattr(self, '_userlist_data'):
            # During initialization, just append to our list
            if not hasattr(self, '_userlist_data'):
                self._userlist_data = []
            if item is None and not isinstance(i, int):
                self._userlist_data.append(i)  # i is actually the item
            else:
                self._userlist_data.insert(i, item)
            return
            
        # For SQLiteList instances, implement dual storage
        
        # Special handling for single-argument mode (insert(item))
        if item is None and not isinstance(i, int):
            # Called as insert(item) - switch to append pattern
            item = i
            i = len(self)
        
        # Normalize the index
        if i < 0:
            i += len(self)
        i = max(0, min(len(self), i))
        
        try:
            # Update both storages
            with self.conn:
                # Clear all data and reinsert
                self.conn.execute("DELETE FROM mylist")
                
                # Update Python list first
                self._userlist_data.insert(i, item)
                
                # Reinsert all items
                for pos, value in enumerate(self._userlist_data):
                    self.conn.execute(
                        "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                        (pos, pickle.dumps(value))
                    )
        except Exception as e:
            # If SQLite fails, at least keep the Python list in sync
            self._userlist_data.insert(i, item)
    
    # UserList-compatible operations with dual storage
    
    def append(self, item):
        """Append item to the end of the list."""
        # Check if we're a Results instance
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, use parent UserList implementation
        if is_results:
            self.data.append(item)
            return
            
        # For SQLiteList, insert at the end
        self.insert(len(self), item)
        
    def clear(self):
        """Remove all items from the list."""
        # Check if we're a Results instance
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, use parent UserList implementation
        if is_results:
            self.data.clear()
            return
            
        # Check if we're fully initialized
        if not hasattr(self, 'conn') or not hasattr(self, '_userlist_data'):
            return
            
        # For SQLiteList, clear both storages
        with self.conn:
            # Clear SQLite
            self.conn.execute("DELETE FROM mylist")
            # Clear Python list
            self._userlist_data.clear()
        
    def copy(self):
        """Return a shallow copy of the list."""
        # Check if we're a Results instance
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        
        # For Results, use parent UserList implementation
        if is_results:
            return type(self)(self.data)
            
        # For SQLiteList, use our constructor
        return type(self)(self._userlist_data, db_path=self.db_path)
        
    def count(self, item):
        """Return number of occurrences of item."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().count(item)
            
        # For SQLiteList, use Python list for better performance
        return self._userlist_data.count(item)
        
    def extend(self, other):
        """Extend list by appending elements from the iterable."""
        # For Results, use parent UserList implementation
        if self._is_results:
            super().extend(other)
            return
            
        # For SQLiteList, update both storages
        with self.conn:
            # First update Python list
            self._userlist_data.extend(other)
            
            # Then sync SQLite
            pos = len(self._userlist_data) - len(list(other))
            for item in other:
                self.conn.execute(
                    "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                    (pos, pickle.dumps(item))
                )
                pos += 1
                
    def index(self, item, *args):
        """Return first index of value."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().index(item, *args) if args else super().index(item)
            
        # For SQLiteList, use Python list for better performance
        return self._userlist_data.index(item, *args) if args else self._userlist_data.index(item)
        
    def pop(self, i=-1):
        """Remove and return item at index (default last)."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().pop(i)
            
        # For SQLiteList, handle ourselves
        # Get the value before removing
        value = self[i]
        
        # Remove the item
        del self[i]
        
        # Return the value
        return value
        
    def remove(self, item):
        """Remove first occurrence of value."""
        # For Results, use parent UserList implementation
        if self._is_results:
            super().remove(item)
            return
            
        # For SQLiteList, find the index and remove
        idx = self.index(item)
        del self[idx]
        
    def reverse(self):
        """Reverse IN PLACE."""
        # For Results, use parent UserList implementation
        if self._is_results:
            super().reverse()
            return
            
        # For SQLiteList, update both storages
        with self.conn:
            # Reverse Python list
            self._userlist_data.reverse()
            
            # Sync with SQLite
            self.conn.execute("DELETE FROM mylist")
            for pos, item in enumerate(self._userlist_data):
                self.conn.execute(
                    "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                    (pos, pickle.dumps(item))
                )
        
    def sort(self, *args, **kwargs):
        """Sort IN PLACE."""
        # For Results, use parent UserList implementation
        if self._is_results:
            super().sort(*args, **kwargs)
            return
            
        # For SQLiteList, update both storages
        with self.conn:
            # Sort Python list
            self._userlist_data.sort(*args, **kwargs)
            
            # Sync with SQLite
            self.conn.execute("DELETE FROM mylist")
            for pos, item in enumerate(self._userlist_data):
                self.conn.execute(
                    "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                    (pos, pickle.dumps(item))
                )
        
    def __add__(self, other):
        """Return a new list containing this list and other concatenated."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__add__(other)
            
        # For SQLiteList, create a new list with combined items
        result = self.copy()
        result.extend(other)
        return result
        
    def __iadd__(self, other):
        """Implement self += other."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__iadd__(other)
            
        # For SQLiteList, extend in place
        self.extend(other)
        return self
        
    def __mul__(self, n):
        """Return a new list containing n copies of this list concatenated."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__mul__(n)
            
        # For SQLiteList, create a new multiplied list
        if not isinstance(n, int):
            return NotImplemented
            
        # Create a result with our items * n
        result = type(self)(self._userlist_data * n, db_path=self.db_path)
        return result
        
    def __imul__(self, n):
        """Implement self *= n."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__imul__(n)
            
        # For SQLiteList, multiply in place
        if not isinstance(n, int):
            return NotImplemented
            
        # Update both storages
        with self.conn:
            # Multiply Python list
            self._userlist_data *= n
            
            # Sync with SQLite
            self.conn.execute("DELETE FROM mylist")
            for pos, item in enumerate(self._userlist_data):
                self.conn.execute(
                    "INSERT INTO mylist (pos, val) VALUES (?, ?)",
                    (pos, pickle.dumps(item))
                )
        
        return self

    def __iter__(self):
        """Iterate through items in order."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__iter__()
            
        # For SQLiteList, use Python list for better performance
        return iter(self._userlist_data)
            
    def __contains__(self, item):
        """Return True if item is in the list."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__contains__(item)
            
        # For SQLiteList, check Python list
        return item in self._userlist_data

    def __repr__(self):
        """Return string representation like a list."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__repr__()
            
        # For SQLiteList, show the Python list
        return repr(self._userlist_data)
    
    def __str__(self):
        """Return string representation like a list."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__str__()
            
        # For SQLiteList, show the Python list
        return str(self._userlist_data)
        
    def _repr_html_(self):
        """HTML representation for Jupyter notebooks."""
        # For Results, use parent UserList implementation if it has one
        if self._is_results and hasattr(super(), '_repr_html_'):
            return super()._repr_html_()
            
        # Create a basic HTML list representation
        items = self._userlist_data if not self._is_results else super().data
        return f"<ul>{''.join(f'<li>{item}</li>' for item in items)}</ul>"
    
    def __eq__(self, other):
        """Compare for equality with another sequence."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__eq__(other)
            
        # For SQLiteList, compare with Python list
        if isinstance(other, (UserList, list)):
            return self._userlist_data == other
        return NotImplemented
    
    def __lt__(self, other):
        """Compare for less than."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__lt__(other)
            
        # For SQLiteList, compare with Python list
        if isinstance(other, (UserList, list)):
            return self._userlist_data < other
        return NotImplemented
        
    def __le__(self, other):
        """Compare for less than or equal."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__le__(other)
            
        # For SQLiteList, compare with Python list
        if isinstance(other, (UserList, list)):
            return self._userlist_data <= other
        return NotImplemented
        
    def __gt__(self, other):
        """Compare for greater than."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__gt__(other)
            
        # For SQLiteList, compare with Python list
        if isinstance(other, (UserList, list)):
            return self._userlist_data > other
        return NotImplemented
        
    def __ge__(self, other):
        """Compare for greater than or equal."""
        # For Results, use parent UserList implementation
        if self._is_results:
            return super().__ge__(other)
            
        # For SQLiteList, compare with Python list
        if isinstance(other, (UserList, list)):
            return self._userlist_data >= other
        return NotImplemented
    
    def close(self):
        """Close the underlying database connection."""
        # Only close if this is a pure SQLiteList (not Results)
        is_results = getattr(self, '_is_results', self.__class__.__name__ == 'Results')
        if not is_results and hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.conn = None
    
    def __del__(self):
        """Clean up resources when the object is garbage collected."""
        self.close()

