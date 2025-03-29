"""
SQLAlchemy ORM definitions for SQLList data persistence.

This module defines the SQLAlchemy ORM models used for storing list data
in a SQLite database.
"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ListItem(Base):
    """
    SQLAlchemy ORM model for list items storage.
    
    This class represents a table in the SQLite database with index and value columns.
    
    Attributes:
        __tablename__ (str): Name of the database table ("list_items")
        index (Column): Index position in the list as an Integer, primary key
        value (Column): String representation of the serialized value
    """
    __tablename__ = "list_items"
    index = Column("item_index", Integer, primary_key=True)  # Using item_index as DB column name to avoid reserved keyword
    value = Column(String)
    
    
class ListMetadata(Base):
    """
    SQLAlchemy ORM model for storing list metadata.
    
    This class stores metadata about the list such as its length.
    
    Attributes:
        __tablename__ (str): Name of the database table ("list_metadata")
        key (Column): Metadata key name as String, primary key
        value (Column): Metadata value as String
    """
    __tablename__ = "list_metadata"
    key = Column(String, primary_key=True)
    value = Column(String)