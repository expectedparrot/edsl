"""Database manager for EDSL objects.

This module provides a central database connection manager for EDSL objects,
handling SQLAlchemy engine initialization, session management, and table creation.
"""

import os
from typing import Optional, Union, Dict, Any, Type, List
from contextlib import contextmanager
import json
import pickle

from sqlalchemy import create_engine, Column, String, Integer, MetaData, Table, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from .. import logger
from ..base import Base as EDSLBase
from ..base.exceptions import BaseValueError


class DBManager:
    """Database connection manager for EDSL objects.
    
    This class serves as the central point for database operations across all EDSL modules,
    handling connection setup, session management, and ensuring all tables are created
    properly.
    
    Attributes:
        engine: SQLAlchemy engine instance
        session_factory: SQLAlchemy sessionmaker instance
        base: SQLAlchemy declarative base
        initialized_models: A dictionary of initialized ORM models by module
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """Initialize the DBManager with a connection string.
        
        Args:
            connection_string: SQLAlchemy connection string. Defaults to SQLite in-memory
                database if not provided, or can be overridden with EDSL_DB_URI env var.
        """
        # If no connection string provided, check environment variable
        self.connection_string = (
            connection_string or 
            os.environ.get("EDSL_DB_URI") or 
            "sqlite:///:memory:"
        )
        
        # Create SQLAlchemy engine
        self.engine = create_engine(
            self.connection_string,
            poolclass=NullPool,
            connect_args={"check_same_thread": False} if self.connection_string.startswith("sqlite") else {}
        )
        
        # Create session factory
        self.session_factory = sessionmaker(bind=self.engine)
        
        # Create declarative base
        self.base = declarative_base()
        
        # Track initialized models by module name
        self.initialized_models = {}
        
        logger.debug(f"DBManager initialized with connection: {self.connection_string}")
    
    @contextmanager
    def session_scope(self):
        """Context manager for handling SQLAlchemy sessions.
        
        Yields a session and automatically handles commit/rollback on success/exception.
        
        Yields:
            SQLAlchemy Session object
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def initialize_tables(self):
        """Create all tables defined by the SQLAlchemy models.
        
        This should be called after all modules have registered their models.
        """
        self.base.metadata.create_all(self.engine)
        logger.debug("All database tables created")
    
    def register_module_models(self, module_name: str, models: Dict[str, Any]):
        """Register ORM models for a specific module.
        
        Args:
            module_name: The name of the module registering models
            models: A dictionary of model classes to register
        """
        self.initialized_models[module_name] = models
        logger.debug(f"Registered models for module: {module_name}")
    
    def get_model_for_class(self, edsl_class: Type[EDSLBase]) -> Type:
        """Get the SQLAlchemy model corresponding to an EDSL class.
        
        Args:
            edsl_class: An EDSL class that inherits from Base
            
        Returns:
            The corresponding SQLAlchemy model class
            
        Raises:
            BaseValueError: If no ORM model is found for the class
        """
        class_name = edsl_class.__name__
        
        # Search through all registered models
        for module_name, models in self.initialized_models.items():
            for model_name, model_class in models.items():
                # Check if this model is for the requested class
                if hasattr(model_class, "from_" + class_name.lower()):
                    return model_class
        
        raise BaseValueError(f"No ORM model found for EDSL class: {class_name}")
    
    def list_tables(self) -> List[str]:
        """List all tables in the database.
        
        Returns:
            List of table names
        """
        inspector = inspect(self.engine)
        return inspector.get_table_names()


# Global instance for app-wide usage
_db_manager = None


def get_db_manager(connection_string: Optional[str] = None) -> DBManager:
    """Get or create the global DBManager instance.
    
    Args:
        connection_string: Optional connection string to use instead of default
        
    Returns:
        The global DBManager instance
    """
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DBManager(connection_string)
    elif connection_string is not None and connection_string != _db_manager.connection_string:
        # If a different connection string is provided, recreate the manager
        _db_manager = DBManager(connection_string)
    
    return _db_manager