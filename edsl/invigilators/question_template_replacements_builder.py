from jinja2 import Environment, meta, TemplateSyntaxError
from typing import Any, Set, TYPE_CHECKING

from ..agents import Agent
from ..scenarios import Scenario

if TYPE_CHECKING:
    from .prompt_constructor import PromptConstructor
    from ..questions import QuestionBase


class QuestionTemplateReplacementsBuilder:

    @classmethod
    def from_prompt_constructor(cls, prompt_constructor: "PromptConstructor"):
        scenario = prompt_constructor.scenario
        question = prompt_constructor.question
        prior_answers_dict = prompt_constructor.prior_answers_dict()
        agent = prompt_constructor.agent

        return cls(scenario, question, prior_answers_dict, agent)

    def __init__(
        self,
        scenario: "Scenario",
        question: "QuestionBase",
        prior_answers_dict: dict,
        agent: "Agent",
    ):
        self.scenario = scenario
        self.question = question
        self.prior_answers_dict = prior_answers_dict
        self.agent = agent

    def question_file_keys(self):
        """
        >>> from ..questions import QuestionMultipleChoice
        >>> from ..scenarios import Scenario
        >>> q = QuestionMultipleChoice(question_text="Do you like school?", question_name = "q0", question_options = ["yes", "no"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = {"file1": "file1"}, question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> qtrb.question_file_keys()
        []
        >>> from ..scenarios import FileStore
        >>> fs = FileStore.example()
        >>> # Test direct key reference
        >>> q = QuestionMultipleChoice(question_text="What do you think of this file: {{ file1 }}", question_name = "q0", question_options = ["good", "bad"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = Scenario({"file1": fs}), question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> qtrb.question_file_keys()
        ['file1']
        >>> # Test scenario.key reference
        >>> q = QuestionMultipleChoice(question_text="What do you think of this file: {{ scenario.file2 }}", question_name = "q0", question_options = ["good", "bad"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = Scenario({"file2": fs}), question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> qtrb.question_file_keys()
        ['file2']
        >>> # Test both formats in the same question
        >>> q = QuestionMultipleChoice(question_text="Compare {{ file1 }} with {{ scenario.file2 }}", question_name = "q0", question_options = ["good", "bad"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = Scenario({"file1": fs, "file2": fs}), question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> sorted(qtrb.question_file_keys())
        ['file1', 'file2']
        """
        question_text = self.question.question_text
        file_keys = self._find_file_keys(self.scenario)
        return self._extract_file_keys_from_question_text(question_text, file_keys)

    def scenario_file_keys(self):
        return self._find_file_keys(self.scenario)

    def get_jinja2_variables(template_str: str) -> Set[str]:
        """
        Extracts all variable names from a Jinja2 template using Jinja2's built-in parsing.

        Args:
        template_str (str): The Jinja2 template string

        Returns:
        Set[str]: A set of variable names found in the template
        """
        env = Environment()
        try:
            ast = env.parse(template_str)
        except TemplateSyntaxError:
            print(f"Error parsing template: {template_str}")
            raise

        return meta.find_undeclared_variables(ast)

    @staticmethod
    def _find_file_keys(scenario: "Scenario") -> list:
        """We need to find all the keys in the scenario that refer to FileStore objects.
        These will be used to append to the prompt a list of files that are part of the scenario.

        >>> from ..scenarios import Scenario
        >>> from ..scenarios import FileStore
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile() as f:
        ...     _ = f.write(b"Hello, world!")
        ...     _ = f.seek(0)
        ...     fs = FileStore(f.name)
        ...     scenario = Scenario({"fs_file": fs, 'a': 1})
        ...     QuestionTemplateReplacementsBuilder._find_file_keys(scenario)
        ['fs_file']
        """
        from ..scenarios import FileStore

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
        Extracts the file keys from a question text, handling both direct references ({{ file_key }})
        and scenario-prefixed references ({{ scenario.file_key }}).

        >>> from edsl import Scenario
        >>> from edsl.scenarios import FileStore
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile() as f:
        ...     _ = f.write(b"Hello, world!")
        ...     _ = f.seek(0)
        ...     fs = FileStore(f.name)
        ...     scenario = Scenario({"fs_file": fs, 'a': 1})
        ...     QuestionTemplateReplacementsBuilder._extract_file_keys_from_question_text("{{ fs_file }}", ['fs_file'])
        ['fs_file']
        >>> with tempfile.NamedTemporaryFile() as f:
        ...     _ = f.write(b"Hello, world!")
        ...     _ = f.seek(0)
        ...     fs = FileStore(f.name)
        ...     scenario = Scenario({"print": fs, 'a': 1})
        ...     QuestionTemplateReplacementsBuilder._extract_file_keys_from_question_text("{{ scenario.print }}", ['print'])
        ['print']
        >>> with tempfile.NamedTemporaryFile() as f:
        ...     _ = f.write(b"Hello, world!")
        ...     _ = f.seek(0)
        ...     fs = FileStore(f.name)
        ...     scenario = Scenario({"file1": fs, "file2": fs})
        ...     sorted(QuestionTemplateReplacementsBuilder._extract_file_keys_from_question_text("Compare {{ file1 }} with {{ scenario.file2 }}", ['file1', 'file2']))
        ['file1', 'file2']
        """
        variables = QuestionTemplateReplacementsBuilder.get_jinja2_variables(
            question_text
        )
        question_file_keys = []
        
        # Direct references: {{ file_key }}
        for var in variables:
            if var in scenario_file_keys:
                question_file_keys.append(var)
                
        # Scenario-prefixed references: {{ scenario.file_key }}
        for var in variables:
            if var == "scenario":
                # If we find a scenario variable, we need to check for nested references
                # Create a modified template with just {{ scenario.* }} expressions to isolate them
                # Using a template format for reference, not actually used
                _ = "".join([
                    "{% for key, value in scenario.items() %}{{ key }}{% endfor %}"
                ])
                try:
                    # This is a check to make sure there's scenario.something syntax in the template
                    if "scenario." in question_text:
                        # Extract dot-notation scenario references by parsing the template
                        import re
                        scenario_refs = re.findall(r'{{\s*scenario\.(\w+)\s*}}', question_text)
                        for key in scenario_refs:
                            if key in scenario_file_keys:
                                question_file_keys.append(key)
                except Exception:
                    # If there's any issue parsing, just continue with what we have
                    pass
                
        return list(set(question_file_keys))  # Remove duplicates

    def _scenario_replacements(
        self, replacement_string: str = "<see file {key}>"
    ) -> dict[str, Any]:
        """
        >>> from edsl import Scenario
        >>> from edsl import QuestionFreeText; 
        >>> q = QuestionFreeText(question_text = "How are you {{ scenario.friend }}?", question_name = "test")
        >>> s = Scenario({'friend':'john'}) 
        >>> q.by(s).prompts().select('user_prompt')
        Dataset([{'user_prompt': [Prompt(text=\"""How are you john?\""")]}])
        """
        # File references dictionary
        file_refs = {
            key: replacement_string.format(key=key) for key in self.scenario_file_keys()
        }

        # Scenario items excluding file keys
        scenario_items = {
            k: v for k, v in self.scenario.items() if k not in self.scenario_file_keys()
        }
        scenario_items_with_prefix = {'scenario': scenario_items}
        
        return {**file_refs, **scenario_items, **scenario_items_with_prefix}

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
        """Builds a dictionary of replacement values for rendering a prompt by combining multiple data sources.


        >>> from edsl import QuestionMultipleChoice, Scenario
        >>> q = QuestionMultipleChoice(question_text="Do you like school?", question_name = "q0", question_options = ["yes", "no"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = {"file1": "file1"}, question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> qtrb.question_file_keys()
        []
        >>> from edsl import FileStore
        >>> fs = FileStore.example()
        >>> s = Scenario({"file1": fs, "first_name": "John"})
        >>> q = QuestionMultipleChoice(question_text="What do you think of this file: {{ file1 }}, {{ first_name}}", question_name = "q0", question_options = ["good", "bad"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = s, question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> qtrb.build_replacement_dict(q.data)
        {'file1': '<see file file1>', 'first_name': 'John', 'scenario': {'first_name': 'John'}, 'use_code': False, 'include_comment': True, 'question_name': 'q0', 'question_text': 'What do you think of this file: {{ file1 }}, {{ first_name}}', 'question_options': ['good', 'bad'], 'q0': 'q0', 'agent': 'agent'}


        """
        rpl = {}
        rpl["scenario"] = self._scenario_replacements()
        rpl["question"] = self._question_data_replacements(self.question, question_data)
        # rpl["prior_answers"] = self.prompt_constructor.prior_answers_dict()
        rpl["prior_answers"] = self.prior_answers_dict
        # rpl["agent"] = {"agent": self.prompt_constructor.agent}
        rpl["agent"] = {"agent": self.agent}

        # Combine all dictionaries using dict.update() for clarity
        replacement_dict = {}
        for r in rpl.values():
            replacement_dict.update(r)

        return replacement_dict


if __name__ == "__main__":
    import doctest

    doctest.testmod()
