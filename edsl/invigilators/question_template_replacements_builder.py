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
        >>> sorted(qtrb.question_file_keys())
        ['file1', 'file2']
        """
        # Add caching to avoid repeated template parsing for same question text
        if not hasattr(self, "_cached_question_file_keys"):
            import time

            start_time = time.time()
            print(f"DEBUG - question_file_keys: parsing template for first time")

            question_text = self.question.question_text
            file_keys = self._find_file_keys(self.scenario)
            result = self._extract_file_keys_from_question_text(
                question_text, file_keys
            )

            self._cached_question_file_keys = result
            parse_time = time.time() - start_time
            print(
                f"DEBUG - question_file_keys: template parsing took {parse_time:.4f}s, found {len(result)} keys"
            )
        else:
            print(f"DEBUG - question_file_keys: using cached result")

        return self._cached_question_file_keys

    def scenario_file_keys(self) -> list:
        # Add caching to avoid repeated file key detection for same scenario
        if not hasattr(self, "_cached_scenario_file_keys"):
            import time

            start_time = time.time()
            print(f"DEBUG - scenario_file_keys: finding file keys for first time")

            result = self._find_file_keys(self.scenario)
            self._cached_scenario_file_keys = result

            find_time = time.time() - start_time
            print(
                f"DEBUG - scenario_file_keys: finding {len(result)} file keys took {find_time:.4f}s"
            )
        else:
            print(
                f"DEBUG - scenario_file_keys: using cached result with {len(self._cached_scenario_file_keys)} keys"
            )

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
        import time

        # Check cache first
        if template_str in _template_variables_cache:
            print(f"DEBUG - get_jinja2_variables: using cached result for template")
            return _template_variables_cache[template_str]

        # Parse template for the first time
        start_time = time.time()
        print(f"DEBUG - get_jinja2_variables: parsing template for first time")

        env = Environment()
        try:
            ast = env.parse(template_str)
        except TemplateSyntaxError:
            print(f"Error parsing template: {template_str}")
            raise

        result = meta.find_undeclared_variables(ast)

        # Cache the result
        _template_variables_cache[template_str] = result

        parse_time = time.time() - start_time
        print(
            f"DEBUG - get_jinja2_variables: template parsing took {parse_time:.4f}s, found {len(result)} variables"
        )

        return result

    @staticmethod
    def _find_file_keys(scenario: "Scenario") -> list:
        """We need to find all the keys in the scenario that refer to FileStore objects.
        These will be used to append to the prompt a list of files that are part of the scenario.
        Uses module-level caching to avoid re-scanning large scenarios.

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
        import time

        # Create a cache key based on scenario content
        # Using id() is fast but only works within same process
        scenario_id = id(scenario)

        # Check cache first
        if scenario_id in _scenario_file_keys_cache:
            print(f"DEBUG - _find_file_keys: using cached result for scenario")
            return _scenario_file_keys_cache[scenario_id]

        # Find file keys for the first time
        start_time = time.time()
        print(f"DEBUG - _find_file_keys: scanning scenario for FileStore objects")

        from ..scenarios import FileStore

        result = [
            key for key, value in scenario.items() if isinstance(value, FileStore)
        ]

        # Cache the result
        _scenario_file_keys_cache[scenario_id] = result

        scan_time = time.time() - start_time
        print(
            f"DEBUG - _find_file_keys: scenario scanning took {scan_time:.4f}s, found {len(result)} file keys"
        )

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
        import time

        # Create cache key from question text and scenario file keys
        cache_key = (question_text, tuple(sorted(scenario_file_keys)))

        # Check cache first
        if cache_key in _file_keys_extraction_cache:
            print(f"DEBUG - _extract_file_keys_from_question_text: using cached result")
            return _file_keys_extraction_cache[cache_key]

        # Extract file keys for the first time
        start_time = time.time()
        print(
            f"DEBUG - _extract_file_keys_from_question_text: extracting file keys for first time"
        )

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

        result = list(set(question_file_keys))  # Remove duplicates

        # Cache the result
        _file_keys_extraction_cache[cache_key] = result

        extract_time = time.time() - start_time
        print(
            f"DEBUG - _extract_file_keys_from_question_text: extraction took {extract_time:.4f}s, found {len(result)} file keys"
        )

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
        import time

        start_time = time.time()
        print(f"DEBUG - _scenario_replacements called")

        # OPTIMIZATION: Only process files that are actually referenced in the question
        referenced_file_keys_start = time.time()
        referenced_file_keys = self.question_file_keys()  # Only files used in question
        referenced_file_keys_time = time.time() - referenced_file_keys_start

        # File references dictionary - ONLY for referenced files
        file_refs_start = time.time()
        file_refs = {
            key: replacement_string.format(key=key) for key in referenced_file_keys
        }
        file_refs_time = time.time() - file_refs_start

        # Get all scenario file keys for exclusion (cached call)
        all_file_keys_start = time.time()
        all_file_keys = self.scenario_file_keys()
        all_file_keys_time = time.time() - all_file_keys_start

        # Scenario items excluding file keys
        scenario_items_start = time.time()
        scenario_items = {
            k: v for k, v in self.scenario.items() if k not in all_file_keys
        }
        scenario_items_with_prefix = {"scenario": scenario_items}
        scenario_items_time = time.time() - scenario_items_start

        result = {**file_refs, **scenario_items, **scenario_items_with_prefix}

        total_time = time.time() - start_time
        print(
            f"DEBUG - _scenario_replacements: referenced_files={referenced_file_keys_time:.4f}s, "
            f"file_refs={file_refs_time:.4f}s, all_files={all_file_keys_time:.4f}s, "
            f"scenario_items={scenario_items_time:.4f}s, total={total_time:.4f}s"
        )
        print(
            f"DEBUG - _scenario_replacements: processing {len(referenced_file_keys)} referenced files instead of {len(all_file_keys)} total files"
        )

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
        >>> qtrb.build_replacement_dict(q.data)
        {'file1': '<see file file1>', 'first_name': 'John', 'scenario': {'first_name': 'John'}, 'use_code': False, 'include_comment': True, 'question_name': 'q0', 'question_text': 'What do you think of this file: {{ file1 }}, {{ first_name}}', 'question_options': ['good', 'bad'], 'q0': 'q0', 'agent': 'agent'}


        """
        import time

        start_time = time.time()

        rpl = {}

        scenario_start = time.time()
        rpl["scenario"] = self._scenario_replacements()
        scenario_time = time.time() - scenario_start

        question_start = time.time()
        rpl["question"] = self._question_data_replacements(self.question, question_data)
        question_time = time.time() - question_start

        prior_start = time.time()
        rpl["prior_answers"] = self.prior_answers_dict
        prior_time = time.time() - prior_start

        agent_start = time.time()
        rpl["agent"] = {"agent": self.agent}
        agent_time = time.time() - agent_start

        # Combine all dictionaries using dict.update() for clarity
        combine_start = time.time()
        replacement_dict = {}
        for r in rpl.values():
            replacement_dict.update(r)
        combine_time = time.time() - combine_start

        total_time = time.time() - start_time
        print(
            f"DEBUG - build_replacement_dict: scenario={scenario_time:.4f}s, question={question_time:.4f}s, prior={prior_time:.4f}s, agent={agent_time:.4f}s, combine={combine_time:.4f}s, total={total_time:.4f}s"
        )

        return replacement_dict


if __name__ == "__main__":
    import doctest

    doctest.testmod()
