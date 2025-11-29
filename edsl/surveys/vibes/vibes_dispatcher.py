"""
Vibes Dispatcher: Central dispatch logic for vibes methods

This module provides the VibesDispatcher class that routes vibes method calls
through the registry system. It handles both local execution and will support
remote execution through the server package.

The dispatcher enables a unified interface for all vibes operations and provides
backward compatibility by maintaining the same method signatures as existing
Survey methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Union
import logging

try:
    from .vibes_registry import RegisterVibesMethodsMeta
    from .vibes_handler_base import VibesHandlerError
    from .schemas import VibesDispatchRequest, VibesDispatchResponse

    # Import all handlers to ensure they are registered
    from .handlers import *
except ImportError:
    from vibes_registry import RegisterVibesMethodsMeta
    from vibes_handler_base import VibesHandlerError
    from schemas import VibesDispatchRequest, VibesDispatchResponse

    # Import all handlers to ensure they are registered
    from handlers import *

if TYPE_CHECKING:
    from ..survey import Survey

# Set up logging
logger = logging.getLogger(__name__)


class VibesDispatchError(Exception):
    """Exception raised when vibes dispatch operations fail."""

    def __init__(
        self,
        message: str,
        target: Optional[str] = None,
        method: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.target = target
        self.method = method
        self.original_error = original_error

    def __str__(self):
        parts = [super().__str__()]
        if self.target and self.method:
            parts.append(f"Target.Method: {self.target}.{self.method}")
        if self.original_error:
            parts.append(
                f"Caused by: {type(self.original_error).__name__}: {self.original_error}"
            )
        return " | ".join(parts)


class VibesDispatcher:
    """
    Central dispatcher for vibes method calls.

    This class provides a unified interface for executing vibes methods
    through the registry system. It handles method lookup, validation,
    and execution, with support for both local and remote execution modes.

    The dispatcher maintains backward compatibility with existing Survey
    methods while providing the foundation for extensible remote execution.

    Attributes
    ----------
    default_remote : bool
        Default setting for remote execution (default: False)

    Examples
    --------
    >>> dispatcher = VibesDispatcher()
    >>> survey = dispatcher.dispatch(
    ...     target="survey", method="from_vibes", survey_cls=Survey,
    ...     description="Customer satisfaction survey", num_questions=5
    ... )
    """

    def __init__(self, default_remote: bool = False):
        """
        Initialize the vibes dispatcher.

        Args:
            default_remote: Default setting for remote execution
        """
        self.default_remote = default_remote
        self._registry = RegisterVibesMethodsMeta

    def dispatch(
        self, target: str, method: str, *args, remote: Optional[bool] = None, **kwargs
    ) -> Any:
        """
        Dispatch a vibes method call through the registry system.

        This is the main entry point for all vibes method calls. It performs
        method lookup, validation, and execution through the appropriate handler.

        Args:
            target: Target object type (e.g., "survey", "agent", "question")
            method: Method name (e.g., "from_vibes", "vibe_edit", "vibe_add", "vibe_describe")
            *args: Positional arguments for the method
            remote: Whether to execute remotely (overrides default_remote)
            **kwargs: Keyword arguments for the method

        Returns:
            Any: Result of the method execution (type depends on method)

        Raises:
            VibesDispatchError: If dispatch fails due to invalid target/method or execution error
            VibesHandlerError: If handler validation fails
        """
        # Determine execution mode
        use_remote = remote if remote is not None else self.default_remote

        try:
            # Validate that the method is registered
            if not self._registry.is_method_registered(target, method):
                available_methods = self._registry.list_available_methods(target)
                raise VibesDispatchError(
                    f"Method '{method}' not registered for target '{target}'. "
                    f"Available methods for {target}: {available_methods}",
                    target=target,
                    method=method,
                )

            # Get handler information
            handler_info = self._registry.get_method_handler(target, method)
            if not handler_info:
                raise VibesDispatchError(
                    f"Handler information not found for {target}.{method}",
                    target=target,
                    method=method,
                )

            # Get the handler class (should be a subclass of VibesHandlerBase)
            registered_by = handler_info.get("registered_by")
            if not registered_by:
                raise VibesDispatchError(
                    f"No registered handler class found for {target}.{method}",
                    target=target,
                    method=method,
                )

            # Find the handler class by searching through all registered classes
            # Since handlers inherit from VibesHandlerBase which uses the metaclass,
            # we can get them from the registry
            handler_class = None

            # Simple approach: the handler info should contain what we need
            # We can get the handler class from the registry info
            try:
                # Try to import the handler class by name
                import sys

                # Look for the handler class in the handlers module
                handlers_module = sys.modules.get("edsl.surveys.vibes.handlers")
                if not handlers_module:
                    # Try to import handlers module
                    try:
                        from . import handlers as handlers_module
                    except ImportError:
                        import handlers as handlers_module

                if handlers_module and hasattr(handlers_module, registered_by):
                    handler_class = getattr(handlers_module, registered_by)

            except Exception as e:
                logger.warning(f"Could not find handler class {registered_by}: {e}")
                handler_class = None

            if handler_class is None:
                raise VibesDispatchError(
                    f"Handler class '{registered_by}' not found for {target}.{method}",
                    target=target,
                    method=method,
                )

            # Execute based on mode
            if use_remote:
                return self._execute_remote(
                    handler_class, target, method, *args, **kwargs
                )
            else:
                return self._execute_local(
                    handler_class, target, method, *args, **kwargs
                )

        except VibesDispatchError:
            # Re-raise dispatch errors as-is
            raise
        except Exception as e:
            # Wrap other exceptions in dispatch error
            raise VibesDispatchError(
                f"Unexpected error during dispatch",
                target=target,
                method=method,
                original_error=e,
            ) from e

    def _execute_local(
        self, handler_class, target: str, method: str, *args, **kwargs
    ) -> Any:
        """
        Execute a vibes method locally through its handler.

        Args:
            handler_class: Handler class to execute
            target: Target object type
            method: Method name
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Any: Result of local execution

        Raises:
            VibesDispatchError: If local execution fails
        """
        try:
            logger.debug(
                f"Executing {target}.{method} locally with handler {handler_class.__name__}"
            )

            # Call the handler's execute_local method
            result = handler_class.execute_local(*args, **kwargs)

            logger.debug(f"Successfully executed {target}.{method} locally")
            return result

        except Exception as e:
            raise VibesDispatchError(
                f"Local execution failed for {target}.{method}",
                target=target,
                method=method,
                original_error=e,
            ) from e

    def _execute_remote(
        self, handler_class, target: str, method: str, *args, **kwargs
    ) -> Any:
        """
        Execute a vibes method remotely through the server.

        Args:
            handler_class: Handler class for serialization/deserialization
            target: Target object type
            method: Method name
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Any: Result of remote execution

        Raises:
            VibesDispatchError: If remote execution fails
        """
        try:
            import httpx
            import os
            from .schemas import VibesDispatchRequest, VibesDispatchResponse

            logger.info(f"Executing {target}.{method} remotely")

            # Get server configuration
            server_url = os.getenv("EDSL_VIBES_SERVER_URL", "http://localhost:8000")
            api_key = os.getenv("EXPECTED_PARROT_API_KEY")

            if not api_key:
                raise VibesDispatchError(
                    "Remote execution requires EXPECTED_PARROT_API_KEY environment variable",
                    target=target,
                    method=method,
                )

            # Convert local arguments to remote request format
            try:
                request_data = handler_class.to_remote_request(*args, **kwargs)
                logger.debug(
                    f"Converted to remote request: {list(request_data.keys())}"
                )
            except Exception as e:
                raise VibesDispatchError(
                    f"Failed to convert arguments to remote format: {str(e)}",
                    target=target,
                    method=method,
                    original_error=e,
                ) from e

            # Create dispatch request
            dispatch_request = VibesDispatchRequest(
                target=target, method=method, request_data=request_data
            )

            # Send HTTP request to server
            headers = {"Authorization": f"Bearer {api_key}"}
            endpoint = f"{server_url.rstrip('/')}/api/v1/vibes/dispatch"

            logger.debug(f"Sending request to: {endpoint}")

            try:
                with httpx.Client(timeout=300.0) as client:  # 5 minute timeout
                    response = client.post(
                        endpoint, json=dispatch_request.model_dump(), headers=headers
                    )

                logger.debug(f"Server response status: {response.status_code}")

                if response.status_code != 200:
                    error_detail = "Unknown error"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get(
                            "detail", error_data.get("error", str(error_data))
                        )
                    except:
                        error_detail = (
                            response.text[:200]
                            if response.text
                            else f"HTTP {response.status_code}"
                        )

                    raise VibesDispatchError(
                        f"Server returned error: {error_detail}",
                        target=target,
                        method=method,
                    )

            except httpx.RequestError as e:
                raise VibesDispatchError(
                    f"Failed to connect to server at {endpoint}: {str(e)}",
                    target=target,
                    method=method,
                    original_error=e,
                ) from e

            # Parse server response
            try:
                response_data = response.json()
                dispatch_response = VibesDispatchResponse(**response_data)
                logger.debug("Server response parsed successfully")
            except Exception as e:
                raise VibesDispatchError(
                    f"Failed to parse server response: {str(e)}",
                    target=target,
                    method=method,
                    original_error=e,
                ) from e

            # Check if execution was successful
            if not dispatch_response.success:
                error_msg = dispatch_response.error or "Unknown server error"
                raise VibesDispatchError(
                    f"Server execution failed: {error_msg}",
                    target=target,
                    method=method,
                )

            # Convert server response back to local format
            try:
                # For classmethods like from_vibes, we need to pass survey_cls
                if method == "from_vibes":
                    # survey_cls is passed as a keyword argument
                    survey_cls = kwargs.get("survey_cls")
                    result = handler_class.from_remote_response(
                        dispatch_response.result, survey_cls=survey_cls
                    )
                elif method in ["vibe_edit", "vibe_add", "vibe_describe"]:
                    # For instance methods, args[0] is the survey instance
                    survey = args[0] if args else None
                    result = handler_class.from_remote_response(
                        dispatch_response.result, survey=survey
                    )
                else:
                    # Generic fallback
                    result = handler_class.from_remote_response(
                        dispatch_response.result
                    )
                logger.debug("Remote response converted successfully")
                logger.info(f"Successfully executed {target}.{method} remotely")
                return result

            except Exception as e:
                raise VibesDispatchError(
                    f"Failed to convert server response to local format: {str(e)}",
                    target=target,
                    method=method,
                    original_error=e,
                ) from e

        except VibesDispatchError:
            # Re-raise dispatch errors as-is
            raise
        except ImportError as e:
            if "httpx" in str(e):
                raise VibesDispatchError(
                    f"Remote execution requires 'httpx' package. Install with: pip install httpx",
                    target=target,
                    method=method,
                    original_error=e,
                ) from e
            else:
                raise VibesDispatchError(
                    f"Import error during remote execution: {str(e)}",
                    target=target,
                    method=method,
                    original_error=e,
                ) from e
        except Exception as e:
            raise VibesDispatchError(
                f"Unexpected error during remote execution: {str(e)}",
                target=target,
                method=method,
                original_error=e,
            ) from e

    def validate_request(self, target: str, method: str, **kwargs) -> Any:
        """
        Validate request parameters for a specific target and method.

        Args:
            target: Target object type
            method: Method name
            **kwargs: Request parameters to validate

        Returns:
            Validated request object

        Raises:
            VibesDispatchError: If validation fails
        """
        try:
            return self._registry.validate_request(target, method, **kwargs)
        except Exception as e:
            raise VibesDispatchError(
                f"Request validation failed for {target}.{method}",
                target=target,
                method=method,
                original_error=e,
            ) from e

    def get_available_methods(self, target: str) -> list[str]:
        """
        Get all available methods for a target.

        Args:
            target: Target object type

        Returns:
            list: Available method names for the target
        """
        return self._registry.list_available_methods(target)

    def get_available_targets(self) -> list[str]:
        """
        Get all available targets with registered methods.

        Returns:
            list: Available target object types
        """
        return self._registry.list_available_targets()

    def is_method_available(self, target: str, method: str) -> bool:
        """
        Check if a method is available for a target.

        Args:
            target: Target object type
            method: Method name

        Returns:
            bool: True if method is available
        """
        return self._registry.is_method_registered(target, method)

    def get_method_info(self, target: str, method: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a registered method.

        Args:
            target: Target object type
            method: Method name

        Returns:
            dict or None: Method information if available
        """
        return self._registry.get_method_handler(target, method)

    def debug_registry(self) -> str:
        """
        Get a formatted string representation of the registry for debugging.

        Returns:
            str: Human-readable registry contents
        """
        return self._registry.debug_registry()


