"""This module contains the Question class, which is the base class for all questions in EDSL."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Type, Optional, List, Callable, Union
import copy

from edsl.exceptions import (
    QuestionResponseValidationError,
    QuestionSerializationError,
)
from edsl.questions.descriptors import QuestionNameDescriptor, QuestionTextDescriptor


from edsl.questions.AnswerValidatorMixin import AnswerValidatorMixin
from edsl.questions.RegisterQuestionsMeta import RegisterQuestionsMeta
from edsl.Base import PersistenceMixin, RichPrintingMixin
from edsl.BaseDiff import BaseDiff, BaseDiffCollection

from edsl.questions.SimpleAskMixin import SimpleAskMixin
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version
from edsl.exceptions import QuestionAnswerValidationError


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

    # default_template_settings = {"include_comment": True, "use_code": True}

    @property
    def response_model(self):
        if self._response_model is not None:
            return self._response_model
        else:
            return self.create_response_model()

    @classmethod
    def self_check(cls):
        q = cls.example()
        for answer, params in q.response_validator.valid_examples:
            for key, value in params.items():
                setattr(q, key, value)
            q._validate_answer(answer)
        for answer, params, reason in q.response_validator.invalid_examples:
            for key, value in params.items():
                setattr(q, key, value)
            try:
                q._validate_answer(answer)
            except QuestionAnswerValidationError:
                pass
            else:
                raise ValueError(f"Example {answer} should have failed for {reason}.")

    @property
    def new_default_instructions(self):
        "This is set up as a property because there are mutable question values that determine how it is rendered."
        from edsl.prompts import Prompt

        return Prompt.from_template("question_" + self.question_type)

    @property
    def response_validator(self) -> "ResponseValidatorBase":
        """Return the response validator."""
        params = {
            "response_model": self.response_model,
        } | {k: getattr(self, k) for k in self.validator_parameters}
        return self.response_validator_class(**params)

    def _simulate_answer(self, human_readable: bool = True):
        """Simulate a valid answer for debugging purposes (what the validator expects)."""
        # num_items = random.randint(1, self.max_list_items or 2)
        # from edsl.utilities.utilities import random_string
        # return {"answer": [random_string() for _ in range(num_items)]}
        from polyfactory.factories.pydantic_factory import ModelFactory

        class FakeData(ModelFactory[self.response_model]): ...

        return FakeData.build().dict()

    def _validate_answer(
        self, answer: dict[str, Any]
    ) -> dict[str, Union[str, float, int]]:
        """Validate the answer."""
        return self.response_validator.validate(answer)

    def __getitem__(self, key: str) -> Any:
        """Get an attribute of the question."""
        return getattr(self, key)

    def __hash__(self) -> int:
        """Return a hash of the question."""
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self._to_dict())

    @property
    def name(self):
        "Helper function so questions and instructions can use the same access method"
        return self.question_name

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        data = self.to_dict()
        try:
            _ = data.pop("edsl_version")
            _ = data.pop("edsl_class_name")
        except KeyError:
            print("Serialized question lacks edsl version, but is should have it.")

        return data_to_html(data)

    def apply_function(self, func: Callable, exclude_components=None) -> QuestionBase:
        """Apply a function to the question parts

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite color?")
        >>> shouting = lambda x: x.upper()
        >>> q.apply_function(shouting)
        Question('free_text', question_name = \"""color\""", question_text = \"""WHAT IS YOUR FAVORITE COLOR?\""")

        """
        if exclude_components is None:
            exclude_components = ["question_name", "question_type"]

        d = copy.deepcopy(self._to_dict())
        for key, value in d.items():
            if key in exclude_components:
                continue
            if isinstance(value, dict):
                for k, v in value.items():
                    value[k] = func(v)
                d[key] = value
                continue
            if isinstance(value, list):
                value = [func(v) for v in value]
                d[key] = value
                continue
            d[key] = func(value)
        return QuestionBase.from_dict(d)

    @property
    def data(self) -> dict:
        """Return a dictionary of question attributes **except** for question_type."""
        exclude_list = ["question_type", "_include_comment", "_use_code"]
        candidate_data = {
            k.replace("_", "", 1): v
            for k, v in self.__dict__.items()
            if k.startswith("_") and k not in exclude_list
        }
        # optional_attributes = {
        #     "set_instructions": "instructions",
        #     "set_comment_off": "include_comment",
        #     "set_code_off": "use_code",
        # }
        # for boolean_flag, attribute in optional_attributes.items():
        #     if hasattr(self, boolean_flag):  # and not getattr(self, boolean_flag):
        #         candidate_data.pop(attribute, None)

        if "func" in candidate_data:
            func = candidate_data.pop("func")
            import inspect

            candidate_data["function_source_code"] = inspect.getsource(func)

        return candidate_data

    def loop(self, scenario_list: "ScenarioList") -> List[QuestionBase]:
        from jinja2 import Environment

        staring_name = self.question_name
        questions = []
        for index, scenario in enumerate(scenario_list):
            env = Environment()
            new_data = self.to_dict().copy()
            for key, value in new_data.items():
                if isinstance(value, str):
                    new_data[key] = env.from_string(value).render(scenario)
                elif isinstance(value, list):
                    new_data[key] = [
                        env.from_string(v).render(scenario) if isinstance(v, str) else v
                        for v in value
                    ]
                elif isinstance(value, dict):
                    new_data[key] = {
                        (
                            env.from_string(k).render(scenario)
                            if isinstance(k, str)
                            else k
                        ): (
                            env.from_string(v).render(scenario)
                            if isinstance(v, str)
                            else v
                        )
                        for k, v in value.items()
                    }
                else:
                    raise ValueError(f"Unexpected value type: {type(value)}")

            if new_data["question_name"] == staring_name:
                new_data["question_name"] = new_data["question_name"] + f"_{index}"
            questions.append(QuestionBase.from_dict(new_data))
        return questions

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
        from edsl.prompts.registry import get_classes as prompt_lookup

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

    def _all_text(self) -> str:
        """Return the question text."""
        txt = ""
        for key, value in self.data.items():
            if isinstance(value, str):
                txt += value
            elif isinstance(value, list):
                txt += "".join(str(value))
        return txt

    @property
    def parameters(self) -> set[str]:
        """Return the parameters of the question."""
        from jinja2 import Environment, meta

        env = Environment()
        # Parse the template
        txt = self._all_text()
        # txt = self.question_text
        # if hasattr(self, "question_options"):
        #    txt += " ".join(self.question_options)
        parsed_content = env.parse(txt)
        # Extract undeclared variables
        variables = meta.find_undeclared_variables(parsed_content)
        # Return as a list
        return set(variables)

    @model_instructions.setter
    def model_instructions(self, data: dict):
        """Set the model-specific instructions for the question."""
        self._model_instructions = data

    def add_model_instructions(
        self, *, instructions: str, model: Optional[str] = None
    ) -> None:
        """Add model-specific instructions for the question that override the default instructions.

        :param instructions: The instructions to add. This is typically a jinja2 template.
        :param model: The language model for this instruction.

        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite color?")
        >>> q.add_model_instructions(instructions = "{{question_text}}. Answer in valid JSON like so {'answer': 'comment: <>}", model = "gpt3")
        >>> q.get_instructions(model = "gpt3")
        Prompt(text=\"""{{question_text}}. Answer in valid JSON like so {'answer': 'comment: <>}\""")
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

        >>> from edsl import QuestionFreeText
        >>> QuestionFreeText.example().get_instructions()
        Prompt(text=\"""You are being asked the following question: {{question_text}}
        Return a valid JSON formatted like this:
        {"answer": "<put free text answer here>"}
        \""")
        """
        from edsl.prompts.Prompt import Prompt

        if model in self.model_instructions:
            return Prompt(text=self.model_instructions[model])
        else:
            if hasattr(self, "new_default_instructions"):
                return self.new_default_instructions
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
    def _to_dict(self):
        """Convert the question to a dictionary that includes the question type (used in deserialization)."""
        candidate_data = self.data.copy()
        candidate_data["question_type"] = self.question_type
        return candidate_data

    @add_edsl_version
    def to_dict(self) -> dict[str, Any]:
        """Convert the question to a dictionary that includes the question type (used in deserialization)."""
        return self._to_dict()

    @classmethod
    @remove_edsl_version
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

    def copy(self) -> Type[QuestionBase]:
        """Return a deep copy of the question."""
        return copy.deepcopy(self)

    ############################
    # Dunder methods
    ############################
    def print(self):
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

    def __call__(self, just_answer=True, model=None, agent=None, **kwargs):
        """Call the question.

        >>> from edsl.language_models import LanguageModel
        >>> m = LanguageModel.example(canned_response = "Yo, what's up?", test_model = True)
        >>> from edsl import QuestionFreeText
        >>> q = QuestionFreeText(question_name = "color", question_text = "What is your favorite color?")
        >>> q(model = m)
        "Yo, what's up?"

        """
        survey = self.to_survey()
        results = survey(model=model, agent=agent, **kwargs)
        if just_answer:
            return results.select(f"answer.{self.question_name}").first()
        else:
            return results

    async def run_async(
        self,
        just_answer: bool = True,
        model: Optional["Model"] = None,
        agent: Optional["Agent"] = None,
        **kwargs,
    ) -> Union[Any, "Results"]:
        """Call the question asynchronously."""
        survey = self.to_survey()
        results = await survey.run_async(model=model, agent=agent, **kwargs)
        if just_answer:
            return results.select(f"answer.{self.question_name}").first()
        else:
            return results

    def __repr__(self) -> str:
        """Return a string representation of the question. Should be able to be used to reconstruct the question."""
        class_name = self.__class__.__name__
        items = [
            f'{k} = """{v}"""' if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        question_type = self.to_dict().get("question_type", "None")
        return f"Question('{question_type}', {', '.join(items)})"

    def __eq__(self, other: Type[QuestionBase]) -> bool:
        """Check if two questions are equal. Equality is defined as having the .to_dict()."""
        if not isinstance(other, QuestionBase):
            return False
        return self.to_dict() == other.to_dict()

    def __sub__(self, other) -> BaseDiff:
        """Return the difference between two objects."""

        return BaseDiff(other, self)

    # TODO: Throws an error that should be addressed at QuestionFunctional
    def __add__(self, other_question_or_diff):
        """
        Compose two questions into a single question.

        TODO: Probably getting deprecated.

        """
        if isinstance(other_question_or_diff, BaseDiff) or isinstance(
            other_question_or_diff, BaseDiffCollection
        ):
            return other_question_or_diff.apply(self)

        from edsl.questions import compose_questions

        return compose_questions(self, other_question_or_diff)

    # @abstractmethod
    # def _validate_answer(self, answer: dict[str, str]):
    #     """Validate the answer from the LLM. Behavior depends on the question type."""
    #     pass

    def _validate_response(self, response):
        """Validate the response from the LLM. Behavior depends on the question type."""
        if "answer" not in response:
            raise QuestionResponseValidationError(
                "Response from LLM does not have an answer"
            )
        return response

    @property
    def validator_parameters(self) -> list[str]:
        return self.response_validator_class.required_params

    def _translate_answer_code_to_answer(
        self, answer, scenario: Optional["Scenario"] = None
    ):
        """There is over-ridden by child classes that ask for codes."""
        return answer

    # @abstractmethod
    # def _simulate_answer(self, human_readable=True) -> dict:  # pragma: no cover
    #     """Simulate a valid answer for debugging purposes (what the validator expects)."""
    #     pass

    ############################
    # Forward methods
    ############################
    def add_question(self, other: QuestionBase) -> "Survey":
        """Add a question to this question by turning them into a survey with two questions."""
        from edsl.surveys.Survey import Survey

        s = Survey([self, other])
        return s

    def to_survey(self) -> "Survey":
        """Turn a single question into a survey."""
        from edsl.surveys.Survey import Survey

        s = Survey([self])
        return s

    def run(self, *args, **kwargs) -> "Results":
        """Turn a single question into a survey and run it."""
        from edsl.surveys.Survey import Survey

        s = self.to_survey()
        return s.run(*args, **kwargs)

    def by(self, *args) -> "Jobs":
        """Turn a single question into a survey and then a Job."""
        from edsl.surveys.Survey import Survey

        s = Survey([self])
        return s.by(*args)

    def human_readable(self) -> str:
        """Print the question in a human readable format.

        >>> from edsl.questions import QuestionFreeText
        >>> QuestionFreeText.example().human_readable()
        'Question Type: free_text\\nQuestion: How are you?'
        """
        lines = []
        lines.append(f"Question Type: {self.question_type}")
        lines.append(f"Question: {self.question_text}")
        if hasattr(self, "question_options"):
            lines.append("Please name the option you choose from the following.:")
            for index, option in enumerate(self.question_options):
                lines.append(f"{option}")
        return "\n".join(lines)

    def html(
        self,
        scenario: Optional[dict] = None,
        include_question_name: bool = False,
        height: Optional[int] = None,
        width: Optional[int] = None,
        iframe=False,
    ):
        """Return the question in HTML format."""
        from jinja2 import Template

        if scenario is None:
            scenario = {}

        base_template = """
        <div id="{{ question_name }}" class="survey_question" data-type="{{ question_type }}">
            {% if include_question_name %}
            <p>question_name: {{ question_name }}</p>
            {% endif %}
            <p class="question_text">{{ question_text }}</p>
            {{ question_content }}
        </div>
        """
        if not hasattr(self, "question_type"):
            self.question_type = "unknown"

        if hasattr(self, "question_html_content"):
            question_content = self.question_html_content
        else:
            question_content = Template("")

        base_template = Template(base_template)

        params = {
            "question_name": self.question_name,
            "question_text": Template(self.question_text).render(scenario),
            "question_type": self.question_type,
            "question_content": Template(question_content).render(scenario),
            "include_question_name": include_question_name,
        }
        rendered_html = base_template.render(**params)

        if iframe:
            import html
            from IPython.display import display, HTML

            height = height or 200
            width = width or 600
            escaped_output = html.escape(rendered_html)
            # escaped_output = rendered_html
            iframe = f""""
            <iframe srcdoc="{ escaped_output }" style="width: {width}px; height: {height}px;"></iframe>
            """
            display(HTML(iframe))
            return None

        return rendered_html

    def rich_print(self):
        """Print the question in a rich format."""
        from rich.table import Table

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
