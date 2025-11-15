"""
ScenarioList Vibe Extractor: Extract table data from HTML and convert to scenarios.

This module provides a VibeExtract class that analyzes HTML content containing
tables and extracts structured data to create a ScenarioList.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List
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


# ---------- 1) Pydantic schema for extracted table data ----------
from typing import Union

class ExtractedTableSchema(BaseModel):
    """
    Schema for extracted table data from HTML.

    Attributes
    ----------
    headers : List[str]
        List of column headers extracted from the table
    rows_data : str
        JSON string containing list of row dictionaries (needed for OpenAI structured outputs)
    notes : str
        Any relevant notes or observations about the table structure or data
    """

    headers: List[str] = Field(
        description="List of column headers from the table (should be valid variable names in snake_case)"
    )
    rows_data: str = Field(
        description="JSON string containing a list of dictionaries, where each dictionary represents a row with keys matching the headers and values being the cell data (use appropriate types: strings, numbers, booleans, or null)"
    )
    notes: str = Field(
        default="",
        description="Any notes about data quality, missing values, or extraction issues"
    )


# ---------- 2) The main extractor class ----------
@dataclass
class VibeExtract:
    """
    Extract table data from HTML and convert to structured scenarios.

    This class uses an LLM to analyze HTML content containing tables and
    extract structured data that can be used to create EDSL scenarios.

    Parameters
    ----------
    model : str
        The OpenAI model to use for extraction (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.0 for more consistent extraction)

    Examples
    --------
    >>> extractor = VibeExtract()  # doctest: +SKIP
    >>> result = extractor.extract_table_from_html(html_content)  # doctest: +SKIP
    >>> scenarios = result["scenarios"]  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.0  # Lower temp for more consistent extraction

    def __post_init__(self):
        self.client = create_openai_client()

    def extract_table_from_html(
        self,
        html_content: str,
        instructions: str = "",
        max_rows: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Extract table data from HTML content.

        Parameters
        ----------
        html_content : str
            HTML content containing one or more tables
        instructions : str, optional
            Additional instructions for the extraction (e.g., "Extract only the first table",
            "Ignore the footer row", etc.)

        Returns
        -------
        dict
            Dictionary containing:
            - "scenarios": List of dictionaries, one per row
            - "headers": List of column headers
            - "notes": Any extraction notes
            - "num_scenarios": Number of scenarios extracted

        Examples
        --------
        >>> extractor = VibeExtract(model="gpt-4o", temperature=0.0)  # doctest: +SKIP
        >>> html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"  # doctest: +SKIP
        >>> result = extractor.extract_table_from_html(html)  # doctest: +SKIP
        >>> result["scenarios"]  # doctest: +SKIP
        [{"name": "Alice", "age": 30}]
        """
        max_rows_instruction = f"\n- Extract up to {max_rows} rows" if max_rows else "\n- Extract ALL rows from the table (IMPORTANT: do not truncate or limit the number of rows)"

        system = (
            "You are an expert data extraction specialist. "
            "Given HTML content containing a table, your task is to: "
            "\n\n"
            "1. Identify the table structure (headers and rows)\n"
            "2. Extract ALL data from the table (every single row)\n"
            "3. Clean and normalize the column headers to be valid variable names (lowercase, underscores)\n"
            "4. Convert data to appropriate types (numbers, strings, etc.)\n"
            "5. Return each row as a dictionary mapping headers to values\n"
            "6. Note any issues or observations about the data\n"
            "\n"
            "CRITICAL: You MUST extract EVERY row from the table. Do not truncate or summarize.\n"
            "If the HTML is too large and you cannot see all rows, note this in the 'notes' field.\n"
            "\n"
            "Guidelines:\n"
            "- Headers should be lowercase with underscores (snake_case)\n"
            "- Remove any special characters from headers\n"
            "- Each row should be a dictionary where keys match the headers\n"
            "- Preserve the original data values as much as possible\n"
            "- If a value looks like a number, extract it as a number (int or float)\n"
            "- If a value is clearly boolean (yes/no, true/false), extract as boolean\n"
            "- If there are multiple tables, extract the most relevant/largest one (or follow user instructions)"
            + max_rows_instruction + "\n"
            "- Note any missing values, formatting issues, or ambiguities\n"
            "- In the notes field, include the total number of rows you were able to extract\n"
        )

        user_prompt = {
            "task": "Extract table data from the following HTML",
            "html_content": html_content,
        }

        if instructions:
            user_prompt["additional_instructions"] = instructions

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            text_format=ExtractedTableSchema,
            temperature=self.temperature,
        )

        extracted = resp.output_parsed

        # Parse the JSON string containing row data
        scenarios = json.loads(extracted.rows_data)

        return {
            "scenarios": scenarios,
            "headers": extracted.headers,
            "notes": extracted.notes,
            "num_scenarios": len(scenarios),
        }


# ---------- 3) Example usage ----------
if __name__ == "__main__":
    extractor = VibeExtract(model="gpt-4o", temperature=0.0)

    # Example HTML with a table
    sample_html = """
    <html>
    <body>
        <h1>Customer Data</h1>
        <table>
            <tr>
                <th>Name</th>
                <th>Age</th>
                <th>City</th>
                <th>Purchases</th>
            </tr>
            <tr>
                <td>Alice Johnson</td>
                <td>30</td>
                <td>New York</td>
                <td>5</td>
            </tr>
            <tr>
                <td>Bob Smith</td>
                <td>25</td>
                <td>San Francisco</td>
                <td>12</td>
            </tr>
            <tr>
                <td>Charlie Brown</td>
                <td>35</td>
                <td>Los Angeles</td>
                <td>8</td>
            </tr>
        </table>
    </body>
    </html>
    """

    # Extract table
    result = extractor.extract_table_from_html(sample_html)
    print(f"Extracted {result['num_scenarios']} scenarios")
    print(f"Headers: {result['headers']}")
    print(f"Scenarios: {json.dumps(result['scenarios'], indent=2)}")
    print(f"Notes: {result['notes']}")
