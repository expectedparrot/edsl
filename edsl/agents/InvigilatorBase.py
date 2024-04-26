from abc import ABC, abstractmethod
import asyncio
from typing import Coroutine, Dict, Any, Optional

from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.prompts.registry import get_classes as prompt_lookup
from edsl.data_transfer_models import AgentResponseDict

from edsl.data.Cache import Cache


class InvigilatorBase(ABC):
    """An invigiator (someone who administers an exam) is a class that is responsible for administering a question to an agent."""

    def __init__(
        self,
        agent,
        question,
        scenario,
        model,
        memory_plan,
        current_answers: dict,
        cache=None,
        iteration: int = 1,
        additional_prompt_data: Optional[dict] = None,
        sidecar_model=None,
    ):
        """Initialize a new Invigilator."""
        self.agent = agent
        self.question = question
        self.scenario = scenario
        self.model = model
        self.memory_plan = memory_plan
        self.current_answers = current_answers
        self.iteration = iteration
        self.additional_prompt_data = additional_prompt_data
        self.cache = cache
        self.sidecar_model = sidecar_model

    def get_failed_task_result(self) -> AgentResponseDict:
        """Return an AgentResponseDict used in case the question-askinf fails."""
        return AgentResponseDict(
            answer=None,
            comment="Failed to get response",
            question_name=self.question.question_name,
            prompts=self.get_prompts(),
        )

    def get_prompts(self) -> Dict[str, Prompt]:
        """Return the prompt used."""
        return {
            "user_prompt": Prompt("NA").text,
            "system_prompt": Prompt("NA").text,
        }

    @classmethod
    def example(cls):
        """Return an example invigilator."""
        from edsl.agents.Agent import Agent
        from edsl.questions import QuestionMultipleChoice
        from edsl.scenarios.Scenario import Scenario
        from edsl.language_models import LanguageModel

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
                return {"message": """{"answer": "SPAM!"}"""}
                """Return a response from the model."""

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                """Parse the response from the model."""
                return raw_response["message"]

        model = TestLanguageModelGood()
        agent = Agent.example()
        question = QuestionMultipleChoice.example()
        scenario = Scenario.example()
        #        model = LanguageModel.example()
        memory_plan = None
        current_answers = None
        return cls(
            agent=agent,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
        )

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

    def create_memory_prompt(self, question_name):
        """Create a memory for the agent."""
        return self.memory_plan.get_memory_prompt_fragment(
            question_name, self.current_answers
        )
