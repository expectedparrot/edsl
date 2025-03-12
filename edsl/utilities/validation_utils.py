"""Utility functions for validation."""

import ast
import keyword
import re


def is_valid_variable_name(name, allow_name=True):
    """Check if a string is a valid variable name."""
    if allow_name:
        return name.isidentifier() and not keyword.iskeyword(name)
    else:
        return (
            name.isidentifier() and not keyword.iskeyword(name) and not name == "name"
        )


def extract_variable_names(node):
    """Extract variable names from an abstract syntax tree (AST) node."""
    if isinstance(node, ast.Name):
        return [node.id]  # Extract variable name
    elif isinstance(node, ast.BinOp):
        left_names = extract_variable_names(node.left)
        right_names = extract_variable_names(node.right)
        return left_names + right_names
    elif isinstance(node, ast.UnaryOp):
        return extract_variable_names(node.operand)
    elif isinstance(node, ast.Call):
        names = []
        for arg in node.args:
            names.extend(extract_variable_names(arg))
        return names
    else:
        names = []
        for child in ast.iter_child_nodes(node):
            names.extend(extract_variable_names(child))
        return names
        
        
# Alternate regex-based implementation for simple cases
def extract_variable_names_from_string(code_string):
    """Extract variable names from a code string using regex."""
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*='
    matches = re.findall(pattern, code_string)
    return matches