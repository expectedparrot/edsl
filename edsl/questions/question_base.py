"""This module contains the Question class, which is the base class for all questions in EDSL."""

from __future__ import annotations
from abc import ABC
from typing import Any, Type, Optional, List, Callable, Union, TypedDict, TYPE_CHECKING

from .exceptions import QuestionSerializationError

from ..base import PersistenceMixin, RepresentationMixin, BaseDiff, BaseDiffCollection
from ..utilities import remove_edsl_version, is_valid_variable_name

if TYPE_CHECKING:
    from ..agents import Agent
    from ..scenarios import Scenario
    from ..surveys import Survey

from .descriptors import QuestionNameDescriptor, QuestionTextDescriptor
from .answer_validator_mixin import AnswerValidatorMixin
from .register_questions_meta import RegisterQuestionsMeta
from .simple_ask_mixin import SimpleAskMixin
from .question_base_prompts_mixin import QuestionBasePromptsMixin
from .question_base_gen_mixin import QuestionBaseGenMixin

if TYPE_CHECKING:
    from .response_validator_abc import ResponseValidatorABC
    from ..language_models import LanguageModel
    from ..results import Results
    from ..jobs import Jobs


class QuestionBase(
    PersistenceMixin,
    RepresentationMixin,
    SimpleAskMixin,
    QuestionBasePromptsMixin,
    QuestionBaseGenMixin,
    ABC,
    AnswerValidatorMixin,
    metaclass=RegisterQuestionsMeta,
):
    """ABC for the Question class. All questions inherit from this class.
    Some of the constraints on child questions are defined in the RegisterQuestionsMeta metaclass.


    Every child class wiill have class attributes of question_type, _response_model and response_validator_class e.g.,

        question_type = "free_text"
        _response_model = FreeTextResponse
        response_validator_class = FreeTextResponseValidator

    """

    question_name: str = QuestionNameDescriptor()
    question_text: str = QuestionTextDescriptor()

    _answering_instructions = None
    _question_presentation = None

    def is_valid_question_name(self) -> bool:
        """Check if the question name is valid."""
        return is_valid_variable_name(self.question_name)

    @property
    def response_validator(self) -> "ResponseValidatorABC":
        """Return the response validator."""
        from edsl.questions.response_validator_factory import ResponseValidatorFactory

        rvf = ResponseValidatorFactory(self)
        return rvf.response_validator

    def duplicate(self):
        """Return a duplicate of the question."""
        return self.from_dict(self.to_dict())

    @property
    def fake_data_factory(self):
        """Return the fake data factory."""
        if not hasattr(self, "_fake_data_factory"):
            from polyfactory.factories.pydantic_factory import ModelFactory

            class FakeData(ModelFactory[self.response_model]): ...

            self._fake_data_factory = FakeData
        return self._fake_data_factory

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """Simulate a valid answer for debugging purposes (what the validator expects).
        >>> from edsl import QuestionFreeText as Q
        >>> Q.example()._simulate_answer()
        {'answer': '...', 'generated_tokens': ...}
        """
        if self.question_type == "free_text":
            return {"answer": "Hello, how are you?", 'generated_tokens': "Hello, how are you?"}
        
        simulated_answer = self.fake_data_factory.build().dict()
        if human_readable and hasattr(self, "question_options") and self.use_code:
            simulated_answer["answer"] = [
                self.question_options[index] for index in simulated_answer["answer"]
            ]
        return simulated_answer

    class ValidatedAnswer(TypedDict):
        answer: Any
        comment: Optional[str]
        generated_tokens: Optional[str]

    def _validate_answer(
        self, answer: dict, replacement_dict: dict = None
    ) -> ValidatedAnswer:
        """Validate the answer.
        >>> from edsl.questions.exceptions import QuestionAnswerValidationError
        >>> from edsl.questions import QuestionFreeText as Q
        >>> Q.example()._validate_answer({'answer': 'Hello', 'generated_tokens': 'Hello'})
        {'answer': 'Hello', 'generated_tokens': 'Hello'}
        """

        return self.response_validator.validate(answer, replacement_dict)

    @property
    def name(self) -> str:
        "Helper function so questions and instructions can use the same access method"
        return self.question_name

    def __hash__(self) -> int:
        """Return a hash of the question.

        >>> from edsl import QuestionFreeText as Q
        >>> hash(Q.example())
        1144312636257752766
        """
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    @property
    def data(self) -> dict:
        """Return a dictionary of question attributes **except** for question_type.

        >>> from edsl.questions import QuestionFreeText as Q
        >>> Q.example().data
        {'question_name': 'how_are_you', 'question_text': 'How are you?'}
        """
        exclude_list = [
            "question_type",
            # "_include_comment",
            "_fake_data_factory",
            # "_use_code",
            "_model_instructions",
        ]
        only_if_not_na_list = ["_answering_instructions", "_question_presentation"]

        only_if_not_default_list = {"_include_comment": True, "_use_code": False}

        def ok(key, value):
            if not key.startswith("_"):
                return False
            if key in exclude_list:
                return False
            if key in only_if_not_na_list and value is None:
                return False
            if (
                key in only_if_not_default_list
                and value == only_if_not_default_list[key]
            ):
                return False

            return True

        candidate_data = {
            k.replace("_", "", 1): v for k, v in self.__dict__.items() if ok(k, v)
        }

        if "func" in candidate_data:
            func = candidate_data.pop("func")
            import inspect

            candidate_data["function_source_code"] = inspect.getsource(func)

        return candidate_data

    def to_dict(self, add_edsl_version: bool = True):
        """Convert the question to a dictionary that includes the question type (used in deserialization).

        >>> from edsl.questions import QuestionFreeText as Q; Q.example().to_dict(add_edsl_version = False)
        {'question_name': 'how_are_you', 'question_text': 'How are you?', 'question_type': 'free_text'}
        """
        candidate_data = self.data.copy()
        candidate_data["question_type"] = self.question_type
        d = {key: value for key, value in candidate_data.items() if value is not None}
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "QuestionBase"

        return d

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

    @classmethod
    def _get_test_model(self, canned_response: Optional[str] = None) -> "LanguageModel":
        """Get a test model for the question."""
        from edsl.language_models import LanguageModel

        return LanguageModel.example(canned_response=canned_response, test_model=True)

    @classmethod
    def run_example(
        cls,
        show_answer: bool = True,
        model: Optional["LanguageModel"] = None,
        cache=False,
        disable_remote_cache: bool = False,
        disable_remote_inference: bool = False,
        **kwargs,
    ):
        """Run an example of the question.
        >>> from edsl.language_models import LanguageModel
        >>> from edsl import QuestionFreeText as Q
        >>> m = Q._get_test_model(canned_response = "Yo, what's up?")
        >>> m.execute_model_call("", "")
        {'message': [{'text': "Yo, what's up?"}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}
        >>> Q.run_example(show_answer = True, model = m, disable_remote_cache = True, disable_remote_inference = True)
        Dataset([{'answer.how_are_you': ["Yo, what's up?"]}])
        """
        if model is None:
            from edsl.language_models.model import Model

            model = Model()
        results = (
            cls.example(**kwargs)
            .by(model)
            .run(
                cache=cache,
                disable_remote_cache=disable_remote_cache,
                disable_remote_inference=disable_remote_inference,
            )
        )
        if show_answer:
            return results.select("answer.*")
        else:
            return results

    def __call__(
        self,
        just_answer: bool = True,
        model: Optional["LanguageModel"] = None,
        agent: Optional["Agent"] = None,
        disable_remote_cache: bool = False,
        disable_remote_inference: bool = False,
        verbose: bool = False,
        **kwargs,
    ) -> Union[Any, "Results"]:
        """Call the question.


        >>> from edsl import QuestionFreeText as Q
        >>> from edsl import Model
        >>> m = Model("test", canned_response = "Yo, what's up?")
        >>> q = Q(question_name = "color", question_text = "What is your favorite color?")
        >>> q(model = m, disable_remote_cache = True, disable_remote_inference = True, cache = False)
        "Yo, what's up?"

        """
        survey = self.to_survey()
        results = survey(
            model=model,
            agent=agent,
            **kwargs,
            verbose=verbose,
            disable_remote_cache=disable_remote_cache,
            disable_remote_inference=disable_remote_inference,
        )
        if just_answer:
            return results.select(f"answer.{self.question_name}").first()
        else:
            return results

    def run(self, *args, **kwargs) -> "Results":
        """Turn a single question into a survey and runs it."""
        return self.to_survey().run(*args, **kwargs)

    def using(self, *args, **kwargs) -> "Jobs":
        """Turn a single question into a survey and then a Job."""
        return self.to_survey().to_jobs().using(*args, **kwargs)

    async def run_async(
        self,
        just_answer: bool = True,
        model: Optional["LanguageModel"] = None,
        agent: Optional["Agent"] = None,
        disable_remote_inference: bool = False,
        **kwargs,
    ) -> Union[Any, "Results"]:
        """Call the question asynchronously.

        >>> import asyncio
        >>> from edsl.questions import QuestionFreeText as Q
        >>> m = Q._get_test_model(canned_response = "Blue")
        >>> q = Q(question_name = "color", question_text = "What is your favorite color?")
        >>> async def test_run_async(): result = await q.run_async(model=m, disable_remote_inference = True, disable_remote_cache = True); print(result)
        >>> asyncio.run(test_run_async())
        Blue
        """
        survey = self.to_survey()
        results = await survey.run_async(
            model=model,
            agent=agent,
            disable_remote_inference=disable_remote_inference,
            **kwargs,
        )
        if just_answer:
            return results.select(f"answer.{self.question_name}").first()
        else:
            return results

    def __getitem__(self, key: str) -> Any:
        """Get an attribute of the question so it can be treated like a dictionary.

        >>> from edsl.questions import QuestionFreeText as Q
        >>> Q.example()['question_text']
        'How are you?'
        """
        try:
            return getattr(self, key)
        except TypeError:
            raise KeyError(f"Question has no attribute {key} of type {type(key)}")

    def __repr__(self) -> str:
        """Return a string representation of the question. Should be able to be used to reconstruct the question.

        >>> from edsl import QuestionFreeText as Q
        >>> repr(Q.example())
        'Question(\\'free_text\\', question_name = \"""how_are_you\""", question_text = \"""How are you?\""")'
        """
        items = [
            f'{k} = """{v}"""' if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        question_type = self.to_dict().get("question_type", "None")
        return f"Question('{question_type}', {', '.join(items)})"

    def __eq__(self, other: Union[Any, Type[QuestionBase]]) -> bool:
        """Check if two questions are equal. Equality is defined as having the .to_dict().

        >>> from edsl import QuestionFreeText as Q
        >>> q1 = Q.example()
        >>> q2 = Q.example()
        >>> q1 == q2
        True
        >>> q1.question_text = "How are you John?"
        >>> q1 == q2
        False

        """
        return hash(self) == hash(other)

    def __sub__(self, other) -> BaseDiff:
        """Return the difference between two objects.
        >>> from edsl import QuestionFreeText as Q
        >>> q1 = Q.example()
        >>> q2 = q1.copy()
        >>> q2.question_text = "How are you John?"
        >>> diff = q1 - q2
        """

        return BaseDiff(other, self)

    # TODO: Throws an error that should be addressed at QuestionFunctional
    def __add__(self, other_question_or_diff):
        """
        Compose two questions into a single question.
        """
        if isinstance(other_question_or_diff, BaseDiff) or isinstance(
            other_question_or_diff, BaseDiffCollection
        ):
            return other_question_or_diff.apply(self)

    def _translate_answer_code_to_answer(
        self, answer, scenario: Optional["Scenario"] = None
    ):
        """There is over-ridden by child classes that ask for codes."""
        return answer

    def add_question(self, other: QuestionBase) -> "Survey":
        """Add a question to this question by turning them into a survey with two questions.

        >>> from edsl.questions import QuestionFreeText as Q
        >>> from edsl.questions import QuestionMultipleChoice as QMC
        >>> s = Q.example().add_question(QMC.example())
        >>> len(s.questions)
        2
        """
        return self.to_survey().add_question(other)

    def to_survey(self) -> "Survey":
        """Turn a single question into a survey.
        >>> from edsl import QuestionFreeText as Q
        >>> Q.example().to_survey().questions[0].question_name
        'how_are_you'
        """
        from edsl.surveys import Survey

        return Survey([self])

    def humanize(
        self,
        project_name: str = "Project",
        survey_description: Optional[str] = None,
        survey_alias: Optional[str] = None,
        survey_visibility: Optional["VisibilityType"] = "unlisted",
    ) -> dict:
        """
        Turn a single question into a survey and send the survey to Coop.

        Then, create a project on Coop so you can share the survey with human respondents.
        """
        s = self.to_survey()
        project_details = s.humanize(
            project_name, survey_description, survey_alias, survey_visibility
        )
        return project_details

    def by(self, *args) -> "Jobs":
        """Turn a single question into a survey and then a Job."""
        from edsl.surveys import Survey

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
        agent: Optional[dict] = {},
        answers: Optional[dict] = None,
        include_question_name: bool = False,
        height: Optional[int] = None,
        width: Optional[int] = None,
        iframe=False,
    ):
        from edsl.questions.HTMLQuestion import HTMLQuestion

        return HTMLQuestion(self).html(
            scenario, agent, answers, include_question_name, height, width, iframe
        )

    @classmethod
    def example_model(cls):
        from edsl.language_models.model import Model

        q = cls.example()
        m = Model("test", canned_response=cls._simulate_answer(q)["answer"])

        return m

    @classmethod
    def example_results(cls):
        m = cls.example_model()
        q = cls.example()
        return q.by(m).run(cache=False)

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

    # endregion


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
