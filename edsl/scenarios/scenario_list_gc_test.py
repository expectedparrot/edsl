"""
Test script to investigate garbage collection behavior with ScenarioList.
"""

import gc
import os
import psutil
import pickle
import tracemalloc
from typing import Dict, List, Any

def get_memory_usage() -> float:
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / (1024 * 1024)
    return memory_mb

def display_memory_usage(label: str) -> float:
    """Display and return current memory usage."""
    mem = get_memory_usage()
    print(f"{label}: {mem:.2f} MB")
    return mem

def test_pickle_gc() -> None:
    """Test if pickle.dumps objects are properly garbage collected."""
    display_memory_usage("Initial memory")
    
    # Force garbage collection
    gc.collect()
    start_mem = display_memory_usage("Memory after initial gc")
    
    # Test with a string of 1MB
    text = "x" * (1024 * 1024)  # 1MB string
    display_memory_usage("Memory after creating 1MB string")
    
    # Create 100 large dictionaries
    data_list: List[Dict[str, Any]] = []
    for i in range(100):
        data = {"id": i, "text": text, "value": i * 100}
        data_list.append(data)
    
    gc.collect()
    display_memory_usage("Memory after creating 100 dicts with shared string")
    
    # Now pickle each object
    print("\nPickling objects one at a time:")
    for i, data in enumerate(data_list):
        # Pickle the object and immediately delete the reference
        serialized = pickle.dumps(data)
        # Explicitly delete to help garbage collection
        del serialized
        
        # Every 10 items, force garbage collection and check memory
        if i % 10 == 9:
            gc.collect()
            display_memory_usage(f"Memory after pickling {i+1} objects and gc")
    
    # Final garbage collection
    gc.collect()
    end_mem = display_memory_usage("Memory after final gc")
    
    print(f"\nTotal memory increase: {end_mem - start_mem:.2f} MB")
    
    # Now test with tracemalloc to see exactly where memory is allocated
    print("\nDetailed memory tracing with tracemalloc:")
    tracemalloc.start()
    
    # Get snapshot before
    data = {"id": 1, "text": "x" * (1024 * 1024), "value": 100}
    snapshot1 = tracemalloc.take_snapshot()
    
    # Do 10 pickling operations
    for i in range(10):
        serialized = pickle.dumps(data)
        del serialized
    
    # Get snapshot after
    snapshot2 = tracemalloc.take_snapshot()
    
    # Compare and show top differences
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    print("\nTop 10 memory allocations:")
    for stat in top_stats[:10]:
        print(f"{stat.traceback.format()[0]} - {stat.size_diff / 1024:.2f} KB")
    
    tracemalloc.stop()

def test_sqlite_insert() -> None:
    """Test SQLite insertion memory behavior."""
    import sqlite3
    import tempfile
    
    display_memory_usage("Initial memory")
    
    # Force garbage collection
    gc.collect()
    start_mem = display_memory_usage("Memory after initial gc")
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS items (idx INTEGER, value BLOB)")
    
    # Create a large string and dictionary
    text = "x" * (1024 * 1024)  # 1MB string
    display_memory_usage("Memory after creating 1MB string")
    
    # Insert 100 large pickled objects
    print("\nInserting objects one at a time:")
    for i in range(100):
        data = {"id": i, "text": text, "value": i * 100}
        serialized = pickle.dumps(data)
        
        # Insert into database
        conn.execute("INSERT INTO items (idx, value) VALUES (?, ?)", (i, serialized))
        
        # Explicitly delete serialized data
        del serialized
        
        # Every 10 items, force garbage collection and check memory
        if i % 10 == 9:
            conn.commit()  # Commit to ensure SQLite releases memory
            gc.collect()
            display_memory_usage(f"Memory after inserting {i+1} objects and gc")
    
    # Close connection and clean up
    conn.close()
    os.unlink(db_path)
    
    # Final garbage collection
    gc.collect()
    end_mem = display_memory_usage("Memory after final gc")
    
    print(f"\nTotal memory increase: {end_mem - start_mem:.2f} MB")

if __name__ == "__main__":
    print("===== Testing pickle garbage collection =====")
    test_pickle_gc()
    
    print("\n\n===== Testing SQLite insertion memory behavior =====")
    test_sqlite_insert()