# Global dispatcher instance for convenience
# Can be used directly or modules can create their own instances
default_dispatcher = VibesDispatcher()


# Convenience functions for common operations
def dispatch_vibes_method(target: str, method: str, *args, **kwargs) -> Any:
    """
    Convenience function to dispatch a vibes method using the default dispatcher.

    Args:
        target: Target object type
        method: Method name
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Any: Result of method execution
    """
    return default_dispatcher.dispatch(target, method, *args, **kwargs)


def get_vibes_methods(target: str) -> list[str]:
    """
    Convenience function to get available methods for a target.

    Args:
        target: Target object type

    Returns:
        list: Available method names
    """
    return default_dispatcher.get_available_methods(target)


def is_vibes_method_available(target: str, method: str) -> bool:
    """
    Convenience function to check if a vibes method is available.

    Args:
        target: Target object type
        method: Method name

    Returns:
        bool: True if method is available
    """
    return default_dispatcher.is_method_available(target, method)


if __name__ == "__main__":
    # Example usage and testing
    print("EDSL Vibes Dispatcher")
    print("=" * 50)

    # Create dispatcher
    dispatcher = VibesDispatcher()

    # Show available targets and methods
    targets = dispatcher.get_available_targets()
    print(f"Available targets: {targets}")

    for target in targets:
        methods = dispatcher.get_available_methods(target)
        print(f"\nMethods for {target}:")
        for method in methods:
            method_info = dispatcher.get_method_info(target, method)
            description = method_info.get("metadata", {}).get(
                "description", "No description"
            )
            print(f"  {method}: {description}")

    # Show debug registry
    print(f"\n{dispatcher.debug_registry()}")

    print("\nDispatcher ready for method calls!")
    print(
        "Use dispatcher.dispatch(target, method, *args, **kwargs) to execute vibes methods."
    )
