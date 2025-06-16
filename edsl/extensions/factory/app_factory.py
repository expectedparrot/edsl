from importlib import import_module
# Standard library
import time, secrets, inspect, logging, os
from typing import Callable, Optional, Any, Dict, Union
from contextlib import contextmanager

# Third-party
from fastapi import FastAPI, APIRouter, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

# Local imports
from edsl.extensions.authoring import extract_bearer_token
from ..authoring import Service, Services  # Add import for Services class

from .config import Settings


# ---------------------------------------------------------------------------
# Helper utilities (logging middleware, auto-generated routes, …)
# ---------------------------------------------------------------------------


logger = logging.getLogger(__name__)


def add_standard_middleware(app: FastAPI) -> None:
    """Attach request-timer + correlation-ID logging middleware."""

    @app.middleware("http")  # type: ignore[valid-type]
    async def _timer(request, call_next):
        rid = request.headers.get("x-request-id") or secrets.token_hex(4)
        start = time.time()
        logger.info("rid=%s start path=%s", rid, request.url.path)
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            duration = (time.time() - start) * 1000
            logger.exception(
                "rid=%s unhandled error after %.1f ms: %s", rid, duration, exc
            )
            raise

        duration = (time.time() - start) * 1000
        logger.info(
            "rid=%s completed_in=%.1fms status_code=%s",
            rid,
            duration,
            response.status_code,
        )
        response.headers["x-request-id"] = rid
        return response


@contextmanager
def temporary_api_token(token: Optional[str] = None):
    """Context manager for temporarily setting the EXPECTED_PARROT_API_KEY environment variable.
    
    Args:
        token (Optional[str]): The API token to set. If None, no changes are made.
    """
    if token is None:
        yield
        return
        
    old_token = os.environ.get("EXPECTED_PARROT_API_KEY")
    try:
        os.environ["EXPECTED_PARROT_API_KEY"] = token
        yield
    finally:
        if old_token is not None:
            os.environ["EXPECTED_PARROT_API_KEY"] = old_token
        else:
            os.environ.pop("EXPECTED_PARROT_API_KEY", None)


def create_extension_route(
    router: APIRouter,
    service_def,
    implementation: Callable[..., Any],
    *,
    route_path: str | None = None,
) -> None:
    """Auto-generate a POST endpoint from a ServiceDefinition & callable."""

    # Validate that the implementation's signature is compatible right away so
    # that errors surface during application start-up rather than on first
    # request.
    _validate_implementation_signature(service_def, implementation)

    request_model = service_def.get_request_model()
    response_model = service_def.get_response_model()
    path = route_path or f"/{service_def.name}"

    async def _invoke(fn: Callable[..., Any], **kwargs):  # noqa: D401
        if inspect.iscoroutinefunction(fn):
            return await fn(**kwargs)
        return fn(**kwargs)

    @router.post(path, response_model=response_model)  # type: ignore[arg-type]
    async def _endpoint(  # noqa: D401
        body: request_model,  # type: ignore[arg-type]
        authorization: Optional[str] = Header(None),
    ) -> Dict[str, Any]:
        token = extract_bearer_token(authorization)
        try:
            with temporary_api_token(token):
                result = await _invoke(
                    implementation, **body.model_dump()
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("%s failed: %s", service_def.name, exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        # Validate output structure matches service definition
        service_def.validate_service_output(result)
        return result


# ---------------------------------------------------------------------------
# Signature validation helper
# ---------------------------------------------------------------------------


def _validate_implementation_signature(service_def, implementation: Callable[..., Any]) -> None:
    """Ensure that *implementation* has a compatible signature with *service_def*.

    The callable must be able to accept **all** parameters declared in the
    ServiceDefinition as keyword arguments. Validation happens eagerly when
    the route is registered so that mistakes surface during application start-
    up rather than as runtime 500 errors on first request.

    Raises
    ------
    TypeError
        If the implementation function's signature is incompatible. The error
        message details the mismatch so it can be fixed quickly.
    """

    sig = inspect.signature(implementation)

    # Collect basic facts about the callable's parameters --------------------
    params = sig.parameters
    param_names = set(params)

    # Determine if **kwargs is present – this relaxes most restrictions.
    accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

    # ---------------------------------------------------------------------
    # 1. All parameters defined by the service must be accepted ------------
    # ---------------------------------------------------------------------

    missing = [p for p in service_def.parameters.keys() if p not in param_names and not accepts_var_kw]

    # ---------------------------------------------------------------------
    # 2. Required implementation parameters must be declared by service ----
    # ---------------------------------------------------------------------

    required_impl_params: list[str] = []
    for p in params.values():
        if p.kind == inspect.Parameter.POSITIONAL_ONLY:
            raise TypeError(
                f"Implementation for service '{service_def.name}' may not use positional-only parameter '{p.name}'. "
                "The router passes arguments by keyword."
            )

        if p.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ) and p.default is inspect._empty and p.name != "self":
            required_impl_params.append(p.name)

    extra_required = [p for p in required_impl_params if p not in service_def.parameters]

    # ---------------------------------------------------------------------
    # 3. Raise informative error if we have discrepancies ------------------
    # ---------------------------------------------------------------------

    if missing or extra_required:
        message_parts = []
        if missing:
            message_parts.append(
                "missing parameters in implementation: " + ", ".join(sorted(missing))
            )
        if extra_required:
            message_parts.append(
                "implementation declares unexpected *required* parameters: "
                + ", ".join(sorted(extra_required))
            )

        details = "; ".join(message_parts)
        raise TypeError(
            f"Signature mismatch for service '{service_def.name}': {details}. "
            "Either update the implementation or the ServiceDefinition so that they match."
        )


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def create_app(
    services: Services,
    settings: Settings = None,
) -> FastAPI:
    """
    Build a FastAPI instance from a Services container.

    Args:
        services: A Services container with all service implementations
        settings: Optional Settings instance for app configuration
    
    Returns:
        FastAPI: The configured FastAPI application
    """
    app = FastAPI(
        title="application name",  # settings.app_name if settings else "application name",
        description="A modern FastAPI application",
        version="1.0",  # settings.version if settings else "1.0",
        debug=False,  # settings.debug if settings else False
    )
    
    # CORS middleware setup
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # For production, specify your actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Standard timing / logging middleware
    add_standard_middleware(app)

    # Create routes for all services
    for service in services:
        create_extension_route(
            router=app,
            service_def=service.service_def,
            implementation=service.implementation,
        )
    
    # Root path response – list all registered routes
    @app.get("/")
    async def root():
        route_infos = [
            {
                "path": route.path,
                "methods": sorted(m for m in route.methods if m not in {"HEAD", "OPTIONS"}),
                "name": route.name,
            }
            for route in app.routes
            if isinstance(route, APIRoute)
        ]

        return {
            "routes": route_infos,
            "docs_url": "/docs",
            "version": "1.0",
        }
    
    return app
