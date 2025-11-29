#!/usr/bin/env python3
"""
Startup script for the EDSL survey generation server.

This script provides a convenient way to start the FastAPI server for remote
survey generation. It checks for required environment variables and provides
helpful error messages for common configuration issues.
"""

import os
import sys
import argparse
from pathlib import Path


def check_environment():
    """
    Check that required environment variables are set.

    Returns:
        bool: True if environment is properly configured, False otherwise
    """
    required_vars = {"OPENAI_API_KEY": "OpenAI API key for survey generation"}

    missing_vars = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing_vars.append((var, description))

    if missing_vars:
        print("❌ Environment Configuration Error")
        print("The following required environment variables are missing:")
        print()
        for var, description in missing_vars:
            print(f"  {var}: {description}")
        print()
        print("Please set these variables before starting the server:")
        for var, _ in missing_vars:
            print(f"  export {var}='your-{var.lower().replace('_', '-')}-here'")
        print()
        return False

    # Check optional but recommended variables
    optional_vars = {
        "EXPECTED_PARROT_API_KEY": "For testing client authentication",
        "HOST": "Server host (default: 0.0.0.0)",
        "PORT": "Server port (default: 8000)",
        "RELOAD": "Auto-reload on code changes (default: true)",
    }

    print("✓ Required environment variables configured")

    missing_optional = []
    for var, description in optional_vars.items():
        if not os.environ.get(var):
            missing_optional.append((var, description))

    if missing_optional:
        print("ℹ️  Optional environment variables:")
        for var, description in missing_optional:
            print(f"  {var}: {description}")
        print()

    return True


def main():
    """Main entry point for the server startup script."""
    parser = argparse.ArgumentParser(
        description="Start the EDSL Survey Generation Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  OPENAI_API_KEY        Required: OpenAI API key for survey generation
  EXPECTED_PARROT_API_KEY  Optional: For testing client authentication
  HOST                  Optional: Server host (default: 0.0.0.0)
  PORT                  Optional: Server port (default: 8000)
  RELOAD                Optional: Auto-reload on changes (default: true)

Examples:
  # Basic usage (after setting OPENAI_API_KEY)
  python run_server.py

  # Custom host and port
  HOST=localhost PORT=9000 python run_server.py

  # Production mode (no auto-reload)
  RELOAD=false python run_server.py

  # With specific log level
  python run_server.py --log-level warning
        """,
    )

    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "0.0.0.0"),
        help="Host to bind the server to (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 8000)),
        help="Port to bind the server to (default: 8000)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.environ.get("RELOAD", "true").lower() == "true",
        help="Enable auto-reload on code changes (default: True)",
    )

    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (useful for production)",
    )

    parser.add_argument(
        "--log-level",
        choices=["critical", "error", "warning", "info", "debug"],
        default="info",
        help="Log level for the server (default: info)",
    )

    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check environment configuration, don't start server",
    )

    args = parser.parse_args()

    print("=== EDSL Survey Generation Server ===")
    print("Version: 1.0.0")
    print("Service: Remote survey generation for EDSL vibes functionality")
    print()

    # Check environment configuration
    if not check_environment():
        sys.exit(1)

    if args.check_only:
        print("✓ Environment configuration check passed")
        return

    # Override reload setting if --no-reload is specified
    reload = args.reload and not args.no_reload

    print(f"Starting server:")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Reload: {reload}")
    print(f"  Log Level: {args.log_level}")
    print()
    print(f"API Documentation: http://{args.host}:{args.port}/docs")
    print(f"Health Check: http://{args.host}:{args.port}/health")
    print(f"Root Info: http://{args.host}:{args.port}/")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 50)

    try:
        import uvicorn

        # Get the path to the app module relative to this script
        app_module = "edsl.surveys.vibes.server.app:app"

        uvicorn.run(
            app_module,
            host=args.host,
            port=args.port,
            reload=reload,
            log_level=args.log_level,
            access_log=True,
        )

    except KeyboardInterrupt:
        print("\n=== Server Shutdown ===")
        print("Server stopped by user")

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("\nMissing dependencies. Please install required packages:")
        print("  pip install fastapi uvicorn")
        print("\nOr install EDSL with server dependencies:")
        print("  pip install edsl[server]")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Server Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
