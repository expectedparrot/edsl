"""
FastAPI backend for Why Would I Lie web interface.
Wraps the existing Two Truths and a Lie game engine.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import experiment, streaming, config

app = FastAPI(
    title="Why Would I Lie API",
    description="Backend API for LLM deception experiment platform",
    version="1.0.0"
)

# CORS configuration for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:3001",
        "https://*.vercel.app",   # Vercel preview/production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(experiment.router, prefix="/api/experiment", tags=["experiment"])
app.include_router(streaming.router, prefix="/api/stream", tags=["streaming"])
app.include_router(config.router, prefix="/api/config", tags=["config"])

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Why Would I Lie API",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "services": {
            "api": "ok",
            "game_engine": "ok",
            "edsl": "ok"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
