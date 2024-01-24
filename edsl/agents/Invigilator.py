from abc import ABC, abstractmethod
import asyncio
import json
from typing import Coroutine, Dict, Any
from collections import UserDict

from edsl.exceptions import AgentRespondedWithBadJSONError
from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.prompts.registry import get_classes
from edsl.exceptions import QuestionScenarioRenderError


class InvigilatorBase(ABC):
    """An invigiator is a class that is responsible for administering a question to an agent."""

    def __init__(self, agent, question, scenario, model, memory_plan, current_answers):
        self.agent = agent
        self.question = question
        self.scenario = scenario
        self.model = model
        self.memory_plan = memory_plan
        self.current_answers = current_answers

    @abstractmethod
    async def async_answer_question(self):
        "This is the async method that actually answers the question."
        pass

    @jupyter_nb_handler
    def answer_question(self) -> Coroutine:
        async def main():
            results = await asyncio.gather(self.async_answer_question())
            return results[0]  # Since there's only one task, return its result

        return main()

    def create_memory_prompt(self, question_name):
        """Creates a memory for the agent."""
        return self.memory_plan.get_memory_prompt_fragment(
            question_name, self.current_answers
        )


class InvigilatorAI(InvigilatorBase):
    def construct_system_prompt(self) -> Prompt:
        """Constructs the system prompt for the LLM call."""
        applicable_prompts = get_classes(
            component_type="agent_instructions",
            model=self.model.model,
        )
        if len(applicable_prompts) == 0:
            raise Exception("No applicable prompts found")

        agent_instructions = applicable_prompts[0]()
        # print(f"Agent instructions are: {agent_instructions}")

        ## agent_persona
        applicable_prompts = get_classes(
            component_type="agent_persona",
            model=self.model.model,
        )
        persona_prompt = applicable_prompts[0]()
        persona_prompt.render({"traits": self.agent.traits})
        return agent_instructions + persona_prompt

    async def async_get_response(self, user_prompt: Prompt, system_prompt: Prompt):
        """Calls the LLM and gets a response. Used in the `answer_question` method."""
        try:
            response = await self.model.async_get_response(
                user_prompt.text, system_prompt.text
            )
        except json.JSONDecodeError as e:
            raise AgentRespondedWithBadJSONError(
                f"Returned bad JSON: {e}"
                f"Prompt: {user_prompt}"
                f"System Prompt: {system_prompt}"
            )

        return response

    get_response = sync_wrapper(async_get_response)

    def get_question_instructions(self) -> Prompt:
        """Gets the instructions for the question."""
        applicable_prompts = get_classes(
            component_type="question_instructions",
            question_type=self.question.question_type,
        )
        ## Get the question instructions and renders with the scenario & question.data
        question_prompt = applicable_prompts[0]()

        question_prompt.render(self.question.data | self.scenario)

        if question_prompt.has_variables:
            raise QuestionScenarioRenderError(
                "Question instructions still has variables"
            )
        return question_prompt

    def construct_user_prompt(self) -> Prompt:
        """Gets the user prompt for the LLM call."""
        user_prompt = self.get_question_instructions()
        if self.memory_plan is not None:
            user_prompt += self.create_memory_prompt(self.question.question_name)
        return user_prompt

    def get_prompts(self) -> Dict[str, Prompt]:
        """Gets the prompts for the LLM call."""
        system_prompt = self.construct_system_prompt()
        user_prompt = self.construct_user_prompt()
        return {"user_prompt": user_prompt, "system_prompt": system_prompt}

    class Response(UserDict):
        def __init__(self, agent, question, scenario, raw_response):
            response = question.validate_answer(raw_response)
            comment = response.get("comment", "")
            answer_code = response["answer"]
            answer = question.translate_answer_code_to_answer(answer_code, scenario)
            data = {
                "answer": answer,
                "comment": comment,
                "prompts": agent.get_prompts(),
            }
            super().__init__(data)

    async def async_answer_question(self):
        raw_response = await self.async_get_response(**self.get_prompts())
        response = self.Response(
            agent=self,
            question=self.question,
            scenario=self.scenario,
            raw_response=raw_response,
        )
        return response

    answer_question = sync_wrapper(async_answer_question)


class InvigilatorDebug(InvigilatorBase):
    async def async_answer_question(self):
        return self.question.simulate_answer(human_readable=True)


class InvigilatorHuman(InvigilatorBase):
    async def async_answer_question(self):
        answer = self.agent.answer_question_directly(self.question.question_name)
        response = {"answer": answer}
        response = self.question.validate_response(response)
        response["model"] = "human"
        response["scenario"] = self.scenario
        return response


class InvigilatorFunctional(InvigilatorBase):
    async def async_answer_question(self):
        func = self.question.answer_question_directly
        return func(scenario=self.scenario, agent_traits=self.agent.traits)
