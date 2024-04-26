"""This module contains the Question class, which is the base class for all questions in EDSL."""
from __future__ import annotations
from abc import ABC, abstractmethod
from rich.table import Table
from typing import Any, Type, Optional

from edsl.exceptions import (
    QuestionResponseValidationError,
    QuestionSerializationError,
)
from edsl.questions.descriptors import QuestionNameDescriptor, QuestionTextDescriptor

from edsl.prompts.registry import get_classes as prompt_lookup
from edsl.questions.AnswerValidatorMixin import AnswerValidatorMixin
from edsl.questions.RegisterQuestionsMeta import RegisterQuestionsMeta
from edsl.Base import PersistenceMixin, RichPrintingMixin

from edsl.questions.SimpleAskMixin import SimpleAskMixin


class QuestionBase(
    PersistenceMixin,
    RichPrintingMixin,
    SimpleAskMixin,
    ABC,
    AnswerValidatorMixin,
    metaclass=RegisterQuestionsMeta,
):
    """ABC for the Question class. All questions should inherit from this class."""

    question_name: str = QuestionNameDescriptor()
    question_text: str = QuestionTextDescriptor()

    def __getitem__(self, key: str) -> Any:
        """Get an attribute of the question."""
        return getattr(self, key)

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    @property
    def data(self) -> dict:
        """Return a dictionary of question attributes **except** for question_type."""
        candidate_data = {
            k.replace("_", "", 1): v
            for k, v in self.__dict__.items()
            if k.startswith("_")
        }
        optional_attributes = {
            "set_instructions": "instructions",
        }
        for boolean_flag, attribute in optional_attributes.items():
            if hasattr(self, boolean_flag) and not getattr(self, boolean_flag):
                candidate_data.pop(attribute, None)

        return candidate_data

    @classmethod
    def applicable_prompts(
        cls, model: Optional[str] = None
    ) -> list[type["PromptBase"]]:
        """Get the prompts that are applicable to the question type.

        :param model: The language model to use.

        >>> from edsl.questions import QuestionFreeText
        >>> QuestionFreeText.applicable_prompts()
        [<class 'edsl.prompts.library.question_freetext.FreeText'>]

        :param model: The language model to use. If None, assumes does not matter.

        """
        applicable_prompts = prompt_lookup(
            component_type="question_instructions",
            question_type=cls.question_type,
            model=model,
        )
        return applicable_prompts

    @property
    def model_instructions(self) -> dict:
        """Get the model-specific instructions for the question."""
        if not hasattr(self, "_model_instructions"):
            self._model_instructions = {}
        return self._model_instructions

    @model_instructions.setter
    def model_instructions(self, data: dict):
        """Set the model-specific instructions for the question."""
        self._model_instructions = data

    def add_model_instructions(
        self, *, instructions: str, model: Optional[str] = None
    ) -> None:
        """Add model-specific instructions for the question.

        :param instructions: The instructions to add. This is typically a jinja2 template.
        :param model: The language model for this instruction.

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite color?")
        >>> q.add_model_instructions(instructions = "Answer in valid JSON like so {'answer': 'comment: <>}", model = "gpt3")

        """
        from edsl import Model

        if not hasattr(self, "_model_instructions"):
            self._model_instructions = {}
        if model is None:
            # if not model is passed, all the models are mapped to this instruction, including 'None'
            self._model_instructions = {
                model_name: instructions
                for model_name in Model.available(name_only=True)
            }
            self._model_instructions.update({model: instructions})
        else:
            self._model_instructions.update({model: instructions})

    def get_instructions(self, model: Optional[str] = None) -> type["PromptBase"]:
        """Get the mathcing question-answering instructions for the question.

        :param model: The language model to use.
        """
        from edsl.prompts.Prompt import Prompt

        if model in self.model_instructions:
            return Prompt(text=self.model_instructions[model])
        else:
            return self.applicable_prompts(model)[0]()

    def option_permutations(self) -> list[QuestionBase]:
        """Return a list of questions with all possible permutations of the options."""

        if not hasattr(self, "question_options"):
            return [self]

        import copy
        import itertools

        questions = []
        for index, permutation in enumerate(
            itertools.permutations(self.question_options)
        ):
            question = copy.deepcopy(self)
            question.question_options = list(permutation)
            question.question_name = f"{self.question_name}_{index}"
            questions.append(question)
        return questions

    ############################
    # Serialization methods
    ############################
    def to_dict(self) -> dict[str, Any]:
        """Convert the question to a dictionary that includes the question type (used in deserialization)."""
        candidate_data = self.data.copy()
        candidate_data["question_type"] = self.question_type
        return candidate_data

    @classmethod
    def from_dict(cls, data: dict) -> Type[QuestionBase]:
        """Construct a question object from a dictionary created by that question's `to_dict` method."""
        local_data = data.copy()
        try:
            question_type = local_data.pop("question_type")
            if question_type == "linear_scale":
                # This is a fix for issue https://github.com/expectedparrot/edsl/issues/165
                options_labels = local_data.get("option_labels", None)
                if options_labels:
                    options_labels = {
                        int(key): value for key, value in options_labels.items()
                    }
                    local_data["option_labels"] = options_labels
        except:
            raise QuestionSerializationError(
                f"Data does not have a 'question_type' field (got {data})."
            )
        from edsl.questions.question_registry import get_question_class

        try:
            question_class = get_question_class(question_type)
        except ValueError:
            raise QuestionSerializationError(
                f"No question registered with question_type {question_type}"
            )

        if "model_instructions" in local_data:
            model_instructions = local_data.pop("model_instructions")
            new_q = question_class(**local_data)
            new_q.model_instructions = model_instructions
            return new_q

        return question_class(**local_data)

    ############################
    # Dunder methods
    ############################
    def __repr__(self) -> str:
        """Return a string representation of the question. Should be able to be used to reconstruct the question."""
        class_name = self.__class__.__name__
        items = [
            f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))
        return f"{class_name}({', '.join(items)})"

    def __eq__(self, other: Type[QuestionBase]) -> bool:
        """Check if two questions are equal. Equality is defined as having the .to_dict()."""
        if not isinstance(other, QuestionBase):
            return False
        return self.to_dict() == other.to_dict()

    # TODO: Throws an error that should be addressed at QuestionFunctional
    def __add__(self, other_question):
        """
        Compose two questions into a single question.

        >>> from edsl.scenarios.Scenario import Scenario
        >>> from edsl.questions.QuestionFreeText import QuestionFreeText
        >>> from edsl.questions.QuestionNumerical import QuestionNumerical
        >>> q1 = QuestionFreeText(question_text = "What is the capital of {{country}}", question_name = "capital")
        >>> q2 = QuestionNumerical(question_text = "What is the population of {{capital}}, in millions. Please round", question_name = "population")
        >>> q3 = q1 + q2
        """
        from edsl.questions import compose_questions

        return compose_questions(self, other_question)

    @abstractmethod
    def _validate_answer(self, answer: dict[str, str]):
        """Validate the answer from the LLM. Behavior depends on the question type."""
        pass

    def _validate_response(self, response):
        """Validate the response from the LLM. Behavior depends on the question type."""
        if "answer" not in response:
            raise QuestionResponseValidationError(
                "Response from LLM does not have an answer"
            )
        return response

    @abstractmethod
    def _translate_answer_code_to_answer(self):  # pragma: no cover
        """Translate the answer code to the actual answer. Behavior depends on the question type."""
        pass

    @abstractmethod
    def _simulate_answer(self, human_readable=True) -> dict:  # pragma: no cover
        """Simulate a valid answer for debugging purposes (what the validator expects)."""
        pass

    ############################
    # Forward methods
    ############################
    def add_question(self, other: Question) -> "Survey":
        """Add a question to this question by turning them into a survey with two questions."""
        from edsl.surveys.Survey import Survey

        s = Survey([self, other])
        return s

    def run(self, *args, **kwargs):
        """Turn a single question into a survey and run it."""
        from edsl.surveys.Survey import Survey

        s = Survey([self])
        return s.run(*args, **kwargs)

    def by(self, *args):
        """Turn a single question into a survey and run it."""
        from edsl.surveys.Survey import Survey

        s = Survey([self])
        return s.by(*args)

    def human_readable(self):
        """Print the question in a human readable format."""
        lines = []
        lines.append(f"Question Type: {self.question_type}")
        lines.append(f"Question: {self.question_text}")
        if hasattr(self, "question_options"):
            lines.append("Please name the option you choose from the following.:")
            for index, option in enumerate(self.question_options):
                lines.append(f"{option}")
        return "\n".join(lines)

    def rich_print(self):
        """Print the question in a rich format."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Question Name", style="dim")
        table.add_column("Question Type")
        table.add_column("Question Text")
        table.add_column("Options")

        question = self
        if hasattr(question, "question_options"):
            options = ", ".join([str(o) for o in question.question_options])
        else:
            options = "None"
        table.add_row(
            question.question_name,
            question.question_type,
            question.question_text,
            options,
        )
        return table


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
