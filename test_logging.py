"""
Test script to demonstrate the EDSL logging system.
"""

import logging
from edsl import logger
from edsl.base import BaseException


def test_logger_levels():
    """Test different logging levels."""
    print("Testing different logging levels...")
    
    # Set to debug to see all messages
    logger.set_level(logging.DEBUG)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # Reset to default level
    logger.set_level(logging.INFO)


def test_exception_logging():
    """Test exception logging."""
    print("\nTesting exception logging...")
    
    try:
        # Raise a custom exception that will be logged
        raise BaseException("This is a test exception", log_level="warning")
    except Exception as e:
        print(f"Caught exception: {e}")
    
    try:
        # Raise a custom exception with a different log level
        raise BaseException("This is a critical test exception", log_level="critical")
    except Exception as e:
        print(f"Caught exception: {e}")


def test_module_logger():
    """Test getting a module-specific logger."""
    print("\nTesting module-specific logger...")
    
    # Get a logger for this module
    module_logger = logger.get_logger(__name__)
    
    module_logger.info("This message is from the module-specific logger")
    module_logger.warning("This is a module-specific warning")
    

if __name__ == "__main__":
    print("EDSL Logging Test\n")
    
    # Show current log level
    print(f"Default log level: INFO\n")
    
    # Run tests
    test_logger_levels()
    test_exception_logging()
    test_module_logger()
    
    print("\nLogging test complete. Check the console output and ~/.edsl/logs/edsl.log")