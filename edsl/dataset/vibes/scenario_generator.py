from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
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


# ---------- 1) Pydantic schema for schema inference step ----------
class SchemaDefinition(BaseModel):
    fields: List[str] = Field(
        description="List of field names that should be included in each scenario dictionary"
    )
    count: int = Field(description="Number of scenarios to generate", default=10)


# ---------- 2) Pydantic schema for data generation step ----------
# Note: We'll create dynamic models at runtime based on the inferred fields


# ---------- 3) The main generator class ----------
@dataclass
class ScenarioGenerator:
    model: str = "gpt-4o"
    temperature: float = 0.7

    def __post_init__(self):
        self.client = OpenAI()  # reads OPENAI_API_KEY from env

    def _create_dynamic_schema(self, fields: List[str]) -> type[BaseModel]:
        """
        Create a dynamic Pydantic model based on the specified fields.

        Parameters
        ----------
        fields : List[str]
            List of field names for the scenario

        Returns
        -------
        type[BaseModel]
            A dynamically created Pydantic model class
        """
        # Create field definitions - all fields are strings by default
        field_definitions = {
            field: (str, Field(description=f"The {field} value")) for field in fields
        }

        # Create the scenario item model
        ScenarioItem = type(
            "ScenarioItem",
            (BaseModel,),
            {
                "__annotations__": {k: v[0] for k, v in field_definitions.items()},
                **{k: v[1] for k, v in field_definitions.items()},
                "model_config": {"extra": "forbid"},
            },
        )

        # Create the reply model with a list of scenario items
        ScenariosReply = type(
            "ScenariosReply",
            (BaseModel,),
            {
                "__annotations__": {"scenarios": List[ScenarioItem]},
                "scenarios": Field(
                    description="List of scenario dictionaries with the specified fields"
                ),
                "model_config": {"extra": "forbid"},
            },
        )

        return ScenariosReply

    def _infer_schema(self, user_request: str) -> SchemaDefinition:
        """
        Infer the field names and count from the user's natural language request.

        Parameters
        ----------
        user_request : str
            Natural language description like "Give me 20 fruits" or "Fruits and their colors"

        Returns
        -------
        SchemaDefinition
            Parsed schema with field names and count
        """
        system = (
            "You are an expert at understanding data structure requests. "
            "Given a natural language description, determine what field names should be in each dictionary "
            "and how many items to generate. "
            "For example: 'Give me 20 fruits' -> fields=['fruit'], count=20. "
            "'Fruits and their colors' -> fields=['fruit', 'color'], count=10 (default). "
            "'5 countries with capitals and populations' -> fields=['country', 'capital', 'population'], count=5."
        )

        user = {
            "request": user_request,
            "task": "Determine the field names and count for the requested scenarios.",
        }

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, indent=2)},
            ],
            text_format=SchemaDefinition,
            temperature=0.1,  # Low temperature for consistent schema inference
        )

        return resp.output_parsed

    def generate_scenarios(
        self,
        user_request: str,
        *,
        count: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate structured scenario data based on a natural language request.

        Parameters
        ----------
        user_request : str
            Natural language description of what scenarios to generate.
            Examples:
            - "Give me 20 fruits"
            - "Fruits and their colors"
            - "Countries with their capitals and populations"
            - "Researchers studying different topics"
        count : int, optional
            Override the number of scenarios to generate. If not provided,
            will be inferred from the request or default to 10.
        fields : List[str], optional
            Override the field names. If not provided, will be inferred from the request.

        Returns
        -------
        dict
            Dictionary with a "scenarios" key containing a list of generated dictionaries.
            Example: {"scenarios": [{"fruit": "Apple"}, {"fruit": "Banana"}, ...]}
        """
        # Step 1: Infer schema if not provided
        if fields is None or count is None:
            schema_def = self._infer_schema(user_request)
            if fields is None:
                fields = schema_def.fields
            if count is None:
                count = schema_def.count

        # Step 2: Create dynamic schema based on inferred fields
        ScenariosReply = self._create_dynamic_schema(fields)

        # Step 3: Generate the actual data
        system = (
            "You are an expert data generator. "
            "Generate realistic, diverse, and appropriate data based on the user's request. "
            "Each scenario should be a dictionary with the specified fields. "
            "Make the data varied and interesting. "
            "Do not repeat the same values unless it makes sense contextually. "
            "For numeric fields, provide actual numbers. "
            "For text fields, provide descriptive, realistic values."
        )

        user = {
            "task": "Generate scenarios as a list of dictionaries",
            "request": user_request,
            "fields": fields,
            "count": count,
            "format": "Return a JSON object with a 'scenarios' key containing a list of dictionaries, each with the specified fields.",
            "examples": [
                {
                    "request": "Give me 3 fruits",
                    "output": {
                        "scenarios": [
                            {"fruit": "Apple"},
                            {"fruit": "Banana"},
                            {"fruit": "Orange"},
                        ]
                    },
                },
                {
                    "request": "Fruits and their colors",
                    "output": {
                        "scenarios": [
                            {"fruit": "Apple", "color": "Red"},
                            {"fruit": "Banana", "color": "Yellow"},
                            {"fruit": "Grape", "color": "Purple"},
                        ]
                    },
                },
            ],
        }

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, indent=2)},
            ],
            text_format=ScenariosReply,
            temperature=self.temperature,
        )

        out = resp.output_parsed
        # Convert Pydantic models to dictionaries
        return {"scenarios": [item.model_dump() for item in out.scenarios]}


# ---------- 4) Example usage ----------
if __name__ == "__main__":
    gen = ScenarioGenerator(model="gpt-4o", temperature=0.7)

    # Example 1: Simple list
    print("Example 1: Give me 5 fruits")
    result1 = gen.generate_scenarios("Give me 5 fruits")
    print(json.dumps(result1, indent=2))
    print()

    # Example 2: Multiple fields
    print("Example 2: Fruits and their colors")
    result2 = gen.generate_scenarios("Fruits and their colors", count=5)
    print(json.dumps(result2, indent=2))
    print()

    # Example 3: Complex request
    print("Example 3: Countries with capitals and populations")
    result3 = gen.generate_scenarios(
        "Countries with their capitals and populations", count=5
    )
    print(json.dumps(result3, indent=2))
    print()

    # Example 4: Researchers (similar to user's example)
    print("Example 4: Researchers studying different LLM topics")
    result4 = gen.generate_scenarios(
        "Researchers studying different aspects of LLMs", count=3
    )
    print(json.dumps(result4, indent=2))
