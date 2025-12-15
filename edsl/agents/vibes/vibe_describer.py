"""
AgentList Vibe Describer: Generate descriptive titles and descriptions for agent lists.

This module provides a AgentListVibeDescribe class that analyzes an agent list and generates
a descriptive title and detailed description of what the agent list represents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
from pydantic import BaseModel, Field
import os
import json
from dotenv import load_dotenv
from pathlib import Path
from ...base.openai_utils import create_openai_client


def find_dotenv_upwards(start_path: str | None = None) -> Path | None:
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


# ---------- 1) Pydantic schema for agent list description ----------
class AgentListDescriptionSchema(BaseModel):
    """
    Schema for an agent list description.

    Attributes
    ----------
    proposed_title : str
        A single sentence title that captures the essence of the agent list
    description : str
        A paragraph-length description of what the agent list represents
    """

    proposed_title: str = Field(
        description="A single sentence title that captures the essence of the agent list"
    )
    description: str = Field(
        description="A paragraph-length description explaining what the agent list represents, its purpose, and what agents it contains"
    )


# ---------- 2) The main describer class ----------
@dataclass
class AgentListVibeDescribe:
    """
    Generate descriptive titles and descriptions for agent lists.

    This class uses an LLM to analyze an agent list and generate a descriptive
    title and detailed description of what the agent list represents.

    Parameters
    ----------
    model : str
        The OpenAI model to use for generation (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.7)

    Examples
    --------
    >>> describer = AgentListVibeDescribe()  # doctest: +SKIP
    >>> result = describer.describe_agent_list(agent_data)  # doctest: +SKIP
    >>> print(result["proposed_title"])  # doctest: +SKIP
    >>> print(result["description"])  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.7

    def __post_init__(self):
        self.client = (
            create_openai_client()
        )  # reads OPENAI_API_KEY from env with proper error handling

    def describe_agent_list(
        self,
        agent_data: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Generate a title and description for an agent list.

        Parameters
        ----------
        agent_data : Dict[str, Any]
            Dictionary containing:
            - "agents": List of agent information (traits, instructions, etc.)
            - "num_agents": Number of agents in the list
            - "agent_names": List of agent names (if available)
            - "traits": Summary of traits across agents

        Returns
        -------
        dict
            Dictionary with keys:
            - "proposed_title": A single sentence title for the agent list
            - "description": A paragraph-length description of the agent list

        Examples
        --------
        >>> describer = AgentListVibeDescribe(model="gpt-4o", temperature=0.7)  # doctest: +SKIP
        >>> data = {  # doctest: +SKIP
        ...     "agents": [...],  # doctest: +SKIP
        ...     "num_agents": 5,  # doctest: +SKIP
        ...     "agent_names": ["Alice", "Bob", "Charlie"],  # doctest: +SKIP
        ...     "traits": {...}  # doctest: +SKIP
        ... }  # doctest: +SKIP
        >>> result = describer.describe_agent_list(data)  # doctest: +SKIP
        >>> result["proposed_title"]  # doctest: +SKIP
        'Diverse Agent Collection for Survey Research'
        """
        system = (
            "You are an expert data analyst and copywriter. "
            "Given information about an agent list (a collection of AI agents with different personas), "
            "your task is to analyze the agents and generate: "
            "\n\n"
            "1. A clear, concise title (single sentence) that captures the essence of the agent list\n"
            "2. A detailed description (paragraph length) that explains:\n"
            "   - What the agent list represents\n"
            "   - What types of agents it contains\n"
            "   - What purpose or use case it serves\n"
            "   - What patterns or themes are evident in the agent personas\n"
            "\n"
            "Guidelines for the title:\n"
            "- Should be a single sentence (not a fragment)\n"
            "- Should be clear and informative\n"
            "- Should capture the main theme or purpose of the agents\n"
            "- Should be suitable as a dataset title or heading\n"
            "\n"
            "Guidelines for the description:\n"
            "- Should be one paragraph (3-5 sentences)\n"
            "- Should provide context about what the agent list represents\n"
            "- Should mention the key characteristics or traits of the agents\n"
            "- Should explain what the agents could be used for\n"
            "- Should be written in a professional, neutral tone\n"
            "- Should help users understand the nature and scope of the agent collection\n"
        )

        user_prompt = {
            "task": "Analyze this agent list and generate a title and description",
            "agent_list_data": agent_data,
            "instructions": (
                "Based on the agents, their traits, names, and characteristics provided, generate a descriptive title "
                "and detailed description that accurately captures what this agent list represents "
                "and what it could be used for."
            ),
        }

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            text_format=AgentListDescriptionSchema,
            temperature=self.temperature,
        )

        out = resp.output_parsed
        # Convert Pydantic model to dict
        return out.model_dump()


# ---------- 3) Example usage ----------
if __name__ == "__main__":
    describer = AgentListVibeDescribe(model="gpt-4o", temperature=0.7)

    # Example agent list data
    sample_data = {
        "agents": [
            {
                "name": "Conservative Voter",
                "traits": {"political_leaning": "conservative", "age": "65"},
                "instructions": "Act as a conservative voter concerned about traditional values",
            },
            {
                "name": "Liberal Student",
                "traits": {"political_leaning": "liberal", "age": "22"},
                "instructions": "Act as a progressive college student interested in social justice",
            },
        ],
        "num_agents": 2,
        "agent_names": ["Conservative Voter", "Liberal Student"],
        "traits": {
            "political_leaning": ["conservative", "liberal"],
            "age": ["65", "22"],
        },
    }

    # Generate description
    result = describer.describe_agent_list(sample_data)
    print("Title:", result["proposed_title"])
    print("\nDescription:", result["description"])
