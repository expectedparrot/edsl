from jinja2 import Environment, meta
from typing import Any, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.agents.PromptConstructor import PromptConstructor
    from edsl.scenarios.Scenario import Scenario


class QuestionTemplateReplacementsBuilder:
    def __init__(self, prompt_constructor: "PromptConstructor"):
        self.prompt_constructor = prompt_constructor

    def question_file_keys(self):
        question_text = self.prompt_constructor.question.question_text
        file_keys = self._find_file_keys(self.prompt_constructor.scenario)
        return self._extract_file_keys_from_question_text(question_text, file_keys)

    def scenario_file_keys(self):
        return self._find_file_keys(self.prompt_constructor.scenario)

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
        ...     QuestionTemplateReplacementsBuilder._find_file_keys(scenario)
        ['fs_file']
        """
        from edsl.scenarios.FileStore import FileStore

        file_entries = []
        for key, value in scenario.items():
            if isinstance(value, FileStore):
                file_entries.append(key)
        return file_entries

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
        ...     QuestionTemplateReplacementsBuilder._extract_file_keys_from_question_text("{{ fs_file }}", ['fs_file'])
        ['fs_file']
        """
        variables = QuestionTemplateReplacementsBuilder.get_jinja2_variables(
            question_text
        )
        question_file_keys = []
        for var in variables:
            if var in scenario_file_keys:
                question_file_keys.append(var)
        return question_file_keys

    def _scenario_replacements(self) -> dict[str, Any]:
        # File references dictionary
        file_refs = {key: f"<see file {key}>" for key in self.scenario_file_keys()}

        # Scenario items excluding file keys
        scenario_items = {
            k: v
            for k, v in self.prompt_constructor.scenario.items()
            if k not in self.scenario_file_keys()
        }
        return {**file_refs, **scenario_items}

    @staticmethod
    def _question_data_replacements(
        question: dict, question_data: dict
    ) -> dict[str, Any]:
        """Builds a dictionary of replacement values for rendering a prompt by combining multiple data sources.

        >>> from edsl import QuestionMultipleChoice
        >>> q = QuestionMultipleChoice(question_text="Do you like school?", question_name = "q0", question_options = ["yes", "no"])
        >>> QuestionTemplateReplacementsBuilder._question_data_replacements(q, q.data)
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
        rpl["question"] = self._question_data_replacements(
            self.prompt_constructor.question, question_data
        )
        rpl["prior_answers"] = self.prompt_constructor.prior_answers_dict()
        rpl["agent"] = {"agent": self.prompt_constructor.agent}

        # Combine all dictionaries using dict.update() for clarity
        replacement_dict = {}
        for r in rpl.values():
            replacement_dict.update(r)

        return replacement_dict


if __name__ == "__main__":
    import doctest

    doctest.testmod()
