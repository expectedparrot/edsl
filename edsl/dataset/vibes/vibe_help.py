"""
Dataset Vibe Help: Answer questions about Dataset usage using introspection.

This module provides a VibeHelp class that uses inspect to analyze Dataset methods
and generates helpful responses to user questions about dataset usage.
"""

from __future__ import annotations

import inspect
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from ...base.openai_utils import create_openai_client


def find_dotenv_upwards(start_path: Optional[str] = None) -> Optional[Path]:
    """
    Search for .env file starting from start_path and moving up the directory tree.

    Parameters
    ----------
    start_path : str, optional
        Starting directory for the search. Defaults to current working directory.

    Returns
    -------
    Path or None
        Path to the .env file if found, None otherwise.
    """
    if start_path is None:
        start_path = os.getcwd()

    current = Path(start_path).resolve()

    # Search upwards until we find .env or reach the root
    while True:
        env_file = current / ".env"
        if env_file.is_file():
            return env_file

        # Check if we've reached the root
        parent = current.parent
        if parent == current:
            # We've reached the root directory
            return None

        current = parent


# Load environment variables from .env file (search upwards from current directory)
env_path = find_dotenv_upwards()
if env_path:
    load_dotenv(env_path)


@dataclass
class VibeHelp:
    """
    Answer questions about Dataset usage using introspection and LLM assistance.

    This class uses inspect to gather information about Dataset methods and their
    documentation, then uses an LLM to provide helpful, contextual responses to
    user questions about how to use the Dataset class.

    Parameters
    ----------
    model : str
        The OpenAI model to use (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.1 for consistent responses)
    include_source : bool
        Whether to include source code in the analysis (default: False)

    Examples
    --------
    >>> help_tool = VibeHelp()  # doctest: +SKIP
    >>> response = help_tool.get_help(  # doctest: +SKIP
    ...     question="How do I flatten a dictionary field?",
    ...     dataset_instance=my_dataset
    ... )  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.1
    include_source: bool = False

    def __post_init__(self):
        self.client = create_openai_client()

    def _get_dataset_methods_info(self, dataset_class) -> List[Dict[str, Any]]:
        """
        Extract method information from the Dataset class using introspection.

        Parameters
        ----------
        dataset_class : type
            The Dataset class to analyze

        Returns
        -------
        List[Dict[str, Any]]
            List of dictionaries containing method information
        """
        methods_info = []

        for name, method in inspect.getmembers(
            dataset_class, predicate=inspect.isfunction
        ):
            if not name.startswith("_") and hasattr(method, "__doc__"):
                method_info = {
                    "name": name,
                    "signature": str(inspect.signature(method)),
                    "docstring": method.__doc__ or "No documentation available",
                }

                if self.include_source:
                    try:
                        method_info["source"] = inspect.getsource(method)
                    except (OSError, TypeError):
                        method_info["source"] = "Source not available"

                methods_info.append(method_info)

        return methods_info

    def get_help(
        self,
        question: str,
        dataset_instance,
        context_columns: Optional[List[str]] = None,
    ) -> str:
        """
        Generate a helpful response to a Dataset usage question.

        Parameters
        ----------
        question : str
            Natural language question about Dataset usage.
            Examples:
            - "How do I flatten a dictionary field?"
            - "What methods are available for filtering data?"
            - "How do I convert to different formats?"
            - "Show me examples of data manipulation"
        dataset_instance : Dataset
            An instance of the Dataset class to provide context
        context_columns : List[str], optional
            Specific columns to use as context (default: first 5 columns)

        Returns
        -------
        str
            Markdown-formatted response with explanations and code examples

        Examples
        --------
        >>> help_tool = VibeHelp(model="gpt-4o", temperature=0.1)  # doctest: +SKIP
        >>> dataset = Dataset.example()  # doctest: +SKIP
        >>> response = help_tool.get_help("How do I select columns?", dataset)  # doctest: +SKIP
        >>> isinstance(response, str)  # doctest: +SKIP
        True  # doctest: +SKIP
        """
        # Get Dataset class information
        dataset_class = dataset_instance.__class__
        class_docstring = dataset_class.__doc__ or "No class documentation available"
        methods_info = self._get_dataset_methods_info(dataset_class)

        # Get context from the dataset instance
        if context_columns is None:
            context_columns = (
                dataset_instance.keys()[:5]
                if len(dataset_instance.keys()) > 0
                else ["a", "b", "c"]
            )

        dataset_length = len(dataset_instance) if len(dataset_instance) > 0 else 0

        # Create the system prompt
        system_prompt = (
            "You are an expert Python developer and data analyst specializing in the EDSL Dataset class. "
            "Your job is to provide helpful, accurate, and practical guidance on how to use Dataset methods. "
            "Always provide concrete code examples and explain the reasoning behind your suggestions."
        )

        # Create the user prompt with all the context
        user_prompt = {
            "task": "Answer a question about Dataset usage",
            "question": question,
            "class_documentation": class_docstring,
            "available_methods": [
                {
                    "name": method["name"],
                    "signature": method["signature"],
                    "docstring": (
                        method["docstring"][:500] + "..."
                        if len(method["docstring"]) > 500
                        else method["docstring"]
                    ),
                }
                for method in methods_info
            ],
            "dataset_context": {
                "available_columns": context_columns,
                "num_observations": dataset_length,
                "example_usage": "d = Dataset.example()",
            },
            "instructions": (
                "Provide a helpful response that:\n"
                "1. Directly answers the user's question\n"
                "2. Shows relevant Dataset method(s) to use\n"
                "3. Provides concrete, executable code examples\n"
                "4. Uses markdown formatting with proper code blocks\n"
                "5. Explains why you chose specific methods\n"
                "6. Shows step-by-step examples when appropriate\n"
                "7. References the actual method signatures and documentation\n"
                "8. Uses the provided dataset context for realistic examples\n\n"
                "Format your response as markdown. Use ```python for code blocks. "
                "Be concise but thorough. Focus on practical examples the user can try immediately."
            ),
        }

        # Add source code if requested
        if self.include_source:
            user_prompt["source_code"] = {
                method["name"]: method.get("source", "Not available")
                for method in methods_info
                if "source" in method
            }

        # Make the API call
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            temperature=self.temperature,
        )

        return resp.choices[0].message.content

    def get_help_for_class(
        self,
        question: str,
        target_class,
        example_instance=None,
        context_columns: Optional[List[str]] = None,
    ) -> str:
        """
        Generate a helpful response to a usage question for any EDSL class.

        Parameters
        ----------
        question : str
            Natural language question about class usage
        target_class : type
            The class to analyze (e.g., Dataset, Survey, Question, etc.)
        example_instance : Any, optional
            An example instance to provide context (will create one if None)
        context_columns : List[str], optional
            Specific columns/attributes to use as context

        Returns
        -------
        str
            Markdown-formatted response with explanations and code examples
        """
        # Get class information
        class_name = target_class.__name__
        class_docstring = target_class.__doc__ or "No class documentation available"
        methods_info = self._get_dataset_methods_info(target_class)

        # Get context from the example instance if available
        if example_instance is not None:
            if hasattr(example_instance, "keys") and callable(example_instance.keys):
                # For objects with keys() method like Dataset
                context_keys = (
                    example_instance.keys()[:5]
                    if len(example_instance.keys()) > 0
                    else ["example_key"]
                )
                instance_length = (
                    len(example_instance) if hasattr(example_instance, "__len__") else 0
                )
            elif hasattr(example_instance, "to_dict"):
                # For any EDSL object with to_dict method
                obj_dict = example_instance.to_dict()
                context_keys = list(obj_dict.keys())[:5]
                instance_length = len(obj_dict)
            else:
                context_keys = ["example_attribute"]
                instance_length = 0
        else:
            context_keys = ["example_attribute"]
            instance_length = 0

        if context_columns:
            context_keys = context_columns

        # Create the system prompt
        system_prompt = (
            f"You are an expert Python developer specializing in the EDSL {class_name} class. "
            f"Your job is to provide helpful, accurate, and practical guidance on how to use {class_name} methods. "
            f"Always provide concrete code examples and explain the reasoning behind your suggestions."
        )

        # Create the user prompt with all the context
        user_prompt = {
            "task": f"Answer a question about {class_name} usage",
            "question": question,
            "class_name": class_name,
            "class_documentation": class_docstring,
            "available_methods": [
                {
                    "name": method["name"],
                    "signature": method["signature"],
                    "docstring": (
                        method["docstring"][:500] + "..."
                        if len(method["docstring"]) > 500
                        else method["docstring"]
                    ),
                }
                for method in methods_info
            ],
            "context": {
                "class_example": (
                    f"{class_name}.example()"
                    if example_instance
                    else f"# {class_name} instance"
                ),
                "available_attributes": context_keys,
                "example_size": instance_length,
            },
            "instructions": (
                "Provide a helpful response that:\n"
                "1. Directly answers the user's question\n"
                f"2. Shows relevant {class_name} method(s) to use\n"
                "3. Provides concrete, executable code examples\n"
                "4. Uses markdown formatting with proper code blocks\n"
                "5. Explains why you chose specific methods\n"
                "6. Shows step-by-step examples when appropriate\n"
                "7. References the actual method signatures and documentation\n"
                "8. Uses the provided context for realistic examples\n\n"
                "Format your response as markdown. Use ```python for code blocks. "
                "Be concise but thorough. Focus on practical examples the user can try immediately."
            ),
        }

        # Add source code if requested
        if self.include_source:
            user_prompt["source_code"] = {
                method["name"]: method.get("source", "Not available")
                for method in methods_info
                if "source" in method
            }

        # Make the API call
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            temperature=self.temperature,
        )

        return resp.choices[0].message.content


# ---------- Example usage ----------
if __name__ == "__main__":
    from ..dataset import Dataset

    # Create a help tool instance
    help_tool = VibeHelp(model="gpt-4o", temperature=0.1)

    # Create an example dataset
    dataset = Dataset(
        [
            {"name": ["Alice", "Bob", "Charlie"]},
            {"age": [25, 30, 35]},
            {"city": ["Boston", "New York", "San Francisco"]},
        ]
    )

    # Example questions
    questions = [
        "How do I flatten a dictionary field?",
        "What methods are available for filtering data?",
        "How do I select specific columns?",
        "How do I convert this dataset to different formats?",
        "Show me how to manipulate and transform data",
    ]

    for question in questions:
        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print("=" * 60)
        response = help_tool.get_help(question, dataset)
        print(response)
        print("\n")
