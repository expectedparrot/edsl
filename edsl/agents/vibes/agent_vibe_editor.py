"""
Agent Vibe Editor: Edit existing agent lists using natural language instructions.

This module provides an AgentVibeEdit class that can modify existing agent lists
based on natural language instructions. It can modify agent traits, add or remove
traits, change trait values, or make other edits as requested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import os
import json
from dotenv import load_dotenv
from pathlib import Path
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


# Note: We don't use Pydantic schemas here because agent traits are dynamic
# and OpenAI's structured output requires all object properties to be defined
# with additionalProperties: false. Instead, we use JSON mode.


# ---------- 2) The main editor class ----------
@dataclass
class AgentVibeEdit:
    """
    Edit existing agent lists using natural language instructions.

    This class uses an LLM to modify an existing agent list based on natural language
    instructions. It can modify agent traits, add or remove traits, change trait values,
    filter agents, or make other modifications as requested.

    Parameters
    ----------
    model : str
        The OpenAI model to use for editing (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.7)

    Examples
    --------
    >>> editor = AgentVibeEdit()  # doctest: +SKIP
    >>> edited_agents = editor.edit_agent_list(original_agents, "Make all agents older")  # doctest: +SKIP
    >>> print(json.dumps(edited_agents, indent=2))  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.7

    def __post_init__(self):
        self.client = create_openai_client()  # reads OPENAI_API_KEY from env with proper error handling

    def edit_agent_list(
        self,
        current_agents: List[Dict[str, Any]],
        edit_instructions: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Edit an agent list based on natural language instructions.

        Parameters
        ----------
        current_agents : List[Dict[str, Any]]
            List of current agent dictionaries from the agent list. Each agent
            dict should have a "traits" key containing a dictionary of traits,
            and optionally a "name" key.
        edit_instructions : str
            Natural language description of the edits to apply.
            Examples:
            - "Make all agents 10 years older"
            - "Add an 'education' trait to all agents"
            - "Remove agents under age 25"
            - "Translate all text traits to Spanish"
            - "Make the agents more diverse"

        Returns
        -------
        dict
            Dictionary with an "agents" key containing a list of edited agent
            dictionaries. Each agent dict has "traits" and optionally "name" keys.

        Examples
        --------
        >>> editor = AgentVibeEdit(model="gpt-4o", temperature=0.7)  # doctest: +SKIP
        >>> original = [  # doctest: +SKIP
        ...     {  # doctest: +SKIP
        ...         "traits": {"age": 25, "occupation": "student"},  # doctest: +SKIP
        ...         "name": "Alice"  # doctest: +SKIP
        ...     }  # doctest: +SKIP
        ... ]  # doctest: +SKIP
        >>> result = editor.edit_agent_list(original, "Make 5 years older")  # doctest: +SKIP
        >>> result["agents"][0]["traits"]["age"]  # doctest: +SKIP
        30
        """
        system = (
            "You are an expert agent list editor. "
            "Given a set of existing agents and instructions for editing them, "
            "apply the requested changes while maintaining agent quality and coherence. "
            "\n\n"
            "Your task is to:\n"
            "1. Understand the current agent list structure\n"
            "2. Apply the requested edits carefully\n"
            "3. Maintain agent integrity (proper traits and optional names)\n"
            "4. Preserve existing traits unless explicitly asked to change or remove them\n"
            "5. Return ONLY the agents that should remain in the edited list\n"
            "\n"
            "Agent Structure:\n"
            "- Each agent has a 'traits' dictionary containing trait_name: trait_value pairs\n"
            "- Each agent may optionally have a 'name' field\n"
            "- Traits can be any valid JSON type (strings, numbers, booleans, lists, dicts)\n"
            "\n"
            "Important guidelines:\n"
            "- If asked to add a trait, add it to all agents unless specified otherwise\n"
            "- If asked to remove a trait, remove it from all agents\n"
            "- If asked to modify trait values, modify them appropriately\n"
            "- If asked to filter/remove agents, exclude them from the output\n"
            "- If asked to translate, translate string values in traits\n"
            "- Maintain consistency across all agents\n"
            "- Preserve data types of traits (e.g., keep numbers as numbers)\n"
            "- Be creative but realistic when generating new trait values\n"
        )

        user_prompt = {
            "task": "Edit the following agent list",
            "current_agents": current_agents,
            "edit_instructions": edit_instructions,
            "instructions": (
                "Apply the requested edits to the agent list. "
                "Return the complete edited agent list with all agents that should remain. "
                "Ensure all agents maintain proper structure with a 'traits' dictionary "
                "and optionally a 'name' field. "
                "Return ONLY a valid JSON object with an 'agents' key containing an array of agent objects. "
                "Each agent object must have a 'traits' key (object) and optionally a 'name' key (string)."
            ),
        }

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            response_format={"type": "json_object"},
            temperature=self.temperature,
        )

        # Parse the JSON response
        result = json.loads(resp.choices[0].message.content)
        return result


# ---------- 3) Example usage ----------
if __name__ == "__main__":
    editor = AgentVibeEdit(model="gpt-4o", temperature=0.7)

    # Example agent list to edit
    original_agents = [
        {
            "traits": {"age": 25, "occupation": "student", "city": "Boston"},
            "name": "Alice",
        },
        {
            "traits": {"age": 30, "occupation": "engineer", "city": "San Francisco"},
            "name": "Bob",
        },
        {
            "traits": {"age": 28, "occupation": "teacher", "city": "New York"},
            "name": "Charlie",
        },
    ]

    # Example 1: Make all agents older
    print("Example 1: Make all agents 10 years older")
    result1 = editor.edit_agent_list(original_agents, "Make all agents 10 years older")
    print(json.dumps(result1, indent=2))
    print()

    # Example 2: Add a new trait
    print("Example 2: Add education level trait")
    result2 = editor.edit_agent_list(
        original_agents,
        "Add an 'education_level' trait to all agents with appropriate values",
    )
    print(json.dumps(result2, indent=2))
    print()

    # Example 3: Filter agents
    print("Example 3: Keep only agents over 27")
    result3 = editor.edit_agent_list(original_agents, "Remove agents under age 27")
    print(json.dumps(result3, indent=2))
