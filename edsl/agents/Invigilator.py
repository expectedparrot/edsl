"""Module for creating Invigilators, which are objects to administer a question to an Agent."""
from abc import ABC, abstractmethod
import asyncio
import json
from typing import Coroutine, Dict, Any, Optional

from edsl.exceptions import AgentRespondedWithBadJSONError
from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.prompts.registry import get_classes as prompt_lookup
from edsl.exceptions import QuestionScenarioRenderError
from edsl.data_transfer_models import AgentResponseDict
from edsl.exceptions.agents import FailedTaskException
from edsl.agents.PromptConstructionMixin import PromptConstructorMixin

from edsl.agents.InvigilatorBase import InvigilatorBase

class InvigilatorAI(PromptConstructorMixin, InvigilatorBase):
    """An invigilator that uses an AI model to answer questions."""

    async def async_answer_question(self, failed:bool=False) -> AgentResponseDict:
        """Answer a question using the AI model.
        """
        params = self.get_prompts() | {"iteration": self.iteration}
        raw_response = await self.async_get_response(**params)
        assert "raw_model_response" in raw_response
        data = {
            "agent": self.agent,
            "question": self.question,
            "scenario": self.scenario,
        }
        raw_response_data = {"raw_response": raw_response,
                             "raw_model_response": raw_response["raw_model_response"]}   
        params = data | raw_response_data
        response = self._format_raw_response(**params)
        return AgentResponseDict(**response)

    async def async_get_response(
        self, user_prompt: Prompt, system_prompt: Prompt, iteration: int = 1
    ):
        """Call the LLM and gets a response. Used in the `answer_question` method."""
        try:
            response = await self.model.async_get_response(
                user_prompt=user_prompt.text,
                system_prompt=system_prompt.text,
                iteration=iteration,
            )
        except json.JSONDecodeError as e:
            raise AgentRespondedWithBadJSONError(
                f"Returned bad JSON: {e}"
                f"Prompt: {user_prompt}"
                f"System Prompt: {system_prompt}"
            )

        return response

    def _format_raw_response(
        self, *, agent, question, scenario, raw_response, raw_model_response
    ) -> AgentResponseDict:
        """Return formatted raw response.

        This cleans up the raw response to make it suitable to pass to AgentResponseDict.
        """
        response = question._validate_answer(raw_response)
        comment = response.get("comment", "")
        answer_code = response["answer"]
        answer = question._translate_answer_code_to_answer(answer_code, scenario)
        raw_model_response = raw_model_response
        data = {
            "answer": answer,
            "comment": comment,
            "question_name": question.question_name,
            "prompts": {k: v.to_dict() for k, v in self.get_prompts().items()},
            "cached_response": raw_response["cached_response"],
            "usage": raw_response.get("usage", {}),
            "raw_model_response": raw_model_response,
        }
        return AgentResponseDict(**data)

    get_response = sync_wrapper(async_get_response)
    answer_question = sync_wrapper(async_answer_question)

class InvigilatorDebug(InvigilatorBase):
    """An invigilator class for debugging purposes."""

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        results = self.question._simulate_answer(human_readable=True)
        results["prompts"] = self.get_prompts()
        results["question_name"] = self.question.question_name
        results["comment"] = "Debug comment"
        return AgentResponseDict(**results)

    def get_prompts(self) -> Dict[str, Prompt]:
        """Return the prompts used."""
        return {
            "user_prompt": Prompt("NA").text,
            "system_prompt": Prompt("NA").text,
        }

class InvigilatorHuman(InvigilatorBase):
    """An invigilator for when a human is answering the question."""

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        data = {
            "comment": "This is a real survey response from a human.",
            "answer": None,
            "prompts": self.get_prompts(),
            "question_name": self.question.question_name,
        }
        try:
            answer = self.agent.answer_question_directly(self.question, self.scenario)
            return AgentResponseDict(**(data | {"answer": answer}))
        except Exception as e:
            agent_response_dict = AgentResponseDict(
                **(data | {"answer": None, "comment": str(e)})
            )
            raise FailedTaskException(
                f"Failed to get response. The exception is {str(e)}",
                agent_response_dict,
            ) from e


