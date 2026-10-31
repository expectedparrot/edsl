"""Utilities for working with abstract syntax trees (ASTs)."""

import ast


def extract_variable_names(node):
    """Extract variable names from an abstract syntax tree (AST) node.

    Every node recurses into its children, so a name is found wherever it appears.
    The one exception is a call's ``func``, deliberately skipped so that the name
    being called is not reported as a variable.

    Callers rely on this being exhaustive: a name missed here is a dependency the
    survey does not know it has.

    >>> import ast
    >>> extract_variable_names(ast.parse("q0 == 'yes'"))
    ['q0']
    >>> extract_variable_names(ast.parse("f(q0) == 5"))
    ['q0']
    >>> extract_variable_names(ast.parse("f(a=q0, b=10) == 5"))
    ['q0']
    >>> extract_variable_names(ast.parse("f(*q0, **q1) == 5"))
    ['q0', 'q1']
    """
    if isinstance(node, ast.Name):
        return [node.id]  # Extract variable name
    elif isinstance(node, ast.BinOp):
        left_names = extract_variable_names(node.left)
        right_names = extract_variable_names(node.right)
        return left_names + right_names
    elif isinstance(node, ast.UnaryOp):
        return extract_variable_names(node.operand)
    elif isinstance(node, ast.Call):
        # node.func is skipped on purpose; everything passed to the call is not.
        # Keyword arguments carry their value on `.value`, which also covers **kwargs.
        names = []
        for arg in node.args:
            names.extend(extract_variable_names(arg))
        for keyword in node.keywords:
            names.extend(extract_variable_names(keyword.value))
        return names
    else:
        names = []
        for child in ast.iter_child_nodes(node):
            names.extend(extract_variable_names(child))
        return names
