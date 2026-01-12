"""
ServiceAccessor: Generic accessor that wraps any registered service.

Replaces hand-coded accessor classes (FirecrawlAccessor, ExaAccessor, etc.)
with a single generic implementation that works with any service.

Example:
    # Instead of hand-coded accessor:
    class FirecrawlAccessor:
        def scrape(self, url, **kwargs):
            pending = dispatch("firecrawl", {"operation": "scrape", "url": url, ...})
            return pending.result()
    
    # We have a generic accessor that works for any service:
    accessor = ServiceAccessor("firecrawl", instance)
    accessor.scrape(url)  # Dynamically dispatches to firecrawl service
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.scenarios import ScenarioList


class ServiceAccessor:
    """
    Generic accessor that wraps a registered service.
    
    Provides a clean API for calling service methods:
        sl.firecrawl.scrape(url)
        sl.exa.search(query)
    
    The accessor:
    1. Checks dependencies are available (prompts if missing)
    2. Dispatches the task to the service
    3. Returns the parsed result
    
    Attributes:
        service_name: Name of the service
        instance: The EDSL object this accessor is attached to (e.g., ScenarioList)
    """
    
    def __init__(self, service_name: str, instance: Any = None):
        """
        Create an accessor for a service.
        
        Args:
            service_name: Name of the registered service
            instance: Optional EDSL object (ScenarioList, Results, etc.)
        """
        self._service_name = service_name
        self._instance = instance
        
        # Cache service class reference
        from .registry import ServiceRegistry
        self._service_class = ServiceRegistry.get(service_name)
        if self._service_class is None:
            raise ValueError(f"Service '{service_name}' not found in registry")
    
    def __repr__(self) -> str:
        from .registry import ServiceRegistry
        info = ServiceRegistry.info(self._service_name)
        
        if info:
            desc = info.get("description", "No description")
            deps = info.get("dependencies", [])
            keys = info.get("required_keys", [])
            
            # Get available methods/operations
            methods = self._get_available_methods()
            
            lines = [
                f"{self._service_name.title()}Accessor - {desc}",
                "",
            ]
            
            if methods:
                lines.append("Methods: " + ", ".join(f".{m}()" for m in methods))
            
            lines.append("Dependencies: " + (", ".join(deps) if deps else "None"))
            lines.append("Required keys: " + (", ".join(keys) if keys else "None"))
            
            return "\n".join(lines)
        
        return f"<ServiceAccessor({self._service_name})>"
    
    def _get_available_methods(self) -> List[str]:
        """Get available methods for this service."""
        from .registry import ServiceRegistry
        
        methods = []
        
        # First check for operation schemas in registry (preferred source)
        operations = ServiceRegistry.get_operations(self._service_name)
        if operations:
            methods.extend(operations.keys())
        
        # Check for OPERATIONS attribute on service class
        if not methods and hasattr(self._service_class, "OPERATIONS"):
            methods.extend(self._service_class.OPERATIONS)
        
        # Check for common method patterns in docstring
        if not methods and self._service_class.__doc__:
            doc = self._service_class.__doc__
            # Look for "- method_name:" pattern in docstring
            import re
            pattern = r'^\s*-\s*(\w+):'
            for match in re.finditer(pattern, doc, re.MULTILINE):
                methods.append(match.group(1))
        
        # Fallback: check for documented operations in class
        if not methods:
            # Common service method names
            common_methods = [
                'scrape', 'crawl', 'search', 'extract', 'parse',
                'load', 'get', 'query', 'fetch', 'generate',
                'describe', 'filter', 'edit', 'export', 'transcript',
            ]
            # Check if service mentions these in docstring
            if self._service_class.__doc__:
                doc_lower = self._service_class.__doc__.lower()
                for method in common_methods:
                    if method in doc_lower:
                        methods.append(method)
        
        return methods
    
    def _repr_html_(self) -> str:
        from .registry import ServiceRegistry
        info = ServiceRegistry.info(self._service_name)
        
        if info:
            desc = info.get("description", "No description")
            deps = info.get("dependencies", [])
            keys = info.get("required_keys", [])
            methods = self._get_available_methods()
            
            methods_html = ", ".join(f"<code>.{m}()</code>" for m in methods) if methods else "Any method name is forwarded to the service"
            deps_html = "<br>".join(f"• {d}" for d in deps) if deps else "None"
            keys_html = "<br>".join(f"• {k}" for k in keys) if keys else "None"
            
            return f"""
