"""Module for analyzing return value structures using AST."""

import ast
import inspect
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from .authoring import ReturnDefinition


class ReturnStructureError(Exception):
    """Exception raised when return structure is missing required fields."""

    pass


@dataclass
class ReturnStructure:
    """Represents the structure of a return value."""

    is_dict: bool
    keys: List[str]
    nested_structures: Dict[str, "ReturnStructure"]
    literal_values: Dict[str, Any]
    computed_values: Dict[str, str]  # Key -> description of computation

    def to_return_definitions(self) -> Dict[str, ReturnDefinition]:
        """Convert the return structure to ReturnDefinition objects if it matches the expected pattern.

        The expected pattern is a dictionary where each value is itself a dictionary containing:
        - type: str
        - description: str
        - coopr_url: bool
        - value: Any

        Raises:
            ReturnStructureError: If any required fields are missing from the return structure
        """
        return_defs = {}
        required_fields = ["type", "description", "coopr_url"]

        # For each top-level key in the return dictionary
        for key in self.keys:
            if key in self.nested_structures:
                nested = self.nested_structures[key]

                # Check for missing fields
                missing_fields = [
                    field
                    for field in required_fields
                    if field not in nested.literal_values
                    and field not in nested.computed_values
                ]

                if missing_fields:
                    missing_fields_str = ", ".join(missing_fields)
                    raise ReturnStructureError(
                        f"Return value for key '{key}' is missing required fields: {missing_fields_str}.\n"
                        f"Each return value must include: {', '.join(required_fields)}."
                    )

                return_defs[key] = ReturnDefinition(
                    type=nested.literal_values.get("type", "Any"),
                    description=nested.literal_values.get("description", ""),
                    coopr_url=nested.literal_values.get("coopr_url", False),
                )

        return return_defs


class ReturnAnalyzer(ast.NodeVisitor):
    """Analyzes return statements in Python code using AST to extract ReturnDefinition structures."""

    def __init__(self):
        self.return_nodes: List[ast.Return] = []

    def visit_Return(self, node: ast.Return):
        """Collect return statement nodes."""
        self.return_nodes.append(node)
        self.generic_visit(node)

    def _analyze_dict(self, node: ast.Dict) -> ReturnStructure:
        """Analyze a dictionary AST node."""
        keys = []
        nested_structures = {}
        literal_values = {}
        computed_values = {}

        # Process each key-value pair
        for key_node, value_node in zip(node.keys, node.values):
            if not isinstance(key_node, ast.Str):
                continue  # Skip non-string keys for now

            key = key_node.s
            keys.append(key)

            # Handle different types of values
            if isinstance(value_node, ast.Dict):
                # Nested dictionary
                nested_structures[key] = self._analyze_dict(value_node)
            elif isinstance(value_node, (ast.Str, ast.Num, ast.Constant)):
                # Literal values
                literal_values[key] = (
                    value_node.s
                    if isinstance(value_node, ast.Str)
                    else value_node.value
                )
            else:
                # Computed or complex values
                computed_values[key] = ast.unparse(value_node)

        return ReturnStructure(
            is_dict=True,
            keys=keys,
            nested_structures=nested_structures,
            literal_values=literal_values,
            computed_values=computed_values,
        )

    def get_return_definitions(
        self, func_or_source: Union[str, ast.AST, callable]
    ) -> Dict[str, ReturnDefinition]:
        """Analyze the function and extract ReturnDefinition objects from its return value structure.

        This looks at the actual return statement structure, not type annotations.

        Args:
            func_or_source: Either a function object, source code string, or AST node

        Returns:
            Dictionary mapping return keys to ReturnDefinition objects

        Example:
            >>> code = '''
            ... def example():
            ...     return {
            ...         'survey': {
            ...             'type': 'Survey',
            ...             'description': 'A survey object',
            ...             'coopr_url': False,
            ...             'value': compute_value()
            ...         }
            ...     }
            ... '''
            >>> analyzer = ReturnAnalyzer()
            >>> defs = analyzer.get_return_definitions(code)
            >>> 'survey' in defs
            True
            >>> defs['survey'].type == 'Survey'
            True
            >>> defs['survey'].description == 'A survey object'
            True
            >>> defs['survey'].coopr_url == False
            True
        """
        structure = self.analyze_return_value(func_or_source)
        if structure:
            return structure.to_return_definitions()
        return {}

    def analyze_return_value(
        self, func_or_source: Union[str, ast.AST, callable]
    ) -> Optional[ReturnStructure]:
        """Analyze the structure of the return value in the given function or source code."""
        # Convert input to AST
        if isinstance(func_or_source, str):
            tree = ast.parse(func_or_source)
        elif callable(func_or_source):
            tree = ast.parse(inspect.getsource(func_or_source))
        else:
            tree = func_or_source

        # Find return statements
        self.return_nodes = []
        self.visit(tree)

        # Analyze the first return statement that returns a dictionary
        for return_node in self.return_nodes:
            if isinstance(return_node.value, ast.Dict):
                return self._analyze_dict(return_node.value)

        return None


if __name__ == "__main__":
    import doctest

    doctest.testmod()

    # Test with create_automated_survey
    from autostudy.stage_generate_survey import create_automated_survey

    analyzer = ReturnAnalyzer()
    structure = analyzer.analyze_return_value(create_automated_survey)

    # Print the analyzed structure
    print("\nAnalyzing create_automated_survey return value:")
    print(f"Top level keys: {structure.keys}")
    survey_struct = structure.nested_structures["survey"]
    print("\nSurvey dictionary structure:")
    print(f"  Keys: {survey_struct.keys}")
    print(f"  Literal values: {survey_struct.literal_values}")
    print(f"  Computed values: {survey_struct.computed_values}")
