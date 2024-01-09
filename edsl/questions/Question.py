from __future__ import annotations
import re
import textwrap
from abc import ABC, abstractmethod
from jinja2 import Template, Environment, meta

# from pydantic import BaseModel, ValidationError
from typing import Any, Type, Union
from edsl.exceptions import (
    QuestionAnswerValidationError,
    QuestionAttributeMissing,
    QuestionResponseValidationError,
    QuestionSerializationError,
    QuestionScenarioRenderError,
)
from edsl.questions.question_registry import get_question_class

# from edsl.questions.utils import LLMResponse
# from edsl.utilities.utilities import HTMLSnippet


class Question(ABC):
    """ """

    @property
    def data(self):
        """ "Data is a dictionary of all the attributes of the question, except for the question_type"""
        return {k.replace("_", "", 1): v for k, v in self.__dict__.items()}

    def to_dict(self) -> dict:
        """Converts a dictionary and adds in the question type"""
        data = self.data.copy()
        data["question_type"] = self.question_type
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Question:
        """Constructs a Question from the dictionary created by the `to_dict` method"""
        local_data = data.copy()
        try:
            question_type = local_data.pop("question_type")
        except:
            raise QuestionSerializationError(
                "Question data does not have a 'question_type' field"
            )
        question_class = get_question_class(question_type)
        return question_class(**local_data)

    def __repr__(self):
        class_name = self.__class__.__name__.replace("Enhanced", "")
        items = [
            f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        return f"{class_name}({', '.join(items)})"

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
    def translate_answer_code_to_answer(self):  # pragma: no cover
        """Translates the answer code to the actual answer. Behavior depends on the question type."""
        pass

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
