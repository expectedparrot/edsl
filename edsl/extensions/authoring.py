from abc import ABC
from dataclasses import dataclass, field, asdict, fields, MISSING
from typing import Optional, Dict, Any, TypeVar, Type, Callable, List, Union
import requests # Added for __call__
#import doctest
from pydantic import create_model, Field, BaseModel

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
    ep_username: str = "test"

    def __post_init__(self):
        # If we got a dictionary, extract the fields from it
        if isinstance(self.unit, dict):
            data = self.unit  # The entire cost definition was passed as a dict in the unit field
            self.unit = data["unit"]
            self.per_call_cost = data["per_call_cost"]
            self.variable_pricing_cost_formula = data.get("variable_pricing_cost_formula")
            self.uses_client_ep_key = data.get("uses_client_ep_key", False)
            self.ep_username = data.get("ep_username", "test")


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


@dataclass
class ServiceDefinition(DictSerializable):
    name: str
    description: str
    parameters: Dict[str, Union[ParameterDefinition, Dict[str, Any]]]
    cost: Union[CostDefinition, Dict[str, Any]]
    service_returns: Dict[str, Union[ReturnDefinition, Dict[str, Any]]]
    endpoint: str
    # Internal attributes to be set by the client
    _base_url: Optional[str] = field(default=None, init=False, repr=False)
    _ep_api_token: Optional[str] = field(default=None, init=False, repr=False)
    _parameters: Parameters = field(init=False, repr=False)
    _response_processor: ServiceResponseProcessor = field(init=False, repr=False)
    _model_generator: ModelGenerator = field(init=False, repr=False)
    _service_caller_instance: Optional[ServiceCaller] = field(default=None, init=False, repr=False)

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
            "endpoint": self.endpoint
        }
    
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
            cost=CostDefinition.from_dict(data['cost']),
            service_returns={k: ReturnDefinition.from_dict(v) for k, v in data['service_returns'].items()},
            endpoint=data['endpoint']
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
            endpoint="X"
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
            f"Endpoint: {self.endpoint or 'N/A'}"
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



    


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

