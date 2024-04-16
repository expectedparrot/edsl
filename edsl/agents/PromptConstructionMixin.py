from typing import Dict, Any

from edsl.prompts.Prompt import Prompt
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.prompts.registry import get_classes as prompt_lookup
from edsl.exceptions import QuestionScenarioRenderError


class PromptConstructorMixin:
    def construct_system_prompt(self) -> Prompt:
        """Construct the system prompt for the LLM call."""

        agent_instructions = self._get_agent_instructions_prompt()
        persona_prompt = self._get_persona_prompt()

        return (
            agent_instructions
            + " " * int(len(persona_prompt.text) > 0)
            + persona_prompt
        )

    def _get_persona_prompt(self) -> Prompt:
        """Get the persona prompt.

        The is the description of the agent to the LLM.

        The agent_persona is constructed when the Agent is created.
        If the agent is passed a template for "agent_trait_presentation_template" that is used to construct the persona.
        If it does not exist, the persona is looked up in the prompt registry
        """
        if not hasattr(self.agent, "agent_persona"):
            applicable_prompts = prompt_lookup(
                component_type="agent_persona",
                model=self.model.model,
            )
            persona_prompt_template = applicable_prompts[0]()
        else:
            persona_prompt_template = self.agent.agent_persona

        # TODO: This multiple passing of agent traits - not sure if it is necessary. Not harmful.
        if undefined := persona_prompt_template.undefined_template_variables(
            self.agent.traits
            | {"traits": self.agent.traits}
            | {"codebook": self.agent.codebook}
            | {"traits": self.agent.traits}
        ):
            raise QuestionScenarioRenderError(
                f"Agent persona still has variables that were not rendered: {undefined}"
            )

        persona_prompt = persona_prompt_template.render(
            self.agent.traits | {"traits": self.agent.traits},
            codebook=self.agent.codebook,
            traits=self.agent.traits,
        )

        if persona_prompt.has_variables:
            raise QuestionScenarioRenderError(
                "Agent persona still has variables that were not rendered."
            )
        return persona_prompt

    def _get_agent_instructions_prompt(self) -> Prompt:
        """Get the agent instructions prompt."""
        applicable_prompts = prompt_lookup(
            component_type="agent_instructions",
            model=self.model.model,
        )
        if len(applicable_prompts) == 0:
            raise Exception("No applicable prompts found")
        return applicable_prompts[0](text=self.agent.instruction)

    def _get_question_instructions(self) -> Prompt:
        """Get the instructions for the question."""
        # applicable_prompts = prompt_lookup(
        #    component_type="question_instructions",
        #    question_type=self.question.question_type,
        #    model=self.model.model,
        # )
        ## Get the question instructions and renders with the scenario & question.data
        # question_prompt = applicable_prompts[0]()
        question_prompt = self.question.get_instructions(model=self.model.model)

        undefined_template_variables = question_prompt.undefined_template_variables(
            self.question.data | self.scenario
        )
        if undefined_template_variables:
            print(undefined_template_variables)
            raise QuestionScenarioRenderError(
                "Question instructions still has variables."
            )

        return question_prompt.render(self.question.data | self.scenario)

    def construct_user_prompt(self) -> Prompt:
        """Construct the user prompt for the LLM call."""
        user_prompt = self._get_question_instructions()
        if self.memory_plan is not None:
            user_prompt += self.create_memory_prompt(
                self.question.question_name
            ).render(self.scenario)
        return user_prompt

    def get_prompts(self) -> Dict[str, Prompt]:
        """Get both prompts for the LLM call."""
        system_prompt = self.construct_system_prompt()
        user_prompt = self.construct_user_prompt()
        return {
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
        }


if __name__ == "__main__":
    from edsl import Model
    from edsl import Agent

    a = Agent(
        instruction="You are a happy-go lucky agent.",
        traits={"feeling": "happy", "age": "Young at heart"},
        codebook={"feeling": "Feelings right now", "age": "Age in years"},
        trait_presentation_template="",
    )
    p = PromptConstructorMixin()
    p.model = Model(Model.available()[0])
    p.agent = a
    instructions = p._get_agent_instructions_prompt()
    repr(instructions)

    persona = p._get_persona_prompt()
    repr(persona)
