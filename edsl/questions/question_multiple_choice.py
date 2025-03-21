from __future__ import annotations
from typing import Union, Literal, Optional, List, Any

from jinja2 import Template
from pydantic import BaseModel, Field

from .question_base import QuestionBase
from .descriptors import QuestionOptionsDescriptor
from .decorators import inject_exception
from .response_validator_abc import ResponseValidatorABC

def create_response_model(choices: List[str], permissive: bool = False):
    """
    Create a ChoiceResponse model class with a predefined list of choices.

    :param choices: A list of allowed values for the answer field.
    :param permissive: If True, any value will be accepted as an answer.
    :return: A new Pydantic model class.
    """
    choice_tuple = tuple(choices)

    if not permissive:

        class ChoiceResponse(BaseModel):
            answer: Literal[choice_tuple] = Field(description="Selected choice")
            comment: Optional[str] = Field(None, description="Optional comment field")
            generated_tokens: Optional[Any] = Field(
                None, description="Generated tokens"
            )

            class Config:
                @staticmethod
                def json_schema_extra(schema: dict, model: BaseModel) -> None:
                    for prop in schema.get("properties", {}).values():
                        if prop.get("title") == "answer":
                            prop["enum"] = choices

    else:

        class ChoiceResponse(BaseModel):
            answer: Any = Field(description="Selected choice (can be any value)")
            comment: Optional[str] = Field(None, description="Optional comment field")
            generated_tokens: Optional[Any] = Field(
                None, description="Generated tokens"
            )

            class Config:
                @staticmethod
                def json_schema_extra(schema: dict, model: BaseModel) -> None:
                    for prop in schema.get("properties", {}).values():
                        if prop.get("title") == "answer":
                            prop["description"] += f". Suggested choices are: {choices}"
                    schema["title"] += " (Permissive)"

    return ChoiceResponse


class MultipleChoiceResponseValidator(ResponseValidatorABC):
    required_params = ["question_options", "use_code"]

    def fix(self, response, verbose=False):
        response_text = str(response.get("answer"))
        if response_text is None:
            response_text = response.get("generated_tokens", "")

        if verbose:
            print(f"Invalid generated tokens was: {response_text}")

        matches = []
        for idx, option in enumerate(self.question_options):
            if verbose:
                print("The options are: ", self.question_options)
            if str(option) in response_text:
                if verbose:
                    print("Match found with option ", option)
                if option not in matches:
                    matches.append(option)

        if verbose:
            print("The matches are: ", matches)
        if len(matches) == 1:
            proposed_data = {
                "answer": matches[0],
                "generated_tokens": response.get("generated_tokens", None),
            }
            try:
                self.response_model(**proposed_data)
                return proposed_data
            except Exception as e:
                if verbose:
                    print(f"Proposed solution {proposed_data} is invalid. Error: {e}")
            return response

    valid_examples = [
        ({"answer": 1}, {"question_options": ["Good", "Great", "OK", "Bad"]})
    ]

    invalid_examples = [
        (
            {"answer": -1},
            {"question_options": ["Good", "Great", "OK", "Bad"]},
            "Answer code must be a non-negative integer",
        ),
        (
            {"answer": None},
            {"question_options": ["Good", "Great", "OK", "Bad"]},
            "Answer code must not be missing.",
        ),
    ]


