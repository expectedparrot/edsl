#!/usr/bin/env python
"""Re-push the create_personas app to update it with attachment_formatters."""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from create_personas import app

# Push the app to the server
print("Pushing create_personas app to server...")
print(f"App has {len(list(app.attachment_formatters or []))} attachment formatters")

# Delete old app from database first
import requests
import sqlite3

# Get all apps and find the create_personas one
response = requests.get("http://localhost:8000/apps")
apps = response.json()

for app_meta in apps:
    if app_meta["name"] == "create_personas":
        print(f"Found existing app with ID: {app_meta['app_id']}")
        print(f"Deleting old app...")
        delete_response = requests.delete(f"http://localhost:8000/apps/{app_meta['app_id']}")
        print(f"Delete response: {delete_response.status_code}")

# Push the new version
print("Pushing new version...")
push_response = requests.post("http://localhost:8000/apps", json=app.to_dict())
print(f"Push response: {push_response.status_code}")
print(f"Response: {push_response.json()}")
