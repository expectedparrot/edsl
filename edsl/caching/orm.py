"""
SQLAlchemy ORM definitions for EDSL data persistence.

This module defines the SQLAlchemy ORM models used for storing cache data
in a SQL database. It provides a simple key-value schema that allows
for efficient storage and retrieval of cached data.

The sqlalchemy imports are lazy to speed up module import time.
"""

# Lazy-loaded sqlalchemy components
_Base = None
_Data = None


def _get_base():
    """Lazily create and return the SQLAlchemy Base class."""
    global _Base
    if _Base is None:
        try:
            from sqlalchemy.orm import declarative_base
        except ImportError:
            raise ImportError(
                "SQLAlchemy is required for SQL-based caching. "
                "Install it with: pip install edsl[caching] or pip install sqlalchemy"
            )

        _Base = declarative_base()
    return _Base


def _get_data_class():
    """Lazily create and return the Data ORM class."""
    global _Data
    if _Data is None:
        from sqlalchemy import Column, String

        Base = _get_base()

        class Data(Base):
            """
            SQLAlchemy ORM model for key-value data storage.

            This class represents a table in the SQL database with a simple
            key-value schema. It is used by the Cache and SQLiteDict classes
            to store cached data persistently.

            Attributes:
                __tablename__ (str): Name of the database table ("data")
                key (Column): Primary key column for storing lookup keys
                value (Column): Column for storing serialized data values
            """

            __tablename__ = "data"
            key = Column(String, primary_key=True)
            value = Column(String)

        _Data = Data
    return _Data


# For backward compatibility, provide module-level access via __getattr__
def __getattr__(name):
    if name == "Base":
        return _get_base()
    if name == "Data":
        return _get_data_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
