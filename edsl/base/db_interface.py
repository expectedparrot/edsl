"""Database interface for EDSL objects.

This module provides a high-level interface for working with the database persistence
features of EDSL objects. It includes utilities for connecting to databases,
initializing schema, and performing common operations on persisted objects.
"""

from typing import Optional, List, Dict, Any, Type, TypeVar, Union
import os
import logging

from .db_manager import get_db_manager, DBManager
from .base_class import Base as EDSLBase
from .exceptions import BaseValueError, BaseException

# Type variable for EDSL objects
T = TypeVar('T', bound=EDSLBase)


class DBInterfaceException(BaseException):
    """Exception raised for errors in the database interface."""
    pass


class EDSLDB:
    """High-level interface for database operations with EDSL objects.
    
    This class provides a simplified interface for storing and retrieving EDSL objects
    from databases, with support for connection management, batch operations, and queries.
    
    Attributes:
        db_manager: The underlying DBManager instance
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """Initialize the database interface.
        
        Args:
            connection_string: Optional database connection string.
                Defaults to using the environment variable EDSL_DB_URI,
                or an in-memory SQLite database if not specified.
        """
        self.db_manager = get_db_manager(connection_string)
        
        # Initialize all tables
        self.db_manager.initialize_tables()
    
    def save(self, obj: EDSLBase) -> Any:
        """Save an EDSL object to the database.
        
        Args:
            obj: The EDSL object to save
            
        Returns:
            The object identifier in the database
            
        Raises:
            DBInterfaceException: If the object doesn't implement to_db
        """
        if not hasattr(obj, 'to_db'):
            raise DBInterfaceException(
                f"Object of type {type(obj).__name__} does not implement to_db method")
        
        return obj.to_db(self.db_manager)
    
    def load(self, obj_class: Type[T], identifier: Any) -> Optional[T]:
        """Load an EDSL object from the database.
        
        Args:
            obj_class: The class of the object to load
            identifier: The database identifier for the object
            
        Returns:
            The loaded object, or None if not found
            
        Raises:
            DBInterfaceException: If the class doesn't implement from_db
        """
        if not hasattr(obj_class, 'from_db'):
            raise DBInterfaceException(
                f"Class {obj_class.__name__} does not implement from_db method")
        
        return obj_class.from_db(self.db_manager, identifier)
    
    def save_all(self, objects: List[EDSLBase]) -> List[Any]:
        """Save multiple EDSL objects to the database.
        
        Args:
            objects: List of EDSL objects to save
            
        Returns:
            List of object identifiers in the database
        """
        return [self.save(obj) for obj in objects]
    
    def load_all(self, obj_class: Type[T], identifiers: List[Any]) -> List[Optional[T]]:
        """Load multiple EDSL objects from the database.
        
        Args:
            obj_class: The class of the objects to load
            identifiers: List of database identifiers
            
        Returns:
            List of loaded objects (None for any not found)
        """
        return [self.load(obj_class, id) for id in identifiers]
    
    def list_tables(self) -> List[str]:
        """List all tables in the database.
        
        Returns:
            List of table names
        """
        return self.db_manager.list_tables()
    
    def close(self):
        """Close database connections."""
        if hasattr(self.db_manager, 'engine'):
            self.db_manager.engine.dispose()


# Global default instance
_default_db = None


def get_default_db() -> EDSLDB:
    """Get the default EDSLDB instance.
    
    Returns:
        The global default EDSLDB instance
    """
    global _default_db
    
    if _default_db is None:
        # Get connection string from environment or use default
        connection_string = os.environ.get("EDSL_DB_URI")
        _default_db = EDSLDB(connection_string)
    
    return _default_db


def save_object(obj: EDSLBase) -> Any:
    """Save an EDSL object using the default database.
    
    This is a convenience function to save an object without explicitly
    creating an EDSLDB instance.
    
    Args:
        obj: The EDSL object to save
        
    Returns:
        The object identifier in the database
    """
    db = get_default_db()
    return db.save(obj)


def load_object(obj_class: Type[T], identifier: Any) -> Optional[T]:
    """Load an EDSL object using the default database.
    
    This is a convenience function to load an object without explicitly
    creating an EDSLDB instance.
    
    Args:
        obj_class: The class of the object to load
        identifier: The database identifier for the object
        
    Returns:
        The loaded object, or None if not found
    """
    db = get_default_db()
    return db.load(obj_class, identifier)