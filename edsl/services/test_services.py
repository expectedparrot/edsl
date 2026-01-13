"""
Test runner for all registered EDSL services.

This module provides utilities to test each registered service by calling
its example method. Services should implement `get_example_params()` to 
provide test parameters.

Usage:
    # Run all tests
    python -m edsl.services.test_services
    
    # Run specific services
    python -m edsl.services.test_services wikipedia exa firecrawl
    
    # Run with verbose output
    python -m edsl.services.test_services --verbose
    
    # Run with timeout (seconds)
    python -m edsl.services.test_services --timeout 30
"""

from __future__ import annotations

# Services that require interactive auth (OAuth2, browser login, etc.)
# These will be auto-skipped unless --include-interactive is passed
INTERACTIVE_AUTH_SERVICES = {
    "google_sheets",  # Requires OAuth2 browser login
}

import argparse
import os
import signal
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from .registry import ServiceRegistry
from .base import ExternalService


@dataclass
class TestResult:
    """Result of testing a single service."""

    service_name: str
    status: str  # "success", "failed", "timeout", "missing_deps", "missing_key", "no_example", "skipped", "rate_limited"
    duration: float = 0.0
    error: Optional[str] = None
    result_count: Optional[int] = None

    def __str__(self) -> str:
        if self.status == "success":
            return f"✓ {self.service_name}: {self.result_count} results in {self.duration:.1f}s"
        elif self.status == "timeout":
            return f"⏱ {self.service_name}: Timed out after {self.duration:.1f}s"
        elif self.status == "missing_deps":
            return f"⚠ {self.service_name}: Missing dependencies"
        elif self.status == "missing_key":
            return f"🔑 {self.service_name}: Missing API key"
        elif self.status == "no_example":
            return f"📝 {self.service_name}: No example params defined"
        elif self.status == "skipped":
            return f"⊘ {self.service_name}: Skipped"
        elif self.status == "rate_limited":
            return f"🚫 {self.service_name}: Rate limited"
        else:
            return f"✗ {self.service_name}: {self.error[:50] if self.error else 'Unknown error'}"


@dataclass
class TestSummary:
    """Summary of all test results."""

    results: List[TestResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def success(self) -> int:
        return sum(1 for r in self.results if r.status == "success")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")

    @property
    def timeout(self) -> int:
        return sum(1 for r in self.results if r.status == "timeout")

    @property
    def missing_deps(self) -> int:
        return sum(1 for r in self.results if r.status == "missing_deps")

    @property
    def missing_key(self) -> int:
        return sum(1 for r in self.results if r.status == "missing_key")

    @property
    def no_example(self) -> int:
        return sum(1 for r in self.results if r.status == "no_example")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")

    @property
    def rate_limited(self) -> int:
        return sum(1 for r in self.results if r.status == "rate_limited")

    def __str__(self) -> str:
        lines = [
            "",
            "=" * 60,
            "Test Summary",
            "=" * 60,
            f"Total:        {self.total}",
            f"Success:      {self.success}",
            f"Failed:       {self.failed}",
            f"Timeout:      {self.timeout}",
            f"Missing deps: {self.missing_deps}",
            f"Missing key:  {self.missing_key}",
            f"Rate limited: {self.rate_limited}",
            f"No example:   {self.no_example}",
            f"Skipped:      {self.skipped}",
            "=" * 60,
        ]
        return "\n".join(lines)


def get_example_params(
    service_class: Type[ExternalService],
) -> Optional[Dict[str, Any]]:
    """
    Get example parameters for testing a service.

    Services can implement `get_example_params()` class method to provide
    test parameters. If not implemented, returns None.
    """
    if hasattr(service_class, "get_example_params"):
        try:
            return service_class.get_example_params()
        except Exception:
            return None
    return None


def test_service(
    service_name: str,
    timeout: float = 30.0,
    verbose: bool = False,
    include_interactive: bool = False,
) -> TestResult:
    """
    Test a single service by calling it with example parameters.

    Args:
        service_name: Name of the service to test
        timeout: Maximum time to wait for the service call
        verbose: Whether to print detailed progress
        include_interactive: Whether to include services requiring interactive auth

    Returns:
        TestResult with status and details
    """
    from edsl import ScenarioList

    start_time = time.time()

    # Skip interactive auth services unless explicitly included
    if service_name in INTERACTIVE_AUTH_SERVICES and not include_interactive:
        return TestResult(
            service_name=service_name,
            status="skipped",
            duration=0.0,
            error="Requires interactive auth (use --include-interactive to test)",
        )

    # Get service class
    service_class = ServiceRegistry.get(service_name)
    if service_class is None:
        return TestResult(
            service_name=service_name,
            status="failed",
            error=f"Service not found: {service_name}",
        )

    # Get example params
    example_params = get_example_params(service_class)
    if example_params is None:
        return TestResult(
            service_name=service_name,
            status="no_example",
            duration=time.time() - start_time,
        )

    # Extract operation and params
    operation = example_params.pop("_operation", "execute")

    if verbose:
        print(f"  Testing {service_name}.{operation}({example_params})...")

    def run_test():
        """Run the test in a thread for timeout support."""
        try:
            # Get the accessor
            accessor = getattr(ScenarioList, service_name)

            # Call the operation
            method = getattr(accessor, operation)
            result = method(**example_params, verbose=False)

            return result
        except ImportError as e:
            raise ImportError(f"MISSING_DEPS: {e}")
        except Exception as e:
            err_str = str(e)
            if (
                "API" in err_str
                or "KEY" in err_str
                or "key" in err_str.lower()
                or "token" in err_str.lower()
            ):
                raise ValueError(f"MISSING_KEY: {e}")
            raise

    # Run with timeout
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_test)
            result = future.result(timeout=timeout)

            duration = time.time() - start_time
            result_count = len(result) if hasattr(result, "__len__") else None

            return TestResult(
                service_name=service_name,
                status="success",
                duration=duration,
                result_count=result_count,
            )

    except FuturesTimeoutError:
        return TestResult(
            service_name=service_name,
            status="timeout",
            duration=timeout,
        )
    except ImportError as e:
        return TestResult(
            service_name=service_name,
            status="missing_deps",
            duration=time.time() - start_time,
            error=str(e).replace("MISSING_DEPS: ", ""),
        )
    except ValueError as e:
        err_str = str(e)
        if err_str.startswith("MISSING_KEY:"):
            return TestResult(
                service_name=service_name,
                status="missing_key",
                duration=time.time() - start_time,
                error=err_str.replace("MISSING_KEY: ", ""),
            )
        return TestResult(
            service_name=service_name,
            status="failed",
            duration=time.time() - start_time,
            error=str(e),
        )
    except RuntimeError as e:
        # Catch task execution errors
        err_str = str(e)
        # Detect rate limiting
        if (
            "429" in err_str
            or "rate limit" in err_str.lower()
            or "too many requests" in err_str.lower()
        ):
            return TestResult(
                service_name=service_name,
                status="rate_limited",
                duration=time.time() - start_time,
                error=err_str,
            )
        # Detect missing dependencies from task errors
        if "required" in err_str.lower() and (
            "install" in err_str.lower() or "pip" in err_str.lower()
        ):
            return TestResult(
                service_name=service_name,
                status="missing_deps",
                duration=time.time() - start_time,
                error=err_str,
            )
        # Detect API key errors - use more specific patterns
        api_key_patterns = [
            "api_key",
            "api key",
            "apikey",
            "_key is required",
            "_token is required",
            "_id and",
            "_id is required",  # e.g., REDDIT_CLIENT_ID and ...
            "_secret is required",
            "_secret and",
            "authentication",
            "unauthorized",
            "invalid key",
            "missing.*key",
            "key.*missing",
            "are required",  # e.g., "X and Y are required"
        ]
        if any(pattern in err_str.lower() for pattern in api_key_patterns):
            return TestResult(
                service_name=service_name,
                status="missing_key",
                duration=time.time() - start_time,
                error=err_str,
            )
        return TestResult(
            service_name=service_name,
            status="failed",
            duration=time.time() - start_time,
            error=str(e),
        )
    except Exception as e:
        return TestResult(
            service_name=service_name,
            status="failed",
            duration=time.time() - start_time,
            error=str(e),
        )


