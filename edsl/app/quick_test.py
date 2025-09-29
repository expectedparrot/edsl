#!/usr/bin/env python3
"""Quick test script for the FastAPI server with meal planner."""

import threading
import time
import sys
import requests
from pathlib import Path

# Add the parent directories to the path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir.parent.parent))

def start_server():
    """Start the server in a thread."""
    def run_server():
        try:
            import uvicorn
            from edsl.app.server import app
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")
        except Exception as e:
            print(f"Server error: {e}")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to start
    for _ in range(30):
        try:
            requests.get("http://127.0.0.1:8000/health", timeout=2)
            return True
        except:
            time.sleep(1)
    return False

def test_meal_planner():
    """Test the meal planner app."""
    try:
        from edsl.app.client import EDSLAppClient
        from edsl.app.meal_planner import app as meal_planner_app

        print("🚀 Testing meal planner deployment...")

        # Create client
        client = EDSLAppClient("http://127.0.0.1:8000")

        # Push app
        app_id = client.push_app(meal_planner_app)
        print(f"✅ Deployed app: {app_id}")

        # Test answers
        answers = {
            "number_of_people": 1,
            "dietary_preferences_or_restrictions": "None",
            "days_of_the_week": ["Monday", "Tuesday"],
            "time_for_cooking": "Very little - ideally meals are almost no preparation",
            "any_specific_health_goals": "Stay healthy",
            "food_allergies_or_intolerances": "None",
            "other": "Simple meals please"
        }

        # Execute app
        print("🍽️  Executing meal planner...")
        result = client.execute_app(app_id, answers, "Markdown Viewer")

        if result['status'] == 'completed':
            print("✅ Execution successful!")
            print(f"📋 Result type: {type(result.get('result'))}")
            return True
        else:
            print(f"❌ Execution failed: {result.get('error')}")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting quick test...")

    if start_server():
        print("✅ Server started")
        success = test_meal_planner()

        if success:
            print("🎉 Test passed!")
        else:
            print("💥 Test failed")

        # Keep server running for manual testing
        print("Server running at http://127.0.0.1:8000")
        print("Press Ctrl+C to exit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        print("❌ Failed to start server")