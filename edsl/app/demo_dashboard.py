#!/usr/bin/env python3
"""Demo script that starts the server with dashboard and pushes some sample apps."""

import threading
import time
import sys
import webbrowser
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
            print("🚀 Starting EDSL App Server with Dashboard...")
            print("📊 Dashboard: http://localhost:8000")
            print("📚 API Docs: http://localhost:8000/docs")
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        except Exception as e:
            print(f"Server error: {e}")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to start
    import requests
    for _ in range(30):
        try:
            requests.get("http://localhost:8000/health", timeout=2)
            return True
        except:
            time.sleep(1)
    return False

def push_sample_apps():
    """Push some sample apps to demonstrate the dashboard."""
    try:
        from edsl.app.client import EDSLAppClient
        from edsl.app.meal_planner import app as meal_planner_app

        print("📱 Pushing sample apps to server...")
        client = EDSLAppClient("http://localhost:8000")

        # Push the meal planner app
        app_id1 = client.push_app(meal_planner_app)
        print(f"✅ Pushed Meal Planner: {app_id1}")

        # Create and push a simple test app
        try:
            from edsl.app.app import App
            from edsl.app.output_formatter import OutputFormatter, OutputFormatters
            from edsl.surveys import Survey
            from edsl.questions import QuestionFreeText

            simple_survey = Survey([
                QuestionFreeText(
                    question_name="user_input",
                    question_text="What would you like to know about?"
                )
            ])

            simple_formatter = (
                OutputFormatter(name="Simple Response")
                .select('answer.user_input')
                .table()
            )

            simple_app = App(
                application_name="Simple Echo App",
                description="A simple app that echoes your input",
                initial_survey=simple_survey,
                jobs_object=simple_survey.to_jobs(),
                output_formatters=OutputFormatters([simple_formatter])
            )

            app_id2 = client.push_app(simple_app)
            print(f"✅ Pushed Simple Echo App: {app_id2}")

        except Exception as e:
            print(f"⚠️  Could not create simple test app: {e}")

        return True

    except Exception as e:
        print(f"❌ Failed to push sample apps: {e}")
        return False

def main():
    print("🎛️  EDSL App Server Dashboard Demo")
    print("="*50)

    if start_server():
        print("✅ Server started successfully!")

        # Push sample apps
        time.sleep(2)  # Give server a moment to fully start
        push_sample_apps()

        # Open dashboard in browser
        print("\n🌐 Opening dashboard in browser...")
        time.sleep(1)
        try:
            webbrowser.open("http://localhost:8000")
        except:
            print("Could not auto-open browser. Please visit http://localhost:8000")

        print("\n" + "="*60)
        print("🎉 Dashboard is ready!")
        print("🔗 Dashboard: http://localhost:8000")
        print("📚 API Documentation: http://localhost:8000/docs")
        print("⚡ The dashboard will show:")
        print("   • Server statistics")
        print("   • Deployed applications")
        print("   • App details and actions")
        print("   • Real-time updates (refreshes every 30 seconds)")
        print("\n💡 You can:")
        print("   • View app details")
        print("   • Execute apps with custom parameters")
        print("   • Delete apps")
        print("   • Monitor server status")
        print("\n🛑 Press Ctrl+C to stop the server")
        print("="*60)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Shutting down server...")

    else:
        print("❌ Failed to start server")
        return False

if __name__ == "__main__":
    main()