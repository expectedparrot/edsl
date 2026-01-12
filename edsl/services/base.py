"""
ExternalService: Protocol for implementing external services.

Services handle three phases:
1. create_task() - Client-side: Create task parameters
2. execute() - Worker-side: Execute the task and return results
3. parse_result() - Client-side: Convert results to EDSL objects

Example:
    >>> from edsl.services import ExternalService, ServiceRegistry
    >>> 
    >>> @ServiceRegistry.register("myservice")
    >>> class MyService(ExternalService):
    ...     @classmethod
    ...     def create_task(cls, query: str, **kwargs) -> dict:
    ...         return {"query": query, **kwargs}
    ...     
    ...     @classmethod
    ...     def execute(cls, params: dict, keys: dict) -> dict:
    ...         api_key = keys.get("MYSERVICE_API_KEY")
    ...         # ... call external API ...
    ...         return {"rows": [...]}
    ...     
    ...     @classmethod
    ...     def parse_result(cls, result: dict):
    ...         from edsl.scenarios import ScenarioList
    ...         return ScenarioList.from_list_of_dicts(result["rows"])
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Future type hints for return types


class ExternalService(ABC):
    """
    Abstract base class for external services.
    
    Services are stateless - all methods are classmethods that operate
    on the provided parameters. This allows workers to instantiate
    services without any EDSL dependencies.
    
    Attributes:
        name: Service identifier (set by ServiceRegistry on registration)
        description: Human-readable description of the service
        version: Service version string
    """
    
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    
    @classmethod
    @abstractmethod
    def create_task(cls, **kwargs) -> Dict[str, Any]:
        """
        Create task parameters from user-provided arguments.
        
        Called on the client side when a user initiates a service call.
        Should validate and package arguments into a JSON-serializable dict.
        
        Args:
            **kwargs: Service-specific arguments
            
        Returns:
            Dict of parameters to be sent to the worker.
            Must be JSON-serializable.
            
        Raises:
            ValueError: If arguments are invalid
        """
        ...
    
    @classmethod
    @abstractmethod
    def execute(cls, params: Dict[str, Any], keys: Dict[str, str]) -> Dict[str, Any]:
        """
        Execute the task and return results.
        
        Called by the worker process. This method should:
        1. Extract parameters from the params dict
        2. Get API keys from the keys dict
        3. Call the external service
        4. Return results as a JSON-serializable dict
        
        Note: This method runs in a worker process that may not have
        EDSL installed. Keep dependencies minimal.
        
        Args:
            params: Task parameters from create_task()
            keys: Dict of API keys (e.g., {"EXA_API_KEY": "..."})
            
        Returns:
            Dict of results. Must be JSON-serializable.
            Typically contains {"rows": [...]} for ScenarioList results.
            
        Raises:
            Exception: If execution fails (will be captured as task error)
        """
        ...
    
    @classmethod
    @abstractmethod
    def parse_result(cls, result: Dict[str, Any]) -> Any:
        """
        Convert execution results to an EDSL object.
        
        Called on the client side after the worker completes.
        Converts the JSON result dict into the appropriate EDSL type.
        
        Args:
            result: Result dict from execute()
            
        Returns:
            EDSL object (typically ScenarioList, but could be FileStore, etc.)
        """
        ...
    
    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> bool:
        """
        Validate task parameters.
        
        Optional method to validate params before dispatch.
        Default implementation returns True.
        
        Args:
            params: Parameters to validate
            
        Returns:
            True if valid, False otherwise
        """
        return True
    
    @classmethod
    def estimate_duration(cls, params: Dict[str, Any]) -> Optional[float]:
        """
        Estimate task duration in seconds.
        
        Optional method to help with scheduling and user feedback.
        Default returns None (unknown).
        
        Args:
            params: Task parameters
            
        Returns:
            Estimated seconds, or None if unknown
        """
        return None
    
    @classmethod
    def get_required_keys(cls) -> list[str]:
        """
        List of API key names required by this service.
        
        Used for validation and documentation.
        
        Returns:
            List of key names (e.g., ["EXA_API_KEY"])
        """
        return []

