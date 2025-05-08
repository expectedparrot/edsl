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
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, backref

# Create base class for declarative models
Base = declarative_base()

# Import base exception
from ..base.exceptions import BaseException


class CacheOrmException(BaseException):
    """Exception raised for errors in the Cache ORM operations."""
    pass


class SQLCacheEntry(Base):
    """SQLAlchemy ORM model for CacheEntry."""
    
    __tablename__ = "cache_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_id = Column(Integer, ForeignKey("caches.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(255), nullable=False, index=True)
    model = Column(String(255), nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_prompt = Column(Text, nullable=False)
    output = Column(Text, nullable=False)
    iteration = Column(Integer, nullable=False, default=0)
    timestamp = Column(Integer, nullable=False)
    service = Column(String(255), nullable=True)
    validated = Column(Boolean, default=False)
    
    # Store parameters as serialized JSON
    parameters_json = Column(Text, nullable=False)
    
    # Relationship to parent Cache
    cache = relationship("SQLCache", back_populates="entries")
    
    def __repr__(self) -> str:
        """Return string representation of the CacheEntry."""
        return f"<SQLCacheEntry(id={self.id}, key='{self.key}')>"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the parameters dictionary from JSON."""
        return json.loads(self.parameters_json)
    
    @parameters.setter
    def parameters(self, value: Dict[str, Any]):
        """Set the parameters dictionary as JSON."""
        self.parameters_json = json.dumps(value)
    
    def to_cache_entry(self):
        """Convert this ORM model to a CacheEntry domain object."""
        # Import here to avoid circular imports
        from .cache_entry import CacheEntry
        
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
    def from_cache_entry(cls, entry, cache_id: int):
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


class SQLCache(Base):
    """SQLAlchemy ORM model for Cache."""
    
    __tablename__ = "caches"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    filename = Column(String(255), nullable=True)
    immediate_write = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    entries = relationship("SQLCacheEntry", back_populates="cache", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """Return string representation of the Cache."""
        return f"<SQLCache(id={self.id}, entries_count={len(self.entries) if self.entries else 0})>"
    
    def to_cache(self):
        """Convert this ORM model to a Cache domain object."""
        # Import here to avoid circular imports
        from .cache import Cache
        
        # Convert all entries to a dictionary for the cache
        data = {}
        for entry in self.entries:
            cache_entry = entry.to_cache_entry()
            data[entry.key] = cache_entry
        
        # Create a new Cache with the data
        cache = Cache(
            data=data,
            filename=self.filename,
            immediate_write=self.immediate_write
        )
        
        # Store the ORM ID for future reference
        cache._orm_id = self.id
        
        return cache
    
    @classmethod
    def from_cache(cls, cache, session: Optional[Session] = None):
        """Create an ORM model from a Cache domain object."""
        # Create the base record
        orm_cache = cls(
            filename=cache.filename,
            immediate_write=cache.immediate_write
        )
        
        # Add to session to get ID if provided
        if session:
            session.add(orm_cache)
            session.flush()
            
            # Now add all entries
            for key, entry in cache.data.items():
                orm_entry = SQLCacheEntry.from_cache_entry(entry, orm_cache.id)
                session.add(orm_entry)
        
        return orm_cache


# Data table for SQLiteDict and basic key-value storage
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


# CRUD Operations

def save_cache(session: Session, cache) -> SQLCache:
    """Save a Cache to the database."""
    # Check if the cache already exists
    if hasattr(cache, '_orm_id') and cache._orm_id:
        # Try to update the existing cache
        update_success = update_cache(session, cache._orm_id, cache)
        if update_success:
            # Get the updated cache
            cache_orm = session.get(SQLCache, cache._orm_id)
            return cache_orm
    
    # Create new cache (or recreate if update failed)
    cache_orm = SQLCache.from_cache(cache, session)
    
    # Store the ORM ID in the domain object for future reference
    cache._orm_id = cache_orm.id
    
    return cache_orm


def update_cache(session: Session, cache_id: int, cache) -> bool:
    """Update an existing cache in the database."""
    cache_orm = session.get(SQLCache, cache_id)
    if not cache_orm:
        return False
    
    # Update basic attributes
    cache_orm.filename = cache.filename
    cache_orm.immediate_write = cache.immediate_write
    
    # Get current entries in the database
    existing_keys = {entry.key: entry for entry in cache_orm.entries}
    
    # Determine entries to add, update, or delete
    current_keys = set(cache.data.keys())
    db_keys = set(existing_keys.keys())
    
    # Keys to add
    keys_to_add = current_keys - db_keys
    
    # Keys to update (those in both sets)
    keys_to_update = current_keys.intersection(db_keys)
    
    # Keys to delete
    keys_to_delete = db_keys - current_keys
    
    # Delete removed entries
    for key in keys_to_delete:
        session.delete(existing_keys[key])
    
    # Update existing entries
    for key in keys_to_update:
        entry = cache.data[key]
        orm_entry = existing_keys[key]
        
        # Update all fields
        orm_entry.model = entry.model
        orm_entry.parameters = entry.parameters
        orm_entry.system_prompt = entry.system_prompt
        orm_entry.user_prompt = entry.user_prompt
        orm_entry.output = entry.output
        orm_entry.iteration = entry.iteration
        orm_entry.timestamp = entry.timestamp
        orm_entry.service = entry.service
        orm_entry.validated = entry.validated
    
    # Add new entries
    for key in keys_to_add:
        entry = cache.data[key]
        orm_entry = SQLCacheEntry.from_cache_entry(entry, cache_id)
        session.add(orm_entry)
    
    return True


def load_cache(session: Session, cache_id: int):
    """Load a Cache from the database by ID."""
    cache_orm = session.get(SQLCache, cache_id)
    if cache_orm:
        cache = cache_orm.to_cache()
        cache._orm_id = cache_orm.id
        return cache
    return None


def delete_cache(session: Session, cache_id: int) -> bool:
    """Delete a Cache from the database."""
    cache_orm = session.get(SQLCache, cache_id)
    if cache_orm:
        session.delete(cache_orm)
        return True
    return False


def list_caches(session: Session, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List caches in the database with pagination."""
    caches = session.query(SQLCache).order_by(SQLCache.created_at.desc()) \
        .limit(limit).offset(offset).all()
    return [{"id": c.id, "name": c.name, "created_at": c.created_at,
             "entries_count": len(c.entries)} for c in caches]


def print_sql_schema(engine):
    """Print the SQL schema for the cache-related tables."""
    from sqlalchemy.schema import CreateTable
    
    print("\n--- SQL Schema for Cache Tables ---")
    for table in [
        SQLCache.__table__,
        SQLCacheEntry.__table__,
        Data.__table__
    ]:
        print(f"\n-- Table: {table.name}")
        print(CreateTable(table).compile(engine))
    print("--- End of SQL Schema ---")
