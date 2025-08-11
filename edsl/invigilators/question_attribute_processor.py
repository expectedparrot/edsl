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

        def visit_Getitem(self, node):
            # For dictionary access like scenario.color_list['choices']
            parts = []
            current = node

            # Handle the dictionary key
            if isinstance(node.arg, nodes.Const):
                parts.append(node.arg.value)
            else:
                # If the key is not a constant, we can't easily represent it
                # For now, we'll skip these cases
                return

            # Walk up the chain to collect all parts
            while isinstance(current.node, nodes.Getitem):
                if isinstance(current.node.arg, nodes.Const):
                    parts.append(current.node.arg.value)
                else:
                    return  # Skip if key is not a constant
                current = current.node

            # Handle the base object (could be a Name or Getattr)
            if isinstance(current.node, nodes.Name):
                parts.append(current.node.name)
            elif isinstance(current.node, nodes.Getattr):
                # Handle dotted access as the base
                attr_parts = []
                attr_current = current.node
                attr_parts.append(attr_current.attr)

                while isinstance(attr_current.node, nodes.Getattr):
                    attr_current = attr_current.node
                    attr_parts.append(attr_current.attr)

                if isinstance(attr_current.node, nodes.Name):
                    attr_parts.append(attr_current.node.name)

                parts.extend(attr_parts)

            # Reverse to get the correct order
            parts.reverse()
            variables.append(tuple(parts))

    visitor = VariableVisitor()
    visitor.visit(ast)

    return variables


class QuestionAttributeProcessor:
    """
    Class that manages the processing of question attributes.
    These can be provided directly, as a template string, or fetched from prior answers or the scenario.
    """

    @classmethod
    def from_prompt_constructor(cls, prompt_constructor):
        scenario = prompt_constructor.scenario
        prior_answers_dict = prompt_constructor.prior_answers_dict()

        return cls(scenario, prior_answers_dict)

    def __init__(
        self, scenario: "edsl.scenarios.scenario.Scenario", prior_answers_dict: dict
    ):
        # This handles cases where the question has {{ scenario.key }} - eventually
        # we might not allow 'naked' scenario keys w/o the scenario prefix
        # new_scenario = scenario.copy()
        # new_scenario.update({'scenario': new_scenario})
        self.scenario = scenario
        self.prior_answers_dict = prior_answers_dict

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

        >>> QuestionAttributeProcessor._parse_template_variable("Here are some {{ options }}")
        'options'
        >>> QuestionAttributeProcessor._parse_template_variable("Here are some {{ scenario.question_options }}")
        ('scenario', 'question_options')
        >>> try:
        ...     QuestionAttributeProcessor._parse_template_variable("Here are some {{ options }} and {{ other }}")
        ... except Exception as e:
        ...     print("Multiple variables found in template string")
        Multiple variables found in template string
        >>> try:
        ...     QuestionAttributeProcessor._parse_template_variable("Here are some")
        ... except Exception as e:
        ...     print("No variables found in template string")
        No variables found in template string
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
    def _get_nested_key(data: dict, key_path: tuple) -> Union[any, None]:
        """
        Safely get a nested key from a dictionary using a tuple of keys.
        """
        try:
            current = data
            for key in key_path:
                current = current[key]
            return current
        except KeyError:
            return None


if __name__ == "__main__":
    import doctest

    doctest.testmod()