def test_all_services(
    services: Optional[List[str]] = None,
    timeout: float = 30.0,
    verbose: bool = False,
    skip_no_example: bool = False,
    include_interactive: bool = False,
) -> TestSummary:
    """
    Test all registered services (or a specific list).

    Args:
        services: List of service names to test (None = all)
        timeout: Timeout per service in seconds
        verbose: Whether to print detailed progress
        skip_no_example: Whether to skip services without example params
        include_interactive: Whether to include services requiring interactive auth

    Returns:
        TestSummary with all results
    """
    summary = TestSummary()

    # Get list of services to test
    if services:
        service_names = services
    else:
        service_names = sorted(ServiceRegistry.list())

    print(f"Testing {len(service_names)} services...")
    print("=" * 60)

    for name in service_names:
        result = test_service(
            name,
            timeout=timeout,
            verbose=verbose,
            include_interactive=include_interactive,
        )
        summary.results.append(result)
        print(str(result))

    print(str(summary))

    return summary


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Test EDSL services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test all services
    python -m edsl.services.test_services
    
    # Test specific services
    python -m edsl.services.test_services wikipedia exa
    
    # Test with longer timeout
    python -m edsl.services.test_services --timeout 60
    
    # Verbose output
    python -m edsl.services.test_services --verbose
        """,
    )

    parser.add_argument(
        "services",
        nargs="*",
        help="Specific services to test (default: all)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout per service in seconds (default: 30)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all services and exit",
    )
    parser.add_argument(
        "--include-interactive",
        action="store_true",
        help="Include services requiring interactive auth (OAuth2, etc.)",
    )
    parser.add_argument(
        "--auto-install",
        action="store_true",
        help="Automatically install missing dependencies (uses uv or pip)",
    )

    args = parser.parse_args()

    # Import services to register them
    from . import builtin

    if args.list:
        services = sorted(ServiceRegistry.list())
        print(f"Registered services ({len(services)}):")
        for name in services:
            service = ServiceRegistry.get(name)
            has_example = hasattr(service, "get_example_params")
            is_interactive = name in INTERACTIVE_AUTH_SERVICES
            if is_interactive:
                marker = "🔐"
            elif has_example:
                marker = "✓"
            else:
                marker = "·"
            print(f"  {marker} {name}")
        print(f"\n✓ = has example params, 🔐 = requires interactive auth")
        return

    services = args.services if args.services else None

    # Set auto-install env var if requested
    if args.auto_install:
        os.environ["EDSL_AUTO_INSTALL_DEPS"] = "1"

    summary = test_all_services(
        services=services,
        timeout=args.timeout,
        verbose=args.verbose,
        include_interactive=args.include_interactive,
    )

    # Exit with error code if any tests failed
    if summary.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
