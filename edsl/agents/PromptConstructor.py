from __future__ import annotations
from typing import Dict, Any, Optional, Set, Union


from edsl.prompts.Prompt import Prompt
from edsl.agents.prompt_helpers import PromptPlan

from edsl.agents.QuestionTemplateReplacementsBuilder import (
    QuestionTemplateReplacementsBuilder,
)
from edsl.agents.QuestionOptionProcessor import QuestionOptionProcessor


class PlaceholderAnswer:
    """A placeholder answer for when a question is not yet answered."""

    def __init__(self):
        self.answer = "N/A"
        self.comment = "Will be populated by prior answer"

    def __getitem__(self, index):
        return ""

    def __str__(self):
        return "<<PlaceholderAnswer>>"

    def __repr__(self):
        return "<<PlaceholderAnswer>>"


class PromptConstructor:
    """
    This class constructs the prompts for the language model.

    The pieces of a prompt are:
    - The agent instructions - "You are answering questions as if you were a human. Do not break character."
    - The persona prompt - "You are an agent with the following persona: {'age': 22, 'hair': 'brown', 'height': 5.5}"
    - The question instructions - "You are being asked the following question: Do you like school? The options are 0: yes 1: no Return a valid JSON formatted like this, selecting only the number of the option: {"answer": <put answer code here>, "comment": "<put explanation here>"} Only 1 option may be selected."
    - The memory prompt - "Before the question you are now answering, you already answered the following question(s): Question: Do you like school? Answer: Prior answer"
    """

    def __init__(self, invigilator, prompt_plan: Optional["PromptPlan"] = None):
        self.invigilator = invigilator
        self.agent = invigilator.agent
        self.question = invigilator.question
        self.scenario = invigilator.scenario
        self.survey = invigilator.survey
        self.model = invigilator.model
        self.current_answers = invigilator.current_answers
        self.memory_plan = invigilator.memory_plan
        self.prompt_plan = prompt_plan or PromptPlan()

    def get_question_options(self, question_data):
        """Get the question options."""
        return QuestionOptionProcessor(self).get_question_options(question_data)

    @property
    def agent_instructions_prompt(self) -> Prompt:
        """
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i.prompt_constructor.agent_instructions_prompt
        Prompt(text=\"""You are answering questions as if you were a human. Do not break character.\""")
        """
        from edsl import Agent

        if self.agent == Agent():  # if agent is empty, then return an empty prompt
            return Prompt(text="")

        return Prompt(text=self.agent.instruction)

    @property
    def agent_persona_prompt(self) -> Prompt:
        """
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i.prompt_constructor.agent_persona_prompt
        Prompt(text=\"""Your traits: {'age': 22, 'hair': 'brown', 'height': 5.5}\""")
        """
        from edsl import Agent

        if self.agent == Agent():  # if agent is empty, then return an empty prompt
            return Prompt(text="")

        return self.agent.prompt()

    def prior_answers_dict(self) -> dict[str, "QuestionBase"]:
        """This is a dictionary of prior answers, if they exist."""
        return self._add_answers(
            self.survey.question_names_to_questions(), self.current_answers
        )

    @staticmethod
    def _add_answers(answer_dict: dict, current_answers) -> dict[str, "QuestionBase"]:
        """
        >>> from edsl import QuestionFreeText
        >>> d = {"q0": QuestionFreeText(question_text="Do you like school?", question_name = "q0")}
        >>> current_answers = {"q0": "LOVE IT!"}
        >>> PromptConstructor._add_answers(d, current_answers)['q0'].answer
        'LOVE IT!'
        """
        for question in answer_dict:
            if question in current_answers:
                answer_dict[question].answer = current_answers[question]
            else:
                answer_dict[question].answer = PlaceholderAnswer()
        return answer_dict

    @property
    def question_file_keys(self) -> list:
        """Extracts the file keys from the question text.
        It checks if the variables in the question text are in the scenario file keys.
        """
        return QuestionTemplateReplacementsBuilder(self).question_file_keys()

    @property
    def question_instructions_prompt(self) -> Prompt:
        """
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i.prompt_constructor.question_instructions_prompt
        Prompt(text=\"""...
        ...
        """
        if not hasattr(self, "_question_instructions_prompt"):
            self._question_instructions_prompt = (
                self.build_question_instructions_prompt()
            )

        return self._question_instructions_prompt

    def build_question_instructions_prompt(self) -> Prompt:
        """Buils the question instructions prompt."""
        from edsl.agents.QuestionInstructionPromptBuilder import (
            QuestionInstructionPromptBuilder,
        )

        return QuestionInstructionPromptBuilder(self).build()

    @property
    def prior_question_memory_prompt(self) -> Prompt:
        if not hasattr(self, "_prior_question_memory_prompt"):
            from edsl.prompts.Prompt import Prompt

            memory_prompt = Prompt(text="")
            if self.memory_plan is not None:
                memory_prompt += self.create_memory_prompt(
                    self.question.question_name
                ).render(self.scenario | self.prior_answers_dict())
            self._prior_question_memory_prompt = memory_prompt
        return self._prior_question_memory_prompt

    def create_memory_prompt(self, question_name: str) -> Prompt:
        """Create a memory for the agent.

        The returns a memory prompt for the agent.

        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i.current_answers = {"q0": "Prior answer"}
        >>> i.memory_plan.add_single_memory("q1", "q0")
        >>> p = i.prompt_constructor.create_memory_prompt("q1")
        >>> p.text.strip().replace("\\n", " ").replace("\\t", " ")
        'Before the question you are now answering, you already answered the following question(s):          Question: Do you like school?  Answer: Prior answer'
        """
        return self.memory_plan.get_memory_prompt_fragment(
            question_name, self.current_answers
        )

    def get_prompts(self) -> Dict[str, Prompt]:
        """Get both prompts for the LLM call.

        >>> from edsl import QuestionFreeText
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> q = QuestionFreeText(question_text="How are you today?", question_name="q_new")
        >>> i = InvigilatorBase.example(question = q)
        >>> i.get_prompts()
        {'user_prompt': ..., 'system_prompt': ...}
        """
        prompts = self.prompt_plan.get_prompts(
            agent_instructions=self.agent_instructions_prompt,
            agent_persona=self.agent_persona_prompt,
            question_instructions=Prompt(self.question_instructions_prompt),
            prior_question_memory=self.prior_question_memory_prompt,
        )
        if self.question_file_keys:
            files_list = []
            for key in self.question_file_keys:
                files_list.append(self.scenario[key])
            prompts["files_list"] = files_list
        return prompts

    # def _get_scenario_with_image(self) -> Scenario:
    #     """This is a helper function to get a scenario with an image, for testing purposes."""
    #     from edsl import Scenario

    #     try:
    #         scenario = Scenario.from_image("../../static/logo.png")
    #     except FileNotFoundError:
    #         scenario = Scenario.from_image("static/logo.png")
    #     return scenario


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
