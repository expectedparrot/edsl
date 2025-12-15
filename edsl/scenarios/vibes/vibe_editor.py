"""
ScenarioList Vibe Editor for intelligent scenario modification using LLMs.

This module provides the ScenarioListVibeEdit class that uses LLMs to intelligently
edit and modify scenarios based on natural language instructions.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import json


class ScenarioListVibeEdit:
    """
    LLM-powered editor for modifying ScenarioList data based on natural language instructions.

    This class can clean up data, remove unwanted elements, standardize formats,
    and apply various transformations to scenario data using intelligent LLM processing.
    """

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.1):
        """
        Initialize the vibe editor.

        Args:
            model: LLM model to use for editing operations
            temperature: Temperature for LLM calls (low for consistency)
        """
        self.model = model
        self.temperature = temperature
        self._client = None

    @property
    def client(self):
        """Get OpenAI client for LLM editing operations."""
        if self._client is None:
            from edsl.base.openai_utils import create_openai_client

            self._client = create_openai_client()
        return self._client

    def edit_scenario_list(
        self, scenarios: List[Dict[str, Any]], edit_instructions: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Edit a list of scenario dictionaries based on natural language instructions.

        Args:
            scenarios: List of scenario dictionaries to edit
            edit_instructions: Natural language instructions for how to edit the scenarios

        Returns:
            Dict with "scenarios" key containing edited scenarios (expected by vibe_accessor)

        Examples:
            >>> editor = ScenarioListVibeEdit()
            >>> result = editor.edit_scenario_list(
            ...     scenarios,
            ...     "Remove all citation marks and HTML tags, clean up text"
            ... )
            >>> edited_scenarios = result["scenarios"]
        """
        if not scenarios:
            return {"scenarios": []}

        # Process in batches to handle large scenario lists
        batch_size = 10
        edited_scenarios = []

        for i in range(0, len(scenarios), batch_size):
            batch = scenarios[i : i + batch_size]
            edited_batch = self._edit_scenario_batch(batch, edit_instructions)
            edited_scenarios.extend(edited_batch)

        return {"scenarios": edited_scenarios}

    def _edit_scenario_batch(
        self, scenario_batch: List[Dict[str, Any]], edit_instructions: str
    ) -> List[Dict[str, Any]]:
        """
        Edit a batch of scenarios using LLM.

        Args:
            scenario_batch: Batch of scenarios to edit
            edit_instructions: Instructions for editing

        Returns:
            List of edited scenarios
        """
        system_prompt = """You are an expert data cleaner and editor. You receive scenario data and instructions on how to clean and modify it.

Your tasks:
1. Follow the user's editing instructions precisely
2. Clean up any unwanted formatting, citations, HTML tags, etc. as requested
3. Maintain the essential data structure and information
4. Keep all fields that aren't explicitly mentioned for removal
5. Ensure consistent formatting across all scenarios
6. Preserve the original keys/field names unless instructed otherwise

Return the edited scenarios as a JSON array in the same structure as provided."""

        # Format the scenarios for the LLM
        scenarios_json = json.dumps(scenario_batch, indent=2, ensure_ascii=False)

        user_prompt = f"""Please edit these scenarios according to the instructions: "{edit_instructions}"

Original scenarios:
{scenarios_json}

Return the edited scenarios as a JSON array. Preserve all the original keys and structure while applying the requested changes.

Respond with a JSON object in this format:
{{
    "scenarios": [
        // ... edited scenario objects here
    ]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )

            response_content = response.choices[0].message.content

            # Parse the JSON response
            result = json.loads(response_content)

            # Extract scenarios from the response
            if isinstance(result, dict) and "scenarios" in result:
                return result["scenarios"]
            elif isinstance(result, list):
                # Direct list of scenarios
                return result
            else:
                # Fallback: return original scenarios if parsing fails
                print(f"⚠️ Unexpected response format, returning original scenarios")
                return scenario_batch

        except Exception as e:
            print(f"⚠️ Vibe edit failed: {e}, returning original scenarios")
            return scenario_batch

    def clean_wikipedia_data(
        self, scenarios: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Specialized method for cleaning Wikipedia-sourced data.

        Args:
            scenarios: List of scenarios with Wikipedia data

        Returns:
            Cleaned scenarios
        """
        instructions = """Clean up Wikipedia data by:
1. Remove all citation marks like [1], [2], [citation needed], etc.
2. Remove HTML tags and entities like &nbsp;, <sup>, </sup>, etc.
3. Clean up any Wikipedia-specific formatting artifacts
4. Standardize text formatting and remove extra whitespace
5. Keep all the actual data content intact"""

        return self.edit_scenario_list(scenarios, instructions)

    def standardize_formats(
        self, scenarios: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Standardize formats across scenarios.

        Args:
            scenarios: List of scenarios to standardize

        Returns:
            Standardized scenarios
        """
        instructions = """Standardize the data formats by:
1. Ensure consistent date formats (YYYY-MM-DD where possible)
2. Standardize currency formats and remove currency symbols if inconsistent
3. Clean up company names and remove extra corporate suffixes if redundant
4. Ensure consistent capitalization
5. Remove any duplicate or redundant information"""

        return self.edit_scenario_list(scenarios, instructions)

    def remove_empty_fields(
        self, scenarios: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove fields that are empty, null, or contain only whitespace.

        Args:
            scenarios: List of scenarios to clean

        Returns:
            Cleaned scenarios with empty fields removed
        """
        cleaned_scenarios = []

        for scenario in scenarios:
            cleaned_scenario = {}
            for key, value in scenario.items():
                # Keep field if it has meaningful content
                if (
                    value is not None
                    and str(value).strip()
                    and str(value).strip() != "nan"
                ):
                    cleaned_scenario[key] = value
            cleaned_scenarios.append(cleaned_scenario)

        return cleaned_scenarios
