import re
from typing import Any, Set, TYPE_CHECKING

from jinja2 import Environment, meta, TemplateSyntaxError

# Module-level cache for compiled templates and scenario file keys
_template_variables_cache = {}
_scenario_file_keys_cache = {}
_file_keys_extraction_cache = {}

if TYPE_CHECKING:
    from .prompt_constructor import PromptConstructor
    from ..questions import QuestionBase
    from ..agents import Agent
    from ..scenarios import Scenario


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

    def question_file_keys(self) -> list:
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
        >>> result = qtrb.question_file_keys()
        >>> set(result) == {'file1', 'file2'}  # Order may vary due to caching
        True
        """
        # Add caching to avoid repeated template parsing for same question text
        if not hasattr(self, "_cached_question_file_keys"):
            question_text = self.question.question_text
            file_keys = self._find_file_keys(self.scenario)
            result = self._extract_file_keys_from_question_text(
                question_text, file_keys
            )
            self._cached_question_file_keys = result

        return self._cached_question_file_keys

    def scenario_file_keys(self) -> list:
        # Add caching to avoid repeated file key detection for same scenario
        if not hasattr(self, "_cached_scenario_file_keys"):
            result = self._find_file_keys(self.scenario)
            self._cached_scenario_file_keys = result

        return self._cached_scenario_file_keys

    @staticmethod
    def get_jinja2_variables(template_str: str) -> Set[str]:
        """
        Extracts all variable names from a Jinja2 template using Jinja2's built-in parsing.
        Uses module-level caching to avoid re-parsing identical templates.

        Args:
        template_str (str): The Jinja2 template string

        Returns:
        Set[str]: A set of variable names found in the template
        """
        # Check cache first
        if template_str in _template_variables_cache:
            return _template_variables_cache[template_str]

        # Parse template for the first time
        env = Environment()
        try:
            ast = env.parse(template_str)
        except TemplateSyntaxError:
            print(f"Error parsing template: {template_str}")
            raise

        result = meta.find_undeclared_variables(ast)

        # Cache the result
        _template_variables_cache[template_str] = result

        return result

    @staticmethod
    def _find_file_keys(scenario: "Scenario") -> list:
        """We need to find all the keys in the scenario that refer to FileStore objects.
        These will be used to append to the prompt a list of files that are part of the scenario.
        Uses module-level caching with a robust cache key to avoid re-scanning large scenarios.

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

        # Create a robust cache key using (id, key, value_id, value_type) for each item
        # This prevents cache collisions while still allowing caching of the same scenario object
        try:
            # Use id() of the scenario object itself along with a hash of its structure
            # This way, the same scenario object reuses cache, but different objects don't collide
            cache_key = (
                id(scenario),
                tuple(
                    sorted((k, id(v), type(v).__name__) for k, v in scenario.items())
                ),
            )
        except Exception:
            # If we can't create a cache key, don't cache
            cache_key = None

        # Check cache first
        if cache_key and cache_key in _scenario_file_keys_cache:
            return _scenario_file_keys_cache[cache_key]

        # Find file keys for the first time
        result = [
            key for key, value in scenario.items() if isinstance(value, FileStore)
        ]

        # Cache the result
        if cache_key:
            _scenario_file_keys_cache[cache_key] = result

        return result

    @staticmethod
    def _extract_file_keys_from_question_text(
        question_text: str, scenario_file_keys: list
    ) -> list:
        """
        Extracts the file keys from a question text, handling both direct references ({{ file_key }})
        and scenario-prefixed references ({{ scenario.file_key }}).
        Uses module-level caching for identical question text and scenario combinations.

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
        # Create cache key from question text and scenario file keys
        cache_key = (question_text, tuple(sorted(scenario_file_keys)))

        # Check cache first
        if cache_key in _file_keys_extraction_cache:
            return _file_keys_extraction_cache[cache_key]

        # Extract file keys for the first time

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
                _ = "".join(
                    ["{% for key, value in scenario.items() %}{{ key }}{% endfor %}"]
                )
                try:
                    # This is a check to make sure there's scenario.something syntax in the template
                    if "scenario." in question_text:
                        # Extract dot-notation scenario references by parsing the template
                        scenario_refs = re.findall(
                            r"{{\s*scenario\.(\w+)\s*}}", question_text
                        )
                        for key in scenario_refs:
                            if key in scenario_file_keys:
                                question_file_keys.append(key)
                except Exception:
                    # If there's any issue parsing, just continue with what we have
                    pass

        # Remove duplicates while preserving order
        seen = set()
        result = []
        for key in question_file_keys:
            if key not in seen:
                seen.add(key)
                result.append(key)

        # Cache the result
        _file_keys_extraction_cache[cache_key] = result

        return result

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
        # OPTIMIZATION: Only process files that are actually referenced in the question
        referenced_file_keys = self.question_file_keys()  # Only files used in question

        # File references dictionary - ONLY for referenced files
        file_refs = {
            key: replacement_string.format(key=key) for key in referenced_file_keys
        }

        # Get all scenario file keys for exclusion (cached call)
        all_file_keys = set(self.scenario_file_keys())  # Convert to set for O(1) lookup

        # OPTIMIZATION: Only include scenario variables that are actually referenced in the template

        # Get variables actually used in the question template
        question_text = getattr(self.question, "question_text", "")
        template_vars = self.get_jinja2_variables(question_text)

        # Extract scenario variables (those that start with 'scenario.')
        referenced_scenario_vars = set()
        for var in template_vars:
            if var.startswith("scenario."):
                # Extract the variable name after 'scenario.'
                scenario_var = var[9:]  # Remove 'scenario.' prefix
                referenced_scenario_vars.add(scenario_var)

        # Only include scenario items that are actually referenced AND not file keys
        scenario_items = {
            k: v
            for k, v in self.scenario.items()
            if k not in all_file_keys
            and (not referenced_scenario_vars or k in referenced_scenario_vars)
        }
        
        # Add an "all" key that contains all scenario key-value pairs as a string
        all_scenario_items = {
            k: v
            for k, v in self.scenario.items()
            if k not in all_file_keys
        }
        all_items_string = ", ".join(f"{k}: {v}" for k, v in all_scenario_items.items())
        scenario_items_with_all = {**scenario_items, "all": all_items_string}
        
        scenario_items_with_prefix = {"scenario": scenario_items_with_all}

        result = {**file_refs, **scenario_items, **scenario_items_with_prefix}

        return result

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
        >>> result = qtrb.build_replacement_dict(q.data)
        >>> result['file1']  # doctest: +ELLIPSIS
        '<see file file1>'


        """
        rpl = {}

        rpl["scenario"] = self._scenario_replacements()
        rpl["question"] = self._question_data_replacements(self.question, question_data)
        rpl["prior_answers"] = self.prior_answers_dict
        rpl["agent"] = {"agent": self.agent}

        # Combine all dictionaries using dict.update() for clarity
        replacement_dict = {}
        for r in rpl.values():
            replacement_dict.update(r)

        return replacement_dict


if __name__ == "__main__":
    import doctest

    doctest.testmod()
