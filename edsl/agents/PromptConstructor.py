from __future__ import annotations
from typing import Dict, Any, Optional, Set
from collections import UserList
import pdb

from jinja2 import Environment, meta

from edsl.prompts.Prompt import Prompt
from edsl.data_transfer_models import ImageInfo
from edsl.prompts.registry import get_classes as prompt_lookup
from edsl.exceptions import QuestionScenarioRenderError

from edsl.agents.prompt_helpers import PromptComponent, PromptList, PromptPlan


def get_jinja2_variables(template_str: str) -> Set[str]:
    """
    Extracts all variable names from a Jinja2 template using Jinja2's built-in parsing.

    Args:
    template_str (str): The Jinja2 template string

    Returns:
    Set[str]: A set of variable names found in the template
    """
    env = Environment()
    ast = env.parse(template_str)
    return meta.find_undeclared_variables(ast)


class PromptConstructor:
    """
    The pieces of a prompt are:
    - The agent instructions - "You are answering questions as if you were a human. Do not break character."
    - The persona prompt - "You are an agent with the following persona: {'age': 22, 'hair': 'brown', 'height': 5.5}"
    - The question instructions - "You are being asked the following question: Do you like school? The options are 0: yes 1: no Return a valid JSON formatted like this, selecting only the number of the option: {"answer": <put answer code here>, "comment": "<put explanation here>"} Only 1 option may be selected."
    - The memory prompt - "Before the question you are now answering, you already answered the following question(s): Question: Do you like school? Answer: Prior answer"

    This is mixed into the Invigilator class.
    """

    def __init__(self, invigilator):
        self.invigilator = invigilator
        self.agent = invigilator.agent
        self.question = invigilator.question
        self.scenario = invigilator.scenario
        self.survey = invigilator.survey
        self.model = invigilator.model
        self.current_answers = invigilator.current_answers
        self.memory_plan = invigilator.memory_plan
        self.prompt_plan = PromptPlan()

    @property
    def scenario_file_keys(self) -> list:
        """We need to find all the keys in the scenario that refer to FileStore objects.
        These will be used to append to the prompt a list of files that are part of the scenario.
        """
        from edsl.scenarios.FileStore import FileStore

        file_entries = []
        for key, value in self.scenario.items():
            if isinstance(value, FileStore):
                file_entries.append(key)
        return file_entries

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
        Prompt(text=\"""You are an agent with the following persona:
        {'age': 22, 'hair': 'brown', 'height': 5.5}\""")

        """
        from edsl import Agent

        if self.agent == Agent():  # if agent is empty, then return an empty prompt
            return Prompt(text="")

        return self.agent.prompt()

    def prior_answers_dict(self) -> dict:
        d = self.survey.question_names_to_questions()
        # This attaches the answer to the question
        for question, answer in self.current_answers.items():
            if question in d:
                d[question].answer = answer
            else:
                # adds a comment to the question
                if (new_question := question.split("_comment")[0]) in d:
                    d[new_question].comment = answer
        return d

    @property
    def question_file_keys(self):
        raw_question_text = self.question.question_text
        variables = get_jinja2_variables(raw_question_text)
        question_file_keys = []
        for var in variables:
            if var in self.scenario_file_keys:
                question_file_keys.append(var)
        return question_file_keys

    @property
    def question_instructions_prompt(self) -> Prompt:
        """
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> i = InvigilatorBase.example()
        >>> i.prompt_constructor.question_instructions_prompt
        Prompt(text=\"""...
        ...
        """
        # The user might have passed a custom prompt, which would be stored in _question_instructions_prompt
        if not hasattr(self, "_question_instructions_prompt"):
            # Gets the instructions for the question - this is how the question should be answered
            question_prompt = self.question.get_instructions(model=self.model.model)

            # Get the data for the question - this is a dictionary of the question data
            # e.g., {'question_text': 'Do you like school?', 'question_name': 'q0', 'question_options': ['yes', 'no']}
            question_data = self.question.data.copy()

            # check to see if the question_options is actually a string
            # This is used when the user is using the question_options as a variable from a scenario
            # if "question_options" in question_data:
            if isinstance(self.question.data.get("question_options", None), str):
                env = Environment()
                parsed_content = env.parse(self.question.data["question_options"])
                question_option_key = list(
                    meta.find_undeclared_variables(parsed_content)
                )[0]

                # look to see if the question_option_key is in the scenario
                if isinstance(
                    question_options := self.scenario.get(question_option_key), list
                ):
                    question_data["question_options"] = question_options
                    self.question.question_options = question_options

                # might be getting it from the prior answers
                if self.prior_answers_dict().get(question_option_key) is not None:
                    if isinstance(
                        question_options := self.prior_answers_dict()
                        .get(question_option_key)
                        .answer,
                        list,
                    ):
                        question_data["question_options"] = question_options
                        self.question.question_options = question_options

            replacement_dict = (
                {key: f"<see file {key}>" for key in self.scenario_file_keys}
                | question_data
                | {
                    k: v
                    for k, v in self.scenario.items()
                    if k not in self.scenario_file_keys
                }  # don't include images in the replacement dict
                | self.prior_answers_dict()
                | {"agent": self.agent}
                | {
                    "use_code": getattr(self.question, "_use_code", True),
                    "include_comment": getattr(
                        self.question, "_include_comment", False
                    ),
                }
            )

            rendered_instructions = question_prompt.render(replacement_dict)

            # is there anything left to render?
            undefined_template_variables = (
                rendered_instructions.undefined_template_variables({})
            )

            # Check if it's the name of a question in the survey
            for question_name in self.survey.question_names:
                if question_name in undefined_template_variables:
                    print(
                        "Question name found in undefined_template_variables: ",
                        question_name,
                    )

            if undefined_template_variables:
                msg = f"Question instructions still has variables: {undefined_template_variables}."
                import warnings

                warnings.warn(msg)
                # raise QuestionScenarioRenderError(
                #     f"Question instructions still has variables: {undefined_template_variables}."
                # )

            ####################################
            # Check if question has instructions - these are instructions in a Survey that can apply to multiple follow-on questions
            ####################################
            relevant_instructions = self.survey.relevant_instructions(
                self.question.question_name
            )

            if relevant_instructions != []:
                preamble_text = Prompt(
                    text="Before answer this question, you were given the following instructions: "
                )
                for instruction in relevant_instructions:
                    preamble_text += instruction.text
                rendered_instructions = preamble_text + rendered_instructions

            self._question_instructions_prompt = rendered_instructions
        return self._question_instructions_prompt

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

    def construct_system_prompt(self) -> Prompt:
        """Construct the system prompt for the LLM call."""
        import warnings

        warnings.warn(
            "This method is deprecated. Use get_prompts instead.", DeprecationWarning
        )
        return self.get_prompts()["system_prompt"]

    def construct_user_prompt(self) -> Prompt:
        """Construct the user prompt for the LLM call."""
        import warnings

        warnings.warn(
            "This method is deprecated. Use get_prompts instead.", DeprecationWarning
        )
        return self.get_prompts()["user_prompt"]

    def get_prompts(self) -> Dict[str, Prompt]:
        """Get both prompts for the LLM call.

        >>> from edsl import QuestionFreeText
        >>> from edsl.agents.InvigilatorBase import InvigilatorBase
        >>> q = QuestionFreeText(question_text="How are you today?", question_name="q_new")
        >>> i = InvigilatorBase.example(question = q)
        >>> i.get_prompts()
        {'user_prompt': ..., 'system_prompt': ...}
        """
        # breakpoint()
        prompts = self.prompt_plan.get_prompts(
            agent_instructions=self.agent_instructions_prompt,
            agent_persona=self.agent_persona_prompt,
            question_instructions=self.question_instructions_prompt,
            prior_question_memory=self.prior_question_memory_prompt,
        )
        if self.question_file_keys:
            files_list = []
            for key in self.question_file_keys:
                files_list.append(self.scenario[key])
            prompts["files_list"] = files_list
        return prompts

    def _get_scenario_with_image(self) -> Scenario:
        """This is a helper function to get a scenario with an image, for testing purposes."""
        from edsl import Scenario

        try:
            scenario = Scenario.from_image("../../static/logo.png")
        except FileNotFoundError:
            scenario = Scenario.from_image("static/logo.png")
        return scenario


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