class InvigilatorFunctional(InvigilatorBase):
    """A Invigilator for when the question has a answer_question_directly function."""

    async def async_answer_question(self, iteration: int = 0) -> AgentResponseDict:
        """Return the answer to the question."""
        func = self.question.answer_question_directly
        data = {
            "comment": "Functional.",
            "prompts": self.get_prompts(),
            "question_name": self.question.question_name,
        }
        try:
            answer = func(scenario=self.scenario, agent_traits=self.agent.traits)
            return AgentResponseDict(**(data | {"answer": answer}))
        except Exception as e:
            agent_response_dict = AgentResponseDict(
                **(data | {"answer": None, "comment": str(e)})
            )
            raise FailedTaskException(
                f"Failed to get response. The exception is {str(e)}",
                agent_response_dict,
            ) from e

    def get_prompts(self) -> Dict[str, Prompt]:
        """Return the prompts used."""
        return {
            "user_prompt": Prompt("NA").text,
            "system_prompt": Prompt("NA").text,
        }


if __name__ == "__main__":
    from edsl.enums import LanguageModelType

    from edsl.agents.Agent import Agent

    a = Agent(
        instruction="You are a happy-go lucky agent.",
        traits={"feeling": "happy", "age": "Young at heart"},
        codebook={"feeling": "Feelings right now", "age": "Age in years"},
        trait_presentation_template="",
    )

    class MockModel:
        """Mock model for testing."""

        model = LanguageModelType.GPT_4.value

    class MockQuestion:
        """Mock question for testing."""

        question_type = "free_text"
        question_text = "How are you feeling?"
        question_name = "feelings_question"
        data = {
            "question_name": "feelings",
            "question_text": "How are you feeling?",
            "question_type": "feelings_question",
        }

    i = InvigilatorAI(
        agent=a,
        question=MockQuestion(),
        scenario={},
        model=MockModel(),
        memory_plan=None,
        current_answers=None,
    )
    print(i.get_prompts()["system_prompt"])
    assert i.get_prompts()["system_prompt"].text == "You are a happy-go lucky agent."

    ###############
    ## Render one
    ###############

    a = Agent(
        instruction="You are a happy-go lucky agent.",
        traits={"feeling": "happy", "age": "Young at heart"},
        codebook={"feeling": "Feelings right now", "age": "Age in years"},
        trait_presentation_template="You are feeling {{ feeling }}.",
    )

    i = InvigilatorAI(
        agent=a,
        question=MockQuestion(),
        scenario={},
        model=MockModel(),
        memory_plan=None,
        current_answers=None,
    )
    print(i.get_prompts()["system_prompt"])

    assert (
        i.get_prompts()["system_prompt"].text
        == "You are a happy-go lucky agent. You are feeling happy."
    )
    try:
        assert i.get_prompts()["system_prompt"].unused_traits(a.traits) == ["age"]
    except AssertionError:
        unused_traits = i.get_prompts()["system_prompt"].unused_traits(a.traits)
        print(f"System prompt: {i.get_prompts()['system_prompt']}")
        print(f"Agent traits: {a.traits}")
        print(f"Unused_traits: {unused_traits}")
        # breakpoint()

    ###############
    ## Render one
    ###############

    a = Agent(
        instruction="You are a happy-go lucky agent.",
        traits={"feeling": "happy", "age": "Young at heart"},
        codebook={"feeling": "Feelings right now", "age": "Age in years"},
        trait_presentation_template="You are feeling {{ feeling }}. You eat lots of {{ food }}.",
    )

    i = InvigilatorAI(
        agent=a,
        question=MockQuestion(),
        scenario={},
        model=MockModel(),
        memory_plan=None,
        current_answers=None,
    )
    print(i.get_prompts()["system_prompt"])

    ## Should raise a QuestionScenarioRenderError
    assert (
        i.get_prompts()["system_prompt"].text
        == "You are a happy-go lucky agent. You are feeling happy."
    )
