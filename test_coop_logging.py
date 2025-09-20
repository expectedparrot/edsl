#!/usr/bin/env python3
"""
Test script to demonstrate Coop logging functionality.

This script shows how the Coop class now logs server requests and exceptions
at the INFO and ERROR levels respectively.
"""

import logging
import sys
import os

# Add the edsl package to the path so we can import it
sys.path.insert(0, '/Users/johnhorton/tools/ep/edsl')

from edsl.logger import set_level, get_logger
from edsl.coop import Coop

def test_coop_logging():
    """Test the Coop logging functionality"""
    
    # Set up logging to INFO level so we can see the server request logs
    set_level(logging.INFO)
    
    # Create a console handler so we can see the logs in the terminal
    logger = get_logger(__name__)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Add handler to the root EDSL logger
    edsl_logger = logging.getLogger("edsl")
    edsl_logger.addHandler(console_handler)
    
    print("Testing Coop logging functionality...")
    print("=" * 50)
    
    # Initialize Coop (this might make some server requests)
    try:
        coop = Coop()
        print("\n1. Testing a successful API call (if we have valid credentials):")
        
        # Try to get the balance (should log the request)
        try:
            balance = coop.get_balance()
            print(f"✅ Successfully retrieved balance: {balance}")
        except Exception as e:
            print(f"❌ Expected error (likely no valid API key): {e}")
            
        print("\n2. Testing an invalid endpoint (should log an error):")
        
        # Try to call a non-existent endpoint to trigger error logging
        try:
            response = coop._send_server_request(
                uri="api/v0/nonexistent-endpoint",
                method="GET"
            )
        except Exception as e:
            print(f"❌ Expected error from invalid endpoint: {e}")
            
    except Exception as e:
        print(f"Error initializing Coop: {e}")
    
    print("\n" + "=" * 50)
    print("Logging test completed!")
    print("Check the terminal output above for INFO and ERROR level logs.")
    print("Logs are also written to ~/.edsl/logs/edsl.log")

if __name__ == "__main__":
    test_coop_logging()
