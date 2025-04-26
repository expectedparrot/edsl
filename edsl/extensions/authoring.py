from abc import ABC
from dataclasses import dataclass, field, asdict, fields, MISSING
from typing import Optional, Dict, Any, TypeVar, Type, Callable
import yaml  # Import the yaml library
import requests # Added for __call__
#import doctest

import json
import requests

from edsl import Survey # Assume Survey is always available
from edsl.base import RegisterSubclassesMeta

T = TypeVar('T', bound='DictSerializable')

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
            ValueError: If validation fails (missing required param or type mismatch).
        """
        for param_name, param_def in self.parameters.items():
            # Check for missing required parameters (only if no default is defined)
            if param_def.required and param_name not in params and param_def.default_value is MISSING:
                 raise ValueError(f"Missing required parameter: {param_name}")

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
                    raise ValueError(
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
            raise ValueError(f"Service '{self.name}' cannot be called via the gateway. Configuration missing (base_url).")

        url = f"{self._base_url.rstrip('/')}/service/"
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            error_message = f"Error calling service '{self.name}' at {url}: {e}"
            if response is not None:
                error_message += f"\nResponse status: {response.status_code}"
                try:
                    error_message += f"\nResponse content: {response.text}"
                except Exception:
                    error_message += "\nResponse content could not be read."
            print(error_message)
            raise e # Re-raise the exception

    def _deserialize_single_value(self, return_key: str, return_def: ReturnDefinition, response_data: Dict[str, Any]) -> Any:
        """Deserializes a single value from the response data based on its definition."""
        raw_value = response_data.get(return_key)
        if raw_value is None:
            print(f"Warning: Expected return key '{return_key}' not found in response for service '{self.name}'. Returning None.")
            return None

        return_type_str = return_def.type
        edsl_registry = RegisterSubclassesMeta.get_registry()

        # Check registered EDSL types
        if return_type_str in edsl_registry:
            target_cls = edsl_registry[return_type_str]
            try:
                return target_cls.from_dict(raw_value)
            except Exception as e:
                print(f"Warning: Failed to deserialize response key '{return_key}' into {target_cls.__name__} for service '{self.name}'. Returning raw data. Error: {e}")
                print(f"Raw value for '{return_key}': {raw_value}")
                return raw_value
        # Check standard Python types
        elif return_type_str == 'str':
            try:
                return str(raw_value)
            except ValueError:
                print(f"Warning: Could not convert value for key '{return_key}' to str. Returning raw value.")
                return raw_value
        elif return_type_str == 'int':
            try:
                return int(raw_value)
            except ValueError:
                print(f"Warning: Could not convert value for key '{return_key}' to int. Returning raw value.")
                return raw_value
        elif return_type_str == 'float':
            try:
                return float(raw_value)
            except ValueError:
                print(f"Warning: Could not convert value for key '{return_key}' to float. Returning raw value.")
                return raw_value
        elif return_type_str == 'bool':
            # Handle potential string representations of bool
            if isinstance(raw_value, str):
                if raw_value.lower() == 'true':
                    return True
                elif raw_value.lower() == 'false':
                    return False
            try:
                return bool(raw_value)
            except ValueError:
                print(f"Warning: Could not convert value for key '{return_key}' to bool. Returning raw value.")
                return raw_value
        elif return_type_str == 'list':
             try:
                return list(raw_value)
             except TypeError:
                print(f"Warning: Could not convert value for key '{return_key}' to list. Returning raw value.")
                return raw_value
        elif return_type_str == 'dict':
             try:
                return dict(raw_value)
             except (TypeError, ValueError):
                print(f"Warning: Could not convert value for key '{return_key}' to dict. Returning raw value.")
                return raw_value
        else:
            # Type not recognized
            print(f"Warning: Unrecognized return type '{return_type_str}' for key '{return_key}' in service '{self.name}'. Returning raw value.")
            return raw_value

    def _deserialize_response(self, response: requests.Response) -> Any:
        """Deserializes the API response based on the service definition."""
        try:
            response_data = response.json()
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from service '{self.name}': {e}")
            raise e # Re-raise

        # If no specific returns defined, return the raw data
        if not self.service_returns:
             return response_data

        deserialized_results = {}
        for return_key, return_def in self.service_returns.items():
            deserialized_value = self._deserialize_single_value(return_key, return_def, response_data)
            # We store the result even if it's None (due to missing key or deserialization failure)
            # to indicate that we attempted to process this key.
            deserialized_results[return_key] = deserialized_value

        # Always return a dictionary, even if only one item was expected/processed.
        # This provides a consistent return structure.
        return deserialized_results

    def __call__(self, **kwargs: Any) -> Any:
        """
        Executes the API call **via the gateway** for this service using provided parameters.
        Validates parameters, prepares payload, executes the call, and deserializes the response.

        Args:
            **kwargs: Parameters for the service call.

        Returns:
            The API response, potentially deserialized based on service definition.

        Raises:
            ValueError: If validation fails (missing/incorrect params) or if internal configuration (_base_url) is not set for gateway call.
            requests.exceptions.RequestException: If the API call fails.
            json.JSONDecodeError: If the response is not valid JSON.
        """
        self.validate_call_parameters(kwargs)
        prepared_params = self._prepare_parameters(**kwargs)

        # Construct the payload specific to the gateway's /service/ endpoint
        payload = {
            "service": self.name,
            "params": prepared_params
        }
        if self._ep_api_token:
            payload["ep_api_token"] = self._ep_api_token

        response = self._make_api_call(payload)
        return self._deserialize_response(response)

    def call_directly(self, **kwargs: Any) -> Any:
        """
        Executes the API call **directly** to the service's endpoint using provided parameters.
        Validates parameters, prepares payload, constructs headers, executes the call, and deserializes the response.

        Args:
            **kwargs: Parameters for the service call.

        Returns:
            The API response, potentially deserialized based on service definition.

        Raises:
            ValueError: If validation fails (missing/incorrect params) or if the endpoint is not defined.
            requests.exceptions.RequestException: If the API call fails.
            json.JSONDecodeError: If the response is not valid JSON.
        """
        if not self.endpoint:
            raise ValueError(f"Service '{self.name}' cannot be called directly. 'endpoint' is not defined.")

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
            return self._deserialize_response(response)
        except requests.exceptions.RequestException as e:
            error_message = f"Error calling service '{self.name}' directly at {url}: {e}"
            if response is not None:
                error_message += f"\nResponse status: {response.status_code}"
                try:
                    error_message += f"\nResponse content: {response.text}"
                except Exception:
                    error_message += "\nResponse content could not be read."
            print(error_message)
            raise e # Re-raise the exception
        except json.JSONDecodeError as e:
            # Handle JSON decoding errors specifically from _deserialize_response
            print(f"Error decoding JSON response from direct call to service '{self.name}' at {url}: {e}")
            raise e # Re-raise


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    # print(create_survey_service)
    # Run doctests
    #results = doctest.testmod()
    #print(f"Doctest results: {results}")
    # Optional: exit with non-zero status if tests fail
    #if results.failed > 0:
    #    exit(1)