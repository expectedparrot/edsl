"""QuestionPydantic - A question type that uses custom Pydantic models for structured responses.

This module implements QuestionPydantic, which allows users to specify arbitrary Pydantic
models as response schemas. When supported by the inference service, the schema is passed
to the LLM to enable structured output generation. Otherwise, the response is validated
against the schema post-hoc.

Key features:
- User-defined Pydantic models as response schemas
- Automatic JSON schema generation and passing to inference services
- Graceful fallback when structured output is not supported
- Full validation of responses against the provided schema
"""

from __future__ import annotations
from typing import Optional, Any, Dict, Type, List
from uuid import uuid4
import json

from pydantic import BaseModel, field_validator

from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception


class PydanticResponse(BaseModel):
    """
    Pydantic model for validating responses to QuestionPydantic.

    This model wraps arbitrary user-defined Pydantic model responses. The answer
    field contains a dictionary representation of the user's Pydantic model instance.

    Attributes:
        answer: Dictionary representation of the user's Pydantic model data.
        generated_tokens: Optional raw LLM output for token tracking.

    Examples:
        >>> # With a simple user model
        >>> from pydantic import BaseModel as UserModel
        >>> class Person(UserModel):
        ...     name: str
        ...     age: int
        >>> response = PydanticResponse(answer={"name": "Alice", "age": 30})
        >>> response.answer["name"]
        'Alice'
    """

    answer: Dict[str, Any]
    generated_tokens: Optional[str] = None

    @field_validator("answer")
    @classmethod
    def validate_answer_is_dict(cls, v):
        """
        Validate that the answer is a dictionary.

        Args:
            v: The value to validate.

        Returns:
            The validated dictionary.

        Raises:
            ValueError: If the answer is not a dictionary.
        """
        if not isinstance(v, dict):
            raise ValueError("Answer must be a dictionary")
        return v


class PydanticResponseValidator(ResponseValidatorABC):
    """
    Validator for QuestionPydantic responses.

    This class implements validation logic for responses to QuestionPydantic questions.
    It ensures that responses contain valid data conforming to the user's Pydantic model.

    Attributes:
        required_params: List of required parameters for validation.
        valid_examples: Examples of valid responses for testing.
        invalid_examples: Examples of invalid responses for testing.
    """

    required_params = ["user_pydantic_model"]
    valid_examples = []  # Will be populated dynamically
    invalid_examples = []

    def fix(self, response: dict, verbose: bool = False) -> dict:
        """
        Fix common issues in Pydantic responses.

        This method attempts to fix invalid responses by parsing JSON strings
        and ensuring the answer field contains a valid dictionary.

        Args:
            response: The response dictionary to fix.
            verbose: If True, print information about the fixing process.

        Returns:
            A fixed version of the response dictionary.
        """
        answer = response.get("answer")
        generated_tokens = response.get("generated_tokens")

        # Try to parse answer as JSON if it's a string
        if isinstance(answer, str):
            try:
                answer = json.loads(answer)
                if verbose:
                    print(f"Parsed answer from JSON string: {answer}")
            except json.JSONDecodeError:
                if verbose:
                    print(f"Could not parse answer as JSON: {answer}")

        # Try to parse generated_tokens as JSON if answer parsing failed
        if not isinstance(answer, dict) and isinstance(generated_tokens, str):
            try:
                answer = json.loads(generated_tokens)
                if verbose:
                    print(f"Parsed answer from generated_tokens JSON: {answer}")
            except json.JSONDecodeError:
                if verbose:
                    print(
                        f"Could not parse generated_tokens as JSON: {generated_tokens}"
                    )

        # If still not a dict, create empty dict
        if not isinstance(answer, dict):
            answer = {}
            if verbose:
                print("Created empty dict as fallback answer")

        return {"answer": answer, "generated_tokens": generated_tokens}

    def validate_pydantic_model(
        self, answer_dict: dict, user_pydantic_model: Type[BaseModel]
    ) -> bool:
        """
        Validate that the answer dictionary conforms to the user's Pydantic model.

        Args:
            answer_dict: Dictionary representation of the answer.
            user_pydantic_model: The user's Pydantic model class.

        Returns:
            bool: True if the data validates against the model, False otherwise.
        """
        try:
            user_pydantic_model.model_validate(answer_dict)
            return True
        except Exception:
            return False


