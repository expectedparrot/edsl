from __future__ import annotations
import textwrap
from abc import ABC, abstractmethod
from jinja2 import Template, Environment, meta
from typing import Any, Type
from edsl.exceptions import (
    QuestionResponseValidationError,
    QuestionSerializationError,
    QuestionScenarioRenderError,
)
from edsl.questions.descriptors import (
    InstructionsDescriptor,
    QuestionNameDescriptor,
    QuestionTextDescriptor,
    ShortNamesDictDescriptor,
)
from edsl.questions.question_registry import get_question_class
from edsl.questions.AnswerValidatorMixin import AnswerValidatorMixin


class Question(ABC, AnswerValidatorMixin):
    """
    ABC for something.
    """

    question_name: str = QuestionNameDescriptor()
    question_text: str = QuestionTextDescriptor()
    short_names_dict: dict[str, str] = ShortNamesDictDescriptor()
    instructions: str = InstructionsDescriptor()

    @property
    def data(self) -> dict:
        """Returns a dictionary of question attributes **except** for question_type"""
        # question-specific attributes start with an underscore
        candidate_data = {
            k.replace("_", "", 1): v
            for k, v in self.__dict__.items()
            if k.startswith("_")
        }
        # things (?) that over-ride defaults
        optional_attributes = {
            "set_instructions": "instructions",
        }
        # ?
        for boolean_flag, attribute in optional_attributes.items():
            if hasattr(self, boolean_flag) and not getattr(self, boolean_flag):
                candidate_data.pop(attribute, None)

        return candidate_data

    ############################
    # Serialization methods
    ############################
    def to_dict(self) -> dict[str, Any]:
        """Converts the question to a dictionary that includes the question type (useful for deserialization)."""
        candidate_data = self.data.copy()
        candidate_data["question_type"] = self.question_type
        return candidate_data

    @classmethod
    def from_dict(cls, data: dict) -> Type[Question]:
        """Constructs a question object from a dictionary created by that question's `to_dict` method."""
        local_data = data.copy()
        try:
            question_type = local_data.pop("question_type")
        except:
            raise QuestionSerializationError(
                f"Cannot deserialize question data because it does not have a 'question_type' field. "
                f"Data: {data}"
            )
        question_class = get_question_class(question_type)
        return question_class(**local_data)

    ############################
    # Dunder methods
    ############################
    def __repr__(self) -> str:
        """Returns a string representation of the question. Should be able to be used to reconstruct the question."""
        class_name = self.__class__.__name__
        items = [
            f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        return f"{class_name}({', '.join(items)})"

    def __eq__(self, other: Type[Question]) -> bool:
        """Checks if two questions are equal. Equality is defined as having the .to_dict()"""
        if not isinstance(other, Question):
            return False
        return self.to_dict() == other.to_dict()

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

    ############################
    # LLM methods
    ############################
    @staticmethod
    def scenario_render(text: str, scenario_dict: dict[str, Any]) -> str:
        """
        Replaces the variables in the question text with the values from the scenario.
        - We allow nesting, and hence we may need to do this many times. There is a nesting limit of 100.
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

    def get_prompt(self, scenario=None) -> str:
        """Shows which prompt should be used with the LLM for this question.
        It extracts the question attributes from the instantiated question data model.
        """
        scenario = scenario or {}
        template = Template(self.instructions)
        template_with_attributes = template.render(self.data)
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
    def validate_answer(self, answer: dict[str, str]):
        pass

    def validate_response(self, response):
        """Validates the response from the LLM"""
        if "answer" not in response:
            raise QuestionResponseValidationError(
                "Response from LLM does not have an answer"
            )
        return response

    @abstractmethod
    def translate_answer_code_to_answer(self):  # pragma: no cover
        """Translates the answer code to the actual answer. Behavior depends on the question type."""
        pass

    @abstractmethod
    def simulate_answer(self, human_readable=True) -> dict:  # pragma: no cover
        """Simulates a valid answer for debugging purposes (what the validator expects)"""
        pass

    ############################
    # Forward methods
    ############################
    def add_question(self, other):
        "Adds a question to this question by turning them into a survey with two questions"
        from edsl.surveys.Survey import Survey

        s = Survey([self, other], [self.question_name, other.question_name])
        return s

    def run(self, *args, **kwargs):
        "Turns a single question into a survey and runs it."
        from edsl.surveys.Survey import Survey

        s = Survey([self], [self.question_name])
        return s.run(*args, **kwargs)

    def by(self, *args):
        "Documentation missing."
        from edsl.surveys.Survey import Survey

        s = Survey([self], [self.question_name])
        return s.by(*args)
