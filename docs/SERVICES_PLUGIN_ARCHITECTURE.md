# EDSL Services Plugin Architecture

EDSL supports a plugin architecture for external services using Python entry points. This allows services to be distributed as separate packages, reducing the size of the core `edsl` package and enabling independent versioning.

## Quick Start

### Installing Services

```bash
# Install the standard service collection
pip install edsl-services

# Install with specific service dependencies
pip install edsl-services[firecrawl]
pip install edsl-services[exa,embeddings]

# Install everything
pip install edsl-services[all]
```

### Using Services

Services are automatically discovered and available through the accessor pattern:

```python
from edsl import ScenarioList

# Use the exa service for web search
scenarios = ScenarioList.exa.search("AI researchers at Stanford")

# Use firecrawl to scrape a webpage
scenarios = ScenarioList.from_url("https://example.com")
```

Or through the dispatch API:

```python
from edsl.services import dispatch

pending = dispatch("exa", {"query": "AI researchers"})
result = pending.result()  # Returns ScenarioList
```

## How It Works

### Entry Point Discovery

EDSL discovers services through Python's entry points mechanism. When you install a package that declares services in the `edsl.services` group, they are automatically available:

```toml
# In pyproject.toml of a service package
[project.entry-points."edsl.services"]
myservice = "mypackage.services:MyService"
```

### Discovery Order

1. **Built-in services** from `edsl.services.builtin` are loaded first
2. **Entry point services** are discovered and registered if not already present
3. Built-in services take precedence over entry points with the same name

### Lazy Loading

Services are loaded lazily - the discovery only happens when you first access the service registry or use a service. This keeps import times fast.

## Creating a Custom Service Package

### 1. Define Your Service

```python
# mypackage/services.py
from edsl.services import ExternalService, ServiceRegistry

@ServiceRegistry.register("myservice")
class MyService(ExternalService):
    name = "myservice"
    description = "My custom service"
    
    @classmethod
    def create_task(cls, query: str, **kwargs) -> dict:
        """Prepare task parameters (runs on client)."""
        return {"query": query, **kwargs}
    
    @classmethod
    def execute(cls, params: dict, keys: dict) -> dict:
        """Execute the service (runs on worker).
        
        Args:
            params: Task parameters from create_task
            keys: API keys/credentials from KEYS
            
        Returns:
            Raw result dict (will be passed to parse_result)
        """
        # Your implementation here
        api_key = keys.get("MY_API_KEY")
        results = call_external_api(params["query"], api_key)
        return {"rows": results}
    
    @classmethod
    def parse_result(cls, result: dict):
        """Convert raw result to EDSL objects (runs on client)."""
        from edsl.scenarios import ScenarioList
        return ScenarioList.from_list_of_dicts(result["rows"])
```

### 2. Configure Entry Points

```toml
# pyproject.toml
[project]
name = "my-edsl-services"
dependencies = ["edsl>=1.0"]

[project.entry-points."edsl.services"]
myservice = "mypackage.services:MyService"

[project.optional-dependencies]
# Declare external dependencies your service needs
myservice = ["some-api-client>=1.0"]
```

### 3. Publish Your Package

```bash
# Build and publish
pip install build twine
python -m build
twine upload dist/*
```

### 4. Users Install and Use

```bash
pip install my-edsl-services[myservice]
```

```python
from edsl import ScenarioList

# Your service is automatically available
result = ScenarioList.myservice.search("query")
```

## Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EDSL Client                             │
│                                                                 │
│  ┌───────────────┐     ┌────────────────┐     ┌──────────────┐ │
│  │ ServiceRegistry│────▶│ TaskDispatcher │────▶│ RemoteServer │ │
│  │   (discovery)  │     │   (routing)    │     │   (queue)    │ │
│  └───────────────┘     └────────────────┘     └──────────────┘ │
│         │                                              │        │
│         ▼                                              ▼        │
│  ┌───────────────┐                          ┌──────────────────┐│
│  │ Entry Points  │                          │  UnifiedWorker   ││
│  │  (discovery)  │                          │   (execution)    ││
│  └───────────────┘                          └──────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

- **ServiceRegistry**: Discovers and manages service classes
- **TaskDispatcher**: Routes service requests to the appropriate queue
- **RemoteServer**: Task queue (local or remote)
- **UnifiedWorker**: Executes tasks using service `execute()` methods

### Execution Model

1. **Client calls service** via accessor or dispatch
2. **ServiceRegistry.get()** returns the service class
3. **create_task()** prepares parameters
4. **TaskDispatcher** sends to queue
5. **UnifiedWorker** claims and executes task
6. **execute()** runs with credentials
7. **parse_result()** converts response to EDSL objects

## Configuration

### API Keys

Services access credentials through the `KEYS` object:

```python
@classmethod
def execute(cls, params: dict, keys: dict) -> dict:
    api_key = keys.get("MY_SERVICE_API_KEY")
    # Use the key...
```

Set keys via environment variables or the EDSL config:

```python
from edsl.services import KEYS
KEYS.set("MY_SERVICE_API_KEY", "sk-...")
```

### Local vs Remote Execution

By default, services run locally. To use remote workers:

```python
from edsl.services import set_default_server

# Use Expected Parrot's remote service
set_default_server("https://services.expectedparrot.com")
```

## Best Practices

### 1. Keep `execute()` Minimal

The `execute()` method should have minimal EDSL dependencies since it runs on workers that may not have the full EDSL package:

```python
# Good - minimal dependencies
@classmethod
def execute(cls, params: dict, keys: dict) -> dict:
    import requests  # Standard library or small deps only
    resp = requests.get(...)
    return {"data": resp.json()}

# Bad - importing EDSL types
@classmethod
def execute(cls, params: dict, keys: dict) -> dict:
    from edsl.scenarios import Scenario  # Don't do this
    ...
```

### 2. Handle Missing Dependencies Gracefully

```python
@classmethod
def execute(cls, params: dict, keys: dict) -> dict:
    try:
        import optional_package
    except ImportError:
        raise ImportError(
            "This service requires 'optional_package'. "
            "Install with: pip install my-edsl-services[myservice]"
        )
```

### 3. Document Required Keys

```python
class MyService(ExternalService):
    name = "myservice"
    description = "My service - requires MY_API_KEY environment variable"
    
    @classmethod
    def get_required_keys(cls) -> list[str]:
        return ["MY_API_KEY"]
```

## Migration from Built-in Services

The built-in services in `edsl.services.builtin` will continue to work, but are deprecated. To migrate:

1. Install `edsl-services`:
   ```bash
   pip install edsl-services
   ```

2. Update imports (optional - old imports still work):
   ```python
   # Old (deprecated)
   from edsl.services.builtin import WikipediaService
   
   # New (preferred)
   from edsl.services import ServiceRegistry
   service = ServiceRegistry.get("wikipedia")
   ```

3. Use the accessor pattern:
   ```python
   # Best approach - no direct service imports needed
   from edsl import ScenarioList
   result = ScenarioList.wikipedia.search("Python programming")
   ```

