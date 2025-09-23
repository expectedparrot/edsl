#!/usr/bin/env python3
"""Comprehensive test script that starts the server, deploys the meal planner app, and runs it."""

import threading
import time
import sys
import requests
import signal
import os
from pathlib import Path

# Add the parent directories to the path so we can import edsl modules
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir.parent.parent))

def start_server_thread():
    """Start the FastAPI server in a separate thread."""
    try:
        import uvicorn
        from edsl.app.server import app

        print("🚀 Starting FastAPI server in background thread...")
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="warning",  # Reduce noise during testing
            access_log=False
        )
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

def wait_for_server(max_attempts=30, delay=1):
    """Wait for the server to be ready."""
    print("⏳ Waiting for server to start...")

    for attempt in range(max_attempts):
        try:
            response = requests.get("http://127.0.0.1:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ Server is ready!")
                return True
        except requests.exceptions.RequestException:
            pass

        if attempt < max_attempts - 1:
            time.sleep(delay)

    print("❌ Server failed to start within timeout period")
    return False

def test_meal_planner_deployment():
    """Test the meal planner app deployment and execution."""
    print("\n" + "="*60)
    print("🍽️  TESTING MEAL PLANNER APP DEPLOYMENT")
    print("="*60)

    try:
        # Import all the required modules
        from edsl.app.client import EDSLAppClient
        from edsl.app.meal_planner import app as meal_planner_app

        # Initialize client
        client = EDSLAppClient("http://127.0.0.1:8000")

        # Test server health
        print("\n1. Testing server health...")
        health = client.health_check()
        print(f"   Server status: {health['status']}")

        # List current apps
        print("\n2. Checking current apps on server...")
        apps_before = client.list_apps()
        print(f"   Apps on server: {len(apps_before)}")

        # Deploy the meal planner app
        print("\n3. Deploying meal planner app to server...")
        app_id = client.push_app(meal_planner_app)
        print(f"   ✅ Meal planner deployed with ID: {app_id}")

        # Verify deployment
        apps_after = client.list_apps()
        print(f"   Apps on server after deployment: {len(apps_after)}")

        # Get app metadata
        print("\n4. Getting app metadata...")
        metadata = client.get_app_metadata(app_id)
        print(f"   App name: {metadata['name']}")
        print(f"   Description: {metadata['description']}")
        print(f"   Type: {metadata['application_type']}")
        print(f"   Available formatters: {metadata['available_formatters']}")

        # Get app parameters
        print("\n5. Getting app parameters...")
        parameters = client.get_app_parameters(app_id)
        print("   Required parameters:")
        for param_name, param_type, param_text in parameters['parameters']:
            print(f"     - {param_name} ({param_type}): {param_text}")

        # Prepare test answers
        test_answers = {
            "number_of_people": 2,
            "dietary_preferences_or_restrictions": "Vegetarian",
            "days_of_the_week": ["Monday", "Tuesday", "Wednesday"],
            "time_for_cooking": "Some - I'm find with cooking for 15 minutes or so for a hot meal",
            "any_specific_health_goals": "Maintain healthy weight and get more protein",
            "food_allergies_or_intolerances": "None",
            "other": "I prefer simple, nutritious meals"
        }

        print(f"\n6. Executing meal planner with test parameters...")
        print(f"   Parameters: {test_answers}")

        # Execute the app remotely
        execution = client.execute_app(
            app_id=app_id,
            answers=test_answers,
            formatter_name="Markdown Viewer"  # Use the markdown viewer
        )

        print(f"   Execution ID: {execution['execution_id']}")
        print(f"   Status: {execution['status']}")

        # Check execution results
        if execution['status'] == 'completed':
            print("\n7. ✅ Execution completed successfully!")
            if execution.get('result'):
                print("   📋 Meal plan generated:")
                print("   " + "-" * 40)
                # The result should be the viewed content from the markdown formatter
                result_str = str(execution['result'])
                # Print first 500 characters to avoid overwhelming output
                preview = result_str[:500] + "..." if len(result_str) > 500 else result_str
                print(f"   {preview}")
                print("   " + "-" * 40)
            else:
                print("   ⚠️  No result content returned")
        else:
            print(f"\n7. ❌ Execution failed with status: {execution['status']}")
            if execution.get('error'):
                print(f"   Error: {execution['error']}")

        # Test with different formatter
        print(f"\n8. Testing with different formatter (Docx Writer)...")
        execution2 = client.execute_app(
            app_id=app_id,
            answers=test_answers,
            formatter_name="Docx Writer"
        )

        print(f"   Execution ID: {execution2['execution_id']}")
        print(f"   Status: {execution2['status']}")

        if execution2['status'] == 'completed':
            print("   ✅ Second execution with Docx Writer completed!")
        else:
            print(f"   ❌ Second execution failed: {execution2.get('error', 'Unknown error')}")

        # Get server stats
        print(f"\n9. Final server statistics...")
        stats = client.get_stats()
        print(f"   Total apps: {stats['total_apps']}")
        print(f"   Total executions: {stats['total_executions']}")

        print(f"\n✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print(f"🎉 Meal planner app successfully deployed and executed on FastAPI server!")

        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("🧪 EDSL App FastAPI Server Integration Test")
    print("🍽️  Testing with Meal Planner Application")
    print("=" * 60)

    # Start server in background thread
    server_thread = threading.Thread(target=start_server_thread, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    if not wait_for_server():
        print("❌ Cannot proceed without running server")
        return False

    try:
        # Run the meal planner test
        success = test_meal_planner_deployment()

        if success:
            print(f"\n🎊 Integration test completed successfully!")
            print(f"📊 Server is still running at http://127.0.0.1:8000")
            print(f"📚 API docs available at http://127.0.0.1:8000/docs")
            print(f"🔄 You can manually test more apps or press Ctrl+C to exit")

            # Keep the main thread alive to let user explore
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print(f"\n👋 Shutting down...")

        else:
            print(f"\n💥 Integration test failed!")

        return success

    except KeyboardInterrupt:
        print(f"\n👋 Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Starting EDSL App Server Integration Test...")
    print("This will:")
    print("1. Start FastAPI server in background")
    print("2. Deploy the meal planner app")
    print("3. Execute it with sample data")
    print("4. Show results")
    print()

    # Give user a moment to read
    time.sleep(2)

    success = main()
    sys.exit(0 if success else 1)