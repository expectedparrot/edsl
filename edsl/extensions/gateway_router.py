from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx
import traceback

# Import the actual definitions from authoring.py
from .authoring import ServiceDefinition, ParameterDefinition

# Import the dependency function from dependencies.py
from .dependencies import get_http_client 

# Removed Placeholder ServiceDefinition and ParameterDefinition classes

# Define services directly using the imported ServiceDefinition
# Ensure the example() method in authoring.py provides a valid ServiceDefinition

## TODO: This should be a list of all the services. 
example_service = ServiceDefinition.example() 
services_list: List[ServiceDefinition] = [example_service]
services_config_objects: Dict[str, ServiceDefinition] = {service.name: service for service in services_list}

# --- Request Model ---
class ServiceRequest(BaseModel):
    service: str
    params: Dict[str, Any]
    ep_api_token: Optional[str] = None

# --- Router Definition ---
router = APIRouter()

# --- Helper Functions ---

def validate_params(service_name: str, params: Dict[str, Any]):
    """Validate that all required parameters are present and of the correct type"""
    if service_name not in services_config_objects:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    
    service_def = services_config_objects[service_name]
    service_params = service_def.parameters
    
    for param_name, param_def in service_params.items():
        if param_def.required and param_name not in params:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required parameter: {param_name}"
            )
        
        if param_name in params:
            expected_type = param_def.type.lower()
            actual_value = params[param_name]
            type_mismatch = False
            # Basic type validation (can be expanded)
            if expected_type in ("string", "str") and not isinstance(actual_value, str):
                type_mismatch = True
            elif expected_type in ("int", "integer") and not isinstance(actual_value, int):
                type_mismatch = True
            elif expected_type in ("number", "float") and not isinstance(actual_value, (int, float)):
                type_mismatch = True
            elif expected_type in ("bool", "boolean") and not isinstance(actual_value, bool):
                type_mismatch = True
            elif expected_type in ("list", "array") and not isinstance(actual_value, list):
                type_mismatch = True
            elif expected_type in ("dict", "object") and not isinstance(actual_value, dict):
                type_mismatch = True

            if type_mismatch:
                 raise HTTPException(
                     status_code=400,
                     detail=f"Parameter '{param_name}' has incorrect type. Expected '{param_def.type}', got '{type(actual_value).__name__}'"
                 )

async def handle_external_service(
    service_def: ServiceDefinition, 
    params: Dict[str, Any], 
    http_client: httpx.AsyncClient, # Get client via dependency injection
    ep_api_token: Optional[str] = None
):
    """Handle external service calls by forwarding the request to the external endpoint defined in ServiceDefinition"""
    
    # Use 'endpoint' attribute from authoring.ServiceDefinition
    if not hasattr(service_def, 'endpoint') or not service_def.endpoint:
        raise HTTPException(
            status_code=500, 
            detail=f"Service '{service_def.name}' is missing the required 'endpoint' configuration."
        )
    
    endpoint_url = service_def.endpoint # Use the correct attribute name
    headers = {"Content-Type": "application/json"}
    if ep_api_token:
        headers["Authorization"] = f"Bearer {ep_api_token}"

    try:
        response = await http_client.post(endpoint_url, json=params, headers=headers)
        
        if response.status_code >= 400:
             try:
                 error_detail = response.json()
             except Exception:
                 error_detail = response.text
             raise HTTPException(status_code=response.status_code, detail=error_detail)

        return response.json()
    
    # Update exception type for httpx
    except httpx.RequestError as e:
        print(f"External service request failed for {service_def.name} at {endpoint_url}: {e}")
        raise HTTPException(status_code=503, detail=f"Error connecting to external service '{service_def.name}': {str(e)}")
    except Exception as e: 
        print(f"Error processing external service response for {service_def.name}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing response from external service '{service_def.name}'.")

# --- API Routes ---

@router.post("/service/")
async def service(
    request: ServiceRequest, 
    # Explicitly use the dependency provider function
    http_client: httpx.AsyncClient = Depends(get_http_client) 
):
    """
    General service endpoint that forwards requests to external services.
    """
    try:
        service_name = request.service
        actual_ep_api_token = request.ep_api_token 

        if service_name not in services_config_objects:
            raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
        
        service_def = services_config_objects[service_name]
        validate_params(service_name, request.params)
        
        return await handle_external_service(
            service_def=service_def,
            params=request.params,
            http_client=http_client, # Pass the injected client
            ep_api_token=actual_ep_api_token
        )
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Error processing service request: {type(e).__name__} - {e}") 
        traceback.print_exc() 
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/services")
async def list_services():
    """List all available services using the imported ServiceDefinition."""
    services_info_list = []
    for name, service_def in services_config_objects.items():
        # Use to_dict() method from authoring.ServiceDefinition
        services_info_list.append(service_def.to_dict())
    
    return {"services": services_info_list}

# Note: The root ("/") endpoint from the original app.py is omitted here, 
# as the main application will likely have its own root endpoint. 