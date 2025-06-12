from abc import ABC
from dataclasses import dataclass, field, asdict, fields, MISSING
from typing import Optional, Dict, Any, TypeVar, Type, Callable, List
import yaml  # Import the yaml library
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

class Service(Scenario):

    # def __init__(self, service_definition: 'ServiceDefinition'):
    #     super().__init__({'yaml_string': service_definition.to_yaml()})

    @classmethod
    def from_service_definition(cls, service_definition: 'ServiceDefinition') -> 'Service':
        return cls({'yaml_string':service_definition.to_yaml()})
    
    def to_service_definition(self) -> 'ServiceDefinition':
        return ServiceDefinition.from_yaml(self['yaml_string'])
    
    @classmethod
    def example(cls) -> 'Service':
        return cls(ServiceDefinition.example())

# (no top-level compute_price import – avoid circular dependency)

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


@dataclass
class CostDefinition(DictSerializable):
    unit: str
    per_call_cost: int
    variable_pricing_cost_formula: Optional[str] = None
    uses_client_ep_key: bool = False
    ep_username: str = "test"


@dataclass
class ReturnDefinition(DictSerializable):
    type: str
    description: str
    coopr_url: Optional[bool] = False


@dataclass
class ServiceDefinition(DictSerializable):
    name: str
    description: str
    parameters: Dict[str, ParameterDefinition]
    cost: CostDefinition
    service_returns: Dict[str, ReturnDefinition]
    endpoint: str
    # Internal attributes to be set by the client
    _base_url: Optional[str] = field(default=None, init=False, repr=False)
    _ep_api_token: Optional[str] = field(default=None, init=False, repr=False)

    def push(self, *args, **kwargs):
        service = Service.from_service_definition(self)
        return service.push(*args, **kwargs)

    def pull(self, *args, **kwargs):
        scenario = Scenario.pull(*args, **kwargs)
        return scenario.to_service_definition()

    def __post_init__(self):
        """Populate an instance-specific __doc__ right after initialization."""
        # Avoid dataclass immutability issues by using object.__setattr__
        object.__setattr__(self, "__doc__", self._generate_dynamic_doc())

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
        # Use the base to_dict logic potentially first, then handle nested
        # Or handle nested explicitly like before:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {k: v.to_dict() for k, v in self.parameters.items()},
            "cost": self.cost.to_dict(),
            "service_returns": {k: v.to_dict() for k, v in self.service_returns.items()},
            "endpoint": self.endpoint
        }

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
            endpoint="http://localhost:8000/test_create_survey"
        )

    def to_yaml(self) -> str:
        """Converts the ServiceDefinition instance to a YAML string.

        >>> sd = ServiceDefinition.example()
        >>> yaml_str = sd.to_yaml()
        >>> isinstance(yaml_str, str)
        True
        >>> # Check if a key known to be present exists
        >>> "name: create_survey" in yaml_str
        True
        >>> "parameters:" in yaml_str
        True
        >>> "endpoint: http://localhost:8000/test_create_survey" in yaml_str
        True
        """
        return yaml.dump(self.to_dict())

    @classmethod
    def from_yaml(cls, yaml_data: str) -> 'ServiceDefinition':
        """Creates a ServiceDefinition instance from a YAML string.

        >>> sd_orig = ServiceDefinition.example()
        >>> yaml_str = sd_orig.to_yaml()
        >>> sd_new = ServiceDefinition.from_yaml(yaml_str)
        >>> sd_new == sd_orig
        True
        """
        data = yaml.safe_load(yaml_data)
        return cls.from_dict(data)

    @classmethod
    def example_with_running(cls) -> 'ServiceDefinition':
        """Returns an example instance of a service for running a survey."""
        return cls(
            name="run_survey",
            description="runs a survey",
            parameters={
                "survey": ParameterDefinition(
                    type="Survey", # Assuming Survey is a known type or will be registered
                    required=True,
                    description="The EDSL survey object to run"
                )
            },
            cost=CostDefinition(
                unit="ep_credits",
                per_call_cost=50, # Example cost
                uses_client_ep_key=True # Assuming running a survey needs API key
            ),
            service_returns={
                'results': ReturnDefinition( # Example return
                    type="dict",
                    description="A dictionary containing the survey results"
                )
            },
            endpoint="http://localhost:8000/test_run_survey" # Example endpoint
        )

    def validate_call_parameters(self, params: Dict[str, Any]):
        """Validates that all required parameters are present and of the correct type for a call.

        Raises:
            ServiceParameterValidationError: If validation fails (missing required param or type mismatch).
        """
        for param_name, param_def in self.parameters.items():
            # Check for missing required parameters (only if no default is defined)
            if param_def.required and param_name not in params and param_def.default_value is MISSING:
                 raise ServiceParameterValidationError(f"Missing required parameter: {param_name}")

            # Check type if parameter is provided
            if param_name in params:
                expected_type_str = param_def.type.lower()
                actual_value = params[param_name]
                type_mismatch = False

                # Basic type validation
                if expected_type_str in ("string", "str") and not isinstance(actual_value, str):
                    type_mismatch = True
                elif expected_type_str in ("int", "integer") and not isinstance(actual_value, int):
                    # Allow ints where floats are expected
                    if not (expected_type_str in ("number", "float") and isinstance(actual_value, int)):
                         type_mismatch = True
                elif expected_type_str in ("number", "float") and not isinstance(actual_value, (int, float)):
                     type_mismatch = True
                elif expected_type_str in ("bool", "boolean") and not isinstance(actual_value, bool):
                    type_mismatch = True
                elif expected_type_str in ("list", "array") and not isinstance(actual_value, list):
                    type_mismatch = True
                elif expected_type_str in ("dict", "object") and not isinstance(actual_value, dict):
                    type_mismatch = True
                # Add more complex type checks if needed (e.g., for custom EDSL objects)

                if type_mismatch:
                    raise ServiceParameterValidationError(
                        f"Parameter '{param_name}' has incorrect type. "
                        f"Expected '{param_def.type}', got '{type(actual_value).__name__}'"
                    )

    def _prepare_parameters(self, **kwargs: Any) -> Dict[str, Any]:
        """Prepares the dictionary of parameters for the API call, serializing EDSL objects and including defaults.
        Assumes parameters have been validated by validate_call_parameters.
        """
        # Prepare payload, serializing EDSL objects and including defaults
        call_params = {}
        edsl_registry = RegisterSubclassesMeta.get_registry() # Get the registry

        for param_name, param_def in self.parameters.items():
            if param_name in kwargs:
                value = kwargs[param_name]
                expected_type_str = param_def.type

                # Check if the expected type is a registered EDSL type
                if expected_type_str in edsl_registry:
                    target_cls = edsl_registry[expected_type_str]
                    # Check if the provided value is an instance of this EDSL type
                    # and has a 'to_dict' method. Validation should have already ensured type match.
                    if isinstance(value, target_cls) and hasattr(value, 'to_dict'):
                        call_params[param_name] = value.to_dict() # Serialize
                    else:
                        # This case *shouldn't* happen if validate_call_parameters was called first
                        # and the registry/type definitions are consistent.
                        # Passing as-is might be risky. Assuming validation covers mismatches.
                        call_params[param_name] = value
                else:
                    # Not an EDSL type, pass as-is
                    call_params[param_name] = value
            elif param_def.default_value is not MISSING:
                 # Use default value if provided parameter is missing
                 call_params[param_name] = param_def.default_value

        return call_params

    def _make_api_call(self, payload: Dict[str, Any]) -> requests.Response:
        """Makes the API request to the gateway and returns the response object."""
        if not self._base_url:
            # Raise ServiceConfigurationError for missing base_url
            raise ServiceConfigurationError(f"Service '{self.name}' cannot be called via the gateway. Configuration missing (base_url).")

        url = f"{self._base_url.rstrip('/')}/service/"
        response = None # Initialize response to None
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status() # Raises HTTPError for 4xx/5xx
            return response
        except requests.exceptions.HTTPError as e:
            # Raise ServiceResponseError for bad status codes
            error_message = f"Error calling service '{self.name}' at {url}. Server returned status {e.response.status_code}."
            try:
                error_message += f" Response: {e.response.text}"
            except Exception:
                error_message += " Response content could not be read."
            print(error_message) # Keep print for logging, but raise specific error
            raise ServiceResponseError(error_message) from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Raise ServiceConnectionError for connection issues
            error_message = f"Error connecting to service '{self.name}' at {url}: {e}"
            print(error_message)
            raise ServiceConnectionError(error_message) from e
        except requests.exceptions.RequestException as e:
            # Catch other potential request errors (e.g., invalid URL, too many redirects)
            error_message = f"Error during request for service '{self.name}' at {url}: {e}"
            if response is not None: # This part might be less relevant now if HTTPError is caught first
                error_message += f"\nResponse status (potentially before error): {response.status_code}"
                try:
                    error_message += f"\nResponse content: {response.text}"
                except Exception:
                    error_message += "\nResponse content could not be read."
            print(error_message)
            # Use ServiceConnectionError as a general category for request issues
            raise ServiceConnectionError(error_message) from e

    def _deserialize_single_value(self, return_key: str, return_def: ReturnDefinition, response_data: Dict[str, Any]) -> Any:
        """Deserializes a single value from the response data based on its definition."""
        raw_value = response_data.get(return_key)
        if raw_value is None:
            raise ServiceDeserializationError(f"Expected return key '{return_key}' not found in response for service '{self.name}'.")

        return_type_str = return_def.type
        edsl_registry = RegisterSubclassesMeta.get_registry()

        # Check registered EDSL types
        if return_type_str in edsl_registry:
            target_cls = edsl_registry[return_type_str]
            try:
                # Ensure raw_value is a dict for from_dict
                if not isinstance(raw_value, dict):
                     raise ServiceDeserializationError(f"Expected dict for EDSL type '{return_type_str}' key '{return_key}', got {type(raw_value).__name__}.")
                return target_cls.from_dict(raw_value)
            except Exception as e:
                msg = f"Failed to deserialize response key '{return_key}' into {target_cls.__name__} for service '{self.name}'. Error: {e}"
                raise ServiceDeserializationError(msg) from e
        # Check standard Python types
        elif return_type_str in ('str', 'string'):
            try:
                return str(raw_value)
            except ValueError as e:
                raise ServiceDeserializationError(f"Could not convert value for key '{return_key}' to str.") from e
        elif return_type_str in ('int', 'integer'):
            try:
                return int(raw_value)
            except (ValueError, TypeError) as e:
                raise ServiceDeserializationError(f"Could not convert value for key '{return_key}' to int.") from e
        elif return_type_str in ('float', 'number'):
            try:
                return float(raw_value)
            except (ValueError, TypeError) as e:
                raise ServiceDeserializationError(f"Could not convert value for key '{return_key}' to float.") from e
        elif return_type_str in ('bool', 'boolean'):
            # Handle potential string representations of bool
            if isinstance(raw_value, str):
                if raw_value.lower() == 'true':
                    return True
                elif raw_value.lower() == 'false':
                    return False
            try:
                return bool(raw_value)
            except ValueError as e:
                raise ServiceDeserializationError(f"Could not convert value for key '{return_key}' to bool.") from e
        elif return_type_str in ('list', 'array'):
             try:
                # Ensure it's actually list-like, basic check
                if not isinstance(raw_value, list):
                    raise TypeError # Caught below
                return list(raw_value)
             except TypeError as e:
                raise ServiceDeserializationError(f"Could not convert value for key '{return_key}' to list.") from e
        elif return_type_str in ('dict', 'object'):
             try:
                 # Ensure it's actually dict-like, basic check
                if not isinstance(raw_value, dict):
                    raise TypeError # Caught below
                return dict(raw_value)
             except (TypeError, ValueError) as e:
                raise ServiceDeserializationError(f"Could not convert value for key '{return_key}' to dict.") from e
        else:
            # Type not recognized - raise an error instead of returning raw value
            raise ServiceDeserializationError(f"Unrecognized return type '{return_type_str}' defined for key '{return_key}' in service '{self.name}'.")

    def _deserialize_response(self, response: requests.Response) -> Any:
        """Deserializes the API response based on the service definition."""
        try:
            response_data = response.json()
        except json.JSONDecodeError as e:
            msg = f"Error decoding JSON response from service '{self.name}'. Response text: {response.text[:500]}..."
            # print(msg) # Keep print for logging maybe?
            raise ServiceResponseError(msg) from e # Re-raise

        # If no specific returns defined, return the raw data
        if not self.service_returns:
             # Perhaps raise an error or warning if returns ARE expected but none defined?
             # For now, returning raw data is the existing behavior.
             return response_data

        deserialized_results = {}
        try:
            for return_key, return_def in self.service_returns.items():
                deserialized_value = self._deserialize_single_value(return_key, return_def, response_data)
                # We store the result even if it's None (due to missing key or deserialization failure)
                # to indicate that we attempted to process this key.
                deserialized_results[return_key] = deserialized_value
        except ServiceDeserializationError as e:
             # Catch errors from _deserialize_single_value and re-raise
             raise e
        except Exception as e:
             # Catch unexpected errors during deserialization loop
             raise ServiceDeserializationError(f"Unexpected error during response deserialization for service '{self.name}': {e}") from e


        # Always return a dictionary, even if only one item was expected/processed.
        # This provides a consistent return structure.
        return deserialized_results

    def call_via_gateway(self, **kwargs: Any) -> Any:
        """
        Executes the API call **via the gateway** for this service using provided parameters.
        Validates parameters, prepares payload, executes the call, and deserializes the response.

        Args:
            **kwargs: Parameters for the service call.

        Returns:
            The API response, potentially deserialized based on service definition.

        Raises:
            ServiceParameterValidationError: If validation fails (missing/incorrect params).
            ServiceConfigurationError: If internal configuration (_base_url) is not set.
            ServiceConnectionError: If the API call fails due to connection issues.
            ServiceResponseError: If the API call returns an error status or invalid JSON.
            ServiceDeserializationError: If the response cannot be deserialized correctly.
        """
        # Validation raises ServiceParameterValidationError
        self.validate_call_parameters(kwargs)
        prepared_params = self._prepare_parameters(**kwargs)
        # Construct the payload specific to the gateway's /service/ endpoint
        payload = {
            "service": self.name,
            "params": prepared_params
        }
        if self._ep_api_token:
            payload["ep_api_token"] = self._ep_api_token

        # Display a spinner with elapsed-time feedback while the request is in flight.
        logger.info("Calling service '%s' via gateway...", self.name)

        class _Spinner:
            """Lightweight console spinner that also shows elapsed seconds."""

            def __init__(self, message: str, delay: float = 0.1):
                self.message = message.rstrip()
                self.delay = delay
                self._stop_event = threading.Event()
                self._thread = threading.Thread(target=self._spin, daemon=True)

            def _spin(self):
                spinner_chars = itertools.cycle("|/-\\")
                start = time.time()
                while not self._stop_event.is_set():
                    char = next(spinner_chars)
                    elapsed = time.time() - start
                    sys.stdout.write(f"\r{self.message} {char} {elapsed:.1f}s")
                    sys.stdout.flush()
                    time.sleep(self.delay)
                # Clear line and print final time
                elapsed = time.time() - start
                sys.stdout.write(f"\r{self.message} done in {elapsed:.2f}s\n")
                sys.stdout.flush()

            def start(self):
                if sys.stdout.isatty():
                    self._thread.start()

            def stop(self):
                if sys.stdout.isatty():
                    self._stop_event.set()
                    self._thread.join()

        spinner = _Spinner(message=f"Calling service '{self.name}' via gateway")
        spinner.start()
        try:
            # _make_api_call raises ServiceConfigurationError, ServiceConnectionError, ServiceResponseError
            response = self._make_api_call(payload)
            # _deserialize_response raises ServiceResponseError, ServiceDeserializationError
            return self._deserialize_response(response)
        finally:
            spinner.stop()

        # --- Print/log estimated cost -----------------------------------
        try:
            from .price_calculation import compute_price  # local import to avoid circular deps
            estimated_cost = compute_price(self, prepared_params)
            logger.info("Estimated cost for call to '%s': %s %s", self.name, estimated_cost, self.cost.unit)
        except Exception as _e:
            # Avoid hard failure if pricing formula is invalid – just log at debug level.
            logger.debug("Could not compute price for '%s': %s", self.name, _e)

    def __call__(self, **kwargs: Any) -> Any:
        """
        Executes the service call via the gateway only (no automatic
        fallback to a direct endpoint).

        Args:
            **kwargs: Parameters for the service call.

        Returns:
            The API response, potentially deserialized based on the service
            definition.

        Raises:
            All exceptions are propagated from `call_via_gateway` so callers
            can handle them as needed.
        """
        # --- Estimate cost and potentially ask for confirmation --------
        try:
            from .price_calculation import compute_price  # Local import to avoid circular deps
            estimated_cost = compute_price(self, kwargs)
        except Exception as _e:  # pragma: no cover – cost estimation failure should never abort the call
            logger.debug("Could not compute price for '%s': %s", self.name, _e)
            estimated_cost = None

        # Check env var – if set and a numeric value, compare against the cost
        #threshold_str = os.getenv("MAX_PRICE_BEFORE_CONFIRM")
        from ..config import CONFIG
        threshold_str = CONFIG.EDSL_MAX_PRICE_BEFORE_CONFIRM
        #threshold_str = "90"
        threshold: Optional[int] = None
        if threshold_str is not None:
            try:
                threshold = int(threshold_str)
            except ValueError:
                logger.warning("Environment variable MAX_PRICE_BEFORE_CONFIRM is not a valid integer: %s", threshold_str)

        if estimated_cost is not None and threshold is not None and estimated_cost > threshold:
            # Prompt the user for confirmation. Use a simple stdin prompt so the check works in most shells.
            prompt = (
                f"This service call is estimated to cost {estimated_cost} {self.cost.unit}, "
                f"which exceeds your threshold of {threshold}. Proceed? [y/N]: "
            )
            try:
                user_input = input(prompt)
            except EOFError:
                # Non-interactive environment – default to 'no'
                logger.info("No TTY available for confirmation prompt; aborting expensive call.")
                return None

            if user_input.strip().lower() not in ("y", "yes"):
                logger.info("User declined to proceed with service '%s' due to estimated cost.", self.name)
                print("Aborted service call.")
                return None

        # Proceed with the actual call – call_via_gateway handles the rest
        return self.call_via_gateway(**kwargs)

    def call_directly(self, **kwargs: Any) -> Any:
        """
        Executes the API call **directly** to the service's endpoint using provided parameters.
        Validates parameters, prepares payload, constructs headers, executes the call, and deserializes the response.

        Args:
            **kwargs: Parameters for the service call.

        Returns:
            The API response, potentially deserialized based on service definition.

        Raises:
            ServiceParameterValidationError: If validation fails (missing/incorrect params).
            ServiceConfigurationError: If the endpoint is not defined.
            ServiceConnectionError: If the API call fails due to connection issues.
            ServiceResponseError: If the API call returns an error status or invalid JSON.
            ServiceDeserializationError: If the response cannot be deserialized correctly.
        """
        if not self.endpoint:
            raise ServiceConfigurationError(f"Service '{self.name}' cannot be called directly. 'endpoint' is not defined.")

        # Validation raises ServiceParameterValidationError
        self.validate_call_parameters(kwargs)
        prepared_params = self._prepare_parameters(**kwargs)

        headers = {"Content-Type": "application/json"}
        if self._ep_api_token:
            headers["Authorization"] = f"Bearer {self._ep_api_token}"

        url = self.endpoint
        response = None # Initialize response to None for broader scope in error handling
        try:
            # Make the direct POST request
            response = requests.post(url, json=prepared_params, headers=headers)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            # Deserialize response, catching potential errors
            # _deserialize_response raises ServiceResponseError (for JSON decode), ServiceDeserializationError
            return self._deserialize_response(response)

        except requests.exceptions.HTTPError as e:
            # Raise ServiceResponseError for bad status codes
            error_message = f"Error calling service '{self.name}' directly at {url}. Server returned status {e.response.status_code}."
            try:
                error_message += f" Response: {e.response.text}"
            except Exception:
                error_message += " Response content could not be read."
            print(error_message) # Keep print for logging
            raise ServiceResponseError(error_message) from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Raise ServiceConnectionError for connection issues
            error_message = f"Error connecting to service '{self.name}' directly at {url}: {e}"
            print(error_message)
            raise ServiceConnectionError(error_message) from e
        except requests.exceptions.RequestException as e:
            # Catch other potential request errors
            error_message = f"Error during direct request for service '{self.name}' at {url}: {e}"
            if response is not None:
                error_message += f"\nResponse status (potentially before error): {response.status_code}"
                try:
                    error_message += f"\nResponse content: {response.text}"
                except Exception:
                    error_message += "\nResponse content could not be read."
            print(error_message)
            raise ServiceConnectionError(error_message) from e
        except (ServiceResponseError, ServiceDeserializationError) as e:
            # Re-raise errors from _deserialize_response
            raise e
        except Exception as e:
            # Catch any other unexpected errors during the process
            raise ExtensionError(f"Unexpected error during direct call for service '{self.name}': {e}") from e

        # --- Print/log estimated cost -----------------------------------
        try:
            from .price_calculation import compute_price  # local import to avoid circular deps
            estimated_cost = compute_price(self, prepared_params)
            logger.info("Estimated cost for direct call to '%s': %s %s", self.name, estimated_cost, self.cost.unit)
        except Exception as _e:
            logger.debug("Could not compute price for '%s': %s", self.name, _e)

    def validate_service_output(self, output_data: Dict[str, Any]):
        """
        Validates the structure and types of the service output dictionary against the 'service_returns' definition.

        Args:
            output_data: The dictionary returned by the service implementation.

        Raises:
            TypeError: If the output_data is not a dictionary.
            ServiceOutputValidationError: If a required return key is missing or a value has the wrong type.
        """
        if not isinstance(output_data, dict):
             # Keep TypeError for the overall output structure being wrong
             raise TypeError(f"Service output must be a dictionary, but got {type(output_data).__name__}.")

        edsl_registry = RegisterSubclassesMeta.get_registry()
        TYPE_MAP = {
            "str": str, "string": str,
            "int": int, "integer": int,
            "float": float, "number": float,
            "bool": bool, "boolean": bool,
            "list": list, "array": list,
            "dict": dict, "object": dict,
            # Add other basic types if necessary
        }

        for return_key, return_def in self.service_returns.items():
            # Check if the key exists in the output
            if return_key not in output_data:
                # Changed ValueError to ServiceOutputValidationError
                raise ServiceOutputValidationError(f"Missing expected return key in service output: '{return_key}'")

            actual_value = output_data[return_key]
            expected_type_str = return_def.type

            # Type Validation
            expected_python_type = TYPE_MAP.get(expected_type_str.lower())

            if expected_type_str in edsl_registry:
                # For EDSL objects defined in returns, we expect a dictionary representation
                if not isinstance(actual_value, dict):
                    # Changed TypeError to ServiceOutputValidationError
                    raise ServiceOutputValidationError(
                        f"Type mismatch for return key '{return_key}'. "
                        f"Expected a dictionary representation of EDSL type '{expected_type_str}', "
                        f"but got type '{type(actual_value).__name__}'."
                    )
                # Optional: Deeper validation (as before)
                # ...

            elif expected_python_type:
                # Basic Python types
                # Special case: allow int for float/number
                if expected_python_type in (float,) and isinstance(actual_value, int):
                    pass # Allow int where float/number is expected
                elif not isinstance(actual_value, expected_python_type):
                    # Changed TypeError to ServiceOutputValidationError
                    raise ServiceOutputValidationError(
                        f"Type mismatch for return key '{return_key}'. "
                        f"Expected type '{expected_type_str}' (mapped to {expected_python_type.__name__}), "
                        f"but got type '{type(actual_value).__name__}'."
                    )
            else:
                # Type not found in basic map or EDSL registry
                # Changed from print warning to raising an error
                raise ServiceOutputValidationError(f"Unknown type '{expected_type_str}' defined for return key '{return_key}'. Cannot validate.")
                # print(f"Warning: Unknown type '{expected_type_str}' for return key '{return_key}'. Skipping type validation.")

    def get_request_model(self) -> Type[BaseModel]:
        """Dynamically creates a Pydantic model for the service parameters."""
        fields_definitions = {}
        edsl_registry = RegisterSubclassesMeta.get_registry()

        TYPE_MAP = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": float,
            "number": float,
            "bool": bool,
            "boolean": bool,
            "list": List[Any],
            "array": List[Any],
            "dict": Dict[str, Any],
            "object": Dict[str, Any],
        }

        for param_name, param_def in self.parameters.items():
            type_str = param_def.type
            python_type = TYPE_MAP.get(type_str.lower())

            # If not a basic type, check if it's a known EDSL type (expect dict)
            if python_type is None and type_str in edsl_registry:
                python_type = Dict[str, Any] # Expect serialized dict for EDSL objects
            elif python_type is None:
                python_type = Any # Default to Any if type is unknown

            default_value = param_def.default_value
            description = param_def.description

            if default_value is not MISSING:
                # Parameter has a default value
                field_definition = Field(default=default_value, description=description)
                type_annotation = python_type
            else:
                # Parameter does not have a default value
                if param_def.required:
                    # Required parameter
                    field_definition = Field(description=description)
                    type_annotation = python_type
                else:
                    # Optional parameter (required=False, no default)
                    field_definition = Field(default=None, description=description)
                    type_annotation = Optional[python_type]

            fields_definitions[param_name] = (type_annotation, field_definition)

        # Create a suitable model name
        model_name = f"{self.name.replace('_', ' ').title().replace(' ', '')}Parameters"
        # Dynamically create the Pydantic model
        pydantic_model = create_model(
            model_name,
            **fields_definitions,
            __base__=BaseModel
        )
        return pydantic_model

    def get_response_model(self) -> Type[BaseModel]:
        """Dynamically creates a Pydantic model for the service return values."""
        fields_definitions = {}
        edsl_registry = RegisterSubclassesMeta.get_registry()

        TYPE_MAP = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": float,
            "number": float,
            "bool": bool,
            "boolean": bool,
            "list": List[Any],
            "array": List[Any],
            "dict": Dict[str, Any],
            "object": Dict[str, Any],
        }

        for return_key, return_def in self.service_returns.items():
            type_str = return_def.type
            python_type = TYPE_MAP.get(type_str.lower())

            # Check EDSL types (expect dict representation in response)
            if python_type is None and type_str in edsl_registry:
                python_type = Dict[str, Any]
            elif python_type is None:
                python_type = Any # Default to Any if type is unknown

            description = return_def.description

            # All return fields are effectively required in the response model
            field_definition = Field(description=description)
            type_annotation = python_type

            fields_definitions[return_key] = (type_annotation, field_definition)

        # Create a suitable model name
        model_name = f"{self.name.replace('_', ' ').title().replace(' ', '')}Response"
        # Dynamically create the Pydantic model
        pydantic_model = create_model(
            model_name,
            **fields_definitions,
            __base__=BaseModel
        )
        return pydantic_model

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




def extract_bearer_token(authorization: str | None) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    raise HTTPException(401, "Missing or invalid Bearer token")



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
