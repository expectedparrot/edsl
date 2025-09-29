"""Test script for EDSL App FastAPI server."""

import time
import sys
from pathlib import Path

# Add the parent directory to the path so we can import edsl modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_server():
    """Test the FastAPI server with a sample app."""

    try:
        from edsl.app.client import EDSLAppClient
        from edsl.app.app import App
        from edsl.app.output_formatter import OutputFormatter, OutputFormatters
        from edsl.surveys import Survey
        from edsl.questions import QuestionFreeText, QuestionList
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure to install the 'services' extra: pip install 'edsl[services]'")
        return

    # Create a test app (similar to the example in app.py)
    print("Creating test app...")

    initial_survey = Survey([
        QuestionFreeText(
            question_name="raw_text",
            question_text="What is the text to split into a twitter thread?"
        )
    ])

    jobs_survey = Survey([
        QuestionList(
            question_name="twitter_thread",
            question_text="Please take this text: {{scenario.raw_text}} and split into a twitter thread, if necessary."
        )
    ])

    # Use a simple output formatter that works with JSON
    twitter_output_formatter = OutputFormatter(name="Twitter Thread Splitter")

    test_app = App(
        application_name="Twitter Thread Splitter",
        description="This application splits text into a twitter thread.",
        initial_survey=initial_survey,
        jobs_object=jobs_survey.to_jobs(),
        output_formatters=OutputFormatters([twitter_output_formatter])
    )

    # Test client
    print("Testing server connection...")
    client = EDSLAppClient("http://localhost:8000")

    try:
        # Health check
        health = client.health_check()
        print(f"Server health: {health}")

        # List apps (should be empty initially)
        apps = client.list_apps()
        print(f"Apps on server: {len(apps)}")

        # Push the app
        print("Pushing test app to server...")
        app_id = client.push_app(test_app)
        print(f"App pushed with ID: {app_id}")

        # List apps again
        apps = client.list_apps()
        print(f"Apps on server after push: {len(apps)}")

        # Get app metadata
        metadata = client.get_app_metadata(app_id)
        print(f"App metadata: {metadata}")

        # Get app parameters
        parameters = client.get_app_parameters(app_id)
        print(f"App parameters: {parameters}")

        # Execute the app
        print("Executing app...")
        test_answers = {
            "raw_text": "This is a short test text that probably doesn't need to be split into a thread."
        }

        execution = client.execute_app(app_id, test_answers)
        print(f"Execution result: {execution}")

        # Get execution status
        execution_status = client.get_execution_status(execution["execution_id"])
        print(f"Execution status: {execution_status}")

        # Get server stats
        stats = client.get_stats()
        print(f"Server stats: {stats}")

        print("\n✅ All tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("EDSL App FastAPI Server Test")
    print("=============================")
    print("Make sure the server is running with:")
    print("  python -m edsl.app.server")
    print("or")
    print("  uvicorn edsl.app.server:app --host 0.0.0.0 --port 8000")
    print()

    # Wait a moment for user to see the message
    print("Starting test in 3 seconds...")
    time.sleep(3)

    test_server()