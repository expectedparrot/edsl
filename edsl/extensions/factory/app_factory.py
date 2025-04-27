from importlib import import_module
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings


def create_app(variant_module_path: str, settings: Settings = None) -> FastAPI:
    """
    Build a FastAPI instance, then import a variant's router
    and bolt it on.
    """
    if settings is None:
        from .config import settings as default_settings
        settings = default_settings
        
    app = FastAPI(
        title=settings.app_name,
        description="A modern FastAPI application deployed on Replit",
        version=settings.version,
        debug=settings.debug
    )
    
    # CORS middleware setup
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # For production, specify your actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # pull in variant-specific router(s)
    variant_mod = import_module(variant_module_path)
    # expect a top-level fastapi.APIRouter named `router`
    app.include_router(variant_mod.router, prefix=settings.api_prefix)
    
    # Root path response
    @app.get("/")
    async def root():
        return {
            "message": "Welcome to FastAPI on Replit!",
            "docs_url": "/docs",
            "version": settings.version
        }
    
    return app
