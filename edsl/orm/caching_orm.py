"""
SQLAlchemy ORM definitions for EDSL data persistence.

This module defines the SQLAlchemy ORM models used for storing Cache and CacheEntry
objects in a SQL database. It provides models and functions for persisting the cache
data with all its metadata.
"""

from __future__ import annotations
import json
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Type

from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime, Table, Boolean
from sqlalchemy.orm import relationship, Session, backref, mapped_column, Mapped

#from .sql_model_base import Base
# Import base exception
from .sql_base import Base

from edsl.base.exceptions import BaseException


class CacheOrmException(BaseException):
    """Exception raised for errors in the Cache ORM operations."""
    pass


class CacheEntryMappedObject(Base):
    """SQLAlchemy ORM model for CacheEntry."""
    
    __tablename__ = "cache_entry"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_id: Mapped[int] = mapped_column(Integer, ForeignKey("cache.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    iteration: Mapped[int] = mapped_column(nullable=False, default=0)
    timestamp: Mapped[int] = mapped_column(nullable=False)
    service: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Store parameters as serialized JSON
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Relationship to parent Cache
    cache: Mapped["CacheMappedObject"] = relationship("CacheMappedObject", back_populates="entries")
    
    def __repr__(self) -> str:
        """Return string representation of the CacheEntry."""
        return f"<CacheEntryMappedObject(id={self.id}, key='{self.key}')>"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the parameters dictionary from JSON."""
        return json.loads(self.parameters_json)
    
    @parameters.setter
    def parameters(self, value: Dict[str, Any]):
        """Set the parameters dictionary as JSON."""
        self.parameters_json = json.dumps(value)
    
    def to_edsl_object(self):
        """Convert this ORM model to a CacheEntry domain object."""
        # Import here to avoid circular imports
        from edsl.caching.cache_entry import CacheEntry
        
        # Create a new CacheEntry with all the attributes
        entry = CacheEntry(
            model=self.model,
            parameters=self.parameters,
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt,
            output=self.output,
            iteration=self.iteration,
            timestamp=self.timestamp,
            service=self.service,
            validated=self.validated
        )
        
        # Store the ORM ID for future reference
        entry._orm_id = self.id
        
        return entry
    
    @classmethod
    def from_edsl_object(cls, entry, cache_id: int):
        """Create an ORM model from a CacheEntry domain object."""
        # Create the base record
        orm_entry = cls(
            key=entry.key,
            model=entry.model,
            parameters_json=json.dumps(entry.parameters),
            system_prompt=entry.system_prompt,
            user_prompt=entry.user_prompt,
            output=entry.output,
            iteration=entry.iteration,
            timestamp=entry.timestamp,
            service=entry.service,
            validated=entry.validated,
            cache_id=cache_id
        )
        
        return orm_entry


class CacheMappedObject(Base):
    """SQLAlchemy ORM model for Cache."""
    
    __tablename__ = "cache"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True) # Removed
    # immediate_write: Mapped[bool] = mapped_column(Boolean, default=True) # Removed
    
    # Fields to mirror Cache.to_dict() output's top-level metadata
    edsl_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    edsl_class_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    entries: Mapped[List[CacheEntryMappedObject]] = relationship("CacheEntryMappedObject", back_populates="cache", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """Return string representation of the Cache."""
        return f"<CacheMappedObject(id={self.id}, entries_count={len(self.entries) if self.entries else 0})>"
    
    def to_edsl_object(self):
        """Convert this ORM model to a Cache domain object."""
        # Import here to avoid circular imports
        from edsl.caching.cache import Cache 
        
        # Prepare the data dictionary for Cache.from_dict()
        data_for_from_dict = {}
        for entry_orm in self.entries:
            edsl_entry_object = entry_orm.to_edsl_object() 
            data_for_from_dict[entry_orm.key] = edsl_entry_object.to_dict()
            
        # Add edsl_version and edsl_class_name to the dictionary
        if self.edsl_version:
            data_for_from_dict["edsl_version"] = self.edsl_version
        if self.edsl_class_name:
            data_for_from_dict["edsl_class_name"] = self.edsl_class_name
            
        # Create Cache using from_dict. This will use default filename and immediate_write.
        cache_edsl = Cache.from_dict(data_for_from_dict)
        
        # Store the ORM ID for future reference
        cache_edsl._orm_id = self.id
        
        return cache_edsl
    
    @classmethod
    def from_edsl_object(cls, cache_edsl, session: Optional[Session] = None):
        """Create an ORM model from a Cache domain object."""
        # Get version and class name from cache_edsl.to_dict()
        cache_as_dict = cache_edsl.to_dict(add_edsl_version=True)
        
        # Create the base record - only storing what's in to_dict's top level
        orm_cache = cls(
            edsl_version=cache_as_dict.get("edsl_version"),
            edsl_class_name=cache_as_dict.get("edsl_class_name")
        )
        
        # Add to session to get ID if provided
        if session:
            session.add(orm_cache)
            session.flush()
            
            # Now add all entries
            if hasattr(cache_edsl, 'data') and cache_edsl.data:
                for key, entry_edsl in cache_edsl.data.items():
                    orm_entry = CacheEntryMappedObject.from_edsl_object(entry_edsl, orm_cache.id)
                    session.add(orm_entry)
        
        return orm_cache


# Data table for SQLiteDict and basic key-value storage
class CacheDataMappedObject(Base):
    """
    SQLAlchemy ORM model for key-value data storage, specifically for cache-related data.
    
    This class represents a table in the SQL database with a simple
    key-value schema. It is used by the Cache and SQLiteDict classes
    to store cached data persistently.
    
    Attributes:
        __tablename__ (str): Name of the database table ("cache_data")
        key (Column): Primary key column for storing lookup keys
        value (Column): Column for storing serialized data values
    """
    __tablename__ = "cache_data"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(String, nullable=True)


if __name__ == "__main__":
    from edsl import Cache 
    cache_example = Cache.example()

    cache_example = Cache.pull("e56306e6-bb9c-40b9-b03b-c55c0fba79e6")

    from .sql_base import create_test_session

    db, _, _ = create_test_session()

    cache_orm = CacheMappedObject.from_edsl_object(cache_example, db)
    db.add(cache_orm)
    db.commit()

    print(cache_orm)

    # working with JSON
    #  SELECT output -> '$.content[0].text' FROM cache_entry;