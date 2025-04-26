# test_service_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import Survey to create the example response
from edsl import Survey

# Define the expected input model for the test service
# based on ServiceDefinition.example()
class TestCreateSurveyRequest(BaseModel):
    overall_question: str
    population: str
    num_questions: Optional[int] = 10 # Match default from ServiceDefinition

# Define the expected input model for the test run service
# based on ServiceDefinition.example_with_running()
# We'll accept a dictionary for the survey for simplicity in the test endpoint
class TestRunSurveyRequest(BaseModel):
    survey: Dict[str, Any] # Represents the serialized Survey object

# Create the router
router = APIRouter()

@router.post("/test_create_survey", tags=["Test Services"])
async def create_survey_endpoint(request_body: TestCreateSurveyRequest) -> Dict[str, Any]:
    """
    Simulated external service endpoint for 'create_survey'.
    Receives forwarded parameters and returns a dummy success response.
    """
    print(f"--- Test Service Endpoint Received Request ---")
    print(f"Received data: {request_body.model_dump_json(indent=2)}")
    
    # Simulate processing and return a response similar to what an external service might
    # Create an example survey and format the response as expected
    example_survey = Survey.example()
    response_data = {
        "survey": example_survey.to_dict()
    }
    
    print(f"--- Test Service Endpoint Sending Response ---")
    print(f"Response data: {response_data}")
    
    return response_data 

@router.post("/test_run_survey", tags=["Test Services"])
async def run_survey_endpoint(request_body: TestRunSurveyRequest) -> Dict[str, Any]:
    """
    Simulated external service endpoint for 'run_survey'.
    Receives forwarded parameters and returns a dummy success response.
    """
    print(f"--- Test Service Endpoint Received Request ---")
    print(f"Received survey data (structure): {request_body.model_dump_json(indent=2)}")

    # Simulate processing and return a dummy 'results' dictionary
    from edsl import Survey
    survey = Survey.from_dict(request_body.survey)
    results = survey.run()
    response_data = {
        "results": results.to_dict()
        }

    print(f"--- Test Service Endpoint Sending Response ---")
    print(f"Response data: {response_data}")

    return response_data 