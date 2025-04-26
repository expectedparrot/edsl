from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx
import traceback
from collections import UserDict

from .authoring import ServiceDefinition
from .dependencies import get_http_client


## TODO: This should be a list of all the services.

services_list: List[ServiceDefinition] = [ServiceDefinition.example(), 
                                          ServiceDefinition.example_with_running()]

# Define the ServiceRegistry class
class ServiceRegistry(UserDict):
    """A container for managing service definitions, behaving like a dictionary."""
    def __init__(self, initial_services: List[ServiceDefinition]):
        super().__init__()
        for service in initial_services:
            self.data[service.name] = service

# Instantiate the ServiceRegistry
services_registry = ServiceRegistry(services_list)

class ServiceRequest(BaseModel):
    service: str
    params: Dict[str, Any]
    ep_api_token: Optional[str] = None

router = APIRouter()

class ExternalServiceHandler:
    """Handles requests to external services defined by ServiceDefinition."""
    def __init__(
        self,
        service_def: ServiceDefinition,
        http_client: httpx.AsyncClient,
        ep_api_token: Optional[str] = None
    ):
        self.service_def = service_def
        self.http_client = http_client
        self.ep_api_token = ep_api_token

        if not hasattr(self.service_def, 'endpoint') or not self.service_def.endpoint:
            raise HTTPException(
                status_code=500,
                detail=f"Service '{self.service_def.name}' is missing the required 'endpoint' configuration."
            )
        self.endpoint_url = self.service_def.endpoint

    async def handle_request(self, params: Dict[str, Any]):
        """Forwards the request to the external endpoint."""
        headers = {"Content-Type": "application/json"}
        if self.ep_api_token:
            headers["Authorization"] = f"Bearer {self.ep_api_token}"

        # Prepare the payload - REMOVED token addition here
        payload = params.copy()
        # REMOVED: if self.ep_api_token:
        # REMOVED:     payload["ep_api_token"] = self.ep_api_token

        try:
            # Send the original params, not the modified payload
            response = await self.http_client.post(self.endpoint_url, json=params, headers=headers)

            if response.status_code >= 400:
                 try:
                     error_detail = response.json()
                 except Exception:
                     error_detail = response.text
                 raise HTTPException(status_code=response.status_code, detail=error_detail)

            return response.json()

        except httpx.RequestError as e:
            print(f"External service request failed for {self.service_def.name} at {self.endpoint_url}: {e}")
            raise HTTPException(status_code=503, detail=f"Error connecting to external service '{self.service_def.name}': {str(e)}")
        except Exception as e:
            print(f"Error processing external service response for {self.service_def.name}: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error processing response from external service '{self.service_def.name}'.")


# --- API Routes ---

@router.post("/service/")
async def service(
    request: ServiceRequest,
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """
    General service endpoint that forwards requests to external services.
    """
    try:
        service_name = request.service
        actual_ep_api_token = request.ep_api_token

        if service_name not in services_registry:
            raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")

        service_def = services_registry[service_name]

        # Validate parameters using the method on ServiceDefinition
        try:
            service_def.validate_call_parameters(request.params)
        except ValueError as e:
            # Convert validation errors to HTTP 400 Bad Request
            raise HTTPException(status_code=400, detail=str(e))

        # Use the handler class
        handler = ExternalServiceHandler(
            service_def=service_def,
            http_client=http_client,
            ep_api_token=actual_ep_api_token
        )

        return await handler.handle_request(params=request.params)

    except Exception as e:
        # Re-raise HTTPExceptions directly
        if isinstance(e, HTTPException):
            raise e
        # Log other exceptions and return a generic 500 error
        print(f"Error processing service request: {type(e).__name__} - {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/services")
async def list_services():
    """List all available services using the imported ServiceDefinition."""
    services_info_list = []
    for name, service_def in services_registry.items():
        services_info_list.append(service_def.to_dict())

    return {"services": services_info_list}

# Note: The root ("/") endpoint from the original app.py is omitted here,
# as the main application will likely have its own root endpoint. 