<div style="font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9;">
<b style="color: #3498db;">{self._service_name.title()}Accessor</b><br>
{desc}<br><br>
<b>Methods:</b> {methods_html}<br><br>
<b>Dependencies:</b><br>{deps_html}<br><br>
<b>Required Keys:</b><br>{keys_html}
</div>
"""
        return f"<code>&lt;ServiceAccessor({self._service_name})&gt;</code>"
    
    def _dispatch_batch(
        self,
        base_params: dict,
        batch_key: str,
        batch_items: list,
        result_kwargs: dict,
        verbose: bool = True,
    ):
        """
        Dispatch multiple tasks (one per item) and combine results.
        
        This provides better parallelism than processing all items in one task.
        
        Args:
            base_params: Common parameters for all tasks
            batch_key: The parameter name for the item (e.g., "url", "query")
            batch_items: List of items to process
            result_kwargs: kwargs to pass to pending.result()
            verbose: Whether to show progress
            
        Returns:
            Combined result (typically a ScenarioList)
        """
        from . import dispatch
        from .registry import ServiceRegistry
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        if verbose:
            print(f"[{self._service_name}] Dispatching {len(batch_items)} tasks...")
        
        # Dispatch all tasks
        pending_tasks = []
        for i, item in enumerate(batch_items):
            task_params = {**base_params, batch_key: item}
            pending = dispatch(self._service_name, task_params)
            pending_tasks.append((item, pending))
            if verbose:
                # Show abbreviated item for URLs
                item_display = item[:50] + "..." if len(str(item)) > 50 else item
                print(f"  [{i+1}/{len(batch_items)}] Task {pending.task_id[:8]}... for {item_display}")
        
        # Collect results as they complete
        results = []
        errors = []
        
        for item, pending in pending_tasks:
            try:
                result = pending.result(**result_kwargs)
                results.append(result)
            except Exception as e:
                errors.append((item, str(e)))
                if verbose:
                    print(f"  Error for {item}: {e}")
        
        if verbose:
            print(f"[{self._service_name}] Completed: {len(results)} succeeded, {len(errors)} failed")
        
        # Combine results
        # Most services return ScenarioList, so concatenate them
        if results:
            combined = results[0]
            for r in results[1:]:
                if hasattr(combined, '__add__'):
                    combined = combined + r
                elif hasattr(combined, 'extend'):
                    combined.extend(r)
            return combined
        
        # All failed - return empty or raise
        if errors:
            from edsl.scenarios import ScenarioList
            # Return empty ScenarioList with error info
            error_scenarios = [{"source": item, "error": err} for item, err in errors]
            return ScenarioList.from_list_of_dicts(error_scenarios)
        
        from edsl.scenarios import ScenarioList
        return ScenarioList([])
    
    def __getattr__(self, method_name: str) -> Callable:
        """
        Dynamically handle method calls.
        
        Any method call on the accessor (e.g., .scrape(), .search()) is
        forwarded to the service via dispatch.
        """
        if method_name.startswith("_"):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{method_name}'"
            )
        
        def method_wrapper(*args, verbose: bool = True, **kwargs) -> Any:
            """Dispatch the method call to the service."""
            # Ensure dependencies are available
            from .dependency_manager import DependencyManager
            from .registry import ServiceRegistry
            DependencyManager.ensure_available(self._service_name)
            
            # Build params dict
            timeout = kwargs.pop("timeout", None)
            poll_interval = kwargs.pop("poll_interval", None)
            
            # Get operation schema if defined
            op_schema = ServiceRegistry.get_operation_schema(self._service_name, method_name)
            
            # Start with operation name (many services use this)
            params = {"operation": method_name}
            
            # Add defaults from schema (if any)
            if op_schema and op_schema.defaults:
                params.update(op_schema.defaults)
            
            # Add kwargs (they override defaults)
            params.update(kwargs)
            
            serialized_data = None
            
            # Handle positional args using schema or fallback patterns
            if args:
                first_arg = args[0]
                
                # Check if first arg is a FileStore
                if hasattr(first_arg, "base64_string") and hasattr(first_arg, "suffix"):
                    # It's a FileStore - serialize it
                    params["source"] = first_arg.to_dict()
                elif op_schema and op_schema.input_param:
                    # Use schema-defined input param name
                    params[op_schema.input_param] = first_arg
                else:
                    # Fallback to common patterns for backwards compatibility
                    if method_name in ("scrape", "crawl", "extract", "parse"):
                        params["url"] = first_arg
                    elif method_name in ("search", "query"):
                        params["query"] = first_arg
                    elif method_name in ("load", "get"):
                        params["name"] = first_arg
                    elif method_name == "transcript":
                        params["video"] = first_arg
                    elif method_name in ("import_qsf", "from_qsf"):
                        params["source"] = first_arg
                    elif method_name in ("generate", "from_vibes", "create"):
                        params["description"] = first_arg
                    elif method_name in ("edit", "filter"):
                        if method_name == "edit":
                            params["edit_instructions"] = first_arg
                        else:
                            params["criteria"] = first_arg
                    elif method_name in ("translate",):
                        params["target_language"] = first_arg
                    elif method_name in ("enrich",):
                        params["enrich_instructions"] = first_arg
                    elif method_name in ("add",):
                        params["add_instructions"] = first_arg
                    elif method_name in ("plot", "sql"):
                        params["description"] = first_arg
                    elif method_name == "indicator":
                        params["indicator"] = first_arg
                    else:
                        # Generic: pass as 'input'
                        params["input"] = first_arg
                
                # Additional positional args
                if len(args) > 1:
                    params["args"] = args[1:]
            
            # Include instance data if available - handle different object types
            if self._instance is not None:
                instance_type = type(self._instance).__name__
                
                # Serialize based on type
                if hasattr(self._instance, "to_dict"):
                    # Survey, Dataset, Results all have to_dict()
                    serialized_data = self._instance.to_dict()
                    params["data"] = serialized_data
                    params["data_type"] = instance_type.lower()
                elif hasattr(self._instance, "to_dicts"):
                    # Backwards compatibility
                    serialized_data = self._instance.to_dicts()
                    params["_instance_data"] = serialized_data

                # Results-specific aliases expected by services
                if instance_type == "Results":
                    # Keep server copy in sync before dispatching remote services
                    try:
                        self._instance.push()
                    except Exception as e:
                        # If push fails, continue with best-effort dispatch
                        # (service may still handle results_dict fallback)
                        if verbose:
                            print(f"[edsl] Results push skipped: {e}")
                    # Prefer server-side fetch by ID; fall back to serialized dict
                    store_id = getattr(self._instance, "_store_id", None)
                    if store_id is None:
                        store = getattr(self._instance, "store", None)
                        if store is not None:
                            meta = getattr(store, "_meta", None)
                            if isinstance(meta, dict):
                                store_id = meta.get("id")
                    if store_id:
                        params.setdefault("results_id", store_id)
                    if serialized_data is not None:
                        params.setdefault("results_dict", serialized_data)
                        params.setdefault("results_data", serialized_data)
            
            # Check if this is a batch operation (list of URLs/queries)
            # If so, dispatch one task per item for better parallelism
            from . import dispatch
            from .registry import ServiceRegistry
            
            batch_key = None
            batch_items = None
            
            # Detect batch operations
            if method_name in ("scrape", "extract"):
                if "urls" in params and isinstance(params.get("urls"), list):
                    batch_key = "url"
                    batch_items = params.pop("urls")
                elif "url" in params and isinstance(params.get("url"), list):
                    batch_key = "url"
                    batch_items = params.pop("url")
            elif method_name == "search":
                if "queries" in params and isinstance(params.get("queries"), list):
                    batch_key = "query"
                    batch_items = params.pop("queries")
                elif "query" in params and isinstance(params.get("query"), list):
                    batch_key = "query"
                    batch_items = params.pop("query")
            
            # Debug: show what we detected
            if verbose and batch_items:
                print(f"[{self._service_name}] Batch mode: {len(batch_items)} {batch_key}s detected")
            
            # Build result() kwargs
            result_kwargs = {"verbose": verbose}
            if timeout is not None:
                result_kwargs["timeout"] = timeout
            if poll_interval is not None:
                result_kwargs["poll_interval"] = poll_interval
            
            if batch_items and len(batch_items) > 1:
                # Dispatch one task per item
                result = self._dispatch_batch(
                    params, batch_key, batch_items, result_kwargs, verbose
                )
            else:
                # Single item - dispatch normally
                if batch_items and len(batch_items) == 1:
                    params[batch_key] = batch_items[0]
                
                pending = dispatch(self._service_name, params)
                result = pending.result(**result_kwargs)
            
            # Check if this is a versioned service
            meta = ServiceRegistry.get_metadata(self._service_name)
            if meta and meta.versioned and self._instance is not None:
                # Versioned service: use replace_with() to create new version
                if hasattr(self._instance, "replace_with"):
                    # Build audit params (filter out large data)
                    audit_params = {
                        k: v for k, v in kwargs.items()
                        if not (isinstance(v, (list, dict)) and len(str(v)) > 500)
                    }
                    
                    return self._instance.replace_with(
                        result,
                        operation=f"{self._service_name}.{method_name}",
                        params=audit_params,
                    )
                else:
                    # Service is versioned but instance doesn't support it
                    import warnings
                    warnings.warn(
                        f"Service '{self._service_name}' is versioned but "
                        f"{type(self._instance).__name__} doesn't have replace_with(). "
                        "Returning raw result."
                    )
            
            return result
        
        return method_wrapper
    
    def __dir__(self) -> List[str]:
        """Support tab completion for service methods."""
        base = ["_service_name", "_instance", "_service_class"]
        
        # Get available methods from the service's OPERATIONS
        methods = self._get_available_methods()
        
        # If no specific operations, fall back to common method names
        if not methods:
            methods = [
                "scrape", "crawl", "search", "extract", "load", "get",
                "parse", "query", "fetch", "generate", "transcript",
            ]
        
        return base + methods


def get_accessor(
    service_name: str, 
    instance: Any = None,
    owner_class: Optional[type] = None
) -> Optional[ServiceAccessor]:
    """
    Get an accessor for a service if it supports the instance type.
    
    Args:
        service_name: Name of the service
        instance: The EDSL object to attach to (None for class-level access)
        owner_class: The class type when accessed at class level
        
    Returns:
        ServiceAccessor if service exists and extends instance type, else None
    """
    from .registry import ServiceRegistry
    
    # Check if service exists
    if not ServiceRegistry.exists(service_name):
        return None
    
    # Check if service extends this instance's class or owner class
    meta = ServiceRegistry.get_metadata(service_name)
    if meta:
        if instance is not None:
            instance_type = type(instance).__name__
            if meta.extends and instance_type not in meta.extends:
                return None
        elif owner_class is not None:
            class_name = owner_class.__name__
            if meta.extends and class_name not in meta.extends:
                return None
    
    return ServiceAccessor(service_name, instance)


def get_class_accessor(service_name: str, cls: type) -> Optional[ServiceAccessor]:
    """
    Get an accessor for a service at the class level.
    
    This is used for class-level access like:
        ScenarioList.firecrawl.scrape(url)
    
    Args:
        service_name: Name of the service
        cls: The class type (e.g., ScenarioList)
        
    Returns:
        ServiceAccessor if service exists and extends this class, else None
    """
    from .registry import ServiceRegistry
    
    # Check if service exists
    if not ServiceRegistry.exists(service_name):
        return None
    
    # Check if service extends this class
    meta = ServiceRegistry.get_metadata(service_name)
    if meta:
        class_name = cls.__name__
        if meta.extends and class_name not in meta.extends:
            # Service doesn't extend this class
            return None
    
    # Return accessor without instance (class-level access)
    return ServiceAccessor(service_name, None)

