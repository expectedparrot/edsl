"""
Entry point for running the EDSL Service Runner as a module.

Usage:
    python -m edsl.services_runner --port 8080
    python -m edsl.services_runner --host 0.0.0.0 --port 8080 --workers 8
"""

from .server import main

if __name__ == "__main__":
    main()
