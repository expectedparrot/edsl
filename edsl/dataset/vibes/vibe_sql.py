"""
Dataset Vibe SQL: Generate SQL queries from natural language descriptions.

This module provides a VibeSQLGenerator class that can generate SQL queries
based on natural language descriptions of data queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import pandas as pd
import os
import json
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, Field
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


# ---------- 1) Pydantic schema for structured output ----------
class SQLQueryReply(BaseModel):
    query: str = Field(
        description=(
            "A SQL query string that operates on a table named 'self'. "
            "Use standard SQLite syntax. No backticks, no prose, just the query."
        )
    )
    note: Optional[str] = Field(
        default=None, description="Any brief explanation of the query logic."
    )


# ---------- 2) DataFrame → schema summary for SQL generation ----------
def summarize_df_for_sql(df: pd.DataFrame, sample_n: int = 3) -> Dict[str, Any]:
    """
    Produce a compact schema summary for the LLM to understand the data structure.

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe to summarize
    sample_n : int, default 3
        Number of sample rows to include

    Returns
    -------
    Dict[str, Any]
        Schema information including columns, types, and sample data
    """
    cols: List[Dict[str, Any]] = []
    for name in df.columns:
        s = df[name]
        dtype = str(s.dtype)

        # Get basic statistics for the column
        col_info: Dict[str, Any] = {
            "name": name,
            "dtype": dtype,
            "n_missing": int(s.isna().sum()),
        }

        # Add type-specific information
        if pd.api.types.is_numeric_dtype(s):
            col_info["role"] = "numeric"
            if s.notna().any():
                col_info["min"] = float(s.min())
                col_info["max"] = float(s.max())
                col_info["mean"] = float(s.mean())
        elif pd.api.types.is_datetime64_any_dtype(s):
            col_info["role"] = "datetime"
        elif pd.api.types.is_bool_dtype(s):
            col_info["role"] = "boolean"
        else:
            # Categorical or text
            nunique = s.nunique(dropna=True)
            col_info["role"] = "categorical" if nunique <= 20 else "text"
            if col_info["role"] == "categorical":
                # Show unique values for categorical columns
                unique_vals = s.dropna().unique().tolist()[:10]
                col_info["unique_values"] = unique_vals
                col_info["n_unique"] = nunique

        cols.append(col_info)

    schema = {
        "shape": list(df.shape),
        "columns": cols,
    }

    # Add sample rows for context
    if sample_n and sample_n > 0:
        sample_df = df.head(min(sample_n, len(df)))
        # Convert to string representation, truncating long values
        sample_records = []
        for _, row in sample_df.iterrows():
            record = {}
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    record[col] = None
                elif isinstance(val, str) and len(val) > 50:
                    record[col] = val[:50] + "..."
                else:
                    record[col] = val
            sample_records.append(record)
        schema["sample_data"] = sample_records

    return schema


# ---------- 3) The main SQL generator ----------
@dataclass
class VibeSQLGenerator:
    """
    Generate SQL queries from natural language descriptions.

    This class uses an LLM to generate SQL queries based on natural language
    descriptions. The queries operate on a table named 'self' containing the dataset.

    Parameters
    ----------
    model : str
        The OpenAI model to use (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.1 for consistent logic)

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame({'age': [25, 35, 42], 'occupation': ['student', 'engineer', 'teacher']})
    >>> gen = VibeSQLGenerator()  # doctest: +SKIP
    >>> query = gen.make_sql_query(df, "Show all people over 30")  # doctest: +SKIP
    >>> print(query)  # doctest: +SKIP
    SELECT * FROM self WHERE age > 30
    """

    model: str = "gpt-4o"
    temperature: float = 0.1

    def __post_init__(self):
        self.client = (
            create_openai_client()
        )  # reads OPENAI_API_KEY from env with proper error handling

    def make_sql_query(
        self,
        df: pd.DataFrame,
        user_request: str,
        *,
        sample_n: int = 3,
    ) -> str:
        """
        Generate a SQL query from a natural language request.

        Parameters
        ----------
        df : pandas.DataFrame
            The data whose schema will be shared with the LLM
        user_request : str
            Natural-language description of the desired query
            (e.g., "Show all people over 30", "Count by occupation", "Average age by city")
        sample_n : int, default 3
            Number of sample rows to include for context

        Returns
        -------
        str
            A SQL query string that operates on a table named 'self'

        Examples
        --------
        >>> import pandas as pd
        >>> df = pd.DataFrame({'age': [25, 35, 42], 'occupation': ['student', 'engineer', 'teacher']})
        >>> gen = VibeSQLGenerator()  # doctest: +SKIP
        >>> query = gen.make_sql_query(df, "Show all engineers")  # doctest: +SKIP
        """
        schema = summarize_df_for_sql(df, sample_n=sample_n)

        system = (
            "You are an expert SQL assistant specializing in SQLite queries. "
            "Output only SQL code (no Markdown, no ``` fences, no commentary). "
            "CRITICAL: All queries must operate on a table named 'self'. "
            "Use standard SQLite syntax. "
            "If a requested column is missing, pick the closest plausible alternative from the schema. "
            "Be concise and efficient: write clear, performant SQL. "
            "Common patterns:\n"
            "- Filtering: SELECT * FROM self WHERE column_name condition\n"
            "- Aggregation: SELECT column, COUNT(*) as count FROM self GROUP BY column\n"
            "- Ordering: SELECT * FROM self ORDER BY column DESC\n"
            "- Limiting: SELECT * FROM self LIMIT 10\n"
            "Use column names exactly as provided in the schema."
        )

        user = {
            "purpose": "Return ONLY a SQL query string that operates on a table named 'self'.",
            "request": user_request,
            "dataframe_schema": schema,
            "examples": [
                {
                    "ask": "Show all people over 30",
                    "ok": "SELECT * FROM self WHERE age > 30",
                },
                {
                    "ask": "Count how many people in each occupation",
                    "ok": "SELECT occupation, COUNT(*) as count FROM self GROUP BY occupation ORDER BY count DESC",
                },
                {
                    "ask": "Average age by city",
                    "ok": "SELECT city, AVG(age) as avg_age FROM self GROUP BY city",
                },
                {
                    "ask": "Top 5 highest salaries",
                    "ok": "SELECT * FROM self ORDER BY salary DESC LIMIT 5",
                },
            ],
        }

        # Use structured output to guarantee we can parse it cleanly.
        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, indent=2)},
            ],
            text_format=SQLQueryReply,
            temperature=self.temperature,
        )

        out: SQLQueryReply = resp.output_parsed
        query = out.query.strip()

        # Safety: ensure the query uses 'self' as the table name
        # This is a basic check - more sophisticated parsing could be added
        if "FROM self" not in query.upper() and "from self" not in query:
            # Try to fix common mistakes
            import re

            # Replace common table name patterns with 'self'
            query = re.sub(
                r"\bFROM\s+\w+\b", "FROM self", query, flags=re.IGNORECASE, count=1
            )

        return query


# ---------- 4) Example usage ----------
if __name__ == "__main__":
    # Fake data
    df = pd.DataFrame(
        {
            "age": [25, 35, 42, 28, 31],
            "occupation": ["student", "engineer", "teacher", "designer", "engineer"],
            "city": ["Boston", "San Francisco", "New York", "Austin", "Seattle"],
            "salary": [50000, 120000, 65000, 75000, 115000],
        }
    )

    gen = VibeSQLGenerator(model="gpt-4o", temperature=0.1)

    # Example 1: Simple filtering
    print("Example 1: Filter by age")
    query1 = gen.make_sql_query(df, "Show all people over 30")
    print(f"Query: {query1}")
    print()

    # Example 2: Aggregation
    print("Example 2: Count by occupation")
    query2 = gen.make_sql_query(df, "Count how many people in each occupation")
    print(f"Query: {query2}")
    print()

    # Example 3: Statistical query
    print("Example 3: Average salary by city")
    query3 = gen.make_sql_query(df, "What is the average salary in each city?")
    print(f"Query: {query3}")
    print()

    # Example 4: Ordering and limiting
    print("Example 4: Top earners")
    query4 = gen.make_sql_query(df, "Show me the top 3 highest paid people")
    print(f"Query: {query4}")
