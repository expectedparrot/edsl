from abc import ABC, abstractmethod
import asyncio
import json
from edsl.exceptions import AgentRespondedWithBadJSONError
from edsl.prompts.Prompt import Prompt

from edsl.utilities.decorators import sync_wrapper


class InvigilatorBase(ABC):
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

    def answer_question(self):
        """Blocking code to answer a question."""

        async def main():
            results = await asyncio.gather(self.async_answer_question())
            return results[0]  # Since there's only one task, return its result

        return asyncio.run(main())

    def create_memory_prompt(self, question_name):
        """Creates a memory for the agent."""
        return self.memory_plan.get_memory_prompt_fragment(
            question_name, self.current_answers
        )


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


class InvigilatorAI(InvigilatorBase):
    def construct_system_prompt(self) -> str:
        """Constructs the system prompt for the LLM call."""
        instruction = self.agent.instruction
        traits = f"Your traits are: {self.agent.traits}."
        return f"{instruction} {traits}"

    async def async_get_response(self, prompt: str, system_prompt):
        """Calls the LLM and gets a response. Used in the `answer_question` method."""
        try:
            response = await self.model.async_get_response(prompt, system_prompt)
        except json.JSONDecodeError as e:
            raise AgentRespondedWithBadJSONError(
                f"Returned bad JSON: {e}"
                f"Prompt: {prompt}"
                f"System Prompt: {system_prompt}"
            )

        return response

    get_response = sync_wrapper(async_get_response)

    async def async_answer_question(self):
        system_prompt = Prompt(self.construct_system_prompt())
        prompt = Prompt(self.question.get_prompt(self.scenario))
        if self.memory_plan is not None:
            prompt += self.create_memory_prompt(self.question.question_name)
        response = await self.async_get_response(prompt.text, system_prompt.text)
        response = self.question.validate_answer(response)
        answer_code = response["answer"]
        response["answer"] = self.question.translate_answer_code_to_answer(
            answer_code, self.scenario
        )
        return response

    answer_question = sync_wrapper(async_answer_question)
