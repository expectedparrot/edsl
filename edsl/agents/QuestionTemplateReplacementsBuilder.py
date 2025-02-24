from jinja2 import Environment, meta, TemplateSyntaxError
from typing import Any, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.agents.PromptConstructor import PromptConstructor
    from edsl.scenarios.Scenario import Scenario
    from edsl.questions.QuestionBase import QuestionBase
    from edsl.agents.Agent import Agent


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

    def extract_question_file_keys(self):
        """
        Extracts the file keys from the question text.

        These are keys from Scenario object that are associated with FileStore objects.

        >>> from edsl import QuestionMultipleChoice, Scenario
        >>> q = QuestionMultipleChoice(question_text="Do you like school?", question_name = "q0", question_options = ["yes", "no"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = Scenario({"file1": "file1"}), question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> qtrb.extract_question_file_keys()
        []
        >>> from edsl import FileStore
        >>> fs = FileStore.example()
        >>> q = QuestionMultipleChoice(question_text="What do you think of this file: {{ file1 }}", question_name = "q0", question_options = ["good", "bad"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = Scenario({"file1": fs}), question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> qtrb.extract_question_file_keys()
        ['file1']
        """
        #question_text = self.question.question_text
        #file_keys = self._find_file_keys(self.scenario)
        #file_keys = self.scenario._find_file_keys()
        #return self._extract_file_keys_from_question_text(question_text, file_keys)
        return self.question._file_keys(self.scenario)

    def scenario_file_keys(self):
        return self.scenario._find_file_keys()

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

    # @staticmethod
    # def _extract_file_keys_from_question_text(
    #     question_text: str, scenario_file_keys: list
    # ) -> list:
    #     """
    #     Extracts the file keys from a question text.

    #     >>> from edsl import Scenario
    #     >>> from edsl.scenarios.FileStore import FileStore
    #     >>> import tempfile
    #     >>> with tempfile.NamedTemporaryFile() as f:
    #     ...     _ = f.write(b"Hello, world!")
    #     ...     _ = f.seek(0)
    #     ...     fs = FileStore(f.name)
    #     ...     scenario = Scenario({"fs_file": fs, 'a': 1})
    #     ...     QuestionTemplateReplacementsBuilder._extract_file_keys_from_question_text("{{ fs_file }}", ['fs_file'])
    #     ['fs_file']
    #     """
    #     variables = QuestionTemplateReplacementsBuilder.get_jinja2_variables(
    #         question_text
    #     )
    #     question_file_keys = []
    #     for var in variables:
    #         if var in scenario_file_keys:
    #             question_file_keys.append(var)
    #     return question_file_keys

    def _scenario_replacements(
        self, replacement_string: str = "<see file {key}>"
    ) -> dict[str, Any]:
        # File references dictionary
        file_refs = {
            key: replacement_string.format(key=key) for key in self.scenario_file_keys()
        }

        # Scenario items excluding file keys
        scenario_items = {
            k: v for k, v in self.scenario.items() if k not in self.scenario_file_keys()
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
        """Builds a dictionary of replacement values for rendering a prompt by combining multiple data sources.


        >>> from edsl import QuestionMultipleChoice, Scenario
        >>> q = QuestionMultipleChoice(question_text="Do you like school?", question_name = "q0", question_options = ["yes", "no"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = Scenario({"file1": "file1"}), question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> qtrb.extract_question_file_keys()
        []
        >>> from edsl import FileStore
        >>> fs = FileStore.example()
        >>> s = Scenario({"file1": fs, "first_name": "John"})
        >>> q = QuestionMultipleChoice(question_text="What do you think of this file: {{ file1 }}, {{ first_name}}", question_name = "q0", question_options = ["good", "bad"])
        >>> qtrb = QuestionTemplateReplacementsBuilder(scenario = s, question = q, prior_answers_dict = {'q0': 'q0'}, agent = "agent")
        >>> qtrb.build_replacement_dict(q.data)
        {'file1': '<see file file1>', 'first_name': 'John', 'use_code': False, 'include_comment': True, 'question_name': 'q0', 'question_text': 'What do you think of this file: {{ file1 }}, {{ first_name}}', 'question_options': ['good', 'bad'], 'q0': 'q0', 'agent': 'agent'}


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
    
    def final_question_data(self):
        question_data = self.question.data.copy()
        replacement_dict = self.build_replacement_dict(question_data)
        for key, value in replacement_dict.items():
            question_data[key] = value
        return question_data



if __name__ == "__main__":
    import doctest

    doctest.testmod()
