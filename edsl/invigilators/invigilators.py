"""Module for creating Invigilators, which are objects to administer a question to an Agent."""
from abc import ABC, abstractmethod
import asyncio
from typing import Coroutine, Dict, Any, Optional, TYPE_CHECKING
from typing import Literal

from ..utilities.decorators import sync_wrapper
from ..questions.exceptions import QuestionAnswerValidationError
from ..base.data_transfer_models import AgentResponseDict, EDSLResultObjectInput
from ..utilities.decorators import jupyter_nb_handler

from .prompt_constructor import PromptConstructor
from .prompt_helpers import PromptPlan

if TYPE_CHECKING:
    from ..prompts import Prompt
    from ..scenarios import Scenario
    from ..surveys import Survey
    from ..caching import Cache
    from ..questions import QuestionBase
    from ..surveys.memory import MemoryPlan
    from ..language_models import LanguageModel
    from ..agents import Agent
    from ..key_management import KeyLookup


PromptType = Literal["user_prompt", "system_prompt", "encoded_image", "files_list"]

NA = "Not Applicable"


class InvigilatorBase(ABC):
    """An invigiator (someone who administers an exam) is a class that is responsible for administering a question to an agent.

    >>> InvigilatorBase.example().answer_question()
    {'message': [{'text': 'SPAM!'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}

    >>> InvigilatorBase.example().get_failed_task_result(failure_reason="Failed to get response").comment
    'Failed to get response'

    This returns an empty prompt because there is no memory the agent needs to have at q0.
    """

    def __init__(
        self,
        agent: "Agent",
        question: "QuestionBase",
        scenario: "Scenario",
        model: "LanguageModel",
        memory_plan: "MemoryPlan",
        current_answers: dict,
        survey: Optional["Survey"],
        cache: Optional["Cache"] = None,
        iteration: Optional[int] = 1,
        additional_prompt_data: Optional[dict] = None,
        raise_validation_errors: Optional[bool] = True,
        prompt_plan: Optional["PromptPlan"] = None,
        key_lookup: Optional["KeyLookup"] = None,
    ):
        """Initialize a new Invigilator."""
        self.agent = agent
        self.question = question
        self.scenario = scenario
        self.model = model
        self.memory_plan = memory_plan
        self.current_answers = current_answers or {}
        self.iteration = iteration
        self.additional_prompt_data = additional_prompt_data
        self.cache = cache
        self.survey = survey
        self.raise_validation_errors = raise_validation_errors
        self.key_lookup = key_lookup

        if prompt_plan is None:
            self.prompt_plan = PromptPlan()
        else:
            self.prompt_plan = prompt_plan

        # placeholder to store the raw model response
        self.raw_model_response = None

    @property
    def prompt_constructor(self) -> PromptConstructor:
        """Return the prompt constructor."""
        return PromptConstructor.from_invigilator(self, prompt_plan=self.prompt_plan)

    def to_dict(self, include_cache=False) -> Dict[str, Any]:
        attributes = [
            "agent",
            "question",
            "scenario",
            "model",
            "memory_plan",
            "current_answers",
            "iteration",
            "additional_prompt_data",
            "survey",
            "raw_model_response",
        ]
        if include_cache:
            attributes.append("cache")

        def serialize_attribute(attr):
            value = getattr(self, attr)
            if value is None:
                return None
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if isinstance(value, (int, float, str, bool, dict, list)):
                return value
            return str(value)

        return {attr: serialize_attribute(attr) for attr in attributes}

    @classmethod
    def from_dict(cls, data) -> "InvigilatorBase":
        from ..agents import Agent
        from ..questions import QuestionBase
        from ..scenarios import Scenario
        from ..surveys.memory import MemoryPlan
        from ..language_models import LanguageModel
        from ..surveys import Survey
        from ..caching import Cache

        attributes_to_classes = {
            "agent": Agent,
            "question": QuestionBase,
            "scenario": Scenario,
            "model": LanguageModel,
            "memory_plan": MemoryPlan,
            "survey": Survey,
            "cache": Cache,
        }
        d = {}
        for attr, cls_ in attributes_to_classes.items():
            if attr in data and data[attr] is not None:
                if attr not in data:
                    d[attr] = {}
                else:
                    d[attr] = cls_.from_dict(data[attr])

        d["current_answers"] = data["current_answers"]
        d["iteration"] = data["iteration"]
        d["additional_prompt_data"] = data["additional_prompt_data"]

        d = cls(**d)
        d.raw_model_response = data.get("raw_model_response")
        return d

    def __repr__(self) -> str:
        """Return a string representation of the Invigilator.

        >>> InvigilatorBase.example().__repr__()
        'InvigilatorExample(...)'

        """
        return f"{self.__class__.__name__}(agent={repr(self.agent)}, question={repr(self.question)}, scenario={repr(self.scenario)}, model={repr(self.model)}, memory_plan={repr(self.memory_plan)}, current_answers={repr(self.current_answers)}, iteration={repr(self.iteration)}, additional_prompt_data={repr(self.additional_prompt_data)}, cache={repr(self.cache)})"

    def get_failed_task_result(self, failure_reason: str) -> EDSLResultObjectInput:
        """Return an AgentResponseDict used in case the question-asking fails.

        Possible reasons include:
        - Legimately skipped because of skip logic
        - Failed to get response from the model

        """
        data = {
            "answer": None,
            "generated_tokens": getattr(self, "generated_tokens", None),
            "comment": failure_reason,
            "question_name": self.question.question_name,
            "prompts": self.get_prompts(),
            "cached_response": getattr(self, "cached_response", None),
            "raw_model_response": getattr(self, "raw_model_response", None),
            "cache_used": getattr(self, "cache_used", None),
            "cache_key": getattr(self, "cache_key", None),
        }
        return EDSLResultObjectInput(**data)

    def get_prompts(self) -> Dict[str, "Prompt"]:
        """Return the prompt used."""
        from ..prompts import Prompt

        return {
            "user_prompt": Prompt("NA"),
            "system_prompt": Prompt("NA"),
        }

    @abstractmethod
    async def async_answer_question(self):
        """Asnwer a question."""
        pass

    @jupyter_nb_handler
    def answer_question(self) -> Coroutine:
        """Return a function that gets the answers to the question."""

        async def main():
            """Return the answer to the question."""
            results = await asyncio.gather(self.async_answer_question())
            return results[0]  # Since there's only one task, return its result

        return main()

    @classmethod
    def example(
        cls, throw_an_exception=False, question=None, scenario=None, survey=None
    ) -> "InvigilatorBase":
        """Return an example invigilator.

        >>> InvigilatorBase.example()
        InvigilatorExample(...)

        >>> InvigilatorBase.example().answer_question()
        {'message': [{'text': 'SPAM!'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}

        >>> InvigilatorBase.example(throw_an_exception=True).answer_question()
        Traceback (most recent call last):
        ...
        Exception: This is a test error
        """
        from ..agents import Agent
        from ..scenarios import Scenario
        from ..surveys.memory import MemoryPlan
        from ..language_models import Model
        from ..surveys import Survey

        model = Model("test", canned_response="SPAM!")

        if throw_an_exception:
            model.throw_exception = True
        agent = Agent.example()

        if not survey:
            survey = Survey.example()

        if question not in survey.questions and question is not None:
            survey.add_question(question)

        question = question or survey.questions[0]
        scenario = scenario or Scenario.example()
        memory_plan = MemoryPlan(survey=survey)
        current_answers = None

        class InvigilatorExample(cls):
            """An example invigilator."""

            async def async_answer_question(self):
                """Answer a question."""
                return await self.model.async_execute_model_call(
                    user_prompt="Hello", system_prompt="Hi"
                )

        return InvigilatorExample(
            agent=agent,
            question=question,
            scenario=scenario,
            survey=survey,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
        )


