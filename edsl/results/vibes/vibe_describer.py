"""
Results Vibe Describer: Generate descriptive titles and descriptions for Results objects.

This module provides a VibeDescribe class that analyzes a Results object (including
Survey, AgentList, and ScenarioList) and generates a descriptive title and detailed
description of what the research/study is about.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
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


# ---------- 1) Pydantic schema for results description ----------
class ResultsDescriptionSchema(BaseModel):
    """
    Schema for a Results object description.

    Attributes
    ----------
    proposed_title : str
        A single sentence title that captures the essence of the research/study
    description : str
        A paragraph-length description of what the research is about
    """

    proposed_title: str = Field(
        description="A single sentence title that captures the essence of the research study"
    )
    description: str = Field(
        description="A paragraph-length description explaining what the research is about, its purpose, and what it investigates"
    )


# ---------- 2) The main describer class ----------
@dataclass
class VibeDescribe:
    """
    Generate descriptive titles and descriptions for Results objects.

    This class uses an LLM to analyze a Results object (including Survey, AgentList,
    and ScenarioList) and generate a descriptive title and detailed description
    of what the research/study is about.

    Parameters
    ----------
    model : str
        The OpenAI model to use for generation (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.7)

    Examples
    --------
    >>> describer = VibeDescribe()  # doctest: +SKIP
    >>> result = describer.describe_results(...)  # doctest: +SKIP
    >>> print(result["proposed_title"])  # doctest: +SKIP
    >>> print(result["description"])  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.7

    def __post_init__(self):
        self.client = (
            create_openai_client()
        )  # reads OPENAI_API_KEY from env with proper error handling

    def describe_survey(
        self,
        questions: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Generate a title and description for a survey.

        This method maintains compatibility with the original survey describe functionality.

        Parameters
        ----------
        questions : List[Dict[str, Any]]
            List of question dictionaries from the survey. Each question
            dict should have keys: question_name, question_text, question_type,
            and optionally question_options.

        Returns
        -------
        dict
            Dictionary with keys:
            - "proposed_title": A single sentence title for the survey
            - "description": A paragraph-length description of the survey
        """
        system = (
            "You are an expert survey analyst and copywriter. "
            "Given a set of survey questions, your task is to analyze the survey and generate: "
            "\n\n"
            "1. A clear, concise title (single sentence) that captures the essence of the survey\n"
            "2. A detailed description (paragraph length) that explains:\n"
            "   - What the survey is about\n"
            "   - What topics it covers\n"
            "   - What insights or information it aims to gather\n"
            "   - Who might be the intended audience or respondents\n"
            "\n"
            "Guidelines for the title:\n"
            "- Should be a single sentence (not a fragment)\n"
            "- Should be clear and informative\n"
            "- Should capture the main purpose or theme\n"
            "- Should be suitable as a survey title or heading\n"
            "\n"
            "Guidelines for the description:\n"
            "- Should be one paragraph (3-5 sentences)\n"
            "- Should provide context about the survey's purpose\n"
            "- Should mention the key topics or themes covered\n"
            "- Should be written in a professional, neutral tone\n"
            "- Should help potential respondents understand what to expect\n"
        )

        user_prompt = {
            "task": "Analyze this survey and generate a title and description",
            "survey_questions": questions,
            "instructions": (
                "Based on the questions provided, generate a descriptive title and detailed description "
                "that accurately captures what this survey is about and what it aims to measure or understand."
            ),
        }

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            text_format=ResultsDescriptionSchema,
            temperature=self.temperature,
        )

        out = resp.output_parsed
        # Convert Pydantic model to dict
        return out.model_dump()

    def describe_results(
        self,
        questions: List[Dict[str, Any]],
        agents_info: Dict[str, Any],
        scenarios_info: Dict[str, Any],
        results_stats: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Generate a title and description for a Results object.

        This method analyzes the complete Results object including the survey questions,
        agent information, scenarios, and results statistics to provide a comprehensive
        description of the research study.

        Parameters
        ----------
        questions : List[Dict[str, Any]]
            List of question dictionaries from the survey
        agents_info : Dict[str, Any]
            Information about the agents including number and traits
        scenarios_info : Dict[str, Any]
            Information about scenarios including number and examples
        results_stats : Dict[str, Any]
            Basic statistics about the results

        Returns
        -------
        dict
            Dictionary with keys:
            - "proposed_title": A single sentence title for the results
            - "description": A paragraph-length description of the results
        """
        system = (
            "You are an expert research analyst and copywriter. "
            "Given information about a research study that includes survey questions, "
            "agent/participant information, scenarios, and results statistics, your task is to analyze "
            "the study and generate: "
            "\n\n"
            "1. A clear, concise title (single sentence) that captures the essence of the research study\n"
            "2. A detailed description (paragraph length) that explains:\n"
            "   - What the research study is about\n"
            "   - What topics or phenomena it investigates\n"
            "   - What kind of participants/agents were involved\n"
            "   - What scenarios or conditions were tested\n"
            "   - What insights or knowledge it aims to generate\n"
            "\n"
            "Guidelines for the title:\n"
            "- Should be a single sentence (not a fragment)\n"
            "- Should be clear and informative\n"
            "- Should capture the main research purpose or theme\n"
            "- Should sound like a research study title\n"
            "- Can reference the type of study (survey, experiment, analysis, etc.)\n"
            "\n"
            "Guidelines for the description:\n"
            "- Should be one paragraph (4-6 sentences)\n"
            "- Should provide context about the research purpose and design\n"
            "- Should mention the key topics or constructs being studied\n"
            "- Should describe the participants/agents and scenarios if relevant\n"
            "- Should be written in a professional, academic tone\n"
            "- Should help readers understand the scope and nature of the research\n"
        )

        user_prompt = {
            "task": "Analyze this research study and generate a title and description",
            "survey_questions": questions,
            "agents_info": agents_info,
            "scenarios_info": scenarios_info,
            "results_stats": results_stats,
            "instructions": (
                "Based on all the information provided about this research study "
                "(including survey questions, agent/participant details, scenarios, and results statistics), "
                "generate a descriptive title and detailed description that accurately captures "
                "what this research is about and what it investigates."
            ),
        }

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            text_format=ResultsDescriptionSchema,
            temperature=self.temperature,
        )

        out = resp.output_parsed
        # Convert Pydantic model to dict
        return out.model_dump()


