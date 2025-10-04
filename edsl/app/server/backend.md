# EDSL App FastAPI Backend Specification

## Overview

A FastAPI backend service that allows users to push EDSL applications to a server and execute them remotely. The service provides REST endpoints for app management and execution.

## Architecture

### Core Components

1. **App Storage**: Apps are stored server-side with unique identifiers
2. **Execution Engine**: Handles running apps with user-provided parameters
3. **Authentication**: Optional API key-based authentication for app management
4. **Result Caching**: Cache execution results for performance

### Data Models

```python
class AppMetadata(BaseModel):
    app_id: str
    name: str
    description: Optional[str]
    application_type: str
    created_at: datetime
    parameters: list[dict]  # [(param_name, param_type, param_description), ...]
    available_formatters: list[str]

class AppExecutionRequest(BaseModel):
    app_id: str
    answers: dict[str, Any]
    formatter_name: Optional[str] = None

class AppExecutionResponse(BaseModel):
    execution_id: str
    status: str  # "running", "completed", "failed"
    result: Optional[Any] = None
    error: Optional[str] = None
```

## API Endpoints

### App Management

#### `POST /apps`
Push a new app to the server
- **Request**: Multipart form with serialized AppBase object
- **Response**: `{"app_id": str, "message": str}`
- **Authentication**: Required

#### `GET /apps`
List all available apps
- **Response**: `list[AppMetadata]`
- **Authentication**: Optional (may filter by user)

#### `GET /apps/{app_id}`
Get app metadata and parameters
- **Response**: `AppMetadata`
- **Authentication**: Optional

#### `DELETE /apps/{app_id}`
Remove an app from the server
- **Response**: `{"message": str}`
- **Authentication**: Required (owner only)

### App Execution

#### `POST /apps/{app_id}/execute`
Execute an app with provided parameters
- **Request**: `AppExecutionRequest`
- **Response**: `AppExecutionResponse`
- **Authentication**: Optional

#### `GET /executions/{execution_id}`
Get execution status and results
- **Response**: `AppExecutionResponse`
- **Authentication**: Optional

#### `GET /apps/{app_id}/parameters`
Get required parameters for an app
- **Response**: `{"parameters": list[dict]}`
- **Authentication**: None

### Health & Status

#### `GET /health`
Service health check
- **Response**: `{"status": "healthy", "version": str}`

#### `GET /stats`
Server statistics
- **Response**: `{"total_apps": int, "total_executions": int, "uptime": str}`

## Implementation Details

### Storage Backend
- **Development**: SQLite database
- **Production**: PostgreSQL with Redis for caching
- **App serialization**: Store `AppBase.to_dict()` output as JSON

### Execution Model
- **Synchronous**: Direct execution for simple apps
- **Asynchronous**: Background tasks for long-running apps using Celery/RQ
- **Resource limits**: Timeout and memory constraints per execution

### Security Considerations
- Input validation for all app parameters
- Sandboxed execution environment
- Rate limiting per client
- Optional app visibility controls (public/private)

### Error Handling
- Standardized error responses with codes
- Detailed logging for debugging
- Graceful degradation for service issues

## Client Integration

The existing `AppBase.push()` method can be extended to work with this backend:

```python
def push_to_server(self, server_url: str, api_key: Optional[str] = None):
    """Push app to FastAPI server instead of EDSL cloud"""
    # Implementation details...

@classmethod
def pull_from_server(cls, server_url: str, app_id: str):
    """Pull app from FastAPI server"""
    # Implementation details...
```

## Example Usage

### Server Side
```bash
# Start the FastAPI server
uvicorn edsl.app.backend:app --host 0.0.0.0 --port 8000
```

### Client Side
```python
# Push an app
app = App(...)
app_id = app.push_to_server("http://localhost:8000")

# Execute remotely
import requests
response = requests.post(f"http://localhost:8000/apps/{app_id}/execute",
                        json={"answers": {"param1": "value1"}})
result = response.json()["result"]
```

## Future Enhancements

- WebSocket support for real-time execution updates
- App versioning and rollback capabilities
- Collaborative features (sharing, forking)
- Integration with existing EDSL cloud infrastructure
- Docker containerization for easy deployment