class InvigilatorAI(InvigilatorBase):
    """An invigilator that uses an AI model to answer questions."""

    def get_prompts(self) -> Dict[PromptType, "Prompt"]:
        """Return the prompts used."""
        return self.prompt_constructor.get_prompts()

    def get_captured_variables(self) -> dict:
        """Get the captured variables."""
        return self.prompt_constructor.get_captured_variables()

    async def async_get_agent_response(self) -> AgentResponseDict:
        prompts = self.get_prompts()
        params = {
            "user_prompt": prompts["user_prompt"].text,
            "system_prompt": prompts["system_prompt"].text,
        }
        if "encoded_image" in prompts:
            params["encoded_image"] = prompts["encoded_image"]
            from .exceptions import InvigilatorNotImplementedError

            raise InvigilatorNotImplementedError("encoded_image not implemented")

        if "files_list" in prompts:
            params["files_list"] = prompts["files_list"]

        params.update({"iteration": self.iteration, "cache": self.cache})
        params.update({"invigilator": self})

        if self.key_lookup:
            self.model.set_key_lookup(self.key_lookup)

        return await self.model.async_get_response(**params)

    def store_response(self, agent_response_dict: AgentResponseDict) -> None:
        """Store the response in the invigilator, in case it is needed later because of validation failure."""
        self.raw_model_response = agent_response_dict.model_outputs.response
        self.generated_tokens = agent_response_dict.edsl_dict.generated_tokens
        self.cache_key = agent_response_dict.model_outputs.cache_key

    async def async_answer_question(self) -> EDSLResultObjectInput:
        """Answer a question using the AI model.

        >>> i = InvigilatorAI.example()
        """
        agent_response_dict: AgentResponseDict = await self.async_get_agent_response()
        self.store_response(agent_response_dict)
        out = self._extract_edsl_result_entry_and_validate(agent_response_dict)
        return out

    def _remove_from_cache(self, cache_key) -> None:
        """Remove an entry from the cache."""
        if cache_key:
            del self.cache.data[cache_key]

    def _determine_answer(self, raw_answer: str) -> Any:
        """Determine the answer from the raw answer.

        >>> i = InvigilatorAI.example()
        >>> i._determine_answer("SPAM!")
        'SPAM!'

        >>> from edsl.questions import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(question_text = "How are you?", question_name = "how_are_you", question_options = ["Good", "Bad"], use_code = True)
        >>> i = InvigilatorAI.example(question = q)
        >>> i._determine_answer("1")
        'Bad'
        >>> i._determine_answer("0")
        'Good'

        This shows how the answer can depend on scenario details

        >>> from edsl import Scenario
        >>> s = Scenario({'feeling_options':['Good', 'Bad']})
        >>> q = QuestionMultipleChoice(question_text = "How are you?", question_name = "how_are_you", question_options = "{{ feeling_options }}", use_code = True)
        >>> i = InvigilatorAI.example(question = q, scenario = s)
        >>> i._determine_answer("1")
        'Bad'

        >>> from edsl import QuestionList, QuestionMultipleChoice, Survey
        >>> q1 = QuestionList(question_name = "favs", question_text = "What are your top 3 colors?")
        >>> q2 = QuestionMultipleChoice(question_text = "What is your favorite color?", question_name = "best", question_options = "{{ favs.answer }}", use_code = True)
        >>> survey = Survey([q1, q2])
        >>> i = InvigilatorAI.example(question = q2, scenario = s, survey = survey)
        >>> i.current_answers = {"favs": ["Green", "Blue", "Red"]}
        >>> i._determine_answer("2")
        'Red'
        """
        substitution_dict = self._prepare_substitution_dict(
            self.survey, self.current_answers, self.scenario
        )
        return self.question._translate_answer_code_to_answer(
            raw_answer, substitution_dict
        )

    @staticmethod
    def _prepare_substitution_dict(
        survey: "Survey", current_answers: dict, scenario: "Scenario"
    ) -> Dict[str, Any]:
        """Prepares a substitution dictionary for the question based on the survey, current answers, and scenario.

        This is necessary beause sometimes the model's answer to a question could depend on details in
        the prompt that were provided by the answer to a previous question or a scenario detail.

        Note that the question object is getting the answer & a the comment appended to it, as the
        jinja2 template might be referencing these values with a dot notation.

        """
        question_dict = survey.duplicate().question_names_to_questions()

        # iterates through the current answers and updates the question_dict (which is all questions)
        for other_question, answer in current_answers.items():
            if other_question in question_dict:
                question_dict[other_question].answer = answer
            else:
                # it might be a comment
                if (
                    new_question := other_question.split("_comment")[0]
                ) in question_dict:
                    question_dict[new_question].comment = answer

        return {**question_dict, **scenario}

    def _extract_edsl_result_entry_and_validate(
        self, agent_response_dict: AgentResponseDict
    ) -> EDSLResultObjectInput:
        """Extract the EDSL result entry and validate it."""
        edsl_dict = agent_response_dict.edsl_dict._asdict()
        exception_occurred = None
        validated = False

        if agent_response_dict.model_outputs.cache_used:
            data = {
                "answer": agent_response_dict.edsl_dict.answer
                if type(agent_response_dict.edsl_dict.answer) is str
                or type(agent_response_dict.edsl_dict.answer) is dict
                or type(agent_response_dict.edsl_dict.answer) is list
                or type(agent_response_dict.edsl_dict.answer) is int
                or type(agent_response_dict.edsl_dict.answer) is float
                or type(agent_response_dict.edsl_dict.answer) is bool
                else "",
                "comment": agent_response_dict.edsl_dict.comment
                if agent_response_dict.edsl_dict.comment
                else "",
                "generated_tokens": agent_response_dict.edsl_dict.generated_tokens,
                "question_name": self.question.question_name,
                "prompts": self.get_prompts(),
                "cached_response": agent_response_dict.model_outputs.cached_response,
                "raw_model_response": agent_response_dict.model_outputs.response,
                "cache_used": agent_response_dict.model_outputs.cache_used,
                "cache_key": agent_response_dict.model_outputs.cache_key,
                "validated": True,
                "exception_occurred": exception_occurred,
                "cost": agent_response_dict.model_outputs.cost,
            }

            result = EDSLResultObjectInput(**data)
            return result

        try:
            # if the question has jinja parameters, it is easier to make a new question with the parameters
            if self.question.parameters:
                prior_answers_dict = self.prompt_constructor.prior_answers_dict()

                # question options have be treated differently because of dynamic question
                # this logic is all in the prompt constructor
                if "question_options" in self.question.data:
                    new_question_options = self.prompt_constructor.get_question_options(
                        self.question.data
                    )
                    if new_question_options != self.question.data["question_options"]:
                        # I don't love this direct writing but it seems to work
                        self.question.question_options = new_question_options

                question_with_validators = self.question.render(
                    self.scenario | prior_answers_dict | {"agent": self.agent.traits}
                )
                question_with_validators.use_code = self.question.use_code
            else:
                question_with_validators = self.question

            validated_edsl_dict = question_with_validators._validate_answer(edsl_dict)
            answer = self._determine_answer(validated_edsl_dict["answer"])
            comment = validated_edsl_dict.get("comment", "")
            validated = True
        except QuestionAnswerValidationError as e:
            answer = None
            comment = "The response was not valid."
            # if self.raise_validation_errors:
            exception_occurred = e
        except Exception as non_validation_error:
            answer = None
            comment = "Some other error occurred."
            exception_occurred = non_validation_error
        finally:
            # even if validation failes, we still return the result

            data = {
                "answer": answer,
                "comment": comment,
                "generated_tokens": agent_response_dict.edsl_dict.generated_tokens,
                "question_name": self.question.question_name,
                "prompts": self.get_prompts(),
                "cached_response": agent_response_dict.model_outputs.cached_response,
                "raw_model_response": agent_response_dict.model_outputs.response,
                "cache_used": agent_response_dict.model_outputs.cache_used,
                "cache_key": agent_response_dict.model_outputs.cache_key,
                "validated": validated,
                "exception_occurred": exception_occurred,
                "cost": agent_response_dict.model_outputs.cost,
            }
            result = EDSLResultObjectInput(**data)
            return result

    answer_question = sync_wrapper(async_answer_question)


