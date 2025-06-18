from abc import ABC
from pathlib import Path
from dataclasses import dataclass, field, asdict, fields, MISSING
from typing import Optional, Dict, Any, TypeVar, Type, Callable, List, Union, TYPE_CHECKING, TypedDict
from collections import UserDict

import requests
from pydantic import create_model, Field, BaseModel
import yaml  # Added for YAML serialization

import os
import sys
import logging

from fastapi import HTTPException
from fastapi import APIRouter, Header, HTTPException
from typing import Callable, Optional, Any, Dict

from ..surveys import Survey # Assume Survey is always available
from ..scenarios import Scenario
from ..base import RegisterSubclassesMeta

from .exceptions import (
    ExtensionError,
    ServiceConnectionError,
    ServiceResponseError,
    ServiceConfigurationError,
    ServiceParameterValidationError,
    ServiceDeserializationError,
    ServiceOutputValidationError
)

from .parameter_validation import Parameters
from .service_caller import ServiceCaller
from .service_callers import GatewayServiceCaller, DirectServiceCaller
from .response_processor import ServiceResponseProcessor
from .model_generation import ModelGenerator


API_BASE_URL = os.getenv("EDSL_API_URL", "http://localhost:8000")

if TYPE_CHECKING:
    from .service_definition_helper import ServiceDefinitionHelper

def extract_bearer_token(authorization: Optional[str] = None) -> Optional[str]:
    """Extract the token from the Authorization header.
    
    Args:
        authorization: The Authorization header value, expected to be in the format "Bearer <token>"
        
    Returns:
        The token if present, None otherwise
        
    Example:
        >>> extract_bearer_token("Bearer abc123")
        'abc123'
        >>> extract_bearer_token("bearer abc123")
        'abc123'
        >>> extract_bearer_token("Basic abc123")
        >>> extract_bearer_token(None)
    """
    if not authorization:
        return None
        
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
        
    return parts[1]

T = TypeVar('T', bound='DictSerializable')


logger = logging.getLogger(__name__)