# ---------- 3) Example usage ----------
if __name__ == "__main__":
    describer = VibeDescribe(model="gpt-4o", temperature=0.7)

    # Example results data
    sample_questions = [
        {
            "question_name": "satisfaction",
            "question_text": "How satisfied are you with our product?",
            "question_type": "multiple_choice",
            "question_options": [
                "Very satisfied",
                "Satisfied",
                "Neutral",
                "Dissatisfied",
                "Very dissatisfied",
            ],
        },
        {
            "question_name": "recommendation",
            "question_text": "Would you recommend us to a friend?",
            "question_type": "yes_no",
        },
    ]

    sample_agents_info = {
        "num_agents": 3,
        "agent_traits": [
            {"name": "Alice", "traits": {"age": 25, "occupation": "student"}},
            {"name": "Bob", "traits": {"age": 35, "occupation": "teacher"}},
            {"name": "Carol", "traits": {"age": 45, "occupation": "engineer"}},
        ],
    }

    sample_scenarios_info = {
        "num_scenarios": 2,
        "scenario_examples": [
            {"context": "morning", "mood": "happy"},
            {"context": "evening", "mood": "tired"},
        ],
    }

    sample_results_stats = {
        "num_observations": 6,
        "num_questions": 2,
        "question_names": ["satisfaction", "recommendation"],
    }

    # Generate description
    result = describer.describe_results(
        sample_questions,
        sample_agents_info,
        sample_scenarios_info,
        sample_results_stats,
    )
    print("Title:", result["proposed_title"])
    print("\nDescription:", result["description"])
