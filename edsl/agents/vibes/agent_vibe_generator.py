"""
Agent Generator: Generate agent populations from natural language descriptions using LLMs.

This module provides an AgentGenerator class that can create collections of agents
with appropriate traits based on a natural language description of a population.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from openai import OpenAI
import os
import json
from dotenv import load_dotenv
from pathlib import Path


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
        env_file = current / '.env'
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


# ---------- 1) Pydantic schema for agent definition ----------
# OpenAI's structured output requires all fields to be defined explicitly
# We'll use a flexible approach with many optional fields

class AgentDefinition(BaseModel):
    """
    Schema for a single agent in a population.

    Uses predefined trait fields that cover most use cases.
    The LLM will populate relevant fields based on the population description.
    """
    # Identity fields
    name: Optional[str] = Field(None, description="Name of the agent (if applicable)")
    age: Optional[int] = Field(None, description="Age in years")
    gender: Optional[str] = Field(None, description="Gender identity")

    # Location fields
    location: Optional[str] = Field(None, description="City, state, or general location")
    hometown: Optional[str] = Field(None, description="Place of origin")

    # Professional fields
    occupation: Optional[str] = Field(None, description="Job title or occupation")
    industry: Optional[str] = Field(None, description="Industry or sector")
    years_experience: Optional[int] = Field(None, description="Years in current role or field")

    # Education fields
    education_level: Optional[str] = Field(None, description="Highest education level")
    major: Optional[str] = Field(None, description="Field of study or major")
    school: Optional[str] = Field(None, description="Educational institution")

    # Socioeconomic fields
    income: Optional[int] = Field(None, description="Annual income")
    income_bracket: Optional[str] = Field(None, description="Income range or bracket")

    # Demographic fields
    marital_status: Optional[str] = Field(None, description="Marital or relationship status")
    household_size: Optional[int] = Field(None, description="Number of people in household")
    children: Optional[int] = Field(None, description="Number of children")

    # Behavioral/Attitudinal fields
    political_affiliation: Optional[str] = Field(None, description="Political leaning or party")
    values: Optional[str] = Field(None, description="Core values or beliefs")
    interests: Optional[str] = Field(None, description="Hobbies or interests")
    personality: Optional[str] = Field(None, description="Personality traits")

    # Context-specific fields (can be adapted by LLM)
    trait_1: Optional[Union[str, int, float, bool]] = Field(None, description="Additional context-specific trait")
    trait_2: Optional[Union[str, int, float, bool]] = Field(None, description="Additional context-specific trait")
    trait_3: Optional[Union[str, int, float, bool]] = Field(None, description="Additional context-specific trait")
    trait_4: Optional[Union[str, int, float, bool]] = Field(None, description="Additional context-specific trait")
    trait_5: Optional[Union[str, int, float, bool]] = Field(None, description="Additional context-specific trait")
    trait_6: Optional[Union[str, int, float, bool]] = Field(None, description="Additional context-specific trait")
    trait_7: Optional[Union[str, int, float, bool]] = Field(None, description="Additional context-specific trait")
    trait_8: Optional[Union[str, int, float, bool]] = Field(None, description="Additional context-specific trait")

    model_config = {"extra": "forbid"}  # Required by OpenAI


class AgentPopulationSchema(BaseModel):
    """
    Schema for a population of agents.

    Attributes
    ----------
    agents : List[AgentDefinition]
        List of agent definitions that make up the population
    """
    agents: List[AgentDefinition] = Field(
        description="List of agents in the population, each with their own traits"
    )


# ---------- 2) The main generator class ----------
@dataclass
class AgentGenerator:
    """
    Generate agent populations from natural language descriptions.

    This class uses an LLM to generate appropriate agent traits based on
    a natural language description of a population. It automatically creates
    diverse, realistic agents with appropriate characteristics.

    Parameters
    ----------
    model : str
        The OpenAI model to use for generation (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.8 for more diversity)

    Examples
    --------
    >>> gen = AgentGenerator()  # doctest: +SKIP
    >>> result = gen.generate_agents("College students studying computer science")  # doctest: +SKIP
    >>> print(json.dumps(result, indent=2))  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.8  # Higher temperature for more diverse agents

    def __post_init__(self):
        self.client = OpenAI()  # reads OPENAI_API_KEY from env

    def generate_agents(
        self,
        description: str,
        *,
        num_agents: Optional[int] = None,
        traits: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate a population of agents based on a natural language description.

        Parameters
        ----------
        description : str
            Natural language description of the population.
            Examples:
            - "College students studying computer science"
            - "Small business owners in the Midwest"
            - "Retired professionals interested in travel"
            - "Healthcare workers during the pandemic"
        num_agents : int, optional
            Number of agents to generate. If not provided, will be determined
            automatically based on the population (typically 5-10).
        traits : List[str], optional
            Specific trait names to include for each agent. If not provided,
            appropriate traits will be inferred from the population description.
            Examples: ["age", "occupation", "education_level", "income_bracket"]

        Returns
        -------
        dict
            Dictionary with an "agents" key containing a list of agent dictionaries.
            Each agent dict has a "traits" key with trait name-value pairs, and
            optionally a "name" key.

        Examples
        --------
        >>> gen = AgentGenerator(model="gpt-4o", temperature=0.8)  # doctest: +SKIP
        >>> result = gen.generate_agents("College students studying computer science")  # doctest: +SKIP
        >>> result["agents"][0]["traits"].keys()  # doctest: +SKIP
        dict_keys(['age', 'major', 'year', 'gpa', ...])  # doctest: +SKIP
        """
        system = (
            "You are an expert at creating realistic, diverse populations of people for research and testing. "
            "Given a description of a population, create specific individuals who MATCH that exact description. "
            "\n\n"
            "CRITICAL: Create agents that fit the EXACT population described.\n"
            "- 'Potential customers for a dental practice CRM' = dentists, practice managers, dental office administrators\n"
            "- 'College students' = undergraduate or graduate students currently enrolled\n"
            "- 'Small business owners' = people who own and operate small businesses\n"
            "- 'Retired professionals' = people who have retired from their careers\n"
            "\n"
            "AVAILABLE TRAIT FIELDS:\n"
            "You have predefined fields to populate for each agent. Fill in the relevant ones based on the population:\n"
            "- Identity: name, age, gender\n"
            "- Location: location, hometown\n"
            "- Professional: occupation, industry, years_experience\n"
            "- Education: education_level, major, school\n"
            "- Socioeconomic: income, income_bracket\n"
            "- Demographic: marital_status, household_size, children\n"
            "- Behavioral/Attitudinal: political_affiliation, values, interests, personality\n"
            "- Context-specific: trait_1 through trait_8 for population-specific attributes\n"
            "\n"
            "For trait_1 through trait_8, provide ACTUAL VALUES for population-specific attributes:\n"
            "Examples:\n"
            "- Dental practice customers: trait_1 = 'General dentistry' (practice type), trait_2 = 8 (staff size), "
            "trait_3 = 'Paper records' (current system), trait_4 = 2500 (patients), trait_5 = 'High' (tech comfort)\n"
            "- College students: trait_1 = 3.8 (GPA), trait_2 = 'Junior' (year), trait_3 = 'Dorm' (living situation), "
            "trait_4 = 'Coding club' (extracurriculars)\n"
            "- Small business owners: trait_1 = 'Coffee shop' (business type), trait_2 = 5 (years in business), "
            "trait_3 = 3 (employees), trait_4 = 250000 (annual revenue)\n"
            "\n"
            "DO NOT use field names as values. Provide actual data that describes the individual.\n"
            "\n"
            "For each agent, determine:\n"
            "1. Which predefined fields are relevant for this SPECIFIC population\n"
            "2. Realistic, varied values that create diverse individuals WHO FIT THE DESCRIPTION\n"
            "3. Use trait_1 through trait_8 for population-specific attributes\n"
            "\n"
            "GUIDELINES FOR CREATING AGENTS:\n"
            "================================\n"
            "\n"
            "1. TRAIT SELECTION:\n"
            "   - Choose traits that are relevant to the population description\n"
            "   - Include demographic traits (age, gender, location, etc.) when appropriate\n"
            "   - Include behavioral/attitudinal traits when relevant\n"
            "   - Use 5-10 traits per agent for good characterization\n"
            "   - Keep trait names descriptive but concise (snake_case preferred)\n"
            "\n"
            "2. TRAIT VALUES:\n"
            "   - Use appropriate data types: strings, numbers, booleans, lists\n"
            "   - Make values realistic and specific (not generic)\n"
            "   - Create diversity: vary ages, backgrounds, perspectives, etc.\n"
            "   - Avoid stereotypes: create nuanced, complex individuals\n"
            "   - Be specific: '28' not 'late 20s', 'Brooklyn' not 'New York area'\n"
            "\n"
            "3. POPULATION DIVERSITY:\n"
            "   - Ensure agents have meaningful variation\n"
            "   - Represent different perspectives within the population\n"
            "   - Include edge cases and outliers (within reason)\n"
            "   - Balance demographic representation appropriately\n"
            "\n"
            "4. TRAIT CONSISTENCY:\n"
            "   - All agents should have the same set of trait names\n"
            "   - Use consistent data types for each trait across agents\n"
            "   - Maintain logical consistency (e.g., retirement age vs occupation)\n"
            "\n"
            "5. NAMING:\n"
            "   - Use the 'name_trait' field for agent names (optional)\n"
            "   - Provide names only if it adds value\n"
            "   - Names should reflect appropriate cultural/demographic context\n"
            "   - Use realistic, diverse names\n"
            "\n"
            "EXAMPLES OF GOOD TRAIT SETS:\n"
            "\n"
            "For 'College students':\n"
            "- age, major, year_in_school, gpa, hometown, living_situation, part_time_job, \n"
            "  student_debt, extracurriculars, career_goals\n"
            "\n"
            "For 'Small business owners':\n"
            "- age, business_type, years_in_business, num_employees, annual_revenue, \n"
            "  location, education_level, industry_experience, challenges, growth_goals\n"
            "\n"
            "For 'Voters in swing state':\n"
            "- age, political_affiliation, education_level, occupation, household_income, \n"
            "  location, voting_frequency, key_issues, media_sources, previous_vote\n"
            "\n"
            "TRAIT VALUE EXAMPLES:\n"
            "- age: 34 (not '30s' or 'mid-30s')\n"
            "- location: 'Phoenix, AZ' (not 'Southwest' or 'Arizona')\n"
            "- occupation: 'High school math teacher' (not 'Education')\n"
            "- income_bracket: '75000-90000' or 75000 (not 'middle class')\n"
            "- political_affiliation: 'Independent, leans left' (not just 'Independent')\n"
        )

        user_prompt = {
            "task": "Generate a diverse population of agents",
            "description": description,
        }

        if traits:
            user_prompt["required_traits"] = traits
            user_prompt["instructions_traits"] = (
                f"Each agent MUST have exactly these traits: {', '.join(traits)}. "
                "Provide realistic, varied values for each trait."
            )
        else:
            user_prompt["instructions_traits"] = (
                "Infer appropriate traits based on the population description. "
                "Ensure all agents have the same set of traits."
            )

        if num_agents:
            user_prompt["num_agents"] = num_agents
            user_prompt["instructions_count"] = (
                f"Generate exactly {num_agents} distinct agents. "
                "Ensure meaningful diversity across the population."
            )
        else:
            user_prompt["instructions_count"] = (
                "Generate an appropriate number of agents (typically 5-10) "
                "to represent diversity in this population."
            )

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            text_format=AgentPopulationSchema,
            temperature=self.temperature,
        )

        out = resp.output_parsed
        # Convert Pydantic models to dicts and restructure as traits
        agents_list = []
        for agent_def in out.agents:
            agent_dict = agent_def.model_dump(exclude_none=True)

            # Extract name if present
            agent_name = agent_dict.pop("name", None)

            # Everything else becomes traits (excluding None values)
            traits = {k: v for k, v in agent_dict.items() if v is not None}

            agents_list.append({
                "traits": traits,
                "name": agent_name
            })

        return {"agents": agents_list}


# ---------- 3) Example usage ----------
if __name__ == "__main__":
    gen = AgentGenerator(model="gpt-4o", temperature=0.8)

    # Example 1: College students
    print("Example 1: College students studying computer science")
    result1 = gen.generate_agents("College students studying computer science")
    print(json.dumps(result1, indent=2))
    print()

    # Example 2: Small business owners
    print("Example 2: Small business owners in the Midwest")
    result2 = gen.generate_agents(
        "Small business owners in the Midwest",
        num_agents=6
    )
    print(json.dumps(result2, indent=2))
    print()

    # Example 3: Specific traits
    print("Example 3: Voters with specific traits")
    result3 = gen.generate_agents(
        "Voters in a swing state",
        traits=["age", "political_affiliation", "education_level", "key_issue"],
        num_agents=5
    )
    print(json.dumps(result3, indent=2))
