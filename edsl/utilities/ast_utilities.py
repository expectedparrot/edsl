"""Utilities for working with abstract syntax trees (ASTs)."""

import ast


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
