"""
FastAPI server for remote survey generation.

This server provides an API endpoint for generating surveys from natural
language descriptions. It uses OpenAI's API to generate survey schemas
and requires Expected Parrot API key authentication for access.
"""

from fastapi import FastAPI, HTTPException, status, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import logging
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="EDSL Survey Generation API",
    description="Remote survey generation service for EDSL vibes functionality",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Security scheme for Expected Parrot API key authentication
security = HTTPBearer()


# Request/Response Models
class SurveyGenerationRequest(BaseModel):
    """Request model for survey generation."""

    description: str = Field(
        ...,
        description="Natural language description of the survey topic",
        example="Survey about a new consumer brand of vitamin water",
        min_length=10,
        max_length=5000,
    )
    num_questions: Optional[int] = Field(
        None,
        description="Number of questions to generate (optional)",
        ge=1,
        le=50,
        example=5,
    )
    model: str = Field(
        "gpt-4o", description="OpenAI model to use for generation", example="gpt-4o"
    )
    temperature: float = Field(
        0.7, description="Temperature for generation", ge=0.0, le=2.0, example=0.7
    )


class QuestionDefinition(BaseModel):
    """Model for a single question definition."""

    question_name: str = Field(..., description="Variable name for the question")
    question_text: str = Field(..., description="The actual question text")
    question_type: str = Field(
        ..., description="Type of question (e.g., 'multiple_choice', 'free_text')"
    )
    question_options: Optional[List[str]] = Field(
        None, description="Answer choices for multiple choice questions"
    )
    min_value: Optional[float] = Field(
        None, description="Minimum value for numerical questions"
    )
    max_value: Optional[float] = Field(
        None, description="Maximum value for numerical questions"
    )


class SurveyGenerationResponse(BaseModel):
    """Response model for survey generation."""

    questions: List[QuestionDefinition] = Field(
        ..., description="List of generated questions"
    )
    request_id: str = Field(..., description="Unique identifier for this request")
    generated_with: Dict[str, Any] = Field(
        ..., description="Metadata about generation parameters"
    )


class ErrorResponse(BaseModel):
    """Model for error responses."""

    detail: str = Field(..., description="Error message")
    request_id: Optional[str] = Field(None, description="Request ID if available")
    error_type: str = Field(..., description="Type of error")


