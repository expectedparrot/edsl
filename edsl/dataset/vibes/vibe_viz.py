from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field
import os
import json
from dotenv import load_dotenv
from pathlib import Path
import html
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
class GGPlotReply(BaseModel):
    code: str = Field(
        description=(
            "An R code string that begins with 'ggplot(data = self, ...)' "
            "and can be pasted into an R session. No backticks, no prose."
        )
    )
    # Optional short tip (kept tiny to avoid verbosity). You can drop this field if you don't need it.
    note: Optional[str] = Field(default=None, description="Any brief caveat or hint.")


# ---------- 2) DataFrame → compact schema summary ----------
def summarize_df_for_llm(
    df: pd.DataFrame, max_levels: int = 12, sample_n: int = 0
) -> Dict[str, Any]:
    """
    Produce a compact, *non-sensitive* schema for the LLM (no full data).
    """
    cols: List[Dict[str, Any]] = []
    for name in df.columns:
        s = df[name]
        dtype = str(s.dtype)

        # Heuristic role
        if pd.api.types.is_numeric_dtype(s):
            role = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(s):
            role = "datetime"
        elif pd.api.types.is_bool_dtype(s):
            role = "binary"
        else:
            # treat as categorical if few unique values
            nunique = s.nunique(dropna=True)
            role = "categorical" if nunique <= max_levels else "text"

        info: Dict[str, Any] = {
            "name": name,
            "dtype": dtype,
            "role": role,
            "n_missing": int(s.isna().sum()),
        }

        if role == "numeric":
            info["min"] = (
                float(np.nanmin(s.values.astype("float64")))
                if s.notna().any()
                else None
            )
            info["max"] = (
                float(np.nanmax(s.values.astype("float64")))
                if s.notna().any()
                else None
            )
        elif role in ("categorical", "binary"):
            # small peek at levels
            lvls = (
                s.astype("string")
                .dropna()
                .value_counts()
                .head(max_levels)
                .index.tolist()
            )
            info["levels_preview"] = lvls

        cols.append(info)

    schema = {
        "shape": list(df.shape),
        "columns": cols,
    }

    if sample_n and sample_n > 0:
        # extremely tiny sample for context (strings only, truncated)
        tiny = (
            df.sample(min(sample_n, len(df)), random_state=0)
            .astype({c: "string" for c in df.columns})
            .fillna("NA")
            .applymap(lambda x: x[:80])
        )
        schema["tiny_sample"] = tiny.to_dict(orient="records")

    return schema


# ---------- 3) R Code Display Wrapper ----------
@dataclass
class RCodeDisplay:
    """
    Wrapper for R code with display options including syntax highlighting and copy functionality.

    In HTML/Jupyter environments, displays the code with syntax highlighting and a click-to-copy button.
    In terminal environments, displays the plain code string.

    Parameters
    ----------
    code : str
        The R code to display.
    show_code : bool, default True
        Whether to show the code. If False, returns empty string.

    Examples
    --------
    >>> r_code = "ggplot(data = self, aes(x = x, y = y)) + geom_point()"
    >>> display = RCodeDisplay(r_code)
    >>> # In Jupyter: displays with HTML formatting and copy button
    >>> # In terminal: displays plain code string
    >>> print(display)  # Always prints plain string
    ggplot(data = self, aes(x = x, y = y)) + geom_point()
    """

    code: str
    show_code: bool = True

    def _repr_html_(self) -> str:
        """
        Generate HTML representation with syntax highlighting and click-to-copy button.
        """
        if not self.show_code:
            return ""

        # Escape HTML special characters
        escaped_code = html.escape(self.code)

        # Generate a unique ID for this code block
        import random
        import string

        code_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

        # HTML with syntax highlighting (using CSS classes for R) and copy button
        html_output = f"""
        <div style="margin: 10px 0; font-family: monospace; position: relative;">
            <div style="background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px; padding: 10px; position: relative;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; border-bottom: 1px solid #ddd; padding-bottom: 8px;">
                    <span style="font-weight: bold; color: #666; font-size: 12px;">R CODE</span>
                    <button onclick="copyCode_{code_id}()" 
                            style="background: #4CAF50; color: white; border: none; padding: 4px 12px; border-radius: 3px; cursor: pointer; font-size: 11px; font-family: sans-serif;"
                            onmouseover="this.style.background='#45a049'" 
                            onmouseout="this.style.background='#4CAF50'"
                            id="copy_btn_{code_id}">
                        Copy
                    </button>
                </div>
                <pre id="code_{code_id}" style="margin: 0; overflow-x: auto; background: white; padding: 8px; border-radius: 3px;"><code class="language-r">{escaped_code}</code></pre>
            </div>
        </div>
        <script>
        function copyCode_{code_id}() {{
            const code = document.getElementById('code_{code_id}').textContent;
            navigator.clipboard.writeText(code).then(function() {{
                const btn = document.getElementById('copy_btn_{code_id}');
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                btn.style.background = '#2196F3';
                setTimeout(function() {{
                    btn.textContent = originalText;
                    btn.style.background = '#4CAF50';
                }}, 2000);
            }}, function(err) {{
                console.error('Failed to copy: ', err);
            }});
        }}
        </script>
        """
        return html_output

    def __repr__(self) -> str:
        """
        Plain text representation for terminal display.
        """
        if not self.show_code:
            return ""
        return self.code

    def __str__(self) -> str:
        """
        Return just the code string.
        """
        return self.code


