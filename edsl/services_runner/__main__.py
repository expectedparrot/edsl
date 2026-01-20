"""
EDSL Services Runner - CLI entry point.

Run with:
    python -m edsl.services_runner [options]

The server automatically discovers and serves all EDSL services that are
installed via Python entry points in the 'edsl.services' group.

To register a service, add an entry point in your package's pyproject.toml:

    [project.entry-points."edsl.services"]
    my_service = "my_package.services:MyService"

Options:
    --host HOST     Host to bind to (default: 0.0.0.0)
    --port PORT     Port to bind to (default: 8000)
    --reload        Enable auto-reload for development
    --list          List available services and exit
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="edsl.services_runner",
        description="Run the EDSL services server (auto-discovers installed services)",
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_services",
        help="List available services and exit",
    )

    parser.add_argument(
        "--title",
        default="EDSL Services API",
        help="API title for documentation",
    )

    args = parser.parse_args()

    # Import here to defer heavy imports
    from edsl.services_runner.registry import discover_services, get_all_services

    # Discover services from entry points
    discovered = discover_services()

    if args.list_services:
        # List services and exit
        services = get_all_services()

        if not services:
            print("No services found.")
            print()
            print("To register services, install a package that provides")
            print("entry points in the 'edsl.services' group.")
            print()
            print("Example pyproject.toml for an extension package:")
            print()
            print('  [project.entry-points."edsl.services"]')
            print('  my_service = "my_package.services:MyService"')
            sys.exit(0)

        print(f"Found {len(services)} service(s):")
        print()

        for name, cls in services.items():
            extends = getattr(cls, 'extends', [])
            extends_str = ", ".join(t.__name__ for t in extends) if extends else "None"
            desc = cls.__doc__.split('\n')[0].strip() if cls.__doc__ else "No description"

            print(f"  {name}")
            print(f"    Extends: {extends_str}")
            print(f"    Description: {desc}")

            # Get method info if possible
            try:
                instance = cls()
                info = instance.get_info()
                methods = [m['method_name'] for m in info.get('methods', [])]
                if methods:
                    print(f"    Methods: {', '.join(methods)}")
            except Exception:
                pass

            print()

        sys.exit(0)

    # Run the server
    from edsl.services_runner.server import run_server

    run_server(
        host=args.host,
        port=args.port,
        reload=args.reload,
        title=args.title,
    )


if __name__ == "__main__":
    main()