class QuestionPydantic(QuestionBase):
    """
    A question that expects a response conforming to a user-defined Pydantic model.

    This question type allows users to specify arbitrary Pydantic models as response
    schemas. When the inference service supports structured output (e.g., OpenAI's
    JSON schema mode), the schema is passed to the LLM to constrain generation.
    Otherwise, responses are validated post-hoc against the provided model.

    Attributes:
        question_type (str): Identifier for this question type, set to "pydantic".
        _response_model: Pydantic model for validating the response wrapper.
        response_validator_class: Class used to validate and fix responses.
        user_pydantic_model: The user's custom Pydantic model for the answer structure.

    Examples:
        >>> from pydantic import BaseModel, Field
        >>> class Person(BaseModel):
        ...     name: str = Field(description="Full name")
        ...     age: int = Field(description="Age in years")
        ...     city: str = Field(description="City of residence")

        >>> q = QuestionPydantic(
        ...     question_name="extract_person",
        ...     question_text="Extract person info: John Smith, 35, lives in Boston",
        ...     pydantic_model=Person
        ... )
        >>> q.question_type
        'pydantic'
        >>> hasattr(q, 'user_pydantic_model')
        True
    """

    question_type = "pydantic"
    _response_model = PydanticResponse
    response_validator_class = PydanticResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        pydantic_model: Optional[Type[BaseModel]] = None,
        pydantic_model_schema: Optional[Dict[str, Any]] = None,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """
        Initialize a new Pydantic question.

        Args:
            question_name: Identifier for the question, used in results and templates.
                          Must be a valid Python variable name.
            question_text: The actual text of the question to be asked.
            pydantic_model: User's custom Pydantic model defining the expected response structure.
            pydantic_model_schema: JSON schema of a Pydantic model (for deserialization).
            answering_instructions: Optional additional instructions for answering
                                    the question, overrides default instructions.
            question_presentation: Optional custom presentation template for the
                                  question, overrides default presentation.

        Raises:
            QuestionInitializationError: If initialization parameters are invalid or misspelled.

        Examples:
            >>> from pydantic import BaseModel
            >>> class Product(BaseModel):
            ...     name: str
            ...     price: float
            ...     in_stock: bool

            >>> q = QuestionPydantic(
            ...     question_name="extract_product",
            ...     question_text="Extract product details from: Widget Pro costs $19.99 and is in stock",
            ...     pydantic_model=Product
            ... )
            >>> q.user_pydantic_model == Product
            True
        """
        from .exceptions import QuestionInitializationError

        self.question_name = question_name
        self.question_text = question_text
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

        # Handle both direct model and schema-based initialization
        if pydantic_model is not None:
            self._user_pydantic_model = pydantic_model
            # Validate that pydantic_model is actually a Pydantic model
            if not (
                isinstance(pydantic_model, type)
                and issubclass(pydantic_model, BaseModel)
            ):
                raise QuestionInitializationError(
                    f"The 'pydantic_model' parameter must be a Pydantic BaseModel subclass, "
                    f"but got {type(pydantic_model).__name__}",
                    question_type="QuestionPydantic",
                    invalid_parameter="pydantic_model",
                    suggested_fix="Ensure you're passing a class that inherits from pydantic.BaseModel",
                )
        elif pydantic_model_schema is not None:
            # Reconstruct model from schema (deserialization path)
            self._user_pydantic_model = self._create_model_from_schema(
                pydantic_model_schema
            )
        else:
            raise QuestionInitializationError(
                "QuestionPydantic requires either 'pydantic_model' or 'pydantic_model_schema' parameter",
                question_type="QuestionPydantic",
                suggested_fix="Provide either a pydantic_model (Pydantic class) or pydantic_model_schema (dict)",
            )

    @staticmethod
    def _create_model_from_schema(schema: Dict[str, Any]) -> Type[BaseModel]:
        """
        Create a dynamic Pydantic model from a JSON schema.

        Args:
            schema: JSON schema dictionary.

        Returns:
            A dynamically created Pydantic model class.
        """
        from pydantic import create_model, Field

        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        # Map JSON types to Python types for *scalar* values
        scalar_type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "object": dict,
        }

        field_definitions = {}
        for field_name, field_info in properties.items():
            field_type = field_info.get("type", "string")
            is_required = field_name in required_fields

            # --------- NEW LOGIC FOR ARRAYS ----------
            if field_type == "array":
                items_schema = field_info.get("items", {}) or {}
                item_type_name = items_schema.get("type", "string")

                # Default to Any if we don't recognize it
                item_python_type = scalar_type_map.get(item_type_name, Any)

                # This is the key: use List[item_type], not bare list
                python_type = List[item_python_type]
            else:
                # Scalar or object types
                python_type = scalar_type_map.get(field_type, str)
            # --------- END NEW LOGIC ----------

            # Extract Field metadata from JSON schema
            field_kwargs = {}

            # Description
            if "description" in field_info:
                field_kwargs["description"] = field_info["description"]

            # Constraints for numeric types
            if field_type in ("integer", "number"):
                if "minimum" in field_info:
                    field_kwargs["ge"] = field_info["minimum"]
                if "maximum" in field_info:
                    field_kwargs["le"] = field_info["maximum"]
                if "exclusiveMinimum" in field_info:
                    field_kwargs["gt"] = field_info["exclusiveMinimum"]
                if "exclusiveMaximum" in field_info:
                    field_kwargs["lt"] = field_info["exclusiveMaximum"]

            # Constraints for strings
            if field_type == "string":
                if "minLength" in field_info:
                    field_kwargs["min_length"] = field_info["minLength"]
                if "maxLength" in field_info:
                    field_kwargs["max_length"] = field_info["maxLength"]
                if "pattern" in field_info:
                    field_kwargs["pattern"] = field_info["pattern"]

            # Constraints for arrays
            if field_type == "array":
                if "minItems" in field_info:
                    field_kwargs["min_length"] = field_info["minItems"]
                if "maxItems" in field_info:
                    field_kwargs["max_length"] = field_info["maxItems"]

            # Create the field with metadata
            if is_required:
                if field_kwargs:
                    field_definitions[field_name] = (
                        python_type,
                        Field(..., **field_kwargs),
                    )
                else:
                    field_definitions[field_name] = (python_type, ...)
            else:
                if field_kwargs:
                    field_definitions[field_name] = (
                        python_type,
                        Field(None, **field_kwargs),
                    )
                else:
                    field_definitions[field_name] = (python_type, None)

        model_name = schema.get("title", "DynamicModel")
        return create_model(model_name, **field_definitions)

    # @staticmethod
    # def _create_model_from_schema(schema: Dict[str, Any]) -> Type[BaseModel]:
    #     """
    #     Create a dynamic Pydantic model from a JSON schema.

    #     Args:
    #         schema: JSON schema dictionary.

    #     Returns:
    #         A dynamically created Pydantic model class.
    #     """
    #     from pydantic import create_model, Field

    #     properties = schema.get("properties", {})
    #     required_fields = schema.get("required", [])

    #     # Build field definitions for create_model
    #     field_definitions = {}
    #     for field_name, field_info in properties.items():
    #         field_type = field_info.get("type", "string")
    #         is_required = field_name in required_fields

    #         # Map JSON schema types to Python types
    #         type_map = {
    #             "string": str,
    #             "integer": int,
    #             "number": float,
    #             "boolean": bool,
    #             "array": list,
    #             "object": dict,
    #         }

    #         python_type = type_map.get(field_type, str)

    #         # Extract Field metadata from JSON schema
    #         field_kwargs = {}

    #         # Description
    #         if "description" in field_info:
    #             field_kwargs["description"] = field_info["description"]

    #         # Constraints for numeric types
    #         if field_type in ("integer", "number"):
    #             if "minimum" in field_info:
    #                 field_kwargs["ge"] = field_info["minimum"]
    #             if "maximum" in field_info:
    #                 field_kwargs["le"] = field_info["maximum"]
    #             if "exclusiveMinimum" in field_info:
    #                 field_kwargs["gt"] = field_info["exclusiveMinimum"]
    #             if "exclusiveMaximum" in field_info:
    #                 field_kwargs["lt"] = field_info["exclusiveMaximum"]

    #         # Constraints for strings
    #         if field_type == "string":
    #             if "minLength" in field_info:
    #                 field_kwargs["min_length"] = field_info["minLength"]
    #             if "maxLength" in field_info:
    #                 field_kwargs["max_length"] = field_info["maxLength"]
    #             if "pattern" in field_info:
    #                 field_kwargs["pattern"] = field_info["pattern"]

    #         # Constraints for arrays
    #         if field_type == "array":
    #             if "minItems" in field_info:
    #                 field_kwargs["min_length"] = field_info["minItems"]
    #             if "maxItems" in field_info:
    #                 field_kwargs["max_length"] = field_info["maxItems"]

    #         # Create the field with metadata
    #         if is_required:
    #             if field_kwargs:
    #                 field_definitions[field_name] = (
    #                     python_type,
    #                     Field(..., **field_kwargs),
    #                 )
    #             else:
    #                 field_definitions[field_name] = (python_type, ...)
    #         else:
    #             if field_kwargs:
    #                 field_definitions[field_name] = (
    #                     python_type,
    #                     Field(None, **field_kwargs),
    #                 )
    #             else:
    #                 field_definitions[field_name] = (python_type, None)

    #     # Create a dynamic model
    #     model_name = schema.get("title", "DynamicModel")
    #     return create_model(model_name, **field_definitions)

    @property
    def user_pydantic_model(self) -> Type[BaseModel]:
        """Get the user's Pydantic model."""
        return self._user_pydantic_model

    @property
    def data(self) -> Dict[str, Any]:
        """
        Return a dictionary of question attributes except for question_type.

        This overrides the base data property to exclude the Pydantic model class,
        which is not JSON serializable, and to include template-friendly data.
        """
        d = super().data
        # Remove the Pydantic model if it was included
        d.pop("user_pydantic_model", None)
        # Add template data for rendering prompts
        schema = self.get_response_schema()
        d["json_schema"] = json.dumps(schema, indent=2)
        d["pydantic_schema"] = schema
        d["pydantic_model_name"] = self.user_pydantic_model.__name__
        return d

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """
        Serialize the question to a dictionary.

        This overrides the base to_dict to handle the Pydantic model serialization.
        We store the model's JSON schema instead of the class itself.

        Args:
            add_edsl_version: Whether to include EDSL version information.

        Returns:
            dict: Dictionary representation of the question.
        """
        d = super().to_dict(add_edsl_version=add_edsl_version)
        # Store the schema instead of the class
        d["pydantic_model_schema"] = self.get_response_schema()
        # Remove fields that shouldn't be serialized
        d.pop("user_pydantic_model", None)  # Remove the class if it got added
        d.pop("json_schema", None)  # Remove template-only field
        d.pop("pydantic_schema", None)  # Remove template-only field
        d.pop("pydantic_model_name", None)  # Remove template-only field
        return d

    def get_response_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for the user's Pydantic model.

        This method generates a JSON schema from the user's Pydantic model that
        can be passed to inference services supporting structured output.

        The schema is modified to be compatible with OpenAI's strict mode by
        adding `additionalProperties: false` and ensuring all required fields
        are properly marked.

        Returns:
            dict: JSON schema representation of the user's Pydantic model.

        Examples:
            >>> from pydantic import BaseModel
            >>> class Simple(BaseModel):
            ...     value: str
            >>> q = QuestionPydantic(
            ...     question_name="test",
            ...     question_text="Test",
            ...     pydantic_model=Simple
            ... )
            >>> schema = q.get_response_schema()
            >>> 'properties' in schema
            True
            >>> 'value' in schema['properties']
            True
        """
        schema = self._user_pydantic_model.model_json_schema()

        # Add additionalProperties: false for OpenAI strict mode compatibility
        schema["additionalProperties"] = False

        return schema

    def _validate_answer(self, answer: dict, replacement_dict: dict = None) -> dict:
        """
        Validate a raw answer against this question's constraints.

        This method extends the base validation to include validation against
        the user's Pydantic model, ensuring the answer dictionary conforms to
        the expected structure.

        Args:
            answer: Dictionary containing the raw answer to validate.
            replacement_dict: Optional dictionary of replacements to apply during
                             validation for template variables.

        Returns:
            dict: A dictionary containing the validated answer.

        Raises:
            QuestionAnswerValidationError: If the answer fails validation.
        """
        # First, validate using the wrapper response model
        validated_answer = super()._validate_answer(answer, replacement_dict)
        answer_dict = validated_answer["answer"]

        # Then validate against the user's Pydantic model
        validator = self.response_validator
        if not validator.validate_pydantic_model(answer_dict, self.user_pydantic_model):
            from .exceptions import QuestionAnswerValidationError

            try:
                # Try to get detailed validation errors
                self.user_pydantic_model.model_validate(answer_dict)
            except Exception as e:
                raise QuestionAnswerValidationError(
                    message=f"Answer does not conform to Pydantic model {self.user_pydantic_model.__name__}: {str(e)}",
                    data=answer_dict,
                    model=self.user_pydantic_model,
                    pydantic_error=e if hasattr(e, "errors") else None,
                )

        return validated_answer

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.

        Returns:
            str: HTML markup for rendering the question.
        """
        from jinja2 import Template

        # Get field descriptions from the Pydantic model
        schema = self.get_response_schema()
        properties = schema.get("properties", {})

        fields_html = []
        for field_name, field_info in properties.items():
            field_type = field_info.get("type", "string")
            field_desc = field_info.get("description", "")
            fields_html.append(
                f"<label>{field_name} ({field_type}): {field_desc}</label>"
            )

        question_html_content = Template(
            """
        <div>
        <p>Expected response structure ({{ model_name }}):</p>
        {% for field in fields %}
            {{ field }}<br>
        {% endfor %}
        <label for="{{ question_name }}">Response JSON:</label>
        <textarea id="{{ question_name }}" name="{{ question_name }}"
                  placeholder="Enter JSON conforming to {{ model_name }}"></textarea>
        </div>
        """
        ).render(
            question_name=self.question_name,
            model_name=self.user_pydantic_model.__name__,
            fields=fields_html,
        )
        return question_html_content

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionPydantic":
        """
        Create an example instance of a Pydantic question.

        Args:
            randomize: If True, appends a random UUID to the question text.

        Returns:
            QuestionPydantic: An example Pydantic question.

        Examples:
            >>> q = QuestionPydantic.example()
            >>> q.question_name
            'extract_person'
            >>> q.user_pydantic_model.__name__
            'Person'
        """
        from pydantic import BaseModel, Field

        class Person(BaseModel):
            """Example Pydantic model for a person."""

            name: str = Field(description="Full name of the person")
            age: int = Field(description="Age in years", ge=0, le=150)
            occupation: str = Field(description="Job title or profession")

        addition = "" if not randomize else str(uuid4())
        return cls(
            question_name="extract_person",
            question_text=f"Extract information about the person: Alice Johnson is a 28-year-old software engineer.{addition}",
            pydantic_model=Person,
        )

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """
        Generate a simulated valid answer for this question.

        Args:
            human_readable: Not used for Pydantic questions.

        Returns:
            dict: A dictionary containing a simulated valid answer.
        """
        # Use Pydantic's model_validate to create a valid example
        try:
            schema = self.get_response_schema()
            properties = schema.get("properties", {})
            required = set(schema.get("required", []))

            # Build a minimal valid instance with realistic defaults
            example_data = {}
            for field_name, field_info in properties.items():
                field_type = field_info.get("type", "string")

                # Get constraints if they exist
                minimum = field_info.get(
                    "minimum", field_info.get("exclusiveMinimum", 0)
                )

                if field_type == "string":
                    example_data[field_name] = "example"
                elif field_type == "integer":
                    # Use a value that respects constraints
                    if "minimum" in field_info or "exclusiveMinimum" in field_info:
                        example_data[field_name] = int(minimum) + 1
                    else:
                        example_data[field_name] = 1
                elif field_type == "number":
                    # Use a value that respects constraints
                    if "minimum" in field_info or "exclusiveMinimum" in field_info:
                        example_data[field_name] = float(minimum) + 0.1
                    elif "exclusiveMinimum" in field_info:
                        example_data[field_name] = (
                            float(field_info["exclusiveMinimum"]) + 0.1
                        )
                    else:
                        example_data[field_name] = 1.0
                elif field_type == "boolean":
                    example_data[field_name] = True
                elif field_type == "array":
                    example_data[field_name] = []
                elif field_type == "object":
                    example_data[field_name] = {}
                else:
                    # For complex types or missing field info, only add if required
                    if field_name in required:
                        example_data[field_name] = "example"

            # Validate it works
            validated = self.user_pydantic_model.model_validate(example_data)
            result = validated.model_dump()

        except Exception:
            # Fallback: try to create from model fields directly
            try:
                # Get model fields and use their defaults or construct minimally
                model_fields = self.user_pydantic_model.model_fields
                example_data = {}
                for field_name, field in model_fields.items():
                    if field.is_required():
                        # Provide a minimal value based on annotation
                        annotation = field.annotation
                        if annotation == str:
                            example_data[field_name] = "example"
                        elif annotation == int:
                            example_data[field_name] = 1
                        elif annotation == float:
                            example_data[field_name] = 1.0
                        elif annotation == bool:
                            example_data[field_name] = True
                        else:
                            example_data[field_name] = "example"
                validated = self.user_pydantic_model.model_validate(example_data)
                result = validated.model_dump()
            except Exception:
                # Last resort fallback
                result = {}

        return {"answer": result, "generated_tokens": json.dumps(result)}

    @classmethod
    def example_model(cls):
        """
        Create an example model with proper canned response for Pydantic questions.

        The canned response needs to be keyed by question_name for the test service.
        """
        from ..language_models import Model

        q = cls.example()
        simulated_answer = q._simulate_answer()

        # Create canned response keyed by question name
        canned_response = {q.question_name: simulated_answer["answer"]}

        return Model("test", canned_response=canned_response)


def main():
    """
    Demonstrate the functionality of the QuestionPydantic class.
    """
    from pydantic import BaseModel, Field

    class Book(BaseModel):
        """Example Pydantic model for a book."""

        title: str = Field(description="Title of the book")
        author: str = Field(description="Author's name")
        year: int = Field(description="Publication year", ge=1000, le=2100)
        isbn: str = Field(description="ISBN number")

    # Create an example question
    q = QuestionPydantic(
        question_name="extract_book",
        question_text="Extract book information: '1984' by George Orwell, published in 1949, ISBN: 978-0451524935",
        pydantic_model=Book,
    )

    print(f"Question text: {q.question_text}")
    print(f"Question name: {q.question_name}")
    print(f"Pydantic model: {q.user_pydantic_model.__name__}")
    print("\nJSON Schema:")
    print(json.dumps(q.get_response_schema(), indent=2))

    # Simulate an answer
    simulated = q._simulate_answer()
    print(f"\nSimulated answer: {simulated}")

    # Validate the simulated answer
    validated = q._validate_answer(simulated)
    print(f"Validated answer: {validated}")

    print("\nQuestionPydantic demonstration completed")


if __name__ == "__main__":
    main()
