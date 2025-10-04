#!/usr/bin/env python
"""Load all app examples to the server."""

import sys
import importlib
from pathlib import Path
import requests

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

SERVER_URL = "http://localhost:8000"

# List of apps to load (excluding utility scripts)
APP_FILES = [
    "advice_to_checklist",
    "agent_blueprint_creator",
    "auto_survey",
    "cognitive_testing",
    "color_survey",
    "conjoint_analysis",
    "conjoint_profiles_app",
    "create_personas",
    "data_labeling",
    "eligible_agents",
    "food_health",
    "food_health_true_skill",
    "jeopardy",
    "meal_planner",
    "packing_list",
    "panel_reaction",
    "referee_report",
    "robot_vc",
    "rubric_generator",
    "sample_size_calculator",
    "story_time",
    "survey_option_inference",
    "telephone_app",
    "twitter_thread",
    "variant_creator",
]

def delete_existing_app(app_name):
    """Delete an app from the server if it exists."""
    try:
        response = requests.get(f"{SERVER_URL}/apps")
        if response.status_code == 200:
            apps = response.json()
            for app_meta in apps:
                if app_meta["name"] == app_name:
                    print(f"  Deleting existing app with ID: {app_meta['app_id']}")
                    delete_response = requests.delete(f"{SERVER_URL}/apps/{app_meta['app_id']}")
                    if delete_response.status_code == 200:
                        print(f"  ✓ Deleted successfully")
                    return True
    except Exception as e:
        print(f"  Error checking/deleting existing app: {e}")
    return False

def load_app(module_name):
    """Load an app module and push it to the server."""
    print(f"\n{'='*60}")
    print(f"Loading: {module_name}")
    print(f"{'='*60}")

    try:
        # Import the module
        module = importlib.import_module(module_name)

        # Get the app object
        if not hasattr(module, 'app'):
            print(f"  ⚠ No 'app' object found in {module_name}, skipping")
            return False

        app = module.app
        app_name = app.application_name

        print(f"  App name: {app_name}")
        print(f"  Description: {app.description}")
        print(f"  Output formatters: {list(app.output_formatters.mapping.keys())}")
        print(f"  Attachment formatters: {len(list(app.attachment_formatters or []))}")

        # Delete existing app if present
        delete_existing_app(app_name)

        # Push the app
        print(f"  Pushing to server...")
        response = requests.post(f"{SERVER_URL}/apps", json=app.to_dict())

        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ Successfully pushed with ID: {result['app_id']}")
            return True
        else:
            print(f"  ✗ Failed to push: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"  ✗ Error loading {module_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Load all apps."""
    print(f"Loading {len(APP_FILES)} apps to {SERVER_URL}")
    print(f"{'='*60}\n")

    success_count = 0
    fail_count = 0

    for app_file in APP_FILES:
        if load_app(app_file):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total apps: {len(APP_FILES)}")
    print(f"Successfully loaded: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