# ---------- 4) The main generator ----------
@dataclass
class GGPlotGenerator:
    model: str = "gpt-4o"  # pick your preferred latest model
    temperature: float = 0.2

    def __post_init__(self):
        self.client = (
            create_openai_client()
        )  # reads OPENAI_API_KEY from env with proper error handling

    def make_plot_code(
        self,
        df: pd.DataFrame,
        user_request: str,
        *,
        sample_n: int = 0,
        return_display: bool = False,
        show_code: bool = True,
    ) -> str | RCodeDisplay:
        """
        Return an R ggplot2 string that *begins* with: ggplot(data = self, ...)

        Parameters
        ----------
        df : pandas.DataFrame
            The data whose *schema* will be shared.
        user_request : str
            Natural-language instructions from a ggplot2-savvy user
            (e.g., "plot price vs quantity, facet by market, color by year, use log scales").
        sample_n : int, default 0
            Optional tiny string-only sample row count to include for extra context.
        return_display : bool, default False
            If True, return an RCodeDisplay object with HTML formatting and copy button.
            If False, return the plain R code string.
        show_code : bool, default True
            If return_display is True, controls whether the code is displayed.
            Only relevant when return_display=True.

        Returns
        -------
        str or RCodeDisplay
            R code starting with ggplot(data = self, ...).
            If return_display=True, returns RCodeDisplay object with HTML support.
            If return_display=False, returns plain string.
        """
        schema = summarize_df_for_llm(df, sample_n=sample_n)

        system = (
            "You are an expert R/ggplot2 assistant. "
            "Output only R code (no Markdown, no ``` fences, no commentary). "
            "CRITICAL: The code must BEGIN with: ggplot(data = self, ...). "
            "Assume 'self' is an R data.frame with the provided columns. "
            "If a requested column is missing, pick the closest plausible alternative from the schema and proceed. "
            "Prefer tidyverse style. Do not call library()—assume ggplot2 and dplyr are already loaded. "
            "Be concise: include only what is necessary for the described plot. "
            "If faceting or grouping is requested, use facet_wrap/facet_grid and suitable aesthetics. "
            "Use aes() mappings with column names exactly as provided."
        )

        user = {
            "purpose": "Return ONLY a single R code string that begins with ggplot(data = self, ...).",
            "request": user_request,
            "dataframe_schema": schema,
            "examples": [
                {
                    "ask": "scatter price vs quantity with smooth and color by market",
                    "ok": "ggplot(data = self, aes(x = quantity, y = price, color = market)) + geom_point() + geom_smooth(se = FALSE, method = 'loess')",
                },
                {
                    "ask": "histogram of log(price) faceted by year",
                    "ok": "ggplot(data = self, aes(x = log(price))) + geom_histogram(bins = 30) + facet_wrap(~ year)",
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
            text_format=GGPlotReply,
            temperature=self.temperature,
        )

        out: GGPlotReply = resp.output_parsed
        code = out.code.strip()

        # Hard safety: enforce required prefix if the model forgets.
        if not code.startswith("ggplot(") and "ggplot(" in code:
            code = code[code.index("ggplot(") :].lstrip()
        if not code.startswith("ggplot(data = self"):
            # best-effort coercion: inject data = self if missing
            if code.startswith("ggplot("):
                code = code.replace("ggplot(", "ggplot(data = self, ", 1)

        if return_display:
            return RCodeDisplay(code=code, show_code=show_code)
        return code


# ---------- 5) Example usage ----------
if __name__ == "__main__":
    # Fake data
    df = pd.DataFrame(
        {
            "price": [10, 12, 9, 14],
            "quantity": [100, 120, 80, 140],
            "market": ["A", "B", "A", "B"],
            "year": [2022, 2022, 2023, 2023],
        }
    )

    gen = GGPlotGenerator(model="gpt-4o", temperature=0.1)
    request = "Plot price versus quantity with a loess smoother; color by market and facet by year."

    # Example 1: Return plain string (default behavior)
    r_code = gen.make_plot_code(df, request)
    print("Plain string output:")
    print(r_code)
    print()

    # Example 2: Return RCodeDisplay object (for HTML/Jupyter with copy button)
    r_code_display = gen.make_plot_code(df, request, return_display=True)
    print("Display object (shows fancy HTML in Jupyter, plain code in terminal):")
    print(r_code_display)
