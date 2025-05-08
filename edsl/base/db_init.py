"""Database initialization utilities for EDSL.

This module provides functions for initializing the database schema
for all EDSL domain objects that implement ORM models.
"""

import importlib
import logging
from typing import List, Optional

from .db_manager import get_db_manager

# List of modules with ORM implementations
ORM_MODULES = [
    "edsl.jobs.orm",
    "edsl.scenarios.orm",  # Assuming this exists
    "edsl.agents.orm",     # Assuming this exists
    "edsl.language_models.orm",  # Assuming this exists
    "edsl.results.orm",    # Result and Results ORM
    "edsl.caching.orm"     # Cache and CacheEntry ORM
]


def load_all_orm_modules() -> List[str]:
    """Import all ORM modules to register their models.
    
    Returns:
        List of successfully loaded module names
    """
    loaded_modules = []
    
    for module_name in ORM_MODULES:
        try:
            importlib.import_module(module_name)
            loaded_modules.append(module_name)
            logging.info(f"Loaded ORM module: {module_name}")
        except ImportError as e:
            logging.warning(f"Could not import ORM module {module_name}: {e}")
    
    return loaded_modules


def initialize_db_schema(connection_string: Optional[str] = None) -> bool:
    """Initialize database schema for all EDSL objects.
    
    This function loads all ORM modules and creates tables for their models.
    
    Args:
        connection_string: Optional database connection string
            
    Returns:
        True if initialization was successful, False otherwise
    """
    try:
        # Load all ORM modules to register their models
        loaded_modules = load_all_orm_modules()
        
        if not loaded_modules:
            logging.error("No ORM modules could be loaded")
            return False
        
        # Get the DB manager and initialize tables
        db_manager = get_db_manager(connection_string)
        db_manager.initialize_tables()
        
        tables = db_manager.list_tables()
        logging.info(f"Initialized database schema with {len(tables)} tables")
        
        return True
    except Exception as e:
        logging.error(f"Error initializing database schema: {e}")
        return False


if __name__ == "__main__":
    """Run this script directly to initialize the database schema."""
    import argparse
    import sys
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Initialize EDSL database schema')
    parser.add_argument('--connection', 
                       help='Database connection string (defaults to EDSL_DB_URI env var)')
    
    args = parser.parse_args()
    
    # Initialize the schema
    success = initialize_db_schema(args.connection)
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)