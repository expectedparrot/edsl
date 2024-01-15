from abc import ABC, abstractmethod
import asyncio
import json
from typing import Coroutine, Dict, Any
from edsl.exceptions import AgentRespondedWithBadJSONError
from edsl.prompts.Prompt import Prompt

from jinja2 import Template, Environment, meta

from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler

from collections import UserDict

from edsl.prompts.Prompt import get_classes
from edsl.exceptions import QuestionScenarioRenderError


# ############################
# # LLM methods
# ############################
def render(text: str, replacements: dict[str, Any]) -> str:
    """
    Replaces the variables in the question text with the values from the scenario.
    - We allow nesting, and hence we may need to do this many times. There is a nesting limit of 100.
    """
    t = text
    MAX_NESTING = 100
    counter = 0
    while True:
        counter += 1
        new_t = Template(t).render(replacements)
        if new_t == t:
            break
        t = new_t
        if counter > MAX_NESTING:
            raise QuestionScenarioRenderError(
                "Too much nesting - you created an infnite loop here, pal"
            )

    return new_t


# def get_prompt(self, scenario=None) -> Prompt:
#     """Shows which prompt should be used with the LLM for this question.
#     It extracts the question attributes from the instantiated question data model.
#     """
#     scenario = scenario or {}
#     template = Template(self.instructions)
#     template_with_attributes = template.render(self.data)
# env = Environment()
# ast = env.parse(template_with_attributes)
# undeclared_variables = meta.find_undeclared_variables(ast)
# if any([v not in scenario for v in undeclared_variables]):
#     raise QuestionScenarioRenderError(
#         f"Scenario is missing variables: {undeclared_variables}"
#     )
#     prompt = self.scenario_render(template_with_attributes, scenario)
#     return Prompt(prompt)


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


################################
### This is the one that matters
############################


class InvigilatorAI(InvigilatorBase):
    def construct_system_prompt(self) -> str:
        """Constructs the system prompt for the LLM call."""
        instruction = self.agent.instruction
        traits = f"Your traits are: {self.agent.traits}."
        return f"{instruction} {traits}"

    async def async_get_response(self, user_prompt: Prompt, system_prompt: Prompt):
        """Calls the LLM and gets a response. Used in the `answer_question` method."""
        try:
            response = await self.model.async_get_response(
                user_prompt.text, system_prompt.text
            )
        except json.JSONDecodeError as e:
            raise AgentRespondedWithBadJSONError(
                f"Returned bad JSON: {e}"
                f"Prompt: {prompt}"
                f"System Prompt: {system_prompt}"
            )

        return response

    get_response = sync_wrapper(async_get_response)

    def get_question_instructions(self):
        """Gets the instructions for the question."""
        applicable_prompts = get_classes(
            component_type="question_instructions",
            question_type=self.question.question_type,
        )
        ## Get the question instructions
        template = applicable_prompts[0]().text
        ## Populate with the question data
        template_with_attributes = Template(template).render(self.question.data)

        env = Environment()
        ast = env.parse(template_with_attributes)
        undeclared_variables = meta.find_undeclared_variables(ast)
        if any([v not in self.scenario for v in undeclared_variables]):
            raise QuestionScenarioRenderError(
                f"Scenario is missing variables: {undeclared_variables}"
            )
        ## File in the scenario data
        txt = render(template_with_attributes, self.scenario)
        return txt

    def get_prompts(self) -> Dict[str, Prompt]:
        """Gets the prompts for the LLM call."""
        system_prompt = Prompt(self.construct_system_prompt())
        user_prompt = Prompt(self.get_question_instructions())
        # breakpoint()
        # user_prompt = Prompt(self.question.get_prompt(self.scenario))
        if self.memory_plan is not None:
            user_prompt += self.create_memory_prompt(self.question.question_name)
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
