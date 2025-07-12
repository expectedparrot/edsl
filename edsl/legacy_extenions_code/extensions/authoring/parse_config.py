import ast
import yaml
from .authoring import ServiceDefinition


def load_service_definition_from_file(filepath):
    """
    Safely parse a Python file containing a YAML string and return a ServiceDefinition object.

    Args:
        filepath: Path to the Python file containing YAML_STRING variable

    Returns:
        ServiceDefinition object instantiated from the YAML content

    Raises:
        ValueError: If YAML_STRING variable not found or cannot be parsed
    """
    with open(filepath, "r") as f:
        content = f.read()

    # Parse the Python file into an AST
    tree = ast.parse(content)

    # Look for the YAML_STRING assignment
    yaml_string = None

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            # Check if this is assigning to YAML_STRING
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "YAML_STRING":
                    # Extract the string value
                    try:
                        yaml_string = ast.literal_eval(node.value)
                        if not isinstance(yaml_string, str):
                            raise ValueError("YAML_STRING must be a string literal")
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"Could not parse YAML_STRING value: {e}")
                    break

    if yaml_string is None:
        raise ValueError("YAML_STRING variable not found in file")

    # Create and return the ServiceDefinition
    return ServiceDefinition.from_yaml(yaml_string)


# Usage
# service_def = load_service_definition_from_file('config.py')
