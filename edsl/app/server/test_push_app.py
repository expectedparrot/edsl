"""Test script to push an app to the server."""
import sys
sys.path.insert(0, '/Users/johnhorton/tools/ep/edsl')

from edsl.app.server.client import EDSLAppClient

# Import an example app
from edsl.app.examples.meal_planner import app

def main():
    client = EDSLAppClient("http://localhost:8000")

    # Check health
    print("Checking server health...")
    health = client.health_check()
    print(f"Server status: {health}")

    # Push the app
    print(f"\nPushing app: {app.application_name}")
    app_id = client.push_app(app)
    print(f"App pushed successfully! ID: {app_id}")

    # List all apps
    print("\nListing all apps:")
    apps = client.list_apps()
    for a in apps:
        print(f"  - {a['name']} ({a['app_id']})")

    print(f"\nYou can now access the app at: http://localhost:3000")

if __name__ == "__main__":
    main()
