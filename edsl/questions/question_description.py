"""
Introspects the EDSL question system to generate comprehensive guides for LLM agents.
"""

from __future__ import annotations
import inspect
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass


QUESTION_PURPOSES = {
    "multiple_choice": "When options are known and limited; respondent selects exactly one option",
    "multiple_choice_with_other": "When options are known but you want to allow for custom 'Other' responses",
    "free_text": "When the answer should be open-ended text with no predefined options",
    "checkbox": "When multiple options can be selected from a list",
    "numerical": "When the answer is a single numerical value (integer or float)",
    "linear_scale": "When options are integers on a scale (e.g., 1-5, 1-10) with optional endpoint labels",
    "yes_no": "When the question can be fully answered with either 'Yes' or 'No'",
    "list": "When the answer should be a list of items",
    "rank": "When the answer should be a ranked ordering of items",
    "budget": "When the answer should be an amount allocated among a set of options",
    "top_k": "When the answer should be a selection of the top k items from a list",
    "likert_five": "When measuring agreement on a 5-point scale (Strongly disagree to Strongly agree)",
    "extract": "When extracting or extrapolating structured information from text",
    "dict": "When the answer should be a dictionary with specific keys",
    "matrix": "When asking multiple related questions with the same response options",
    "dropdown": "When options are numerous and need to be presented in a searchable dropdown",
}

COMMON_CONVERSION_ERRORS = """
COMMON CONVERSION ERRORS TO DETECT AND FIX:

1. Rating Scales Misclassified:
   - ERROR: A 1-5 or 1-10 rating scale converted as QuestionMultipleChoice with options like ["1", "2", "3", "4", "5"]
   - FIX: Should be QuestionLinearScale with question_options=[1, 2, 3, 4, 5] and optional option_labels

2. Agree/Disagree Statements:
   - ERROR: Likert-style agree/disagree converted as QuestionMultipleChoice
   - FIX: Should be QuestionLikertFive (uses standard 5-point scale automatically)

3. Yes/No Questions:
   - ERROR: Binary yes/no converted as QuestionMultipleChoice with options=["Yes", "No"]
   - FIX: Should be QuestionYesNo (no options needed, they are automatic)

4. Open Text Fields:
   - ERROR: Free-form text fields converted as QuestionMultipleChoice with arbitrary options
   - FIX: Should be QuestionFreeText (no options parameter)

5. Multi-Select Questions:
   - ERROR: "Select all that apply" converted as QuestionMultipleChoice
   - FIX: Should be QuestionCheckBox (allows multiple selections)

6. Incomplete Option Lists:
   - ERROR: Options like [3, 5] when it should be [1, 2, 3, 4, 5] for a full scale
   - FIX: Reconstruct the complete scale based on context

7. HTML/Encoding Artifacts:
   - ERROR: Question text contains <p>, <b>, &nbsp;, &lt;, etc.
   - FIX: Clean HTML tags and decode entities while preserving original wording
"""


class EDSLQuestionDescription:
    """Introspects EDSL questions to generate LLM guidance for question fixing/transformation."""

    DEFAULT_TEMPLATE = """EDSL QUESTION SYSTEM GUIDE

This guide describes the available EDSL question types for properly classifying and fixing survey questions.

{question_types_section}

{conversion_errors_section}

VALIDATION RULES:
- question_name must be a valid Python identifier (letters, numbers, underscores; cannot start with number)
- question_text is the prompt shown to respondents
- question_options (where applicable) must be a non-empty list
- For QuestionLinearScale, question_options must be integers
- For QuestionNumerical, min_value must be <= max_value if both are specified
"""

    def __init__(self, template: Optional[str] = None):
        self.template = template if template is not None else self.DEFAULT_TEMPLATE

    @classmethod
    def get_all_question_types(cls) -> dict[str, dict[str, Any]]:
        """Return all registered EDSL question types with their metadata."""
        from .register_questions_meta import RegisterQuestionsMeta

        type_to_class = RegisterQuestionsMeta.question_types_to_classes()
        result = {}

        for question_type, question_class in type_to_class.items():
            if question_type in ("functional", "compute", "interview", "random"):
                continue

            try:
                sig = inspect.signature(question_class.__init__)
                params = sig.parameters

                required_params = []
                optional_params = {}
                all_params = []

                for name, param in params.items():
                    if name == "self":
                        continue
                    all_params.append(name)

                    if param.default is inspect.Parameter.empty:
                        required_params.append(name)
                    else:
                        optional_params[name] = param.default

                result[question_type] = {
                    "class": question_class,
                    "class_name": question_class.__name__,
                    "purpose": QUESTION_PURPOSES.get(
                        question_type,
                        getattr(question_class, "purpose", "General purpose question"),
                    ),
                    "parameters": all_params,
                    "required_params": required_params,
                    "optional_params": optional_params,
                }
            except Exception:
                continue

        return result

    @classmethod
    def get_type_details(cls, question_type: str) -> Optional[dict[str, Any]]:
        """Get detailed information for a specific question type."""
        all_types = cls.get_all_question_types()
        return all_types.get(question_type)

    @classmethod
    def format_question_types_section(cls) -> str:
        """Generate a formatted string describing all available question types."""
        all_types = cls.get_all_question_types()
        lines = ["AVAILABLE EDSL QUESTION TYPES:", ""]

        for qtype in sorted(all_types.keys()):
            info = all_types[qtype]
            lines.append(f"  {info['class_name']} (question_type='{qtype}')")
            lines.append(f"    Purpose: {info['purpose']}")

            if info["required_params"]:
                lines.append(f"    Required: {', '.join(info['required_params'])}")

            if info["optional_params"]:
                optional_strs = []
                for param, default in info["optional_params"].items():
                    if default is None:
                        optional_strs.append(f"{param}=None")
                    elif isinstance(default, str):
                        optional_strs.append(f"{param}='{default}'")
                    else:
                        optional_strs.append(f"{param}={default}")
                lines.append(f"    Optional: {', '.join(optional_strs)}")

            lines.append("")

        return "\n".join(lines)

    def prompt(self) -> str:
        """Generate the complete EDSL question guide using the template."""
        question_types_section = self.format_question_types_section()
        conversion_errors_section = COMMON_CONVERSION_ERRORS

        return self.template.format(
            question_types_section=question_types_section,
            conversion_errors_section=conversion_errors_section,
        )
