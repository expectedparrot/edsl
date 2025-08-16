"""Module for extracting parameter and return type definitions from Python functions."""

from typing import (
    Dict,
    Callable,
    Any,
    get_origin,
    get_args,
    Union,
    Tuple,
)
import inspect
import re

from .authoring import ParameterDefinition, ReturnDefinition


class FunctionSignatureExtractor:
    """A class that extracts and manages parameter and return definitions from a callable.

    Args:
        func: The callable to extract signature information from

    Example:
        >>> def example_func(name: str, age: int = 25, *, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...     '''Example function with docstring.
        ...
        ...     Args:
        ...         name: The person's name
        ...         age: The person's age
        ...         details: Additional details about the person
        ...
        ...     Returns:
        ...         Dict[str, Any]: A dictionary containing the person's information
        ...     '''
        ...     pass
        >>> extractor = FunctionSignatureExtractor(example_func)
        >>> params = extractor.get_parameter_definitions()
        >>> params['name'].type == 'str' and params['name'].required
        True
        >>> params['age'].type == 'int' and not params['age'].required
        True
        >>> params['age'].default_value == 25
        True
        >>> returns = extractor.get_return_definitions()
        >>> returns['return'].type == 'Dict[str, Any]'
        True
    """

    def __init__(self, func: Callable):
        self.func = func
        self.signature = inspect.signature(func)

    def _get_type_str(self, annotation) -> str:
        """Helper to convert type annotation to string representation."""
        if annotation == inspect.Parameter.empty:
            return "Any"

        # Handle Optional types
        if get_origin(annotation) is Union:
            args = get_args(annotation)
            if len(args) == 2 and type(None) in args:
                # It's an Optional type
                real_type = next(arg for arg in args if arg is not type(None))
                return self._get_type_str(real_type)

        # Handle basic types
        if isinstance(annotation, type):
            return annotation.__name__

        # Handle generic types (List, Dict, etc)
        origin = get_origin(annotation)
        if origin is not None:
            args = get_args(annotation)
            origin_name = (
                origin.__name__ if hasattr(origin, "__name__") else str(origin)
            )
            if args:
                args_str = ", ".join(self._get_type_str(arg) for arg in args)
                return f"{origin_name}[{args_str}]"
            return origin_name

        return str(annotation)

    def _get_param_description(self, param_name: str) -> str:
        """Extract parameter description from function docstring if available."""
        if not self.func.__doc__:
            return ""

        docstring = inspect.cleandoc(self.func.__doc__)

        # Try Google-style docstring first (Args: param: description)
        google_pattern = (
            rf"Args:.*?\n\s+{param_name}\s*\([^)]+\):\s*(.*?)(?=\n\s+\w+\s*\(|$)"
        )
        match = re.search(google_pattern, docstring, re.DOTALL | re.MULTILINE)
        if match:
            # Clean up multi-line descriptions
            desc = match.group(1).strip()
            desc = " ".join(line.strip() for line in desc.split("\n"))
            return desc

        # Try RST-style docstring (Parameters: \n---------\nparam_name : type\n    description)
        rst_pattern = rf"Parameters.*?\n\s*{param_name}\s*:\s*[^\n]*\n\s+(.*?)(?=\n\s*(?:\w+\s*:|$))"
        match = re.search(rst_pattern, docstring, re.DOTALL | re.MULTILINE)
        if match:
            # Clean up the description by removing extra whitespace and newlines
            desc = match.group(1).strip()
            # Join multiple lines and normalize whitespace
            desc = " ".join(line.strip() for line in desc.split("\n"))
            return desc

        # Try simple pattern as fallback
        simple_pattern = rf"{param_name}\s*(?:\([^)]*\))?\s*:\s*(.*?)(?=\n\s*\w+(?:\s*\([^)]*\))?\s*:|$)"
        match = re.search(simple_pattern, docstring, re.DOTALL)
        if match:
            desc = match.group(1).strip()
            desc = " ".join(line.strip() for line in desc.split("\n"))
            return desc

        return ""

    def get_parameter_definitions(self) -> Dict[str, ParameterDefinition]:
        """Creates a dictionary of ParameterDefinition objects from the function.

        Returns:
            A dictionary mapping parameter names to ParameterDefinition objects
        """
        param_defs = {}

        for name, param in self.signature.parameters.items():
            # Skip *args and **kwargs
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            type_str = self._get_type_str(param.annotation)
            has_default = param.default is not param.empty
            description = self._get_param_description(name)

            param_defs[name] = ParameterDefinition(
                type=type_str,
                required=not has_default,
                description=description,
                default_value=param.default if has_default else None,
            )

        return param_defs

    def get_parameter_names(self) -> list[str]:
        """Returns a list of parameter names, excluding *args and **kwargs.

        Returns:
            List of parameter names
        """
        return [
            name
            for name, param in self.signature.parameters.items()
            if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
        ]

    def get_required_parameters(self) -> list[str]:
        """Returns a list of required parameter names.

        Returns:
            List of required parameter names
        """
        return [
            name
            for name, param in self.signature.parameters.items()
            if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
            and param.default is param.empty
        ]

    def get_optional_parameters(self) -> Dict[str, Any]:
        """Returns a dictionary of optional parameters and their default values.

        Returns:
            Dictionary mapping optional parameter names to their default values
        """
        return {
            name: param.default
            for name, param in self.signature.parameters.items()
            if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
            and param.default is not param.empty
        }

    def _get_return_description(self) -> str:
        """Extract return value description from function docstring if available."""
        if not self.func.__doc__:
            return ""

        docstring = inspect.cleandoc(self.func.__doc__)

        # Try Google-style docstring first (Returns: description)
        google_pattern = r"Returns:\s*(.*?)(?=\n\s*(?:\w+:|$))"
        match = re.search(google_pattern, docstring, re.DOTALL | re.MULTILINE)
        if match:
            desc = match.group(1).strip()
            desc = " ".join(line.strip() for line in desc.split("\n"))
            return desc

        # Try RST-style docstring
        rst_pattern = r"Returns.*?\n\s*-+\s*\n\s*(.*?)(?=\n\s*(?:\w+:|\Z))"
        match = re.search(rst_pattern, docstring, re.DOTALL | re.MULTILINE)
        if match:
            desc = match.group(1).strip()
            desc = " ".join(line.strip() for line in desc.split("\n"))
            return desc

        return ""

    def get_return_definitions(self) -> Dict[str, ReturnDefinition]:
        """Creates a dictionary of ReturnDefinition objects from the function's return annotation.

        Returns:
            A dictionary mapping return names to ReturnDefinition objects. For single return values,
            the key will be 'return'. For annotated tuple returns, the keys will be the field names
            if available, or 'return_0', 'return_1', etc.
        """
        return_defs = {}
        return_annotation = self.signature.return_annotation

        if return_annotation == inspect.Signature.empty:
            # If no return annotation, create a default ReturnDefinition
            return_defs["return"] = ReturnDefinition(
                type="Any", description=self._get_return_description(), coopr_url=False
            )
            return return_defs

        # Handle tuple returns (e.g., Tuple[str, int])
        if get_origin(return_annotation) in (tuple, Tuple):
            args = get_args(return_annotation)
            for i, arg in enumerate(args):
                return_defs[f"return_{i}"] = ReturnDefinition(
                    type=self._get_type_str(arg),
                    description=self._get_return_description(),
                    coopr_url=False,
                )
        else:
            # Single return value
            return_defs["return"] = ReturnDefinition(
                type=self._get_type_str(return_annotation),
                description=self._get_return_description(),
                coopr_url=False,  # This could be made configurable if needed
            )

        return return_defs


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
