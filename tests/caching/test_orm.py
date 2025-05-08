"""
Tests for the Cache ORM implementation.

This module tests the ORM functionality for persisting Cache objects
to a database, including serialization, deserialization, and CRUD operations.
"""

import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Import the ORM components first to avoid circular imports
from edsl.caching.orm import (
    Base,
    SQLCache,
    SQLCacheEntry,
    save_cache,
    load_cache,
    update_cache,
    delete_cache,
    list_caches
)

# Then import the domain classes
from edsl.caching.cache import Cache
from edsl.caching.cache_entry import CacheEntry


class TestCacheOrm(unittest.TestCase):
    """Test the Cache ORM implementation."""

    def setUp(self):
        """Set up a new database for each test."""
        # Create a new in-memory SQLite database for each test
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        """Clean up resources after each test."""
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_save_and_load_cache(self):
        """Test saving and loading a Cache with entries."""
        # Create a test Cache with entries
        cache = Cache.example()
        
        # Print cache info for debugging
        print("Original cache entries:", len(cache.data))
        
        # Save the cache
        cache_orm = save_cache(self.session, cache)
        self.session.commit()
        cache_id = cache_orm.id
        
        # Verify the cache has an ORM ID
        self.assertTrue(hasattr(cache, '_orm_id'))
        self.assertEqual(cache._orm_id, cache_id)
        
        # Print ORM entries for debugging
        print("Entries saved to ORM:", len(cache_orm.entries))
        for entry in cache_orm.entries:
            print(f"  {entry.key}: {entry.model}, prompt: '{entry.system_prompt[:20]}...'")

        # Load the cache
        loaded_cache = load_cache(self.session, cache_id)
        
        # Print loaded cache info for debugging
        print("Loaded cache entries:", len(loaded_cache.data))
        
        # Verify that cache attributes were loaded correctly
        self.assertEqual(loaded_cache.immediate_write, cache.immediate_write)
        self.assertEqual(loaded_cache.filename, cache.filename)
        
        # Verify that all entries were loaded correctly
        self.assertEqual(len(loaded_cache.data), len(cache.data))
        
        # Verify entry contents
        for key, entry in cache.data.items():
            self.assertIn(key, loaded_cache.data)
            loaded_entry = loaded_cache.data[key]
            self.assertEqual(loaded_entry.model, entry.model)
            self.assertEqual(loaded_entry.parameters, entry.parameters)
            self.assertEqual(loaded_entry.system_prompt, entry.system_prompt)
            self.assertEqual(loaded_entry.user_prompt, entry.user_prompt)
            self.assertEqual(loaded_entry.output, entry.output)
            self.assertEqual(loaded_entry.iteration, entry.iteration)
            self.assertEqual(loaded_entry.service, entry.service)
            self.assertEqual(loaded_entry.validated, entry.validated)

    def test_update_cache(self):
        """Test updating an existing Cache."""
        # Create and save an initial cache
        cache = Cache.example()
        cache_orm = save_cache(self.session, cache)
        self.session.commit()
        cache_id = cache_orm.id
        
        # Add a new entry to the cache
        new_entry = CacheEntry.example(True)  # Use randomize=True for a unique entry
        cache.data[new_entry.key] = new_entry
        
        # Update the cache
        update_success = update_cache(self.session, cache_id, cache)
        self.session.commit()
        
        # Verify update was successful
        self.assertTrue(update_success)
        
        # Load the cache again
        loaded_cache = load_cache(self.session, cache_id)
        
        # Verify the new entry was added
        self.assertEqual(len(loaded_cache.data), len(cache.data))
        self.assertIn(new_entry.key, loaded_cache.data)
        
        # Verify the entry contents
        loaded_entry = loaded_cache.data[new_entry.key]
        self.assertEqual(loaded_entry.model, new_entry.model)
        self.assertEqual(loaded_entry.system_prompt, new_entry.system_prompt)
        self.assertEqual(loaded_entry.output, new_entry.output)

    def test_delete_cache(self):
        """Test deleting a Cache."""
        # Create and save a cache
        cache = Cache.example()
        cache_orm = save_cache(self.session, cache)
        self.session.commit()
        cache_id = cache_orm.id
        
        # Delete the cache
        success = delete_cache(self.session, cache_id)
        self.session.commit()
        
        # Verify deletion was successful
        self.assertTrue(success)
        self.assertIsNone(load_cache(self.session, cache_id))
        
        # Verify no orphaned entries remain
        entry_count = self.session.query(SQLCacheEntry).count()
        self.assertEqual(entry_count, 0)

    def test_list_caches(self):
        """Test listing Caches with pagination."""
        # Create and save multiple caches
        for i in range(5):
            cache = Cache.example()
            save_cache(self.session, cache)
            
        self.session.commit()
        
        # List all caches
        caches = list_caches(self.session)
        self.assertEqual(len(caches), 5)
        
        # Test pagination
        caches_page1 = list_caches(self.session, limit=3, offset=0)
        caches_page2 = list_caches(self.session, limit=3, offset=3)
        self.assertEqual(len(caches_page1), 3)
        self.assertEqual(len(caches_page2), 2)


if __name__ == '__main__':
    unittest.main()