class QuestionMultipleChoice(QuestionBase):
    """
    A question that prompts the agent to select one option from a list of choices.
    
    QuestionMultipleChoice presents a set of predefined choices to the agent and asks
    them to select exactly one option. This question type is ideal for scenarios where
    the possible answers are known and limited, such as surveys, preference questions,
    or classification tasks.
    
    Key Features:
    - Presents a fixed set of options to choose from
    - Enforces selection of exactly one option
    - Can use numeric codes for options (use_code=True)
    - Supports custom instructions and presentation
    - Optional comment field for additional explanation
    - Can be configured to be permissive (accept answers outside the options)
    
    Technical Details:
    - Uses Pydantic models for validation with Literal types for strict checking
    - Supports dynamic options from scenario variables
    - HTML rendering for web interfaces
    - Robust validation with repair capabilities
    
    Examples:
        Basic usage:
        
        ```python
        q = QuestionMultipleChoice(
            question_name="preference",
            question_text="Which color do you prefer?",
            question_options=["Red", "Green", "Blue", "Yellow"]
        )
        ```
        
        With numeric codes:
        
        ```python
        q = QuestionMultipleChoice(
            question_name="rating",
            question_text="Rate this product from 1 to 5",
            question_options=["Very Poor", "Poor", "Average", "Good", "Excellent"],
            use_code=True  # The answer will be 0-4 instead of the text
        )
        ```
        
        Dynamic options from scenario:
        
        ```python
        q = QuestionMultipleChoice(
            question_name="choice",
            question_text="Select an option",
            question_options=["{{option1}}", "{{option2}}", "{{option3}}"]
        )
        scenario = Scenario({"option1": "Choice A", "option2": "Choice B", "option3": "Choice C"})
        result = q.by(model).with_scenario(scenario).run()
        ```
    
    See also:
        https://docs.expectedparrot.com/en/latest/questions.html#questionmultiplechoice-class
    """

    question_type = "multiple_choice"
    purpose = "When options are known and limited"
    question_options: Union[list[str], list[list], list[float], list[int]] = (
        QuestionOptionsDescriptor()
    )
    _response_model = None
    response_validator_class = MultipleChoiceResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: Union[list[str], list[list], list[float], list[int]],
        include_comment: bool = True,
        use_code: bool = False,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        permissive: bool = False,
    ):
        """
        Initialize a new multiple choice question.
        
        Parameters
        ----------
        question_name : str
            The name of the question, used as an identifier. Must be a valid Python variable name.
            This name will be used in results, templates, and when referencing the question in surveys.
            
        question_text : str
            The actual text of the question to be asked. This is the prompt that will be presented
            to the language model or agent.
            
        question_options : Union[list[str], list[list], list[float], list[int]]
            The list of options the agent can select from. These can be:
            - Strings: ["Option A", "Option B", "Option C"]
            - Lists: Used for nested or complex options
            - Numbers: [1, 2, 3, 4, 5] or [0.1, 0.2, 0.3]
            - Template strings: ["{{var1}}", "{{var2}}"] which will be rendered with scenario variables
            
        include_comment : bool, default=True
            Whether to include a comment field in the response, allowing the model to provide
            additional explanation beyond just selecting an option.
            
        use_code : bool, default=False
            If True, the answer will be the index of the selected option (0-based) instead of
            the option text itself. This is useful for numeric scoring or when option text is long.
            
        answering_instructions : Optional[str], default=None
            Custom instructions for how the model should answer the question. If None,
            default instructions for multiple choice questions will be used.
            
        question_presentation : Optional[str], default=None
            Custom template for how the question is presented to the model. If None,
            the default presentation for multiple choice questions will be used.
            
        permissive : bool, default=False
            If True, the validator will accept answers that are not in the provided options list.
            If False (default), only exact matches to the provided options are allowed.
            
        Examples
        --------
        >>> q = QuestionMultipleChoice(
        ...     question_name="color_preference",
        ...     question_text="What is your favorite color?",
        ...     question_options=["Red", "Blue", "Green", "Yellow"],
        ...     include_comment=True
        ... )
        
        >>> q_numeric = QuestionMultipleChoice(
        ...     question_name="rating",
        ...     question_text="How would you rate this product?",
        ...     question_options=["Very Poor", "Poor", "Average", "Good", "Excellent"],
        ...     use_code=True,
        ...     include_comment=True
        ... )
        
        Notes
        -----
        - When `use_code=True`, the answer will be the index (0-based) of the selected option
        - The `permissive` parameter is useful when you want to allow free-form responses
          while still suggesting options
        - Dynamic options can reference variables in a scenario using Jinja2 template syntax
        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options

        self._include_comment = include_comment
        self.use_code = use_code
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
        self.permissive = permissive

    ################
    # Answer methods
    ################

    def create_response_model(self, replacement_dict: dict = None):
        if replacement_dict is None:
            replacement_dict = {}
            # The replacement dict that could be from scenario, current answers, etc. to populate the response model

        if self.use_code:
            return create_response_model(
                list(range(len(self.question_options))), self.permissive
            )
        else:
            return create_response_model(self.question_options, self.permissive)

    @staticmethod
    def _translate_question_options(
        question_options, substitution_dict: dict
    ) -> list[str]:

        if isinstance(question_options, str):
            # If dynamic options are provided like {{ options }}, render them with the scenario
            # We can check if it's in the Scenario.
            from jinja2 import Environment, meta

            env = Environment()
            parsed_content = env.parse(question_options)
            template_variables = list(meta.find_undeclared_variables(parsed_content))
            # print("The template variables are: ", template_variables)
            question_option_key = template_variables[0]
            # We need to deal with possibility it's actually an answer to a question.
            potential_replacement = substitution_dict.get(question_option_key, None)

            if isinstance(potential_replacement, list):
                # translated_options = potential_replacement
                return potential_replacement

            if isinstance(potential_replacement, QuestionBase):
                if hasattr(potential_replacement, "answer") and isinstance(
                    potential_replacement.answer, list
                ):
                    return potential_replacement.answer
                    # translated_options = potential_replacement.answer

            # if not isinstance(potential_replacement, list):
            # translated_options = potential_replacement

            if potential_replacement is None:
                # Nope - maybe it's in the substition dict?
                from .exceptions import QuestionValueError
                raise QuestionValueError(
                    f"Could not find the key '{question_option_key}' in the scenario."
                    f"The substition dict was: '{substitution_dict}.'"
                    f"The question options were: '{question_options}'."
                )
        else:
            translated_options = [
                Template(str(option)).render(substitution_dict)
                for option in question_options
            ]
        return translated_options

    def _translate_answer_code_to_answer(
        self, answer_code: int, replacements_dict: Optional[dict] = None
    ):
        """Translate the answer code to the actual answer.

        It is used to translate the answer code to the actual answer.
        The question options might be templates, so they need to be rendered with the scenario.

        >>> q = QuestionMultipleChoice.example()
        >>> q._translate_answer_code_to_answer('Good', {})
        'Good'

        >>> q = QuestionMultipleChoice(question_name="how_feeling", question_text="How are you?", question_options=["{{emotion[0]}}", "emotion[1]"])
        >>> q._translate_answer_code_to_answer('Happy', {"emotion": ["Happy", "Sad"]})
        'Happy'

        """
        if replacements_dict is None:
            replacements_dict = {}
        translated_options = self._translate_question_options(
            self.question_options, replacements_dict
        )

        if self._use_code:
            try:
                return translated_options[int(answer_code)]
            except IndexError:
                from .exceptions import QuestionValueError
                raise QuestionValueError(
                    f"Answer code is out of range. The answer code index was: {int(answer_code)}. The options were: {translated_options}."
                )
            except TypeError:
                from .exceptions import QuestionValueError
                raise QuestionValueError(
                    f"The answer code was: '{answer_code}.'",
                    f"The options were: '{translated_options}'.",
                )
        else:
            # return translated_options[answer_code]
            return answer_code

    @property
    def question_html_content(self) -> str:
        """Return the HTML version of the question."""
        if hasattr(self, "option_labels"):
            option_labels = self.option_labels
        else:
            option_labels = {}
        question_html_content = Template(
            """
        {% for option in question_options %} 
        <div>
        <input type="radio" id="{{ option }}" name="{{ question_name }}" value="{{ option }}">
        <label for="{{ option }}">
        {{ option }}
        {% if option in option_labels %}
        : {{ option_labels[option] }}
        {% endif %}
        </label>
        </div>
        {% endfor %}
        """
        ).render(
            question_name=self.question_name,
            question_options=self.question_options,
            option_labels=option_labels,
        )
        return question_html_content

    ################
    # Example
    ################
    @classmethod
    @inject_exception
    def example(cls, include_comment=False, use_code=False) -> QuestionMultipleChoice:
        """Return an example instance."""
        return cls(
            question_text="How are you?",
            question_options=["Good", "Great", "OK", "Bad"],
            question_name="how_feeling",
            include_comment=include_comment,
            use_code=use_code,
        )


# def main():
#     """Create an example QuestionMultipleChoice and test its methods."""
#     from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice

#     q = QuestionMultipleChoice.example()
#     q.question_text
#     q.question_options
#     q.question_name
#     # validate an answer
#     q._validate_answer({"answer": 0, "comment": "I like custard"})
#     # translate answer code
#     q._translate_answer_code_to_answer(0, {})
#     # simulate answer
#     q._simulate_answer()
#     q._simulate_answer(human_readable=False)
#     # serialization (inherits from Question)
#     q.to_dict()
#     assert q.from_dict(q.to_dict()) == q


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
