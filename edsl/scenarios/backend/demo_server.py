# demo_server.py
"""
Simple demo of push/pull with the FastAPI server.

Usage:
  1. In one terminal: uvicorn backend.server:app --port 8000
  2. In another terminal: python -m backend.demo_server
"""
import requests

SERVER = "http://localhost:8000"


def main():
    print("=" * 50)
    print("Push/Pull Demo")
    print("=" * 50)
    
    # 1. Create a list on the server
    print("\n1. Create list on server:")
    resp = requests.post(f"{SERVER}/lists", json={
        "scenarios": [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
    })
    server_list = resp.json()
    list_id = server_list["list_id"]
    print(f"   Created list_id={list_id}, version={server_list['version']}")
    
    # 2. Check server state
    print("\n2. Server state:")
    resp = requests.get(f"{SERVER}/lists/{list_id}")
    state = resp.json()
    for s in state["scenarios"]:
        print(f"   {s}")
    
    # 3. Simulate local changes (we'll use the server's push endpoint directly)
    print("\n3. Simulating local changes and pushing...")
    
    # Create a local ScenarioList, make changes, get delta
    from .scenario_list import ScenarioList, Backend
    
    # Start with same data as server
    local = ScenarioList([
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ], backend=Backend.MEMORY)
    
    base_version = local.version  # 2
    print(f"   Local at version {base_version}")
    
    # Make local changes
    local.append({"name": "Carol", "age": 35})
    local.rename("name", "first_name")
    print(f"   After changes: version {local.version}")
    
    # Get delta and push
    delta = local.get_delta(base_version)
    print(f"   Delta: {delta['from_version']} -> {delta['to_version']}")
    
    resp = requests.post(f"{SERVER}/lists/{list_id}/push", json=delta)
    result = resp.json()
    print(f"   Push result: {result['status']}")
    
    # 4. Check server state after push
    print("\n4. Server state after push:")
    resp = requests.get(f"{SERVER}/lists/{list_id}")
    state = resp.json()
    print(f"   Version: {state['version']}")
    for s in state["scenarios"]:
        print(f"   {s}")
    
    # 5. Another client pulls
    print("\n5. Another client pulls from version 0:")
    resp = requests.get(f"{SERVER}/lists/{list_id}/pull", params={"from_version": 0})
    pull_result = resp.json()
    print(f"   Status: {pull_result['status']}")
    print(f"   Server version: {pull_result['version']}")
    if pull_result.get("delta"):
        d = pull_result["delta"]
        print(f"   Delta: {d['from_version']} -> {d['to_version']}")
        print(f"   Scenarios in delta: {len(d['scenarios'])}")
        print(f"   History entries: {len(d['history'])}")
    
    # 6. Pull into a fresh local list
    print("\n6. Create fresh local list and apply delta:")
    fresh_local = ScenarioList(backend=Backend.MEMORY)
    if pull_result.get("delta"):
        fresh_local.apply_delta(pull_result["delta"])
    print(f"   Fresh local version: {fresh_local.version}")
    print(f"   Fresh local data:")
    for s in fresh_local.get_all_scenarios():
        print(f"   {s}")
    
    # 7. Conflict demo
    print("\n7. Conflict demo - push from stale version:")
    stale_delta = {
        "from_version": 2,  # Server is now at 4
        "to_version": 3,
        "scenarios": [{"position": 2, "digest": "abc", "version_added": 3, "payload": {"name": "Dan"}}],
        "meta_changes": [],
        "overrides": [],
        "history": [{"version": 3, "method_name": "append", "args": [{"name": "Dan"}], "kwargs": {}}],
    }
    resp = requests.post(f"{SERVER}/lists/{list_id}/push", json=stale_delta)
    result = resp.json()
    print(f"   Push from v2 result: {result['status']}")
    print(f"   Message: {result.get('message', '')}")
    
    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()

