"""
SQLAlchemy ORM definitions for EDSL data persistence.

This module defines the SQLAlchemy ORM models used for storing cache data
in a SQL database. It provides a simple key-value schema that allows
for efficient storage and retrieval of cached data.
"""

from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


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
