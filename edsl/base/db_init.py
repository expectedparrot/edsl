"""Database initialization utilities for EDSL.

This module provides functions for initializing the database schema
for all EDSL domain objects that implement ORM models.
"""

import importlib
import logging
from typing import List, Optional, Tuple
import tempfile
import os

from sqlalchemy.orm import sessionmaker, Session

from .db_manager import DBManager, get_db_manager

# List of modules with ORM implementations
ORM_MODULES = [
    "edsl.jobs.orm",
    "edsl.scenarios.orm",  # Assuming this exists
    "edsl.agents.orm",     # Assuming this exists
    "edsl.language_models.orm",  # Assuming this exists
    "edsl.results.orm",    # Result and Results ORM
    "edsl.caching.orm",     # Cache and CacheEntry ORM
    "edsl.surveys.orm",
    "edsl.questions.orm"
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
            logging.debug(f"Successfully loaded ORM module: {module_name}")
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
        loaded_modules = load_all_orm_modules()
        if not loaded_modules:
            logging.error("No ORM modules could be loaded for schema initialization.")
            return False
        
        db_manager = get_db_manager(connection_string)
        db_manager.initialize_tables()
        
        tables = db_manager.list_tables()
        logging.info(f"Initialized database schema with {len(tables)} tables: {tables}")
        
        return True
    except Exception as e:
        logging.error(f"Error initializing database schema: {e}", exc_info=True)
        return False


def create_test_session() -> Tuple[Session, DBManager, str]:
    """ 
    Creates and returns an SQLAlchemy session connected to a new, 
    temporary file-based SQLite database with the EDSL schema initialized.

    Returns:
        A tuple containing:
            - session: The SQLAlchemy Session object.
            - db_manager: The DBManager instance configured for the temporary database.
            - temp_db_file_path: The path to the temporary database file.
    """
    # 1. Create a temporary file for the SQLite database
    # Ensure the file is not deleted automatically on close, so we can manage its lifecycle.
    tmp_file_handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    temp_db_file_path = tmp_file_handle.name
    tmp_file_handle.close() # Close the handle, but the file remains
    
    db_connection_string = f"sqlite:///{temp_db_file_path}"
    logging.debug(f"create_test_session: Using temporary SQLite database: {db_connection_string}")

    # 2. Ensure all ORM models are loaded
    load_all_orm_modules()
    logging.debug("create_test_session: ORM modules loaded.")

    # 3. Get a DBManager instance connected to the temporary file-based DB
    # Pass the specific connection string to ensure a fresh DBManager if needed for this path
    db_manager = get_db_manager(db_connection_string) 
    logging.debug(f"create_test_session: DB Manager obtained. Engine: {db_manager.engine}")

    # 4. Create all tables defined by the loaded ORM models
    db_manager.initialize_tables()
    logging.debug("create_test_session: Tables initialized in temporary DB.")

    # 5. Create and return a new session and the temp file path
    # The session factory should be available on the db_manager instance
    if hasattr(db_manager, 'session_factory'):
        session = db_manager.session_factory()
    else:
        # Fallback if session_factory isn't on db_manager (e.g. older version or direct engine use)
        # This branch might indicate DBManager structure needs confirming if hit unexpectedly.
        logging.warning("create_test_session: db_manager.session_factory not found, creating session manually from engine.")
        SessionLocal_manual = sessionmaker(autocommit=False, autoflush=False, bind=db_manager.engine)
        session = SessionLocal_manual()
    
    logging.debug(f"create_test_session: Session created for {temp_db_file_path}")
    return session, db_manager, temp_db_file_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logging.info("Running DB initialization script using create_test_session.")

    session: Optional[Session] = None
    db_manager_instance: Optional[DBManager] = None
    temp_db_path: Optional[str] = None

    try:
        session, db_manager_instance, temp_db_path = create_test_session()
        
        logging.info(f"Session and temp DB created: {temp_db_path}")

        # List and print tables using the returned db_manager
        if db_manager_instance:
            tables = db_manager_instance.list_tables()
            logging.info(f"Tables in the database ({temp_db_path}): {tables}")
            print(f"Database tables found in {temp_db_path}: {tables}")
        else:
            logging.error("DBManager instance not returned from create_test_session.")

    except Exception as e:
        logging.error(f"An error occurred in __main__: {e}", exc_info=True)
    finally:
        if session is not None:
            logging.info("Closing session.")
            session.close()
        
        if temp_db_path and os.path.exists(temp_db_path):
            logging.info(f"Deleting temporary database file: {temp_db_path}")
            os.remove(temp_db_path)
        elif temp_db_path:
            logging.warning(f"Temporary database file {temp_db_path} was expected but not found for deletion.")
        else:
            logging.debug("No temporary database file path recorded to delete.")