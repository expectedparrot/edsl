from jinja2 import Environment
from typing import List, Union

import edsl.scenarios.scenario  # noqa: F401


def extract_template_variables(ast) -> List[Union[str, tuple]]:
    """
    Extract variable expressions from a Jinja2 AST.
    
    Args:
        ast: Jinja2 AST
        
    Returns:
        List[Union[str, tuple]]: List of variable names or tuples for dotted paths
    """
    from jinja2 import nodes
    from jinja2.visitor import NodeVisitor
    
    variables = []
    
    class VariableVisitor(NodeVisitor):
        def visit_Name(self, node):
            variables.append(node.name)
        
        def visit_Getattr(self, node):
            # For dotted access like scenario.question_options
            parts = []
            current = node
            
            # Handle the leaf attribute
            parts.append(node.attr)
            
            # Walk up the chain to collect all parts
            while isinstance(current.node, nodes.Getattr):
                current = current.node
                parts.append(current.attr)
            
            # Add the root name
            if isinstance(current.node, nodes.Name):
                parts.append(current.node.name)
            
            # Reverse to get the correct order
            parts.reverse()
            variables.append(tuple(parts))
    
    visitor = VariableVisitor()
    visitor.visit(ast)
    
    return variables


class QuestionOptionProcessor:
    """
    Class that manages the processing of question options.
    These can be provided directly, as a template string, or fetched from prior answers or the scenario.
    """

    @classmethod
    def from_prompt_constructor(cls, prompt_constructor):
        scenario = prompt_constructor.scenario
        prior_answers_dict = prompt_constructor.prior_answers_dict()

        return cls(scenario, prior_answers_dict)

    def __init__(self, scenario: 'edsl.scenarios.scenario.Scenario', prior_answers_dict: dict):
        # This handles cases where the question has {{ scenario.key }} - eventually 
        # we might not allow 'naked' scenario keys w/o the scenario prefix
        #new_scenario = scenario.copy()
        #new_scenario.update({'scenario': new_scenario})
        self.scenario = scenario
        self.prior_answers_dict = prior_answers_dict

    @staticmethod
    def _get_default_options() -> list:
        """Return default placeholder options."""
        return [f"<< Option {i} - Placeholder >>" for i in range(1, 4)]

    @staticmethod
    def _parse_template_variable(template_str: str) -> Union[str, tuple]:
        """
        Extract the variable name from a template string.
        If the variable contains dots (e.g., scenario.question_options), 
        returns a tuple of the path components.

        Args:
            template_str (str): Jinja template string

        Returns:
            Union[str, tuple]: Name of the first undefined variable in the template,
                              or a tuple of path components if the variable contains dots

        >>> QuestionOptionProcessor._parse_template_variable("Here are some {{ options }}")
        'options'
        >>> QuestionOptionProcessor._parse_template_variable("Here are some {{ scenario.question_options }}")
        ('scenario', 'question_options')
        >>> QuestionOptionProcessor._parse_template_variable("Here are some {{ options }} and {{ other }}")
        Traceback (most recent call last):
        ...
        ValueError: Multiple variables found in template string
        >>> QuestionOptionProcessor._parse_template_variable("Here are some")
        Traceback (most recent call last):
        ...
        ValueError: No variables found in template string
        """
        env = Environment()
        parsed_content = env.parse(template_str)
        undeclared_variables = extract_template_variables(parsed_content)
        
        if not undeclared_variables:
            from edsl.invigilators.exceptions import InvigilatorValueError
            raise InvigilatorValueError("No variables found in template string")
        if len(undeclared_variables) > 1:
            from edsl.invigilators.exceptions import InvigilatorValueError
            raise InvigilatorValueError("Multiple variables found in template string")
        
        return undeclared_variables[0]

    @staticmethod
    def _get_options_from_scenario(
        scenario: dict, option_key: str
    ) -> Union[list, None]:
        """
        Try to get options from scenario data.

        >>> from edsl import Scenario
        >>> scenario = Scenario({"options": ["Option 1", "Option 2"]})
        >>> QuestionOptionProcessor._get_options_from_scenario(scenario, "options")
        ['Option 1', 'Option 2']


        Returns:
            list | None: List of options if found in scenario, None otherwise
        """
        scenario_options = scenario.get(option_key)
        return scenario_options if isinstance(scenario_options, list) else None

    @staticmethod
    def _get_options_from_prior_answers(
        prior_answers: dict, option_key: str
    ) -> Union[list, None]:
        """
        Try to get options from prior answers.

        prior_answers (dict): Dictionary of prior answers
        option_key (str): Key to look up in prior answers

        >>> from edsl import QuestionList as Q
        >>> q = Q.example()
        >>> q.answer = ["Option 1", "Option 2"]
        >>> prior_answers = {"options": q}
        >>> QuestionOptionProcessor._get_options_from_prior_answers(prior_answers, "options")
        ['Option 1', 'Option 2']
        >>> QuestionOptionProcessor._get_options_from_prior_answers(prior_answers, "wrong_key") is None
        True

        Returns:
            list | None: List of options if found in prior answers, None otherwise
        """
        prior_answer = prior_answers.get(option_key)
        if prior_answer and hasattr(prior_answer, "answer"):
            if isinstance(prior_answer.answer, list):
                return prior_answer.answer
        return None

    def get_question_options(self, question_data: dict) -> list:
        """
        Extract and process question options from question data.

        Args:
            question_data (dict): Dictionary containing question configuration

        Returns:
            list: List of question options. Returns default placeholders if no valid options found.

        >>> class MockPromptConstructor:
        ...     pass
        >>> mpc = MockPromptConstructor()
        >>> from edsl import Scenario
        >>> mpc.scenario = Scenario({"options": ["Option 1", "Option 2"]})
        >>> mpc.prior_answers_dict = lambda: {'q0': 'q0'}
        >>> processor = QuestionOptionProcessor.from_prompt_constructor(mpc)

        The basic case where options are directly provided:

        >>> question_data = {"question_options": ["Option 1", "Option 2"]}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2']

        The case where options are provided as a template string:

        >>> question_data = {"question_options": "{{ scenario.options }}"}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2']

        The case where there is a templace string but it's in the prior answers:

        >>> class MockQuestion:
        ...     pass
        >>> q0 = MockQuestion()
        >>> q0.answer = ["Option 1", "Option 2"]
        >>> mpc.prior_answers_dict = lambda: {'q0': q0}
        >>> processor = QuestionOptionProcessor.from_prompt_constructor(mpc)
        >>> question_data = {"question_options": "{{ q0.answer }}"}
        >>> processor.get_question_options(question_data)
        ['Option 1', 'Option 2']

        The case we're no options are found:
        >>> processor.get_question_options({"question_options": "{{ poop }}"})
        ['<< Option 1 - Placeholder >>', '<< Option 2 - Placeholder >>', '<< Option 3 - Placeholder >>']

        """
        options_entry = question_data.get("question_options")

        # If not a template string, return as is or default
        if not isinstance(options_entry, str):
            return options_entry if options_entry else self._get_default_options()

        # Parse template to get variable name
        raw_option_key = self._parse_template_variable(options_entry)

        source_type = None

        if isinstance(raw_option_key, tuple):
            if raw_option_key[0] == 'scenario':
                source_type = 'scenario'
                option_key = raw_option_key[-1]
            else:
                source_type = 'prior_answers'
                option_key = raw_option_key[0]
                #breakpoint()
        else:
            option_key = raw_option_key

        #breakpoint()

        if source_type == 'scenario':
            # Try getting options from scenario
            scenario_options = self._get_options_from_scenario(
                self.scenario, option_key
            )
            if scenario_options:
                return scenario_options
            
        if source_type == 'prior_answers':

            # Try getting options from prior answers
            prior_answer_options = self._get_options_from_prior_answers(
                self.prior_answers_dict, option_key
            )
            if prior_answer_options:
                return prior_answer_options

        return self._get_default_options()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
