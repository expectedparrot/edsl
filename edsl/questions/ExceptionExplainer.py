from pydantic import ValidationError
from typing import Union


class ExceptionExplainer:
    """
    A class that converts validation errors into human-readable explanations,
    specifically for Language Model responses.
    """

    def __init__(self, error: Union[ValidationError, Exception], model_response: str):
        """
        Initialize the explainer with the error and model response.

        Args:
            error: The validation error that occurred
            model_response: The raw response from the Language Model
        """
        self.error = error
        self.model_response = model_response

    def explain(self) -> str:
        """
        Generate a human-readable explanation of why the model's response failed validation.

        Returns:
            A user-friendly explanation of why the model's response was invalid
        """
        self.error = self.error.pydantic_error
        return self._explain_validation_error()

        # Fallback for unknown errors
        return self._create_generic_explanation()

    def _explain_validation_error(self) -> str:
        """Handle Pydantic ValidationError specifically."""
        error_dict = self.error.errors()
        explanations = []

        context = f'The AI model returned "{self.model_response}", but this was invalid for the question you asked and the constraints you provided.\n'
        explanations.append(context)
        explanations.append("Reason(s) invalidated:")
        for e in error_dict:
            msg = e.get("msg", "Unknown error")
            explanations.append(f"- {msg}")

        main_message = "\n".join(explanations)
        return f"{main_message}\n\n{self._get_suggestion()}"

    def _create_generic_explanation(self) -> str:
        """Create a generic explanation for non-ValidationError exceptions."""
        return (
            f'The AI model returned "{self.model_response}", but this response was invalid. '
            f"Error: {str(self.error)}"
        )

    def _get_suggestion(self) -> str:
        """Get a suggestion for handling the error."""
        return (
            "EDSL Advice:\n"
            "- Look at the Model comments - often the model will provide a hint about what went wrong.\n"
            "- If the model's response doesn't make sense, try rephrasing your question.\n"
            "- Try using 'use_code' parameter of a MultipleChoice.\n"
            "- A QuestionFreeText will almost always validate.\n"
            "- Try setting the 'permissive' = True parameter in the Question constructor."
        )


# Example usage:
if __name__ == "__main__":
    try:
        # Your validation code here
        raise ValidationError.parse_obj({"answer": "120"})
    except ValidationError as e:
        explainer = ExceptionExplainer(e, "120")
        explanation = explainer.explain()
        print(explanation)