class InvigilatorHuman(InvigilatorBase):
    """An invigilator for when a human is answering the question."""

    validate_response: bool = False
    translate_response: bool = False

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        comment = "This is a real survey response from a human."

        def __repr__(self):
            return f"{self.literal}"

        exception_occurred = None
        validated = False
        try:
            answer = self.agent.answer_question_directly(self.question, self.scenario)
            self.raw_model_response = answer

            if self.validate_response:
                _ = self.question._validate_answer({"answer": answer})
            if self.translate_response:
                answer = self.question._translate_answer_code_to_answer(
                    answer, self.scenario
                )
            validated = True
        except QuestionAnswerValidationError as e:
            answer = None
            if self.raise_validation_errors:
                exception_occurred = e
        except Exception as e:
            answer = None
            if self.raise_validation_errors:
                exception_occurred = e
        finally:
            data = {
                "generated_tokens": NA,  # NotApplicable(),
                "question_name": self.question.question_name,
                "prompts": self.get_prompts(),
                "cached_response": NA,
                "raw_model_response": NA,
                "cache_used": NA,
                "cache_key": NA,
                "answer": answer,
                "comment": comment,
                "validated": validated,
                "exception_occurred": exception_occurred,
            }
            return EDSLResultObjectInput(**data)


class InvigilatorFunctional(InvigilatorBase):
    """A Invigilator for when the question has an answer_question_directly function."""

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        func = self.question.answer_question_directly
        answer = func(scenario=self.scenario, agent_traits=self.agent.traits)

        return EDSLResultObjectInput(
            generated_tokens=str(answer),
            question_name=self.question.question_name,
            prompts=self.get_prompts(),
            cached_response=NA,
            raw_model_response=NA,
            cache_used=NA,
            cache_key=NA,
            answer=answer["answer"],
            comment="This is the result of a functional question.",
            validated=True,
            exception_occurred=None,
        )

    def get_prompts(self) -> Dict[str, "Prompt"]:
        from ..prompts import Prompt

        """Return the prompts used."""
        return {
            "user_prompt": Prompt("NA"),
            "system_prompt": Prompt("NA"),
        }


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
