from __future__ import annotations
from typing import Dict, Any, Optional, Set

from jinja2 import Environment, meta

from edsl.prompts.Prompt import Prompt
from edsl.agents.prompt_helpers import PromptPlan


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

    @property
    def scenario_file_keys(self) -> list:
        """We need to find all the keys in the scenario that refer to FileStore objects.
        These will be used to append to the prompt a list of files that are part of the scenario.
        """
        return self._find_file_keys(self.scenario)

    @staticmethod
    def _find_file_keys(scenario: "Scenario") -> list:
        """We need to find all the keys in the scenario that refer to FileStore objects.
        These will be used to append to the prompt a list of files that are part of the scenario.

        >>> from edsl import Scenario
        >>> from edsl.scenarios.FileStore import FileStore
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile() as f:
        ...     _ = f.write(b"Hello, world!")
        ...     _ = f.seek(0)
        ...     fs = FileStore(f.name)
        ...     scenario = Scenario({"fs_file": fs, 'a': 1})
        ...     from edsl.agents.PromptConstructor import PromptConstructor
        ...     PromptConstructor._find_file_keys(scenario)
        ['fs_file']
        """
        from edsl.scenarios.FileStore import FileStore

        file_entries = []
        for key, value in scenario.items():
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
        """Extracts the file keys from the question text."""
        return self._extract_file_keys_from_question_text(
            self.question.question_text, self.scenario_file_keys
        )

    @staticmethod
    def _extract_file_keys_from_question_text(
        question_text: str, scenario_file_keys: list
    ) -> list:
        """
        Extracts the file keys from a question text.

        >>> from edsl import Scenario
        >>> from edsl.scenarios.FileStore import FileStore
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile() as f:
        ...     _ = f.write(b"Hello, world!")
        ...     _ = f.seek(0)
        ...     fs = FileStore(f.name)
        ...     scenario = Scenario({"fs_file": fs, 'a': 1})
        ...     from edsl.agents.PromptConstructor import PromptConstructor
        ...     PromptConstructor._extract_file_keys_from_question_text("{{ fs_file }}", ['fs_file'])
        ['fs_file']
        """
        variables = get_jinja2_variables(question_text)
        question_file_keys = []
        for var in variables:
            if var in scenario_file_keys:
                question_file_keys.append(var)
        return question_file_keys

    def _scenario_replacements(self) -> dict[str, Any]:
        # File references dictionary
        file_refs = {key: f"<see file {key}>" for key in self.scenario_file_keys}

        # Scenario items excluding file keys
        scenario_items = {
            k: v for k, v in self.scenario.items() if k not in self.scenario_file_keys
        }
        return {**file_refs, **scenario_items}

    @staticmethod
    def _question_data_replacements(
        question: dict, question_data: dict
    ) -> dict[str, Any]:
        """Builds a dictionary of replacement values for rendering a prompt by combining multiple data sources.

        >>> from edsl import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(question_text="Do you like school?", question_name = "q0", question_options = ["yes", "no"])
        >>> PromptConstructor._question_data_replacements(q, q.data)
        {'use_code': False, 'include_comment': True, 'question_name': 'q0', 'question_text': 'Do you like school?', 'question_options': ['yes', 'no']}

        """
        question_settings = {
            "use_code": getattr(question, "_use_code", True),
            "include_comment": getattr(question, "_include_comment", False),
        }
        return {**question_settings, **question_data}

    def build_replacement_dict(self, question_data: dict) -> dict[str, Any]:
        """Builds a dictionary of replacement values for rendering a prompt by combining multiple data sources."""
        rpl = {}
        rpl["scenario"] = self._scenario_replacements()
        rpl["question"] = self._question_data_replacements(self.question, question_data)
        rpl["prior_answers"] = self.prior_answers_dict()
        rpl["agent"] = {"agent": self.agent}

        # Combine all dictionaries using dict.update() for clarity
        replacement_dict = {}
        for r in rpl.values():
            replacement_dict.update(r)

        return replacement_dict

    def _get_question_options(self, question_data: dict) -> list:
        """
        Extract and process question options from question data.
        """
        from edsl.agents.QuestionOptionProcessor import QuestionOptionProcessor

        return QuestionOptionProcessor(self).get_question_options(question_data)

    def build_question_instructions_prompt(self):
        """Buils the question instructions prompt."""

        question_prompt = Prompt(self.question.get_instructions(model=self.model.model))

        # Get the data for the question - this is a dictionary of the question data
        # e.g., {'question_text': 'Do you like school?', 'question_name': 'q0', 'question_options': ['yes', 'no']}
        question_data = self.question.data.copy()

        if (
            "question_options" in question_data
        ):  # is this a question with question options?
            question_options = self._get_question_options(question_data)
            question_data["question_options"] = question_options

        replacement_dict = self.build_replacement_dict(question_data)
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

        # Check if question has instructions - these are instructions in a Survey that can apply to multiple follow-on questions
        relevant_instructions = self.survey.relevant_instructions(
            self.question.question_name
        )

        if relevant_instructions != []:
            preamble_text = Prompt(text="")
            for instruction in relevant_instructions:
                preamble_text += instruction.text
            rendered_instructions = preamble_text + rendered_instructions

        return rendered_instructions

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
            question_instructions=Prompt(self.question_instructions_prompt),
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
