# EDSL Extension Authoring Guide

This guide provides a comprehensive overview of how to author new extensions in the EDSL framework, based on analysis of the existing codebase.

## Table of Contents

1. [Overview](#overview)
2. [Core Components](#core-components)
3. [Service Definition Creation](#service-definition-creation)
4. [Service Implementation Patterns](#service-implementation-patterns)
5. [Factory Pattern Usage](#factory-pattern-usage)
6. [Service Loaders](#service-loaders)
7. [Testing Extensions](#testing-extensions)
8. [Best Practices](#best-practices)
9. [Complete Example](#complete-example)

## Overview

The EDSL extensions system provides a framework for creating external services that integrate seamlessly with the EDSL ecosystem. Extensions are built around:

- **Service Definitions**: Structured specifications of service interfaces
- **Service Implementations**: The actual logic that executes when services are called
- **Service Registration**: Integration with FastAPI routers and the EDSL service registry
- **Service Discovery**: Mechanisms for loading and accessing services

## Core Components

### 1. Service Definition Framework (`authoring.py`)

The foundation of extension authoring is the `ServiceDefinition` class and its supporting classes:

```python
from edsl.extensions.authoring import (
    ServiceDefinition, 
    ParameterDefinition, 
    CostDefinition, 
    ReturnDefinition
)
```

**Key classes:**
- `ServiceDefinition`: Main service specification
- `ParameterDefinition`: Input parameter specifications
- `CostDefinition`: Cost structure and pricing
- `ReturnDefinition`: Output value specifications

### 2. Service Registration (`register_service`)

Services are registered using the `register_service` decorator:

```python
from edsl.extensions.authoring import register_service

@register_service(router, "service_name", service_definition)
async def service_implementation(...):
    # Implementation logic
    pass
```

### 3. Service Loading (`service_loaders.py`)

Two main patterns for loading service configurations:
- `GithubYamlLoader`: Load from YAML files in GitHub repositories
- `APIServiceLoader`: Load from API endpoints

## Service Definition Creation

### Step 1: Define Parameters

```python
parameters = {
    "input_text": ParameterDefinition(
        type="str",
        required=True,
        description="The text to process"
    ),
    "max_length": ParameterDefinition(
        type="int",
        required=False,
        default_value=100,
        description="Maximum output length"
    )
}
```

**Supported parameter types:**
- Basic: `str`, `int`, `float`, `bool`, `list`, `dict`
- EDSL types: `Survey`, `Agent`, `Scenario` (auto-serialized)
- Complex: Any type in EDSL's type registry

### Step 2: Define Cost Structure

```python
cost = CostDefinition(
    unit="ep_credits",
    per_call_cost=50,
    variable_pricing_cost_formula="max_length * 0.1",  # Optional
    uses_client_ep_key=True
)
```

### Step 3: Define Return Values

```python
returns = {
    "processed_text": ReturnDefinition(
        type="str",
        description="The processed output"
    ),
    "metadata": ReturnDefinition(
        type="dict",
        description="Processing metadata"
    )
}
```

### Step 4: Create Service Definition

```python
service_def = ServiceDefinition(
    name="text_processor",
    description="Processes text with various transformations",
    parameters=parameters,
    cost=cost,
    service_returns=returns,
    endpoint="https://api.example.com/process"
)
```

## Service Implementation Patterns

### Pattern 1: Simple Function Implementation

```python
from fastapi import APIRouter
from edsl.extensions.authoring import register_service

router = APIRouter()

@register_service(router, "text_processor", service_def)
async def text_processor_impl(input_text: str, max_length: int, ep_api_token: str):
    """Implementation receives parameters as keyword arguments."""
    
    # Process the input
    result = input_text[:max_length]
    
    # Return dict matching service_returns definition
    return {
        "processed_text": result,
        "metadata": {
            "original_length": len(input_text),
            "truncated": len(input_text) > max_length
        }
    }
```

### Pattern 2: Complex Service with EDSL Objects

```python
@register_service(router, "create_survey", extensions["create_survey"])
async def create_survey_impl(overall_question: str, population: str, ep_api_token: str):
    """Service that returns EDSL objects."""
    
    # Create EDSL Survey object
    survey = Survey([
        QuestionFreeText(
            question_name="main_question",
            question_text=overall_question
        )
    ])
    
    # Return serialized EDSL object
    return {"survey": survey.to_dict()}
```

### Pattern 3: External API Integration

```python
import httpx

@register_service(router, "external_service", service_def)
async def external_service_impl(query: str, ep_api_token: str):
    """Service that calls external APIs."""
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://external-api.com/endpoint",
            json={"query": query},
            headers={"Authorization": f"Bearer {ep_api_token}"}
        )
        response.raise_for_status()
        data = response.json()
    
    return {"result": data["output"]}
```

## Factory Pattern Usage

The factory pattern (`factory/`) provides a standardized way to create FastAPI applications with extension support.

### Basic App Creation

```python
from edsl.extensions.factory.app_factory import create_app
from edsl.extensions.factory.config import Settings

# Custom configuration
settings = Settings(
    app_name="My Extension Service",
    version="1.0.0",
    api_prefix="/api/v1",
    debug=False
)

# Create app with router module
app = create_app("my_extension.router", settings)
```

### Router Module Structure

Create a module (e.g., `my_extension/router.py`) with:

```python
from fastapi import APIRouter
from edsl.extensions.authoring import register_service

router = APIRouter()

# Health check endpoint
@router.get("/health")
async def health_check():
    return {"status": "healthy"}

# Register your services
@register_service(router, "my_service", my_service_definition)
async def my_service_impl(...):
    # Implementation
    pass
```

### Configuration Options

The `Settings` class supports:

```python
class Settings(BaseSettings):
    app_name: str = "FastAPI Replit App"
    debug: bool = True
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: Optional[str] = None
    
    class Config:
        env_file = ".env"
```

## Service Loaders

### GitHub YAML Loader

Load service definitions from YAML files in GitHub repositories:

```python
from edsl.extensions.service_loaders import GithubYamlLoader

loader = GithubYamlLoader(
    repo_owner='your-org',
    repo_name='service-definitions',
    directory_path='services',
    github_token='your-token'  # Optional for private repos
)

services = loader.load_services()
```

**YAML service definition format:**

```yaml
name: my_service
description: Service description
endpoint: https://api.example.com/service

parameters:
  input_param:
    type: str
    required: true
    description: Input parameter

cost:
  unit: ep_credits
  per_call_cost: 25

service_returns:
  output:
    type: str
    description: Service output
```

### API Service Loader

Load from API endpoints returning JSON:

```python
from edsl.extensions.service_loaders import APIServiceLoader

loader = APIServiceLoader(base_url="https://api.example.com")
services = loader.load_services()
```

Expected API response format:

```json
{
  "services": [
    {
      "name": "service_name",
      "description": "Service description",
      "parameters": {...},
      "cost": {...},
      "service_returns": {...},
      "endpoint": "https://api.example.com/service"
    }
  ]
}
```

## Testing Extensions

### 1. Unit Testing Service Definitions

```python
def test_service_definition():
    service_def = ServiceDefinition.example()
    
    # Test serialization
    yaml_output = service_def.to_yaml()
    assert "name: create_survey" in yaml_output
    
    # Test deserialization
    restored = ServiceDefinition.from_yaml(yaml_output)
    assert restored == service_def
```

### 2. Testing Service Implementation

```python
import pytest
from fastapi.testclient import TestClient

def test_service_endpoint():
    client = TestClient(app)
    
    response = client.post(
        "/my_service",
        json={"input_text": "test"},
        headers={"Authorization": "Bearer test-token"}
    )
    
    assert response.status_code == 200
    assert "processed_text" in response.json()
```

### 3. Integration Testing

The codebase includes `test_service_router.py` for development testing:

```python
@router.post("/test_create_survey")
async def test_create_survey(request: dict):
    """Test endpoint for create_survey service."""
    # Mock implementation for testing
    pass
```

## Best Practices

### 1. Service Definition Design

- **Clear naming**: Use descriptive service and parameter names
- **Comprehensive descriptions**: Document all parameters and returns
- **Type consistency**: Use consistent type naming across services
- **Default values**: Provide sensible defaults for optional parameters

### 2. Error Handling

Use the provided exception hierarchy:

```python
from edsl.extensions.exceptions import (
    ServiceParameterValidationError,
    ServiceConnectionError,
    ServiceResponseError
)

try:
    # Service logic
    pass
except ValueError as e:
    raise ServiceParameterValidationError(f"Invalid input: {e}")
```

### 3. Authentication

Services automatically receive `ep_api_token` parameter:

```python
async def my_service(param1: str, ep_api_token: str):
    # Use ep_api_token for authenticated calls
    headers = {"Authorization": f"Bearer {ep_api_token}"}
```

### 4. Cost Calculation

Implement variable pricing formulas:

```python
cost = CostDefinition(
    unit="ep_credits",
    per_call_cost=10,
    variable_pricing_cost_formula="len(input_text) * 0.01"
)
```

### 5. Output Validation

Services automatically validate outputs against `service_returns`:

```python
# This will be validated automatically
return {
    "result": "processed output",
    "metadata": {"processing_time": 1.5}
}
```

## Complete Example

Here's a complete example of creating a text analysis extension:

### 1. Service Definition

```python
# text_analyzer_service.py
from edsl.extensions.authoring import (
    ServiceDefinition, ParameterDefinition, 
    CostDefinition, ReturnDefinition
)

text_analyzer_def = ServiceDefinition(
    name="text_analyzer",
    description="Analyzes text for sentiment and key metrics",
    parameters={
        "text": ParameterDefinition(
            type="str",
            required=True,
            description="Text to analyze"
        ),
        "include_keywords": ParameterDefinition(
            type="bool",
            required=False,
            default_value=True,
            description="Whether to extract keywords"
        )
    },
    cost=CostDefinition(
        unit="ep_credits",
        per_call_cost=15,
        variable_pricing_cost_formula="len(text) * 0.001",
        uses_client_ep_key=True
    ),
    service_returns={
        "sentiment": ReturnDefinition(
            type="str",
            description="Sentiment: positive, negative, or neutral"
        ),
        "confidence": ReturnDefinition(
            type="float",
            description="Confidence score (0-1)"
        ),
        "keywords": ReturnDefinition(
            type="list",
            description="Extracted keywords (if requested)"
        )
    },
    endpoint="https://api.textanalyzer.com/analyze"
)
```

### 2. Router Implementation

```python
# router.py
from fastapi import APIRouter
from edsl.extensions.authoring import register_service
from .text_analyzer_service import text_analyzer_def
import re

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@register_service(router, "text_analyzer", text_analyzer_def)
async def text_analyzer_impl(
    text: str, 
    include_keywords: bool, 
    ep_api_token: str
):
    """Text analysis implementation."""
    
    # Simple sentiment analysis (replace with real implementation)
    positive_words = ["good", "great", "excellent", "amazing"]
    negative_words = ["bad", "terrible", "awful", "horrible"]
    
    text_lower = text.lower()
    pos_count = sum(word in text_lower for word in positive_words)
    neg_count = sum(word in text_lower for word in negative_words)
    
    if pos_count > neg_count:
        sentiment = "positive"
        confidence = min(0.9, 0.5 + (pos_count - neg_count) * 0.1)
    elif neg_count > pos_count:
        sentiment = "negative"
        confidence = min(0.9, 0.5 + (neg_count - pos_count) * 0.1)
    else:
        sentiment = "neutral"
        confidence = 0.5
    
    # Extract keywords if requested
    keywords = []
    if include_keywords:
        words = re.findall(r'\b\w+\b', text.lower())
        # Simple keyword extraction (get unique words > 4 chars)
        keywords = list(set(word for word in words if len(word) > 4))[:10]
    
    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "keywords": keywords
    }
```

### 3. Application Setup

```python
# app.py
from edsl.extensions.factory.app_factory import create_app
from edsl.extensions.factory.config import Settings

settings = Settings(
    app_name="Text Analyzer Service",
    version="1.0.0",
    api_prefix="/api/v1"
)

app = create_app("router", settings)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
```

### 4. YAML Service Definition

```yaml
# text_analyzer.yaml
name: text_analyzer
description: Analyzes text for sentiment and key metrics
endpoint: https://api.textanalyzer.com/analyze

parameters:
  text:
    type: str
    required: true
    description: Text to analyze
  include_keywords:
    type: bool
    required: false
    default_value: true
    description: Whether to extract keywords

cost:
  unit: ep_credits
  per_call_cost: 15
  variable_pricing_cost_formula: "len(text) * 0.001"
  uses_client_ep_key: true

service_returns:
  sentiment:
    type: str
    description: "Sentiment: positive, negative, or neutral"
  confidence:
    type: float
    description: "Confidence score (0-1)"
  keywords:
    type: list
    description: "Extracted keywords (if requested)"
```

### 5. Usage

```python
# Using the extension
from edsl.extensions import extensions

# Call the service
analyzer = extensions["text_analyzer"]
result = analyzer(
    text="This is a great product!",
    include_keywords=True
)

print(f"Sentiment: {result['sentiment']}")
print(f"Confidence: {result['confidence']}")
print(f"Keywords: {result['keywords']}")
```

This comprehensive guide covers all aspects of authoring new extensions in the EDSL framework, from basic service definitions to complete implementations with testing and deployment patterns.