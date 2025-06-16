from abc import ABC
from pathlib import Path
from dataclasses import dataclass, field, asdict, fields, MISSING
from typing import Optional, Dict, Any, TypeVar, Type, Callable, List, Union, TYPE_CHECKING
import requests # Added for __call__
#import doctest
from pydantic import create_model, Field, BaseModel
import yaml  # Added for YAML serialization

import json
import os
# Std-lib imports for spinner/timer functionality
import sys
import threading
import itertools
import time
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
from .response_processor import ServiceResponseProcessor
from .model_generation import ModelGenerator

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

# Removed Exception Classes (moved to exceptions.py)

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

from collections import UserDict

from typing import TypedDict

class ServiceLocation(TypedDict):
    service_name: str
    creator_ep_username: str
    gateway_url: str
    service_url: str

class ServiceLocations(TypedDict):
    def __init__(self, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.locations = {}
    
    def add_location(self, name: str, location: ServiceLocation) -> None:
        self.locations[name] = location

    def get_service_endpoint(self, service_name: str) -> str:
        return self.locations[service_name]["service_url"] + "/" + self.locations[service_name]["service_name"]


@dataclass
class ServiceDefinition(DictSerializable):
    name: str
    description: str
    parameters: Dict[str, Union[ParameterDefinition, Dict[str, Any]]]
    cost: Union[CostDefinition, Dict[str, Any]]
    service_returns: Dict[str, Union[ReturnDefinition, Dict[str, Any]]]
    # Internal attributes to be set by the client
    _base_url: Optional[str] = field(default=None, init=False, repr=False)
    _ep_api_token: Optional[str] = field(default=None, init=False, repr=False)
    _parameters: Parameters = field(init=False, repr=False)
    _response_processor: ServiceResponseProcessor = field(init=False, repr=False)
    _model_generator: ModelGenerator = field(init=False, repr=False)
    _service_caller_instance: Optional[ServiceCaller] = field(default=None, init=False, repr=False)
    creator_ep_username: str = "test"

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
            service_name=self.name,
            service_returns=self.service_returns
        )

        # Initialize model generator
        self._model_generator = ModelGenerator(
            service_name=self.name,
            parameters=self.parameters,
            service_returns=self.service_returns
        )

        # Handle cost
        if isinstance(self.cost, dict):
            self.cost = CostDefinition(self.cost, 0)  # The dict will be processed in CostDefinition's __post_init__

        # Generate dynamic doc
        object.__setattr__(self, "__doc__", self._generate_dynamic_doc())

    @property
    def _service_caller(self) -> ServiceCaller:
        """Lazy-loaded ServiceCaller instance."""
        if self._service_caller_instance is None:
            if not self._base_url:
                raise ServiceConfigurationError(f"Service '{self.name}' cannot be called. Configuration missing (base_url).")
            self._service_caller_instance = ServiceCaller(
                service_name=self.name,
                base_url=self._base_url,
                ep_api_token=self._ep_api_token
            )
        return self._service_caller_instance

    def push(self, *args, **kwargs):
        #service = Service.from_service_definition(self)
        scenario = Scenario(self.to_dict())
        return scenario.push(*args, **kwargs)
    
    @classmethod
    def pull(cls, *args, **kwargs):
        scenario = Scenario.pull(*args, **kwargs)
        return cls.from_dict(scenario.to_dict())
    
    @classmethod
    def from_uuid(cls, service_uuid: str) -> 'ServiceDefinition':
        from edsl import Scenario
        scenario = Scenario.pull(service_uuid)
        return cls.from_dict(scenario.to_dict())
    
    def update(self, service_uuid: str):
        new_scenario = Scenario(self.to_dict())
        return Scenario.patch(service_uuid, value = new_scenario)
                
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
        >>> d['endpoint'] == 'http://localhost:8000/test_create_survey'
        True
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {k: v.to_dict() for k, v in self.parameters.items()},
            "cost": self.cost.to_dict(),
            "service_returns": {k: v.to_dict() for k, v in self.service_returns.items()},
            "creator_ep_username": self.creator_ep_username,
        }
    
    def __hash__(self) -> int:
        return hash(Scenario(self.to_dict()))

    def add_service_to_expected_parrot(self) -> None:
        """Adds a service to the registry"""
        from .services_model import ServicesRegistry
        print("Fetching current services")
        services_registry = ServicesRegistry.from_config()
        print("Adding service to Expected Parrot")
        services_registry.add_service(self)
        print("Service added to Expected Parrot")

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
            name=data['name'],
            description=data['description'],
            parameters={k: ParameterDefinition.from_dict(v) for k, v in data['parameters'].items()},
            cost=CostDefinition.from_dict({k: v for k, v in data['cost'].items() if k != 'ep_username'}),
            service_returns={k: ReturnDefinition.from_dict(v) for k, v in data['service_returns'].items()},
            creator_ep_username=data.get('creator_ep_username', 'test'),
        )

    @classmethod
    def example(cls) -> 'ServiceDefinition':
        """Returns an example instance of the ServiceDefinition."""
        return cls(
            name="create_survey",
            description="Creates a survey to answer an overall research question",
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

    def __call__(self, **kwargs: Any) -> Any:
        """
        Executes the API call for this service using provided parameters.

        Args:
            **kwargs: Parameters for the service call.

        Returns:
            The API response, potentially deserialized based on service definition.

        Raises:
            ServiceParameterValidationError: If validation fails (missing/incorrect params).
            ServiceConfigurationError: If base_url is not set when needed.
            ServiceConnectionError: If the API call fails due to connection issues.
            ServiceResponseError: If the API call returns an error status or invalid JSON.
            ServiceDeserializationError: If the response cannot be deserialized correctly.
        """
        # Validate and prepare parameters
        self.validate_call_parameters(kwargs)
        prepared_params = self._prepare_parameters(**kwargs)

        # Make the service call - this will raise ServiceConfigurationError if base_url not set
        result = self._service_caller.call_service(
            prepared_params=prepared_params,
            deserialize_response=self._response_processor.deserialize_response
        )

        # Log estimated cost
        try:
            from .price_calculation import compute_price  # local import to avoid circular deps
            estimated_cost = compute_price(self, prepared_params)
            logger.info("Estimated cost for call to '%s': %s %s", self.name, estimated_cost, self.cost.unit)
        except Exception as _e:
            # Avoid hard failure if pricing formula is invalid – just log at debug level.
            logger.debug("Could not compute price for '%s': %s", self.name, _e)

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
        signature = f"{self.name}({', '.join(signature_parts)})"

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

    def call_directly(self, ep_api_token: Optional[str] = None, timeout: int = 120, **kwargs: Any) -> Any:
        """Call the service *directly* at the URL contained in ``self.endpoint`` – bypassing the
        gateway entirely.

        Parameters
        ----------
        ep_api_token : str, optional
            Bearer token to forward in the ``Authorization`` header.  If not supplied, the
            value previously set via ``service_def._ep_api_token`` (if any) is used.
        timeout : int, default ``120`` seconds
            Request timeout in seconds passed through to ``requests.post``.
        **kwargs : Any
            Service parameters (same as for calling the service via the gateway).

        Returns
        -------
        Any
            Deserialised response according to the service's ``service_returns`` definition.

        Raises
        ------
        ServiceParameterValidationError
            If required parameters are missing or of wrong type.
        ServiceResponseError
            If the endpoint returns an HTTP status ≥400.
        ServiceConnectionError
            If the HTTP request fails due to network issues.
        ServiceDeserializationError
            If the response body cannot be parsed or mapped to the declared return types.
        ServiceConfigurationError
            If ``self.endpoint`` is empty.
        """
        # ------------------------------------------------------------------
        # 1) Validate parameters and build the JSON payload
        # ------------------------------------------------------------------
        self.validate_call_parameters(kwargs)
        prepared_params = self._prepare_parameters(**kwargs)

        # ------------------------------------------------------------------
        # 2) Build HTTP request details
        # ------------------------------------------------------------------
        if not self.endpoint:
            raise ServiceConfigurationError(
                f"Service '{self.name}' has no endpoint defined – cannot call directly.")

        url = self.endpoint.rstrip("/")  # Avoid accidental double slashes
        headers: Dict[str, str] = {"Content-Type": "application/json"}

        token = ep_api_token or self._ep_api_token
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # ------------------------------------------------------------------
        # 3) Execute the request
        # ------------------------------------------------------------------
        try:
            response = requests.post(url, json=prepared_params, headers=headers, timeout=timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise ServiceConnectionError(
                f"Error connecting to service '{self.name}' at {url}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise ServiceConnectionError(
                f"Unexpected error calling service '{self.name}' at {url}: {e}") from e

        # Error status codes – surface as ServiceResponseError for consistency
        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise ServiceResponseError(
                f"Direct call to '{self.name}' failed with status {response.status_code}: {detail}")

        # ------------------------------------------------------------------
        # 4) Deserialize & log cost as in the standard __call__ path
        # ------------------------------------------------------------------
        result = self._response_processor.deserialize_response(response)

        try:
            from .price_calculation import compute_price  # local import to avoid circular deps
            estimated_cost = compute_price(self, prepared_params)
            logger.info("Estimated cost for direct call to '%s': %s %s", self.name, estimated_cost, self.cost.unit)
        except Exception as _e:
            logger.debug("Could not compute price for '%s' (direct call): %s", self.name, _e)

        return result

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


class Service:
    def __init__(
        self, 
        implementation: Callable, 
        overwrite: bool = False,
        name: Optional[str] = None,
        description: Optional[str] = None,
        endpoint: Optional[str] = None,
        cost_unit: Optional[str] = None,
        per_call_cost: Optional[int] = None,
        variable_pricing_cost_formula: Optional[str] = None,
        uses_client_ep_key: Optional[bool] = None,
        creator_ep_username: Optional[str] = None
    ):
        from .service_definition_helper import ServiceDefinitionHelper
        self.implementation = implementation
        helper = ServiceDefinitionHelper(implementation)
        self.service_def = helper.propose_service_definition()
        
        # Override service definition fields if provided
        if name:
            self.service_def.name = name
        if description:
            self.service_def.description = description
        if endpoint:
            self.service_def.endpoint = endpoint
            
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
        yaml_path = configs_dir / f"{self.service_def.name}.yaml"
        
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


class Services:
    """A container class for managing multiple service definitions."""
    
    def __init__(self):
        self._services: Dict[str, Service] = {}
    
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
            **kwargs: Additional keyword arguments to pass to the Service constructor (e.g., name, description, 
                     endpoint, cost_unit, per_call_cost, variable_pricing_cost_formula, uses_client_ep_key, ep_username)
        """
        service = Service(implementation, overwrite=overwrite, **kwargs)
        self._services[service.service_def.name] = service
    
    def set_base_url(self, base_url: str) -> None:
        """Set the base URL for all service definitions in this container.
        
        Args:
            base_url: The base URL to set for all services
        """
        for service in self._services.values():
            service.service_def._base_url = base_url
    
    def __getitem__(self, key: str) -> Service:
        """Get a service by name."""
        return self._services[key]
    
    def __iter__(self):
        """Iterate over services."""
        return iter(self._services.values())
    
    def __len__(self) -> int:
        """Get number of services."""
        return len(self._services)


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)


# ---------------------------------------------------------------------------
# ExtensionSource – simple helper to push a local extension repo to gateway
# ---------------------------------------------------------------------------


@dataclass
class ExtensionSource:
    """Utility for packaging a local directory and pushing it to a running
    extension-gateway instance via the `/receive_extension_repository` route.

    Example
    -------
    >>> es = ExtensionSource(path="/path/to/extension_repo")
    >>> es.push()  # doctest: +ELLIPSIS
    {"archive": ..., "file_count": ...}
    """

    path: str
    gateway_url: str = "http://localhost:8000/receive_extension_repository"

    def _collect_files(self) -> List[tuple]:
        """Walk *self.path* recursively and build the `files` payload list for
        `requests.post`.  Each list element is a 2-tuple with key 'files' so
        that FastAPI interprets them as multiple values of the same field.
        The tuple structure is `(fieldname, (filename, fileobj, content_type))`.
        """

        if not os.path.isdir(self.path):
            raise FileNotFoundError(f"ExtensionSource path not found or not a directory: {self.path}")

        payload: List[tuple] = []

        for root, _dirs, filenames in os.walk(self.path):
            for fname in filenames:
                f_path = os.path.join(root, fname)
                # Preserve directory hierarchy via relative path.
                rel_path = os.path.relpath(f_path, self.path)

                # Read content immediately to avoid keeping many file handles open.
                # For typical extension repositories this memory footprint is small
                # (tens/hundreds of KB).  For larger trees consider streaming or
                # packaging into a single archive instead.
                with open(f_path, "rb") as f_obj:
                    content_bytes = f_obj.read()

                payload.append(
                    (
                        "files",
                        (rel_path, content_bytes, "application/octet-stream"),
                    )
                )

        if not payload:
            raise ValueError(f"No files found under {self.path} to push")

        return payload

    def push(self) -> Dict[str, Any]:
        """POST the contents of *path* to the gateway.  Returns parsed JSON
        response on success or raises an HTTPException on non-2xx status codes.
        """

        files_payload = self._collect_files()

        # Directly post – no need to close file handles since we embedded bytes.
        response = requests.post(self.gateway_url, files=files_payload, timeout=300)

        if response.status_code >= 400:
            # Re-raise as FastAPI-style HTTPException for consistency with other components.
            raise HTTPException(status_code=response.status_code, detail=response.text)

        try:
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not decode gateway response: {e}")