# Authentication dependency
def verify_expected_parrot_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """
    Verify the Expected Parrot API key from the Authorization header.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        str: The validated API key

    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Extract the API key from Bearer token
        api_key = credentials.credentials

        if not api_key:
            logger.warning("Empty API key provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key is required for access",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # For local development, we can be less strict with key validation
        # In production, you might want to validate against a specific format or database
        if len(api_key) < 10:  # Basic sanity check
            logger.warning(f"Invalid API key format: {api_key[:5]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"Authenticated request with API key: {api_key[:5]}...")
        return api_key

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Root endpoint
@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": "EDSL Survey Generation API",
        "version": "1.0.0",
        "description": "Remote survey generation service for EDSL vibes functionality",
        "endpoints": {
            "health": "/health",
            "generate": "/api/v1/surveys/from-vibes",
            "docs": "/docs",
            "redoc": "/redoc",
        },
        "authentication": "Bearer token required (Expected Parrot API key)",
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    openai_key_available = bool(os.environ.get("OPENAI_API_KEY"))

    return {
        "status": "healthy",
        "service": "EDSL Survey Generation API",
        "openai_configured": openai_key_available,
        "timestamp": str(uuid.uuid4()),  # Simple timestamp alternative
    }


# Main generation endpoint
@app.post(
    "/api/v1/surveys/from-vibes",
    response_model=SurveyGenerationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Survey Generation"],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def generate_survey_from_vibes(
    request: SurveyGenerationRequest, api_key: str = Depends(verify_expected_parrot_key)
) -> SurveyGenerationResponse:
    """
    Generate a survey from a natural language description.

    This endpoint uses an LLM to generate a complete survey based on a description
    of what the survey should cover. It automatically selects appropriate question
    types and formats.

    **Authentication Required:** Bearer token with Expected Parrot API key

    Args:
        request: Survey generation request with description and parameters
        api_key: Validated Expected Parrot API key (injected by dependency)

    Returns:
        SurveyGenerationResponse: Generated survey with list of questions

    Raises:
        HTTPException: If survey generation fails
    """
    request_id = str(uuid.uuid4())
    logger.info(
        f"[{request_id}] Received survey generation request: {request.description[:100]}..."
    )
    logger.info(
        f"[{request_id}] Parameters: model={request.model}, temp={request.temperature}, num_questions={request.num_questions}"
    )

    # Check for OpenAI API key on server
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error(f"[{request_id}] OPENAI_API_KEY not configured on server")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                detail="Server configuration error: OPENAI_API_KEY not set on server",
                request_id=request_id,
                error_type="configuration_error",
            ).dict(),
        )

    try:
        # Import here to avoid issues if module isn't available
        from ..survey_generator import SurveyGenerator

        # Create survey generator with request parameters
        generator = SurveyGenerator(
            model=request.model, temperature=request.temperature
        )

        logger.info(f"[{request_id}] Starting survey generation...")

        # Generate survey
        survey_data = generator.generate_survey(
            description=request.description, num_questions=request.num_questions
        )

        # Validate the generated data structure
        if not isinstance(survey_data, dict) or "questions" not in survey_data:
            error_msg = "Invalid survey data structure returned from generator"
            logger.error(f"[{request_id}] {error_msg}: {type(survey_data)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ErrorResponse(
                    detail=f"Survey generation failed: {error_msg}",
                    request_id=request_id,
                    error_type="generation_error",
                ).dict(),
            )

        questions = survey_data["questions"]
        if not isinstance(questions, list):
            error_msg = "Questions data must be a list"
            logger.error(f"[{request_id}] {error_msg}: {type(questions)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ErrorResponse(
                    detail=f"Survey generation failed: {error_msg}",
                    request_id=request_id,
                    error_type="generation_error",
                ).dict(),
            )

        logger.info(f"[{request_id}] Successfully generated {len(questions)} questions")
        logger.debug(
            f"[{request_id}] Question types: {[q.get('question_type') for q in questions]}"
        )

        # Create response
        response = SurveyGenerationResponse(
            questions=[
                QuestionDefinition(
                    question_name=q.get("question_name", f"q{i}"),
                    question_text=q.get("question_text", ""),
                    question_type=q.get("question_type", "free_text"),
                    question_options=q.get("question_options"),
                    min_value=q.get("min_value"),
                    max_value=q.get("max_value"),
                )
                for i, q in enumerate(questions)
            ],
            request_id=request_id,
            generated_with={
                "model": request.model,
                "temperature": request.temperature,
                "num_questions_requested": request.num_questions,
                "num_questions_generated": len(questions),
                "description_length": len(request.description),
            },
        )

        logger.info(f"[{request_id}] Successfully completed survey generation")
        return response

    except HTTPException:
        # Re-raise HTTP exceptions (like auth errors)
        raise

    except ImportError as e:
        error_msg = "Survey generation module not available"
        logger.error(f"[{request_id}] {error_msg}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                detail=f"Server error: {error_msg}",
                request_id=request_id,
                error_type="import_error",
            ).dict(),
        )

    except Exception as e:
        error_msg = f"Survey generation failed: {str(e)}"
        logger.error(f"[{request_id}] {error_msg}", exc_info=True)

        # Distinguish between different types of errors
        error_type = (
            "openai_error" if "openai" in str(e).lower() else "generation_error"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                detail=error_msg, request_id=request_id, error_type=error_type
            ).dict(),
        )


# Server startup event
@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logger.info("=== EDSL Survey Generation Server Starting ===")
    logger.info("Service: EDSL Survey Generation API")
    logger.info("Version: 1.0.0")

    # Check configuration
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        logger.info("✓ OPENAI_API_KEY configured")
    else:
        logger.warning("✗ OPENAI_API_KEY not configured - server will return errors")

    logger.info("✓ Expected Parrot API key authentication enabled")
    logger.info("✓ CORS enabled for local development")
    logger.info("✓ API documentation available at /docs")
    logger.info("=== Server Ready ===")


# Server shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown information."""
    logger.info("=== EDSL Survey Generation Server Shutting Down ===")


if __name__ == "__main__":
    import uvicorn

    # Configuration
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("RELOAD", "true").lower() == "true"

    print(f"Starting EDSL Survey Generation Server on {host}:{port}")
    print(f"Reload mode: {reload}")
    print(f"API documentation: http://{host}:{port}/docs")

    uvicorn.run("app:app", host=host, port=port, reload=reload, log_level="info")
