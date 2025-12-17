# demo.py
"""
Demo of ScenarioList with versioning and digest-based addressing.

Run with: python -m backend.demo
"""
import sqlite3

from .plan import (build_append_plan, build_rename_plan, build_drop_key_plan, build_add_values_plan)
from .memory_backend import MemoryState
from .sqlite_backend import SQLiteState

from typing import List, Any, Dict
from .scenario_list import ScenarioList, Backend


def demo_versioning():
    """Demonstrate versioning and time travel."""
    print("=" * 60)
    print("DEMO: Versioning and Time Travel")
    print("=" * 60)
    
    data = [
        {"persona": "Alice", "likes": "sailing"},
        {"persona": "Bob", "likes": "chickens"},
    ]
    scenario_list = ScenarioList(data, backend=Backend.SQLITE)
    print(f"\nInitial (version {scenario_list.version}):")
    print(scenario_list)

    print("\nAfter rename (persona -> first_name):")
    scenario_list.rename("persona", "first_name")
    print(f"Version: {scenario_list.version}")
    print(scenario_list)

    print("\nAfter drop (likes):")
    scenario_list.drop_key("likes")
    print(f"Version: {scenario_list.version}")
    print(scenario_list)

    print("\nAfter add_values (likes):")
    scenario_list.add_values("likes", ["sailing", "chickens"])
    print(f"Version: {scenario_list.version}")
    print(scenario_list)

    print("\n--- Version History ---")
    for ver, method, args, kwargs in scenario_list.history:
        print(f"  v{ver}: {method}({args})")

    print("\n--- Time Travel ---")
    for v in range(scenario_list.version + 1):
        print(f"at_version({v}): {scenario_list.at_version(v)}")

    print("\n--- Convert view to new list ---")
    v2_view = scenario_list.at_version(2)
    v2_list = v2_view.to_list(backend_type=Backend.MEMORY)
    print(f"New list from v2: {v2_list}")
    print(f"New list version: {v2_list.version}")
    
    return scenario_list


def demo_delta_sync():
    """Demonstrate delta-based synchronization between two lists."""
    print("\n" + "=" * 60)
    print("DEMO: Delta Synchronization")
    print("=" * 60)
    
    # Create "remote" list with initial data
    print("\n1. Create 'remote' list with initial data:")
    remote = ScenarioList([
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ], backend=Backend.MEMORY)
    print(f"   Remote: {remote} (version {remote.version})")
    
    # Create "local" list by pulling current state
    print("\n2. Create 'local' list synced at version 2:")
    local = ScenarioList([
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ], backend=Backend.MEMORY)
    print(f"   Local: {local} (version {local.version})")
    synced_version = local.version
    
    # Make changes on local
    print("\n3. Make local changes:")
    local.append({"name": "Carol", "age": 35})
    local.rename("name", "first_name")
    print(f"   Local after changes: {local} (version {local.version})")
    
    # Get delta from local
    print("\n4. Get delta from local (changes since version 2):")
    delta = local.get_delta(synced_version)
    print(f"   Delta: {len(delta['scenarios'])} scenarios, {len(delta['meta_changes'])} meta changes, {len(delta['history'])} history entries")
    print(f"   From version {delta['from_version']} to {delta['to_version']}")
    
    # Apply delta to remote
    print("\n5. Apply delta to remote:")
    remote.apply_delta(delta)
    print(f"   Remote after sync: {remote} (version {remote.version})")
    
    # Verify they match
    print("\n6. Verify local and remote match:")
    print(f"   Local:  {local.get_all_scenarios()}")
    print(f"   Remote: {remote.get_all_scenarios()}")
    print(f"   Match: {local.get_all_scenarios() == remote.get_all_scenarios()}")


def demo_digest_stability():
    """Demonstrate that digests provide stable IDs across position changes."""
    print("\n" + "=" * 60)
    print("DEMO: Digest-based Stable IDs")
    print("=" * 60)
    
    list1 = ScenarioList([
        {"x": 1},
        {"x": 2},
        {"x": 3},
    ], backend=Backend.MEMORY)
    
    print("\n1. Initial list with digests:")
    digests = list1.backend.get_all_digests()
    for i, (scenario, digest) in enumerate(zip(list1.get_all_scenarios(), digests)):
        print(f"   Position {i}: {scenario} -> digest: {digest[:16]}...")
    
    print("\n2. Add values by position (internally mapped to digest):")
    list1.add_values("label", ["first", "second", "third"])
    print(f"   After add_values: {list1}")
    
    print("\n3. Verify overrides are stored by digest (stable across syncs):")
    for i, digest in enumerate(digests):
        override = list1.backend.get_override_by_digest(digest)
        print(f"   Digest {digest[:16]}... -> override: {override}")


if __name__ == "__main__":
    demo_versioning()
    demo_delta_sync()
    demo_digest_stability()
    
    print("\n" + "=" * 60)
    print("To test the FastAPI server:")
    print("  1. Run: uvicorn backend.server:app --reload")
    print("  2. Visit: http://localhost:8000/docs")
    print("=" * 60)
