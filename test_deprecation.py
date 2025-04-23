#!/usr/bin/env python
"""Test the new ScenarioList.from_source method."""

import os
import tempfile
from edsl.scenarios import ScenarioList

# Create a test file
with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp:
    temp.write(b"name,age\nAlice,30\nBob,25\n")
    temp_path = temp.name

try:
    # Use the specific method
    print("Testing ScenarioList.from_csv:")
    sl_old = ScenarioList.from_csv(temp_path)
    
    # Use the new generic method
    print("\nTesting ScenarioList.from_source:")
    sl_new = ScenarioList.from_source("csv", temp_path)
    
    # Compare results
    print(f"\nBoth methods return the same result: {sl_old == sl_new}")
    
    # Print the content
    print("\nContent of the ScenarioList:")
    for scenario in sl_new:
        print(scenario)
    
finally:
    # Clean up
    os.unlink(temp_path)