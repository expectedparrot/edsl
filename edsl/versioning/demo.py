#!/usr/bin/env python
"""
Demo script for the Object Versions Remote Server.

This script demonstrates:
1. Connecting to the server
2. Creating repositories
3. Applying events (single and batch)
4. Fetching data and history
5. Discovering available events

Prerequisites:
    Start the server first:
    $ python -m edsl.versioning.http_remote --port 8765 --memory

Usage:
    $ python -m edsl.versioning.demo
"""

import requests
import json
from pprint import pprint

BASE_URL = "http://localhost:8765"


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


def main():
    # Check server is running
    print_section("Checking Server Status")
    try:
        resp = requests.get(f"{BASE_URL}/api/status")
        resp.raise_for_status()
        print("Server status:")
        pprint(resp.json())
    except requests.ConnectionError:
        print("ERROR: Server not running!")
        print("Start it with: python -m edsl.versioning.http_remote --port 8765 --memory")
        return

    # List available events
    print_section("Available Events (first 10)")
    resp = requests.get(f"{BASE_URL}/api/events")
    events = resp.json()
    for i, (name, info) in enumerate(list(events.items())[:10]):
        print(f"  {name}: {info['doc'].strip()}")
    print(f"  ... and {len(events) - 10} more events")

    # Create a new repository
    print_section("Creating a New Repository")
    resp = requests.post(f"{BASE_URL}/api/repos", json={
        "alias": "demo/products",
        "description": "Demo product catalog"
    })
    repo_data = resp.json()
    repo_id = repo_data["repo_id"]
    print(f"Created repo: {repo_id}")
    print(f"Alias: {repo_data.get('alias')}")

    # Initialize with some data using replace_all_entries
    print_section("Initializing Data")
    initial_products = [
        {"id": 1, "name": "Laptop", "price": 999.99, "category": "Electronics"},
        {"id": 2, "name": "Headphones", "price": 149.99, "category": "Electronics"},
        {"id": 3, "name": "Coffee Mug", "price": 12.99, "category": "Kitchen"},
    ]

    # Add first product
    resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/events", json={
        "event_name": "append_row",
        "event_payload": {"row": initial_products[0]},
        "message": "First product",
        "author": "demo"
    })
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} - {resp.text}")
        return
    print(f"Added first product: {resp.json().get('commit_id', 'error')[:8]}...")

    # Batch add remaining products
    resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/batch", json={
        "events": [
            {"event_name": "append_row", "event_payload": {"row": p}}
            for p in initial_products[1:]
        ],
        "message": "Added more products",
        "author": "demo"
    })
    result = resp.json()
    print(f"Batch commit: {result.get('commit_id', 'error')[:8]}... ({result.get('events_applied')} events)")

    # Get current data
    print_section("Current Data")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/data")
    data = resp.json()
    print(f"Entries ({data['entries_count']}):")
    for entry in data["entries"]:
        print(f"  {entry}")

    # Apply some transformations
    print_section("Applying Transformations")

    # 1. Add a field to all entries
    print("\n1. Adding 'in_stock' field to all entries...")
    resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/events", json={
        "event_name": "add_field_to_all_entries",
        "event_payload": {"field": "in_stock", "value": True},
        "message": "Added stock status"
    })
    print(f"   Commit: {resp.json().get('commit_id', 'error')[:8]}...")

    # 2. Rename a field
    print("\n2. Renaming 'category' to 'department'...")
    resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/events", json={
        "event_name": "rename_fields",
        "event_payload": {"rename_map": [["category", "department"]]},
        "message": "Renamed category field"
    })
    print(f"   Commit: {resp.json().get('commit_id', 'error')[:8]}...")

    # 3. Update a specific row
    print("\n3. Updating Laptop price...")
    resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/events", json={
        "event_name": "update_row",
        "event_payload": {
            "index": 0,
            "row": {"id": 1, "name": "Laptop Pro", "price": 1299.99, "department": "Electronics", "in_stock": True}
        },
        "message": "Updated laptop"
    })
    print(f"   Commit: {resp.json().get('commit_id', 'error')[:8]}...")

    # 4. Add a new product
    print("\n4. Adding a new product...")
    resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/events", json={
        "event_name": "append_row",
        "event_payload": {"row": {"id": 4, "name": "Keyboard", "price": 79.99, "department": "Electronics", "in_stock": False}},
        "message": "Added keyboard"
    })
    print(f"   Commit: {resp.json().get('commit_id', 'error')[:8]}...")

    # Get updated data
    print_section("Updated Data")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/data")
    data = resp.json()
    print(f"Entries ({data['entries_count']}):")
    for entry in data["entries"]:
        print(f"  {entry}")

    # View commit history
    print_section("Commit History")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/history")
    history = resp.json()
    print(f"Branch: {history['branch']}")
    print("Commits:")
    for commit in history["commits"]:
        print(f"  {commit['commit_id'][:8]} | {commit['event_name']:25} | {commit['message']}")

    # Demonstrate batch operations
    print_section("Batch Operations")
    print("Applying multiple changes in a single commit...")
    resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/batch", json={
        "events": [
            {"event_name": "remove_rows", "event_payload": {"indices": [2]}},  # Remove Coffee Mug
            {"event_name": "append_row", "event_payload": {"row": {"id": 5, "name": "Mouse", "price": 29.99, "department": "Electronics", "in_stock": True}}},
            {"event_name": "set_meta", "event_payload": {"key": "last_updated", "value": "2024-01-09"}},
        ],
        "message": "Batch: removed mug, added mouse, set metadata",
        "author": "demo"
    })
    result = resp.json()
    print(f"Batch commit: {result.get('commit_id', 'error')[:8]}...")
    print(f"Events applied: {result.get('events_applied')}")

    # Final state (shows events_replayed)
    print_section("Final State (Event-Sourced)")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/data")
    data = resp.json()
    print(f"Entries ({data['entries_count']}):")
    for entry in data["entries"]:
        print(f"  {entry}")
    print(f"\nMetadata: {data['meta']}")
    print(f"Events replayed from snapshot: {data.get('events_replayed', 'N/A')}")

    # Demonstrate snapshot creation
    print_section("Snapshot Management")
    print("Creating a snapshot at current HEAD...")
    resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/snapshot?branch=main")
    result = resp.json()
    print(f"Snapshot result: {result}")

    # Now fetch data again - should show 0 events replayed
    print("\nFetching data after snapshot...")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/data")
    data = resp.json()
    print(f"Events replayed: {data.get('events_replayed', 'N/A')} (should be 0 after snapshot)")

    # Add more events after the snapshot
    print("\nAdding more events after snapshot...")
    for i in range(3):
        resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/events", json={
            "event_name": "append_row",
            "event_payload": {"row": {"id": 10+i, "name": f"Post-snapshot Item {i}", "department": "New", "in_stock": True, "price": 9.99}},
            "message": f"Post-snapshot item {i}"
        })

    # Fetch again - should show events replayed
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/data")
    data = resp.json()
    print(f"Entries: {data['entries_count']}, Events replayed: {data.get('events_replayed', 'N/A')}")

    # Using ObjectVersionsServer (high-level client)
    print_section("Using ObjectVersionsServer")
    print("from edsl.versioning import ObjectVersionsServer")
    print("")

    from edsl.versioning import ObjectVersionsServer
    server = ObjectVersionsServer(BASE_URL)

    # List repos
    repos = server.list_repos()
    print(f"Repositories on server: {len(repos)}")
    for r in repos:
        print(f"  - {r.get('alias') or r['repo_id'][:12]}: {r.get('commits_count', 0)} commits")

    # Clone our demo repo
    cloned = server.clone("demo/products")
    print(f"\nCloned 'demo/products':")
    print(f"  Entries: {len(cloned['entries'])}")
    print(f"  Meta: {cloned['meta']}")
    print(f"  Commit: {cloned['commit_id'][:8]}...")

    # === NEW FEATURES DEMO ===

    # Snapshot Statistics
    print_section("Snapshot Statistics")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/snapshot/stats")
    stats = resp.json()
    print(f"Total commits: {stats['total_commits']}")
    print(f"Total snapshots: {stats['total_snapshots']}")
    print(f"Snapshot coverage: {stats['snapshot_coverage']}%")
    print(f"Events since last snapshot: {stats['events_since_last_snapshot']}")
    print(f"Recommendations: {stats['recommendations']}")

    # Event Compaction Analysis
    print_section("Event Compaction Analysis")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/events/compact/analyze")
    analysis = resp.json()
    print(f"Total events: {analysis['total_events']}")
    print(f"Event types: {analysis['event_types']}")
    print(f"Potential reduction: {analysis['potential_reduction']} events")
    print(f"Potential savings: {analysis['potential_savings_percent']}%")

    # Time Travel - Search History
    print_section("Time Travel - Search History")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/history/search", params={"query": "Added"})
    search = resp.json()
    print(f"Search for 'Added': {search['count']} results")
    for r in search['results'][:3]:
        print(f"  {r['commit_id'][:8]} | {r['message']}")

    # Validation / Dry-Run
    print_section("Validation (Dry-Run)")
    print("Testing invalid event (index out of bounds)...")
    resp = requests.post(f"{BASE_URL}/api/repos/{repo_id}/events/validate", json={
        "events": [
            {"event_name": "update_row", "event_payload": {"index": 999, "row": {"x": 1}}},
            {"event_name": "append_row", "event_payload": {"row": {"name": "Test"}}},
        ],
        "branch": "main"
    })
    validation = resp.json()
    print(f"Success: {validation['success']}")
    print(f"Summary: {validation['summary']}")
    for vr in validation['validation_results']:
        status = "✓" if vr['valid'] else "✗"
        issues = ", ".join(i['message'] for i in vr['issues']) if vr['issues'] else "none"
        print(f"  {status} {vr['event_name']}: {issues}")

    # Repository Metrics & Health
    print_section("Repository Metrics & Health")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/metrics")
    metrics = resp.json()
    print("Storage:")
    print(f"  Total commits: {metrics['storage']['total_commits']}")
    print(f"  Total snapshots: {metrics['storage']['total_snapshots']}")
    print(f"  Total events: {metrics['storage']['total_events']}")
    print(f"  Snapshot coverage: {metrics['storage']['snapshot_coverage']}%")
    print("\nHealth:")
    print(f"  Healthy: {metrics['health']['healthy']}")
    print(f"  Scores: {metrics['health']['scores']}")
    if metrics['health']['issues']:
        print(f"  Issues: {metrics['health']['issues']}")
    if metrics['health']['recommendations']:
        print(f"  Recommendations: {metrics['health']['recommendations']}")

    # Diff Commits
    print_section("Diff Between Commits")
    resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/history")
    history = resp.json()
    if len(history['commits']) >= 3:
        from_commit = history['commits'][-1]['commit_id']
        to_commit = history['commits'][0]['commit_id']
        resp = requests.get(f"{BASE_URL}/api/repos/{repo_id}/history/diff", params={
            "from_commit": from_commit,
            "to_commit": to_commit
        })
        diff = resp.json()
        print(f"From: {diff['from_commit'][:8]} → To: {diff['to_commit'][:8]}")
        print(f"  Entries added: {diff['entries_added']}")
        print(f"  Entries removed: {diff['entries_removed']}")
        print(f"  Entries modified: {diff['entries_modified']}")
        if diff['fields_added']:
            print(f"  Fields added: {diff['fields_added']}")
        if diff['meta_changes']:
            print(f"  Meta changes: {list(diff['meta_changes'].keys())}")

    print_section("Demo Complete!")
    print(f"View in browser: {BASE_URL}/repos/{repo_id}")
    print(f"API docs: {BASE_URL}/docs")
    print("\nNew API Endpoints:")
    print("  GET  /api/repos/{id}/snapshot/stats     - Snapshot statistics")
    print("  POST /api/repos/{id}/snapshot/gc        - Garbage collect snapshots")
    print("  GET  /api/repos/{id}/events/compact/analyze - Compaction analysis")
    print("  GET  /api/repos/{id}/history/at?timestamp=  - State at time")
    print("  GET  /api/repos/{id}/history/search?query=  - Search commits")
    print("  GET  /api/repos/{id}/history/diff       - Diff two commits")
    print("  POST /api/repos/{id}/events/validate    - Dry-run validation")
    print("  GET  /api/repos/{id}/metrics            - Repository metrics")
    print("  GET  /api/metrics                       - Global server metrics")


if __name__ == "__main__":
    main()
