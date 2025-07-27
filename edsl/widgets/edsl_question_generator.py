import anywidget
import traitlets
import requests
from typing import Dict, Any, Optional

import requests

url = "http://localhost:8000/widgets/edsl-question-generator/file"

response = requests.get(url)

response_text = response.text


class EDSLQuestionWidget(anywidget.AnyWidget):
    """A widget for generating and validating EDSL questions with real-time feedback."""

    # Point to the compiled JavaScript
    _esm = response_text

    # Traitlets for bidirectional communication
    validation_request = traitlets.Dict({"is_default": True}).tag(
        sync=True
    )  # {id, params} for each validation request
    validation_result = traitlets.Dict({"is_default": True}).tag(
        sync=True
    )  # {id, success, error/message} for results

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Use traitlets observation for validation requests
        self.observe(self._on_validation_request, names=["validation_request"])

    def _on_validation_request(self, change):
        """Called when validation_request traitlet changes - handles form submissions."""
        request = change.get("new", {})

        if not request:
            return

        request_id = request.get("id")
        params = request.get("params", {})

        if not params or "question_type" not in params:
            return

        # Validate the params and store result with request ID
        result = self._validate_question_params(params, request_id)
        self.validation_result = result

    def _validate_question_params(
        self, params: Dict[str, Any], request_id: str = None
    ) -> dict:
        """
        Try to instantiate an EDSL Question with the provided parameters.
        Updates the validation_result traitlet with success/error information.
        """
        try:
            # Try to import edsl and create the question
            from edsl import Question

            # Create a clean copy of params for Question instantiation
            question_params = params.copy()

            # Validate required fields
            if not question_params.get("question_name", "").strip():
                raise ValueError("Question name cannot be empty")

            if not question_params.get("question_text", "").strip():
                raise ValueError("Question text cannot be empty")

            # Additional validation for multiple choice
            if question_params.get("question_type") == "multiple_choice":
                options = question_params.get("question_options", [])
                if not options:
                    raise ValueError(
                        "Multiple choice questions must have at least one option"
                    )
                if any(not str(opt).strip() for opt in options):
                    raise ValueError("Multiple choice options cannot be empty")

            # Try to create the question
            question = Question(**question_params)

            # If successful, set validation result via traitlet
            result = {
                "is_default": False,
                "id": request_id,
                "success": True,
                "message": "Question created successfully!",
                "question_repr": str(question),
                "timestamp": self._get_timestamp(),
            }
            return result

        except ImportError as e:
            # EDSL not available
            result = {
                "is_default": False,
                "id": request_id,
                "success": False,
                "error": f"EDSL not installed. Please install with: pip install edsl\nDetails: {str(e)}",
                "timestamp": self._get_timestamp(),
            }
            return result

        except Exception as e:
            # Question creation failed
            error_msg = str(e)
            if "unexpected keyword argument" in error_msg:
                error_msg = f"Invalid parameter for question type '{params.get('question_type', 'unknown')}': {error_msg}"
            elif "required positional argument" in error_msg:
                error_msg = f"Missing required parameter: {error_msg}"

            result = {
                "is_default": False,
                "id": request_id,
                "success": False,
                "error": f"Question validation failed: {error_msg}",
                "timestamp": self._get_timestamp(),
            }
            return result

    def _get_timestamp(self) -> str:
        """Get current timestamp for validation tracking."""
        import datetime

        return datetime.datetime.now().isoformat()

    def create_question_code(self, include_comment: bool = True) -> str:
        """Generate the Python code string for the current question parameters."""
        params = self.params
        if not params:
            return ""

        question_type = params.get("question_type", "free_text")
        question_name = params.get("question_name", "")
        question_text = params.get("question_text", "")
        question_options = params.get("question_options", [])

        code = "from edsl import Question\n\n"

        if include_comment:
            type_display = question_type.replace("_", " ").title()
            if question_type == "multiple_choice":
                type_display = "Multiple Choice"
            code += f"# Create a {type_display} question\n"

        code += f"Question(\n"
        code += f'    question_type="{question_type}",\n'
        code += f'    question_name="{question_name}",\n'
        code += f'    question_text="{question_text}"'

        if question_type == "multiple_choice" and question_options:
            options_str = ", ".join(f'"{opt}"' for opt in question_options)
            code += f",\n    question_options=[{options_str}]"

        code += "\n)"

        return code

    def get_current_question(self) -> Optional[object]:
        """
        Get the current Question object if validation was successful.
        Returns None if validation failed or no question has been created.
        """
        if not self.validation_result.get("success", False):
            return None

        try:
            from edsl import Question

            return Question(**self.params)
        except:
            return None


# Convenience function for easy import
def create_edsl_widget():
    """Create and return a new EDSL Question Widget instance."""
    return EDSLQuestionWidget()


# For backward compatibility
EDSLWidget = EDSLQuestionWidget

# Export the main class
__all__ = ["EDSLQuestionWidget", "create_edsl_widget", "EDSLWidget"]
