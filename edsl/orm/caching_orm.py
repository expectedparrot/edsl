"""
SQLAlchemy ORM definitions for EDSL data persistence.

This module defines the SQLAlchemy ORM models used for storing EDSL objects,
including Cache, CacheEntry, and generic key-value data (CacheDataMappedObject),
 in a SQL database. It provides models and functions for persisting this data
with all its metadata, facilitating robust data management for EDSL.
"""

from __future__ import annotations
import json
# import pickle # Will be removed later if confirmed unused
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Any, Type

from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime, Table, Boolean, func
# Add JSON type import
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship, Session, backref, mapped_column, Mapped

#from .sql_model_base import Base
# Import base exception
from .sql_base import Base, UUIDTrackable

from edsl.base.exceptions import BaseException
from edsl.caching import CacheEntry, Cache # Ensure Cache is imported

class CacheOrmException(Exception): # Corrected inheritance
    """Exception raised for errors in the Cache ORM operations."""
    pass


class CacheEntryMappedObject(Base):
    """SQLAlchemy ORM model for CacheEntry (not meant to be persisted standalone)."""
    edsl_class = None
    
    __tablename__ = "cache_entry"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_id: Mapped[int] = mapped_column(Integer, ForeignKey("cache.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    iteration: Mapped[int] = mapped_column(nullable=False, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    service: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Store parameters as serialized JSON
    # parameters_json: Mapped[str] = mapped_column(Text, nullable=False) # Old version
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False) # New version using sqlalchemy.JSON
    
    # Relationship to parent Cache
    cache: Mapped["CacheMappedObject"] = relationship("CacheMappedObject", back_populates="entries")
    
    def __repr__(self) -> str:
        """Return string representation of the CacheEntry."""
        return f"<CacheEntryMappedObject(id={self.id}, key='{self.key}')>"
    
    # The @property for parameters and its setter are no longer needed
    # if parameters is directly mapped as JSON and EDSL expects a dict.
    # SQLAlchemy's JSON type will handle the load/dump to dict automatically.
    # However, EDSL's CacheEntry.from_edsl_object expects 'parameters' not 'parameters_json'.
    # And the EDSL object uses 'parameters'. So direct mapping is fine.

    # @property
    # def parameters(self) -> Dict[str, Any]:
    #     """Get the parameters dictionary from JSON."""
    #     return json.loads(self.parameters_json)
    # 
    # @parameters.setter
    # def parameters(self, value: Dict[str, Any]):
    #     """Set the parameters dictionary as JSON."""
    #     self.parameters_json = json.dumps(value)
    
    def to_edsl_object(self):
        """Convert this ORM model to a CacheEntry domain object."""
        entry = CacheEntry(
            model=self.model,
            parameters=self.parameters, # Directly use the dict from JSON type
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt,
            output=self.output,
            iteration=self.iteration,
            timestamp=int(self.timestamp.timestamp()) if self.timestamp else None,
            service=self.service,
            validated=self.validated
        )
        entry._orm_id = self.id
        return entry
    
    @classmethod
    def from_edsl_object(cls, entry: CacheEntry):
        """Create an ORM model from an EDSL CacheEntry domain object."""
        return cls(
            key=entry.key,
            model=entry.model,
            parameters=entry.parameters, # Pass the dict directly
            system_prompt=entry.system_prompt,
            user_prompt=entry.user_prompt,
            output=entry.output,
            iteration=entry.iteration,
            timestamp=datetime.fromtimestamp(entry.timestamp, tz=timezone.utc) if entry.timestamp is not None else None,
            service=entry.service,
            validated=entry.validated,
        )


class CacheMappedObject(Base, UUIDTrackable):
    """SQLAlchemy ORM model for Cache."""
    edsl_class = Cache
    __tablename__ = "cache"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    edsl_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    edsl_class_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    entries: Mapped[List[CacheEntryMappedObject]] = relationship(
        "CacheEntryMappedObject", 
        back_populates="cache", 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<CacheMappedObject(id={self.id}, entries_count={len(self.entries) if self.entries else 0})>"
    
    def to_edsl_object(self):
        data_for_from_dict = {}
        for entry_orm in self.entries:
            edsl_entry_object = entry_orm.to_edsl_object() 
            data_for_from_dict[entry_orm.key] = edsl_entry_object.to_dict()
            
        if self.edsl_version:
            data_for_from_dict["edsl_version"] = self.edsl_version
        if self.edsl_class_name:
            data_for_from_dict["edsl_class_name"] = self.edsl_class_name
            
        cache_edsl = Cache.from_dict(data_for_from_dict)
        cache_edsl._orm_id = self.id
        return cache_edsl
    
    @classmethod
    def from_edsl_object(cls, cache_edsl: Cache):
        """Create an ORM model from an EDSL Cache domain object.
        
        This method performs a pure Python object transformation.
        It does not interact with the database session.
        """
        # Assuming edsl.caching.Cache is imported as Cache
        # Assuming CacheEntryMappedObject.from_edsl_object is already corrected.
        
        cache_as_dict = cache_edsl.to_dict(add_edsl_version=True)
        edsl_version = cache_as_dict.get("edsl_version")
        edsl_class_name = cache_as_dict.get("edsl_class_name")

        parent_orm_cache = cls(
            edsl_version=edsl_version,
            edsl_class_name=edsl_class_name,
        )

        if hasattr(cache_edsl, 'data') and cache_edsl.data:
            child_orm_entries = [
                CacheEntryMappedObject.from_edsl_object(edsl_entry_data)
                for edsl_entry_data in cache_edsl.data.values()
            ]
            parent_orm_cache.entries = child_orm_entries
        else:
            parent_orm_cache.entries = [] 
            
        return parent_orm_cache


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
    edsl_class = None

    __tablename__ = "cache_data"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    @classmethod
    def from_edsl_object(cls, cache_edsl: Cache):
        """Create an ORM model from an EDSL Cache domain object.
        
        This method performs a pure Python object transformation.
        It does not interact with the database session.
        """
        # Assuming edsl.caching.Cache is imported as Cache
        # Assuming CacheEntryMappedObject.from_edsl_object is already corrected.
        
        cache_as_dict = cache_edsl.to_dict(add_edsl_version=True)
        edsl_version = cache_as_dict.get("edsl_version")
        edsl_class_name = cache_as_dict.get("edsl_class_name")

        parent_orm_cache = cls(
            edsl_version=edsl_version,
            edsl_class_name=edsl_class_name,
            # entries attribute will be populated by assignment after instantiation.
        )

        if hasattr(cache_edsl, 'data') and cache_edsl.data:
            child_orm_entries = [
                CacheEntryMappedObject.from_edsl_object(edsl_entry_data)
                for edsl_entry_data in cache_edsl.data.values()
            ]
            parent_orm_cache.entries = child_orm_entries
        else:
            parent_orm_cache.entries = [] # Ensure entries is an empty list if no data
            
        return parent_orm_cache


if __name__ == "__main__":
    from edsl import Cache 
    from edsl.caching.cache_entry import CacheEntry # Ensure CacheEntry is imported for type hints
    from sqlalchemy.orm import Session 

    # Get the EDSL Cache object (example or pulled)
    cache_edsl_object = Cache.example()
    # cache_edsl_object = Cache.pull("e56306e6-bb9c-40b9-b03b-c55c0fba79e6")

    # --- Conversion Layer (Pure Python) ---
    # Use the refactored from_edsl_object method which performs pure object translation
    orm_cache_object = CacheMappedObject.from_edsl_object(cache_edsl_object)

    # --- Persistence Layer (Session/DB Interaction) ---
    from .sql_base import create_test_session
    db_session: Session
    db_session, _, _ = create_test_session()

    # Add the fully constructed ORM object graph to the session
    db_session.add(orm_cache_object)
    
    # Commit the session to persist the graph; SQLAlchemy handles FKs.
    db_session.commit()

    print("--- Persisted Cache ORM Object ---")
    print(orm_cache_object)
    if orm_cache_object.id is not None:
        print(f"Cache ORM ID after commit: {orm_cache_object.id}")
        if orm_cache_object.entries:
            print(f"Number of entries: {len(orm_cache_object.entries)}")
            print(f"First entry ORM ID: {orm_cache_object.entries[0].id}")
            print(f"First entry cache_id (FK): {orm_cache_object.entries[0].cache_id}")
        else:
            print("No entries in this cache.")
    else:
        print("Cache ORM object ID is None after commit. Check session flush/commit.")

    # Example of querying back (optional)
    if orm_cache_object.id is not None:
        retrieved_cache = db_session.get(CacheMappedObject, orm_cache_object.id)
        print("\n--- Retrieved Cache ORM Object (for verification) ---")
        print(retrieved_cache)
        if retrieved_cache and retrieved_cache.entries:
            print(f"Retrieved first entry cache_id: {retrieved_cache.entries[0].cache_id}")

    # working with JSON (comment from original file)
    #  SELECT output -> '$.content[0].text' FROM cache_entry;