class DictSerializable(ABC):
    """Abstract base class for dataclasses that can be converted to/from dictionaries."""
    def to_dict(self) -> Dict[str, Any]:
        """Converts the dataclass instance to a dictionary.

        >>> pd = ParameterDefinition(type='str', required=True, description='Test')
        >>> pd.to_dict() == {'type': 'str', 'required': True, 'description': 'Test', 'default_value': None}
        True

        >>> pd_with_default = ParameterDefinition(type='int', required=False, description='Num', default_value=5)
        >>> pd_with_default.to_dict() == {'type': 'int', 'required': False, 'description': 'Num', 'default_value': 5}
        True
        """
        # Use asdict, which includes all fields
        return asdict(self)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Creates an instance of the dataclass from a dictionary.

        >>> data = {'type': 'str', 'required': True, 'description': 'Test', 'default_value': None}
        >>> pd = ParameterDefinition.from_dict(data)
        >>> pd.type == 'str' and pd.required and pd.description == 'Test' and pd.default_value is None
        True

        >>> data_default = {'type': 'int', 'required': False, 'description': 'Num', 'default_value': 5}
        >>> pd_def = ParameterDefinition.from_dict(data_default)
        >>> pd_def.default_value
        5
        """
        # Basic implementation, assumes keys match field names.
        # Does not automatically handle nested DictSerializable objects.
        return cls(**data)


@dataclass
class ParameterDefinition(DictSerializable):
    type: str
    required: bool
    description: str
    default_value: Optional[Any] = None

    def __post_init__(self):
        # If we got a dictionary, extract the fields from it
        if isinstance(self.type, dict):
            data = self.type  # The entire parameter definition was passed as a dict in the type field
            self.type = data["type"]
            self.required = data.get("required", True)
            self.description = data["description"]
            self.default_value = data.get("default_value")


@dataclass
class CostDefinition(DictSerializable):
    unit: str
    per_call_cost: int
    variable_pricing_cost_formula: Optional[str] = None
    uses_client_ep_key: bool = False

    def __post_init__(self):
        # If we got a dictionary, extract the fields from it
        if isinstance(self.unit, dict):
            data = self.unit  # The entire cost definition was passed as a dict in the unit field
            self.unit = data["unit"]
            self.per_call_cost = data["per_call_cost"]
            self.variable_pricing_cost_formula = data.get("variable_pricing_cost_formula")
            self.uses_client_ep_key = data.get("uses_client_ep_key", False)


@dataclass
class ReturnDefinition(DictSerializable):
    type: str
    description: str
    coopr_url: Optional[bool] = False

    def __post_init__(self):
        # If we got a dictionary, extract the fields from it
        if isinstance(self.type, dict):
            data = self.type  # The entire return definition was passed as a dict in the type field
            self.type = data["type"]
            self.description = data["description"]
            self.coopr_url = data.get("coopr_url", False)


# class ServiceLocation(TypedDict):
#     service_name: str
#     creator_ep_username: str
#     service_url: str
#     last_updated_timestamp: str

# class ServiceLocations(TypedDict):
#     def __init__(self, data=None, **kwargs):
#         super().__init__(data, **kwargs)
#         self.locations = {}
    
#     def add_location(self, name: str, location: ServiceLocation) -> None:
#         self.locations[name] = location

#     def get_service_endpoint(self, service_name: str) -> str:
#         return self.locations[service_name]["service_url"] + "/" + self.locations[service_name]["service_name"]


@dataclass
class ServiceDefinition(DictSerializable):
    service_collection_name: str
    service_name: str
    description: str
    parameters: Dict[str, Union[ParameterDefinition, Dict[str, Any]]]
    cost: Union[CostDefinition, Dict[str, Any]]
    service_returns: Dict[str, Union[ReturnDefinition, Dict[str, Any]]]
    service_endpoint: Optional[str] = None
    creator_ep_username: Optional[str] = "test"

    # Internal attributes to be set by the client
    _ep_api_token: Optional[str] = field(default=None, init=False, repr=False)
    _parameters: Parameters = field(init=False, repr=False)
    _response_processor: ServiceResponseProcessor = field(init=False, repr=False)
    _model_generator: ModelGenerator = field(init=False, repr=False)

    def __post_init__(self):
        """Convert dictionaries to proper objects after initialization."""
        # Handle parameters
        processed_parameters = {}
        for name, param in self.parameters.items():
            if isinstance(param, dict):
                processed_parameters[name] = ParameterDefinition(param, False, "", None)  # The dict will be processed in ParameterDefinition's __post_init__
            else:
                processed_parameters[name] = param
        self.parameters = processed_parameters
        self._parameters = Parameters(self.parameters)

        # Handle service returns
        processed_returns = {}
        for name, ret in self.service_returns.items():
            if isinstance(ret, dict):
                processed_returns[name] = ReturnDefinition(ret, "")  # The dict will be processed in ReturnDefinition's __post_init__
            else:
                processed_returns[name] = ret
        self.service_returns = processed_returns

        # Initialize response processor
        self._response_processor = ServiceResponseProcessor(
            service_name=self.service_name,
            service_returns=self.service_returns
        )

        # Initialize model generator
        self._model_generator = ModelGenerator(
            service_name=self.service_name,
            parameters=self.parameters,
            service_returns=self.service_returns
        )

        # Handle cost
        if isinstance(self.cost, dict):
            self.cost = CostDefinition(self.cost, 0)  # The dict will be processed in CostDefinition's __post_init__

        # Generate dynamic doc
        object.__setattr__(self, "__doc__", self._generate_dynamic_doc())



    def push_to_gateway(self, gateway_url: str = API_BASE_URL, timeout: int = 30) -> Dict[str, Any]:
        """
        Push this ServiceDefinition to an extension gateway.
        
        Parameters
        ----------
        gateway_url : str, default API_BASE_URL
            The base URL of the extension gateway (e.g., "http://localhost:8000").
            The method will append "/service-definitions/" to this URL.
        timeout : int, default 30
            Request timeout in seconds.
            
        Returns
        -------
        Dict[str, Any]
            The response from the gateway including the assigned database ID and confirmation message.
            
        Raises
        ------
        ServiceConnectionError
            If the HTTP request fails due to network issues.
        ServiceResponseError
            If the gateway returns an error status (≥400).
        ServiceDeserializationError
            If the response cannot be parsed as JSON.
            
        Examples
        --------
        >>> service_def = ServiceDefinition.example()
        >>> response = service_def.push_to_gateway()  # Uses API_BASE_URL as default
        >>> "id" in response  # doctest: +SKIP
        True
        >>> # Or specify a custom gateway URL
        >>> response = service_def.push_to_gateway("http://custom-gateway:8000")  # doctest: +SKIP
        """
        # Build the endpoint URL
        endpoint_url = gateway_url.rstrip("/") + "/service-definitions/"
        
        # Prepare the payload with field mapping for backward compatibility with gateway
        base_payload = self.to_dict()
        # Map new field names to what the gateway currently expects
        payload = {
            "service_name": base_payload["service_name"],  # Gateway expects 'name' field
            "description": base_payload["description"],
            "creator_ep_username": base_payload["creator_ep_username"],
            "service_endpoint": base_payload.get("service_endpoint"), 
            "cost": base_payload["cost"],
            "service_returns": base_payload["service_returns"],
            "parameters": base_payload["parameters"],
            "service_collection_name": base_payload["service_collection_name"]
        }
        
        # Set up headers
        headers = {
            "Content-Type": "application/json"
        }
        
        logger.info("Pushing ServiceDefinition '%s' to gateway: %s", self.service_name, endpoint_url)
        logger.debug("Payload: %s", payload)
        
        try:
            response = requests.post(
                endpoint_url, 
                json=payload, 
                headers=headers, 
                timeout=timeout
            )
            
            logger.debug("Gateway response status: %s", response.status_code)
            
            # Handle error status codes
            if response.status_code >= 400:
                try:
                    error_detail = response.json()
                    error_message = error_detail.get("detail", response.text)
                except Exception:
                    error_message = response.text
                
                raise ServiceResponseError(
                    f"Gateway rejected ServiceDefinition '{self.service_name}' with status {response.status_code}: {error_message}"
                )
            
            # Parse successful response
            try:
                result = response.json()
                logger.info("Successfully pushed ServiceDefinition '%s' to gateway. Assigned ID: %s", 
                          self.service_name, result.get("id", "unknown"))
                return result
                
            except Exception as e:
                raise ServiceDeserializationError(
                    f"Could not parse gateway response as JSON: {e}"
                ) from e
                
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise ServiceConnectionError(
                f"Error connecting to gateway at {endpoint_url}: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ServiceConnectionError(
                f"Unexpected error calling gateway at {endpoint_url}: {e}"
            ) from e

    def to_dict(self) -> Dict[str, Any]:
        """Converts the ServiceDefinition to a dictionary, handling nested objects.

        >>> sd = ServiceDefinition.example()
        >>> d = sd.to_dict()
        >>> isinstance(d['parameters']['overall_question'], dict)
        True
        >>> d['cost']['unit'] == 'ep_credits'
        True
        >>> d['service_returns']['survey']['type'] == 'Survey'
        True
        >>> d['service_endpoint'] is None  # Will be set when deployed
        True
        """
        return {
            "service_collection_name": self.service_collection_name,
            "service_name": self.service_name,
            "description": self.description,
            "service_endpoint": self.service_endpoint,
            "parameters": {k: v.to_dict() for k, v in self.parameters.items()},
            "cost": self.cost.to_dict(),
            "service_returns": {k: v.to_dict() for k, v in self.service_returns.items()},
            "creator_ep_username": self.creator_ep_username,
        }
    
    def __hash__(self) -> int:
        return hash(Scenario(self.to_dict()))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServiceDefinition':
        """Creates a ServiceDefinition from a dictionary, handling nested objects.

        >>> sd_orig = ServiceDefinition.example()
        >>> data = sd_orig.to_dict()
        >>> sd_new = ServiceDefinition.from_dict(data)
        >>> sd_new == sd_orig
        True
        """
        return cls(
            service_collection_name=data['service_collection_name'],
            service_name=data['service_name'],
            description=data['description'],
            service_endpoint=data.get('service_endpoint'),
            parameters={k: ParameterDefinition.from_dict(v) for k, v in data['parameters'].items()},
            cost=CostDefinition.from_dict({k: v for k, v in data['cost'].items() if k != 'ep_username'}),
            service_returns={k: ReturnDefinition.from_dict(v) for k, v in data['service_returns'].items()},
            creator_ep_username=data.get('creator_ep_username', 'test'),
        )

    @classmethod
    def example(cls) -> 'ServiceDefinition':
        """Returns an example instance of the ServiceDefinition."""
        return cls(
            service_collection_name="example_collection",
            service_name="create_survey",
            description="Creates a survey to answer an overall research question",
            service_endpoint=None,  # Will be set when deployed
            parameters={
                "overall_question": ParameterDefinition(
                    type="str",
                    required=True,
                    description="Overall question you want to ask"
                ),
                "population": ParameterDefinition(
                    type="string",
                    required=True, 
                    description="Population for the survey"
                ),
                "num_questions": ParameterDefinition(
                     type="int", 
                     required=False, 
                     default_value=10,
                     description="Target number of questions"
                )
            },
            cost=CostDefinition(
                unit="ep_credits",
                per_call_cost=100,  # Cost in credits
                variable_pricing_cost_formula="num_questions * 10",
                uses_client_ep_key=True
             ),
            service_returns={
             'survey': ReturnDefinition(
                type="Survey",
                coopr_url=True,
                description="An EDSL survey object"
             )
            },
            creator_ep_username="test",
        )

    def validate_call_parameters(self, params: Dict[str, Any]):
        """Validates that all required parameters are present and of the correct type for a call.

        Raises:
            ServiceParameterValidationError: If validation fails (missing required param or type mismatch).
        """
        if self._parameters is None:
            raise ServiceConfigurationError("Parameters not initialized")
        self._parameters.validate_call_parameters(params)

    def _prepare_parameters(self, **kwargs: Any) -> Dict[str, Any]:
        """Prepares the dictionary of parameters for the API call, serializing EDSL objects and including defaults.
        Assumes parameters have been validated by validate_call_parameters.
        """
        if self._parameters is None:
            raise ServiceConfigurationError("Parameters not initialized")
        return self._parameters.prepare_parameters(**kwargs)
    


    def __call__(self, use_gateway: bool = True, gateway_url: Optional[str] = None, **kwargs: Any) -> Any:
        """
        Executes the API call for this service using provided parameters.

        Args:
            use_gateway: Whether to use the gateway for calling the service
            gateway_url: Override the default gateway URL (only used when use_gateway=True)
            **kwargs: Parameters for the service call.

        Returns:
            The API response, potentially deserialized based on service definition.

        Raises:
            ServiceParameterValidationError: If validation fails (missing/incorrect params).
            ServiceConfigurationError: If service_endpoint is not set when needed.
            ServiceConnectionError: If the API call fails due to connection issues.
            ServiceResponseError: If the API call returns an error status or invalid JSON.
            ServiceDeserializationError: If the response cannot be deserialized correctly.
        """
        # Validate and prepare parameters
        self.validate_call_parameters(kwargs)
        prepared_params = self._prepare_parameters(**kwargs)

        if use_gateway:
            effective_gateway_url = gateway_url or API_BASE_URL
            service_caller = GatewayServiceCaller(
                service_name=self.service_name,
                gateway_url=effective_gateway_url,
                ep_api_token=self._ep_api_token
            )
        else:
            service_caller = DirectServiceCaller(
                service_name=self.service_name,
                service_endpoint=self.service_endpoint,
                ep_api_token=self._ep_api_token
            )

        result = service_caller.call_service(
            prepared_params=prepared_params,
            deserialize_response=self._response_processor.deserialize_response
        )
        # Log estimated cost
        try:
            from .price_calculation import compute_price  # local import to avoid circular deps
            estimated_cost = compute_price(self, prepared_params)
            logger.info("Estimated cost for call to '%s': %s %s", self.service_name, estimated_cost, self.cost.unit)
        except Exception as _e:
            # Avoid hard failure if pricing formula is invalid – just log at debug level.
            logger.debug("Could not compute price for '%s': %s", self.service_name, _e)

        return result



    def validate_service_output(self, output_data: Dict[str, Any]):
        """
        Validates the structure and types of the service output dictionary against the 'service_returns' definition.

        Args:
            output_data: The dictionary returned by the service implementation.

        Raises:
            TypeError: If the output_data is not a dictionary.
            ServiceOutputValidationError: If a required return key is missing or a value has the wrong type.
        """
        self._response_processor.validate_service_output(output_data)

    def get_request_model(self) -> Type[BaseModel]:
        """Dynamically creates a Pydantic model for the service parameters."""
        return self._model_generator.get_request_model()

    def get_response_model(self) -> Type[BaseModel]:
        """Dynamically creates a Pydantic model for the service return values."""
        return self._model_generator.get_response_model()

    def _generate_dynamic_doc(self) -> str:
        """Dynamically builds a helpful, example-driven docstring for *this* service instance."""
        # Build call signature   e.g. create_survey(overall_question: str, population: string, num_questions: int = 10)
        signature_parts: list[str] = []
        for p_name, p_def in self.parameters.items():
            default_str = ""
            # Only show default if it actually has one (and it's not the MISSING sentinel)
            if p_def.default_value is not MISSING:
                default_str = f" = {p_def.default_value!r}"
            signature_parts.append(f"{p_name}: {p_def.type}{default_str}")
        signature = f"{self.service_name}({', '.join(signature_parts)})"

        # Parameters section
        param_lines: list[str] = []
        for p_name, p_def in self.parameters.items():
            required_str = "required" if p_def.required and p_def.default_value is MISSING else "optional"
            line = f"    {p_name} ({p_def.type}, {required_str}) – {p_def.description}"
            param_lines.append(line)
        params_block = "\n".join(param_lines) if param_lines else "    (no parameters)"

        # Returns section
        return_lines: list[str] = []
        for r_key, r_def in self.service_returns.items():
            line = f"    {r_key} ({r_def.type}) – {r_def.description}"
            return_lines.append(line)
        returns_block = "\n".join(return_lines) if return_lines else "    (no explicit returns)"

        # Cost section (brief)
        cost_line = f"    {self.cost.per_call_cost} {self.cost.unit} per call"
        if self.cost.variable_pricing_cost_formula:
            cost_line += f" + variable component ({self.cost.variable_pricing_cost_formula})"

        doc = (
            f"{self.description}\n\n"
            f"Call signature:\n\n    {signature}\n\n"
            f"Parameters:\n{params_block}\n\n"
            f"Returns:\n{returns_block}\n\n"
            f"Cost:\n{cost_line}\n\n"
        )
        return doc

    def __getattr__(self, item: str):
        # Provide a dynamic, instance-specific docstring when users invoke `help(<service_instance>)`.
        if item == "__doc__":
            return self._generate_dynamic_doc()
        raise AttributeError(f"{self.__class__.__name__!r} object has no attribute {item!r}")

    def register_service(
        router: APIRouter,
        service_name: str,
        service_def,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """
        Usage:
            @register_service(router, "create_survey", extensions["create_survey"])
            async def create_survey_logic(overall_question, population, ep_api_token):
                ...
        """
        request_model  = service_def.get_request_model()
        response_model = service_def.get_response_model()

        def decorator(fn: Callable[..., Any]):
            route_path = f"/{service_name}"

            @router.post(route_path, response_model=response_model)   # type: ignore[arg-type]
            async def _endpoint(
                request_body: request_model,                        # type: ignore[arg-type]
                authorization: Optional[str] = Header(None),
            ) -> Dict[str, Any]:
                token = extract_bearer_token(authorization)
                # Forward request parameters as keyword arguments to avoid relying on positional order
                # and prevent duplicate ep_api_token values.
                result = await fn(**request_body.model_dump(), ep_api_token=token)

                # Plug into your standard output validator
                service_def.validate_service_output(result)
                return result

            _endpoint.__name__ = f"{service_name}_endpoint"   # keeps FastAPI happy
            return _endpoint

        return decorator

    # ------------------------------------------------------------------
    # YAML helpers
    # ------------------------------------------------------------------
    def to_yaml(self) -> str:
        """Serializes the ServiceDefinition to a YAML string.

        >>> sd = ServiceDefinition.example()
        >>> yaml_str = sd.to_yaml()
        >>> isinstance(yaml_str, str)
        True
        """
        # ``sort_keys=False`` to preserve field ordering as defined by ``to_dict``
        return yaml.safe_dump(self.to_dict(), sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_source: Union[str, "Path", os.PathLike]) -> 'ServiceDefinition':
        """Create a :class:`ServiceDefinition` from YAML *content* **or** a YAML *file*.

        The method is flexible:

        • If *yaml_source* is a :class:`pathlib.Path` (or any *os.PathLike*) it is treated as a
          path to a YAML file which will be read.
        • If *yaml_source* is a ``str`` that refers to an **existing file path**, that file will
          be read.
        • Otherwise the argument is treated as a raw YAML string, preserving the original
          behaviour.

        Examples
        --------
        >>> sd_orig = ServiceDefinition.example()
        >>> # Original behaviour still works – pass YAML text
        >>> sd_from_text = ServiceDefinition.from_yaml(sd_orig.to_yaml())
        >>> sd_from_text == sd_orig
        True
        >>> # New behaviour – pass a file path
        >>> import tempfile, pathlib, os
        >>> tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml")
        >>> _ = tmp.write(sd_orig.to_yaml().encode()) and tmp.close()  # doctest: +ELLIPSIS
        >>> sd_from_file = ServiceDefinition.from_yaml(tmp.name)
        >>> sd_from_file == sd_orig
        True
        >>> os.unlink(tmp.name)  # cleanup
        """

        # ------------------------------------------------------------------
        # Detect whether *yaml_source* is a path or raw YAML content.
        # ------------------------------------------------------------------
        yaml_str: str

        # Case 1 – pathlib.Path or os.PathLike explicitly passed
        if isinstance(yaml_source, (Path, os.PathLike)):
            with open(yaml_source, "r", encoding="utf-8") as f:
                yaml_str = f.read()
        # Case 2 – string input: it *might* be a path. If the path exists on disk, read it.
        elif isinstance(yaml_source, str):
            # Heuristic: attempt to parse the string directly as YAML first. If it yields
            # a dictionary, we are done.  This avoids filesystem look-ups on long YAML
            # strings which can raise "File name too long" OSErrors.
            try:
                parsed_tmp = yaml.safe_load(yaml_source)
                if isinstance(parsed_tmp, dict):
                    yaml_str = yaml_source
                    data_parsed = parsed_tmp  # Re-use later, skip second parse
                else:
                    raise yaml.YAMLError  # Force fallback to path handling
            except yaml.YAMLError:
                # Not valid YAML content – treat the string as a potential file path.
                potential_path = Path(yaml_source)
                try:
                    if potential_path.exists():
                        with open(potential_path, "r", encoding="utf-8") as f:
                            yaml_str = f.read()
                    else:
                        raise FileNotFoundError(f"YAML file not found: {yaml_source}")
                except OSError as e:
                    # Re-raise with clearer context
                    raise FileNotFoundError(f"Could not read YAML file: {e}")
        else:
            raise TypeError("yaml_source must be a str, Path, or os.PathLike object")

        # ------------------------------------------------------------------
        # Deserialize and delegate to existing from_dict constructor
        # ------------------------------------------------------------------
        # Use the YAML that we have already parsed if available, otherwise parse now.
        if 'data_parsed' in locals():
            data = data_parsed  # type: ignore[assignment]
        else:
            data = yaml.safe_load(yaml_str)

        if not isinstance(data, dict):
            raise ServiceDeserializationError("YAML content must deserialize to a dictionary")
        return cls.from_dict(data)

    @classmethod
    def list_from_gateway(cls, gateway_url: str = API_BASE_URL, timeout: int = 30) -> List[Dict[str, Any]]:
        """
        List all service definitions stored in an extension gateway.
        
        Parameters
        ----------
        gateway_url : str, default API_BASE_URL
            The base URL of the extension gateway (e.g., "http://localhost:8000").
        timeout : int, default 30
            Request timeout in seconds.
            
        Returns
        -------
        List[Dict[str, Any]]
            List of service definition summaries from the gateway.
            
        Raises
        ------
        ServiceConnectionError
            If the HTTP request fails due to network issues.
        ServiceResponseError
            If the gateway returns an error status (≥400).
        ServiceDeserializationError
            If the response cannot be parsed as JSON.
            
        Examples
        --------
        >>> services = ServiceDefinition.list_from_gateway()  # Uses API_BASE_URL as default
        >>> isinstance(services, list)  # doctest: +SKIP
        True
        >>> # Or specify a custom gateway URL
        >>> services = ServiceDefinition.list_from_gateway("http://custom-gateway:8000")  # doctest: +SKIP
        """
        endpoint_url = gateway_url.rstrip("/") + "/service-definitions/"
        
        logger.info("Listing service definitions from gateway: %s", endpoint_url)
        
        try:
            response = requests.get(endpoint_url, timeout=timeout)
            
            if response.status_code >= 400:
                try:
                    error_detail = response.json()
                    error_message = error_detail.get("detail", response.text)
                except Exception:
                    error_message = response.text
                
                raise ServiceResponseError(
                    f"Gateway failed to list service definitions with status {response.status_code}: {error_message}"
                )
            
            try:
                result = response.json()
                service_definitions = result.get("service_definitions", [])
                logger.info("Retrieved %s service definitions from gateway", len(service_definitions))
                return service_definitions
                
            except Exception as e:
                raise ServiceDeserializationError(
                    f"Could not parse gateway response as JSON: {e}"
                ) from e
                
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise ServiceConnectionError(
                f"Error connecting to gateway at {endpoint_url}: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ServiceConnectionError(
                f"Unexpected error calling gateway at {endpoint_url}: {e}"
            ) from e

    @classmethod
    def pull_from_gateway(cls, service_id: int, gateway_url: str = API_BASE_URL, timeout: int = 30) -> 'ServiceDefinition':
        """
        Retrieve a specific service definition from an extension gateway by ID.
        
        Parameters
        ----------
        service_id : int
            The database ID of the service definition to retrieve.
        gateway_url : str, default API_BASE_URL
            The base URL of the extension gateway (e.g., "http://localhost:8000").
        timeout : int, default 30
            Request timeout in seconds.
            
        Returns
        -------
        ServiceDefinition
            The service definition retrieved from the gateway.
            
        Raises
        ------
        ServiceConnectionError
            If the HTTP request fails due to network issues.
        ServiceResponseError
            If the gateway returns an error status (≥400) or if the service is not found.
        ServiceDeserializationError
            If the response cannot be parsed or converted to a ServiceDefinition.
            
        Examples
        --------
        >>> service_def = ServiceDefinition.pull_from_gateway(1)  # Uses API_BASE_URL as default
        >>> isinstance(service_def, ServiceDefinition)  # doctest: +SKIP
        True
        >>> # Or specify a custom gateway URL
        >>> service_def = ServiceDefinition.pull_from_gateway(1, "http://custom-gateway:8000")  # doctest: +SKIP
        """
        endpoint_url = gateway_url.rstrip("/") + f"/service-definitions/{service_id}"
        
        logger.info("Retrieving service definition ID %s from gateway: %s", service_id, endpoint_url)
        
        try:
            response = requests.get(endpoint_url, timeout=timeout)
            
            if response.status_code >= 400:
                try:
                    error_detail = response.json()
                    error_message = error_detail.get("detail", response.text)
                except Exception:
                    error_message = response.text
                
                if response.status_code == 404:
                    raise ServiceResponseError(
                        f"Service definition with ID {service_id} not found in gateway"
                    )
                else:
                    raise ServiceResponseError(
                        f"Gateway failed to retrieve service definition with status {response.status_code}: {error_message}"
                    )
            
            try:
                result = response.json()
                # Map gateway field names to our internal field names
                service_data = {
                    "service_collection_name": result.get("service_collection_name", "default"),
                    "service_name": result.get("name", result.get("service_name")),  # Gateway sends 'name'
                    "description": result.get("description"),
                    "service_endpoint": result.get("service_location_url", result.get("service_endpoint")),  # Gateway sends 'service_location_url'
                    "creator_ep_username": result.get("creator_ep_username"),
                    "parameters": result.get("parameters", {}),
                    "cost": result.get("cost", {}),
                    "service_returns": result.get("service_returns", {})
                }
                
                service_def = cls.from_dict(service_data)
                logger.info("Successfully retrieved service definition '%s' from gateway", service_def.service_name)
                return service_def
                
            except Exception as e:
                raise ServiceDeserializationError(
                    f"Could not parse gateway response or convert to ServiceDefinition: {e}"
                ) from e
                
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise ServiceConnectionError(
                f"Error connecting to gateway at {endpoint_url}: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ServiceConnectionError(
                f"Unexpected error calling gateway at {endpoint_url}: {e}"
            ) from e

    @classmethod
    def pull_all_from_gateway(cls, gateway_url: str = API_BASE_URL, timeout: int = 30) -> List['ServiceDefinition']:
        """
        Retrieve all service definitions from an extension gateway.
        
        This method first lists all available service definitions, then pulls the full
        definition for each one. This provides complete ServiceDefinition objects with
        all parameters, cost information, and return specifications.
        
        Parameters
        ----------
        gateway_url : str, default API_BASE_URL
            The base URL of the extension gateway (e.g., "http://localhost:8000").
        timeout : int, default 30
            Request timeout in seconds for each individual request.
            
        Returns
        -------
        List[ServiceDefinition]
            List of all service definitions available in the gateway.
            
        Raises
        ------
        ServiceConnectionError
            If any HTTP request fails due to network issues.
        ServiceResponseError
            If the gateway returns an error status (≥400) for any request.
        ServiceDeserializationError
            If any response cannot be parsed or converted to a ServiceDefinition.
            
        Examples
        --------
        >>> services = ServiceDefinition.pull_all_from_gateway()  # Uses API_BASE_URL as default
        >>> isinstance(services, list)  # doctest: +SKIP
        True
        >>> all(isinstance(s, ServiceDefinition) for s in services)  # doctest: +SKIP
        True
        >>> # Or specify a custom gateway URL
        >>> services = ServiceDefinition.pull_all_from_gateway("http://custom-gateway:8000")  # doctest: +SKIP
        """
        logger.info("Retrieving all service definitions from gateway: %s", gateway_url)
        
        try:
            # First, get the list of all service definitions (summaries with IDs)
            service_summaries = cls.list_from_gateway(gateway_url, timeout)
            
            if not service_summaries:
                logger.info("No service definitions found in gateway")
                return []
            
            logger.info("Found %s service definitions, retrieving full definitions...", len(service_summaries))
            
            # Pull each service definition individually
            service_definitions = []
            failed_services = []
            
            for summary in service_summaries:
                service_id = summary.get("id")
                service_name = summary.get("service_name", summary.get("name", f"ID-{service_id}"))
                
                if not service_id:
                    logger.warning("Service summary missing ID, skipping: %s", summary)
                    failed_services.append(f"Unknown service (no ID): {summary}")
                    continue
                
                try:
                    service_def = cls.pull_from_gateway(service_id, gateway_url, timeout)
                    service_definitions.append(service_def)
                    logger.debug("Successfully retrieved service definition: %s", service_def.service_name)
                    
                except Exception as e:
                    logger.warning("Failed to retrieve service definition ID %s (%s): %s", 
                                 service_id, service_name, e)
                    failed_services.append(f"{service_name} (ID: {service_id}): {str(e)}")
            
            # Log summary
            logger.info("Successfully retrieved %s/%s service definitions from gateway", 
                       len(service_definitions), len(service_summaries))
            
            if failed_services:
                logger.warning("Failed to retrieve %s service definitions: %s", 
                             len(failed_services), ", ".join(failed_services))
            
            return service_definitions
            
        except Exception as e:
            # If the list operation itself fails, re-raise with context
            if "list_from_gateway" in str(e) or isinstance(e, (ServiceConnectionError, ServiceResponseError)):
                raise
            else:
                logger.exception("Unexpected error retrieving all service definitions: %s", e)
                raise ServiceConnectionError(
                    f"Unexpected error retrieving all service definitions: {e}"
                ) from e


class ServiceBuilder:
    def __init__(
        self, 
        implementation: Callable, 
        overwrite: bool = False,
        service_name: Optional[str] = None,
        service_collection_name: Optional[str] = None,
        description: Optional[str] = None,
        service_endpoint: Optional[str] = None,
        cost_unit: Optional[str] = None,
        per_call_cost: Optional[int] = None,
        variable_pricing_cost_formula: Optional[str] = None,
        uses_client_ep_key: Optional[bool] = None,
        creator_ep_username: Optional[str] = None
    ):
        from .service_definition_helper import ServiceDefinitionHelper
        self.implementation = implementation
        helper = ServiceDefinitionHelper(implementation)
        self.service_def = helper.propose_service_definition(
            service_name=service_name,
            service_collection_name=service_collection_name
        )
        
        # Override service definition fields if provided
        if service_name:
            self.service_def.service_name = service_name
        if service_collection_name:
            self.service_def.service_collection_name = service_collection_name
        if description:
            self.service_def.description = description
        if service_endpoint:
            self.service_def.service_endpoint = service_endpoint
            
        # Override cost definition fields if provided
        if any([cost_unit, per_call_cost, variable_pricing_cost_formula, uses_client_ep_key, creator_ep_username]):
            if cost_unit:
                self.service_def.cost.unit = cost_unit
            if per_call_cost is not None:
                self.service_def.cost.per_call_cost = per_call_cost
            if variable_pricing_cost_formula:
                self.service_def.cost.variable_pricing_cost_formula = variable_pricing_cost_formula
            if uses_client_ep_key is not None:
                self.service_def.cost.uses_client_ep_key = uses_client_ep_key
            if creator_ep_username:
                self.service_def.creator_ep_username = creator_ep_username
        
        # Write service definition to YAML
        self._write_service_yaml(helper, overwrite)
    
    def _has_differences(self, existing_def: ServiceDefinition, helper: 'ServiceDefinitionHelper') -> bool:
        comparison = helper.validate(existing_def)
        return bool(comparison.strip())
    
    def _get_user_confirmation(self) -> bool:
        """Prompt the user for confirmation and return their choice."""
        while True:
            response = input("\nWould you like to overwrite with these changes? [y/N]: ").lower().strip()
            if response in ['y', 'yes']:
                return True
            if response in ['', 'n', 'no']:
                return False
            print("Please answer 'y' or 'n'")

    def _write_service_yaml(self, helper: 'ServiceDefinitionHelper', overwrite: bool):
        # Get the directory of the caller (where app.py is)
        caller_dir = Path(os.getcwd())
        
        # Ensure configs directory exists in the caller's directory
        configs_dir = caller_dir / 'configs'
        configs_dir.mkdir(exist_ok=True)
        
        # Get YAML path relative to caller
        yaml_path = configs_dir / f"{self.service_def.service_name}.yaml"
        
        # If file exists, compare definitions
        if yaml_path.exists():
            existing_def = ServiceDefinition.from_yaml(yaml_path)
            
            # Compare the actual service definitions
            existing_dict = existing_def.to_dict()
            new_dict = self.service_def.to_dict()
            
            # Check for differences and show them
            differences = []
            for key in set(existing_dict.keys()) | set(new_dict.keys()):
                if key not in existing_dict:
                    differences.append(f"New field added: {key}")
                elif key not in new_dict:
                    differences.append(f"Field removed: {key}")
                elif existing_dict[key] != new_dict[key]:
                    if isinstance(existing_dict[key], dict) and isinstance(new_dict[key], dict):
                        # For nested dicts (like cost), show specific field differences
                        for subkey in set(existing_dict[key].keys()) | set(new_dict[key].keys()):
                            if subkey not in existing_dict[key]:
                                differences.append(f"New subfield added in {key}: {subkey}")
                            elif subkey not in new_dict[key]:
                                differences.append(f"Subfield removed in {key}: {subkey}")
                            elif existing_dict[key][subkey] != new_dict[key][subkey]:
                                differences.append(f"Changed {key}.{subkey}:")
                                differences.append(f"  From: {existing_dict[key][subkey]}")
                                differences.append(f"  To:   {new_dict[key][subkey]}")
                    else:
                        differences.append(f"Changed {key}:")
                        differences.append(f"  From: {existing_dict[key]}")
                        differences.append(f"  To:   {new_dict[key]}")
            
            if differences:
                print("\nDifferences detected between existing YAML and new definition:")
                print("\n".join(differences))
                
                # If there are differences, always ask for confirmation
                should_overwrite = self._get_user_confirmation() if not overwrite else True
                
                if should_overwrite:
                    print(f"Overwriting {yaml_path}")
                    yaml_path.write_text(self.service_def.to_yaml())
                else:
                    print("Keeping existing YAML file")
            else:
                print("\nNo differences detected between existing YAML and new definition")
        else:
            # File doesn't exist, write it
            print(f"Creating new YAML file at {yaml_path}")
            yaml_path.write_text(self.service_def.to_yaml())


class ServicesBuilder:
    """A container class for managing multiple service definitions."""
    
    def __init__(self, service_collection_name: Optional[str] = None, creator_ep_username: Optional[str] = None):
        self._services: Dict[str, ServiceBuilder] = {}
        self._default_service_collection_name = service_collection_name
        self._default_creator_ep_username = creator_ep_username
    
    def add_service(
        self, 
        implementation: Callable[..., Any],
        overwrite: bool = False,
        **kwargs
    ) -> None:
        """Add a service to the container.
        
        Args:
            implementation: The callable that implements the service
            overwrite: Whether to overwrite existing YAML file without confirmation
            **kwargs: Additional keyword arguments to pass to the ServiceBuilder constructor (e.g., service_name, description, 
                     service_endpoint, cost_unit, per_call_cost, variable_pricing_cost_formula, uses_client_ep_key, creator_ep_username)
        """
        # Use default service_collection_name if not provided in kwargs
        if 'service_collection_name' not in kwargs and self._default_service_collection_name is not None:
            kwargs['service_collection_name'] = self._default_service_collection_name
            
        # Use default creator_ep_username if not provided in kwargs
        if 'creator_ep_username' not in kwargs and self._default_creator_ep_username is not None:
            kwargs['creator_ep_username'] = self._default_creator_ep_username
            
        service = ServiceBuilder(implementation, overwrite=overwrite, **kwargs)
        self._services[service.service_def.service_name] = service
    
    def set_base_url(self, base_url: str, push_to_gateway: bool = False, gateway_url: str = API_BASE_URL, timeout: int = 30) -> None:
        """Set the base URL for all service definitions in this container.
        
        This updates the service_endpoint for each service from None to the full URL:
        base_url + "/" + service_name
        
        Args:
            base_url: The base URL to set for all services (e.g., "http://localhost:8000")
            push_to_gateway: Whether to push the updated services to the gateway after setting URLs
            gateway_url: The gateway URL to push to (only used if push_to_gateway=True)
            timeout: Request timeout for gateway operations (only used if push_to_gateway=True)
        """
        base_url = base_url.rstrip("/")  # Remove trailing slash if present
        for service in self._services.values():
            service.service_def.service_endpoint = f"{base_url}/{service.service_def.service_name}"
        
        if push_to_gateway:
            self.push_to_gateway(gateway_url=gateway_url, timeout=timeout)
    
    def push_to_gateway(self, gateway_url: str = API_BASE_URL, timeout: int = 30) -> Dict[str, Any]:
        """Push all service definitions in this container to the gateway.
        
        Args:
            gateway_url: The base URL of the extension gateway (e.g., "http://localhost:8000")
            timeout: Request timeout in seconds for each push operation
            
        Returns:
            Dict[str, Any]: Summary of push results with service names as keys and gateway responses as values
            
        Raises:
            ServiceConnectionError: If any HTTP request fails due to network issues
            ServiceResponseError: If the gateway returns an error status (≥400) for any service
            ServiceDeserializationError: If any response cannot be parsed as JSON
            
        Examples:
            >>> services = ServicesBuilder("example_collection")
            >>> # ... add services ...
            >>> results = services.push_to_gateway()  # Uses API_BASE_URL as default
            >>> isinstance(results, dict)  # doctest: +SKIP
            True
        """
        results = {}
        errors = {}
        
        logger.info("Pushing %s service definitions to gateway: %s", len(self._services), gateway_url)
        
        for service_name, service in self._services.items():
            try:
                result = service.service_def.push_to_gateway(gateway_url=gateway_url, timeout=timeout)
                results[service_name] = result
                logger.debug("Successfully pushed service '%s' to gateway", service_name)
            except Exception as e:
                errors[service_name] = str(e)
                logger.error("Failed to push service '%s' to gateway: %s", service_name, e)
        
        # Include error summary in results
        summary = {
            "successful_pushes": results,
            "failed_pushes": errors,
            "total_services": len(self._services),
            "successful_count": len(results),
            "failed_count": len(errors)
        }
        
        if errors:
            logger.warning("Push completed with %s successes and %s failures", len(results), len(errors))
            # If there were failures, include them in the returned summary but don't raise an exception
            # This allows the caller to inspect what succeeded and what failed
        else:
            logger.info("Successfully pushed all %s service definitions to gateway", len(self._services))
        
        return summary
    
    def __getitem__(self, key: str) -> ServiceBuilder:
        """Get a service by name."""
        return self._services[key]
    
    def __iter__(self):
        """Iterate over services."""
        return iter(self._services.values())
    
    def __len__(self) -> int:
        """Get number of services."""
        return len(self._services)



if __name__ == "__main__":
    #import doctest
    #doctest.testmod(optionflags=doctest.ELLIPSIS)
    
    # Test the new gateway URL functionality
    print("Testing gateway URL configuration...")
    
    # Test environment variable
    import os
    original_env = os.environ.get("EDSL_API_URL")
    os.environ["EDSL_API_URL"] = "http://localhost:9999"
    
    # Reload the module to pick up the environment variable change
    import importlib
    current_module = sys.modules[__name__]
    importlib.reload(current_module)
    
    print(f"API_BASE_URL from environment: {API_BASE_URL}")
    
    # Restore original environment
    if original_env:
        os.environ["EDSL_API_URL"] = original_env
    else:
        os.environ.pop("EDSL_API_URL", None)
    
    # Test service definition calling with custom gateway URL
    sd = ServiceDefinition.example()
    sd.service_name = "test_service"
    
    print("\nExample service call with custom gateway URL:")
    print("service_def(gateway_url='http://localhost:8001', param1='value1')")
    print("\nOr set environment variable EDSL_API_URL to change the default")
    
    # Show that the gateway URL parameter works
    print(f"\nDefault gateway URL: {API_BASE_URL}")
    print("Custom gateway URL: http://localhost:8001")

