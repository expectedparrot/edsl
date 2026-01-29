# EDSL Services Module

## Purpose

A plugin framework for creating, hosting, and consuming remote services that extend EDSL types (ScenarioList, AgentList, etc.). Enables third-party extensions without modifying core EDSL code.

## Architecture Overview

```
EDSL Types (ScenarioList, AgentList, etc.)
    │
    ↓ (metaclass injection via ServiceEnabledMeta)

Client-Side Proxies (service_connector.py)
    │
    ↓ HTTP POST/GET

FastAPI Server (service_hosting.py)
    │
    ↓
ExternalService Instances
```

## Key Files

| File | Role |
|------|------|
| `external_service.py` | Base class for defining services; `@method_type` decorator |
| `service_hosting.py` | Server-side FastAPI app generator |
| `service_connector.py` | Client-side: metaclass, proxies, service discovery |
| `service_client.py` | HTTP client and lightweight proxy classes |
| `__init__.py` | Lazy-loads FastAPI deps; exports public API |

## Core Concepts

### ExternalService (external_service.py)

Base class for all services. Required fields:
- `service_name: str` - unique identifier
- `extends: List[Type]` - EDSL types this service enhances

### Method Types

```python
from edsl.services import method_type, MethodType

@method_type(MethodType.CLASSMETHOD)  # Creates new data, no instance needed
@method_type(MethodType.INSTANCE)     # Operates on existing instance
@method_type(MethodType.STATIC)       # Utility, no state
```

### ServiceEnabledMeta (service_connector.py)

Metaclass that intercepts `__getattr__` on EDSL types to enable transparent service access:
```python
sl = ScenarioList([...])
result = sl.firecrawl.scrape(url="...")  # Proxied to remote service
```

The `extends` field filters which services are visible on which types.

### Proxy Chain

1. `ServiceProxy` - class-level service access (for classmethods)
2. `InstanceServiceProxy` - instance-level, auto-serializes bound object
3. `MethodProxy` / `InstanceMethodProxy` - actual method invocation

## Usage Patterns

### Creating a Service

```python
from edsl.services import ExternalService, method_type, MethodType
from edsl.scenarios import ScenarioList

class MyService(ExternalService):
    service_name = "myservice"
    extends = [ScenarioList]

    @method_type(MethodType.INSTANCE)
    def process(self, instance: ScenarioList) -> ScenarioList:
        # instance is auto-passed when called as sl.myservice.process()
        return instance
```

### Hosting a Service

```python
from edsl.services import ServiceAPI

api = ServiceAPI()
api.register_service(MyService)
app = api.create_app(title="My API")
# Run with: uvicorn server:app
```

### Consuming a Service

```python
from edsl.services import ServiceEnabledMeta

ServiceEnabledMeta.configure(base_url="http://localhost:8008")
sl = ScenarioList([...])
result = sl.myservice.process()  # Transparent remote call
```

## Serialization

- EDSL objects serialized via `to_dict()` / `from_dict()`
- Pydantic models via `model_dump()`
- Recursive handling for nested structures
- `edsl_class_name` marker used for deserialization dispatch

## Service Discovery

Services registered via Python entry points:
```toml
[project.entry-points."edsl.services"]
myservice = "my_package.service:MyService"
```

See `services_runner/registry.py` for discovery logic.

## Key Design Decisions

- **Lazy loading**: Service info fetched on first access, cached
- **Graceful degradation**: Services invisible if server unavailable
- **Optional FastAPI**: Client-only usage works without FastAPI installed
- **Event integration**: Services can return events (integrates with GitMixin)

## Gotchas

- The `_suppress_status_output` flag controls spinner output during server ops
- Multiple caches exist: `_service_cache`, `_all_services_cache`, `_valid_service_names`
