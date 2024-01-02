from __future__ import annotations
import re
import textwrap
import uuid
from abc import ABC, abstractmethod
from jinja2 import Template, Environment, meta
from pydantic import BaseModel, ValidationError
from typing import Any, Type, Union
from edsl.exceptions import (
    QuestionAnswerValidationError,
    QuestionAttributeMissing,
    QuestionResponseValidationError,
    QuestionSerializationError,
    QuestionScenarioRenderError,
)
from edsl.questions.question_registry import get_question_class
from edsl.questions.utils import LLMResponse
from edsl.utilities.utilities import HTMLSnippet


class Question(ABC):
    """
    Methods and requirements for children-Questions.

    Children must implement constuctors for two Pydantic data models:
    - `QuestionData` used to validate the data that creates a question
    - `AnswerData` used to validate the answers, and can depend on `QuestionData`

    Some notes on the attributes
    - `question_type` registers the question type.
    - `instructions` are directed towards agents to help construct prompts.

    There is a validation step for the LLM response:
    - The LLM should always return valid JSON with two fields: "answer" and "comments"
    - Use indices instead of the actual text of the option keys. The reason to use indices instead of
      the actual text is that it will make type checking of LLM responses easier.
    - The "answer" field should be valid for the question type.

    Question responses are required by default but can be specified as required=False at construction.
    """

    def __init__(self, question: BaseModel):
        # create class attributes for all fields of the QuestionData pydantic model
        for key, value in question.model_dump().items():
            setattr(self, key, value)
        # store the dict representation of the QuestionData pydantic model
        self.data = question.model_dump()
        # use QuestionData to construct the AnswerData pydantic model
        self.answer_data_model = self.construct_answer_data_model()
        self.uuid = str(uuid.uuid4())
        self.sanity_checks()

    def to_dict(self) -> dict:
        """Converts a Question to a dictionary"""
        # TODO: This is a very specific dictionary, which should be a model
        # TODO: having {type:str, data:dict}
        data = self.data
        data["type"] = self.question_type
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Question:
        """Constructs a Question from the dictionary created by the `to_dict` method"""
        # do not alter the original data
        local_data = data.copy()
        try:
            question_type = local_data.pop("type")
        except:
            raise QuestionSerializationError(
                "Question data does not have a 'type' field"
            )
        # Use the get_question_class function to lazily load the class
        question_class = get_question_class(question_type)
        return question_class(**local_data)

    def __repr__(self):
        class_name = self.__class__.__name__.replace("Enhanced", "")
        items = [
            f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "type"
        ]
        return f"{class_name}({', '.join(items)})"

    # TODO: Throws an error that should be addressed at QuestionFunctional
    def __add__(self, other_question):
        """
        Composes two questions into a single question.
        >>> from edsl.scenarios.Scenario import Scenario
        >>> from edsl.questions.QuestionFreeText import QuestionFreeText
        >>> from edsl.questions.QuestionNumerical import QuestionNumerical
        >>> q1 = QuestionFreeText(question_text = "What is the capital of {{country}}", question_name = "capital")
        >>> q2 = QuestionNumerical(question_text = "What is the population of {{capital}}, in millions. Please round", question_name = "population")
        >>> q3 = q1 + q2
        >>> Scenario({"country": "France"}).to(q3).run().select("capital_population")
        ['2']
        """
        from edsl.questions import compose_questions

        return compose_questions(self, other_question)

    @property
    @abstractmethod
    def instructions(self) -> str:  # pragma: no cover
        """
        Instructions for each question.
        - the values are question type-specific
        - the templating standard is Jinja2.
        - it is necessary to include both "answer" and "comment" as the only keys.
        - Note: children should implement this method as a property.

        An example for `QuestionFreeText`:
         You are being asked the following question: {{question_text}}
         Return a valid JSON formatted like this:
         {"answer": "<your free text answer>", "comment": "<put explanation here>"}
        """
        pass

    @staticmethod
    def scenario_render(text: str, scenario_dict: dict) -> str:
        """
        Scenarios come in as dictionaries. This function goes through the text of a question
        we are presenting to the LLM and replaces the variables with the values from the scenario.
        Because we allow for nesting, we need to do this many times.
        - We hard-code in a nesting limit of 100 just because if we hit that, it's probably a bug and not that some lunatic has actually made a 100-deep nested question.
        """
        t = text
        MAX_NESTING = 100
        counter = 0
        while True:
            counter += 1
            new_t = Template(t).render(scenario_dict)
            if new_t == t:
                break
            t = new_t
            if counter > MAX_NESTING:
                raise QuestionScenarioRenderError(
                    "Too much nesting - you created an infnite loop here, pal"
                )

        return new_t

    def get_prompt(self, scenario=None) -> str:
        """Shows which prompt should be used with the LLM for this question.
        It extracts the question attributes from the instantiated question data model.
        """
        if scenario is None:
            scenario = {}

        template = Template(self.instructions)
        attributes = self.__dict__
        template_with_attributes = template.render(attributes)

        env = Environment()
        ast = env.parse(template_with_attributes)
        undeclared_variables = meta.find_undeclared_variables(ast)
        if any([v not in scenario for v in undeclared_variables]):
            raise QuestionScenarioRenderError(
                f"Scenario is missing variables: {undeclared_variables}"
            )

        prompt = self.scenario_render(template_with_attributes, scenario)
        return prompt

    @abstractmethod
    def translate_answer_code_to_answer(self):  # pragma: no cover
        """Translates the answer code to the actual answer. Behavior depends on the question type."""
        pass

    @abstractmethod
    def construct_answer_data_model(self) -> Type[BaseModel]:  # pragma: no cover
        """Constructs the Pydantic data model for the answer"""
        pass

    def validate_response(self, response: dict) -> Union[dict, None]:
        """Validates the LLM response."""
        try:
            _ = LLMResponse(**response)
        except Exception as e:
            print(e)
            print(f"Offending response: {response}")
            raise QuestionResponseValidationError("Invalid response")

        return response

    def validate_answer(self, answer: Any) -> Union[dict, None]:
        """Validates the answer to the question using the constructed answer_data_model"""
        try:
            return self.answer_data_model(**answer).model_dump()
        except ValidationError as e:
            raise QuestionAnswerValidationError(f"Invalid answer {answer}/nError: {e}")

    @abstractmethod
    def simulate_answer(self, human_readable=True) -> dict:  # pragma: no cover
        """Simulates a valid answer for debugging purposes (what the validator expects)"""
        pass

    def formulate_prompt(self, traits=None, focal_item=None):
        """
        Builds the prompt to send to the LLM. The system prompt contains:
        - Context that might be helpful
        - The traits of the agent
        - The focal item and a description of what it is.
        """
        system_prompt = ""

        instruction_part = textwrap.dedent(
            """\
        You are answering questions as if you were a human. 
        Do not break character.  
        """
        )
        system_prompt += instruction_part

        if traits is not None:
            relevant_trait = traits.relevant_traits(self)
            traits_part = f"Your traits are: {relevant_trait}"
            system_prompt += traits_part

        prompt = ""
        if focal_item is not None:
            focal_item_prompt_fragment = textwrap.dedent(
                f"""\
            The question you will be asked will be about a {focal_item.meta_description}.
            The particular one you are responding to is: {focal_item.content}.
            """
            )
            prompt += focal_item_prompt_fragment

        prompt += self.get_prompt()

        return prompt, system_prompt

    def sanity_checks(self) -> None:
        """Some sanity checks for a Question."""
        SPECIAL = ["QuestionFunctionalEnhanced"]
        expected_attributes = ["question_name", "question_text"]
        if self.__class__.__name__ not in SPECIAL:
            # Check if all expected attributes are present
            for attribute in expected_attributes:
                if attribute not in self.__dict__:
                    raise QuestionAttributeMissing(
                        f"Question {self.__class__} is missing attribute {attribute}"
                    )
            # Check for unescaped curly braces in `question_text`
            matches_single_but_not_double = r"(?<!\\)(?<!{){(?!{)|(?<!\\)(?!})}(?!})"
            if bool(re.search(matches_single_but_not_double, self.question_text)):
                print("WARNING: unescaped curly braces in `question_text`.")
                print("You probably meant to use **double** curly braces.")

    @abstractmethod
    def form_elements(self):  # pragma: no cover
        """Returns the HTML that helps to put this question in a form"""
        pass

    ################
    # Question -> Survey methods
    ################
    def add_question(self, other):
        "Adds a question to this question by turning them into a survey with two questions"
        from edsl.surveys.Survey import Survey

        s = Survey([self, other], [self.question_name, other.question_name])
        return s

    def run(self, *args, **kwargs):
        "Turns a single question into a survey and run it."
        from edsl.surveys.Survey import Survey

        s = Survey([self], [self.question_name])
        return s.run(*args, **kwargs)

    def by(self, *args):
        "This turns a single question into a survey and runs it."
        from edsl.surveys.Survey import Survey

        s = Survey([self], [self.question_name])
        return s.by(*args)

    ################
    # Less important
    ################
    def html(self, submit_url=None):
        submit_button = f'<input type="submit" value="Submit">\n' if submit_url else ""
        html_string = (
            f'<form id="{self.question_name}" action="{submit_url if submit_url else ""}" method="post">'
            f"<div>{self.form_elements()}</div>"
            f'<input type="hidden" name="question_name" value="{self.question_name}">'
            f"{submit_button}"
            "</form>"
        )
        return HTMLSnippet(html_string)
