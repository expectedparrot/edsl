from abc import ABC, abstractmethod
import asyncio
from typing import Coroutine, Dict, Any, Optional

from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import jupyter_nb_handler
from edsl.data_transfer_models import AgentResponseDict

from edsl.data.Cache import Cache

# from edsl.agents.Agent import Agent
from edsl.questions.QuestionBase import QuestionBase
from edsl.scenarios.Scenario import Scenario
from edsl.surveys.MemoryPlan import MemoryPlan
from edsl.language_models.LanguageModel import LanguageModel


class InvigilatorBase(ABC):
    """An invigiator (someone who administers an exam) is a class that is responsible for administering a question to an agent.

    >>> InvigilatorBase.example().answer_question()
    {'message': '{"answer": "SPAM!"}'}

    >>> InvigilatorBase.example().get_failed_task_result()
    {'answer': None, 'comment': 'Failed to get response', ...

    This returns an empty prompt because there is no memory the agent needs to have at q0.

    >>> InvigilatorBase.example().create_memory_prompt("q0")
    Prompt(text=\"""\""")

    >>> i = InvigilatorBase.example()
    >>> i.current_answers = {"q0": "Prior answer"}
    >>> i.memory_plan.add_single_memory("q1", "q0")
    >>> i.create_memory_prompt("q1")
    Prompt(text=\"""
            Before the question you are now answering, you already answered the following question(s):
    ...
    """

    def __init__(
        self,
        agent: "Agent",
        question: QuestionBase,
        scenario: Scenario,
        model: LanguageModel,
        memory_plan: MemoryPlan,
        current_answers: dict,
        survey: Optional["Survey"],
        cache: Optional[Cache] = None,
        iteration: Optional[int] = 1,
        additional_prompt_data: Optional[dict] = None,
        sidecar_model: Optional[LanguageModel] = None,
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
        self.sidecar_model = sidecar_model
        self.survey = survey

    def __repr__(self) -> str:
        """Return a string representation of the Invigilator.

        >>> InvigilatorBase.example().__repr__()
        'InvigilatorExample(...)'

        """
        return f"{self.__class__.__name__}(agent={repr(self.agent)}, question={repr(self.question)}, scneario={repr(self.scenario)}, model={repr(self.model)}, memory_plan={repr(self.memory_plan)}, current_answers={repr(self.current_answers)}, iteration{repr(self.iteration)}, additional_prompt_data={repr(self.additional_prompt_data)}, cache={repr(self.cache)}, sidecarmodel={repr(self.sidecar_model)})"

    def get_failed_task_result(self) -> AgentResponseDict:
        """Return an AgentResponseDict used in case the question-asking fails.

        >>> InvigilatorBase.example().get_failed_task_result()
        {'answer': None, 'comment': 'Failed to get response', ...}
        """
        return AgentResponseDict(
            answer=None,
            comment="Failed to get response",
            question_name=self.question.question_name,
            prompts=self.get_prompts(),
        )

    def get_prompts(self) -> Dict[str, Prompt]:
        """Return the prompt used."""

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

    def create_memory_prompt(self, question_name: str) -> Prompt:
        """Create a memory for the agent.

        The returns a memory prompt for the agent.

        >>> i = InvigilatorBase.example()
        >>> i.current_answers = {"q0": "Prior answer"}
        >>> i.memory_plan.add_single_memory("q1", "q0")
        >>> p = i.create_memory_prompt("q1")
        >>> p.text.strip().replace("\\n", " ").replace("\\t", " ")
        'Before the question you are now answering, you already answered the following question(s):          Question: Do you like school?  Answer: Prior answer'
        """
        return self.memory_plan.get_memory_prompt_fragment(
            question_name, self.current_answers
        )

    @classmethod
    def example(cls, throw_an_exception=False, question=None, scenario=None):
        """Return an example invigilator.

        >>> InvigilatorBase.example()
        InvigilatorExample(...)

        """
        from edsl.agents.Agent import Agent
        from edsl.questions import QuestionMultipleChoice
        from edsl.scenarios.Scenario import Scenario
        from edsl.language_models import LanguageModel
        from edsl.surveys.MemoryPlan import MemoryPlan

        from edsl.enums import InferenceServiceType

        class TestLanguageModelGood(LanguageModel):
            """A test language model."""

            _model_ = "test"
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                if hasattr(self, "throw_an_exception"):
                    raise Exception("Error!")
                return {"message": """{"answer": "SPAM!"}"""}

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                """Parse the response from the model."""
                return raw_response["message"]

        model = TestLanguageModelGood()
        if throw_an_exception:
            model.throw_an_exception = True
        agent = Agent.example()
        # question = QuestionMultipleChoice.example()
        from edsl.surveys import Survey

        survey = Survey.example()
        # if question:
        # need to have the focal question name in the list of names
        # survey._questions[0].question_name = question.question_name
        #    survey.add_question(question)
        if question:
            survey.add_question(question)

        question = question or survey.questions[0]
        scenario = scenario or Scenario.example()
        # memory_plan = None #memory_plan = MemoryPlan()
        from edsl import Survey

        memory_plan = MemoryPlan(survey=survey)
        current_answers = None
        from edsl.agents.PromptConstructionMixin import PromptConstructorMixin

        class InvigilatorExample(PromptConstructorMixin, InvigilatorBase):
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


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
